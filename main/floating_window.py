from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from config import WindowConfig


"""无边框悬浮窗（Qt 版，ISSUE-MIG-02 外壳；拖拽/双击/右键随 ISSUE-MIG-04 实装）。

主窗口最小化/关闭后显示，置顶。由 WindowManager 按需创建和销毁。
Stack 兼容面（protocol/get_position/set_position/update_balance/
destroy/winfo_exists/deiconify/lift/focus）与 ctk 版同名，保证
WindowManager 双栈零改动。
"""


class FloatingWindow(QWidget):
    """紧凑型悬浮窗：标题 + 余额摘要 + 状态栏。"""

    def __init__(self, on_restore: Callable = None, on_refresh: Callable = None, on_exit: Callable = None):
        super().__init__(
            Qt.Tool  # 不在任务栏出现
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self._on_restore = on_restore
        self._on_refresh = on_refresh
        self._on_exit_cb = on_exit
        self._close_cb: Optional[Callable] = None
        self._destroyed = False
        self.destroyed.connect(self._mark_destroyed)

        self.setFixedSize(260, 120)
        self.setWindowTitle("余额监控")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self._title_label = QLabel("余额监控", objectName="muted")
        self._title_label.setAlignment(Qt.AlignCenter)
        self._balance_label = QLabel("暂无数据", objectName="balance")
        self._balance_label.setAlignment(Qt.AlignCenter)
        self._status_label = QLabel("0 个账号 | 就绪", objectName="status")
        self._status_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self._title_label)
        layout.addWidget(self._balance_label)
        layout.addWidget(self._status_label)
        # ISSUE-MIG-04：拖拽/双击恢复/右键菜单随后实装

    # ---- WindowManager 兼容面 ----

    def protocol(self, name: str, callback: Callable) -> None:
        """ctk protocol 等价：拦截 WM_DELETE_WINDOW（Qt 为 closeEvent）。"""
        self._close_cb = callback

    def closeEvent(self, event):
        if self._close_cb is not None:
            event.ignore()
            self._close_cb()
        else:
            event.accept()

    def get_position(self) -> WindowConfig:
        return WindowConfig(x=self.x(), y=self.y())

    def set_position(self, pos: WindowConfig) -> None:
        if pos is not None and pos.x is not None and pos.y is not None:
            self.move(pos.x, pos.y)
        else:
            self._center_on_screen()

    def _center_on_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        )

    def update_balance(self, total_display: str, available_count: int, status: str) -> None:
        self._balance_label.setText(total_display)
        self._status_label.setText(f"{available_count} 个账号 | {status}")

    def winfo_exists(self) -> bool:
        return not self._destroyed

    def destroy(self) -> None:
        self._mark_destroyed()
        self.close()
        self.deleteLater()

    def deiconify(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def lift(self) -> None:
        self.raise_()

    def focus(self) -> None:
        self.activateWindow()

    def _mark_destroyed(self, *args) -> None:
        self._destroyed = True
