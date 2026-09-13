from __future__ import annotations

from PySide6.QtWidgets import QApplication

from config import AppConfig
from event_bus import EventBus, EVENT_THEME_CHANGED
from theme_manager import ThemeManager
from qss import build_qss


"""主题子系统 App 侧协调（Qt 版，ISSUE-MIG-02）。

底层模型/管理器是 main/theme_manager.py 的 ThemeManager（ISSUE-THM-01），
本类负责 App 层接线：加载内置/用户主题、同步 custom 种子、把
theme_changed 事件的 ThemeLayer 转成 QSS 全局重抛光（THM-05 的
最小形态已随 Phase A 事件契约就位）。
"""


class ThemeCoordinator:
    """ThemeManager 与 QApplication 样式表之间的桥。"""

    def __init__(self, event_bus: EventBus | None, app: QApplication):
        self.theme_manager = ThemeManager(event_bus=event_bus)
        self._app = app
        if event_bus is not None:
            event_bus.subscribe(EVENT_THEME_CHANGED, self._on_theme_changed)

    def _on_theme_changed(self, event) -> None:
        layer = event.payload.get("layer")
        if layer is not None:
            self._app.setStyleSheet(build_qss(layer))

    def load(self, builtin_dir: str) -> None:
        """加载内置主题 + 用户主题目录（同名覆盖）。"""
        self.theme_manager.load_directory(builtin_dir)
        self.load_user()

    def load_user(self) -> None:
        """ISSUE-THM-03：加载用户主题目录（后台加载阶段单独调用）。"""
        self.theme_manager.load_user_directory()

    def sync_config(self, config: AppConfig) -> None:
        """同步配置中的 custom 种子色（THM-06）。"""
        self.theme_manager.set_custom_seed(config.settings.custom_theme_seed)

    def apply_startup(self, config: AppConfig) -> None:
        """按配置应用当前主题（apply 内部广播 theme_changed → QSS 重抛光）。"""
        self.theme_manager.apply(config.settings.theme, mode=config.settings.theme_mode)

    def apply_mode(self, mode: str, config: AppConfig) -> None:
        """设置对话框的亮/暗模式切换（原 App._apply_theme）。

        仅更新 config.settings.theme_mode 并广播重着色；配置落盘由
        settings_changed 事件处理器统一执行（与 Phase B 收敛一致）。
        """
        config.settings.theme_mode = mode
        self.theme_manager.apply(config.settings.theme, mode=mode)
