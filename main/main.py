__version__ = "1.9.3"

import ctypes
import json
import logging
import os
import socket
import sys
import threading
import time
from datetime import datetime

import customtkinter as ctk

if sys.platform == "win32":
    import keyboard

from config import load_config, save_config, AppConfig
from log_setup import setup_logging, get_logger, set_level
from error_logger import log_exception
from scheduler import BalanceScheduler, BalanceResult
from event_bus import (
    EventBus,
    Event,
    EVENT_REFRESH_REQUESTED,
    EVENT_SETTINGS_CHANGED,
    EVENT_ACCOUNT_ADDED,
    EVENT_ACCOUNT_DELETED,
    EVENT_ACCOUNT_UPDATED,
)
from main_window import MainWindow
from floating_window import FloatingWindow
from instance_lock import InstanceLock
from animations import AnimationHelper
from balance_checker import BalanceStatus
from theme_manager import ThemeManager
from usage_history import UsageHistory
from usage_proxy import UsageProxy
# ISSUE-ARC-05：纯逻辑函数抽离到独立模块，便于无 GUI 环境单元测试
from shortcut_util import validate_shortcut_path as _validate_shortcut_path, create_shortcut as _create_shortcut

logger = get_logger(__name__)

ctk.set_default_color_theme("blue")

LOCK_NAME = "DeepSeekBalanceMonitor"
IPC_PORT = 52847


def _get_resource_path(relative_path: str) -> str:
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def _send_show_signal() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(("127.0.0.1", IPC_PORT))
        s.sendall(b"show")
        s.close()
        return True
    except Exception as e:
        log_exception("_send_show_signal", e)
        return False


