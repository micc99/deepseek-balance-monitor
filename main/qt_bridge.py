from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


"""跨线程调用桥：tkinter after(0, fn) 的 Qt 等价物（ISSUE-MIG-02）。

线程模型（AGENTS.md §6.1 → Qt 版）：后台线程（scheduler/IPC/托盘）
不得直接触碰 UI，统一经 CallDispatcher.emit(fn) 投递到主线程执行。
Qt 跨线程信号自动以 QueuedConnection 排队，天然线程安全。

用法：
    bridge = CallDispatcher()          # 必须在主线程创建
    bridge.call.emit(fn)               # 任意线程：fn 在主线程执行
"""


class CallDispatcher(QObject):
    """携带可调用对象投递到主线程的单信号桥。"""

    call = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        # 同线程直连、跨线程自动 QueuedConnection
        self.call.connect(self._execute)

    @Slot(object)
    def _execute(self, fn) -> None:
        fn()
