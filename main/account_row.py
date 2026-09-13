from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from config import AccountConfig, mask_api_key
from balance_checker import BalanceStatus, get_provider
from scheduler import BalanceResult


"""单账户行组件（Qt 版，ISSUE-MIG-03）。

每行显示：标签名、脱敏 API Key、Provider、余额、状态灯、删除按钮。
双击复制 Key（QToolTip 提示）、双击余额查看趋势曲线、拖拽排序由
主窗 QListWidget 承担（本组件只保留视觉状态接口）。

D6 决策：波纹动画/闪烁动画不迁移，hover 反馈由 QSS 承担。
"""


# 语义状态色（非主题 token，Phase D UX-06 统一收编）
_OK_COLOR = "#4caf50"
_WARN_COLOR = "#ff9800"
_ERR_COLOR = "#f44336"


class AccountRow(QFrame):
    """主窗口中的一行账户信息，由 _rebuild_account_list 动态创建。"""

    def __init__(
        self,
        master,
        uid: str,
        account: AccountConfig,
        on_edit: Callable,
        on_delete: Callable,
        on_view_curve: Optional[Callable] = None,
    ):
        super().__init__(master)
        self.uid = uid
        self.account = account
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_view_curve = on_view_curve
        self._prev_balance: str = ""
        self._setup_ui()

    def _setup_ui(self):
        self.setObjectName("card")
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)

        self.label_btn = QPushButton(self.account.label, objectName="rowLabel")
        self.label_btn.setStyleSheet(
            "QPushButton#rowLabel{background:transparent;border:none;text-align:left;"
            "font-weight:bold;padding:2px;}"
            f"QPushButton#rowLabel:hover{{background:{self._hover_hex()};}}")
        self.label_btn.setCursor(Qt.PointingHandCursor)
        self.label_btn.clicked.connect(lambda: self._on_edit(self.uid))
        row.addWidget(self.label_btn, 2)

        self.key_label = QLabel(mask_api_key(self.account.api_key), objectName="muted")
        self.key_label.setCursor(Qt.PointingHandCursor)
        self.key_label.setToolTip("双击复制 API Key")
        self.key_label.mouseDoubleClickEvent = lambda _e: self._on_double_click_key()
        row.addWidget(self.key_label, 2)

        try:
            provider_text = get_provider(self.account.provider).label
        except ValueError:
            provider_text = self.account.provider
        self.provider_label = QLabel(provider_text, objectName="muted")
        row.addWidget(self.provider_label, 1)

        self.balance_label = QLabel("检测中...")
        self.balance_label.setCursor(Qt.PointingHandCursor)
        self.balance_label.mouseDoubleClickEvent = lambda _e: self._on_double_click_balance()
        row.addWidget(self.balance_label, 2)

        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(22)
        self.status_dot.setAlignment(Qt.AlignCenter)
        self.status_dot.setStyleSheet(f"color: gray; background: transparent;")
        row.addWidget(self.status_dot)

        del_btn = QPushButton("✕", objectName="rowDelete")
        del_btn.setFixedSize(30, 28)
        del_btn.setStyleSheet(
            "QPushButton#rowDelete{background:transparent;border:none;color:#b06a6a;}"
            "QPushButton#rowDelete:hover{background:#c62828;color:white;border-radius:6px;}")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.clicked.connect(lambda: self._on_delete(self.uid))
        row.addWidget(del_btn)

    @staticmethod
    def _hover_hex() -> str:
        try:
            from qss import current_hover
            return current_hover()
        except Exception:
            return "rgba(128,128,128,60)"

    # ---- 余额刷新（调度器回调入口）----

    def update_balance(self, result: BalanceResult):
        if self.uid != result.uid:
            return
        info = result.info
        if info.status == BalanceStatus.OK:
            color = _OK_COLOR
            display = info.total_display
            if not info.is_available:
                display += " ⚠"
                color = _WARN_COLOR
            if display != self._prev_balance:
                self.balance_label.setText(display)
                self.balance_label.setStyleSheet(f"color: {color}; background: transparent;")
                self.status_dot.setStyleSheet(f"color: {color}; background: transparent;")
                self._prev_balance = display
        elif info.status == BalanceStatus.ERROR:
            self.status_dot.setStyleSheet(f"color: {_ERR_COLOR}; background: transparent;")
            self.balance_label.setText(info.error_message or "错误")
            self.balance_label.setStyleSheet(f"color: {_ERR_COLOR}; background: transparent;")
            self._prev_balance = ""
        elif info.status == BalanceStatus.LOADING:
            self.status_dot.setStyleSheet(f"color: {_WARN_COLOR}; background: transparent;")
            self.balance_label.setText("检测中...")
            self.balance_label.setStyleSheet("color: gray; background: transparent;")

    def highlight(self, duration_ms: int = 500):
        """重复 uid 提示：短暂高亮边框（原动画闪烁的降级替代，D6）。"""
        self.setStyleSheet("AccountRow{border: 1px solid #ff9800; border-radius: 8px;}")
        QTimer.singleShot(duration_ms, lambda: self.setStyleSheet(""))

    # ---- 交互 ----

    def _on_double_click_balance(self):
        if self._on_view_curve:
            self._on_view_curve(self.account)

    def _on_double_click_key(self):
        QGuiApplication.clipboard().setText(self.account.api_key)
        from PySide6.QtWidgets import QToolTip
        QToolTip.showText(self.key_label.mapToGlobal(self.key_label.rect().center()), "已复制 API Key")

    # ---- 拖拽视觉状态（WindowManager/主窗调用）----

    def set_drag_source(self):
        self.setStyleSheet("AccountRow{border: 1px solid #4a9eff; border-radius: 8px;}")

    def clear_drag_state(self):
        self.setStyleSheet("")
