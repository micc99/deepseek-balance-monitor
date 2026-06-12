#!/usr/bin/env python3
"""DeepSeek Balance Monitor MCP Server.

提供 API 余额查询工具，支持多 Provider：DeepSeek、硅基流动、月之暗面、OpenRouter、智谱AI。
"""

import sys
import os
from typing import Optional, List
from enum import Enum

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict

from balance_checker import (
    PROVIDERS,
    get_provider,
    get_provider_list,
    BalanceStatus,
)
from config import load_config, save_config, AccountConfig, mask_api_key

# 初始化 MCP 服务器
mcp = FastMCP("deepseek_balance_monitor_mcp")


# ==================== Pydantic Models ====================

class ProviderName(str, Enum):
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"
    MOONSHOT = "moonshot"
    OPENROUTER = "openrouter"
    ZHIPU = "zhipu"


class CheckBalanceInput(BaseModel):
    """查询单个账户余额的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    api_key: str = Field(..., description="API Key", min_length=1)
    provider: ProviderName = Field(
        default=ProviderName.DEEPSEEK,
        description="Provider 类型：deepseek、siliconflow、moonshot、openrouter、zhipu"
    )


class CheckAccountBalanceInput(BaseModel):
    """通过账户 UID 查询余额。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    uid: str = Field(..., description="账户 UID（8位十六进制字符串）", min_length=8, max_length=8)


