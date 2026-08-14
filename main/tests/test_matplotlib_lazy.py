"""ISSUE-PFM-01：matplotlib 延迟加载单元测试。

测试覆盖：
- 模块加载后 matplotlib 不被 import（启动时不加载）
- _ensure_matplotlib() 首次调用后缓存模块对象
- 二次调用返回相同缓存（不重复初始化）
- 缓存包含绘图所需对象（Figure / FigureCanvasTkAgg / mdates）
"""
import importlib
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestMatplotlibLazyLoad:
    """ISSUE-PFM-01：matplotlib 延迟加载测试。"""

    def test_matplotlib_not_imported_on_module_load(self):
        """加载 usage_curve_window 模块后，matplotlib 不应被 import。

        验证 AC1：启动时不再 import matplotlib。
        """
        # 移除可能已加载的 matplotlib 与目标模块
        for mod_name in list(sys.modules.keys()):
            if mod_name == "matplotlib" or mod_name.startswith("matplotlib."):
                del sys.modules[mod_name]
        if "usage_curve_window" in sys.modules:
            del sys.modules["usage_curve_window"]

        # 重新加载模块（模拟启动时 import）
        import usage_curve_window

        # matplotlib 不应被 import
        assert "matplotlib" not in sys.modules, \
            "ISSUE-PFM-01 失败：模块加载后 matplotlib 不应被 import"

    def test_matplotlib_not_imported_on_bar_window_load(self):
        """加载 usage_bar_window 模块后，matplotlib 不应被 import。"""
        for mod_name in list(sys.modules.keys()):
            if mod_name == "matplotlib" or mod_name.startswith("matplotlib."):
                del sys.modules[mod_name]
        if "usage_bar_window" in sys.modules:
            del sys.modules["usage_bar_window"]

        import usage_bar_window

        assert "matplotlib" not in sys.modules, \
            "ISSUE-PFM-01 失败：模块加载后 matplotlib 不应被 import"

    def test_ensure_matplotlib_caches_modules(self):
        """_ensure_matplotlib() 首次调用后应缓存 matplotlib 模块对象。"""
        # 清理缓存
        import usage_curve_window
        usage_curve_window._mpl_cache.clear()
        for mod_name in list(sys.modules.keys()):
            if mod_name == "matplotlib" or mod_name.startswith("matplotlib."):
                del sys.modules[mod_name]

        # 首次调用
        mpl = usage_curve_window._ensure_matplotlib()
        assert "matplotlib" in sys.modules, "首次调用后 matplotlib 应被 import"
        assert mpl, "返回的缓存字典不应为空"
        assert "Figure" in mpl, "缓存应包含 Figure"
        assert "FigureCanvasTkAgg" in mpl, "缓存应包含 FigureCanvasTkAgg"
        assert "mdates" in mpl, "缓存应包含 mdates"

    def test_ensure_matplotlib_returns_same_cache(self):
        """二次调用 _ensure_matplotlib() 应返回相同缓存对象（不重复初始化）。"""
        import usage_curve_window
        usage_curve_window._mpl_cache.clear()

        first = usage_curve_window._ensure_matplotlib()
        first_figure_id = id(first["Figure"])

        second = usage_curve_window._ensure_matplotlib()
        second_figure_id = id(second["Figure"])

        assert first is second, "应返回同一缓存字典对象"
        assert first_figure_id == second_figure_id, "Figure 对象应为同一引用"

    def test_ensure_matplotlib_bar_window_caches(self):
        """usage_bar_window 的 _ensure_matplotlib 也应正确缓存。"""
        import usage_bar_window
        usage_bar_window._mpl_cache.clear()
        for mod_name in list(sys.modules.keys()):
            if mod_name == "matplotlib" or mod_name.startswith("matplotlib."):
                del sys.modules[mod_name]

        mpl = usage_bar_window._ensure_matplotlib()
        assert "matplotlib" in sys.modules
        assert "Figure" in mpl
        assert "FigureCanvasTkAgg" in mpl
