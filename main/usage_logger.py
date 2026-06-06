"""
DeepSeek API Usage Logger
=========================
Drop this module into your application code to log token usage data
from DeepSeek Chat Completion calls into a shared SQLite database.

Usage:
    from usage_logger import log_usage

    response = client.chat.completions.create(...)
    log_usage(api_key, response.usage)  # response.usage is a dict-like object

The logged data is read by DeepSeek Balance Monitor to display
token usage curves (API requests, token consumption, cache hit rate).

Supports any model/provider that returns a usage dict with:
    prompt_tokens, completion_tokens, total_tokens
    [optional] prompt_cache_hit_tokens, prompt_cache_miss_tokens

DB location: %%APPDATA%%/DeepSeekBalanceMonitor/usage.db
"""
import hashlib
import os
import sqlite3
import threading
import time
from typing import Optional

_USAGE_DB_DIR = os.path.join(os.path.expandvars("%APPDATA%"), "DeepSeekBalanceMonitor")
_USAGE_DB_PATH = os.path.join(_USAGE_DB_DIR, "usage.db")

_lock = threading.Lock()


def _ensure_db_path():
    os.makedirs(_USAGE_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_USAGE_DB_PATH)
    _init_db(conn)
    conn.close()


def _hash_key(api_key: str) -> str:
    return hashlib.md5(api_key.encode()).hexdigest()[:16]


def _get_conn() -> sqlite3.Connection:
    _ensure_db_path()
    conn = sqlite3.connect(_USAGE_DB_PATH)
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key_hash TEXT    NOT NULL,
            timestamp    REAL    NOT NULL,
            prompt_tokens      INTEGER DEFAULT 0,
            completion_tokens  INTEGER DEFAULT 0,
            total_tokens       INTEGER DEFAULT 0,
            cache_hit_tokens   INTEGER DEFAULT 0,
            cache_miss_tokens  INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_token_usage_hash_time
        ON token_usage(api_key_hash, timestamp)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS balance_snapshots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            uid          TEXT    NOT NULL,
            api_key_hash TEXT    NOT NULL,
            timestamp    REAL    NOT NULL,
            balance      REAL    NOT NULL,
            currency     TEXT    NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_balance_uid_time
        ON balance_snapshots(uid, timestamp)
    """)
    conn.commit()


def log_usage(api_key: str, usage: dict):
    """Log a single API call's usage data into the shared database.

    Args:
        api_key: The DeepSeek API key used for this request.
        usage:   The usage dict from the API response.
                 Expected keys: prompt_tokens, completion_tokens, total_tokens,
                                prompt_cache_hit_tokens, prompt_cache_miss_tokens (optional).
    """
    if usage is None or not isinstance(usage, dict):
        return
    key_hash = _hash_key(api_key)
    now = time.time()
    with _lock:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO token_usage
               (api_key_hash, timestamp, prompt_tokens, completion_tokens,
                total_tokens, cache_hit_tokens, cache_miss_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                key_hash,
                now,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
                usage.get("prompt_cache_hit_tokens", 0),
                usage.get("prompt_cache_miss_tokens", 0),
            ),
        )
        conn.commit()


def prune_old_data(retention_days: int = 30):
    """Delete records older than `retention_days`."""
    cutoff = time.time() - retention_days * 86400
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM token_usage WHERE timestamp < ?", (cutoff,))
        conn.execute("DELETE FROM balance_snapshots WHERE timestamp < ?", (cutoff,))
        conn.commit()
