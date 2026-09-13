from __future__ import annotations

import customtkinter as ctk

from animations import AnimationHelper
from config import AppConfig
from theme_manager import ThemeManager


"""主题子系统 App 侧协调（ISSUE-ARC-01）。

命名说明：底层模型/管理器是 main/theme_manager.py 的 ThemeManager
（ISSUE-THM-01），本类负责 App 层接线——加载内置/用户主题、同步
custom 种子、应用 ctk 外观模式与波纹色（ISSUE-THM-02/06）。
不重复实现主题逻辑；Qt 迁移后 ctk 相关部分由 Phase C 的 QSS 渲染层替代。
"""


class ThemeCoordinator:
    """ThemeManager 与运行中的应用状态（config/ctk）之间的桥。"""

    def __init__(self, event_bus):
        self.theme_manager = ThemeManager(event_bus=event_bus)

    def load(self, builtin_dir: str) -> None:
        """加载内置主题 + 用户主题目录（同名覆盖）。"""
        self.theme_manager.load_directory(builtin_dir)
        self.theme_manager.load_user_directory()

    def sync_config(self, config: AppConfig) -> None:
        """同步配置中的 custom 种子色（THM-06）。"""
        self.theme_manager.set_custom_seed(config.settings.custom_theme_seed)

    def apply_startup(self, config: AppConfig) -> None:
        """按配置应用当前主题（启动与后台加载完成两个时机共用）。"""
        ctk.set_appearance_mode(config.settings.theme_mode)
        AnimationHelper.set_ripple_color(config.settings.ripple_color)
        self.theme_manager.apply(config.settings.theme, mode=config.settings.theme_mode)

    def apply_mode(self, mode: str, config: AppConfig) -> None:
        """设置对话框的亮/暗模式切换（原 App._apply_theme）。

        仅更新 config.settings.theme_mode 并应用外观；配置落盘由
        settings_changed 事件处理器统一执行（原实现此处与事件处理
        各 save 一次，属冗余双写，重构后收敛为一处）。
        """
        ctk.set_appearance_mode(mode)
        config.settings.theme_mode = mode
        self.theme_manager.apply(config.settings.theme, mode=mode)
