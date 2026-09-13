from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from config import AppConfig
from scheduler import BalanceResult
from animations import AnimationHelper
from edit_account_dialog import EditAccountDialog
from settings_dialog import SettingsDialog
from account_row import AccountRow
from error_logger import log_exception
# ISSUE-ARC-02：事件总线替代 6 个 setter 回调注入
from event_bus import (
    EventBus,
    EVENT_REFRESH_REQUESTED,
    EVENT_SETTINGS_CHANGED,
    EVENT_ACCOUNT_ADDED,
    EVENT_ACCOUNT_DELETED,
    EVENT_ACCOUNT_UPDATED,
)


"""主窗口：账户列表管理、余额显示、设置入口。

功能：
- 账户 CRUD（添加/编辑/删除/拖拽排序）
- 余额实时更新（调度器回调 → AccountRow）
- 焦点丢失自动切换到悬浮窗
- 设置对话框（间隔/主题/波纹/代理目标）

ISSUE-ARC-02：窗口只 publish 事件（刷新/设置变更/账户变更），
App 在 _wire_events 中订阅分派；App→窗口的导航命令（趋势图/用量概览）
是"命令"而非"事件"，经构造参数注入（on_view_curve / on_view_usage）。
"""


class MainWindow(ctk.CTk):
    """应用主窗口，继承 CTk（customtkinter 的根窗口）。"""
    CLOSE_ACTION_HIDE = "hide"
    CLOSE_ACTION_EXIT = "exit"

    def __init__(
        self,
        config: AppConfig,
        event_bus: EventBus | None = None,
        on_switch_to_floating: Callable = None,
        on_apply_theme: Callable = None,
        on_view_curve: Callable = None,
        on_view_usage: Callable = None,
    ):
        super().__init__()
        self._config = config
        # ISSUE-ARC-02：事件总线注入；未提供时用私有实例，保证 publish 路径统一
        self._event_bus = event_bus if event_bus is not None else EventBus()
        # App→窗口的导航命令经构造注入（ISSUE-ARC-02：原 set_view_curve_callback / set_view_usage_callback）
        self._on_view_curve = on_view_curve
        self._on_view_usage = on_view_usage
        self._on_switch_to_floating = on_switch_to_floating
        self._on_apply_theme = on_apply_theme
        self._account_rows: list[AccountRow] = []
        self._close_action = self.CLOSE_ACTION_HIDE
        self._focus_check_id: Optional[str] = None

        self._drag_active = False
        self._drag_source_idx: Optional[int] = None
        self._drag_target_idx: Optional[int] = None
        self._drag_timer_id: Optional[str] = None
        self._drag_start_y: int = 0
        self._drag_indicator: Optional[ctk.CTkFrame] = None

        self.title("DeepSeek 余额监控")
        self.geometry("700x500")
        self.minsize(550, 350)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Unmap>", self._on_minimize)
        self._setup_ui()
        self.bind_all("<Control-r>", lambda e: self._on_manual_refresh())
        self.bind_all("<Control-Shift-B>", lambda e: self._on_minimize_to_floating())
        self._rebuild_account_list()

    def _on_minimize(self, event):
        if event.widget == self and self.state() == 'iconic':
            self._cancel_focus_check()
            self.withdraw()
            if self._on_switch_to_floating:
                self._on_switch_to_floating()

    def start_focus_monitor(self):
        """ISSUE-PFM-05：启动事件驱动的焦点监视（替代 500ms 轮询）。

        绑定 FocusIn/FocusOut 事件，收到 FocusOut 后起 300ms 防抖计时器，
        期间若收到 FocusIn 则取消（过滤快速焦点切换）。
        计时器触发后校验是否存在子对话框（CTkToplevel），有则不切悬浮窗。
        """
        self._cancel_focus_check()
        try:
            self.bind_all("<FocusIn>", self._on_focus_in)
            self.bind_all("<FocusOut>", self._on_focus_out)
        except Exception as e:
            log_exception("MainWindow.start_focus_monitor", e)

    def _cancel_focus_check(self):
        """取消挂起的防抖计时器（原 _focus_check_id 复用为防抖计时器 ID）。"""
        if self._focus_check_id is not None:
            try:
                self.after_cancel(self._focus_check_id)
            except Exception:
                pass
            self._focus_check_id = None

    def _on_focus_in(self, event):
        """ISSUE-PFM-05：收到 FocusIn 取消挂起的防抖计时器（用户回到窗口）。"""
        self._cancel_focus_check()

    def _on_focus_out(self, event):
        """ISSUE-PFM-05：收到 FocusOut 后起 300ms 防抖计时器。

        300ms 用于过滤快速焦点切换（如点击子对话框时的瞬时 FocusOut）。
        计时器触发后才真正判断是否切悬浮窗。
        """
        # 仅当事件目标是本窗口或其子组件时才处理
        if not self._is_self_or_descendant(event.widget) and event.widget is not self:
            # 焦点离开本窗口体系才计时；否则忽略（如窗口内组件间切换）
            pass
        self._cancel_focus_check()
        # ISSUE-PFM-05：300ms 防抖，过滤瞬时 FocusOut
        self._focus_check_id = self.after(300, self._on_focus_loss_confirmed)

    def _on_focus_loss_confirmed(self):
        """ISSUE-PFM-05：300ms 防抖后确认焦点丢失，校验子对话框后切悬浮窗。

        - 窗口已销毁则直接返回
        - 窗口已最小化（withdrawn）则不重复切
        - 存在 CTkToplevel 子对话框时暂停切换（避免对话框抢焦点导致误切）
        """
        self._focus_check_id = None
        if not self.winfo_exists():
            return
        if self.state() == "withdrawn":
            return
        # 校验子对话框：有则不切（避免对话框抢焦点误判）
        for w in self.winfo_children():
            if isinstance(w, ctk.CTkToplevel):
                return
        # 确认焦点丢失，切悬浮窗
        self.withdraw()
        if self._on_switch_to_floating:
            self._on_switch_to_floating()

    def _is_self_or_descendant(self, widget) -> bool:
        w = widget
        while w is not None:
            if w is self:
                return True
            try:
                w = w.master
            except Exception:
                break
        return False

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        header.grid_columnconfigure(1, weight=1)

        title_label = ctk.CTkLabel(
            header,
            text="DeepSeek 余额监控",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        title_label.grid(row=0, column=0, padx=(0, 15))

        self.add_btn = ctk.CTkButton(
            header, text="+ 添加账号", width=110, command=self._on_add_account
        )
        self.add_btn.grid(row=0, column=1, padx=5, sticky="e")

        self.refresh_btn = ctk.CTkButton(
            header, text="立即刷新", width=90, fg_color="gray"
        )
        self.refresh_btn.grid(row=0, column=2, padx=5)
        AnimationHelper.bind_ripple(self.refresh_btn, self._on_manual_refresh)

        self.float_btn = ctk.CTkButton(
            header,
            text="最小化到悬浮窗",
            width=130,
            fg_color="gray",
        )
        self.float_btn.grid(row=0, column=3, padx=5)
        AnimationHelper.bind_ripple(self.float_btn, self._on_minimize_to_floating)

        self.settings_btn = ctk.CTkButton(
            header,
            text="设置",
            width=60,
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=self._on_settings,
        )
        self.settings_btn.grid(row=0, column=4, padx=5)

        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=5)
        self.scroll_frame.grid_columnconfigure(0, weight=1)
        AnimationHelper.bind_ripple(self.scroll_frame)

        self.empty_label = ctk.CTkLabel(
            self.scroll_frame,
            text="暂无监控账号\n点击「+ 添加账号」开始",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=15, pady=(5, 10))

        self.status_label = ctk.CTkLabel(
            footer,
            text="就绪",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.status_label.pack(side="left")

        self.interval_label = ctk.CTkLabel(
            footer,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.usage_btn = ctk.CTkButton(
            footer,
            text="用量概览",
            width=100,
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            command=self._on_view_usage,
            font=ctk.CTkFont(size=11),
        )
        self.usage_btn.pack(side="right", padx=(0, 10))

        self.interval_label.pack(side="right")
        self.interval_label.bind("<Double-Button-1>", self._on_interval_double_click)
        self._update_interval_label()

    def _rebuild_account_list(self):
        """销毁所有 AccountRow 并从 config 重建，拖拽排序后也会调用。"""
        for row in self._account_rows:
            row.destroy()
        self._account_rows.clear()

        if not self._config.accounts:
            self.empty_label.pack(expand=True)
            return

        self.empty_label.pack_forget()
        for idx, acc in enumerate(self._config.accounts):
            row = AccountRow(
                self.scroll_frame,
                acc.uid,
                acc,
                on_edit=self._on_edit_account,
                on_delete=self._on_delete_account,
                on_view_curve=self._on_view_curve,
            )
            row.pack(fill="x", pady=2)
            row.key_label.bind("<ButtonPress-1>", lambda e, i=idx: self._on_drag_press(i, e))
            row.key_label.bind("<B1-Motion>", lambda e: self._on_drag_motion(e))
            row.key_label.bind("<ButtonRelease-1>", lambda e: self._on_drag_release(e))
            self._account_rows.append(row)

    def _on_drag_press(self, idx: int, event):
        """记录拖拽起点，400ms 长按或 5px 位移后激活拖拽模式。"""
        self._drag_source_idx = idx
        self._drag_target_idx = idx
        self._drag_start_y = event.y_root
        if self._drag_timer_id:
            self.after_cancel(self._drag_timer_id)
        self._drag_timer_id = self.after(400, self._activate_drag)

    def _on_drag_motion(self, event):
        if self._drag_source_idx is None:
            return
        dy = abs(event.y_root - self._drag_start_y)
        if not self._drag_active:
            if dy >= 5:
                if self._drag_timer_id:
                    self.after_cancel(self._drag_timer_id)
                    self._drag_timer_id = None
                self._activate_drag()
            else:
                return
        if len(self._account_rows) <= 1:
            return

        mouse_y = event.y_root
        new_target = 0
        min_dist = float("inf")
        for i, row in enumerate(self._account_rows):
            try:
                mid = row.winfo_rooty() + row.winfo_height() / 2
            except Exception as e:
                log_exception("MainWindow._on_drag_motion", e)
                continue
            dist = abs(mouse_y - mid)
            if dist < min_dist:
                min_dist = dist
                new_target = i

        if new_target != self._drag_target_idx:
            self._drag_target_idx = new_target
            self._update_drag_indicator()

    def _on_drag_release(self, event):
        if self._drag_timer_id:
            self.after_cancel(self._drag_timer_id)
            self._drag_timer_id = None
        if self._drag_active:
            self._commit_drag()
        self._drag_source_idx = None
        self._drag_target_idx = None
        self._drag_active = False
        self._drag_start_y = 0
        self._hide_drag_indicator()

    def _activate_drag(self):
        src = self._drag_source_idx
        if src is None or src >= len(self._account_rows):
            return
        self._drag_active = True
        self._account_rows[src].set_drag_source()

    def _update_drag_indicator(self):
        self._hide_drag_indicator()
        tgt = self._drag_target_idx
        src = self._drag_source_idx
        if tgt is None or src is None or tgt == src:
            return
        if tgt < 0 or tgt >= len(self._account_rows):
            return

        indicator = ctk.CTkFrame(
            self._account_rows[tgt].master,
            height=3,
            fg_color="#4a9eff",
            corner_radius=0,
        )
        before_row = self._account_rows[tgt]
        indicator.pack(before=before_row, fill="x", pady=(0, 0))
        self._drag_indicator = indicator

    def _hide_drag_indicator(self):
        if self._drag_indicator is not None:
            try:
                self._drag_indicator.destroy()
            except Exception as e:
                log_exception("MainWindow._hide_drag_indicator", e)
            self._drag_indicator = None

    def _commit_drag(self):
        for row in self._account_rows:
            row.clear_drag_state()
        self._hide_drag_indicator()

        src = self._drag_source_idx
        tgt = self._drag_target_idx
        if src is not None and tgt is not None and src != tgt and 0 <= src < len(self._config.accounts) and 0 <= tgt < len(self._config.accounts):
            acc = self._config.accounts.pop(src)
            self._config.accounts.insert(tgt, acc)
            self._rebuild_account_list()
            # ISSUE-ARC-02：拖拽排序经 account_updated 事件触发落盘
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
            # ISSUE-ARC-02：账户变更经事件总线广播，App 订阅后统一落盘
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

    def _highlight_account(self, uid: str):
        for row in self._account_rows:
            if row.uid == uid:
                row.highlight()
                break

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

    def _on_manual_refresh(self):
        # ISSUE-ARC-02：刷新请求经事件总线广播，App 按 _loaded 状态门分派
        self._event_bus.publish(EVENT_REFRESH_REQUESTED, source="main_window")

    def _on_minimize_to_floating(self):
        self.withdraw()
        if self._on_switch_to_floating:
            self._on_switch_to_floating()

    def _on_close(self):
        self.withdraw()
        if self._on_switch_to_floating:
            self._on_switch_to_floating()

    def _on_interval_double_click(self, event):
        self._on_settings()

    def prepare_exit(self):
        self._close_action = self.CLOSE_ACTION_EXIT

    def update_account_balance(self, result: BalanceResult):
        for row in self._account_rows:
            if row.uid == result.uid:
                row.update_balance(result)
                return

    def set_proxy_token_provider(self, provider: Callable[[], str]):
        """ISSUE-SEC-04：注入代理 token 提供者，用于设置面板展示 token hash。

        ISSUE-ARC-02：保留为同步查询接口而非事件——取 token 是"问一个值"，
        不是"通知一件事"，改事件反而不匹配语义。
        """
        self._proxy_token_provider = provider

    def set_status(self, text: str):
        self.status_label.configure(text=text)

    def _on_settings(self):
        # ISSUE-SEC-04：传入已脱敏的代理 token hash，便于用户排查客户端配置
        from usage_proxy import _hash_token
        proxy_token_display = ""
        if hasattr(self, "_proxy_token_provider"):
            try:
                proxy_token_display = _hash_token(self._proxy_token_provider())
            except Exception:
                proxy_token_display = ""

        result = SettingsDialog.show(
            self,
            self._config.settings.interval_sec,
            self._config.settings.autostart,
            self._config.settings.theme,
            self._config.settings.ripple_color,
            self._config.settings.proxy_target,
            proxy_token_display=proxy_token_display,
        )
        if result is not None:
            interval, autostart, theme, ripple_color, proxy_target = result
            self._config.settings.interval_sec = interval
            self._config.settings.autostart = autostart
            self._config.settings.theme = theme
            self._config.settings.ripple_color = ripple_color
            self._config.settings.proxy_target = proxy_target
            AnimationHelper.set_ripple_color(ripple_color)
            self._update_interval_label()
            if self._on_apply_theme:
                self._on_apply_theme(theme)
            # ISSUE-ARC-02：设置变更整体经 settings_changed 事件广播，
            # App 订阅后统一分派（调度器间隔/自启/落盘），替代原 3 个回调链
            self._event_bus.publish(
                EVENT_SETTINGS_CHANGED,
                payload={
                    "interval": interval,
                    "autostart": autostart,
                    "theme": theme,
                    "ripple_color": ripple_color,
                    "proxy_target": proxy_target,
                },
                source="main_window",
            )

    def _on_view_usage(self):
        # ISSUE-ARC-02：原 set_view_usage_callback 改为构造注入
        if self._on_view_usage:
            self._on_view_usage()

    def _update_interval_label(self):
        sec = self._config.settings.interval_sec
        if sec >= 60:
            self.interval_label.configure(text=f"刷新间隔: {sec // 60}分钟")
        else:
            self.interval_label.configure(text=f"刷新间隔: {sec}秒")
