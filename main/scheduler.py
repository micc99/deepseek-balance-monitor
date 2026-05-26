import threading
import time
from typing import Callable

from balance_checker import BalanceInfo, BalanceStatus, get_provider
from config import AppConfig, AccountConfig


class BalanceResult:
    __slots__ = ("uid", "label", "info", "timestamp")

    def __init__(self, uid: str, label: str, info: BalanceInfo):
        self.uid = uid
        self.label = label
        self.info = info
        self.timestamp = time.time()


class BalanceScheduler:
    def __init__(self, config: AppConfig):
        self._config = config
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[BalanceResult], None]] = []
        self._last_results: dict[str, BalanceResult] = {}
        self._wake_event = threading.Event()

    @property
    def interval(self) -> int:
        return max(10, self._config.settings.interval_sec)

    @property
    def last_results(self) -> dict[str, BalanceResult]:
        with self._lock:
            return dict(self._last_results)

    def on_result(self, callback: Callable[[BalanceResult], None]):
        self._callbacks.append(callback)

    def start(self):
        if self._running:
            return
        self._running = True
        self._wake_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        self._wake_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def refresh_all_now(self):
        t = threading.Thread(target=self._check_all, daemon=True)
        t.start()

    def refresh_single_now(self, uid: str):
        t = threading.Thread(target=self._check_single, args=(uid,), daemon=True)
        t.start()

    def set_interval(self, sec: int):
        self._config.settings.interval_sec = max(10, sec)
        self._wake_event.set()

    def set_settings(self, interval: int, autostart: bool = None):
        self._config.settings.interval_sec = max(10, interval)
        if autostart is not None:
            self._config.settings.autostart = autostart
        self._wake_event.set()

    def _run(self):
        while self._running:
            self._check_all()
            self._wake_event.wait(self.interval)
            self._wake_event.clear()

    def _check_all(self):
        with self._lock:
            accounts = list(self._config.accounts)
        threads = []
        for acc in accounts:
            t = threading.Thread(target=self._do_check, args=(acc,), daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join(timeout=15)

    def _check_single(self, uid: str):
        with self._lock:
            acc = next((a for a in self._config.accounts if a.uid == uid), None)
        if acc:
            self._do_check(acc)

    def _do_check(self, acc: AccountConfig):
        provider = get_provider(acc.provider)
        info = provider.check_balance(acc.api_key)
        result = BalanceResult(acc.uid, acc.label, info)
        with self._lock:
            self._last_results[acc.uid] = result
        for cb in self._callbacks:
            try:
                cb(result)
            except Exception:
                pass
