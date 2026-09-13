from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from theme_models import Theme, ThemeLayer, THEME_LAYER_FIELDS, MODE_LIGHT, MODE_DARK


"""主题编辑器（Qt 版，ISSUE-THM-04，迁移线 Phase D）。

颜色矩阵（11 语义色 × 亮/暗双套）+ 实时预览面板 + 保存到用户主题目录 +
导入/导出 JSON + 重置默认。保存后经 ThemeManager.rescan 热加载并广播
theme_changed（QSS 全窗立即重着色，THM-05 链路复用）。

栈兼容：纯 Qt 模块，由 App 按需创建（非模态窗口）。
"""

# 编辑主题时基于哪个内置主题作为重置模板
_RESET_TEMPLATE = "monet_water_lilies"


class ThemeEditorWindow(QWidget):
    """可视化主题编辑器：颜色矩阵 + 预览 + 导入导出。"""

    def __init__(self, parent, theme_manager, builtin_dir: str, user_dir: str, event_bus=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("主题编辑器")
        self.resize(760, 560)
        self.setMinimumSize(640, 480)

        self._theme_manager = theme_manager
        self._builtin_dir = builtin_dir
        self._user_dir = user_dir
        self._event_bus = event_bus

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # 顶部：编辑目标选择 + 显示名 + 新建
        top = QHBoxLayout()
        top.addWidget(QLabel("编辑主题"))
        self._name_edit = QLineEdit()
        self._name_edit.setFixedWidth(140)
        self._target_combo = QComboBox()
        self._target_combo.currentTextChanged.connect(self._on_target_changed)
        top.addWidget(self._target_combo, 1)
        top.addWidget(QLabel("显示名"))
        top.addWidget(self._name_edit)
        new_btn = QPushButton("新建…", objectName="flat")
        new_btn.clicked.connect(self._on_new_theme)
        top.addWidget(new_btn)
        root.addLayout(top)
        # 注意：_reload_targets 在矩阵/预览构建完成后调用（_on_target_changed 依赖 swatches）

        # 中部：颜色矩阵（左）+ 预览（右）
        body = QHBoxLayout()
        body.addWidget(self._build_matrix(), 3)
        body.addWidget(self._build_preview(), 2)
        root.addLayout(body, 1)

        # 底部：操作按钮
        btns = QHBoxLayout()
        save_btn = QPushButton("保存")
        export_btn = QPushButton("导出 JSON…", objectName="flat")
        import_btn = QPushButton("导入 JSON…", objectName="flat")
        reset_btn = QPushButton("重置为默认", objectName="flat")
        save_btn.clicked.connect(self._on_save)
        export_btn.clicked.connect(self._on_export)
        import_btn.clicked.connect(self._on_import)
        reset_btn.clicked.connect(self._on_reset)
        for b in (save_btn, export_btn, import_btn, reset_btn):
            btns.addWidget(b)
        btns.addStretch(1)
        root.addLayout(btns)

        self._reload_targets()

    # ---- UI 构建 ----

    def _build_matrix(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea, QGridLayout

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        matrix_host = QWidget()
        self._matrix_grid = QGridLayout(matrix_host)
        self._matrix_grid.setVerticalSpacing(4)
        self._swatches: dict[tuple[str, str], QPushButton] = {}
        self._hex_labels: dict[tuple[str, str], QLabel] = {}

        self._matrix_grid.addWidget(QLabel("<b>语义色</b>"), 0, 0)
        self._matrix_grid.addWidget(QLabel("<b>亮色变体</b>"), 0, 1)
        self._matrix_grid.addWidget(QLabel("<b>暗色变体</b>"), 0, 2)
        for r, field in enumerate(THEME_LAYER_FIELDS, start=1):
            self._matrix_grid.addWidget(QLabel(field), r, 0)
            for c, mode in ((1, MODE_LIGHT), (2, MODE_DARK)):
                key = (field, mode)
                swatch = QPushButton()
                swatch.setFixedSize(56, 24)
                swatch.setCursor(Qt.PointingHandCursor)
                swatch.clicked.connect(lambda _=False, k=key: self._on_pick(k))
                hex_label = QLabel("", objectName="muted")
                self._matrix_grid.addWidget(swatch, r, c)
                self._matrix_grid.addWidget(hex_label, r, c + 2)
                self._swatches[key] = swatch
                self._hex_labels[key] = hex_label
        scroll.setWidget(matrix_host)
        return scroll

    def _build_preview(self) -> QWidget:
        card = QFrame(objectName="card")
        layout = QVBoxLayout(card)
        layout.setSpacing(6)
        layout.addWidget(QLabel("实时预览", objectName="title"))
        btn_row = QHBoxLayout()
        btn_row.addWidget(QPushButton("主操作"))
        flat = QPushButton("次要", objectName="flat")
        btn_row.addWidget(flat)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)
        layout.addWidget(QLabel("卡片示例文本（surface 底 + text 色）"))
        muted = QLabel("次要文本 text_muted", objectName="muted")
        layout.addWidget(muted)
        self._preview_balance = QLabel("¥100.50 | $20.00", objectName="balance")
        layout.addWidget(self._preview_balance)
        ok_row = QHBoxLayout()
        ok_row.addWidget(QLabel("●", objectName="statusOk"))
        ok_row.addWidget(QLabel("正常"))
        warn = QLabel("●", objectName="statusError")
        warn.setStyleSheet(f"color: {self._warn_hex()}; background: transparent;")
        ok_row.addWidget(warn)
        ok_row.addWidget(QLabel("警告/余额不足"))
        ok_row.addStretch(1)
        layout.addLayout(ok_row)
        layout.addStretch(1)

        # 预览色实时跟随编辑值：以行内样式覆盖全局 QSS
        self._preview_styles = {
            "primary": btn_row.itemAt(0).widget(),
            "surface_card": card,
            "muted": muted,
        }
        return card

    @staticmethod
    def _warn_hex() -> str:
        try:
            from qss import SEMANTIC_WARN
            return SEMANTIC_WARN
        except Exception:
            return "#ff9800"

    # ---- 编辑状态 ----

    def _current_theme(self) -> Theme:
        name = self._current_name()
        theme = self._theme_manager.get(name)
        if theme is None:
            theme = self._theme_manager.get(_RESET_TEMPLATE)
        if theme is None:
            from theme_manager import ThemeManager as _TM
            raise RuntimeError("注册表中无可用主题模板")
        return theme

    def _current_name(self) -> str:
        idx = self._target_combo.currentIndex()
        return self._target_combo.itemData(idx) or _RESET_TEMPLATE

    def _on_target_changed(self, _text: str):
        theme = self._current_theme()
        if theme is None:
            return
        self._name_edit.setText(theme.label)
        for field in THEME_LAYER_FIELDS:
            for mode in (MODE_LIGHT, MODE_DARK):
                key = (field, mode)
                color = getattr(theme.layer(mode), field)
                self._apply_swatch(key, color)

    def _apply_swatch(self, key, color: str):
        self._swatches[key].setStyleSheet(
            f"background-color: {color}; border: 1px solid #888; border-radius: 4px;")
        self._hex_labels[key].setText(color)

    def _on_pick(self, key):
        field, mode = key
        current = self._hex_labels[key].text() or "#000000"
        color = QColorDialog.getColor(QColor(current), self, f"选择 {field}（{mode}）")
        if not color.isValid():
            return
        self._apply_swatch(key, color.name().upper())
        self._refresh_preview()

    def _refresh_preview(self):
        """行内预览色跟随编辑值（编辑即所见）。"""
        primary = self._hex_labels[("primary", MODE_LIGHT)].text()
        card = self._preview_styles["surface_card"]
        card.setStyleSheet(
            f"QFrame#card{{background-color: {self._hex_labels[('surface', MODE_LIGHT)].text()};"
            f"border: 1px solid {self._hex_labels[('border', MODE_LIGHT)].text()}; border-radius: 8px;}}")
        self._preview_styles["primary"].setStyleSheet(
            f"background-color: {primary}; color: #FFFFFF; border: none; border-radius: 6px; padding: 6px 14px;")

    # ---- 保存 / 导入 / 导出 / 重置 ----

    def _collect_theme(self) -> Theme:
        light = {f: self._hex_labels[(f, MODE_LIGHT)].text() for f in THEME_LAYER_FIELDS}
        dark = {f: self._hex_labels[(f, MODE_DARK)].text() for f in THEME_LAYER_FIELDS}
        label = self._name_edit.text().strip() or "自定义主题"
        return Theme(
            name=self._current_name(),
            label=label,
            light=ThemeLayer(**light),
            dark=ThemeLayer(**dark),
            ripple_color=light["primary"],
            description="主题编辑器生成（ISSUE-THM-04）",
        )

    def _on_save(self):
        theme = self._collect_theme()
        os.makedirs(self._user_dir, exist_ok=True)
        path = os.path.join(self._user_dir, f"{theme.name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(theme.to_dict(), f, ensure_ascii=False, indent=2)
        self._theme_manager.register(theme)  # 立即生效（THM-03 热加载语义）
        self._broadcast(theme)
        QMessageBox.information(self, "主题编辑器", f"已保存到用户主题目录：\n{path}")

    def _on_export(self):
        theme = self._collect_theme()
        path, _ = QFileDialog.getSaveFileName(
            self, "导出主题", f"{theme.name}.json", "主题 JSON (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(theme.to_dict(), f, ensure_ascii=False, indent=2)

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入主题", "", "主题 JSON (*.json)")
        if not path:
            return
        try:
            theme = self._theme_manager.import_theme(path)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"主题文件无效：\n{e}")
            return
        self._reload_targets(select=theme.name)
        self._broadcast(theme)

    def _on_reset(self):
        theme = self._current_theme()
        builtin = self._theme_manager.get(_RESET_TEMPLATE)
        if builtin is None:
            return
        # 以内置模板为底重置当前编辑视图（不自动保存，用户确认保存才落盘）
        self._name_edit.setText(theme.label)
        for field in THEME_LAYER_FIELDS:
            self._apply_swatch((field, MODE_LIGHT), getattr(builtin.light, field))
            self._apply_swatch((field, MODE_DARK), getattr(builtin.dark, field))
        self._refresh_preview()

    def _on_new_theme(self):
        name, ok = QInputDialog.getText(self, "新建主题", "主题唯一标识（英文，如 my_theme）：")
        if not ok or not name or not name.strip():
            return
        name = name.strip().lower().replace(" ", "_")
        template = self._current_theme()
        theme = Theme(
            name=name, label=template.label,
            light=template.light, dark=template.dark,
            ripple_color=template.ripple_color, description="新建主题",
        )
        self._theme_manager.register(theme)
        self._reload_targets(select=name)

    # ---- 辅助 ----

    def _broadcast(self, theme: Theme):
        if self._event_bus is not None:
            self._event_bus.publish(
                "theme_changed",
                payload={
                    "name": theme.name,
                    "label": theme.label,
                    "mode": self._theme_manager.current_mode,
                    "layer": theme.layer(self._theme_manager.current_mode),
                    "ripple_color": theme.ripple_color,
                },
                source="theme_editor",
            )

    def _reload_targets(self, select: str | None = None):
        self._target_combo.blockSignals(True)
        self._target_combo.clear()
        for name in self._theme_manager.names():
            theme = self._theme_manager.get(name)
            self._target_combo.addItem(theme.label if theme else name, userData=name)
        if select:
            idx = self._target_combo.findData(select)
            if idx >= 0:
                self._target_combo.setCurrentIndex(idx)
        self._target_combo.blockSignals(False)
        self._on_target_changed(self._target_combo.currentText())
