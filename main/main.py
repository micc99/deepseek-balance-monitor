# ISSUE-MIG-08：注解延迟求值（启动异步化后 Manager 类型仅作 TYPE_CHECKING 注解）
from __future__ import annotations

__version__ = "1.9.3-mig"

import os
import sys
import threading

from PySide6.QtWidgets import QApplication

from config import load_config, save_config, AppConfig
from log_setup import setup_logging, get_logger, set_level
from error_logger import log_exception
from event_bus import (
    EventBus,
    Event,
    EVENT_REFRESH_REQUESTED,
    EVENT_SETTINGS_CHANGED,
    EVENT_ACCOUNT_ADDED,
    EVENT_ACCOUNT_DELETED,
    EVENT_ACCOUNT_UPDATED,
)
from managers.lifecycle_manager import LifecycleManager
from managers.tray_manager import TrayManager
from managers.hotkey_manager import HotkeyManager
from managers.autostart_manager import AutostartManager
from managers.theme_coordinator import ThemeCoordinator
from managers.window_manager import WindowManager

# ISSUE-MIG-08 启动异步化：scheduler/proxy/balance_checker 链含 requests
# （实测 import ~345ms），推迟到后台线程加载，冷启动不为其买单。
# 类型仅用于注解，运行时不触发 import：
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from balance_checker import set_provider_event_bus
    from managers.scheduler_manager import SchedulerManager
    from managers.proxy_manager import ProxyManager
    from usage_history import UsageHistory

logger = get_logger(__name__)

LOCK_NAME = "DeepSeekBalanceMonitor"
IPC_PORT = 52847


def _get_resource_path(relative_path: str) -> str:
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


ICON_PATH = _get_resource_path(os.path.join("assets", "icon.png"))
# ISSUE-THM-02：内置莫奈主题目录（ISSUE-MIG-08 打包加入 PyInstaller datas）
BUILTIN_THEMES_DIR = _get_resource_path("themes")


