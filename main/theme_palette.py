from __future__ import annotations

import colorsys

from theme_models import Theme, ThemeLayer, THEME_LAYER_FIELDS


"""主题颜色数学工具：HEX 解析、WCAG 相对亮度/对比度、种子色派生色板。

ISSUE-THM-02：内置莫奈主题的对比度校验依赖本模块。
ISSUE-THM-06：种子色 → 完整亮/暗双套 Theme 派生（tonal palette 思路，
参考 PRD 7.1.5 与 Material You / Monet）。

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


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{round(r):02X}{round(g):02X}{round(b):02X}"


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def hex_to_hsv(color: str) -> tuple[float, float, float]:
    """HEX → (h∈[0,360), s∈[0,1], v∈[0,1])。非法输入抛 ValueError。"""
    r, g, b = hex_to_rgb(color)
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return h * 360.0, s, v


def hsv_to_hex(h: float, s: float, v: float) -> str:
    """(h∈[0,360), s∈[0,1], v∈[0,1]) → HEX。"""
    h = (h % 360.0) / 360.0
    s = _clamp(s, 0.0, 1.0)
    v = _clamp(v, 0.0, 1.0)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return rgb_to_hex(r * 255.0, g * 255.0, b * 255.0)


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


# ============================================================================
# ISSUE-THM-06：种子色派生（逻辑半）
# ============================================================================

# 明度可派生范围：极端种子色（v<0.10 或 >0.95）钳制到此区间
_DERIVE_V_MIN = 0.10
_DERIVE_V_MAX = 0.95
# 暗变体背景明度区间（莫奈深色，非纯黑）
_DARK_BG_V_MIN = 0.12
_DARK_BG_V_MAX = 0.16


def _fit_text_color(
    h: float,
    s: float,
    bg_hex: str,
    start_v: float,
    direction: float,
    target: float,
    floor: float = 0.04,
    ceil: float = 1.0,
) -> str:
    """沿 direction 方向调整明度直至对比度达标（THM-06 硬校验 + 自动复验）。

    返回第一个达标的颜色；若到明度边界仍未达标（理论不可达，
    明度极限处对比度必然越过 4.5/3.0），返回边界颜色尽力而为。
    """
    v = start_v
    for _ in range(32):
        candidate = hsv_to_hex(h, s, v)
        if contrast_ratio(candidate, bg_hex) >= target:
            return candidate
        v += direction * 0.03
        if v < floor or v > ceil:
            return hsv_to_hex(h, s, _clamp(v, floor, ceil))
    return hsv_to_hex(h, s, _clamp(v, floor, ceil))


def derive_theme(seed: str, name: str = "custom", label: str = "自定义") -> Theme:
    """种子色 → 完整亮/暗双套 Theme（ISSUE-THM-06 逻辑半）。

    派生规则（PRD 7.1.5）：
    - primary：种子色调；亮变体压低明度/饱和度（白字对比 ≥ 4.5:1），暗变体提亮一阶
    - background/surface：种子色调中性色；亮变体明度 ~96%，暗变体 12–16%（莫奈深色）
    - secondary/accent：种子色相偏移 ∓35°
    - text/text_muted/border：按背景明度生成中性阶，硬校验 WCAG AA
    - success/warning/danger：固定语义色相，按背景明度适配深浅

    种子色非法抛 ValueError；明度超出 [0.10, 0.95] 自动钳制。
    """
    h, s, v = hex_to_hsv(seed)  # 非法种子在此抛 ValueError
    v = _clamp(v, _DERIVE_V_MIN, _DERIVE_V_MAX)

    # ---- 亮变体 ----
    light_bg = hsv_to_hex(h, 0.08, 0.96)
    light_surface = hsv_to_hex(h, 0.04, 1.0)
    # primary：从种子明度/饱和度起步，压暗至白字对比 ≥ 4.5:1
    light_primary = _fit_text_color(
        h, max(s * 0.85, 0.25), "#FFFFFF", _clamp(v * 0.72, 0.30, 0.62),
        direction=-1.0, target=WCAG_AA_NORMAL, floor=0.25,
    )
    light_secondary = hsv_to_hex((h - 35.0) % 360.0, s * 0.55, 0.66)
    light_accent = hsv_to_hex((h + 35.0) % 360.0, s * 0.80, 0.78)
    light_text = _fit_text_color(h, 0.10, light_bg, 0.30, direction=-1.0, target=WCAG_AA_NORMAL)
    light_text_muted = _fit_text_color(h, 0.08, light_bg, 0.50, direction=-1.0, target=WCAG_AA_LARGE)
    light_border = hsv_to_hex(h, 0.10, 0.82)
    light = ThemeLayer(
        background=light_bg,
        surface=light_surface,
        primary=light_primary,
        secondary=light_secondary,
        accent=light_accent,
        text=light_text,
        text_muted=light_text_muted,
        border=light_border,
        success=hsv_to_hex(145.0, 0.45, 0.45),
        warning=hsv_to_hex(42.0, 0.62, 0.60),
        danger=hsv_to_hex(6.0, 0.52, 0.48),
    )

    # ---- 暗变体（莫奈深色，非纯黑）----
    dark_bg_v = _clamp(0.12 + (v - _DERIVE_V_MIN) * 0.05, _DARK_BG_V_MIN, _DARK_BG_V_MAX)
    dark_bg = hsv_to_hex(h, 0.18, dark_bg_v)
    dark_surface = hsv_to_hex(h, 0.16, dark_bg_v + 0.07)
    # primary 提亮一阶；需在暗背景上可见（对比 ≥ 3:1）
    dark_primary = _fit_text_color(
        h, max(s * 0.70, 0.20), dark_bg, 0.75,
        direction=1.0, target=WCAG_AA_LARGE,
    )
    dark_secondary = hsv_to_hex((h - 35.0) % 360.0, s * 0.45, 0.82)
    dark_accent = hsv_to_hex((h + 35.0) % 360.0, s * 0.60, 0.86)
    dark_text = _fit_text_color(h, 0.10, dark_bg, 0.90, direction=1.0, target=WCAG_AA_NORMAL)
    dark_text_muted = _fit_text_color(h, 0.08, dark_bg, 0.70, direction=1.0, target=WCAG_AA_LARGE)
    dark_border = hsv_to_hex(h, 0.12, dark_bg_v + 0.18)
    dark = ThemeLayer(
        background=dark_bg,
        surface=dark_surface,
        primary=dark_primary,
        secondary=dark_secondary,
        accent=dark_accent,
        text=dark_text,
        text_muted=dark_text_muted,
        border=dark_border,
        success=hsv_to_hex(145.0, 0.40, 0.72),
        warning=hsv_to_hex(42.0, 0.55, 0.80),
        danger=hsv_to_hex(6.0, 0.45, 0.74),
    )

    return Theme(
        name=name,
        label=label,
        light=light,
        dark=dark,
        ripple_color=light_primary,
        description=f"由种子色 {seed} 派生（ISSUE-THM-06）",
    )