class AddAccountInput(BaseModel):
    """添加新账户的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    label: str = Field(..., description="账户标签名称", min_length=1, max_length=50)
    api_key: str = Field(..., description="API Key", min_length=1)
    provider: ProviderName = Field(
        default=ProviderName.DEEPSEEK,
        description="Provider 类型"
    )


class RemoveAccountInput(BaseModel):
    """删除账户的输入参数。"""
    model_config = ConfigDict(str_strip_whitespace=True)

    uid: str = Field(..., description="账户 UID", min_length=8, max_length=8)


# ==================== Tools ====================

@mcp.tool(
    name="list_providers",
    annotations={
        "title": "列出支持的 Provider",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def list_providers() -> str:
    """列出所有支持的 API Provider。

    Returns:
        Markdown 格式的 Provider 列表，包含名称、标签和描述。
    """
    providers = get_provider_list()
    lines = ["# 支持的 Provider", ""]
    for name, label, desc in providers:
        lines.append(f"- **{label}** (`{name}`): {desc}")
    return "\n".join(lines)


@mcp.tool(
    name="list_accounts",
    annotations={
        "title": "列出已配置的账户",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def list_accounts() -> str:
    """列出所有已配置的账户信息（API Key 会脱敏显示）。

    Returns:
        Markdown 格式的账户列表，包含 UID、标签、Provider 和脱敏后的 API Key。
    """
    config = load_config()
    if not config.accounts:
        return "暂无配置的账户。使用 add_account 工具添加新账户。"

    lines = ["# 已配置的账户", ""]
    for acc in config.accounts:
        masked_key = mask_api_key(acc.api_key)
        provider = get_provider(acc.provider)
        lines.append(f"## {acc.label}")
        lines.append(f"- **UID**: `{acc.uid}`")
        lines.append(f"- **Provider**: {provider.label} ({acc.provider})")
        lines.append(f"- **API Key**: `{masked_key}`")
        lines.append("")
    return "\n".join(lines)


@mcp.tool(
    name="check_balance",
    annotations={
        "title": "查询 API 余额",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def check_balance(params: CheckBalanceInput) -> str:
    """查询指定 Provider 和 API Key 的余额。

    直接提供 API Key 和 Provider 类型进行余额查询，无需预先配置账户。

    Args:
        params: 包含 api_key 和 provider 的输入参数

    Returns:
        Markdown 格式的余额信息，包含状态、余额明细。
    """
    provider = get_provider(params.provider.value)
    result = provider.check_balance(params.api_key)

    lines = [f"# {provider.label} 余额查询结果", ""]

    if result.status == BalanceStatus.ERROR:
        lines.append(f"**状态**: 错误")
        lines.append(f"**错误信息**: {result.error_message}")
        return "\n".join(lines)

    lines.append(f"**状态**: 正常")
    lines.append(f"**可用**: {'是' if result.is_available else '否'}")
    lines.append("")

    if result.balances:
        lines.append("## 余额明细")
        for b in result.balances:
            symbol = "¥" if b.currency == "CNY" else "$"
            lines.append(f"### {b.currency}")
            lines.append(f"- **总余额**: {symbol}{b.total_balance}")
            lines.append(f"- **赠送余额**: {symbol}{b.granted_balance}")
            lines.append(f"- **充值余额**: {symbol}{b.topped_up_balance}")
            lines.append("")
    else:
        lines.append("**余额信息**: 无数据")

    return "\n".join(lines)


@mcp.tool(
    name="check_account_balance",
    annotations={
        "title": "查询已配置账户的余额",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def check_account_balance(params: CheckAccountBalanceInput) -> str:
    """通过账户 UID 查询已配置账户的余额。

    使用 list_accounts 获取账户 UID，然后用此工具查询余额。

    Args:
        params: 包含 uid 的输入参数

    Returns:
        Markdown 格式的余额信息。
    """
    config = load_config()
    account = None
    for acc in config.accounts:
        if acc.uid == params.uid:
            account = acc
            break

    if not account:
        return f"错误：未找到 UID 为 `{params.uid}` 的账户。使用 list_accounts 查看所有账户。"

    provider = get_provider(account.provider)
    result = provider.check_balance(account.api_key)

    lines = [f"# {account.label} 余额查询结果", ""]
    lines.append(f"**Provider**: {provider.label}")
    lines.append(f"**UID**: `{account.uid}`")
    lines.append("")

    if result.status == BalanceStatus.ERROR:
        lines.append(f"**状态**: 错误")
        lines.append(f"**错误信息**: {result.error_message}")
        return "\n".join(lines)

    lines.append(f"**状态**: 正常")
    lines.append(f"**可用**: {'是' if result.is_available else '否'}")
    lines.append("")

    if result.balances:
        lines.append("## 余额明细")
        for b in result.balances:
            symbol = "¥" if b.currency == "CNY" else "$"
            lines.append(f"### {b.currency}")
            lines.append(f"- **总余额**: {symbol}{b.total_balance}")
            lines.append(f"- **赠送余额**: {symbol}{b.granted_balance}")
            lines.append(f"- **充值余额**: {symbol}{b.topped_up_balance}")
            lines.append("")

    return "\n".join(lines)


@mcp.tool(
    name="check_all_balances",
    annotations={
        "title": "查询所有账户余额",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
)
async def check_all_balances() -> str:
    """批量查询所有已配置账户的余额。

    Returns:
        Markdown 格式的所有账户余额汇总。
    """
    config = load_config()
    if not config.accounts:
        return "暂无配置的账户。使用 add_account 工具添加新账户。"

    lines = ["# 所有账户余额汇总", ""]
    total_cny = 0.0
    total_usd = 0.0

    for acc in config.accounts:
        provider = get_provider(acc.provider)
        result = provider.check_balance(acc.api_key)

        lines.append(f"## {acc.label} ({provider.label})")
        lines.append(f"**UID**: `{acc.uid}`")

        if result.status == BalanceStatus.ERROR:
            lines.append(f"**状态**: 错误 - {result.error_message}")
        else:
            lines.append(f"**状态**: {'可用' if result.is_available else '不可用'}")
            for b in result.balances:
                symbol = "¥" if b.currency == "CNY" else "$"
                lines.append(f"- **{b.currency}**: {symbol}{b.total_balance}")
                try:
                    val = float(b.total_balance)
                    if b.currency == "CNY":
                        total_cny += val
                    else:
                        total_usd += val
                except (ValueError, TypeError):
                    pass
        lines.append("")

    lines.append("---")
    lines.append("## 汇总")
    lines.append(f"- **CNY 总计**: ¥{total_cny:.2f}")
    lines.append(f"- **USD 总计**: ${total_usd:.2f}")
    lines.append(f"- **账户数量**: {len(config.accounts)}")

    return "\n".join(lines)


@mcp.tool(
    name="add_account",
    annotations={
        "title": "添加新账户",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    }
)
async def add_account(params: AddAccountInput) -> str:
    """添加一个新的 API 账户到配置。

    Args:
        params: 包含 label、api_key 和 provider 的输入参数

    Returns:
        添加结果，包含新账户的 UID。
    """
    config = load_config()

    # 检查 API Key 是否已存在
    for acc in config.accounts:
        if acc.api_key == params.api_key:
            return f"错误：该 API Key 已存在于账户 `{acc.label}` (UID: `{acc.uid}`)"

    new_account = AccountConfig(
        label=params.label,
        api_key=params.api_key,
        provider=params.provider.value,
    )
    config.accounts.append(new_account)
    save_config(config)

    return f"账户添加成功！\n\n- **标签**: {params.label}\n- **UID**: `{new_account.uid}`\n- **Provider**: {params.provider.value}"


@mcp.tool(
    name="remove_account",
    annotations={
        "title": "删除账户",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
async def remove_account(params: RemoveAccountInput) -> str:
    """删除指定 UID 的账户。

    Args:
        params: 包含 uid 的输入参数

    Returns:
        删除结果。
    """
    config = load_config()
    original_count = len(config.accounts)
    config.accounts = [acc for acc in config.accounts if acc.uid != params.uid]

    if len(config.accounts) == original_count:
        return f"错误：未找到 UID 为 `{params.uid}` 的账户。"

    save_config(config)
    return f"账户 UID `{params.uid}` 已成功删除。"


if __name__ == "__main__":
    mcp.run()
