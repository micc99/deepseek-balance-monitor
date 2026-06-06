from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from config import AppConfig, AccountConfig, mask_api_key
from balance_checker import BalanceInfo, BalanceStatus, PROVIDERS
from scheduler import BalanceResult
from animations import AnimationHelper
from edit_account_dialog import EditAccountDialog


class AccountRow(ctk.CTkFrame):
    def __init__(
        self,
        master,
        uid: str,
        account: AccountConfig,
        on_edit: Callable,
        on_delete: Callable,
        on_view_curve: Optional[Callable] = None,
    ):
        super().__init__(master, fg_color="transparent")
        self.uid = uid
        self.account = account
        self._on_edit = on_edit
        self._on_delete = on_delete
        self._on_view_curve = on_view_curve
        self._prev_balance: str = ""
        self._tooltip: Optional[ctk.CTkToplevel] = None
        self._tooltip_after: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self):
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.columnconfigure(2, weight=1)
        self.columnconfigure(3, weight=2)
        self.columnconfigure(4, weight=0)

        appearance = ctk.get_appearance_mode()
        label_text_color = "black" if appearance == "Light" else "white"

        self.label_btn = ctk.CTkButton(
            self,
            text=self.account.label,
            fg_color="transparent",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
            text_color=label_text_color,
            hover_color=("gray80", "gray30"),
        )
        self.label_btn.grid(row=0, column=0, sticky="ew", padx=(5, 2), pady=4)
        AnimationHelper.bind_ripple(self.label_btn, lambda u=self.account.uid: self._on_edit(u))

        key_text = mask_api_key(self.account.api_key)
        self.key_label = ctk.CTkLabel(
            self,
            text=key_text,
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w",
        )
        self.key_label.bind("<Double-Button-1>", self._on_double_click_key)
        self.key_label.grid(row=0, column=1, sticky="ew", padx=2, pady=4)

        provider_label_text = PROVIDERS.get(self.account.provider, None)
        provider_text = provider_label_text.label if provider_label_text else self.account.provider
        self.provider_label = ctk.CTkLabel(
            self,
            text=provider_text,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            anchor="w",
        )
        self.provider_label.grid(row=0, column=2, sticky="ew", padx=2, pady=4)

        self.balance_label = ctk.CTkLabel(
            self,
            text="检测中...",
            font=ctk.CTkFont(size=14),
            anchor="w",
        )
        self.balance_label.grid(row=0, column=3, sticky="ew", padx=2, pady=4)
        self.balance_label.bind("<Double-Button-1>", self._on_double_click_balance)
        self.balance_label.bind("<Enter>", self._on_balance_enter, add="+")
        self.balance_label.bind("<Leave>", self._on_balance_leave, add="+")

        self.status_dot = ctk.CTkLabel(
            self,
            text="●",
            font=ctk.CTkFont(size=18),
            width=25,
            text_color="gray",
        )
        self.status_dot.grid(row=0, column=4, padx=(2, 5), pady=4)

        del_btn = ctk.CTkButton(
            self,
            text="✕",
            width=30,
            height=28,
            fg_color="transparent",
            hover_color=("#e57373", "#c62828"),
            text_color=("gray50", "gray70"),
        )
        del_btn.grid(row=0, column=5, padx=(0, 5), pady=4)
        AnimationHelper.bind_ripple(del_btn, lambda u=self.account.uid: self._on_delete(u))

    def update_balance(self, result: BalanceResult):
        if self.uid != result.uid:
            return
        info = result.info
        if info.status == BalanceStatus.OK:
            self.status_dot.configure(text_color="#4caf50")
            display = info.total_display
            if not info.is_available:
                display += " ⚠"
                self.status_dot.configure(text_color="#ff9800")
            if display != self._prev_balance:
                self.balance_label.configure(
                    text=display,
                    text_color="#ff9800" if not info.is_available else ("#1b5e20", "#69f0ae"),
                )
                self._prev_balance = display
                AnimationHelper.flash_widget(self, "#1a3a5a", 500)
        elif info.status == BalanceStatus.ERROR:
            self.status_dot.configure(text_color="#f44336")
            self.balance_label.configure(
                text=info.error_message or "错误",
                text_color="#f44336",
            )
            self._prev_balance = ""
        elif info.status == BalanceStatus.LOADING:
            self.status_dot.configure(text_color="#ff9800")
            self.balance_label.configure(text="检测中...", text_color="gray")

    def highlight(self, duration_ms=500):
        AnimationHelper.flash_widget(self, "#fff176", duration_ms)

    def _on_double_click_balance(self, _event):
        if self._on_view_curve:
            self._on_view_curve(self.account)

    def _show_tooltip(self, text: str):
        if self._tooltip:
            return
        top = self.winfo_toplevel()
        tl = ctk.CTkToplevel(top)
        tl.overrideredirect(True)
        tl.attributes("-topmost", True)
        tl.resizable(False, False)
        frame = ctk.CTkFrame(tl, corner_radius=6, fg_color=("gray20", "gray30"))
        frame.pack(fill="both", expand=True, padx=2, pady=2)
        ctk.CTkLabel(
            frame,
            text=text,
            font=ctk.CTkFont(size=11),
            text_color=("#ffffff", "#ffffff"),
        ).pack(padx=8, pady=4)
        tl.update_idletasks()
        bx = self.balance_label.winfo_rootx()
        by = self.balance_label.winfo_rooty() + self.balance_label.winfo_height() + 4
        tl.geometry(f"+{bx}+{by}")
        self._tooltip = tl

    def _hide_tooltip(self):
        if self._tooltip:
            try:
                self._tooltip.destroy()
            except Exception:
                pass
            self._tooltip = None

    def _on_balance_enter(self, _event):
        if self._on_view_curve is None:
            return
        if self._tooltip_after:
            self.after_cancel(self._tooltip_after)
        self._tooltip_after = self.after(600, lambda: self._show_tooltip("双击查看消耗趋势"))

    def _on_balance_leave(self, _event):
        if self._tooltip_after:
            self.after_cancel(self._tooltip_after)
            self._tooltip_after = None
        self._hide_tooltip()

    def set_drag_source(self):
        self.configure(fg_color=("#d5d5d5", "#3a3a3a"))

    def clear_drag_state(self):
        self.configure(fg_color="transparent")

    def _on_double_click_key(self, _event):
        self.clipboard_clear()
        self.clipboard_append(self.account.api_key)
        self._show_copy_toast()

    def _show_copy_toast(self):
        top = self.winfo_toplevel()
        toast = ctk.CTkToplevel(top)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.resizable(False, False)

        frame = ctk.CTkFrame(toast, corner_radius=10, fg_color=("gray30", "gray30"))
        frame.pack(fill="both", expand=True, padx=2, pady=2)
        ctk.CTkLabel(
            frame,
            text="已复制 API Key",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=("#ffffff", "#ffffff"),
        ).pack(padx=24, pady=12)

        toast.update_idletasks()
        tw = toast.winfo_width()
        th = toast.winfo_height()
        p_x = top.winfo_x() + (top.winfo_width() - tw) // 2
        p_y = top.winfo_y() + (top.winfo_height() - th) // 2
        toast.geometry(f"+{p_x}+{p_y}")
        toast.after(1500, toast.destroy)


