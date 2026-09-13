from __future__ import annotations

import logging
import select
import socket
import threading

from error_logger import log_exception
from instance_lock import InstanceLock


"""单实例互斥锁 + IPC 唤醒监听（ISSUE-ARC-01，原 App 内联逻辑）。

IPC 约定（AGENTS.md §6.5）：端口硬编码 52847，仅接受 "show" 指令。
"""

logger = logging.getLogger(__name__)


class LifecycleManager:
    """应用生命周期基础设施：互斥锁、单实例唤醒、优雅释放。"""

    def __init__(self, lock_name: str, ipc_port: int):
        self._lock = InstanceLock(lock_name)
        self._ipc_port = ipc_port
        self._listener_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def acquire(self) -> bool:
        """尝试获取单实例互斥锁；False 表示已有实例在运行。"""
        return self._lock.acquire()

    def release(self):
        """释放互斥锁（App._quit 收尾调用）。"""
        self._lock.release()

    def signal_show(self) -> bool:
        """向已运行实例发送 show 唤醒信号（原 _send_show_signal）。"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", self._ipc_port))
            s.sendall(b"show")
            s.close()
            return True
        except Exception as e:
            log_exception("LifecycleManager.signal_show", e)
            return False

    def start_listener(self, on_show) -> None:
        """启动 IPC 监听线程（原 _start_ipc_listener）。

        收到 "show" 后在监听线程回调 on_show；UI 操作由 on_show 自行
        after(0) 调度回主线程。stop_listener() 置位停止事件后线程在
        0.5s 内退出（select 超时粒度，与 ISSUE-PFM-05 低占用设计一致）。
        """
        if self._listener_thread is not None:
            return
        self._stop_event.clear()

        def listen():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", self._ipc_port))
                s.listen(1)
            except OSError as e:
                log_exception("LifecycleManager.listen.bind", e)
                return
            while not self._stop_event.is_set():
                try:
                    readable, _, _ = select.select([s], [], [], 0.5)
                    if not readable:
                        continue
                    conn, _addr = s.accept()
                    data = conn.recv(1024)
                    conn.close()
                    if data == b"show":
                        on_show()
                except Exception as e:
                    log_exception("LifecycleManager.listen", e)
                    continue
            s.close()

        self._listener_thread = threading.Thread(target=listen, daemon=True, name="IPCMonitor")
        self._listener_thread.start()

    def stop_listener(self) -> None:
        """停止 IPC 监听线程（App._quit 调用；原依赖 _exiting 标志轮询）。"""
        self._stop_event.set()
        if self._listener_thread is not None:
            self._listener_thread.join(timeout=2)
            self._listener_thread = None
