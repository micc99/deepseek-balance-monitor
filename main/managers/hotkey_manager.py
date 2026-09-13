from __future__ import annotations

from error_logger import log_exception


"""全局热键管理（Qt 版，ISSUE-MIG-06，D2 决策：keyboard → pynput）。

pynput GlobalHotKeys 在守护线程监听，回调经 WindowManager 的 after(0)
桥投递回 UI 线程（线程契约见 qt_bridge）。pynput 跨平台一致（D2），
导入失败（无显示环境等）静默降级。UX-02 快捷键可配置化在 Phase D 接入。
"""

DEFAULT_TOGGLE = "<ctrl>+<shift>+b"


def pynput_to_qt(hotkey: str) -> str:
    """pynput 修饰键格式转 QKeySequence 可解析格式。

    "<ctrl>+<shift>+b" → "Ctrl+Shift+b"（QKeySequence 大小写不敏感，
    单字母保留原样即可命中）。
    """
    parts = [seg.strip(" <>") for seg in (hotkey or "").split("+") if seg.strip()]
    return "+".join(parts)


class HotkeyManager:
    """全局热键注册与注销（ISSUE-UX-02：热键来自 config.settings.hotkeys）。"""

    def __init__(self):
        self._listener = None
        self._hotkey = None
        self._callback = None

    def register_toggle(self, callback, hotkey: str = DEFAULT_TOGGLE) -> None:
        """注册悬浮窗切换全局热键；失败记录日志不崩溃。重复注册先注销。"""
        if self._listener is not None:
            self.unregister()
        self._callback = callback
        self._hotkey = hotkey or DEFAULT_TOGGLE
        try:
            from pynput import keyboard
            self._listener = keyboard.GlobalHotKeys({self._hotkey: callback})
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
