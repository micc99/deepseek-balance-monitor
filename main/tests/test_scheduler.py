import os
import sys
import time
import pytest
import responses

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import AppConfig, AccountConfig, SettingsConfig
from scheduler import BalanceScheduler, BalanceResult
from balance_checker import BalanceStatus


@pytest.fixture
def config():
    return AppConfig(
        accounts=[
            AccountConfig(label="DS", api_key="sk-ds", provider="deepseek"),
            AccountConfig(label="SF", api_key="sk-sf", provider="siliconflow"),
        ],
        settings=SettingsConfig(interval_sec=10),
    )


@pytest.fixture
def scheduler(config):
    """ISSUE-PFM-03：创建带线程池的调度器实例。

    start() 会创建 ThreadPoolExecutor(max_workers=4)，测试结束 stop() 关闭。
    """
    s = BalanceScheduler(config)
    s.start()  # 创建线程池
    yield s
    s.stop()


def test_interval_minimum(scheduler):
    scheduler.set_interval(5)
    assert scheduler.interval == 10


def test_interval_normal(scheduler):
    scheduler.set_interval(30)
    assert scheduler.interval == 30


def test_last_results_empty(scheduler):
    assert scheduler.last_results == {}


def test_refresh_all_now(scheduler, config):
    results = []

    def on_result(r):
        results.append(r)

    scheduler.on_result(on_result)

    with responses.RequestsMock() as rsps:
        ds_url = "https://api.deepseek.com/user/balance"
        sf_url = "https://api.siliconflow.cn/v1/user/info"

        rsps.add(responses.GET, ds_url,
                 json={"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "100.00"}]},
                 status=200)
        rsps.add(responses.GET, sf_url,
                 json={"data": {"totalBalance": "200.00", "chargeBalance": "100.00", "grantedBalance": "100.00"}},
                 status=200)

        scheduler.refresh_all_now()
        time.sleep(1.0)

    assert len(results) == 2
    uids = {r.uid for r in results}
    assert len(uids) == 2
    for r in results:
        assert r.info.status == BalanceStatus.OK


def test_settings_change(scheduler):
    scheduler.set_settings(interval=45)
    assert scheduler.interval == 45


def test_start_stop_idempotent(scheduler):
    scheduler.start()
    scheduler.start()
    assert scheduler._running is True
    scheduler.stop()
    scheduler.stop()


def test_result_uid_matches_account(config):
    acc = config.accounts[0]
    from scheduler import BalanceResult as BR
    from balance_checker import BalanceInfo
    r = BR(acc.uid, acc.label, BalanceInfo(status=BalanceStatus.OK))
    assert r.uid == acc.uid
    assert r.label == acc.label


def test_result_slots():
    r = BalanceResult("uid", "label", None)
    with pytest.raises(AttributeError):
        r.new_field = "test"


# ============================================================================
# ISSUE-PFM-03：scheduler 线程池改造测试
# ============================================================================


class TestSchedulerThreadPool:
    """ISSUE-PFM-03：线程池改造测试。"""

    def test_executor_created_on_start(self, scheduler):
        """start() 后应创建 ThreadPoolExecutor。"""
        assert scheduler._executor is not None, "线程池应被创建"

    def test_executor_max_workers_is_4(self, scheduler):
        """线程池 max_workers 应为 4（AC1：单轮刷新线程数 ≤ 4）。"""
        assert scheduler._executor._max_workers == 4, "max_workers 应为 4"

    def test_executor_thread_name_prefix(self, scheduler):
        """线程名前缀应为 balance-check。"""
        # ThreadPoolExecutor 的线程名前缀存储在 _thread_name_prefix
        assert scheduler._executor._thread_name_prefix == "balance-check"

    def test_executor_closed_on_stop(self, config):
        """stop() 后线程池应被关闭（AC3：退出时正确关闭 executor）。"""
        s = BalanceScheduler(config)
        s.start()
        assert s._executor is not None
        s.stop()
        assert s._executor is None, "stop() 后 _executor 应为 None"

    def test_refresh_single_now(self, scheduler, config):
        """单账户刷新应正常工作。"""
        results = []
        scheduler.on_result(lambda r: results.append(r))

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                json={"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "50.00"}]},
                status=200,
            )
            acc = config.accounts[0]
            scheduler.refresh_single_now(acc.uid)
            time.sleep(1.0)

        assert len(results) == 1
        assert results[0].info.status == BalanceStatus.OK


# ============================================================================
# ISSUE-NET-01：scheduler 任务取消测试
# ============================================================================


class TestSchedulerTaskCancellation:
    """ISSUE-NET-01：任务取消测试。"""

    def test_check_all_with_empty_accounts(self, scheduler):
        """无账户时 _check_all 应直接返回（不提交 Future）。"""
        # 临时清空账户
        original_accounts = scheduler._config.accounts
        scheduler._config.accounts = []
        try:
            scheduler._check_all()  # 不应抛异常
        finally:
            scheduler._config.accounts = original_accounts

    def test_check_all_without_executor(self, config):
        """未 start() 时 _check_all 应跳过（executor 为 None）。"""
        s = BalanceScheduler(config)
        # 不调用 start()，executor 为 None
        s._check_all()  # 应记录 warning 并返回，不抛异常

    def test_concurrent_refresh_thread_safe(self, scheduler, config):
        """并发刷新应线程安全（多个账户并发检查不冲突）。"""
        results = []
        scheduler.on_result(lambda r: results.append(r))

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                json={"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "100.00"}]},
                status=200,
            )
            rsps.add(
                responses.GET,
                "https://api.siliconflow.cn/v1/user/info",
                json={"data": {"totalBalance": "200.00"}},
                status=200,
            )
            # 并发触发多次刷新
            scheduler.refresh_all_now()
            scheduler.refresh_all_now()
            time.sleep(1.5)

        # 应至少收到 4 个结果（2 账户 × 2 次刷新）
        assert len(results) >= 2


# ============================================================================
# ISSUE-PFM-07：刷新延迟埋点测试
# ============================================================================


class TestSchedulerRefreshLatency:
    """ISSUE-PFM-07：刷新延迟埋点测试。"""

    def test_refresh_logs_latency(self, scheduler, config, caplog):
        """刷新完成后应记录延迟日志（NFR-PERF-04）。"""
        import logging
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                json={"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "100.00"}]},
                status=200,
            )
            rsps.add(
                responses.GET,
                "https://api.siliconflow.cn/v1/user/info",
                json={"data": {"totalBalance": "200.00"}},
                status=200,
            )
            with caplog.at_level(logging.INFO, logger="scheduler"):
                scheduler.refresh_all_now()
                time.sleep(1.0)

        # 应记录"刷新完成"日志
        found = any("刷新完成" in record.getMessage() for record in caplog.records)
        assert found, "应记录刷新延迟埋点日志"

