from __future__ import annotations

from error_logger import log_exception


"""全局热键管理（Qt 版，ISSUE-MIG-06，D2 决策：keyboard → pynput）。

pynput GlobalHotKeys 在守护线程监听，回调经 WindowManager 的 after(0)
桥投递回 UI 线程（线程契约见 qt_bridge）。pynput 跨平台一致（D2），
导入失败（无显示环境等）静默降级。UX-02 快捷键可配置化在 Phase D 接入。
"""

_HOTKEY_TOGGLE = "<ctrl>+<shift>+b"


class HotkeyManager:
    """全局热键注册与注销。"""

    def __init__(self):
        self._listener = None

    def register_toggle(self, callback) -> None:
        """注册悬浮窗切换热键（Ctrl+Shift+B）；失败记录日志不崩溃。"""
        try:
            from pynput import keyboard
            self._listener = keyboard.GlobalHotKeys({_HOTKEY_TOGGLE: callback})
            self._listener.daemon = True
            self._listener.start()
        except Exception as e:
            self._listener = None
            log_exception("HotkeyManager.register_toggle", e)

    def unregister(self) -> None:
        """停止热键监听（App._quit 调用；幂等）。"""
        if self._listener is None:
            return
        try:
            self._listener.stop()
        except Exception as e:
            log_exception("HotkeyManager.unregister", e)
        self._listener = None
