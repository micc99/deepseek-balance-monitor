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


class TestAnimationConfig:
    """Test the brush-draw animation configuration constants."""

    def test_animation_duration_is_1_second(self):
        from usage_curve_window import BalanceCurveWindow
        assert BalanceCurveWindow._anim_duration_ms == 1000

    def test_animation_frame_delay_is_about_60fps(self):
        from usage_curve_window import BalanceCurveWindow
        assert BalanceCurveWindow._anim_frame_delay_ms == 16

    def test_animation_total_frames_calculation(self):
        from usage_curve_window import BalanceCurveWindow
        expected = BalanceCurveWindow._anim_duration_ms // BalanceCurveWindow._anim_frame_delay_ms
        assert expected == 62
        assert expected * 16 == 992  # ~1000ms total

    def test_animation_state_attributes_exist(self):
        from usage_curve_window import BalanceCurveWindow
        assert hasattr(BalanceCurveWindow, "_animating")
        assert hasattr(BalanceCurveWindow, "_anim_timer")
        assert hasattr(BalanceCurveWindow, "_anim_x_min")
        assert hasattr(BalanceCurveWindow, "_anim_x_max")
        assert hasattr(BalanceCurveWindow, "_anim_total_frames")
        assert hasattr(BalanceCurveWindow, "_animate_draw")
        assert hasattr(BalanceCurveWindow, "_animate_frame")
        assert hasattr(BalanceCurveWindow, "_cancel_animation")


class TestAnimationEasing:
    """Test the easing function used for smooth brush animation."""

    def test_easing_at_zero(self):
        progress = 0.0
        eased = 1.0 - (1.0 - progress) ** 2
        assert eased == pytest.approx(0.0)

    def test_easing_at_one(self):
        progress = 1.0
        eased = 1.0 - (1.0 - progress) ** 2
        assert eased == pytest.approx(1.0)

    def test_easing_at_half(self):
        progress = 0.5
        eased = 1.0 - (1.0 - progress) ** 2
        assert eased == pytest.approx(0.75)

    def test_easing_is_monotonic(self):
        prev = 0.0
        for i in range(0, 101):
            progress = i / 100
            eased = 1.0 - (1.0 - progress) ** 2
            assert eased >= prev - 1e-9
            prev = eased

    def test_easing_is_convex(self):
        """Easing-out should be convex (faster at start, slower at end)."""
        mid_progress = 0.5
        mid_eased = 1.0 - (1.0 - mid_progress) ** 2
        assert mid_eased > mid_progress


class TestAnimationProgressToXlim:
    """Test the mapping from animation progress to xlim values."""

    def test_xlim_collapses_to_single_point_at_start(self):
        x_min, x_max = 100.0, 200.0
        progress = 0.0
        eased = 1.0 - (1.0 - progress) ** 2
        current_x_max = x_min + (x_max - x_min) * eased
        assert current_x_max == pytest.approx(x_min)

    def test_xlim_reaches_full_at_end(self):
        x_min, x_max = 100.0, 200.0
        progress = 1.0
        eased = 1.0 - (1.0 - progress) ** 2
        current_x_max = x_min + (x_max - x_min) * eased
        assert current_x_max == pytest.approx(x_max)

    def test_xlim_at_midpoint(self):
        x_min, x_max = 100.0, 200.0
        progress = 0.5
        eased = 1.0 - (1.0 - progress) ** 2
        current_x_max = x_min + (x_max - x_min) * eased
        assert current_x_max == pytest.approx(100.0 + 100.0 * 0.75)

    def test_xlim_never_exceeds_max(self):
        x_min, x_max = 50.0, 150.0
        for i in range(101):
            progress = i / 100
            eased = 1.0 - (1.0 - progress) ** 2
            current_x_max = x_min + (x_max - x_min) * eased
            assert current_x_max <= x_max + 1e-9

    def test_xlim_never_below_min(self):
        x_min, x_max = 50.0, 150.0
        for i in range(101):
            progress = i / 100
            eased = 1.0 - (1.0 - progress) ** 2
            current_x_max = x_min + (x_max - x_min) * eased
            assert current_x_max >= x_min - 1e-9


