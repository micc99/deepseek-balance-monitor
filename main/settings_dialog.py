from __future__ import annotations

import tkinter as tk

import customtkinter as ctk


class SettingsDialog(ctk.CTkToplevel):
    RIPPLE_COLORS = {
        "淡蓝色": "#aaddff",
        "淡绿色": "#aaffaa",
        "淡紫色": "#ddaaff",
        "淡粉色": "#ffaacc",
        "淡橙色": "#ffccaa",
        "淡白色": "#ffffff",
    }

    PROXY_TARGETS = {
        "DeepSeek": "api.deepseek.com",
        "SiliconFlow": "api.siliconflow.cn",
        "Moonshot": "api.moonshot.cn",
        "OpenRouter": "openrouter.ai",
        "智谱 GLM": "open.bigmodel.cn",
    }

    def __init__(self, parent, interval_sec: int, autostart: bool, theme: str = "dark",
                 ripple_color: str = "#aaddff", proxy_target: str = "api.deepseek.com"):
        super().__init__(parent)
        self.title("设置")
        self.geometry("360x480")
        self.resizable(False, False)
        self.result = None

        self._interval_var = tk.StringVar(value=str(interval_sec))
        self._autostart_var = tk.BooleanVar(value=autostart)
        self._theme_var = tk.StringVar(value="暗黑模式" if theme == "dark" else "白色模式")

        reverse_colors = {v: k for k, v in self.RIPPLE_COLORS.items()}
        current_ripple_name = reverse_colors.get(ripple_color, "淡蓝色")
        self._ripple_var = tk.StringVar(value=current_ripple_name)

        reverse_targets = {v: k for k, v in self.PROXY_TARGETS.items()}
        current_target_name = reverse_targets.get(proxy_target, proxy_target)
        self._proxy_var = tk.StringVar(value=current_target_name)

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

        ctk.CTkLabel(self, text="代理目标 (用量记录)", font=ctk.CTkFont(size=14)).pack(pady=(0, 5))
        ctk.CTkLabel(self, text="选择后需重启程序生效", font=ctk.CTkFont(size=11), text_color="gray").pack()
        proxy_menu = ctk.CTkOptionMenu(
            self,
            values=list(self.PROXY_TARGETS.keys()),
            variable=self._proxy_var,
            width=150
        )
        proxy_menu.pack(pady=(5, 10))

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
            proxy_target = self.PROXY_TARGETS.get(self._proxy_var.get(), self._proxy_var.get())
            self.result = (max(10, val), self._autostart_var.get(), theme, ripple_color, proxy_target)
            self.destroy()
        except ValueError:
            pass

    @classmethod
    def show(cls, parent, interval_sec: int, autostart: bool, theme: str = "dark",
             ripple_color: str = "#aaddff", proxy_target: str = "api.deepseek.com"):
        dlg = cls(parent, interval_sec, autostart, theme, ripple_color, proxy_target)
        dlg.wait_window()
        return dlg.result
