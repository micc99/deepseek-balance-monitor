from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from config import AccountConfig
from balance_checker import get_provider_list


"""添加/编辑账号的模态对话框（Qt 版，ISSUE-MIG-05）。

支持重复 API Key 检测：若 key 已存在，返回 duplicate_uid 而非 result，
调用方据此高亮已有行而非新增。
接口与 ctk 版一致：EditAccountDialog.show(...) 返回 (result, duplicate_uid)。
"""


class EditAccountDialog(QDialog):
    def __init__(self, parent, title: str, account: Optional[AccountConfig] = None, default_label: str = "",
                 existing_accounts: Optional[list[AccountConfig]] = None, exclude_uid: Optional[str] = None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedWidth(400)
        self.setModal(True)
        self.result: Optional[AccountConfig] = None
        self.duplicate_uid: Optional[str] = None
        self._account = account
        self._default_label = default_label
        self._existing_accounts = existing_accounts or []
        self._exclude_uid = exclude_uid

        # ISSUE-ARC-06：注册表快照（运行时注册的 Provider 立即出现在下拉中）
        providers = get_provider_list()
        self._provider_keys = [p[0] for p in providers]
        self._provider_names = [f"{p[1]} ({p[2]})" for p in providers]

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(6)

        root.addWidget(QLabel("标签名称"))
        self._label_edit = QLineEdit(account.label if account else default_label)
        root.addWidget(self._label_edit)

        root.addWidget(QLabel("API Key"))
        self._key_edit = QLineEdit(account.api_key if account else "")
        self._key_edit.setPlaceholderText("sk-...")
        root.addWidget(self._key_edit)

        root.addWidget(QLabel("服务商"))
        self._provider_combo = QComboBox()
        self._provider_combo.addItems(self._provider_names)
        default_provider = account.provider if account else "deepseek"
        if default_provider in self._provider_keys:
            self._provider_combo.setCurrentIndex(self._provider_keys.index(default_provider))
        root.addWidget(self._provider_combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消", objectName="flat")
        save_btn.setFixedWidth(100)
        cancel_btn.setFixedWidth(100)
        save_btn.clicked.connect(self._on_save)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

    def _on_save(self):
        label = self._label_edit.text().strip() or self._default_label
        key = self._key_edit.text().strip()
        if not key:
            return
        for acc in self._existing_accounts:
            if acc.uid == self._exclude_uid:
                continue
            if acc.api_key == key:
                self.duplicate_uid = acc.uid
                self.reject()
                return
        provider = self._provider_keys[self._provider_combo.currentIndex()]
        self.result = AccountConfig(label=label, api_key=key, provider=provider)
        self.accept()

    @classmethod
    def show(cls, parent, title: str, account: Optional[AccountConfig] = None, default_label: str = "",
             existing_accounts: Optional[list[AccountConfig]] = None, exclude_uid: Optional[str] = None):
        dlg = cls(parent, title, account, default_label, existing_accounts, exclude_uid)
        dlg.exec()
        return dlg.result, dlg.duplicate_uid
