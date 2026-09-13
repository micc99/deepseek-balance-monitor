from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from usage_history import UsageHistory
from qss import current_layer


"""用量概览窗口（Qt + pyqtgraph 版，ISSUE-MIG-07）。

分组柱状图展示各账户在今日/本周/本月的消耗金额。
数据源：balance_snapshots 表，通过期初余额 - 期末余额计算消耗。
ISSUE-PFM-01 延迟加载模式保留（pyqtgraph 首次打开时加载）。
配色直读主题 token（THM-05 AC3）：三组柱色 = primary/secondary/accent。
"""

_pg_cache: dict = {}


def _ensure_pyqtgraph() -> dict:
    """延迟加载 pyqtgraph 并缓存（ISSUE-PFM-01 模式延续）。"""
    if _pg_cache:
        return _pg_cache
    import pyqtgraph as pg
    pg.setConfigOptions(antialias=True)
    _pg_cache["pg"] = pg
    return _pg_cache


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


def _theme_colors() -> dict:
    layer = current_layer()
    if layer is not None:
        return dict(bg=layer.background, text=layer.text, grid=layer.border,
                    today=layer.primary, week=layer.secondary, month=layer.accent)
    return dict(bg="#2b2b2b", text="#cccccc", grid="#444444",
                today="#ce93d8", week="#90caf9", month="#a5d6a7")


class UsageBarWindow(QWidget):
    """用量概览窗口：分组柱状图展示各账户在今日/本周/本月的消耗金额。"""

    def __init__(self, parent, history: UsageHistory, accounts: list, event_bus=None):
        super().__init__(parent, Qt_Window())
        self.setWindowTitle("用量概览")
        self.resize(700, 520)
        self.setMinimumSize(550, 400)

        self._history = history
        self._accounts = accounts

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("用量概览", objectName="title"))
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self._plot_holder = QVBoxLayout()
        root.addLayout(self._plot_holder, 1)

        # ISSUE-THM-05：订阅主题变更，打开状态下实时重着色
        self._unsubscribe_theme = None
        if event_bus is not None:
            from PySide6.QtCore import QTimer
            self._unsubscribe_theme = event_bus.subscribe(
                "theme_changed", lambda _e: QTimer.singleShot(0, self._render))
            self.destroyed.connect(lambda: self._unsubscribe_theme and self._unsubscribe_theme())

        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._render)

    def _render(self):
        pg = _ensure_pyqtgraph()["pg"]
        tc = _theme_colors()

        since_map = {
            "今日": _start_of_day(datetime.now()),
            "本周": _start_of_week(datetime.now()),
            "本月": _start_of_month(datetime.now()),
        }
        uid_map = {acc.uid: acc.label for acc in self._accounts}

        self._plot = pg.PlotWidget()
        self._plot.setBackground(tc["bg"])
        self._plot_holder.addWidget(self._plot, 1)

        if not uid_map:
            text = pg.TextItem("暂无账号数据", color=tc["text"])
            self._plot.addItem(text)
            self._plot.hideAxis("left")
            self._plot.hideAxis("bottom")
            return

        all_uids = list(uid_map.keys())
        labels = list(uid_map.values())

        series: dict[str, list[float]] = {}
        has_data = False
        for period_label, since in since_map.items():
            raw = self._history.get_balance_consumption(all_uids, since)
            values = [round(raw.get(uid, 0.0), 2) for uid in all_uids]
            series[period_label] = values
            if any(v > 0 for v in values):
                has_data = True

        colors = {"今日": tc["today"], "本周": tc["week"], "本月": tc["month"]}
        x = list(range(len(labels)))
        width = 0.25
        offsets = {"今日": -width, "本周": 0.0, "本月": width}

        self._plot.addLegend(offset=(10, 10), labelTextSize="9pt")
        for period_label, values in series.items():
            xs = [p + offsets[period_label] for p in x]
            bars = pg.BarGraphItem(
                x0=[xi - width / 2 for xi in xs], x1=[xi + width / 2 for xi in xs],
                y0=[0] * len(xs), y1=values,
                brush=colors[period_label], pen=None,
            )
            self._plot.addItem(bars)
            self._plot.getPlotItem().legend.addItem(bars, period_label)

        ticks = [[(i, lbl) for i, lbl in enumerate(labels)]]
        self._plot.getAxis("bottom").setTicks(ticks)
        self._plot.setLabel("left", "消耗金额", color=tc["text"])
        self._plot.getAxis("left").setTextPen(pg.mkPen(color=tc["text"]))
        self._plot.getAxis("bottom").setTextPen(pg.mkPen(color=tc["text"]))
        self._plot.showGrid(y=True, alpha=0.3)

        if not has_data:
            note = pg.TextItem("暂无消耗记录\n余额未发生变更或无快照数据", color=tc["text"])
            note.setPos(len(labels) / 2, max(1.0, max((max(v) for v in series.values()), default=1.0)))
            self._plot.addItem(note)


def Qt_Window():
    from PySide6.QtCore import Qt
    return Qt.Window
