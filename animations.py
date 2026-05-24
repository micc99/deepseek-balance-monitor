import math
import tkinter as tk
import customtkinter as ctk


class AnimationHelper:
    _ripple_color = "#aaddff"

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
        if command:
            widget.bind("<Button-1>", lambda e: AnimationHelper._create_ripple_with_command(widget, e, command), add="+")
        else:
            widget.bind("<Button-1>", lambda e: AnimationHelper._create_ripple(widget, e), add="+")

    @staticmethod
    def _create_ripple_with_command(widget, event, command):
        AnimationHelper._create_ripple(widget, event)
        widget.after(50, command)

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
        try:
            # 获取按钮的颜色作为基础色
            try:
                btn_color = widget.cget("fg_color")
                if isinstance(btn_color, tuple):
                    appearance = ctk.get_appearance_mode()
                    btn_color = btn_color[0] if appearance == "Light" else btn_color[1]
            except:
                btn_color = None

            # 使用配置的波纹颜色
            ripple_color = AnimationHelper._ripple_color

            # 创建一个临时的 Canvas 覆盖在按钮上
            w = widget.winfo_width()
            h = widget.winfo_height()
            if w <= 0 or h <= 0:
                return

            # 创建 Canvas 作为覆盖层
            canvas = tk.Canvas(widget, width=w, height=h, highlightthickness=0)
            canvas.place(x=0, y=0)

            # 点击位置
            x = event.x
            y = event.y

            # 动画参数
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
