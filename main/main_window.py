from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig
from event_bus import EventBus, EVENT_REFRESH_REQUESTED
from qt_bridge import CallDispatcher


class _Partial:
    """轻量偏函数：保存 (fn, args)，调用时解包（避免 functools 依赖语义差异）。"""

    __slots__ = ("_fn", "_args")

    def __init__(self, fn, args):
        self._fn = fn
        self._args = args

    def __call__(self):
        self._fn(*self._args)


"""主窗口（Qt 版，ISSUE-MIG-02 脚手架壳体 → ISSUE-MIG-03 完整账户列表）。

Stack 兼容面：WindowManager（ISSUE-ARC-01）以 after/winfo_exists/state/
deiconify/lift/focus/prepare_exit/set_status/start_focus_monitor 等方法
操作窗口——这些名称同时存在于 ctk 版与 Qt 版，保证 WindowManager 双栈零改动。

线程模型：后台线程经 after(0, fn) 投递（内部走 CallDispatcher 信号，
跨线程安全）；after(ms>0) 仅限主线程调用。
"""


class MainWindow(QMainWindow):
    """应用主窗口。"""

    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus | None = None,
        on_switch_to_floating: Callable | None = None,
        on_apply_theme: Callable | None = None,
        on_view_curve: Callable | None = None,
        on_view_usage: Callable | None = None,
    ):
        super().__init__()
        self._config = config
        self._event_bus = event_bus if event_bus is not None else EventBus()
        self._on_switch_to_floating = on_switch_to_floating
        self._on_apply_theme = on_apply_theme
        self._on_view_curve = on_view_curve
        self._on_view_usage = on_view_usage
        self._bridge = CallDispatcher(self)
        self._close_hides = True  # ISSUE-LOG-03 语义：点关闭 = 切悬浮窗；prepare_exit 后真退出
        self._destroyed = False
        self.destroyed.connect(self._on_destroyed)

        self.setWindowTitle("DeepSeek 余额监控")
        self.resize(700, 500)
        self.setMinimumSize(550, 350)

        central = QWidget(objectName="central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(15, 12, 15, 10)
        layout.setSpacing(8)

        layout.addWidget(self._build_header())
        layout.addWidget(self._build_list_area(), 1)
        layout.addWidget(self._build_footer())

        # 快捷键（与 ctk 版 bind_all 等价）
        QShortcut(QKeySequence("Ctrl+R"), self, activated=self._on_manual_refresh)
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, activated=self._on_minimize_to_floating)

    # ---- UI 构建 ----

    def _build_header(self) -> QWidget:
        header = QFrame(objectName="card")
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)

        title = QLabel("DeepSeek 余额监控", objectName="title")
        row.addWidget(title)
        row.addStretch(1)

        self.add_btn = QPushButton("+ 添加账号")
        self.refresh_btn = QPushButton("立即刷新")
        self.float_btn = QPushButton("最小化到悬浮窗")
        self.settings_btn = QPushButton("设置", objectName="flat")
        for btn in (self.add_btn, self.refresh_btn, self.float_btn, self.settings_btn):
            row.addWidget(btn)
        # ISSUE-MIG-02：仅刷新/最小化接线；添加/设置随 ISSUE-MIG-03/05 实装
        self.refresh_btn.clicked.connect(self._on_manual_refresh)
        self.float_btn.clicked.connect(self._on_minimize_to_floating)
        return header

    def _build_list_area(self) -> QWidget:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        placeholder = QWidget()
        ph_layout = QVBoxLayout(placeholder)
        ph_layout.setAlignment(Qt.AlignCenter)
        empty = QLabel("账户列表（ISSUE-MIG-03 实装）", objectName="muted")
        ph_layout.addWidget(empty)
        self._scroll.setWidget(placeholder)
        return self._scroll

    def _build_footer(self) -> QWidget:
        footer = QFrame(objectName="card")
        row = QHBoxLayout(footer)
        row.setContentsMargins(12, 6, 12, 6)
        self.status_label = QLabel("就绪", objectName="status")
        self.interval_label = QLabel("", objectName="status")
        usage_btn = QPushButton("用量概览", objectName="flat")
        usage_btn.clicked.connect(self._on_view_usage if self._on_view_usage else lambda: None)
        row.addWidget(self.status_label)
        row.addStretch(1)
        row.addWidget(self.interval_label)
        row.addWidget(usage_btn)
        return footer

    # ---- 动作 ----

    def _on_manual_refresh(self):
        # ISSUE-ARC-02：刷新请求经事件总线广播
        self._event_bus.publish(EVENT_REFRESH_REQUESTED, source="main_window")

    def _on_minimize_to_floating(self):
        self.hide()
        if self._on_switch_to_floating:
            self._on_switch_to_floating()

    # ---- WindowManager 兼容面（双栈同名 API）----

    def title(self, text: str = None):
        """ctk title 等价：get 无参返回标题，set 带参设置。"""
        if text is None:
            return self.windowTitle()
        self.setWindowTitle(text)

    def after(self, ms: int, fn: Callable, *args) -> None:
        """ctk after 等价：ms=0 跨线程安全（信号投递），ms>0 主线程 QTimer。

        支持 *args 透传（tkinter 语义：fn(*args)）。
        """
        if args:
            fn = _Partial(fn, args)
        if ms <= 0:
            self._bridge.call.emit(fn)
        else:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(ms, fn)

    def winfo_exists(self) -> bool:
        return not self._destroyed

    def _on_destroyed(self, *args):
        self._destroyed = True

    def state(self) -> str:
        return "normal" if self.isVisible() else "withdrawn"

    def deiconify(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def lift(self):
        self.raise_()

    def focus(self):
        self.activateWindow()

    def prepare_exit(self):
        self._close_hides = False

    def set_status(self, text: str):
        self.status_label.setText(text)

    def start_focus_monitor(self):
        """ISSUE-PFM-05：焦点监视，随 ISSUE-MIG-04 在 Qt 事件模型下实装。"""

    def set_proxy_token_provider(self, provider: Callable[[], str]):
        """ISSUE-SEC-04：同步查询接口（ARC-02 决策：查询非事件）。"""
        self._proxy_token_provider = provider

    def _rebuild_account_list(self):
        """ISSUE-MIG-03：账户列表重建（壳体阶段占位，随 MIG-03 实装）。"""

    def update_account_balance(self, result):
        """ISSUE-MIG-03：账户行余额刷新（壳体阶段无行可更新）。"""
        for row in getattr(self, "_account_rows", []):
            if row.uid == result.uid:
                row.update_balance(result)
                return

    # ---- 关闭语义 ----

    def closeEvent(self, event):
        if self._close_hides:
            event.ignore()
            self.hide()
            if self._on_switch_to_floating:
                self._on_switch_to_floating()
        else:
            event.accept()
