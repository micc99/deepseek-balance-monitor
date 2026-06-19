import sys

"""Windows 单实例互斥锁。

通过 Win32 CreateMutexW 创建全局命名互斥量，
第二个进程启动时检测到已存在则发送 IPC 信号并退出。
非 Windows 平台直接放行。
"""

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

ERROR_ALREADY_EXISTS = 183


class InstanceLock:
    """系统级单实例锁，支持上下文管理器。"""
    _mutex = None
    _acquired = False

    def __init__(self, name: str):
        self._name = name

    def acquire(self) -> bool:
        if sys.platform != "win32":
            self._acquired = True
            return True

        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, f"Global\\{self._name}")
        self._mutex = mutex

        if ctypes.GetLastError() == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(mutex)
            self._mutex = None
            self._acquired = False
            return False

        self._acquired = True
        return True

    def release(self):
        if self._mutex and self._acquired:
            ctypes.windll.kernel32.CloseHandle(self._mutex)
            self._mutex = None
            self._acquired = False

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

    def __del__(self):
        self.release()
