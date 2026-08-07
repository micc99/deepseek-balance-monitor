"""ISSUE-ARC-05：快捷方式注入修复单元测试。

测试覆盖：
- validate_shortcut_path 路径校验
  - 仅允许绝对路径
  - 禁止 shell 元字符（; | & 换行符）
  - 拒绝相对路径
- create_shortcut 调用安全性
  - 路径校验失败时不执行
  - 不使用字符串拼接 PowerShell 命令

注意：实际快捷方式创建依赖 Windows COM / PowerShell，单元测试仅验证
路径校验逻辑与失败分支，不实际创建 .lnk 文件。
"""
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shortcut_util import validate_shortcut_path as _validate_shortcut_path
from shortcut_util import create_shortcut as _create_shortcut


class TestValidateShortcutPath:
    """_validate_shortcut_path 路径校验测试（ISSUE-ARC-05 AC3）。"""

    def test_absolute_path_valid(self):
        """绝对路径应通过校验。"""
        if sys.platform == "win32":
            assert _validate_shortcut_path("C:\\Users\\test\\app.lnk") is True
            assert _validate_shortcut_path("D:\\Program Files\\app.exe") is True
        else:
            assert _validate_shortcut_path("/usr/local/bin/app") is True
            assert _validate_shortcut_path("/home/test/app.lnk") is True

    def test_relative_path_rejected(self):
        """相对路径应被拒绝。"""
        assert _validate_shortcut_path("relative/path/app.lnk") is False
        assert _validate_shortcut_path("app.exe") is False
        assert _validate_shortcut_path("./app.lnk") is False

    def test_empty_path_rejected(self):
        """空路径应被拒绝。"""
        assert _validate_shortcut_path("") is False

    def test_path_with_semicolon_rejected(self):
        """包含分号的路径应被拒绝（shell 元字符）。"""
        if sys.platform == "win32":
            assert _validate_shortcut_path("C:\\app.lnk; malicious") is False
        assert _validate_shortcut_path("/usr/app; rm -rf") is False

    def test_path_with_pipe_rejected(self):
        """包含管道符的路径应被拒绝。"""
        if sys.platform == "win32":
            assert _validate_shortcut_path("C:\\app.lnk| malicious") is False
        assert _validate_shortcut_path("/usr/app| cat") is False

    def test_path_with_ampersand_rejected(self):
        """包含 & 的路径应被拒绝。"""
        if sys.platform == "win32":
            assert _validate_shortcut_path("C:\\app.lnk& malicious") is False
        assert _validate_shortcut_path("/usr/app& bg") is False

    def test_path_with_newline_rejected(self):
        """包含换行符的路径应被拒绝。"""
        assert _validate_shortcut_path("C:\\app.lnk\nmalicious") is False
        assert _validate_shortcut_path("/usr/app\nrm") is False

    def test_path_with_carriage_return_rejected(self):
        """包含回车符的路径应被拒绝。"""
        assert _validate_shortcut_path("C:\\app.lnk\rmalicious") is False

    def test_path_with_spaces_valid(self):
        """含空格的绝对路径应通过校验（常见情况）。"""
        if sys.platform == "win32":
            path = "C:\\Program Files\\My App\\app.exe"
            assert _validate_shortcut_path(path) is True
        else:
            path = "/usr/local/my app/app"
            assert _validate_shortcut_path(path) is True

    def test_path_with_chinese_valid(self):
        """中文路径应通过校验。"""
        if sys.platform == "win32":
            path = "C:\\用户\\测试\\应用.exe"
            assert _validate_shortcut_path(path) is True

    def test_path_with_unicode_valid(self):
        """Unicode 字符路径应通过校验。"""
        if sys.platform == "win32":
            path = "C:\\用户\\测试\\应用 🔑.exe"
            assert _validate_shortcut_path(path) is True

    def test_path_with_single_quote_valid(self):
        """含单引号的绝对路径应通过校验（ISSUE-ARC-05 核心场景）。

        旧版本因 PowerShell 字符串拼接导致注入，修复后应允许此类路径。
        """
        if sys.platform == "win32":
            path = "C:\\User's App\\app.exe"
            assert _validate_shortcut_path(path) is True


class TestCreateShortcutSafety:
    """_create_shortcut 安全性测试（ISSUE-ARC-05 AC1/AC2）。"""

    def test_invalid_path_does_not_execute(self):
        """路径校验失败时不应执行任何操作。"""
        # 使用无效路径，验证不会抛出异常且不调用 subprocess
        with patch("subprocess.run") as mock_run:
            _create_shortcut("relative/path.lnk", "target.exe")
            mock_run.assert_not_called()

    def test_invalid_target_does_not_execute(self):
        """目标路径校验失败时不应执行任何操作。"""
        with patch("subprocess.run") as mock_run:
            if sys.platform == "win32":
                _create_shortcut("C:\\valid.lnk", "invalid;target")
            else:
                _create_shortcut("/tmp/valid.lnk", "invalid;target")
            mock_run.assert_not_called()

    def test_empty_paths_does_not_execute(self):
        """空路径不应执行。"""
        with patch("subprocess.run") as mock_run:
            _create_shortcut("", "")
            mock_run.assert_not_called()

    def test_valid_path_no_string_interpolation(self):
        """ISSUE-ARC-05 AC2：有效路径不应使用字符串插值 PowerShell 命令。

        验证 subprocess.run 调用时 command 是参数化形式（-ArgumentList），
        而非字符串拼接。
        """
        if sys.platform != "win32":
            pytest.skip("快捷方式创建仅在 Windows 测试")

        # 模拟 pywin32 不可用，强制走 PowerShell 回退路径
        with patch.dict("sys.modules", {"win32com": None, "win32com.client": None}):
            with patch("subprocess.run") as mock_run:
                lnk = "C:\\Test Path\\app.lnk"
                target = "C:\\Program Files\\My App\\app.exe"
                _create_shortcut(lnk, target)
                # 应该调用 subprocess.run
                mock_run.assert_called_once()
                call_args = mock_run.call_args
                # 第一个参数应为 list（参数化），而非字符串拼接
                cmd = call_args[0][0] if call_args[0] else call_args[1].get("args")
                assert isinstance(cmd, list), "应使用参数化调用，而非字符串拼接"
                # 应包含 -ArgumentList 形式（-LnkPath, -TargetPath）
                cmd_str = " ".join(cmd)
                assert "-LnkPath" in cmd_str
                assert "-TargetPath" in cmd_str
                # 路径应作为独立参数，而非拼接到脚本字符串中
                assert lnk in cmd
                assert target in cmd
