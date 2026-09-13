from __future__ import annotations

import os
import threading

from error_logger import log_exception


"""系统托盘管理（ISSUE-ARC-01，原 App._start_tray/_quit 托盘段收编）。

pystray 在独立线程运行事件循环；on_show/on_exit 由 pystray 线程回调，
UI 操作由调用方自行 after(0) 调度回主线程。
"""

logger = __import__("logging").getLogger(__name__)


class TrayManager:
    """系统托盘图标与菜单。"""

    def __init__(self, icon_path: str, title: str, on_show, on_exit):
        self._icon_path = icon_path
        self._title = title
        self._on_show = on_show
        self._on_exit = on_exit
        self._icon = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """创建托盘图标并启动事件线程；图标缺失/pystray 缺失均静默降级。"""
        try:
            from PIL import Image
            import pystray

            if not os.path.exists(self._icon_path):
                return

            image = Image.open(self._icon_path)

            def on_show(icon, item):
                icon.stop()
                self._on_show()

            def on_exit(icon, item):
                icon.stop()
                self._on_exit()

            menu = pystray.Menu(
                pystray.MenuItem("显示主窗口", on_show, default=True),
                pystray.MenuItem("退出", on_exit),
            )
            self._icon = pystray.Icon("deepseek_monitor", image, self._title, menu)
            self._thread = threading.Thread(target=self._icon.run, daemon=True, name="TrayIcon")
            self._thread.start()
        except ImportError:
            pass
        except Exception as e:
            log_exception("TrayManager.start", e)

    def stop(self) -> None:
        """停止托盘事件循环（App._quit 调用；幂等）。"""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as e:
                log_exception("TrayManager.stop", e)
            self._icon = None
