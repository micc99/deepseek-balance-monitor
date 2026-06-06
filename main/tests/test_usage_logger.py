import os
import sys
import sqlite3
import tempfile
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import usage_logger


@pytest.fixture(autouse=True)
def isolate_db():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "usage.db")
    usage_logger._USAGE_DB_DIR = tmpdir
    usage_logger._USAGE_DB_PATH = db_path
    usage_logger._ensure_db_path()
    yield
    usage_logger._USAGE_DB_DIR = os.path.join(os.path.expandvars("%APPDATA%"), "DeepSeekBalanceMonitor")
    usage_logger._USAGE_DB_PATH = os.path.join(usage_logger._USAGE_DB_DIR, "usage.db")


def test_log_usage_inserts_record():
    usage_logger.log_usage("sk-test", {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
    })
    conn = sqlite3.connect(usage_logger._USAGE_DB_PATH)
    rows = conn.execute("SELECT * FROM token_usage").fetchall()
    assert len(rows) == 1
    assert rows[0][3] == 100  # prompt_tokens
    assert rows[0][4] == 50   # completion_tokens
    assert rows[0][5] == 150  # total_tokens


def test_log_usage_ignores_none():
    usage_logger.log_usage("sk-test", None)
    conn = sqlite3.connect(usage_logger._USAGE_DB_PATH)
    rows = conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()
    assert rows[0] == 0


def test_log_usage_ignores_empty_dict():
    usage_logger.log_usage("sk-test", {})
    conn = sqlite3.connect(usage_logger._USAGE_DB_PATH)
    rows = conn.execute("SELECT * FROM token_usage").fetchall()
    assert len(rows) == 1
    assert rows[0][3] == 0
    assert rows[0][5] == 0


def test_hash_key_deterministic():
    h1 = usage_logger._hash_key("sk-test")
    h2 = usage_logger._hash_key("sk-test")
    assert h1 == h2
    assert len(h1) == 16


def test_hash_key_different_for_different_keys():
    h1 = usage_logger._hash_key("sk-aaa")
    h2 = usage_logger._hash_key("sk-bbb")
    assert h1 != h2


def test_prune_old_data():
    usage_logger.log_usage("sk-test", {"total_tokens": 10})
    conn = sqlite3.connect(usage_logger._USAGE_DB_PATH)
    conn.execute("UPDATE token_usage SET timestamp = ?", (time.time() - 60 * 86400,))
    conn.commit()

    usage_logger.prune_old_data(retention_days=30)
    rows = conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()
    assert rows[0] == 0  # Old record pruned


def test_log_usage_with_cache_tokens():
    usage_logger.log_usage("sk-test", {
        "prompt_tokens": 200,
        "completion_tokens": 100,
        "total_tokens": 300,
        "prompt_cache_hit_tokens": 50,
        "prompt_cache_miss_tokens": 25,
    })
    conn = sqlite3.connect(usage_logger._USAGE_DB_PATH)
    rows = conn.execute("SELECT * FROM token_usage").fetchall()
    assert len(rows) == 1
    assert rows[0][6] == 50   # cache_hit_tokens
    assert rows[0][7] == 25   # cache_miss_tokens
