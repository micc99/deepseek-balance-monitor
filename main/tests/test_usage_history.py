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
