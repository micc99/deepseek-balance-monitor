from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional

import customtkinter as ctk

from usage_history import UsageHistory

# ISSUE-PFM-01：matplotlib 延迟加载缓存。
# 启动时不 import matplotlib（首次 import 可达 200-500ms），
# 首次绘图时通过 _ensure_matplotlib() 执行 import + 字体配置，后续直接返回缓存。
_mpl_cache: dict = {}


def _ensure_matplotlib() -> dict:
    """延迟加载 matplotlib 模块并配置中文字体。

    首次调用时执行 import matplotlib + 字体配置（matplotlib.use("TkAgg")、
    rcParams 字体设置），后续调用直接返回缓存，避免重复初始化开销。

    Returns:
        dict: 包含 matplotlib 绘图所需对象的字典，键为：
            - 'matplotlib': matplotlib 模块本身
            - 'FigureCanvasTkAgg': TkAgg 后端的 Canvas 适配器
            - 'Figure': matplotlib Figure 类
    """
    if _mpl_cache:
        return _mpl_cache
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
    _mpl_cache['matplotlib'] = matplotlib
    _mpl_cache['FigureCanvasTkAgg'] = FigureCanvasTkAgg
    _mpl_cache['Figure'] = Figure
    return _mpl_cache

BAR_COLORS = {
    "dark": {"today": "#ce93d8", "week": "#90caf9", "month": "#a5d6a7"},
    "light": {"today": "#6a1b9a", "week": "#1565c0", "month": "#2e7d32"},
}
BAR_LABELS = ["today", "week", "month"]


