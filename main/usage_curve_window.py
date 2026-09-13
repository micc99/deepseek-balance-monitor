from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from usage_history import UsageHistory, _hash_key
from qss import current_layer


"""单账户余额趋势图（Qt + pyqtgraph 版，ISSUE-MIG-07）。

双击账户行的余额列打开。数据源为 balance_snapshots 表。
ISSUE-PFM-01 延迟加载模式保留：模块顶部不 import pyqtgraph，
首次打开窗口时 _ensure_pyqtgraph() 执行加载（D1 决策：matplotlib → pyqtgraph，
import ~50ms 且 Qt 原生）。配色直读主题 token（THM-05 AC3）。

行为差异说明：ctk 版的渐进绘制动画与 grab_set 模态不迁移
（D6 动画收敛；Qt 版为非模态窗口），hover 提示保留。
"""

COLOR_BALANCE_KEY = "primary"

TIME_RANGES = [
    ("1小时", 3600),
    ("7小时", 25200),
    ("24小时", 86400),
    ("7天", 604800),
]

_pg_cache: dict = {}


def _ensure_pyqtgraph() -> dict:
    """延迟加载 pyqtgraph 并缓存（ISSUE-PFM-01 模式延续）。"""
    if _pg_cache:
        return _pg_cache
    import pyqtgraph as pg
    pg.setConfigOptions(antialias=True, background=None, foreground=None)
    _pg_cache["pg"] = pg
    return _pg_cache


def _theme_colors() -> dict:
    """从当前主题层取图表配色（qss.current_layer 由 build_qss 维护）。"""
    layer = current_layer()
    if layer is not None:
        return dict(bg=layer.background, axes=layer.surface, text=layer.text,
                    grid=layer.border, primary=layer.primary)
    return dict(bg="#2b2b2b", axes="#333333", text="#cccccc",
                grid="#444444", primary="#7ba9c4")


class BalanceCurveWindow(QWidget):
    """单账户余额趋势折线图，支持时间范围切换与 hover 取值。"""

    def __init__(self, parent, account_label: str, api_key: str, uid: str, history: UsageHistory):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle(f"余额趋势 — {account_label}")
        self.resize(750, 520)
        self.setMinimumSize(550, 400)

        self._api_key_hash = _hash_key(api_key)
        self._uid = uid
        self._history = history
        self._account_label = account_label
        self._hover_text = None

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        toolbar = QHBoxLayout()
        title = QLabel(f"账号: {account_label}", objectName="title")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        self._range_combo = QComboBox()
        for label, _sec in TIME_RANGES:
            self._range_combo.addItem(label)
        self._range_combo.setCurrentText("24小时")
        self._range_combo.currentTextChanged.connect(lambda _t: self._render())
        self._range_combo.setFixedWidth(100)
        toolbar.addWidget(self._range_combo)
        self._balance_label = QLabel("")
        self._balance_label.setStyleSheet("font-weight: bold;")
        toolbar.addWidget(self._balance_label)
        root.addLayout(toolbar)

        self._plot_holder = QVBoxLayout()
        root.addLayout(self._plot_holder, 1)

        QTimer_start(self, 50, self._render)  # 让窗口先渲染，再绘图

    def _render(self):
        pg = _ensure_pyqtgraph()["pg"]
        tc = _theme_colors()

        if hasattr(self, "_plot") and self._plot is not None:
            self._plot.setParent(None)
            self._plot = None

        since, range_label = self._get_range_params()
        balance_history = self._history.get_balance_history(self._uid, since)

        axis = pg.DateAxisItem(orientation="bottom")
        self._plot = pg.PlotWidget(axisItems={"bottom": axis})
        self._plot.setBackground(tc["bg"])
        self._plot_holder.addWidget(self._plot, 1)

        if not balance_history:
            self._balance_label.setText("")
            text = pg.TextItem("暂无余额变更记录", color=tc["text"])
            self._plot.addItem(text)
            self._plot.hideAxis("left")
            self._plot.hideAxis("bottom")
            return

        times = [b.timestamp for b in balance_history]
        values = [b.balance for b in balance_history]
        currency = balance_history[0].currency
        symbol = "¥" if currency == "CNY" else "$"

        self._balance_label.setText(f"当前余额: {symbol}{values[-1]:,.4f}")

        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setTitle("余额趋势", color=tc["text"], size="12pt")
        self._plot.setLabel("left", f"余额 ({symbol})", color=tc["text"])
        self._plot.setLabel("bottom", "时间", color=tc["text"])
        for key in ("left", "bottom"):
            self._plot.getAxis(key).setPen(pg.mkPen(color=tc["grid"]))
            self._plot.getAxis(key).setTextPen(pg.mkPen(color=tc["text"]))

        line_color = tc["primary"]
        self._plot.plot(
            times, values,
            pen=pg.mkPen(color=line_color, width=2),
            symbol="o", symbolSize=4,
            symbolBrush=pg.mkBrush(color=line_color),
        )
        fill = pg.FillBetweenItem(
            pg.PlotDataItem(times, values),
            pg.PlotDataItem(times, [0] * len(values)),
            brush=pg.mkBrush(color=line_color, alpha=40),
        )
        self._plot.addItem(fill)

        # hover 取值：点击/悬停最近数据点显示时间与余额
        self._hover_text = pg.TextItem(color=tc["text"], anchor=(0, 1))
        self._hover_text.setBg(30)
        self._plot.addItem(self._hover_text)
        self._data = list(zip(times, values))
        self._symbol = symbol
        self._scene = self._plot.scene()
        self._scene.sigMouseMoved.connect(self._on_mouse_moved)

    def _on_mouse_moved(self, pos):
        if not self._data or self._hover_text is None:
            return
        vb = self._plot.getViewBox()
        mouse_point = vb.mapSceneToView(pos)
        mx = mouse_point.x()
        nearest = min(self._data, key=lambda p: abs(p[0] - mx))
        if abs(nearest[0] - mx) > max(600.0, (self._data[-1][0] - self._data[0][0]) * 0.02):
            self._hover_text.setText("")
            return
        t, v = nearest
        self._hover_text.setPos(t, v)
        self._hover_text.setText(
            f"{datetime.fromtimestamp(t):%Y-%m-%d %H:%M:%S}\n{self._symbol}{v:,.4f}"
        )

    def _get_range_params(self):
        now = time.time()
        range_label = self._range_combo.currentText()
        for _l, duration in TIME_RANGES:
            if _l == range_label:
                return now - duration, range_label
        return now - 86400, "24小时"


def QTimer_start(widget, ms, fn):
    from PySide6.QtCore import QTimer
    QTimer.singleShot(ms, fn)
