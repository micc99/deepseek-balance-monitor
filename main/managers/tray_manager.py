from __future__ import annotations

import os

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


"""系统托盘管理（Qt 版，ISSUE-MIG-06）。

QSystemTrayIcon 必须在主线程创建（App._deferred_init 经 after(0) 在
主线程调用 start，替代 pystray 的独立事件线程）。左键单击 = 显示主窗口
（对应 pystray default 菜单项语义），右键菜单含显示/退出。
"""


class TrayManager:
    """系统托盘图标与菜单。"""

    def __init__(self, icon_path: str, title: str, on_show, on_exit):
        self._icon_path = icon_path
        self._title = title
        self._on_show = on_show
        self._on_exit = on_exit
        self._icon: QSystemTrayIcon | None = None

    def start(self) -> None:
        """创建托盘图标；图标文件缺失/不可用时静默降级。"""
        try:
            if not os.path.exists(self._icon_path):
                return
            icon = QIcon(self._icon_path)
            if icon.isNull():
                return

            menu = QMenu()
            show_action = QAction("显示主窗口", menu)
            show_action.triggered.connect(self._on_show)
            exit_action = QAction("退出", menu)
            exit_action.triggered.connect(self._on_exit)
            menu.addAction(show_action)
            menu.addAction(exit_action)

            self._icon = QSystemTrayIcon(icon)
            self._icon.setToolTip(self._title)
            self._icon.setContextMenu(menu)
            self._icon.activated.connect(self._on_activated)
            self._icon.show()
        except Exception as e:
            from error_logger import log_exception
            log_exception("TrayManager.start", e)

    def _on_activated(self, reason):
        # Trigger = 用户左键单击托盘图标
        if reason == QSystemTrayIcon.Trigger:
            self._on_show()

    def stop(self) -> None:
        """隐藏并销毁托盘图标（幂等）。"""
        if self._icon is not None:
            try:
                self._icon.hide()
                self._icon.deleteLater()
            except Exception as e:
                from error_logger import log_exception
                log_exception("TrayManager.stop", e)
            self._icon = None
