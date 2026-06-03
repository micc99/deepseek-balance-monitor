from __future__ import annotations

import math
import tkinter as tk
from typing import Optional, Callable, Tuple

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter, ImageTk


# ─── Glass Theme Design Tokens ───────────────────────────────────────────────

class GlassTheme:
    """Centralized design tokens for the acrylic glass UI."""

    # Gradient background: soft blue-white
    GRADIENT_TOP = (220, 235, 250)       # #DCEBFA  soft blue
    GRADIENT_BOTTOM = (245, 248, 255)    # #F5F8FF  near-white

    # Acrylic panel (frosted glass)
    ACRYLIC_LIGHT = (255, 255, 255, 140)     # semi-transparent white
    ACRYLIC_DARK = (240, 244, 252, 160)
    ACRYLIC_BORDER = (200, 215, 235, 100)    # subtle blue border
    ACRYLIC_HIGHLIGHT = (255, 255, 255, 180)  # top-edge shine

    # Card (pure white with subtle shadow)
    CARD_BG = (255, 255, 255)
    CARD_SHADOW = (180, 200, 220, 60)
    CARD_HIGHLIGHT = (240, 245, 255, 120)

    # Text
    TEXT_PRIMARY = "#1a2a3a"
    TEXT_SECONDARY = "#6b7d8e"
    TEXT_MUTED = "#9aabb8"
    TEXT_ACCENT = "#3a7bd5"

    # Status colors
    STATUS_OK = "#2e7d32"
    STATUS_WARN = "#ef6c00"
    STATUS_ERROR = "#c62828"
    STATUS_LOADING = "#9e9e9e"

    # Button
    BTN_PRIMARY = "#3a7bd5"
    BTN_PRIMARY_HOVER = "#2e6bc4"
    BTN_SECONDARY = "#e8edf3"
    BTN_SECONDARY_HOVER = "#d0d8e4"
    BTN_DANGER = "#e57373"
    BTN_DANGER_HOVER = "#c62828"

    # Glass squeeze animation
    SQUEEZE_SCALE = 0.93          # shrink to 93%
    SQUEEZE_DARKEN = 25           # darken by 25 units
    SQUEEZE_DOWN_MS = 60          # press duration
    SQUEEZE_RELEASE_MS = 120      # release bounce duration

    # Spacing
    RADIUS_PANEL = 16
    RADIUS_CARD = 12
    RADIUS_BTN = 8
    SHADOW_OFFSET = 4
    SHADOW_BLUR = 12

    # Ripple (kept for backward compat, but glass squeeze is primary)
    RIPPLE_COLOR = "#aaddff"

    @classmethod
    def hex_to_rgb(cls, hex_color: str) -> Tuple[int, int, int]:
        if not hex_color or hex_color == "transparent":
            return (255, 255, 255)
        h = hex_color.lstrip("#")
        if len(h) < 6:
            return (255, 255, 255)
        try:
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
        except ValueError:
            return (255, 255, 255)

    @classmethod
    def rgb_to_hex(cls, r: int, g: int, b: int) -> str:
        return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"

    @classmethod
    def darken(cls, hex_color: str, amount: int = 20) -> str:
        r, g, b = cls.hex_to_rgb(hex_color)
        return cls.rgb_to_hex(r - amount, g - amount, b - amount)

    @classmethod
    def lighten(cls, hex_color: str, amount: int = 20) -> str:
        r, g, b = cls.hex_to_rgb(hex_color)
        return cls.rgb_to_hex(r + amount, g + amount, b + amount)


# ─── Gradient & Acrylic Rendering (PIL-based) ───────────────────────────────

