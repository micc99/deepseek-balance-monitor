from __future__ import annotations


"""主题颜色数学工具：HEX 解析、WCAG 相对亮度与对比度。

ISSUE-THM-02：内置莫奈主题的对比度校验依赖本模块。
ISSUE-THM-06：种子色派生算法（tonal palette）将扩展本模块。

纯逻辑模块，禁止 import 任何 UI 框架（同 theme_models.py 约定）。
"""


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """解析 HEX 颜色为 (r, g, b)，支持 #RGB / #RRGGBB（# 可省略）。

    非法输入抛 ValueError（调用方负责降级/提示）。
    """
    s = (color or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        raise ValueError(f"非法 HEX 颜色: {color!r}")
    try:
        return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except ValueError:
        raise ValueError(f"非法 HEX 颜色: {color!r}") from None


def _channel_luminance(channel: int) -> float:
    """单通道 0-255 → WCAG 相对亮度分量（sRGB 伽马展开）。"""
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    """WCAG 2.x 相对亮度（0 黑 ~ 1 白）。"""
    r, g, b = hex_to_rgb(color)
    return (
        0.2126 * _channel_luminance(r)
        + 0.7152 * _channel_luminance(g)
        + 0.0722 * _channel_luminance(b)
    )


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 对比度：1.0（无对比）~ 21.0（黑白极值）。"""
    la = relative_luminance(foreground)
    lb = relative_luminance(background)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


# WCAG AA 阈值：普通文本 4.5:1，大号/次要文本 3:1
WCAG_AA_NORMAL = 4.5
WCAG_AA_LARGE = 3.0


def wcag_aa_ok(text: str, background: str, large: bool = False) -> bool:
    """判断 文本/背景 组合是否达 WCAG AA（普通文本 4.5:1，大文本 3:1）。"""
    return contrast_ratio(text, background) >= (WCAG_AA_LARGE if large else WCAG_AA_NORMAL)
