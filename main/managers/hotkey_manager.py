from __future__ import annotations

import sys

from error_logger import log_exception


"""全局热键管理（ISSUE-ARC-01，原 App 内联逻辑）。

UX-02 快捷键可配置化在迁移线 Phase D 接入（当前固定 Ctrl+Shift+B）。
keyboard 库为 Windows 专属（AGENTS.md §6.4），非 Windows 全部 no-op。
"""

_HOTKEY_TOGGLE = "ctrl+shift+b"


class HotkeyManager:
    """全局热键注册与注销。"""

    def __init__(self):
        self._registered = False

    def register_toggle(self, callback) -> None:
        """注册悬浮窗切换热键；失败记录日志不崩溃。"""
        if sys.platform != "win32":
            return
        try:
            import keyboard
            keyboard.add_hotkey(_HOTKEY_TOGGLE, callback)
            self._registered = True
        except Exception as e:
            log_exception("HotkeyManager.register_toggle", e)

    def unregister(self) -> None:
        """注销全部热键（App._quit 调用；幂等）。"""
        if sys.platform != "win32":
            return
        if not self._registered:
            return
        try:
            import keyboard
            keyboard.unhook_all()
            self._registered = False
        except Exception as e:
            log_exception("HotkeyManager.unregister", e)