class SettingsDialog(ctk.CTkToplevel):
    RIPPLE_COLORS = {
        "淡蓝色": "#aaddff",
        "淡绿色": "#aaffaa",
        "淡紫色": "#ddaaff",
        "淡粉色": "#ffaacc",
        "淡橙色": "#ffccaa",
        "淡白色": "#ffffff",
    }

    def __init__(self, parent, interval_sec: int, autostart: bool, theme: str = "dark", ripple_color: str = "#aaddff"):
        super().__init__(parent)
        self.title("设置")
        self.geometry("360x400")
        self.resizable(False, False)
        self.result = None

        self._interval_var = tk.StringVar(value=str(interval_sec))
        self._autostart_var = tk.BooleanVar(value=autostart)
        self._theme_var = tk.StringVar(value="暗黑模式" if theme == "dark" else "白色模式")

        reverse_colors = {v: k for k, v in self.RIPPLE_COLORS.items()}
        current_ripple_name = reverse_colors.get(ripple_color, "淡蓝色")
        self._ripple_var = tk.StringVar(value=current_ripple_name)

        self._setup_ui()
        self.grab_set()
        self.lift()

    def _setup_ui(self):
        ctk.CTkLabel(self, text="自动刷新间隔（秒）", font=ctk.CTkFont(size=14)).pack(pady=(20, 5))
        ctk.CTkLabel(self, text="最少 10 秒，推荐 60 秒", font=ctk.CTkFont(size=11), text_color="gray").pack()

        entry_frame = ctk.CTkFrame(self, fg_color="transparent")
        entry_frame.pack(pady=(10, 15))
        entry = ctk.CTkEntry(entry_frame, textvariable=self._interval_var, width=120, justify="center")
        entry.pack(side="left", padx=5)
        ctk.CTkLabel(entry_frame, text="秒", font=ctk.CTkFont(size=13)).pack(side="left")

        ctk.CTkLabel(self, text="主题", font=ctk.CTkFont(size=14)).pack(pady=(0, 5))
        theme_menu = ctk.CTkOptionMenu(
            self,
            values=["暗黑模式", "白色模式"],
            variable=self._theme_var,
            width=150
        )
        theme_menu.pack(pady=(0, 10))

        ctk.CTkLabel(self, text="波纹颜色", font=ctk.CTkFont(size=14)).pack(pady=(0, 5))
        ripple_menu = ctk.CTkOptionMenu(
            self,
            values=list(self.RIPPLE_COLORS.keys()),
            variable=self._ripple_var,
            width=150
        )
        ripple_menu.pack(pady=(0, 10))

        autostart_frame = ctk.CTkFrame(self, fg_color="transparent")
        autostart_frame.pack(pady=(0, 15))
        self._autostart_cb = ctk.CTkCheckBox(
            autostart_frame, text="开机自动启动", variable=self._autostart_var
        )
        self._autostart_cb.pack()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack()
        ctk.CTkButton(btn_frame, text="保存", width=100, command=self._on_save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="取消", width=100, fg_color="gray", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        try:
            val = int(self._interval_var.get().strip())
            theme = "dark" if self._theme_var.get() == "暗黑模式" else "light"
            ripple_color = self.RIPPLE_COLORS.get(self._ripple_var.get(), "#aaddff")
            self.result = (max(10, val), self._autostart_var.get(), theme, ripple_color)
            self.destroy()
        except ValueError:
            pass

    @classmethod
    def show(cls, parent, interval_sec: int, autostart: bool, theme: str = "dark", ripple_color: str = "#aaddff"):
        dlg = cls(parent, interval_sec, autostart, theme, ripple_color)
        dlg.wait_window()
        return dlg.result


class MainWindow(ctk.CTk):
    CLOSE_ACTION_HIDE = "hide"
    CLOSE_ACTION_EXIT = "exit"

    def __init__(self, config: AppConfig, on_switch_to_floating: Callable = None, on_apply_theme: Callable = None):
        super().__init__()
        self._config = config
        self._on_switch_to_floating = on_switch_to_floating
        self._on_apply_theme = on_apply_theme
        self._account_rows: list[AccountRow] = []
        self._close_action = self.CLOSE_ACTION_HIDE
        self._schedule_callback: Optional[Callable] = None
        self._settings_callback: Optional[Callable] = None
        self._autostart_callback: Optional[Callable] = None
        self._save_callback: Optional[Callable] = None
        self._on_view_curve_callback: Optional[Callable] = None
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
        self._rebuild_account_list()

    def _on_minimize(self, event):
        if event.widget == self and self.state() == 'iconic':
            self._cancel_focus_check()
            self.withdraw()
            if self._on_switch_to_floating:
                self._on_switch_to_floating()

    def start_focus_monitor(self):
        self._cancel_focus_check()
        self._focus_check_loop()

    def _cancel_focus_check(self):
        if self._focus_check_id is not None:
            self.after_cancel(self._focus_check_id)
            self._focus_check_id = None

    def _focus_check_loop(self):
        if not self.winfo_exists():
            return
        if self.state() == "withdrawn":
            self._focus_check_id = self.after(1000, self._focus_check_loop)
            return
        for w in self.winfo_children():
            if isinstance(w, ctk.CTkToplevel):
                self._focus_check_id = self.after(500, self._focus_check_loop)
                return
        try:
            focused = self.focus_get()
        except (KeyError, Exception):
            focused = None
        if focused is None or not self._is_self_or_descendant(focused):
            self._cancel_focus_check()
            self.withdraw()
            if self._on_switch_to_floating:
                self._on_switch_to_floating()
        else:
            self._focus_check_id = self.after(500, self._focus_check_loop)

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
        self.interval_label.pack(side="right")
        self.interval_label.bind("<Double-Button-1>", self._on_interval_double_click)
        self._update_interval_label()

    def _rebuild_account_list(self):
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
                on_view_curve=self._on_view_curve_callback,
            )
            row.pack(fill="x", pady=2)
            row.key_label.bind("<ButtonPress-1>", lambda e, i=idx: self._on_drag_press(i, e))
            row.key_label.bind("<B1-Motion>", lambda e: self._on_drag_motion(e))
            row.key_label.bind("<ButtonRelease-1>", lambda e: self._on_drag_release(e))
            self._account_rows.append(row)

    def _on_drag_press(self, idx: int, event):
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
            except Exception:
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
            except Exception:
                pass
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
            self._notify_save()

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
            self._notify_save()

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
            self._notify_save()

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
        self._notify_save()

    def _on_manual_refresh(self):
        if self._schedule_callback:
            self._schedule_callback()

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

    def set_refresh_callback(self, callback: Callable):
        self._schedule_callback = callback

    def set_settings_callback(self, callback: Callable):
        self._settings_callback = callback

    def set_autostart_callback(self, callback: Callable):
        self._autostart_callback = callback

    def set_save_callback(self, callback: Callable):
        self._save_callback = callback

    def set_view_curve_callback(self, callback: Callable):
        self._on_view_curve_callback = callback
        for row in self._account_rows:
            row._on_view_curve = callback

    def set_status(self, text: str):
        self.status_label.configure(text=text)

    def _on_settings(self):
        result = SettingsDialog.show(
            self,
            self._config.settings.interval_sec,
            self._config.settings.autostart,
            self._config.settings.theme,
            self._config.settings.ripple_color,
        )
        if result is not None:
            interval, autostart, theme, ripple_color = result
            self._config.settings.interval_sec = interval
            self._config.settings.autostart = autostart
            self._config.settings.theme = theme
            self._config.settings.ripple_color = ripple_color
            AnimationHelper.set_ripple_color(ripple_color)
            self._update_interval_label()
            if self._settings_callback:
                self._settings_callback(interval)
            if self._autostart_callback:
                self._autostart_callback(autostart)
            if self._on_apply_theme:
                self._on_apply_theme(theme)
            self._notify_save()

    def _update_interval_label(self):
        sec = self._config.settings.interval_sec
        if sec >= 60:
            self.interval_label.configure(text=f"刷新间隔: {sec // 60}分钟")
        else:
            self.interval_label.configure(text=f"刷新间隔: {sec}秒")

    def _notify_save(self):
        if self._save_callback:
            self._save_callback()
