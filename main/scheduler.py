import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Callable

from balance_checker import BalanceInfo, BalanceStatus, get_provider
from config import AppConfig, AccountConfig


"""后台余额轮询调度器。

独立线程按配置间隔逐一检查所有账户余额，
结果通过回调推送给 UI 层，同时缓存在 _last_results 供悬浮窗读取。

ISSUE-PFM-03：使用 ThreadPoolExecutor(max_workers=4) 替代每账户新建 Thread，
避免账户数多时线程爆炸，复用线程降低创建开销。
"""

logger = logging.getLogger(__name__)

# ISSUE-PFM-03：线程池并发上限，避免账户多时线程爆炸
_MAX_WORKERS = 4
# ISSUE-NET-01：单账户刷新超时阈值（秒），超时后取消未启动的 Future
_CHECK_TIMEOUT = 15


class BalanceResult:
    """单次余额查询的打包结果，用 __slots__ 减少内存开销。"""
    __slots__ = ("uid", "label", "info", "timestamp")

    def __init__(self, uid: str, label: str, info: BalanceInfo):
        self.uid = uid
        self.label = label
        self.info = info
        self.timestamp = time.time()


class BalanceScheduler:
    """余额轮询引擎。管理后台线程，支持手动刷新、间隔调整、回调注册。

    ISSUE-PFM-03：内部使用 ThreadPoolExecutor 限制并发线程数（max_workers=4），
    避免账户多时每账户新建 Thread 导致线程爆炸。
    """

    def __init__(self, config: AppConfig):
        self._config = config
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._callbacks: list[Callable[[BalanceResult], None]] = []
        self._last_results: dict[str, BalanceResult] = {}
        self._wake_event = threading.Event()
        # ISSUE-PFM-03：线程池替代每账户新建 Thread
        self._executor: ThreadPoolExecutor | None = None

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
        # ISSUE-PFM-03：创建线程池，max_workers=4 限制并发
        self._executor = ThreadPoolExecutor(
            max_workers=_MAX_WORKERS,
            thread_name_prefix="balance-check",
        )
        self._thread = threading.Thread(target=self._run, daemon=True, name="BalanceScheduler")
        self._thread.start()

    def stop(self):
        self._running = False
        self._wake_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        # ISSUE-PFM-03：关闭线程池，等待已提交任务完成
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None

    def refresh_all_now(self):
        t = threading.Thread(target=self._check_all, daemon=True, name="BalanceRefresh")
        t.start()

    def refresh_single_now(self, uid: str):
        t = threading.Thread(target=self._check_single, args=(uid,), daemon=True, name="BalanceRefreshSingle")
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
        # 首次等待 interval 再刷新（App 启动后通过 refresh_all_now 显式触发首次刷新）
        # 避免后台线程立即刷新干扰测试与启动流程
        self._wake_event.wait(self.interval)
        self._wake_event.clear()
        while self._running:
            self._check_all()
            self._wake_event.wait(self.interval)
            self._wake_event.clear()

    def _check_all(self):
        """ISSUE-PFM-03 / ISSUE-NET-01：并发检查所有账户，使用线程池 + Future。

        - 提交所有账户到 ThreadPoolExecutor（max_workers=4 限制并发）
        - 使用 as_completed 收集结果，超时 15s 后取消未启动的 Future
        - 超时的账户记录 WARN 日志（账户 UID + 超时秒数）
        - 单账户超时不影响其他账户

        ISSUE-PFM-07：埋点统计刷新延迟（NFR-PERF-04：10 账户 < 5s）
        """
        with self._lock:
            accounts = list(self._config.accounts)
        if not accounts:
            return

        # ISSUE-PFM-02：加载未完成或已停止时，executor 可能为 None
        if self._executor is None:
            logger.warning("调度器线程池未初始化，跳过本轮检查")
            return

        # ISSUE-PFM-07：刷新延迟埋点
        refresh_start = time.time()
        account_count = len(accounts)

        # 提交所有账户到线程池
        future_to_acc: dict[Future, AccountConfig] = {}
        for acc in accounts:
            future = self._executor.submit(self._do_check, acc)
            future_to_acc[future] = acc

        # ISSUE-NET-01：as_completed 收集结果，超时取消未启动的 Future
        try:
            for future in as_completed(future_to_acc.keys(), timeout=_CHECK_TIMEOUT):
                acc = future_to_acc[future]
                try:
                    future.result()
                except Exception as e:
                    logger.exception("scheduler._check_all future error (uid=%s): %s", acc.uid, e)
        except TimeoutError:
            # 超时：取消未启动的 Future，记录 WARN 日志
            pending = [f for f in future_to_acc if not f.done()]
            for f in pending:
                acc = future_to_acc[f]
                if f.cancel():
                    logger.warning(
                        "账户刷新超时已取消（uid=%s, label=%s, 超时=%ds）",
                        acc.uid, acc.label, _CHECK_TIMEOUT,
                    )
                else:
                    # 运行中的 Future 无法取消，依赖 requests 的 timeout 参数
                    logger.warning(
                        "账户刷新超时但任务运行中无法取消（uid=%s, label=%s, 超时=%ds）",
                        acc.uid, acc.label, _CHECK_TIMEOUT,
                    )

        # ISSUE-PFM-07：记录刷新延迟（NFR-PERF-04：10 账户 < 5s）
        refresh_elapsed = time.time() - refresh_start
        logger.info(
            "刷新完成: %d 账户, 耗时=%.2fs (目标 < 5s)",
            account_count, refresh_elapsed,
        )

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
            except Exception as e:
                logger.exception("scheduler._do_check.callback: %s", e)
