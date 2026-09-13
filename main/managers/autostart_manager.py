from __future__ import annotations

import os
import sys

from error_logger import log_exception
from shortcut_util import create_shortcut


"""开机自启 .lnk 快捷方式管理（ISSUE-ARC-01，原 App 模块级函数收编）。

Windows 专属；仅在打包（frozen）环境下实际写 .lnk，源码运行 no-op
（与原 _set_autostart 行为一致）。快捷方式创建纯逻辑在 shortcut_util
（ISSUE-ARC-05），本类只做生命周期编排。
"""


def _startup_dir() -> str:
    return os.path.join(
        os.getenv("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


class AutostartManager:
    """开机自启开关。"""

    def __init__(self, shortcut_name: str = "DeepSeekBalanceMonitor.lnk"):
        self._lnk_path = os.path.join(_startup_dir(), shortcut_name)

    @property
    def lnk_path(self) -> str:
        return self._lnk_path

    def set(self, enable: bool) -> None:
        """启用创建 .lnk，禁用删除；非 Windows / 源码运行 no-op。"""
        if sys.platform != "win32":
            return
        if not getattr(sys, "frozen", False):
            return
        if enable:
            create_shortcut(self._lnk_path, sys.executable)
        else:
            try:
                os.remove(self._lnk_path)
            except FileNotFoundError:
                pass
            except Exception as e:
                log_exception("AutostartManager.set", e)

    def is_enabled(self) -> bool:
        """快捷方式存在即视为启用；非 Windows 返回 False。"""
        if sys.platform != "win32":
            return False
        return os.path.exists(self._lnk_path)
