from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QKeySequenceEdit,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


"""设置对话框（Qt 版，ISSUE-MIG-05）：刷新间隔、主题、波纹颜色、代理目标、开机自启。

代理目标变更后需重启程序才能生效（代理端口在启动时绑定）。
接口与 ctk 版一致：SettingsDialog.show(...) 返回
(interval, autostart, theme_mode, ripple_color, proxy_target) 或 None。

注：波纹动画已按 D6 决策移除，波纹颜色项仅维持配置兼容（无视觉效果）；
Phase D THM-06 将把主题区扩展为莫奈预设 + 自定义种子色。
"""


class SettingsDialog(QDialog):
    RIPPLE_COLORS = {
        "淡蓝色": "#aaddff",
        "淡绿色": "#aaffaa",
        "淡紫色": "#ddaaff",
        "淡粉色": "#ffaacc",
        "淡橙色": "#ffccaa",
        "淡白色": "#ffffff",
    }

    # 代理可转发的 API 提供商列表，值为各 provider 的域名
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
        proxy_token_display: str = "",
        hotkeys: dict | None = None,
        auto_float_on_focus_loss: bool = True,
    ):
        super().__init__(parent)
        self.setWindowTitle("设置")
        hotkeys = hotkeys or {}
        self.setFixedWidth(460)
        self.setModal(True)
        self.result = None

        reverse_colors = {v: k for k, v in self.RIPPLE_COLORS.items()}
        current_ripple_name = reverse_colors.get(ripple_color, "淡蓝色")
        reverse_targets = {v: k for k, v in self.PROXY_TARGETS.items()}
        current_target_name = reverse_targets.get(proxy_target, proxy_target)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(6)

        root.addWidget(QLabel("自动刷新间隔（秒）"))
        hint = QLabel("最少 10 秒，推荐 60 秒", objectName="muted")
        root.addWidget(hint)
        entry_row = QHBoxLayout()
        self._interval_edit = QLineEdit(str(interval_sec))
        self._interval_edit.setFixedWidth(120)
        self._interval_edit.setAlignment(Qt.AlignCenter)
        entry_row.addWidget(self._interval_edit)
        entry_row.addWidget(QLabel("秒"))
        entry_row.addStretch(1)
        root.addLayout(entry_row)

        root.addWidget(QLabel("主题"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["暗黑模式", "白色模式"])
        self._theme_combo.setCurrentText("暗黑模式" if theme == "dark" else "白色模式")
        self._theme_combo.setFixedWidth(150)
        root.addWidget(self._theme_combo)

        root.addWidget(QLabel("波纹颜色"))
        self._ripple_combo = QComboBox()
        self._ripple_combo.addItems(list(self.RIPPLE_COLORS.keys()))
        self._ripple_combo.setCurrentText(current_ripple_name)
        self._ripple_combo.setFixedWidth(150)
        root.addWidget(self._ripple_combo)

        root.addWidget(QLabel("代理目标 (用量记录)"))
        root.addWidget(QLabel("选择后需重启程序生效", objectName="muted"))
        self._proxy_combo = QComboBox()
        self._proxy_combo.addItems(list(self.PROXY_TARGETS.keys()))
        self._proxy_combo.setCurrentText(current_target_name)
        self._proxy_combo.setFixedWidth(150)
        root.addWidget(self._proxy_combo)

        self._autostart_check = QCheckBox("开机自动启动")
        root.addWidget(self._autostart_check)
        self._autostart_check.setChecked(autostart)

        # ISSUE-UX-02：可配置快捷键
        root.addWidget(QLabel("快捷键"))
        hk_row = QHBoxLayout()
        hk_row.addWidget(QLabel("切换悬浮窗"))
        from managers.hotkey_manager import pynput_to_qt
        self._toggle_edit = QKeySequenceEdit(QKeySequence(pynput_to_qt(hotkeys.get("toggle_window", ""))))
        hk_row.addWidget(self._toggle_edit)
        hk_row.addWidget(QLabel("手动刷新"))
        self._refresh_edit = QKeySequenceEdit(QKeySequence(pynput_to_qt(hotkeys.get("manual_refresh", ""))))
        hk_row.addWidget(self._refresh_edit)
        root.addLayout(hk_row)

        # ISSUE-UX-04：失焦行为开关
        self._auto_float_check = QCheckBox("失焦后自动最小化到悬浮窗")
        root.addWidget(self._auto_float_check)
        self._auto_float_check.setChecked(auto_float_on_focus_loss)

        # 代理 token 展示（只读，便于用户排查客户端配置）
        if proxy_token_display:
            root.addWidget(QLabel("代理鉴权 Token（已脱敏）"))
            root.addWidget(QLabel(proxy_token_display, objectName="muted"))
            root.addWidget(QLabel("客户端需在请求头携带 X-Proxy-Token 才能使用代理", objectName="muted"))

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
        try:
            val = int(self._interval_edit.text().strip())
        except ValueError:
            return
        theme = "dark" if self._theme_combo.currentText() == "暗黑模式" else "light"
        ripple_color = self.RIPPLE_COLORS.get(self._ripple_combo.currentText(), "#aaddff")
        proxy_target = self.PROXY_TARGETS.get(self._proxy_combo.currentText(), self._proxy_combo.currentText())
        def _to_pynput(seq: QKeySequence) -> str:
            """QKeySequence → pynput 修饰键格式（"Ctrl+Shift+B" → "<ctrl>+<shift>+b"）。"""
            if seq.isEmpty():
                return ""
            parts = [seg.lower() for seg in seq.toString().split("+") if seg]
            mod = {"ctrl", "shift", "alt", "meta", "win"}
            return "+".join(f"<{p}>" if p in mod else p for p in parts)

        self.result = (
            max(10, val),
            self._autostart_check.isChecked(),
            theme,
            ripple_color,
            proxy_target,
            {
                "toggle_window": _to_pynput(self._toggle_edit.keySequence()) or "<ctrl>+<shift>+b",
                "manual_refresh": _to_pynput(self._refresh_edit.keySequence()) or "<ctrl>+r",
            },
            self._auto_float_check.isChecked(),
        )
        self.accept()

    @classmethod
    def show(
        cls,
        parent,
        interval_sec: int,
        autostart: bool,
        theme: str = "dark",
        ripple_color: str = "#aaddff",
        proxy_target: str = "api.deepseek.com",
        proxy_token_display: str = "",
        hotkeys: dict | None = None,
        auto_float_on_focus_loss: bool = True,
    ):
        dlg = cls(
            parent,
            interval_sec,
            autostart,
            theme,
            ripple_color,
            proxy_target,
            proxy_token_display,
            hotkeys,
            auto_float_on_focus_loss,
        )
        dlg.exec()
        return dlg.result