from __future__ import annotations

import hashlib
import logging

from balance_checker import BalanceStatus, safe_float
from config import AppConfig
from scheduler import BalanceScheduler, BalanceResult


"""调度器生命周期 + 余额快照记录（ISSUE-ARC-01，原 App 内联逻辑收编）。

SchedulerManager 在后台加载完成后由 App 创建（PFM-02 状态门：
加载完成前 App.scheduler_manager 为 None，一切入口判空）。
"""

logger = logging.getLogger(__name__)


class SchedulerManager:
    """BalanceScheduler 的创建/启停与余额快照持久化。"""

    def __init__(self, config: AppConfig, usage_history):
        self._config = config
        self._usage_history = usage_history
        self.scheduler: BalanceScheduler | None = None

    def start(self, on_result) -> None:
        """创建调度器、注册结果回调并启动轮询线程。"""
        self.scheduler = BalanceScheduler(self._config)
        self.scheduler.on_result(on_result)
        self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler is not None:
            self.scheduler.stop()
            self.scheduler = None

    def refresh_now(self) -> None:
        """立即全量刷新；调度器未就绪时忽略（PFM-02 门）。"""
        if self.scheduler is not None:
            self.scheduler.refresh_all_now()

    def set_settings(self, interval: int, autostart=None) -> None:
        if self.scheduler is not None:
            self.scheduler.set_settings(interval, autostart)
        else:
            # PFM-02：加载未完成时仅暂存到内存配置
            self._config.settings.interval_sec = max(10, interval)

    def record_snapshot(self, result: BalanceResult) -> None:
        """将余额快照写入 SQLite（原 App._record_balance_snapshot）。

        仅记录 OK 且有余额的结果；数值解析用 safe_float（ARC-04）。
        """
        if self._usage_history is None:
            return
        if result.info.status != BalanceStatus.OK or not result.info.balances:
            return
        acc = next((a for a in self._config.accounts if a.uid == result.uid), None)
        if not acc:
            return
        key_hash = hashlib.md5(acc.api_key.encode()).hexdigest()[:16]
        for b in result.info.balances:
            # 与原实现一致：不可解析的值跳过（None 哨兵），可解析则原样记录（含负数）
            val = safe_float(b.total_balance, default=None)
            if val is None:
                continue
            self._usage_history.record_balance_snapshot(
                uid=result.uid,
                api_key_hash=key_hash,
                balance=val,
                currency=b.currency,
            )
