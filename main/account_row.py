from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from config import AccountConfig, mask_api_key
from balance_checker import BalanceStatus, PROVIDERS
from scheduler import BalanceResult
from animations import AnimationHelper


"""单账户行组件。

每行显示：标签名、脱敏 API Key、Provider、余额、状态灯、删除按钮。
支持双击复制 Key、双击余额查看趋势曲线、拖拽排序。
"""


class AccountRow(ctk.CTkFrame):
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
        """调度器回调入口：根据状态更新余额文字、颜色和状态灯。"""
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
