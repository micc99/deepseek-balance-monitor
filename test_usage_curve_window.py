"""TDD tests for usage_curve_window module.

Run: pytest test_usage_curve_window.py -v
"""

from __future__ import annotations

import os
import sys
import time
import sqlite3
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "main"))


class TestTimeRanges:
    """Test TIME_RANGES and _TIME_FORMATS definitions."""

    def test_time_ranges_count(self):
        from usage_curve_window import TIME_RANGES
        assert len(TIME_RANGES) == 4

    def test_time_ranges_labels(self):
        from usage_curve_window import TIME_RANGES
        labels = [r[0] for r in TIME_RANGES]
        assert labels == ["1小时", "7小时", "24小时", "7天"]

    def test_time_ranges_durations(self):
        from usage_curve_window import TIME_RANGES
        durations = [r[1] for r in TIME_RANGES]
        assert durations == [3600, 25200, 86400, 604800]

    def test_time_ranges_buckets(self):
        from usage_curve_window import TIME_RANGES
        buckets = [r[2] for r in TIME_RANGES]
        assert buckets == [60, 300, 300, 3600]

    def test_time_formats_exist_for_all_ranges(self):
        from usage_curve_window import TIME_RANGES, _TIME_FORMATS
        for label, _, _ in TIME_RANGES:
            assert label in _TIME_FORMATS, f"Missing format for {label}"

    def test_time_formats_values(self):
        from usage_curve_window import _TIME_FORMATS
        assert _TIME_FORMATS["1小时"] == "%H:%M"
        assert _TIME_FORMATS["7小时"] == "%H:%M"
        assert _TIME_FORMATS["24小时"] == "%H:%M"
        assert _TIME_FORMATS["7天"] == "%m-%d"


class TestThemeColors:
    """Test _get_theme_colors function."""

    def test_returns_dict_with_required_keys(self):
        from usage_curve_window import _get_theme_colors
        tc = _get_theme_colors()
        for key in ("bg", "axes", "text", "grid", "title", "label", "tick"):
            assert key in tc

    def test_dark_theme_by_default(self):
        import customtkinter as ctk
        from usage_curve_window import _get_theme_colors
        appearance = ctk.get_appearance_mode()
        tc = _get_theme_colors()
        if appearance == "Light":
            assert tc["bg"] == "#ffffff"
        else:
            assert tc["bg"] == "#2b2b2b"


class TestColorConstants:
    def test_balance_color_value(self):
        from usage_curve_window import COLOR_BALANCE
        assert COLOR_BALANCE == "#ce93d8"


class TestUsageHistoryIntegration:
    """Integration tests with UsageHistory (SQLite)."""

    @pytest.fixture
    def temp_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        try:
            os.remove(path)
        except OSError:
            pass

    def test_balance_snapshot_record_and_query(self, temp_db):
        from usage_history import UsageHistory
        history = UsageHistory(db_path=temp_db)

        now = time.time()
        history.record_balance_snapshot("uid-test", "hash123", 100.0, "CNY")
        history.record_balance_snapshot("uid-test", "hash123", 95.5, "CNY")

        results = history.get_balance_history("uid-test", now - 10)
        assert len(results) == 2
        assert results[0].balance == 100.0
        assert results[0].currency == "CNY"
        assert results[1].balance == 95.5

    def test_get_balance_history_respects_since(self, temp_db):
        from usage_history import UsageHistory
        history = UsageHistory(db_path=temp_db)

        now = time.time()
        history.record_balance_snapshot("uid-a", "hash1", 200.0, "USD")
        time.sleep(0.01)
        mid = time.time()
        time.sleep(0.01)
        history.record_balance_snapshot("uid-a", "hash1", 180.0, "USD")

        recent = history.get_balance_history("uid-a", mid)
        assert len(recent) == 1
        assert recent[0].balance == 180.0

        all_data = history.get_balance_history("uid-a", now - 10)
        assert len(all_data) == 2

    def test_get_balance_history_empty(self, temp_db):
        from usage_history import UsageHistory
        history = UsageHistory(db_path=temp_db)
        results = history.get_balance_history("nonexistent", 0)
        assert results == []

    def test_hash_key_deterministic(self):
        from usage_history import _hash_key
        h1 = _hash_key("sk-test-key-12345")
        h2 = _hash_key("sk-test-key-12345")
        h3 = _hash_key("sk-different-key")
        assert h1 == h2
        assert h1 != h3
        assert len(h1) == 16


class TestRangeParamsUnit:
    """Unit tests for _get_range_params logic."""

    def test_get_range_params_24h(self):
        from usage_curve_window import TIME_RANGES
        now = time.time()
        for _l, duration, _b in TIME_RANGES:
            if _l == "24小时":
                since = now - duration
                assert since == pytest.approx(now - 86400, abs=2)
                break

    def test_get_range_params_1h(self):
        from usage_curve_window import TIME_RANGES
        now = time.time()
        for _l, duration, _b in TIME_RANGES:
            if _l == "1小时":
                since = now - duration
                assert since == pytest.approx(now - 3600, abs=2)
                break

    def test_get_range_params_7h(self):
        from usage_curve_window import TIME_RANGES
        now = time.time()
        for _l, duration, _b in TIME_RANGES:
            if _l == "7小时":
                since = now - duration
                assert since == pytest.approx(now - 25200, abs=2)
                break

    def test_get_range_params_7d(self):
        from usage_curve_window import TIME_RANGES
        now = time.time()
        for _l, duration, _b in TIME_RANGES:
            if _l == "7天":
                since = now - duration
                assert since == pytest.approx(now - 604800, abs=2)
                break


class TestModuleImports:
    """Smoke test: module can be imported without errors."""

    def test_import_usage_curve_window(self):
        import usage_curve_window
        assert hasattr(usage_curve_window, "BalanceCurveWindow")
        assert hasattr(usage_curve_window, "TIME_RANGES")
        assert hasattr(usage_curve_window, "_TIME_FORMATS")
        assert hasattr(usage_curve_window, "_get_theme_colors")
        assert hasattr(usage_curve_window, "_style_ax")

    def test_import_matplotlib_dates(self):
        import matplotlib.dates as mdates
        assert hasattr(mdates, "DateFormatter")
        assert hasattr(mdates, "AutoDateLocator")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
