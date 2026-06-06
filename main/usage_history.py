import hashlib
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Optional

_USAGE_DB_DIR = os.path.join(os.path.expandvars("%APPDATA%"), "DeepSeekBalanceMonitor")
_USAGE_DB_PATH = os.path.join(_USAGE_DB_DIR, "usage.db")


@dataclass
class TokenUsageRecord:
    timestamp: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cache_hit_tokens: int
    cache_miss_tokens: int


@dataclass
class BalanceSnapshotRecord:
    timestamp: float
    balance: float
    currency: str


@dataclass
class AggregatedUsage:
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cache_hit: int = 0
    total_cache_miss: int = 0

    @property
    def cache_hit_rate(self) -> Optional[float]:
        total = self.total_cache_hit + self.total_cache_miss
        if total == 0:
            return None
        return self.total_cache_hit / total


def _hash_key(api_key: str) -> str:
    return hashlib.md5(api_key.encode()).hexdigest()[:16]


class UsageHistory:
    def __init__(self, db_path: str = _USAGE_DB_PATH):
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
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

    def record_balance_snapshot(self, uid: str, api_key_hash: str, balance: float, currency: str):
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO balance_snapshots (uid, api_key_hash, timestamp, balance, currency) VALUES (?, ?, ?, ?, ?)",
                (uid, api_key_hash, time.time(), balance, currency),
            )
            conn.commit()

    def get_token_usage(self, api_key_hash: str, since: float) -> list[TokenUsageRecord]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, prompt_tokens, completion_tokens, total_tokens, cache_hit_tokens, cache_miss_tokens "
                "FROM token_usage WHERE api_key_hash = ? AND timestamp >= ? "
                "ORDER BY timestamp ASC",
                (api_key_hash, since),
            ).fetchall()
        return [
            TokenUsageRecord(
                timestamp=r["timestamp"],
                prompt_tokens=r["prompt_tokens"],
                completion_tokens=r["completion_tokens"],
                total_tokens=r["total_tokens"],
                cache_hit_tokens=r["cache_hit_tokens"],
                cache_miss_tokens=r["cache_miss_tokens"],
            )
            for r in rows
        ]

    def get_balance_history(self, uid: str, since: float) -> list[BalanceSnapshotRecord]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT timestamp, balance, currency FROM balance_snapshots "
                "WHERE uid = ? AND timestamp >= ? ORDER BY timestamp ASC",
                (uid, since),
            ).fetchall()
        return [
            BalanceSnapshotRecord(timestamp=r["timestamp"], balance=r["balance"], currency=r["currency"])
            for r in rows
        ]

    def get_aggregated_usage(self, api_key_hash: str, since: float) -> AggregatedUsage:
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT
                    COUNT(*) as total_requests,
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cache_hit_tokens), 0) as total_cache_hit,
                    COALESCE(SUM(cache_miss_tokens), 0) as total_cache_miss
                   FROM token_usage
                   WHERE api_key_hash = ? AND timestamp >= ?""",
                (api_key_hash, since),
            ).fetchone()
        return AggregatedUsage(
            total_requests=row["total_requests"],
            total_prompt_tokens=row["total_prompt_tokens"],
            total_completion_tokens=row["total_completion_tokens"],
            total_tokens=row["total_tokens"],
            total_cache_hit=row["total_cache_hit"],
            total_cache_miss=row["total_cache_miss"],
        )

    def get_total_usage_all_keys(self, since: float) -> AggregatedUsage:
        with self._get_conn() as conn:
            row = conn.execute(
                """SELECT
                    COUNT(*) as total_requests,
                    COALESCE(SUM(prompt_tokens), 0) as total_prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) as total_completion_tokens,
                    COALESCE(SUM(total_tokens), 0) as total_tokens,
                    COALESCE(SUM(cache_hit_tokens), 0) as total_cache_hit,
                    COALESCE(SUM(cache_miss_tokens), 0) as total_cache_miss
                   FROM token_usage
                   WHERE timestamp >= ?""",
                (since,),
            ).fetchone()
        return AggregatedUsage(
            total_requests=row["total_requests"],
            total_prompt_tokens=row["total_prompt_tokens"],
            total_completion_tokens=row["total_completion_tokens"],
            total_tokens=row["total_tokens"],
            total_cache_hit=row["total_cache_hit"],
            total_cache_miss=row["total_cache_miss"],
        )

    def prune(self, retention_days: int = 30):
        cutoff = time.time() - retention_days * 86400
        with self._get_conn() as conn:
            conn.execute("DELETE FROM token_usage WHERE timestamp < ?", (cutoff,))
            conn.execute("DELETE FROM balance_snapshots WHERE timestamp < ?", (cutoff,))
            conn.commit()

    def get_bucketed_usage(self, api_key_hash: str, since: float, bucket_sec: int) -> list[dict]:
        """Aggregate token_usage into time buckets.

        Args:
            api_key_hash: The hashed API key.
            since:        Unix timestamp (inclusive start).
            bucket_sec:   Bucket width in seconds (e.g. 60 = 1min buckets).

        Returns list of dicts with keys:
            bucket_start, requests, prompt_tokens, completion_tokens,
            total_tokens, cache_hit_tokens, cache_miss_tokens
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT
                    CAST((timestamp - ?) / ? AS INTEGER) AS bucket,
                    COUNT(*)                              AS requests,
                    COALESCE(SUM(prompt_tokens), 0)       AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0)   AS completion_tokens,
                    COALESCE(SUM(total_tokens), 0)        AS total_tokens,
                    COALESCE(SUM(cache_hit_tokens), 0)    AS cache_hit_tokens,
                    COALESCE(SUM(cache_miss_tokens), 0)   AS cache_miss_tokens
                   FROM token_usage
                   WHERE api_key_hash = ? AND timestamp >= ?
                   GROUP BY bucket
                   ORDER BY bucket ASC""",
                (since, bucket_sec, api_key_hash, since),
            ).fetchall()
        return [
            {
                "bucket_start": since + r["bucket"] * bucket_sec,
                "requests": r["requests"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "total_tokens": r["total_tokens"],
                "cache_hit_tokens": r["cache_hit_tokens"],
                "cache_miss_tokens": r["cache_miss_tokens"],
            }
            for r in rows
        ]

    def get_account_usage_summary(self, api_key_hashes: list[str], since: float) -> dict[str, int]:
        if not api_key_hashes:
            return {}
        placeholders = ",".join("?" * len(api_key_hashes))
        with self._get_conn() as conn:
            rows = conn.execute(
                f"""SELECT api_key_hash, COALESCE(SUM(total_tokens), 0) as tokens
                    FROM token_usage
                    WHERE api_key_hash IN ({placeholders}) AND timestamp >= ?
                    GROUP BY api_key_hash""",
                (*api_key_hashes, since),
            ).fetchall()
        result: dict[str, int] = {}
        for r in rows:
            result[r["api_key_hash"]] = r["tokens"]
        return result