def _start_of_day(dt: datetime) -> float:
    """当天 00:00:00 的 Unix 时间戳，用作查询下界。"""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def _start_of_week(dt: datetime) -> float:
    """本周一 00:00:00 的 Unix 时间戳。"""
    monday = dt - timedelta(days=dt.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def _start_of_month(dt: datetime) -> float:
    """本月 1 日 00:00:00 的 Unix 时间戳。"""
    first = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first.timestamp()


def _get_theme_colors():
    if ctk.get_appearance_mode() == "Light":
        return dict(bg="#ffffff", axes="#f0f0f0", text="#333333",
                    grid="#cccccc", title="#222222", label="#333333", tick="#222222")
    return dict(bg="#2b2b2b", axes="#333333", text="#cccccc",
                grid="#444444", title="#eeeeee", label="#cccccc", tick="#cccccc")


class UsageBarWindow(ctk.CTkToplevel):
    """用量概览窗口：分组柱状图展示各账户在今日/本周/本月的消耗金额。

    数据源：balance_snapshots 表，通过期初余额 - 期末余额计算消耗。
    如果 token_usage 表有数据（代理记录），也可切换为 token 维度。
    """

    def __init__(self, parent, history: UsageHistory, accounts: list):
        super().__init__(parent)
        self.title("用量概览")
        self.geometry("700x520")
        self.minsize(550, 400)
        self.resizable(True, True)

        self._history = history
        self._accounts = accounts

        # matplotlib 延迟加载：先不持有 Figure/Canvas 引用，首次绘图时才创建
        self._canvas = None
        self._fig = None
        self._loading_label: Optional[ctk.CTkLabel] = None

        self._setup_ui()
        # ISSUE-PFM-01：首次打开窗口时显示 loading 提示，避免空白等待
        self._show_loading()
        # 延迟一帧后实际绘图，让 loading 提示先渲染可见
        self.after(50, self._render)

        self.grab_set()
        self.lift()
        self.focus()

    def _show_loading(self):
        """ISSUE-PFM-01：显示加载提示，告知用户图表正在初始化。"""
        self._loading_label = ctk.CTkLabel(
            self,
            text="加载图表中...",
            font=ctk.CTkFont(size=14),
            text_color="gray",
        )
        self._loading_label.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self._loading_label.update_idletasks()

    def _hide_loading(self):
        """ISSUE-PFM-01：绘图完成后销毁 loading 提示。"""
        if self._loading_label is not None:
            try:
                self._loading_label.destroy()
            except Exception:
                pass
            self._loading_label = None

    def destroy(self):
        """关闭窗口时释放 matplotlib Figure，避免内存泄漏。

        matplotlib 的 Figure 对象不会随 tkinter 窗口销毁自动回收，
        必须显式 plt.close() 才能释放其内部缓存和渲染上下文。
        """
        if self._fig is not None:
            import matplotlib.pyplot as plt
            plt.close(self._fig)
            self._fig = None
        if self._canvas is not None:
            self._canvas.get_tk_widget().destroy()
            self._canvas = None
        super().destroy()

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=15, pady=(15, 5))
        toolbar.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(
            toolbar,
            text="用量概览",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, padx=(0, 15))

    def _render(self):
        # ISSUE-PFM-01：延迟加载 matplotlib，首次调用时执行 import + 字体配置
        mpl = _ensure_matplotlib()
        Figure = mpl['Figure']
        FigureCanvasTkAgg = mpl['FigureCanvasTkAgg']

        if self._canvas:
            self._canvas.get_tk_widget().destroy()
            self._canvas = None

        tc = _get_theme_colors()
        fig = Figure(figsize=(9, 5), dpi=100)
        fig.patch.set_facecolor(tc["bg"])
        self._fig = fig

        ax = fig.add_subplot(111)
        ax.set_facecolor(tc["axes"])

        now = datetime.now()
        periods = {
            "today": ("今日", _start_of_day(now)),
            "week": ("本周", _start_of_week(now)),
            "month": ("本月", _start_of_month(now)),
        }

        uid_map = {acc.uid: acc.label for acc in self._accounts}

        if not uid_map:
            ax.text(0.5, 0.5, "暂无账号数据", ha="center", va="center",
                    transform=ax.transAxes, color=tc["text"], fontsize=12)
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ax.spines.values():
                spine.set_visible(False)
            self._canvas = FigureCanvasTkAgg(fig, master=self)
            canvas_widget = self._canvas.get_tk_widget()
            canvas_widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
            self.grid_rowconfigure(1, weight=1)
            canvas_widget.update_idletasks()
            fig.tight_layout()
            self._canvas.draw()
            # ISSUE-PFM-01：绘图完成后销毁 loading 提示
            self._hide_loading()
            return

        all_uids = list(uid_map.keys())
        data: dict[str, dict[str, float]] = {}
        for period_key, (_, since) in periods.items():
            raw = self._history.get_balance_consumption(all_uids, since)
            data[period_key] = {uid_map.get(uid, uid): round(val, 2) for uid, val in raw.items()}

        labels = list(uid_map.values())
        x = range(len(labels))
        width = 0.25

        mode = "dark" if ctk.get_appearance_mode() == "Dark" else "light"
        colors = BAR_COLORS.get(mode, BAR_COLORS["dark"])

        offsets = [-width, 0, width]
        has_data = False
        for i, (period_key, period_label) in enumerate(zip(BAR_LABELS, ["今日", "本周", "本月"])):
            values = [data[period_key].get(lbl, 0.0) for lbl in labels]
            if any(v > 0 for v in values):
                has_data = True
            bars = ax.bar([p + offsets[i] for p in x], values, width,
                          label=period_label, color=colors[period_key], alpha=0.85)
            for bar, val in zip(bars, values):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.01,
                            f"¥{val:,.2f}", ha="center", va="bottom", fontsize=8, color=tc["tick"])

        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=11)
        ax.set_ylabel("消耗金额", fontsize=11)
        ax.set_title("用量概览", fontsize=13, color=tc["title"], pad=8)
        ax.legend(fontsize=10, loc="upper right")

        for spine in ax.spines.values():
            spine.set_color(tc["grid"])
        ax.grid(True, color=tc["grid"], linewidth=0.4, alpha=0.5, axis="y")
        ax.tick_params(colors=tc["tick"], labelsize=10)
        ax.yaxis.label.set_color(tc["label"])
        ax.xaxis.label.set_color(tc["label"])

        if not has_data:
            ax.text(0.5, 0.45, "暂无消耗记录", ha="center", va="center",
                    transform=ax.transAxes, color=tc["text"], fontsize=14, alpha=0.7)
            ax.text(0.5, 0.35, "余额未发生变更或无快照数据", ha="center", va="center",
                    transform=ax.transAxes, color=tc["text"], fontsize=10, alpha=0.5)

        self._canvas = FigureCanvasTkAgg(fig, master=self)
        canvas_widget = self._canvas.get_tk_widget()
        canvas_widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))
        self.grid_rowconfigure(1, weight=1)
        canvas_widget.update_idletasks()
        fig.tight_layout()
        self._canvas.draw()
        # ISSUE-PFM-01：绘图完成后销毁 loading 提示
        self._hide_loading()
