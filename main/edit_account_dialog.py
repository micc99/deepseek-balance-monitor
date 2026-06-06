from __future__ import annotations

import tkinter as tk
from typing import Optional

import customtkinter as ctk

from config import AccountConfig


class EditAccountDialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, account: Optional[AccountConfig] = None, default_label: str = "",
                 existing_accounts: Optional[list[AccountConfig]] = None, exclude_uid: Optional[str] = None):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x280")
        self.resizable(False, False)
        self.result: Optional[AccountConfig] = None
        self.duplicate_uid: Optional[str] = None
        self._account = account
        self._default_label = default_label
        self._existing_accounts = existing_accounts or []
        self._exclude_uid = exclude_uid

        self._label_var = tk.StringVar(value=account.label if account else default_label)
        self._key_var = tk.StringVar(value=account.api_key if account else "")
        self._provider_var = tk.StringVar(value=account.provider if account else "deepseek")

        self._setup_ui()
        self.grab_set()
        self.lift()

    def _setup_ui(self):
        from balance_checker import PROVIDERS

        ctk.CTkLabel(self, text="标签名称", font=ctk.CTkFont(size=13)).pack(pady=(20, 0))
        ctk.CTkEntry(self, textvariable=self._label_var, width=300).pack(pady=(5, 10))

        ctk.CTkLabel(self, text="API Key", font=ctk.CTkFont(size=13)).pack()
        key_entry = ctk.CTkEntry(self, textvariable=self._key_var, width=300)
        key_entry.pack(pady=(5, 10))

        ctk.CTkLabel(self, text="服务商", font=ctk.CTkFont(size=13)).pack()
        provider_names = [f"{p.label} ({p.description})" for p in PROVIDERS.values()]
        provider_keys = list(PROVIDERS.keys())
        self._provider_names = provider_names
        self._provider_keys = provider_keys

        def _on_provider_select(choice):
            idx = provider_names.index(choice) if choice in provider_names else 0
            self._provider_var.set(provider_keys[idx])

        provider_menu = ctk.CTkOptionMenu(
            self, values=provider_names, command=_on_provider_select
        )
        provider_menu.pack(pady=(5, 15))

        default_key = self._account.provider if self._account else "deepseek"
        if default_key in provider_keys:
            idx = provider_keys.index(default_key)
            provider_menu.set(provider_names[idx])

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack()
        ctk.CTkButton(btn_frame, text="保存", width=100, command=self._on_save).pack(
            side="left", padx=5
        )
        ctk.CTkButton(
            btn_frame, text="取消", width=100, fg_color="gray", command=self.destroy
        ).pack(side="left", padx=5)

    def _on_save(self):
        label = self._label_var.get().strip() or self._default_label
        key = self._key_var.get().strip()
        if not key:
            return
        for acc in self._existing_accounts:
            if acc.uid == self._exclude_uid:
                continue
            if acc.api_key == key:
                self.duplicate_uid = acc.uid
                self.destroy()
                return
        self.result = AccountConfig(label=label, api_key=key, provider=self._provider_var.get())
        self.destroy()

    @classmethod
    def show(cls, parent, title: str, account: Optional[AccountConfig] = None, default_label: str = "",
             existing_accounts: Optional[list[AccountConfig]] = None, exclude_uid: Optional[str] = None):
        dlg = cls(parent, title, account, default_label, existing_accounts, exclude_uid)
        dlg.wait_window()
        return dlg.result, dlg.duplicate_uid
