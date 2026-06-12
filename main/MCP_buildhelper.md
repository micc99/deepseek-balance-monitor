# DeepSeek Balance Monitor - MCP 服务器构建记录

## 概述

本文档记录了将 DeepSeek Balance Monitor Python 脚本转换为 MCP (Model Context Protocol) 服务器的完整过程。

**项目路径**: `D:\#MCP-Serve\deepseek-balance-monitor\main`  
**创建时间**: 2025-06-12  
**MCP 服务器文件**: `mcp_server.py`

---

## 1. 项目分析

### 1.1 原有项目结构

```
main/
├── balance_checker.py    # 核心：多 Provider 余额查询抽象层
├── config.py             # 配置管理：加载/保存 config.json
├── config.json           # 账户配置：API Key、Provider 类型
├── main.py               # GUI 入口（PyQt/customtkinter）
├── main_window.py        # 主窗口
├── floating_window.py    # 悬浮窗
├── scheduler.py          # 定时任务
├── usage_logger.py       # 用量记录
└── ...其他 GUI 相关文件
```

### 1.2 核心功能识别

通过阅读 `balance_checker.py`，识别出以下核心功能：

1. **Provider 抽象层**: `BaseProvider` 基类，各 Provider 实现 `_parse_response`
2. **支持的 Provider**:
   - `deepseek` - 深度求索官方
   - `siliconflow` - 硅基流动
   - `moonshot` - 月之暗面 Kimi
   - `openrouter` - OpenRouter
   - `zhipu` - 智谱AI (GLM)
3. **统一返回格式**: `BalanceInfo` 数据类，包含 `CurrencyBalance` 列表
4. **Provider 注册表**: `PROVIDERS` 字典，通过 `get_provider()` 访问

### 1.3 配置管理

`config.py` 提供：
- `load_config()` - 加载配置
- `save_config()` - 保存配置
- `AccountConfig` - 账户数据类（label, api_key, provider, uid）
- `mask_api_key()` - API Key 脱敏

---

## 2. MCP 服务器设计

### 2.1 工具规划

| 工具名                | 功能        | 类型   | 注解                            |
| --------------------- | ----------- | ------ | ------------------------------- |
| `list_providers`        | 列出 Provider | 只读   | readOnlyHint: true              |
| `list_accounts`         | 列出账户    | 只读   | readOnlyHint: true              |
| `check_balance`         | 按 Key 查询 | 只读   | readOnlyHint, openWorldHint     |
| `check_account_balance` | 按 UID 查询 | 只读   | readOnlyHint, openWorldHint     |
| `check_all_balances`    | 批量查询    | 只读   | readOnlyHint, openWorldHint     |
| `add_account`           | 添加账户    | 写入   | destructiveHint: false          |
| `remove_account`        | 删除账户    | 破坏性 | destructiveHint: true           |

### 2.2 输入验证设计

使用 Pydantic BaseModel 定义输入参数：

```python
class ProviderName(str, Enum):
    DEEPSEEK = "deepseek"
    SILICONFLOW = "siliconflow"
    MOONSHOT = "moonshot"
    OPENROUTER = "openrouter"
    ZHIPU = "zhipu"

class CheckBalanceInput(BaseModel):
    api_key: str = Field(..., description="API Key", min_length=1)
    provider: ProviderName = Field(default=ProviderName.DEEPSEEK, description="Provider 类型")
```

---

## 3. 实现细节

### 3.1 创建的文件

**文件**: `mcp_server.py`  
**路径**: `D:\#MCP-Serve\deepseek-balance-monitor\main\mcp_server.py`

### 3.2 关键代码结构

#### 导入部分

```python
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
```

**说明**:
- `sys.path.insert(0, ...)` 确保能导入项目模块
- 从 `balance_checker` 导入 Provider 相关函数
- 从 `config` 导入配置管理函数

#### 服务器初始化

```python
mcp = FastMCP("deepseek_balance_monitor_mcp")
```

**命名规范**: 使用 `{service}_mcp` 格式（Python MCP 标准）

#### 工具注册示例

```python
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
    """查询指定 Provider 和 API Key 的余额。"""
    provider = get_provider(params.provider.value)
    result = provider.check_balance(params.api_key)
    
    # 构建 Markdown 格式响应
    lines = [f"# {provider.label} 余额查询结果", ""]
    if result.status == BalanceStatus.ERROR:
        lines.append(f"**状态**: 错误")
        lines.append(f"**错误信息**: {result.error_message}")
        return "\n".join(lines)
    
    # ... 格式化余额信息
```

