from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")

import matplotlib.font_manager as _fm
_CHINESE_FONTS = ['Microsoft YaHei', 'SimHei', 'DengXian', 'Noto Sans CJK SC']
_FONT_NAMES = {f.name for f in _fm.fontManager.ttflist}
_CHOSEN_FONT = next((f for f in _CHINESE_FONTS if f in _FONT_NAMES), None)
if _CHOSEN_FONT:
    matplotlib.rcParams['font.sans-serif'] = [_CHOSEN_FONT] + matplotlib.rcParams.get('font.sans-serif', [])
    matplotlib.rcParams['axes.unicode_minus'] = False
    matplotlib.rcParams['font.size'] = 10

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates

from usage_history import UsageHistory, _hash_key

COLOR_BALANCE = "#ce93d8"

TIME_RANGES = [
    ("1小时", 3600, 60),
    ("7小时", 25200, 300),
    ("24小时", 86400, 300),
    ("7天", 604800, 3600),
]

_TIME_FORMATS = {
    "1小时": "%H:%M",
    "7小时": "%H:%M",
    "24小时": "%H:%M",
    "7天": "%m-%d",
}


def _get_theme_colors():
    if ctk.get_appearance_mode() == "Light":
        return dict(bg="#ffffff", axes="#f0f0f0", text="#333333",
                    grid="#cccccc", title="#222222", label="#333333", tick="#222222")
    return dict(bg="#2b2b2b", axes="#333333", text="#cccccc",
                grid="#444444", title="#eeeeee", label="#cccccc", tick="#cccccc")


