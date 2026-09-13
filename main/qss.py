from __future__ import annotations

from theme_models import ThemeLayer


"""主题 token → QSS 渲染链（ISSUE-MIG-02 最小实现，Phase D THM-05/UX-06 扩展）。

约定：UI 代码不写死颜色，QSS 由 ThemeManager 当前 ThemeLayer 生成，
setStyleSheet 全局生效；theme_changed 事件触发重生成即全窗重着色。
D6 决策：波纹动画移除，以 QSS hover 过渡替代。
"""


def build_qss(layer: ThemeLayer) -> str:
    """由语义色层生成全局样式表。"""
    return f"""
* {{
    background-color: {layer.background};
    color: {layer.text};
    font-size: 13px;
    selection-background-color: {layer.primary};
    selection-color: #FFFFFF;
}}
QMainWindow, QWidget#central {{ background-color: {layer.background}; }}
QFrame#card {{ background-color: {layer.surface}; border: 1px solid {layer.border}; border-radius: 8px; }}

QPushButton {{
    background-color: {layer.primary};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{ background-color: {layer.accent}; }}
QPushButton:pressed {{ background-color: {layer.secondary}; }}
QPushButton:disabled {{ background-color: {layer.border}; color: {layer.text_muted}; }}

QPushButton#flat {{
    background-color: transparent;
    color: {layer.text};
    border: 1px solid {layer.border};
}}
QPushButton#flat:hover {{ background-color: {layer.surface}; }}

QLabel#title {{ font-size: 18px; font-weight: bold; }}
QLabel#muted, QLabel#status {{ color: {layer.text_muted}; font-size: 11px; }}
QLabel#balance {{ font-size: 15px; font-weight: bold; }}
QLabel#statusOk {{ color: {layer.success}; }}
QLabel#statusError {{ color: {layer.danger}; }}

QLineEdit, QComboBox, QSpinBox {{
    background-color: {layer.surface};
    border: 1px solid {layer.border};
    border-radius: 6px;
    padding: 4px 8px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border-color: {layer.primary}; }}

QScrollArea {{ border: none; background-color: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 8px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {layer.border}; border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {layer.text_muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QMenu {{
    background-color: {layer.surface};
    border: 1px solid {layer.border};
}}
QMenu::item:selected {{ background-color: {layer.primary}; color: #FFFFFF; }}
"""