**注解说明**:
- `readOnlyHint: True` - 只读操作，不修改系统状态
- `destructiveHint: False` - 非破坏性操作
- `idempotentHint: True` - 幂等操作，重复调用结果相同
- `openWorldHint: True` - 需要访问外部 API（DeepSeek 等）

### 3.3 复用的原有代码

直接复用了以下模块，无需修改：

1. **`balance_checker.py`** - 完整复用
   - `PROVIDERS` 字典
   - `get_provider()` 函数
   - `get_provider_list()` 函数
   - `BalanceStatus` 枚举

2. **`config.py`** - 完整复用
   - `load_config()` 函数
   - `save_config()` 函数
   - `AccountConfig` 数据类
   - `mask_api_key()` 函数

---

## 4. 依赖检查

### 4.1 已有依赖

项目 `requirements.txt` 包含：
```
customtkinter>=5.2.0
requests>=2.28.0
pystray>=0.19.0
Pillow>=9.0.0
matplotlib>=3.9.0
keyboard>=0.13.5
```

### 4.2 新增依赖

MCP 服务器需要额外安装：
```bash
pip install mcp pydantic
```

**已验证**: 系统中已安装 `mcp==1.27.0` 和 `pydantic==2.13.3`

---

## 5. 测试验证

### 5.1 导入测试

```bash
cd "D:\#MCP-Serve\deepseek-balance-monitor\main"
python -c "import asyncio; from mcp_server import mcp; print('OK')"
```

**结果**: `OK` - 导入成功

---

## 6. 配置使用

### 6.1 MiMoCode 配置

在 `mimocode.json` 的 `mcp` 部分添加：

```json
{
  "mcp": {
    "balance-monitor": {
      "command": ["python", "D:\\#MCP-Serve\\deepseek-balance-monitor\\main\\mcp_server.py"],
      "enabled": true,
      "type": "local"
    }
  }
}
```

### 6.2 使用示例

配置完成后，可通过以下方式使用：

1. **列出支持的 Provider**:
   ```
   调用 list_providers 工具
   ```

2. **查看所有账户余额**:
   ```
   调用 check_all_balances 工具
   ```

3. **查询特定账户**:
   ```
   调用 list_accounts 获取 UID
   调用 check_account_balance 查询指定 UID
   ```

---

## 7. 技术要点

### 7.1 FastMCP 框架

- 使用 `@mcp.tool` 装饰器注册工具
- Pydantic BaseModel 自动验证输入参数
- docstring 自动生成工具描述
- `annotations` 提供工具元数据

### 7.2 响应格式

所有工具返回 Markdown 格式字符串，便于人类阅读：
- 使用 `#` 标题层级
- 使用 `**粗体**` 强调关键信息
- 使用列表展示详细数据

### 7.3 错误处理

- API 请求错误：捕获 `requests` 异常，返回友好错误信息
- 配置错误：账户不存在时返回提示
- 输入验证：Pydantic 自动验证，返回清晰错误

---

## 8. 文件变更清单

| 操作   | 文件            | 说明                      |
| ------ | --------------- | ------------------------- |
| 新建   | `mcp_server.py`   | MCP 服务器主文件          |
| 新建   | `MCP_buildhelper.md` | 本文档                    |
| 未修改 | `balance_checker.py` | 核心逻辑，直接复用        |
| 未修改 | `config.py`         | 配置管理，直接复用        |
| 未修改 | `config.json`       | 账户配置，MCP 服务器读取  |

---

## 9. 后续扩展建议

1. **添加更多 Provider**: 继承 `BaseProvider`，实现 `_parse_response`，注册到 `PROVIDERS`
2. **用量历史查询**: 暴露 `usage_logger.py` 的查询功能
3. **定时监控**: 添加设置定时查询的工具
4. **告警阈值**: 添加余额低于阈值的告警配置

---

## 10. 参考资料

- **MCP Python SDK**: `mcp.server.fastmcp.FastMCP`
- **Pydantic v2**: `pydantic.BaseModel`, `pydantic.Field`
- **项目源码**: `balance_checker.py`, `config.py`
