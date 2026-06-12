__version__ = "1.9"

import ctypes
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime

import customtkinter as ctk
import keyboard

from config import load_config, save_config
from scheduler import BalanceScheduler, BalanceResult
from main_window import MainWindow
from floating_window import FloatingWindow
from instance_lock import InstanceLock
from animations import AnimationHelper
from balance_checker import BalanceStatus
from usage_history import UsageHistory
from usage_curve_window import BalanceCurveWindow
from usage_bar_window import UsageBarWindow
from usage_proxy import UsageProxy

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
    except Exception:
        return False


def _get_startup_lnk_path() -> str:
    startup = os.path.join(
        os.getenv("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )
    return os.path.join(startup, "DeepSeekBalanceMonitor.lnk")


def _create_shortcut(lnk_path: str, target: str):
    import subprocess
    escaped_lnk = lnk_path.replace("'", "''")
    escaped_target = target.replace("'", "''")
    ps_script = (
        f"$WshShell = New-Object -ComObject WScript.Shell; "
        f"$Shortcut = $WshShell.CreateShortcut('{escaped_lnk}'); "
        f"$Shortcut.TargetPath = '{escaped_target}'; "
        f"$Shortcut.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=10)


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
        except Exception:
            pass


def _is_autostart_enabled() -> bool:
    if sys.platform != "win32":
        return False
    return os.path.exists(_get_startup_lnk_path())


def _load_active_keys() -> set[str]:
    if sys.platform != "win32":
        return set()
    candidates = [
        os.path.join(os.path.expandvars("%USERPROFILE%"), "Desktop", "auth.json"),
        os.path.join(os.path.expandvars("%USERPROFILE%"), ".local", "share", "opencode", "auth.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return {
                    entry["key"]
                    for entry in data.values()
                    if isinstance(entry, dict) and "key" in entry
                }
            except Exception:
                continue
    return set()

ICON_PATH = _get_resource_path(os.path.join("assets", "icon.png"))


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
        self._lock = InstanceLock(LOCK_NAME)
        if not self._lock.acquire():
            _send_show_signal()
            sys.exit(0)

        self._pending_show = False
        self._exiting = False
        self._last_update_time: float = 0

        self.config = load_config()
        theme = self.config.settings.theme
        ctk.set_appearance_mode(theme)
        AnimationHelper.set_ripple_color(self.config.settings.ripple_color)

        self.scheduler = BalanceScheduler(self.config)
        self._active_keys: set[str] = _load_active_keys()
        self._usage_history = UsageHistory()
        # 代理目标从配置读取，用户可在设置中切换 provider（需重启生效）
        self._usage_proxy = UsageProxy(target_host=self.config.settings.proxy_target)
        self._usage_proxy.start()
        try:
            keyboard.add_hotkey("ctrl+shift+b", self._toggle_window)
        except Exception:
            pass
        self._proxy_url = self._usage_proxy.proxy_url
        self.main_window: MainWindow | None = None
        self.floating_window: FloatingWindow | None = None
        self._tray_icon = None
        self._tray_thread: threading.Thread | None = None

    def _start_ipc_listener(self):
        def listen():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", IPC_PORT))
            s.listen(1)
            s.settimeout(1)
            while not self._exiting:
                try:
                    conn, _addr = s.accept()
                    data = conn.recv(1024)
                    conn.close()
                    if data == b"show":
                        self._handle_show_signal()
                except socket.timeout:
                    continue
                except Exception:
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
            on_switch_to_floating=self._show_floating,
            on_apply_theme=self._apply_theme,
        )
        self.main_window.title(f"DeepSeek 余额监控 v{__version__}")
        self.main_window.set_refresh_callback(self.scheduler.refresh_all_now)
        self.main_window.set_settings_callback(self.scheduler.set_settings)
        self.main_window.set_autostart_callback(_set_autostart)
        self.main_window.set_save_callback(lambda: save_config(self.config))
        self.main_window.set_view_curve_callback(self._on_view_curve)
        self.main_window.set_view_usage_callback(self._on_view_usage)

        if self.config.settings.autostart:
            _set_autostart(True)

        self.main_window.after(100, self._deferred_init)
        self.main_window.after(500, self.main_window.start_focus_monitor)
        self.main_window.mainloop()

    def _deferred_init(self):
        threading.Thread(target=self._background_init, daemon=True).start()
        self._start_tray()
        if self.main_window and self.main_window.winfo_exists():
            proxy_info = f"代理: {self._proxy_url}"
            self.main_window.set_status(proxy_info)

    def _background_init(self):
        self._start_ipc_listener()
        self.scheduler.on_result(self._on_balance_result)
        self.scheduler.start()
        if self.config.accounts:
            self.scheduler.refresh_all_now()

    def _apply_theme(self, theme: str):
        ctk.set_appearance_mode(theme)
        self.config.settings.theme = theme
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
        if self.main_window and self.main_window.winfo_exists():
            BalanceCurveWindow(
                self.main_window,
                account_label=account.label,
                api_key=account.api_key,
                uid=account.uid,
                history=self._usage_history,
            )

    def _on_view_usage(self):
        if self.main_window and self.main_window.winfo_exists():
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

        active_uids = {
            acc.uid for acc in self.config.accounts if acc.api_key in self._active_keys
        }
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
        except Exception:
            pass

    def _quit(self):
        self._exiting = True
        self._save_window_position()
        save_config(self.config)
        self.scheduler.stop()

        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass

        try:
            if self.main_window:
                self.main_window.prepare_exit()
                self.main_window.destroy()
            if self.floating_window and self.floating_window.winfo_exists():
                self.floating_window.destroy()
        except Exception:
            pass

        self._usage_proxy.stop()
        self._cleanup_lock()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        os._exit(0)


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