class BalanceCurveWindow(ctk.CTkToplevel):
    _anim_duration_ms: int = 1000
    _anim_frame_delay_ms: int = 16
    _animating: bool = False
    _anim_timer: Optional[str] = None
    _anim_x_min: Optional[float] = None
    _anim_x_max: Optional[float] = None
    _anim_total_frames: int = 0

    def __init__(self, parent, account_label: str, api_key: str, uid: str, history: UsageHistory):
        super().__init__(parent)
        self.title(f"余额趋势 — {account_label}")
        self.geometry("750x520")
        self.minsize(550, 400)
        self.resizable(True, True)

        self._api_key_hash = _hash_key(api_key)
        self._uid = uid
        self._history = history
        self._account_label = account_label

        self._canvas: Optional[FigureCanvasTkAgg] = None

        self._setup_ui()
        self._render(animate=True)

        self.grab_set()
        self.lift()
        self.focus()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        toolbar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            toolbar,
            text=f"账号: {self._account_label}",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 15))

        range_values = [r[0] for r in TIME_RANGES]
        self._range_menu = ctk.CTkOptionMenu(
            toolbar,
            values=range_values,
            width=100,
        )
        self._range_menu.grid(row=0, column=1, padx=5)
        self._range_menu.set("24小时")
        self._range_menu.configure(command=self._on_range_change)

        self._balance_label = ctk.CTkLabel(
            toolbar,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="e",
        )
        self._balance_label.grid(row=0, column=2, padx=5, sticky="e")

    def _on_range_change(self, _choice):
        self._render(animate=True)

    def _get_range_params(self):
        now = time.time()
        range_label = self._range_menu.get()
        for _l, duration, bucket in TIME_RANGES:
            if _l == range_label:
                return now - duration, range_label
        return now - 86400, "24小时"

    def _render(self, animate: bool = False):
        self._cancel_animation()
        since, range_label = self._get_range_params()
        balance_history = self._history.get_balance_history(self._uid, since)
        self._draw_chart(balance_history, range_label, animate)

    def _draw_chart(self, balance_history, range_label: str, animate: bool):
        if self._canvas:
            self._canvas.get_tk_widget().destroy()
            self._canvas = None

        tc = _get_theme_colors()
        fig = Figure(figsize=(9, 5), dpi=100)
        fig.patch.set_facecolor(tc["bg"])

        ax = fig.add_subplot(111)
        ax.set_facecolor(tc["axes"])

        if not balance_history:
            ax.text(0.5, 0.5, "暂无余额变更记录", ha="center", va="center",
                    transform=ax.transAxes, color=tc["text"], fontsize=12)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            fig.tight_layout()
            self._canvas = FigureCanvasTkAgg(fig, master=self)
            canvas_widget = self._canvas.get_tk_widget()
            canvas_widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
            self.grid_rowconfigure(1, weight=1)
            self._canvas.draw()
            return

        times = [datetime.fromtimestamp(b.timestamp) for b in balance_history]
        values = [b.balance for b in balance_history]
        currency = balance_history[0].currency
        symbol = "¥" if currency == "CNY" else "$"

        latest = values[-1]
        self._balance_label.configure(text=f"当前余额: {symbol}{latest:,.4f}")

        fmt = _TIME_FORMATS.get(range_label, "%H:%M")
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
        ax.xaxis.set_major_locator(locator)

        ax.set_title("余额趋势", fontsize=13, color=tc["title"], pad=8)
        ax.set_ylabel(f"余额 ({symbol})", fontsize=11)
        ax.set_xlabel("时间", fontsize=11)
        _style_ax(ax, tc)

        fig.tight_layout()

        self._canvas = FigureCanvasTkAgg(fig, master=self)
        canvas_widget = self._canvas.get_tk_widget()
        canvas_widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.grid_rowconfigure(1, weight=1)
        self._canvas.draw()

        self._times = times
        self._values = values
        self._fig = fig
        self._ax = ax
        self._tc = tc

        self._line, = ax.plot(times, values, color=COLOR_BALANCE, linewidth=1.5,
                               marker=".", markersize=3)  # type: ignore[arg-type]
        self._fill = ax.fill_between(times, values, alpha=0.15, color=COLOR_BALANCE)  # type: ignore[arg-type]

        if animate and len(times) > 0:
            self._canvas.draw()
            self._animate_draw()
        else:
            self._canvas.draw()

    def _animate_draw(self, _idx: int = 0):
        if not self._canvas or not self._ax:
            return
        if self._animating:
            return
        self._animating = True

        n = len(self._times)
        if n < 2:
            self._animating = False
            return

        x_data = mdates.date2num(self._times)
        self._anim_x_min = float(x_data[0])
        self._anim_x_max = float(x_data[-1])
        if self._anim_x_max <= self._anim_x_min:
            self._anim_x_max = self._anim_x_min + 1.0

        self._anim_total_frames = max(1, self._anim_duration_ms // self._anim_frame_delay_ms)
        self._ax.set_xlim(self._anim_x_min, self._anim_x_min)
        self._canvas.draw()
        self._animate_frame(0)

    def _animate_frame(self, frame: int):
        if not self._canvas or not self._ax or self._anim_x_min is None or self._anim_x_max is None:
            self._animating = False
            self._anim_timer = None
            return

        total = self._anim_total_frames
        progress = (frame + 1) / total

        if progress >= 1.0:
            self._ax.set_xlim(self._anim_x_min, self._anim_x_max)
            self._canvas.draw()
            self._animating = False
            self._anim_timer = None
            return

        eased = 1.0 - (1.0 - progress) ** 2
        current_x_max = self._anim_x_min + (self._anim_x_max - self._anim_x_min) * eased
        self._ax.set_xlim(self._anim_x_min, current_x_max)
        self._canvas.draw()

        self._anim_timer = self.after(
            self._anim_frame_delay_ms,
            lambda: self._animate_frame(frame + 1),
        )

    def _cancel_animation(self):
        self._animating = False
        if self._anim_timer is not None:
            self.after_cancel(self._anim_timer)
            self._anim_timer = None


def _style_ax(ax, tc):
    ax.set_facecolor(tc["axes"])
    ax.tick_params(colors=tc["tick"], labelsize=10)
    for spine in ax.spines.values():
        spine.set_color(tc["grid"])
    ax.grid(True, color=tc["grid"], linewidth=0.4, alpha=0.5)
    ax.yaxis.label.set_color(tc["label"])
    ax.xaxis.label.set_color(tc["label"])
