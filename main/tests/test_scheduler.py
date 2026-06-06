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
    s = BalanceScheduler(config)
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
        time.sleep(0.5)

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