class TestAnimationWithMockedWindow:
    """Test animation logic using a mocked Tk window (no GUI required)."""

    @pytest.fixture
    def mocked_window(self, monkeypatch):
        """Create a BalanceCurveWindow instance with all GUI deps mocked."""
        import tempfile
        from usage_history import UsageHistory

        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        history = UsageHistory(db_path=db_path)

        import usage_curve_window as ucw

        class FakeCanvas:
            def __init__(self):
                self.draw_count = 0
                self.xlims = []
            def draw(self):
                self.draw_count += 1

        class FakeAx:
            def __init__(self):
                self.title_text = ""
                self.xlims = []
                self.calls = []
            def __getattr__(self, name):
                if name in ("transAxes", "transData"):
                    return object()
                if name in ("xlim", "ylim"):
                    return (0.0, 1.0)
                if name.startswith("set_"):
                    def _stub(*a, **kw):
                        self.calls.append((name, a, kw))
                        return None
                    return _stub
                if name == "plot":
                    def _plot(*a, **kw):
                        return [object()]
                    return _plot
                if name == "fill_between":
                    return lambda *a, **kw: object()
                if name == "tick_params":
                    return lambda **kw: None
                if name == "grid":
                    return lambda *a, **kw: None
                if name == "set_xlim":
                    def _setxlim(lo, hi):
                        self.xlims.append((lo, hi))
                    return _setxlim
                if name == "set_facecolor":
                    return lambda *a, **kw: None
                return lambda *a, **kw: None
            def set_title(self, text, **kwargs):
                self.title_text = text
            def set_xlim(self, lo, hi):
                self.xlims.append((lo, hi))
            def plot(self, *args, **kwargs):
                return [object()]
            def fill_between(self, *args, **kwargs):
                return object()
            def set_facecolor(self, *args, **kwargs):
                pass
            def tick_params(self, **kwargs):
                pass
            def grid(self, *args, **kwargs):
                pass
            @property
            def spines(self):
                class _Spines(dict):
                    def values(self_inner):
                        class _Sp:
                            def set_color(self_inner2, *_):
                                pass
                        return [_Sp() for _ in range(4)]
                return _Spines()
            @property
            def yaxis(self):
                class _A:
                    label = type("L", (), {"set_color": lambda self, c: None})()
                return _A()
            @property
            def xaxis(self):
                class _A:
                    label = type("L", (), {"set_color": lambda self, c: None})()
                    def set_major_formatter(self, *_):
                        pass
                    def set_major_locator(self, *_):
                        pass
                return _A()

        class FakeFig:
            def __init__(self):
                self.patch = type("P", (), {"set_facecolor": lambda s, c: None})()
            def add_subplot(self, *_):
                return FakeAx()
            def tight_layout(self):
                pass

        class FakeCanvasWidget:
            def __init__(self):
                pass
            def grid(self, **_):
                pass
            def destroy(self):
                pass

        class FakeTkCanvas:
            def __init__(self, fig, master):
                self.canvas = FakeCanvas()
            def get_tk_widget(self):
                return FakeCanvasWidget()
            def draw(self):
                self.canvas.draw()

        monkeypatch.setattr(ucw, "Figure", lambda *a, **kw: FakeFig())
        monkeypatch.setattr(ucw, "FigureCanvasTkAgg", FakeTkCanvas)

        class FakeMenu:
            def __init__(self, master=None, values=None, width=None, **kwargs):
                self._value = values[2] if values and len(values) > 2 else (values[0] if values else "")
            def grid(self, **_):
                pass
            def set(self, v):
                self._value = v
            def configure(self, **_):
                pass
            def get(self):
                return self._value
        monkeypatch.setattr(ucw.ctk, "CTkOptionMenu", FakeMenu)

        class FakeFont:
            def __init__(self, *a, **kw):
                pass
        monkeypatch.setattr(ucw.ctk, "CTkFont", FakeFont)

        class FakeLabel:
            def __init__(self, master=None, **kwargs):
                pass
            def grid(self, **_):
                pass
            def configure(self, **_):
                pass
        monkeypatch.setattr(ucw.ctk, "CTkLabel", FakeLabel)

        class FakeFrame:
            def __init__(self, master=None, **kwargs):
                pass
            def grid(self, **_):
                pass
            def grid_columnconfigure(self, *_, **__):
                pass
            def grid_rowconfigure(self, *_, **__):
                pass
        monkeypatch.setattr(ucw.ctk, "CTkFrame", FakeFrame)

        monkeypatch.setattr(ucw.ctk.CTkToplevel, "__init__", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "grab_set", lambda self: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "lift", lambda self: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "focus", lambda self: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "title", lambda self, t: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "geometry", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "minsize", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "resizable", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "after", lambda self, ms, fn: f"timer-{ms}")
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "after_cancel", lambda self, t: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "grid_columnconfigure", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "grid_rowconfigure", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "grid", lambda self, *a, **kw: None)

        now = time.time()
        for i in range(20):
            history.record_balance_snapshot("uid-test", "hash", 100.0 - i * 0.1, "CNY")
            time.sleep(0.001)

        win = ucw.BalanceCurveWindow(
            parent=None,
            account_label="Test",
            api_key="sk-fake-key",
            uid="uid-test",
            history=history,
        )
        win._anim_after = lambda ms, fn: f"timer-{ms}"
        win._anim_after_cancel = lambda t: None
        win._render_calls = []

        yield win, history, db_path

        try:
            os.remove(db_path)
        except OSError:
            pass

    def test_animation_starts_animating_flag(self, mocked_window):
        win, _, _ = mocked_window
        assert win._animating is True

    def test_animation_initial_xlim_collapsed(self, mocked_window):
        win, _, _ = mocked_window
        assert win._anim_x_min is not None
        assert win._anim_x_max is not None
        assert win._anim_x_max > win._anim_x_min

    def test_animation_total_frames_set(self, mocked_window):
        win, _, _ = mocked_window
        assert win._anim_total_frames == 62

    def test_animation_xlim_collapsed_at_start(self, mocked_window):
        win, _, _ = mocked_window
        ax = win._ax
        first_xlim = ax.xlims[0]
        assert first_xlim[0] == first_xlim[1]

    def test_animate_frame_completes_to_full_xlim(self, mocked_window):
        win, _, _ = mocked_window
        ax = win._ax
        win._animate_frame(win._anim_total_frames - 1)
        last_xlim = ax.xlims[-1]
        assert last_xlim[0] == pytest.approx(win._anim_x_min)
        assert last_xlim[1] == pytest.approx(win._anim_x_max)
        assert win._animating is False

    def test_animate_frame_intermediate_progress(self, mocked_window):
        win, _, _ = mocked_window
        ax = win._ax
        mid_frame = win._anim_total_frames // 2
        win._animate_frame(mid_frame)
        last_xlim = ax.xlims[-1]
        progress = (mid_frame + 1) / win._anim_total_frames
        eased = 1.0 - (1.0 - progress) ** 2
        expected_x_max = win._anim_x_min + (win._anim_x_max - win._anim_x_min) * eased
        assert last_xlim[1] == pytest.approx(expected_x_max, rel=1e-6)
        assert win._animating is True

    def test_animate_frame_zero_does_not_finalize(self, mocked_window):
        win, _, _ = mocked_window
        win._animate_frame(0)
        assert win._animating is True
        assert win._anim_timer is not None

    def test_cancel_animation_resets_state(self, mocked_window):
        win, _, _ = mocked_window
        win._anim_timer = "fake-timer"
        win._cancel_animation()
        assert win._animating is False
        assert win._anim_timer is None

    def test_re_render_starts_new_animation(self, mocked_window):
        """Re-rendering should cancel the previous animation timer and start a new one."""
        win, _, _ = mocked_window
        win._anim_timer = "fake-timer"
        win._animating = True
        win._on_range_change("1小时")
        assert win._animating is True
        assert win._anim_timer is not None
        assert win._anim_timer != "fake-timer"


