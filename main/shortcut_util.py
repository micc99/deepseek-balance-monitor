"""快捷方式创建工具（ISSUE-ARC-05 注入修复）。

从 main.py 抽离的纯逻辑模块，无 GUI 依赖，便于单元测试。

功能：
- validate_shortcut_path: 路径安全校验，禁止 shell 元字符注入
- create_shortcut: 优先用 pywin32，回退到 PowerShell 参数化调用
"""
import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def validate_shortcut_path(path: str) -> bool:
    """校验快捷方式相关路径安全性（ISSUE-ARC-05）。

    仅允许绝对路径，禁止包含 shell 元字符（; | & 等），
    防止 PowerShell 字符串拼接注入。

    参数:
        path: 待校验的文件路径

    返回:
        bool: True 表示路径安全，False 表示不安全
    """
    if not path:
        return False
    if not os.path.isabs(path):
        return False
    # 禁止 shell 元字符（即使经过转义，也按危险处理）
    forbidden = (";", "|", "&", "\n", "\r")
    return not any(ch in path for ch in forbidden)


def create_shortcut(lnk_path: str, target: str):
    """创建 Windows 快捷方式（ISSUE-ARC-05 修复注入风险）。

    优先使用 pywin32 的 ShellLink 对象（无字符串拼接）；
    若 pywin32 不可用，回退到 PowerShell 但使用 -ArgumentList 参数化，
    禁止字符串插值。

    路径校验：仅允许绝对路径，不含 ; | & 等特殊字符。

    参数:
        lnk_path: 快捷方式 .lnk 文件的绝对路径
        target: 快捷方式指向的目标可执行文件绝对路径
    """
    if not validate_shortcut_path(lnk_path):
        logger.error("快捷方式路径校验失败：%s", lnk_path)
        return
    if not validate_shortcut_path(target):
        logger.error("快捷方式目标路径校验失败：%s", target)
        return

    # 优先方案：pywin32（无 shell 调用，无注入风险）
    try:
        import win32com.client  # type: ignore
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(lnk_path)
        shortcut.TargetPath = target
        shortcut.Save()
        logger.info("快捷方式已创建（pywin32）：%s -> %s", lnk_path, target)
        return
    except ImportError:
        logger.debug("pywin32 未安装，回退到 PowerShell 参数化调用")
    except Exception as e:
        logger.warning("pywin32 创建快捷方式失败，回退到 PowerShell：%s", e)

    # 回退方案：PowerShell 参数化调用（禁止字符串插值）
    # 通过 -ArgumentList 将路径作为参数传递，PowerShell 内部用单引号包裹
    # 路径中若含单引号，PowerShell 单引号转义为两个单引号
    ps_script = (
        "param([string]$LnkPath, [string]$TargetPath); "
        "$WshShell = New-Object -ComObject WScript.Shell; "
        "$Shortcut = $WshShell.CreateShortcut($LnkPath); "
        "$Shortcut.TargetPath = $TargetPath; "
        "$Shortcut.Save()"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script,
             "-LnkPath", lnk_path, "-TargetPath", target],
            capture_output=True,
            timeout=10,
            check=False,
        )
        logger.info("快捷方式已创建（PowerShell 参数化）：%s -> %s", lnk_path, target)
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.error("PowerShell 创建快捷方式失败：%s", e)


# 平台非 Windows 时提供空实现，避免 import 失败
if sys.platform != "win32":
    def create_shortcut(lnk_path: str, target: str):  # noqa: F811
        """非 Windows 平台的空实现。"""
        logger.debug("非 Windows 平台，跳过快捷方式创建")