class App:
    """应用编排器（ISSUE-ARC-01 / ISSUE-MIG-02 Qt 化）：实例化 Manager 并连接事件。

    职责归属：Lifecycle=锁+IPC / WindowManager=双窗+图表窗+余额UI /
    ThemeCoordinator=主题→QSS / Tray·Hotkey·Autostart=托盘热键自启 /
    SchedulerManager·ProxyManager=调度代理（后台加载后创建，PFM-02 门）。
    """

    def __init__(self):
        # 日志系统必须最先初始化
        setup_logging(level="INFO", console=True)

        self.lifecycle = LifecycleManager(LOCK_NAME, IPC_PORT)
        if not self.lifecycle.acquire():
            self.lifecycle.signal_show()
            sys.exit(0)

        # QApplication 先于任何控件创建
        self.qt_app = QApplication.instance() or QApplication(sys.argv)

        self._exiting = False
        # ISSUE-PFM-02：后台加载状态门——以下两者加载完成前为 None
        self._loaded = False
        self._load_error: str = ""
        self.scheduler_manager: SchedulerManager | None = None
        self.proxy_manager: ProxyManager | None = None
        self._usage_history: UsageHistory | None = None
        self.tray: TrayManager | None = None

        self.config = AppConfig()

        # ISSUE-ARC-02：应用级事件总线
        self.event_bus = EventBus()
        # ISSUE-ARC-06：Provider 注册表广播接线在 _background_init 中
        # （set_provider_event_bus 所在模块链含 requests，随启动异步化推迟）
        # ISSUE-THM-01/MIG-02：主题协调器（内置主题同步加载，保证首帧 QSS 正确；
        # 三个小 JSON 约 1ms，不构成 PFM-02 延迟加载的对象——那是给建表/端口留的）
        self.theme = ThemeCoordinator(self.event_bus, self.qt_app)
        self.theme.load(BUILTIN_THEMES_DIR)
        self.theme.apply_startup(self.config)

        # ISSUE-ARC-01：Manager 依赖注入（访问器而非 App 引用）
        self.autostart = AutostartManager()
        self.hotkeys = HotkeyManager()
        self.windows = WindowManager(
            config_provider=lambda: self.config,
            get_last_results=lambda: self.scheduler_manager.scheduler.last_results if self.scheduler_manager else {},
            get_refresh_now=lambda: self.scheduler_manager.refresh_now if self.scheduler_manager else None,
            get_history=lambda: self._usage_history,
            on_exit=self._quit,
            event_bus=self.event_bus,
        )
        self.hotkeys.register_toggle(
            self.windows.toggle,
            self.config.settings.hotkeys.get("toggle_window", "<ctrl>+<shift>+b"),
        )

    # ---- 启动流程 ----

    def run(self):
        self.windows.create_main_window(
            event_bus=self.event_bus,
            on_switch_to_floating=self.windows.show_floating,
            on_apply_theme=lambda mode: self.theme.apply_mode(mode, self.config),
            on_view_curve=self.windows.open_curve_window,
            on_view_usage=self.windows.open_usage_window,
            version_title=f"DeepSeek 余额监控 v{__version__}",
        )
        self._wire_events()
        self.windows.set_status("正在加载配置...")
        if self.config.settings.autostart:
            self.autostart.set(True)
        # ISSUE-PFM-02：100ms 后后台加载（首屏先渲染）；500ms 后启动焦点监视
        self.windows.main_window.after(100, self._deferred_init)
        self.windows.main_window.after(500, self.windows.main_window.start_focus_monitor)
        # ISSUE-PFM-07：启动完成标记，供 measure_startup_time.py 检测
        print("__STARTUP_DONE__", flush=True)
        self.windows.main_window.show()
        self.qt_app.exec()

    def _wire_events(self):
        """ISSUE-ARC-02：订阅 MainWindow 事件，按 scheduler 就绪状态分派。"""
        bus = self.event_bus
        bus.subscribe(EVENT_REFRESH_REQUESTED, self._on_refresh_requested)
        bus.subscribe(EVENT_SETTINGS_CHANGED, self._on_settings_changed)
        bus.subscribe(EVENT_ACCOUNT_ADDED, self._on_accounts_changed)
        bus.subscribe(EVENT_ACCOUNT_UPDATED, self._on_accounts_changed)
        bus.subscribe(EVENT_ACCOUNT_DELETED, self._on_accounts_changed)

    def _on_refresh_requested(self, event: Event):
        if self.scheduler_manager is not None:
            self.scheduler_manager.refresh_now()
        else:
            logger.info("配置尚未加载完成，刷新请求已忽略")

    def _on_settings_changed(self, event: Event):
        payload = event.payload
        interval = int(payload.get("interval") or 0)
        autostart = payload.get("autostart")
        if self.scheduler_manager is not None:
            self.scheduler_manager.set_settings(interval, autostart)
        else:
            self.config.settings.interval_sec = max(10, interval)
            logger.info("配置尚未加载完成，间隔设置已暂存")
        self.autostart.set(bool(autostart))
        # ISSUE-UX-02：全局热键重注册（配置可能已变更）
        self.hotkeys.register_toggle(
            self.windows.toggle,
            payload.get("hotkeys", {}).get(
                "toggle_window", self.config.settings.hotkeys.get("toggle_window", "<ctrl>+<shift>+b")),
        )
        save_config(self.config)

    def _on_accounts_changed(self, event: Event):
        save_config(self.config)

    def _deferred_init(self):
        threading.Thread(target=self._background_init, daemon=True, name="AppInit").start()
        self.tray = TrayManager(ICON_PATH, "DeepSeek 余额监控", self._on_tray_show, self._quit)
        self.tray.start()

    def _on_tray_show(self):
        if self.windows.main_window:
            self.windows.main_window.after(0, self.windows.show_main)

    def _background_init(self):
        """ISSUE-PFM-02：磁盘 IO/建表/端口绑定全部在此后台线程执行。

        ISSUE-MIG-08 启动异步化：requests 链（scheduler/proxy/balance_checker/
        usage_history）的重 import 也在本线程完成，冷启动不为其买单。
        """
        try:
            from balance_checker import set_provider_event_bus
            from managers.proxy_manager import ProxyManager
            from managers.scheduler_manager import SchedulerManager
            from usage_history import UsageHistory

            # ISSUE-ARC-06：Provider 注册表广播接线（此处 requests 链已就绪）
            set_provider_event_bus(self.event_bus)

            loaded_config = load_config()
            self.config = loaded_config
            set_level(loaded_config.settings.log_level)
            logger.info("应用启动，版本 %s，日志级别 %s", __version__, loaded_config.settings.log_level)

            self._usage_history = UsageHistory()
            self.theme.load_user()
            self.theme.sync_config(loaded_config)

            self.proxy_manager = ProxyManager()
            self.proxy_manager.start(loaded_config)
            if self.proxy_manager.token_enc_changed:
                loaded_config.settings.proxy_token_enc = self.proxy_manager.proxy_token_enc
                save_config(loaded_config)

            self.scheduler_manager = SchedulerManager(loaded_config, self._usage_history)
            self.scheduler_manager.start(self._on_balance_result)

            self.lifecycle.start_listener(self.windows.handle_show_signal)

            if self.windows.main_window and self.windows.main_window.winfo_exists():
                self.windows.main_window.after(0, self._on_loaded)
        except Exception as e:
            logger.exception("后台加载失败：%s", e)
            self._load_error = str(e)
            if self.windows.main_window and self.windows.main_window.winfo_exists():
                self.windows.main_window.after(0, self._on_load_failed)

    def _on_loaded(self):
        self._loaded = True
        if not self.windows.main_window or not self.windows.main_window.winfo_exists():
            return
        self.windows.rebind_loaded_config(self.proxy_manager.get_proxy_token)
        self.theme.apply_startup(self.config)
        proxy_info = f"代理: {self.proxy_manager.proxy_url}" if self.proxy_manager.proxy_url else "就绪"
        self.windows.set_status(proxy_info)
        if self.config.accounts:
            self.scheduler_manager.refresh_now()

    def _on_load_failed(self):
        self._loaded = False
        self.windows.set_status(f"加载失败: {self._load_error}")
        logger.error("应用启动加载失败，UI 显示错误状态：%s", self._load_error)

    def _on_balance_result(self, result):
        """调度器回调（后台线程）：记录快照 + 经 after(0) 回主线程更新 UI。"""
        if self._exiting:
            return
        self.scheduler_manager.record_snapshot(result)
        self.windows.post_balance_update(result)

    def _quit(self):
        self._exiting = True
        self.windows.save_floating_position()
        save_config(self.config)
        if self.scheduler_manager is not None:
            self.scheduler_manager.stop()
        if self.tray is not None:
            self.tray.stop()
        self.windows.destroy_for_exit()
        if self.proxy_manager is not None:
            self.proxy_manager.stop()
        if self._usage_history is not None:
            self._usage_history.close()  # ISSUE-PFM-08
        try:
            from balance_checker import close_all_provider_sessions
            close_all_provider_sessions()
        except Exception as e:
            log_exception("_quit.close_provider_sessions", e)
        self.lifecycle.stop_listener()
        self.lifecycle.release()
        self.hotkeys.unregister()
        # ISSUE-LOG-03：--force-exit 应急开关保留 os._exit；否则收尾后退出事件循环
        if "--force-exit" in sys.argv:
            logger.warning("检测到 --force-exit 开关，使用 os._exit 强制退出")
            os._exit(0)
        self.qt_app.quit()  # 线程安全：exec() 返回后进程正常结束


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
