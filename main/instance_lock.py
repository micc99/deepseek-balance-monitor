import ctypes
import ctypes.wintypes
import sys

ERROR_ALREADY_EXISTS = 183


class InstanceLock:
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
