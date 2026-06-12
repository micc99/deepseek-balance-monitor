import os
import sys
import tempfile
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usage_history import UsageHistory, _hash_key, AggregatedUsage


@pytest.fixture
def history():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "usage.db")
    h = UsageHistory(db_path=db_path)
    yield h


def test_record_and_get_balance_history(history):
    now = time.time()
    history.record_balance_snapshot("uid1", _hash_key("sk-a"), 100.0, "CNY")
    history.record_balance_snapshot("uid1", _hash_key("sk-a"), 150.0, "CNY")

    records = history.get_balance_history("uid1", now - 10)
    assert len(records) == 2
    assert records[0].balance == 100.0
    assert records[1].balance == 150.0
    assert records[0].currency == "CNY"


def test_get_balance_history_empty(history):
    records = history.get_balance_history("nonexistent", time.time() - 86400)
    assert records == []


def test_get_token_usage_empty(history):
    records = history.get_token_usage(_hash_key("sk-xxx"), time.time() - 86400)
    assert records == []


def test_get_aggregated_usage_empty(history):
    result = history.get_aggregated_usage(_hash_key("sk-xxx"), time.time() - 86400)
    assert result.total_requests == 0
    assert result.total_tokens == 0
    assert result.cache_hit_rate is None


def test_get_total_usage_all_keys_empty(history):
    result = history.get_total_usage_all_keys(time.time() - 86400)
    assert result.total_requests == 0


def test_get_bucketed_usage_empty(history):
    result = history.get_bucketed_usage(_hash_key("sk-xxx"), time.time() - 86400, 3600)
    assert result == []


def test_hash_key():
    h = _hash_key("sk-test")
    assert len(h) == 16
    assert _hash_key("sk-test") == h


def test_aggregated_usage_cache_rate():
    ag = AggregatedUsage(total_cache_hit=70, total_cache_miss=30)
    rate = ag.cache_hit_rate
    assert rate is not None
    assert 0.69 < rate < 0.71


def test_aggregated_usage_cache_rate_zero():
    ag = AggregatedUsage()
    assert ag.cache_hit_rate is None


def test_get_account_usage_summary_label_map(history):
    now = time.time()
    conn = history._get_conn()
    conn.execute(
        "INSERT INTO token_usage (api_key_hash, timestamp, total_tokens) VALUES (?, ?, ?)",
        (_hash_key("sk-a"), now, 500),
    )
    conn.execute(
        "INSERT INTO token_usage (api_key_hash, timestamp, total_tokens) VALUES (?, ?, ?)",
        (_hash_key("sk-b"), now, 300),
    )
    conn.commit()
    conn.close()

    label_map = {"Account A": _hash_key("sk-a"), "Account B": _hash_key("sk-b")}
    result = history.get_account_usage_summary(
        [_hash_key("sk-a"), _hash_key("sk-b")], now - 10, label_map=label_map
    )

    assert result["Account A"] == 500
    assert result["Account B"] == 300


def test_get_latest_balance_per_account(history):
    now = time.time()
    history.record_balance_snapshot("uid1", _hash_key("sk-a"), 100.0, "CNY")
    history.record_balance_snapshot("uid1", _hash_key("sk-a"), 80.0, "CNY")
    history.record_balance_snapshot("uid2", _hash_key("sk-b"), 50.0, "USD")

    result = history.get_latest_balance_per_account(
        ["uid1", "uid2"], now - 10
    )
    assert result["uid1"] == 80.0
    assert result["uid2"] == 50.0


def test_get_latest_balance_per_account_empty(history):
    result = history.get_latest_balance_per_account(["uid1"], time.time() - 10)
    assert result == {}


def test_get_balance_consumption(history):
    now = time.time()
    history.record_balance_snapshot("uid1", "h1", 100.0, "CNY")
    history.record_balance_snapshot("uid1", "h1", 80.0, "CNY")
    history.record_balance_snapshot("uid2", "h2", 50.0, "USD")
    history.record_balance_snapshot("uid2", "h2", 30.0, "USD")

    result = history.get_balance_consumption(["uid1", "uid2"], now - 10)
    assert result["uid1"] == 20.0
    assert result["uid2"] == 20.0


def test_get_balance_consumption_with_topup(history):
    now = time.time()
    history.record_balance_snapshot("uid1", "h1", 50.0, "CNY")
    history.record_balance_snapshot("uid1", "h1", 200.0, "CNY")

    result = history.get_balance_consumption(["uid1"], now - 10)
    assert result["uid1"] == 0.0


def test_get_balance_consumption_empty(history):
    result = history.get_balance_consumption(["uid1"], time.time() - 10)
    assert result == {}
