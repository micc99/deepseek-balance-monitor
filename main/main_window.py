from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import AppConfig
from edit_account_dialog import EditAccountDialog
from settings_dialog import SettingsDialog
from event_bus import (
    EventBus,
    EVENT_REFRESH_REQUESTED,
    EVENT_SETTINGS_CHANGED,
    EVENT_ACCOUNT_ADDED,
    EVENT_ACCOUNT_DELETED,
    EVENT_ACCOUNT_UPDATED,
)
from managers.hotkey_manager import pynput_to_qt
from qt_bridge import CallDispatcher
from account_row import AccountRow


class _Partial:
    """轻量偏函数：保存 (fn, args)，调用时解包（tkinter after *args 语义）。"""

    __slots__ = ("_fn", "_args")

    def __init__(self, fn, args):
        self._fn = fn
        self._args = args

    def __call__(self):
        self._fn(*self._args)


"""主窗口（Qt 版，ISSUE-MIG-03 完整实装）。

功能：账户列表（QListWidget 原生拖拽排序替代 ctk 手写拖拽）、余额实时
更新、添加/编辑/删除（添加/编辑对话框随 ISSUE-MIG-05 接线）、设置入口。

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
        self._account_rows: list = []
        self._drag_active = False
        self._drag_source_idx: Optional[int] = None

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

        # ISSUE-UX-02：快捷键来自 config（toggle_window 为全局 pynput 热键，
        # manual_refresh 为窗口内 QShortcut；均可经设置对话框修改）
        self._refresh_shortcut = QShortcut(
            QKeySequence(pynput_to_qt(self._config.settings.hotkeys.get("manual_refresh", "<ctrl>+r"))),
            self, activated=self._on_manual_refresh)
        QShortcut(
            QKeySequence(pynput_to_qt(self._config.settings.hotkeys.get("toggle_window", "<ctrl>+<shift>+b"))),
            self, activated=self._on_minimize_to_floating)

        self._rebuild_account_list()

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
        self.refresh_btn.clicked.connect(self._on_manual_refresh)
        self.float_btn.clicked.connect(self._on_minimize_to_floating)
        self.add_btn.clicked.connect(self._on_add_account)
        self.settings_btn.clicked.connect(self._on_settings)
        return header

    def _build_list_area(self) -> QWidget:
        self._list = QListWidget()
        self._list.setObjectName("accountList")
        self._list.setDragDropMode(QListWidget.InternalMove)
        self._list.setSelectionMode(QListWidget.NoSelection)
        self._list.setSpacing(2)
        self._list.setStyleSheet(
            "QListWidget{background:transparent;border:none;}"
            "QListWidget::item{margin:0;}")
        # 原生拖拽排序完成后，把新顺序写回 config 并广播（ISSUE-ARC-02）
        self._list.model().rowsMoved.connect(self._on_rows_moved)

        self._empty_label = QLabel("暂无监控账号\n点击「+ 添加账号」开始", objectName="muted")
        self._empty_label.setAlignment(Qt.AlignCenter)

        wrapper = QWidget()
        w_layout = QVBoxLayout(wrapper)
        w_layout.setContentsMargins(0, 0, 0, 0)
        w_layout.addWidget(self._list)
        w_layout.addWidget(self._empty_label)
        self._empty_label.setVisible(False)
        return wrapper

    def _build_footer(self) -> QWidget:
        footer = QFrame(objectName="card")
        row = QHBoxLayout(footer)
        row.setContentsMargins(12, 6, 12, 6)
        self.status_label = QLabel("就绪", objectName="status")
        self.interval_label = QLabel("", objectName="status")
        usage_btn = QPushButton("用量概览", objectName="flat")
        usage_btn.clicked.connect(self._safe_view_usage)
        row.addWidget(self.status_label)
        row.addStretch(1)
        row.addWidget(self.interval_label)
        row.addWidget(usage_btn)
        self.interval_label.mouseDoubleClickEvent = lambda _e: self._on_settings()
        self._update_interval_label()
        return footer

    # ---- 账户列表（ISSUE-MIG-03）----

    def _rebuild_account_list(self):
        """销毁所有 AccountRow 并从 config 重建，拖拽排序后也会调用。"""
        self._list.clear()
        self._account_rows.clear()
        if not self._config.accounts:
            self._empty_label.setVisible(True)
            self._list.setVisible(False)
            return
        self._empty_label.setVisible(False)
        self._list.setVisible(True)
        for acc in self._config.accounts:
            row = AccountRow(
                self._list,
                acc.uid,
                acc,
                on_edit=self._on_edit_account,
                on_delete=self._on_delete_account,
                on_view_curve=self._on_view_curve,
            )
            item = QListWidgetItem()
            item.setData(Qt.UserRole, acc.uid)
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
            self._account_rows.append(row)

    def _on_rows_moved(self, *args):
        """原生拖拽落点：按列表新顺序重排 config.accounts 并广播落盘。"""
        order = [self._list.item(i).data(Qt.UserRole) for i in range(self._list.count())]
        by_uid = {a.uid: a for a in self._config.accounts}
        if set(order) != set(by_uid):
            self._rebuild_account_list()  # 异常状态兜底：按 config 还原
            return
        self._config.accounts[:] = [by_uid[u] for u in order]
        self._event_bus.publish(
            EVENT_ACCOUNT_UPDATED,
            payload={"action": "reorder"},
            source="main_window",
        )

    def _on_add_account(self):
        default_label = f"Account {len(self._config.accounts) + 1}"
        result, dup_uid = EditAccountDialog.show(
            self, "添加监控账号", default_label=default_label,
            existing_accounts=self._config.accounts
        )
        if dup_uid:
            self._highlight_account(dup_uid)
            return
        if result:
            self._config.accounts.append(result)
            self._rebuild_account_list()
            self._event_bus.publish(
                EVENT_ACCOUNT_ADDED,
                payload={"uid": result.uid, "label": result.label},
                source="main_window",
            )

    def _on_edit_account(self, uid: str):
        idx = next((i for i, a in enumerate(self._config.accounts) if a.uid == uid), None)
        if idx is None:
            return
        acc = self._config.accounts[idx]
        result, dup_uid = EditAccountDialog.show(
            self, "编辑账号", acc, default_label=acc.label,
            existing_accounts=self._config.accounts, exclude_uid=uid
        )
        if dup_uid:
            self._highlight_account(dup_uid)
            return
        if result:
            result.uid = uid
            self._config.accounts[idx] = result
            self._rebuild_account_list()
            self._event_bus.publish(
                EVENT_ACCOUNT_UPDATED,
                payload={"uid": uid, "label": result.label},
                source="main_window",
            )

    def _on_delete_account(self, uid: str):
        idx = next((i for i, a in enumerate(self._config.accounts) if a.uid == uid), None)
        if idx is None:
            return
        del self._config.accounts[idx]
        self._rebuild_account_list()
        self._event_bus.publish(
            EVENT_ACCOUNT_DELETED,
            payload={"uid": uid},
            source="main_window",
        )

    def _highlight_account(self, uid: str):
        for row in self._account_rows:
            if row.uid == uid:
                row.highlight()
                break

    def _safe_view_usage(self):
        if self._on_view_usage:
            self._on_view_usage()

    # ---- 动作 ----

    def _on_manual_refresh(self):
        # ISSUE-ARC-02：刷新请求经事件总线广播
        self._event_bus.publish(EVENT_REFRESH_REQUESTED, source="main_window")

    def _on_minimize_to_floating(self):
        self.hide()
        if self._on_switch_to_floating:
            self._on_switch_to_floating()

    def _update_interval_label(self):
        sec = self._config.settings.interval_sec
        if sec >= 60:
            self.interval_label.setText(f"刷新间隔: {sec // 60}分钟")
        else:
            self.interval_label.setText(f"刷新间隔: {sec}秒")

    def _on_settings(self):
        # ISSUE-SEC-04：传入已脱敏的代理 token hash，便于用户排查客户端配置
        proxy_token_display = ""
        provider = getattr(self, "_proxy_token_provider", None)
        if provider is not None:
            try:
                from usage_proxy import _hash_token
                proxy_token_display = _hash_token(provider())
            except Exception:
                proxy_token_display = ""

        result = SettingsDialog.show(
            self,
            self._config.settings.interval_sec,
            self._config.settings.autostart,
            self._config.settings.theme_mode,
            self._config.settings.ripple_color,
            self._config.settings.proxy_target,
            proxy_token_display=proxy_token_display,
            hotkeys=self._config.settings.hotkeys,
            auto_float_on_focus_loss=self._config.settings.auto_float_on_focus_loss,
        )
        if result is not None:
            interval, autostart, mode, ripple_color, proxy_target, hotkeys, auto_float = result
            self._config.settings.interval_sec = interval
            self._config.settings.autostart = autostart
            # ISSUE-THM-02：对话框返回的是亮暗模式（dark/light），写入 theme_mode；
            # 主题身份 settings.theme 由 ThemeManager/Phase D 编辑器管理
            self._config.settings.theme_mode = mode
            self._config.settings.ripple_color = ripple_color
            self._config.settings.proxy_target = proxy_target
            # ISSUE-UX-02/UX-04：快捷键与失焦行为写入配置，重绑窗口内快捷键
            self._config.settings.hotkeys = hotkeys
            self._config.settings.auto_float_on_focus_loss = auto_float
            self.apply_hotkeys()
            self._update_interval_label()
            # ISSUE-ARC-02：设置变更整体经 settings_changed 事件广播，
            # App 订阅后统一分派（调度器间隔/自启/全局热键/落盘）
            self._event_bus.publish(
                EVENT_SETTINGS_CHANGED,
                payload={
                    "interval": interval,
                    "autostart": autostart,
                    "theme_mode": mode,
                    "ripple_color": ripple_color,
                    "proxy_target": proxy_target,
                    "hotkeys": hotkeys,
                    "auto_float": auto_float,
                },
                source="main_window",
            )

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
        """ISSUE-PFM-05（Qt 实装，ISSUE-MIG-04）：事件驱动焦点监视。

        QApplication 级 eventFilter 捕获本窗口的 FocusIn/FocusOut（对应
        ctk 版 bind_all）；FocusOut 起 300ms 单发防抖计时器，FocusIn 取消；
        触发后校验可见 QDialog 子对话框，存在则不切悬浮窗。
        """
        if getattr(self, "_focus_monitor_installed", False):
            return
        self._focus_monitor_installed = True
        from PySide6.QtCore import QTimer
        self._focus_check_id = QTimer(self)
        self._focus_check_id.setSingleShot(True)
        self._focus_check_id.setInterval(300)
        self._focus_check_id.timeout.connect(self._on_focus_loss_confirmed)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent
        if watched is self:
            if event.type() == QEvent.FocusOut:
                # ISSUE-PFM-05：300ms 防抖，过滤瞬时焦点切换
                self._focus_check_id.start()
            elif event.type() == QEvent.FocusIn:
                self._focus_check_id.stop()
        return super().eventFilter(watched, event)

    def _on_focus_in(self, _event=None):
        """ISSUE-PFM-05：FocusIn 取消挂起的防抖计时器（保留 ctk 版同名入口）。"""
        if getattr(self, "_focus_check_id", None) is not None:
            self._focus_check_id.stop()

    def _on_focus_out(self, _event=None):
        """ISSUE-PFM-05：FocusOut 起防抖计时器（保留 ctk 版同名入口）。"""
        if getattr(self, "_focus_check_id", None) is not None:
            self._focus_check_id.start()

    def _on_focus_loss_confirmed(self):
        """ISSUE-PFM-05：300ms 防抖后确认焦点丢失，校验子对话框后切悬浮窗。

        ISSUE-UX-04：auto_float_on_focus_loss=False 时不自动切换。
        """
        if not self.winfo_exists() or not self.isVisible():
            return
        if not getattr(self._config.settings, "auto_float_on_focus_loss", True):
            return
        # 校验子对话框：有可见 QDialog 时不切（避免对话框抢焦点误判）
        from PySide6.QtWidgets import QDialog
        for w in self.findChildren(QDialog):
            if w.isVisible():
                return
        self.hide()
        if self._on_switch_to_floating:
            self._on_switch_to_floating()

    def apply_hotkeys(self):
        """ISSUE-UX-02：设置变更后重绑窗口内快捷键。"""
        hk = self._config.settings.hotkeys.get("manual_refresh", "<ctrl>+r")
        self._refresh_shortcut.setKey(QKeySequence(pynput_to_qt(hk)))

    def set_proxy_token_provider(self, provider: Callable[[], str]):
        """ISSUE-SEC-04：同步查询接口（ARC-02 决策：查询非事件）。"""
        self._proxy_token_provider = provider

    def update_account_balance(self, result):
        """余额结果分发到对应账户行。"""
        for row in self._account_rows:
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
