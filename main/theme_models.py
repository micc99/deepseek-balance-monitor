from __future__ import annotations

from dataclasses import dataclass, asdict


"""主题数据模型：ThemeLayer（单语义层亮/暗一套）与 Theme（完整主题）。

ISSUE-THM-01：字段集以 PRD 第 7.1.2 节为准，使用 dataclass（用户决策：
配置保留 dataclass，不引入 pydantic）。本模块为纯逻辑，禁止 import 任何
UI 框架（tkinter/customtkinter/PySide6），保证迁移到 Qt 后原样存活。

JSON 序列化格式（to_dict/from_dict）同时是 THM-02 内置主题 JSON 与
THM-03 用户主题 JSON 的文件契约：

    {
      "name": "monet_water_lilies",
      "label": "莫奈·睡莲",
      "description": "可选",
      "ripple_color": "#5B8AA6",
      "light": {"background": ..., 11 个语义色},
      "dark":  {"background": ..., 11 个语义色}
    }
"""

# 11 个语义色的固定顺序（PRD 7.1.2），供校验与编辑器枚举
THEME_LAYER_FIELDS = (
    "background",   # 主背景
    "surface",      # 卡片/面板背景
    "primary",      # 主操作色（按钮）
    "secondary",    # 次要操作色
    "accent",       # 强调色（高亮、链接）
    "text",         # 主文本
    "text_muted",   # 次要文本
    "border",       # 边框
    "success",      # 成功状态
    "warning",      # 警告状态
    "danger",       # 危险状态
)

# 亮/暗变体取值
MODE_LIGHT = "light"
MODE_DARK = "dark"


@dataclass
class ThemeLayer:
    """单个语义层颜色集合（一套完整配色，亮或暗）。"""
    background: str
    surface: str
    primary: str
    secondary: str
    accent: str
    text: str
    text_muted: str
    border: str
    success: str
    warning: str
    danger: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Theme:
    """完整主题定义：唯一名 + 显示名 + 亮/暗双变体。"""
    name: str             # 唯一标识（如 "monet_water_lilies"）
    label: str            # 显示名（如 "莫奈·睡莲"）
    light: ThemeLayer     # 亮色变体
    dark: ThemeLayer      # 暗色变体（莫奈深色，非纯黑）
    ripple_color: str = ""    # 波纹动画色（取亮变体值；暗变体由 UI 层从 dark.primary 派生）
    description: str = ""     # 主题描述

    def layer(self, mode: str) -> ThemeLayer:
        """按模式取对应变体，非法模式回退暗色。"""
        return self.light if mode == MODE_LIGHT else self.dark

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "ripple_color": self.ripple_color,
            "light": self.light.to_dict(),
            "dark": self.dark.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Theme":
        """从字典（JSON）反序列化，结构不合法抛 ValueError。

        校验范围：必需键存在且为字符串、11 个语义色齐全。
        不校验 HEX 格式（由调用方/派生算法负责，格式错误主题在
        THM-03 加载层降级跳过）。
        """
        if not isinstance(data, dict):
            raise ValueError("主题数据必须是对象")
        for key in ("name", "label"):
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"主题缺少有效字段: {key}")
        layers = {}
        for mode in (MODE_LIGHT, MODE_DARK):
            raw = data.get(mode)
            if not isinstance(raw, dict):
                raise ValueError(f"主题缺少 {mode} 变体")
            missing = [f for f in THEME_LAYER_FIELDS if not isinstance(raw.get(f), str)]
            if missing:
                raise ValueError(f"{mode} 变体缺少语义色字段: {', '.join(missing)}")
            layers[mode] = ThemeLayer(**{f: raw[f] for f in THEME_LAYER_FIELDS})
        ripple = data.get("ripple_color", "")
        if not isinstance(ripple, str):
            ripple = ""
        description = data.get("description", "")
        if not isinstance(description, str):
            description = ""
        return cls(
            name=data["name"].strip(),
            label=data["label"].strip(),
            light=layers[MODE_LIGHT],
            dark=layers[MODE_DARK],
            ripple_color=ripple,
            description=description,
        )