class AcrylicRenderer:
    """Renders gradient backgrounds and frosted-glass panels using PIL."""

    _cache: dict[str, ImageTk.PhotoImage] = {}

    @staticmethod
    def render_gradient(width: int, height: int,
                        top: Tuple[int, ...] = GlassTheme.GRADIENT_TOP,
                        bottom: Tuple[int, ...] = GlassTheme.GRADIENT_BOTTOM) -> Image.Image:
        """Create a vertical linear gradient image."""
        img = Image.new("RGB", (width, max(height, 1)))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            t = y / max(height - 1, 1)
            r = int(top[0] + (bottom[0] - top[0]) * t)
            g = int(top[1] + (bottom[1] - top[1]) * t)
            b = int(top[2] + (bottom[2] - top[2]) * t)
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        return img

    @staticmethod
    def render_acrylic_panel(width: int, height: int, radius: int = GlassTheme.RADIUS_PANEL) -> Image.Image:
        """Create a frosted-glass style panel with soft edges and highlight."""
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Main body - semi-transparent white
        fill = GlassTheme.ACRYLIC_LIGHT
        draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius, fill=fill)

        # Top highlight band (simulates light refraction)
        highlight_h = max(2, height // 5)
        for y in range(highlight_h):
            alpha = int(GlassTheme.ACRYLIC_HIGHLIGHT[3] * (1 - y / highlight_h))
            draw.line([(radius, y), (width - radius, y)],
                      fill=(*GlassTheme.ACRYLIC_HIGHLIGHT[:3], alpha))

        # Border
        border_color = GlassTheme.ACRYLIC_BORDER
        draw.rounded_rectangle([0, 0, width - 1, height - 1], radius=radius,
                               outline=border_color, width=1)

        return img

    @staticmethod
    def render_card_shadow(width: int, height: int, offset: int = GlassTheme.SHADOW_OFFSET,
                           blur: int = GlassTheme.SHADOW_BLUR, radius: int = GlassTheme.RADIUS_CARD) -> Image.Image:
        """Create a soft drop shadow for cards."""
        pad = blur * 2
        sw = width + pad * 2
        sh = height + pad * 2
        shadow = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shadow)
        color = GlassTheme.CARD_SHADOW
        draw.rounded_rectangle(
            [pad, pad + offset, pad + width, pad + height + offset],
            radius=radius, fill=color
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
        return shadow

    @classmethod
    def gradient_to_tk(cls, width: int, height: int, cache_key: str = "") -> ImageTk.PhotoImage:
        """Get a cached tkinter PhotoImage of a gradient."""
        if cache_key and cache_key in cls._cache:
            return cls._cache[cache_key]
        img = cls.render_gradient(width, height)
        tk_img = ImageTk.PhotoImage(img)
        if cache_key:
            cls._cache[cache_key] = tk_img
        return tk_img

    @classmethod
    def clear_cache(cls):
        cls._cache.clear()


# ─── Gradient Background Canvas ──────────────────────────────────────────────

class GradientCanvas(tk.Canvas):
    """A Canvas that draws a gradient background, auto-resizing."""

    def __init__(self, master, **kwargs):
        kwargs.pop("bg", None)
        super().__init__(master, highlightthickness=0, bd=0, bg="", **kwargs)
        self._tk_img: Optional[ImageTk.PhotoImage] = None
        self._img_id: Optional[int] = None
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        w, h = event.width, event.height
        if w < 2 or h < 2:
            return
        img = AcrylicRenderer.render_gradient(w, h)
        self._tk_img = ImageTk.PhotoImage(img)
        if self._img_id is None:
            self._img_id = self.create_image(0, 0, anchor="nw", image=self._tk_img)
        else:
            self.itemconfig(self._img_id, image=self._tk_img)


# ─── Glass Squeeze Button Animation ──────────────────────────────────────────

class GlassSqueeze:
    """
    Glass squeeze button animation:
    On press  -> instantly darken + shrink (scale down)
    On release -> bounce back to original with slight overshoot
    Feels like pressing on glass - crisp, tactile, minimal.
    """

    @staticmethod
    def bind(widget, command: Optional[Callable] = None,
             base_color: Optional[str] = None, hover_color: Optional[str] = None):
        """
        Bind glass-squeeze animation to a widget.
        If command is provided, it fires on release.
        base_color/hover_color override the widget's own colors if given.
        """
        state = {"pressed": False, "animating": False}

        def _get_colors():
            try:
                fg = widget.cget("fg_color")
                if isinstance(fg, tuple):
                    mode = ctk.get_appearance_mode()
                    fg = fg[0] if mode == "Light" else fg[1]
                return base_color or fg
            except Exception:
                return base_color or "#3a7bd5"

        def _get_hover():
            if hover_color:
                return hover_color
            try:
                hc = widget.cget("hover_color")
                if isinstance(hc, tuple):
                    mode = ctk.get_appearance_mode()
                    hc = hc[0] if mode == "Light" else hc[1]
                return hc
            except Exception:
                return None

        def _on_press(event):
            if state["animating"]:
                return
            state["pressed"] = True
            color = _get_colors()
            darkened = GlassTheme.darken(color, GlassTheme.SQUEEZE_DARKEN)
            try:
                widget.configure(fg_color=darkened)
            except Exception:
                pass
            # Scale effect via geometry shrink (if widget supports width/height)
            try:
                w = widget.cget("width")
                h = widget.cget("height")
                if w and h:
                    shrink_w = int(w * GlassTheme.SQUEEZE_SCALE)
                    shrink_h = int(h * GlassTheme.SQUEEZE_SCALE)
                    widget.configure(width=shrink_w, height=shrink_h)
            except Exception:
                pass

        def _on_release(event):
            if not state["pressed"]:
                return
            state["pressed"] = False
            state["animating"] = True

            color = _get_colors()
            # Restore with slight delay for tactile feel
            def _restore():
                try:
                    widget.configure(fg_color=color)
                except Exception:
                    pass
                # Restore original size
                try:
                    # We need to know original size - read from widget's geometry
                    # This is handled by the caller passing size info
                    pass
                except Exception:
                    pass
                state["animating"] = False

            widget.after(GlassTheme.SQUEEZE_DOWN_MS, _restore)

            if command:
                widget.after(GlassTheme.SQUEEZE_DOWN_MS + 20, command)

        def _on_enter(event):
            if not state["pressed"]:
                hc = _get_hover()
                if hc:
                    try:
                        widget.configure(fg_color=hc)
                    except Exception:
                        pass

        def _on_leave(event):
            if not state["pressed"]:
                color = _get_colors()
                try:
                    widget.configure(fg_color=color)
                except Exception:
                    pass

        widget.bind("<Button-1>", _on_press, add="+")
        widget.bind("<ButtonRelease-1>", _on_release, add="+")
        widget.bind("<Enter>", _on_enter, add="+")
        widget.bind("<Leave>", _on_leave, add="+")

    @staticmethod
    def bind_ctk_button(btn: "ctk.CTkButton", command: Optional[Callable] = None):
        """
        Optimized binding for CTkButton that preserves original dimensions
        and handles the full glass-squeeze lifecycle.
        """
        state = {"pressed": False, "orig_w": None, "orig_h": None}

        def _get_color():
            try:
                fg = btn.cget("fg_color")
                if isinstance(fg, tuple):
                    mode = ctk.get_appearance_mode()
                    return fg[0] if mode == "Light" else fg[1]
                return fg
            except Exception:
                return GlassTheme.BTN_PRIMARY

        def _on_press(event):
            if state["pressed"]:
                return
            state["pressed"] = True
            state["orig_w"] = btn.cget("width")
            state["orig_h"] = btn.cget("height")

            color = _get_color()
            darkened = GlassTheme.darken(color, GlassTheme.SQUEEZE_DARKEN)
            try:
                btn.configure(fg_color=darkened)
                if state["orig_w"]:
                    btn.configure(width=int(state["orig_w"] * GlassTheme.SQUEEZE_SCALE))
                if state["orig_h"]:
                    btn.configure(height=int(state["orig_h"] * GlassTheme.SQUEEZE_SCALE))
            except Exception:
                pass

        def _on_release(event):
            if not state["pressed"]:
                return
            state["pressed"] = False

            def _restore():
                try:
                    btn.configure(fg_color=_get_color())
                    if state["orig_w"]:
                        btn.configure(width=state["orig_w"])
                    if state["orig_h"]:
                        btn.configure(height=state["orig_h"])
                except Exception:
                    pass

            btn.after(GlassTheme.SQUEEZE_DOWN_MS, _restore)
            if command:
                btn.after(GlassTheme.SQUEEZE_DOWN_MS + 30, command)

        btn.bind("<Button-1>", _on_press, add="+")
        btn.bind("<ButtonRelease-1>", _on_release, add="+")


# ─── Legacy AnimationHelper (updated for glass theme) ────────────────────────

class AnimationHelper:
    """Animation utilities updated with glass-squeeze and acrylic effects."""

    _ripple_color = GlassTheme.RIPPLE_COLOR

    @staticmethod
    def set_ripple_color(color: str):
        AnimationHelper._ripple_color = color

    @staticmethod
    def fade_in(window, duration=300):
        steps = 15
        delay = duration // steps
        step_size = 1.0 / steps

        def _animate(current_alpha):
            if current_alpha >= 1.0:
                window.attributes("-alpha", 1.0)
                return
            window.attributes("-alpha", current_alpha)
            window.after(delay, _animate, current_alpha + step_size)

        window.attributes("-alpha", 0.0)
        _animate(0.0)

    @staticmethod
    def fade_out(window, duration=300, callback=None):
        steps = 15
        delay = duration // steps
        step_size = 1.0 / steps

        def _animate(current_alpha):
            if current_alpha <= 0.0:
                window.attributes("-alpha", 0.0)
                if callback:
                    callback()
                return
            window.attributes("-alpha", current_alpha)
            window.after(delay, _animate, current_alpha - step_size)

        _animate(1.0)

    @staticmethod
    def flash_widget(widget, color, duration=500):
        original_color = widget.cget("fg_color")
        widget.configure(fg_color=color)
        widget.after(duration, lambda: widget.configure(fg_color=original_color))

    @staticmethod
    def bind_ripple(widget, command=None):
        """Use glass-squeeze instead of ripple for a modern feel."""
        if command:
            GlassSqueeze.bind(widget, command=command)
        else:
            GlassSqueeze.bind(widget)

    @staticmethod
    def bind_glass_button(btn, command=None):
        """Bind glass-squeeze animation specifically to CTkButton."""
        GlassSqueeze.bind_ctk_button(btn, command)

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _rgb_to_hex(r: int, g: int, b: int) -> str:
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _create_ripple(widget, event):
        """Legacy ripple - kept for backward compatibility."""
        try:
            try:
                btn_color = widget.cget("fg_color")
                if isinstance(btn_color, tuple):
                    appearance = ctk.get_appearance_mode()
                    btn_color = btn_color[0] if appearance == "Light" else btn_color[1]
            except Exception:
                btn_color = None

            ripple_color = AnimationHelper._ripple_color

            w = widget.winfo_width()
            h = widget.winfo_height()
            if w <= 0 or h <= 0:
                return

            canvas = tk.Canvas(widget, width=w, height=h, highlightthickness=0)
            canvas.place(x=0, y=0)

            x = event.x
            y = event.y

            max_radius = math.sqrt(w * w + h * h)
            steps = 15
            delay = 25
            step_size = max_radius / steps

            base_r, base_g, base_b = AnimationHelper._hex_to_rgb(ripple_color)

            def _animate(radius, progress):
                if radius > max_radius or progress <= 0:
                    canvas.destroy()
                    return

                canvas.delete("ripple")
                alpha = progress

                r = int(base_r + (255 - base_r) * (1 - alpha))
                g = int(base_g + (255 - base_g) * (1 - alpha))
                b = int(base_b + (255 - base_b) * (1 - alpha))
                color = AnimationHelper._rgb_to_hex(
                    min(255, r), min(255, g), min(255, b)
                )

                canvas.create_oval(
                    x - radius, y - radius,
                    x + radius, y + radius,
                    fill=color, outline="", tags="ripple"
                )
                canvas.after(delay, _animate, radius + step_size, progress - 0.05)

            _animate(0, 0.4)
        except Exception:
            pass

    @staticmethod
    def _create_ripple_with_command(widget, event, command):
        AnimationHelper._create_ripple(widget, event)
        widget.after(50, command)


# ─── Acrylic Panel Widget ────────────────────────────────────────────────────

class AcrylicPanel(ctk.CTkFrame):
    """
    A frame styled to look like a frosted-glass acrylic panel.
    Renders a semi-transparent background with subtle highlight.
    """

    def __init__(self, master, corner_radius: int = GlassTheme.RADIUS_PANEL,
                 opacity: int = 140, **kwargs):
        # Set acrylic background
        base = GlassTheme.ACRYLIC_LIGHT
        acrylic_color = (*base[:3], opacity)
        r, g, b = acrylic_color[:3]
        kwargs.setdefault("fg_color", f"#{r:02x}{g:02x}{b:02x}")
        kwargs.setdefault("corner_radius", corner_radius)
        kwargs.setdefault("border_width", 1)
        kwargs.setdefault("border_color", "#c8d7eb")
        super().__init__(master, **kwargs)


# ─── Glass Card Widget ───────────────────────────────────────────────────────

class GlassCard(ctk.CTkFrame):
    """
    A pure-white card with subtle shadow and highlight.
    Represents task cards in the glass UI.
    """

    def __init__(self, master, corner_radius: int = GlassTheme.RADIUS_CARD, **kwargs):
        kwargs.setdefault("fg_color", "#ffffff")
        kwargs.setdefault("corner_radius", corner_radius)
        kwargs.setdefault("border_width", 0)
        super().__init__(master, **kwargs)


# ─── Shorthand factory ───────────────────────────────────────────────────────

def create_glass_button(master, text: str, command: Optional[Callable] = None,
                        width: int = 110, height: int = 32,
                        fg_color: str = GlassTheme.BTN_PRIMARY,
                        text_color: str = "#ffffff",
                        hover_color=None,
                        font_size: int = 13) -> ctk.CTkButton:
    """Factory for a button with glass-squeeze animation pre-bound."""
    btn = ctk.CTkButton(
        master,
        text=text,
        width=width,
        height=height,
        fg_color=fg_color,
        text_color=text_color,
        hover_color=hover_color if hover_color is not None else GlassTheme.darken(fg_color, 12),
        corner_radius=GlassTheme.RADIUS_BTN,
        font=ctk.CTkFont(size=font_size),
        command=None,  # we handle command via glass squeeze
    )
    GlassSqueeze.bind_ctk_button(btn, command=command)
    return btn
