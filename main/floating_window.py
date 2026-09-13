from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel, QMenu, QVBoxLayout, QWidget

from config import WindowConfig


"""无边框悬浮窗（Qt 版，ISSUE-MIG-04 完整实装）。

主窗口最小化/关闭后显示，置顶、可拖拽、双击恢复主窗、右键菜单。
由 WindowManager 按需创建和销毁。
Stack 兼容面（protocol/get_position/set_position/update_balance/
destroy/winfo_exists/deiconify/lift/focus）与 ctk 版同名，保证
WindowManager 双栈零改动。D6：淡入淡出动画不迁移。
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
        self._drag_offset = QPoint()

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

    # ---- 拖拽 / 双击 / 右键（ISSUE-MIG-04）----

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # LeftButton 按住拖动（Qt 自动限频，无需手动节流）
        if event.buttons() & Qt.LeftButton and not self._drag_offset.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_offset = QPoint()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self._on_restore:
            self._on_restore()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self._on_refresh:
            act_refresh = QAction("立即刷新", menu)
            act_refresh.triggered.connect(self._on_refresh)
            menu.addAction(act_refresh)
            menu.addSeparator()
        act_exit = QAction("退出", menu)
        act_exit.triggered.connect(self._on_exit)
        menu.addAction(act_exit)
        menu.exec(event.globalPos())

    def _on_exit(self):
        if self._on_exit_cb:
            self._on_exit_cb()

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
