from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk


"""设置对话框：刷新间隔、主题、波纹颜色、代理目标、开机自启、凭证源管理。

代理目标变更后需重启程序才能生效（代理端口在启动时绑定）。

ISSUE-SEC-05：新增"凭证源管理"区域，用户可显式授权读取第三方凭证文件，
仅授权路径的 key 字段用于活跃账户标识（不影响余额查询）。
"""


class SettingsDialog(ctk.CTkToplevel):
    RIPPLE_COLORS = {
        "淡蓝色": "#aaddff",
        "淡绿色": "#aaffaa",
        "淡紫色": "#ddaaff",
        "淡粉色": "#ffaacc",
        "淡橙色": "#ffccaa",
        "淡白色": "#ffffff",
    }

    # 代理可转发的 API 提供商列表，值为各 provider 的域名
    # 用户选择后需重启程序使代理生效
    PROXY_TARGETS = {
        "DeepSeek": "api.deepseek.com",
        "SiliconFlow": "api.siliconflow.cn",
        "Moonshot": "api.moonshot.cn",
        "OpenRouter": "openrouter.ai",
        "智谱 GLM": "open.bigmodel.cn",
    }

    def __init__(
        self,
        parent,
        interval_sec: int,
        autostart: bool,
        theme: str = "dark",
        ripple_color: str = "#aaddff",
        proxy_target: str = "api.deepseek.com",
        active_key_sources: Optional[list[str]] = None,
        proxy_token_display: str = "",
    ):
        super().__init__(parent)
        self.title("设置")
        self.geometry("440x620")
        self.resizable(False, False)
        self.result = None

        self._interval_var = tk.StringVar(value=str(interval_sec))
        self._autostart_var = tk.BooleanVar(value=autostart)
        self._theme_var = tk.StringVar(value="暗黑模式" if theme == "dark" else "白色模式")
        self._active_key_sources: list[str] = list(active_key_sources or [])
        self._proxy_token_display = proxy_token_display  # 已脱敏的 token（hash）

        reverse_colors = {v: k for k, v in self.RIPPLE_COLORS.items()}
        current_ripple_name = reverse_colors.get(ripple_color, "淡蓝色")
        self._ripple_var = tk.StringVar(value=current_ripple_name)

        reverse_targets = {v: k for k, v in self.PROXY_TARGETS.items()}
        current_target_name = reverse_targets.get(proxy_target, proxy_target)
        self._proxy_var = tk.StringVar(value=current_target_name)

        self._setup_ui()
        self._refresh_credential_list()
        self.grab_set()
        self.lift()

    def _setup_ui(self):
        # 滚动容器：内容增多后支持滚动
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(scroll, text="自动刷新间隔（秒）", font=ctk.CTkFont(size=14)).pack(pady=(10, 5), anchor="w")
        ctk.CTkLabel(scroll, text="最少 10 秒，推荐 60 秒", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")

        entry_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        entry_frame.pack(pady=(5, 10), anchor="w")
        ctk.CTkEntry(entry_frame, textvariable=self._interval_var, width=120, justify="center").pack(side="left", padx=5)
        ctk.CTkLabel(entry_frame, text="秒", font=ctk.CTkFont(size=13)).pack(side="left")

        ctk.CTkLabel(scroll, text="主题", font=ctk.CTkFont(size=14)).pack(pady=(0, 5), anchor="w")
        ctk.CTkOptionMenu(
            scroll,
            values=["暗黑模式", "白色模式"],
            variable=self._theme_var,
            width=150,
        ).pack(pady=(0, 10), anchor="w")

        ctk.CTkLabel(scroll, text="波纹颜色", font=ctk.CTkFont(size=14)).pack(pady=(0, 5), anchor="w")
        ctk.CTkOptionMenu(
            scroll,
            values=list(self.RIPPLE_COLORS.keys()),
            variable=self._ripple_var,
            width=150,
        ).pack(pady=(0, 10), anchor="w")

        ctk.CTkLabel(scroll, text="代理目标 (用量记录)", font=ctk.CTkFont(size=14)).pack(pady=(0, 5), anchor="w")
        ctk.CTkLabel(scroll, text="选择后需重启程序生效", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")
        ctk.CTkOptionMenu(
            scroll,
            values=list(self.PROXY_TARGETS.keys()),
            variable=self._proxy_var,
            width=150,
        ).pack(pady=(5, 10), anchor="w")

        autostart_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        autostart_frame.pack(pady=(0, 15), anchor="w")
        ctk.CTkCheckBox(autostart_frame, text="开机自动启动", variable=self._autostart_var).pack()

        # ISSUE-SEC-05：凭证源管理
        cred_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        cred_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            cred_frame,
            text="凭证源管理（活跃账户标识）",
            font=ctk.CTkFont(size=14),
        ).pack(anchor="w")
        ctk.CTkLabel(
            cred_frame,
            text="仅授权路径的 key 字段用于标识活跃账户，不影响余额查询",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(anchor="w")

        self._cred_list_frame = ctk.CTkFrame(cred_frame, fg_color="transparent")
        self._cred_list_frame.pack(fill="x", pady=(5, 5))

        cred_btn_frame = ctk.CTkFrame(cred_frame, fg_color="transparent")
        cred_btn_frame.pack(anchor="w")
        ctk.CTkButton(
            cred_btn_frame, text="+ 添加凭证源", width=130,
            command=self._on_add_credential_source,
        ).pack(side="left", padx=(0, 5))

        # 代理 token 展示（只读，便于用户排查客户端配置）
        if self._proxy_token_display:
            ctk.CTkLabel(
                scroll,
                text="代理鉴权 Token（已脱敏）",
                font=ctk.CTkFont(size=14),
            ).pack(pady=(10, 5), anchor="w")
            ctk.CTkLabel(
                scroll,
                text=self._proxy_token_display,
                font=ctk.CTkFont(size=11),
                text_color="gray",
            ).pack(anchor="w")
            ctk.CTkLabel(
                scroll,
                text="客户端需在请求头携带 X-Proxy-Token 才能使用代理",
                font=ctk.CTkFont(size=11),
                text_color="gray",
            ).pack(anchor="w")

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="保存", width=100, command=self._on_save).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="取消", width=100, fg_color="gray", command=self.destroy).pack(side="left", padx=5)

    def _refresh_credential_list(self):
        """刷新凭证源列表 UI。"""
        for child in self._cred_list_frame.winfo_children():
            child.destroy()

        if not self._active_key_sources:
            ctk.CTkLabel(
                self._cred_list_frame,
                text="（暂无授权凭证源）",
                font=ctk.CTkFont(size=11),
                text_color="gray",
            ).pack(anchor="w")
            return

        for idx, path in enumerate(self._active_key_sources):
            row = ctk.CTkFrame(self._cred_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(
                row,
                text=path,
                font=ctk.CTkFont(size=11),
                anchor="w",
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(
                row, text="移除", width=50, fg_color="gray",
                command=lambda p=path: self._on_remove_credential_source(p),
            ).pack(side="right")

    def _on_add_credential_source(self):
        """ISSUE-SEC-05：添加凭证源。

        1. 弹出文件选择对话框
        2. 选择后弹窗告知用途
        3. 用户确认后记录路径
        """
        path = filedialog.askopenfilename(
            title="选择凭证源文件",
            filetypes=[("JSON 文件", "*.json"), ("所有文件", "*.*")],
            parent=self,
        )
        if not path:
            return

        # 路径安全校验：仅允许绝对路径，不含 ..
        if not os.path.isabs(path) or ".." in path:
            messagebox.showwarning(
                "路径不安全",
                "仅允许绝对路径，且不能包含 ..",
                parent=self,
            )
            return

        if path in self._active_key_sources:
            messagebox.showinfo("提示", "该路径已在授权列表中", parent=self)
            return

        # 弹窗告知用途，用户确认后记录
        confirm = messagebox.askyesno(
            "确认授权",
            f"将读取该文件的 key 字段用于活跃账户标识（不影响余额查询）：\n\n{path}\n\n是否确认授权？",
            parent=self,
        )
        if not confirm:
            return

        self._active_key_sources.append(path)
        self._refresh_credential_list()

    def _on_remove_credential_source(self, path: str):
        """ISSUE-SEC-05：移除已授权凭证源。"""
        if path in self._active_key_sources:
            self._active_key_sources.remove(path)
            self._refresh_credential_list()

    def _on_save(self):
        try:
            val = int(self._interval_var.get().strip())
            theme = "dark" if self._theme_var.get() == "暗黑模式" else "light"
            ripple_color = self.RIPPLE_COLORS.get(self._ripple_var.get(), "#aaddff")
            proxy_target = self.PROXY_TARGETS.get(self._proxy_var.get(), self._proxy_var.get())
            self.result = (
                max(10, val),
                self._autostart_var.get(),
                theme,
                ripple_color,
                proxy_target,
                list(self._active_key_sources),
            )
            self.destroy()
        except ValueError:
            pass

    @classmethod
    def show(
        cls,
        parent,
        interval_sec: int,
        autostart: bool,
        theme: str = "dark",
        ripple_color: str = "#aaddff",
        proxy_target: str = "api.deepseek.com",
        active_key_sources: Optional[list[str]] = None,
        proxy_token_display: str = "",
    ):
        dlg = cls(
            parent,
            interval_sec,
            autostart,
            theme,
            ripple_color,
            proxy_target,
            active_key_sources,
            proxy_token_display,
        )
        dlg.wait_window()
        return dlg.result