def _get_startup_lnk_path() -> str:
    startup = os.path.join(
        os.getenv("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )
    return os.path.join(startup, "DeepSeekBalanceMonitor.lnk")


def _set_autostart(enable: bool):
    if sys.platform != "win32":
        return
    if not getattr(sys, "frozen", False):
        return
    lnk_path = _get_startup_lnk_path()
    if enable:
        _create_shortcut(lnk_path, sys.executable)
    else:
        try:
            os.remove(lnk_path)
        except FileNotFoundError:
            pass
        except Exception as e:
            log_exception("_set_autostart", e)


def _is_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    return os.path.exists(_get_startup_lnk_path())


ICON_PATH = _get_resource_path(os.path.join("assets", "icon.png"))
# ISSUE-THM-02：内置莫奈主题目录（打包需加入 PyInstaller datas，Phase C ISSUE-MIG-02 落实）
BUILTIN_THEMES_DIR = _get_resource_path("themes")


def _format_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


class App:
    """应用编排器：管理所有子系统的生命周期。

    职责：
    - 单实例互斥 + IPC 通信
    - 调度器/代理/历史记录的创建和销毁
    - 主窗口 ↔ 悬浮窗的切换
    - 系统托盘图标
    - 开机自启快捷方式
    """

    def __init__(self):
        # 日志系统必须最先初始化，确保后续所有模块可正常记录
        # 先用默认 INFO 初始化，加载配置后再根据 log_level 调整
        setup_logging(level="INFO", console=True)

        self._lock = InstanceLock(LOCK_NAME)
        if not self._lock.acquire():
            _send_show_signal()
            sys.exit(0)

        self._pending_show = False
        self._exiting = False
        self._last_update_time: float = 0
        # ISSUE-PFM-02：后台加载状态标记，避免退出时操作未初始化的子系统
        self._loaded = False
        self._load_error: str = ""

        # ISSUE-ARC-02：应用级事件总线，App 与各窗口/子系统解耦的中枢
        self.event_bus = EventBus()
        # ISSUE-THM-01：主题管理器（App 持有唯一实例并注入依赖方）
        self.theme_manager = ThemeManager(event_bus=self.event_bus)

        # ISSUE-PFM-02：先用空 AppConfig 创建 MainWindow，磁盘 IO 延迟到后台线程
        # 这样首屏渲染不等待 load_config / UsageHistory 建表 / UsageProxy 端口绑定
        self.config = AppConfig()
        # 应用默认主题模式（实际主题在后台加载配置后由 _on_loaded 应用）
        # ISSUE-THM-02：外观模式取 theme_mode（亮/暗），主题身份在 settings.theme
        ctk.set_appearance_mode(self.config.settings.theme_mode)
        AnimationHelper.set_ripple_color(self.config.settings.ripple_color)

        # 后台线程加载完成后填充的子系统（首屏时为 None）
        self.scheduler: BalanceScheduler | None = None
        self._usage_history: UsageHistory | None = None
        self._usage_proxy: UsageProxy | None = None
        self._proxy_url: str = ""
        self.main_window: MainWindow | None = None
        self.floating_window: FloatingWindow | None = None
        self._tray_icon = None
        self._tray_thread: threading.Thread | None = None

        # 全局热键不涉及磁盘 IO，可在 __init__ 中注册
        if sys.platform == "win32":
            try:
                keyboard.add_hotkey("ctrl+shift+b", self._toggle_window)
            except Exception as e:
                log_exception("App.__init__.keyboard", e)

    def _start_ipc_listener(self):
        def listen():
            import select
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", IPC_PORT))
            s.listen(1)
            # ISSUE-PFM-05：改用 select.select 替代 settimeout(1) 轮询
            # 原方案每秒唤醒一次（continue），导致闲置 CPU 基线 ~1%
            # select.select 在无连接时真正阻塞，仅在有连接或退出信号时唤醒
            while not self._exiting:
                try:
                    # 0.5s 超时用于定期检查 _exiting 标志
                    readable, _, _ = select.select([s], [], [], 0.5)
                    if not readable:
                        continue
                    conn, _addr = s.accept()
                    data = conn.recv(1024)
                    conn.close()
                    if data == b"show":
                        self._handle_show_signal()
                except Exception as e:
                    log_exception("_start_ipc_listener", e)
                    continue
            s.close()

        t = threading.Thread(target=listen, daemon=True)
        t.start()

    def _handle_show_signal(self):
        if self.main_window and self.main_window.winfo_exists():
            self.main_window.after(0, self._show_main)
        else:
            self._pending_show = True

    def _cleanup_lock(self):
        self._lock.release()

    def run(self):
        self.main_window = MainWindow(
            self.config,
            event_bus=self.event_bus,
            on_switch_to_floating=self._show_floating,
            on_apply_theme=self._apply_theme,
            # ISSUE-ARC-02：App→窗口的导航命令经构造注入（原 set_view_curve_callback 等）
            on_view_curve=self._on_view_curve,
            on_view_usage=self._on_view_usage,
        )
        self.main_window.title(f"DeepSeek 余额监控 v{__version__}")
        # ISSUE-ARC-02：一次性订阅窗口事件，替代加载期/加载后两轮 setter 换绑
        self._wire_events()
        # ISSUE-PFM-02：首屏空状态显示"加载中..."友好提示
        self.main_window.set_status("正在加载配置...")

        if self.config.settings.autostart:
            _set_autostart(True)

        # ISSUE-PFM-02：100ms 后启动后台加载线程，让首屏先完成渲染
        self.main_window.after(100, self._deferred_init)
        self.main_window.after(500, self.main_window.start_focus_monitor)
        # ISSUE-PFM-07：输出启动完成标记，供 measure_startup_time.py 检测真实启动耗时
        # 标记在 mainloop() 调用前输出（此时首屏已渲染、后台线程已提交）
        print("__STARTUP_DONE__", flush=True)
        self.main_window.mainloop()

    def _wire_events(self):
        """ISSUE-ARC-02：订阅 MainWindow 发布的事件，替代 6 个 setter 回调注入。

        刷新/设置在加载期与加载完成后行为不同，统一在 handler 内按
        scheduler 是否就绪分派（PFM-02 状态门模式），不再反复换绑回调。
        """
        bus = self.event_bus
        bus.subscribe(EVENT_REFRESH_REQUESTED, self._on_refresh_requested)
        bus.subscribe(EVENT_SETTINGS_CHANGED, self._on_settings_changed)
        bus.subscribe(EVENT_ACCOUNT_ADDED, self._on_accounts_changed)
        bus.subscribe(EVENT_ACCOUNT_UPDATED, self._on_accounts_changed)
        bus.subscribe(EVENT_ACCOUNT_DELETED, self._on_accounts_changed)

    def _on_refresh_requested(self, event: Event):
        """刷新请求：调度器就绪则刷新，否则忽略（原 _on_manual_refresh_during_load）。"""
        if self.scheduler is not None:
            self.scheduler.refresh_all_now()
        else:
            logger.info("配置尚未加载完成，刷新请求已忽略")

    def _on_settings_changed(self, event: Event):
        """设置变更：分派给调度器并落盘（原 _on_settings_during_load + autostart/save 回调）。"""
        payload = event.payload
        interval = int(payload.get("interval") or 0)
        autostart = payload.get("autostart")
        if self.scheduler is not None:
            self.scheduler.set_settings(interval, autostart)
        else:
            self.config.settings.interval_sec = max(10, interval)
            logger.info("配置尚未加载完成，间隔设置已暂存")
        _set_autostart(bool(autostart))
        save_config(self.config)

    def _on_accounts_changed(self, event: Event):
        """账户增删改/排序：统一落盘（原 set_save_callback 的 lambda）。"""
        save_config(self.config)

    def _deferred_init(self):
        """启动后台加载线程 + 托盘图标。"""
        # ISSUE-PFM-02：后台线程执行磁盘 IO（load_config / 建表 / 端口绑定）
        threading.Thread(target=self._background_init, daemon=True, name="AppInit").start()
        self._start_tray()

    def _background_init(self):
        """ISSUE-PFM-02：后台加载配置 + 建表 + 启动代理 + 启动调度器。

        所有磁盘 IO 与端口绑定在此后台线程执行，不阻塞主线程 UI 渲染。
        加载完成后通过 after(0, ...) 回到主线程更新 UI。
        """
        try:
            # 1. 加载配置（磁盘读 + DPAPI 解密）
            loaded_config = load_config()
            self.config = loaded_config
            # 应用配置中的日志级别
            set_level(loaded_config.settings.log_level)
            logger.info("应用启动，版本 %s，日志级别 %s", __version__, loaded_config.settings.log_level)

            # 1.5 ISSUE-THM-02：加载内置莫奈主题（3 个小 JSON，随包分发）
            self.theme_manager.load_directory(BUILTIN_THEMES_DIR)

            # 2. 创建 UsageHistory（SQLite 建表，磁盘 IO）
            self._usage_history = UsageHistory()

            # 3. 创建并启动 UsageProxy（端口绑定）
            self._usage_proxy = UsageProxy(
                target_host=loaded_config.settings.proxy_target,
                proxy_token_enc=loaded_config.settings.proxy_token_enc,
            )
            # 启动后若生成了新 token，回写配置
            if self._usage_proxy.token_enc_changed:
                loaded_config.settings.proxy_token_enc = self._usage_proxy.proxy_token_enc
                save_config(loaded_config)
            self._usage_proxy.start()
            self._proxy_url = self._usage_proxy.proxy_url

            # 4. 创建调度器并注册回调
            self.scheduler = BalanceScheduler(loaded_config)
            self.scheduler.on_result(self._on_balance_result)

            # 5. 启动 IPC 监听 + 调度器
            self._start_ipc_listener()
            self.scheduler.start()

            # 6. 回到主线程更新 UI
            if self.main_window and self.main_window.winfo_exists():
                self.main_window.after(0, self._on_loaded)
        except Exception as e:
            logger.exception("后台加载失败：%s", e)
            self._load_error = str(e)
            if self.main_window and self.main_window.winfo_exists():
                self.main_window.after(0, self._on_load_failed)

    def _on_loaded(self):
        """ISSUE-PFM-02：后台加载完成，主线程更新 UI。

        - 更新 MainWindow 持有的 config 引用并重建账户列表
        - 应用配置中的主题
        - 设置代理 URL 状态
        - 触发首次刷新
        """
        self._loaded = True
        if not self.main_window or not self.main_window.winfo_exists():
            return

        # 更新 MainWindow 的 config 引用并重建账户列表
        self.main_window._config = self.config
        self.main_window._rebuild_account_list()
        # ISSUE-ARC-02：刷新/设置已改事件订阅（_wire_events 一次性接线），加载后无需换绑
        # ISSUE-SEC-04：注入 token 提供者，供设置面板展示 token hash
        self.main_window.set_proxy_token_provider(self._usage_proxy.get_proxy_token)

        # 应用配置中的主题（ISSUE-THM-02：外观模式 theme_mode，身份 theme 同步给 ThemeManager）
        ctk.set_appearance_mode(self.config.settings.theme_mode)
        AnimationHelper.set_ripple_color(self.config.settings.ripple_color)
        self.theme_manager.apply(self.config.settings.theme, mode=self.config.settings.theme_mode)

        # 更新状态栏显示代理 URL
        proxy_info = f"代理: {self._proxy_url}" if self._proxy_url else "就绪"
        self.main_window.set_status(proxy_info)

        # 触发首次刷新
        if self.config.accounts:
            self.scheduler.refresh_all_now()

    def _on_load_failed(self):
        """ISSUE-PFM-02：后台加载失败，主线程显示错误状态（不崩溃）。"""
        self._loaded = False
        if self.main_window and self.main_window.winfo_exists():
            self.main_window.set_status(f"加载失败: {self._load_error}")
            logger.error("应用启动加载失败，UI 显示错误状态：%s", self._load_error)

    def _apply_theme(self, mode: str):
        """应用主题变更（设置对话框触发）。

        ISSUE-THM-02：对话框在 Phase D 前返回 dark/light，这是亮暗模式而非主题身份，
        写入 theme_mode；主题身份 settings.theme 不再被旧值覆盖。
        ThemeManager 同步状态并广播 theme_changed（Phase D 前无订阅方，仅状态记录）。
        """
        ctk.set_appearance_mode(mode)
        self.config.settings.theme_mode = mode
        if self.theme_manager is not None:
            self.theme_manager.apply(self.config.settings.theme, mode=mode)
        save_config(self.config)

    def _on_balance_result(self, result: BalanceResult):
        """调度器回调：记录余额快照 + 更新 UI（线程安全地 post 到主线程）。"""
        if self._exiting:
            return
        self._record_balance_snapshot(result)
        if self.main_window and self.main_window.winfo_exists():
            self.main_window.after(0, self._update_ui, result)

    def _record_balance_snapshot(self, result: BalanceResult):
        """将余额快照写入 SQLite，供余额趋势图和消耗计算使用。"""
        if result.info.status != BalanceStatus.OK or not result.info.balances:
            return
        acc = next((a for a in self.config.accounts if a.uid == result.uid), None)
        if not acc:
            return
        import hashlib
        key_hash = hashlib.md5(acc.api_key.encode()).hexdigest()[:16]
        for b in result.info.balances:
            try:
                val = float(b.total_balance)
            except (ValueError, TypeError):
                continue
            self._usage_history.record_balance_snapshot(
                uid=result.uid,
                api_key_hash=key_hash,
                balance=val,
                currency=b.currency,
            )

    def _update_ui(self, result: BalanceResult):
        if self.main_window:
            self.main_window.update_account_balance(result)
        self._last_update_time = result.timestamp

        self._refresh_floating()

        if self.main_window:
            self.main_window.set_status(f"上次更新: {_format_time(self._last_update_time)}")

    def _on_view_curve(self, account):
        # ISSUE-PFM-02：加载未完成时 usage_history 可能为 None
        if self._usage_history is None:
            logger.warning("用量历史尚未加载完成，无法打开趋势图")
            return
        if self.main_window and self.main_window.winfo_exists():
            from usage_curve_window import BalanceCurveWindow
            BalanceCurveWindow(
                self.main_window,
                account_label=account.label,
                api_key=account.api_key,
                uid=account.uid,
                history=self._usage_history,
            )

    def _on_view_usage(self):
        # ISSUE-PFM-02：加载未完成时 usage_history 可能为 None
        if self._usage_history is None:
            logger.warning("用量历史尚未加载完成，无法打开用量概览")
            return
        if self.main_window and self.main_window.winfo_exists():
            from usage_bar_window import UsageBarWindow
            UsageBarWindow(
                self.main_window,
                history=self._usage_history,
                accounts=self.config.accounts,
            )

    def _toggle_window(self):
        if self._exiting:
            return
        if self.main_window and self.main_window.winfo_exists():
            if self.main_window.state() == "withdrawn":
                self.main_window.after(0, self._show_main)
            else:
                self.main_window.after(0, self._on_minimize_to_floating_safe)

    def _on_minimize_to_floating_safe(self):
        if self.main_window and self.main_window.winfo_exists():
            self.main_window._on_minimize_to_floating()

    def _refresh_floating(self):
        if not self.floating_window or not self.floating_window.winfo_exists():
            return

        # 所有 config.json 中的账户均视为活跃账户
        active_uids = {acc.uid for acc in self.config.accounts}
        results = self.scheduler.last_results
        active_parts = []
        other_parts = []
        available_count = 0
        for uid, r in results.items():
            if r.info.status.value == "ok" and r.info.is_available:
                available_count += 1
                display = r.info.total_display
                if uid in active_uids:
                    active_parts.append(display)
                else:
                    other_parts.append(display)

        all_parts = active_parts + other_parts
        total_display = " | ".join(all_parts) if all_parts else "暂无可用余额"
        status = f"更新于 {_format_time(self._last_update_time)}"

        self.floating_window.update_balance(
            total_display,
            available_count,
            status,
        )

    def _show_floating(self):
        if self.floating_window and self.floating_window.winfo_exists():
            self.floating_window.deiconify()
            self.floating_window.lift()
            self.floating_window.focus()
            self._refresh_floating()
            return

        self.floating_window = FloatingWindow(
            on_restore=self._show_main,
            on_refresh=self.scheduler.refresh_all_now,
            on_exit=self._quit,
        )
        self.floating_window.protocol("WM_DELETE_WINDOW", self._on_floating_close)
        self._init_floating_position()
        self._refresh_floating()

    def _init_floating_position(self):
        if self.floating_window:
            self.floating_window.set_position(self.config.window)

    def _show_main(self):
        # 主动销毁悬浮窗而非 withdraw，释放其 tkinter 资源；
        # 下次切回悬浮窗时 _show_floating 会重建
        if self.floating_window:
            if self.floating_window.winfo_exists():
                self.config.window = self.floating_window.get_position()
                save_config(self.config)
            self.floating_window.destroy()
            self.floating_window = None

        if self.main_window:
            self.main_window.deiconify()
            self.main_window.lift()
            self.main_window.focus()
            self.main_window.after(200, self.main_window.start_focus_monitor)

    def _on_floating_close(self):
        if self.floating_window and self.floating_window.winfo_exists():
            self.config.window = self.floating_window.get_position()
        self._quit()

    def _save_window_position(self):
        if self.floating_window and self.floating_window.winfo_exists():
            self.config.window = self.floating_window.get_position()

    def _start_tray(self):
        try:
            from PIL import Image
            import pystray

            if not os.path.exists(ICON_PATH):
                return

            image = Image.open(ICON_PATH)

            def on_show(icon, item):
                icon.stop()
                if self.main_window:
                    self.main_window.after(0, self._show_main)

            def on_exit(icon, item):
                icon.stop()
                self._quit()

            menu = pystray.Menu(
                pystray.MenuItem("显示主窗口", on_show, default=True),
                pystray.MenuItem("退出", on_exit),
            )

            self._tray_icon = pystray.Icon("deepseek_monitor", image, "DeepSeek 余额监控", menu)

            self._tray_thread = threading.Thread(target=self._tray_icon.run, daemon=True)
            self._tray_thread.start()
        except ImportError:
            pass
        except Exception as e:
            log_exception("_start_tray", e)

    def _quit(self):
        self._exiting = True
        self._save_window_position()
        save_config(self.config)
        # ISSUE-PFM-02：加载未完成时退出，scheduler/proxy 可能为 None
        if self.scheduler is not None:
            self.scheduler.stop()

        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception as e:
                log_exception("_quit.tray_stop", e)

        try:
            if self.main_window:
                self.main_window.prepare_exit()
                self.main_window.destroy()
            if self.floating_window and self.floating_window.winfo_exists():
                self.floating_window.destroy()
        except Exception as e:
            log_exception("_quit.window_destroy", e)

        if self._usage_proxy is not None:
            self._usage_proxy.stop()
        # ISSUE-PFM-04：关闭所有 Provider 的 Session，释放连接池资源
        try:
            from balance_checker import close_all_provider_sessions
            close_all_provider_sessions()
        except Exception as e:
            log_exception("_quit.close_provider_sessions", e)
        self._cleanup_lock()
        if sys.platform == "win32":
            try:
                keyboard.unhook_all()
            except Exception as e:
                log_exception("_quit.keyboard_unhook", e)
        # ISSUE-LOG-03：默认改用 sys.exit 优雅退出，--force-exit 应急开关保留 os._exit
        if "--force-exit" in sys.argv:
            logger.warning("检测到 --force-exit 开关，使用 os._exit 强制退出")
            os._exit(0)
        else:
            sys.exit(0)


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
