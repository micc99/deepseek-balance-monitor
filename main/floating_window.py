from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from config import WindowConfig
from animations import AnimationHelper


"""无边框悬浮窗。

主窗口最小化/关闭后显示，置顶、可拖拽。
双击恢复主窗口，右键弹出刷新/退出菜单。
由 App 按需创建和销毁（非 withdraw），以节省内存。
"""


class FloatingWindow(ctk.CTkToplevel):
    """紧凑型悬浮窗：标题 + 余额摘要 + 状态栏。"""
    def __init__(self, on_restore: Callable = None, on_refresh: Callable = None, on_exit: Callable = None):
        super().__init__()
        self._on_restore = on_restore
        self._on_refresh = on_refresh
        self._on_exit_cb = on_exit
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._account_count = 0
        self._status = "就绪"

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.geometry("260x120")

        self._setup_ui()
        self._bind_drag()
        AnimationHelper.fade_in(self, 300)

    def _setup_ui(self):
        self.configure(fg_color=("gray95", "gray17"))

        self._outer = ctk.CTkFrame(self, fg_color=("gray90", "gray20"), corner_radius=12)
        self._outer.pack(fill="both", expand=True, padx=3, pady=3)

        self._title_label = ctk.CTkLabel(
            self._outer,
            text="余额监控",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="gray",
        )
        self._title_label.pack(pady=(8, 2))

        self._balance_label = ctk.CTkLabel(
            self._outer,
            text="暂无数据",
            font=ctk.CTkFont(size=18, weight="bold"),
        )
        self._balance_label.pack(pady=(0, 4))

        self._status_label = ctk.CTkLabel(
            self._outer,
            text="0 个账号 | 就绪",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._status_label.pack()

    def _bind_drag(self):
        self._outer.bind("<Button-1>", self._on_drag_start)
        self._outer.bind("<B1-Motion>", self._on_drag_motion)
        self._title_label.bind("<Button-1>", self._on_drag_start)
        self._title_label.bind("<B1-Motion>", self._on_drag_motion)
        self._balance_label.bind("<Button-1>", self._on_drag_start)
        self._balance_label.bind("<B1-Motion>", self._on_drag_motion)
        self._status_label.bind("<Button-1>", self._on_drag_start)
        self._status_label.bind("<B1-Motion>", self._on_drag_motion)

        self._outer.bind("<Double-Button-1>", self._on_double)
        self._title_label.bind("<Double-Button-1>", self._on_double)
        self._balance_label.bind("<Double-Button-1>", self._on_double)
        self._status_label.bind("<Double-Button-1>", self._on_double)

        self._outer.bind("<Button-3>", self._on_right_click)
        self._title_label.bind("<Button-3>", self._on_right_click)
        self._balance_label.bind("<Button-3>", self._on_right_click)
        self._status_label.bind("<Button-3>", self._on_right_click)

    def _on_drag_start(self, event):
        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def _on_drag_motion(self, event):
        x = event.x_root - self._drag_offset_x
        y = event.y_root - self._drag_offset_y
        self.geometry(f"+{x}+{y}")

    def _on_double(self, event):
        if self._on_restore:
            def _restore():
                self.attributes("-alpha", 1.0)
                self._on_restore()
            AnimationHelper.fade_out(self, 300, callback=_restore)

    def _on_right_click(self, event):
        menu = tk.Menu(self, tearoff=0)
        if self._on_refresh:
            menu.add_command(label="立即刷新", command=self._on_refresh)
        menu.add_separator()
        menu.add_command(label="退出", command=self._on_exit)
        menu.post(event.x_root, event.y_root)

    def _on_exit(self):
        if self._on_exit_cb:
            self._on_exit_cb()

    def update_balance(self, total_display: str, account_count: int, status: str):
        self._account_count = account_count
        self._status = status
        self._balance_label.configure(text=total_display)
        self._status_label.configure(text=f"{account_count} 个账号 | {status}")

    def get_position(self) -> WindowConfig:
        return WindowConfig(x=self.winfo_x(), y=self.winfo_y())

    def set_position(self, pos: WindowConfig):
        if pos.x is not None and pos.y is not None:
            self.geometry(f"+{pos.x}+{pos.y}")
        else:
            self._center_on_screen()

    def _center_on_screen(self):
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"+{x}+{y}")