class TestAnimationWithEmptyData:
    """Test that animation is skipped when there's not enough data."""

    @pytest.fixture
    def empty_window(self, monkeypatch):
        import tempfile
        from usage_history import UsageHistory

        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(db_fd)
        history = UsageHistory(db_path=db_path)

        import usage_curve_window as ucw

        class FakeAx:
            def __init__(self):
                self.text_content = None
            def __getattr__(self, name):
                if name in ("transAxes", "transData"):
                    return object()
                if name in ("xlim", "ylim"):
                    return (0.0, 1.0)
                if name.startswith("set_"):
                    return lambda *a, **kw: None
                if name == "text":
                    def _text(*a, **kw):
                        self.text_content = a[0] if a else None
                    return _text
                if name == "set_xticks":
                    return lambda *a: None
                if name == "set_yticks":
                    return lambda *a: None
                if name == "tick_params":
                    return lambda **kw: None
                if name == "grid":
                    return lambda *a, **kw: None
                if name == "set_facecolor":
                    return lambda *a: None
                if name == "set_xlim":
                    return lambda *a: None
                return lambda *a, **kw: None
            def text(self, *a, **kw):
                self.text_content = a[0] if a else None
            def set_xticks(self, *a):
                pass
            def set_yticks(self, *a):
                pass
            @property
            def spines(self):
                class _Spines(dict):
                    def values(self_inner):
                        class _Sp:
                            def set_visible(self_inner2, *_):
                                pass
                        return [_Sp() for _ in range(4)]
                return _Spines()
            def set_facecolor(self, *a):
                pass
            def tick_params(self, **kw):
                pass
            def grid(self, *a, **kw):
                pass
            @property
            def yaxis(self):
                class _A:
                    label = type("L", (), {"set_color": lambda self, c: None})()
                return _A()
            @property
            def xaxis(self):
                class _A:
                    label = type("L", (), {"set_color": lambda self, c: None})()
                    def set_major_formatter(self, *_):
                        pass
                    def set_major_locator(self, *_):
                        pass
                return _A()
            def set_title(self, *a, **kw):
                pass
            def set_xlabel(self, *a, **kw):
                pass
            def set_ylabel(self, *a, **kw):
                pass

        class FakeFig:
            def __init__(self):
                self.patch = type("P", (), {"set_facecolor": lambda s, c: None})()
            def add_subplot(self, *_):
                return FakeAx()
            def tight_layout(self):
                pass

        class FakeCanvasWidget:
            def grid(self, **_):
                pass
            def destroy(self):
                pass

        class FakeCanvas:
            def draw(self):
                pass

        class FakeTkCanvas:
            def __init__(self, fig, master):
                pass
            def get_tk_widget(self):
                return FakeCanvasWidget()
            def draw(self):
                pass

        monkeypatch.setattr(ucw, "Figure", lambda *a, **kw: FakeFig())
        monkeypatch.setattr(ucw, "FigureCanvasTkAgg", FakeTkCanvas)

        class FakeMenu:
            def __init__(self, master=None, values=None, **kwargs):
                self._value = values[2] if values and len(values) > 2 else ""
            def grid(self, **_):
                pass
            def set(self, v):
                self._value = v
            def configure(self, **_):
                pass
            def get(self):
                return self._value
        monkeypatch.setattr(ucw.ctk, "CTkOptionMenu", FakeMenu)

        class FakeFont:
            def __init__(self, *a, **kw):
                pass
        monkeypatch.setattr(ucw.ctk, "CTkFont", FakeFont)

        class FakeLabel:
            def __init__(self, master=None, **kwargs):
                pass
            def grid(self, **_):
                pass
            def configure(self, **_):
                pass
        monkeypatch.setattr(ucw.ctk, "CTkLabel", FakeLabel)

        class FakeFrame:
            def __init__(self, master=None, **kwargs):
                pass
            def grid(self, **_):
                pass
            def grid_columnconfigure(self, *_, **__):
                pass
            def grid_rowconfigure(self, *_, **__):
                pass
        monkeypatch.setattr(ucw.ctk, "CTkFrame", FakeFrame)

        monkeypatch.setattr(ucw.ctk.CTkToplevel, "__init__", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "grab_set", lambda self: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "lift", lambda self: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "focus", lambda self: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "title", lambda self, t: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "geometry", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "minsize", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "resizable", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "after", lambda self, ms, fn: f"timer-{ms}")
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "after_cancel", lambda self, t: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "grid_columnconfigure", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "grid_rowconfigure", lambda self, *a, **kw: None)
        monkeypatch.setattr(ucw.ctk.CTkToplevel, "grid", lambda self, *a, **kw: None)

        win = ucw.BalanceCurveWindow(
            parent=None,
            account_label="Empty",
            api_key="sk-fake-key",
            uid="nonexistent",
            history=history,
        )

        yield win

        try:
            os.remove(db_path)
        except OSError:
            pass

    def test_empty_data_no_animation(self, empty_window):
        win = empty_window
        assert win._animating is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
