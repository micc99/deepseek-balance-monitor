from __future__ import annotations

import json
import logging
import os
import threading

from event_bus import EventBus, EVENT_THEME_CHANGED
from theme_models import Theme, ThemeLayer, MODE_DARK, MODE_LIGHT


"""主题管理器：主题注册表 + 应用切换 + 导入导出。

ISSUE-THM-01：
- register(theme) / apply(name) / export(path) / import(path) 四个核心 API
- apply 成功后经事件总线广播 theme_changed，UI 订阅后实时重着色
  （Phase D THM-05 消费该事件实现全窗刷新）
- 零 UI 框架依赖（Phase A AC3，有测试断言），迁移 Qt 后原样存活

实例策略：不做模块级单例/全局变量（用户决策），由 App 创建唯一实例
并注入依赖方（de facto 单例，见 AGENTS.md §4 编排层）。

线程模型：register/apply 可能被任意线程调用，注册表与当前状态由
RLock 保护；theme_changed 广播在调用方线程同步发出，UI 订阅方
自行 after(0) 调度（与 EventBus 契约一致）。
"""

logger = logging.getLogger(__name__)

# ISSUE-THM-03：用户主题目录（THM-02 内置主题同名时可被用户版本覆盖）
DEFAULT_USER_THEMES_DIR = os.path.expanduser(os.path.join("~", ".deepseek-monitor", "themes"))


class ThemeManager:
    """主题注册表与切换中枢。

    Args:
        event_bus: 应用事件总线；None 时静默（单测/无总线场景），
                   apply 仍返回结果但不广播。
    """

    def __init__(self, event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._themes: dict[str, Theme] = {}
        self._lock = threading.RLock()
        self._current_name: str = ""
        self._current_mode: str = MODE_DARK

    # ---- 注册表 ----

    def register(self, theme: Theme, replace: bool = True) -> None:
        """注册主题；同名主题默认覆盖（THM-03 用户主题同名覆盖内置）。"""
        with self._lock:
            if theme.name in self._themes and not replace:
                return
            self._themes[theme.name] = theme
        logger.debug("主题已注册: name=%s label=%s", theme.name, theme.label)

    def get(self, name: str) -> Theme | None:
        with self._lock:
            return self._themes.get(name)

    def names(self) -> list[str]:
        """按注册顺序返回全部主题名（UI 下拉顺序的来源）。"""
        with self._lock:
            return list(self._themes.keys())

    def labels(self) -> list[tuple[str, str]]:
        """按注册顺序返回 (name, label) 对，供设置界面下拉直接使用。"""
        with self._lock:
            return [(t.name, t.label) for t in self._themes.values()]

    # ---- 应用切换 ----

    @property
    def current_name(self) -> str:
        return self._current_name

    @property
    def current_mode(self) -> str:
        return self._current_mode

    def current_theme(self) -> Theme | None:
        with self._lock:
            return self._themes.get(self._current_name)

    def current_layer(self) -> ThemeLayer | None:
        """当前生效的语义色层（name+mode 解析结果），未应用过返回 None。"""
        theme = self.current_theme()
        if theme is None:
            return None
        return theme.layer(self._current_mode)

    def apply(self, name: str, mode: str | None = None) -> bool:
        """应用主题（可同时切换亮/暗模式），成功后广播 theme_changed。

        Args:
            name: 主题名；未注册时 WARN 并返回 False（不改变当前状态）
            mode: MODE_LIGHT / MODE_DARK；None 表示沿用当前模式

        Returns:
            是否应用成功
        """
        theme = self.get(name)
        if theme is None:
            logger.warning("应用主题失败，主题未注册: %s", name)
            return False
        with self._lock:
            self._current_name = name
            if mode in (MODE_LIGHT, MODE_DARK):
                self._current_mode = mode
            effective_mode = self._current_mode
            layer = theme.layer(effective_mode)
        if self._event_bus is not None:
            self._event_bus.publish(
                EVENT_THEME_CHANGED,
                payload={
                    "name": name,
                    "label": theme.label,
                    "mode": effective_mode,
                    "layer": layer,
                    "ripple_color": theme.ripple_color,
                },
                source="theme_manager",
            )
        logger.info("主题已应用: name=%s label=%s mode=%s", name, theme.label, effective_mode)
        return True

    # ---- 目录加载（THM-02 内置主题 / THM-03 用户主题目录共用）----

    def load_directory(self, path: str, replace: bool = True) -> list[str]:
        """扫描目录下全部 *.json 主题并注册，返回成功加载的主题名列表。

        - 主题名以 JSON 内 name 字段为准，与文件名无关
        - 同名主题默认覆盖（replace=False 时保留先注册者；
          用户目录后加载，天然实现"用户主题同名覆盖内置"）
        - 单个文件解析/读取失败：WARN 跳过，不影响其他主题（THM-03 AC4 降级）
        - 目录不存在：静默返回空列表（用户主题目录首次运行时尚未创建）
        """
        loaded: list[str] = []
        if not path or not os.path.isdir(path):
            return loaded
        for fname in sorted(os.listdir(path)):
            if not fname.lower().endswith(".json"):
                continue
            fpath = os.path.join(path, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    theme = Theme.from_dict(json.load(f))
                self.register(theme, replace=replace)
                loaded.append(theme.name)
            except (ValueError, json.JSONDecodeError, OSError) as e:
                logger.warning("主题文件加载失败已跳过: %s (%s)", fpath, e)
        return loaded

    def load_user_directory(self, path: str = DEFAULT_USER_THEMES_DIR) -> list[str]:
        """ISSUE-THM-03：加载用户主题目录（默认 ~/.deepseek-monitor/themes/）。

        在内置主题之后调用，同名用户主题即覆盖内置版本。
        """
        loaded = self.load_directory(path, replace=True)
        if loaded:
            logger.info("已加载用户主题: %s", loaded)
        return loaded

    def rescan(self, builtin_dir: str, user_dir: str = DEFAULT_USER_THEMES_DIR) -> list[str]:
        """ISSUE-THM-03：热加载——重新扫描内置 + 用户目录并重建注册表。

        以目录内容为准：
        - 新增/修改的主题文件生效（编辑器保存后无需重启）
        - 被删除的用户主题覆盖回落到内置版本；用户独有主题被移除
        - 运行时程序化注册的主题（如 THM-06 custom）会被清空，
          由其归属流程在下次 apply 时重建

        Returns:
            重扫后注册表中的全部主题名（内置顺序 + 用户覆盖新增）
        """
        with self._lock:
            self._themes.clear()
        loaded = self.load_directory(builtin_dir)
        if user_dir:
            loaded += self.load_directory(user_dir)
        logger.info("主题热加载完成，共 %d 个主题", len(self.names()))
        return loaded

    # ---- 导入 / 导出（THM-03 用户主题文件、THM-04 编辑器共用）----

    def export(self, path: str, name: str | None = None) -> None:
        """导出主题 JSON。name 为空时导出当前主题；未应用过抛 ValueError。"""
        target = name if name is not None else self._current_name
        theme = self.get(target)
        if theme is None:
            raise ValueError(f"主题未注册，无法导出: {target}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(theme.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("主题已导出: name=%s path=%s", theme.name, path)

    def import_theme(self, path: str) -> Theme:
        """从 JSON 导入主题并注册。文件缺失/格式错误抛异常（THM-03 降级处理）。"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        theme = Theme.from_dict(data)
        self.register(theme)
        logger.info("主题已导入: name=%s label=%s", theme.name, theme.label)
        return theme
