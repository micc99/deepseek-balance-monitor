# DeepSeek 余额监控 · 改进设计方案

> **版本**：v1.5
> **日期**：2026-08-21
> **对象项目**：deepseek-balance-monitor（当前 v1.9.3）
> **覆盖范围**：全面体检式报告（安全 / 性能 / 架构 / 并发 / 错误处理 / 配置 / UX / 主题 / 测试 / 打包 / 新功能 / 技术栈演进）
> **深度**：方向 + 具体可执行清单（背景 → 问题 → 方案 → 步骤 → 影响面 → 优先级 → 风险）
> **语言**：简体中文（技术术语保留英文原文）
> **约束**：①放弃黑色主题，采用莫奈色系并保留主题扩展接口 ②闪电级启动 + 近乎 0 后台占用 ③允许重构与换技术栈（换栈需用户审批，本次仅方案不改动代码）
> **关联独立项目**：[dsh-balance-plugin_PRD_v1.0_2026-08-14.md](file:///d:/#MCP-Serve/deepseek-balance-monitor/dsh-balance-plugin_PRD_v1.0_2026-08-14.md) / [dsh-balance-plugin_issues_v1.0_2026-08-14.md](file:///d:/#MCP-Serve/deepseek-balance-monitor/dsh-balance-plugin_issues_v1.0_2026-08-14.md)（DSH 插件线，独立文档体系维护，与桌面应用无依赖）
> **v1.5 变更说明**：
> - **DSH 插件线拆分至独立文档体系**（用户决策）：v1.4 草案中新增的 11.3 F-5（DeepSeek Harness 余额插件）与第 14 章 M6（v1.13.0）里程碑排期整体迁移至 dsh-balance-plugin 独立文档体系（PRD + Issue 清单）维护
> - 拆分原因：DSH 插件为独立 TypeScript（Cordis）项目，与桌面应用无代码依赖、无交付依赖，独立文档体系便于并行推进与维护
> - 连锁调整：移除总览矩阵 F-5 行、附录 A F-5 行及 M6 排期章节
> - 改进项总数恢复为 36 项（与 v1.3 一致）
> - v1.3 的 S-4 移除变更保留
> **v1.3 变更说明**：
> - 基于用户决策移除以下改进项（功能整体删除，不再保留）：
>   - S-4 移除第三方凭证静默读取（用户决策：仅使用 config.json 中的账户配置查询余额，无需第三方凭证源管理功能）
> - 相关连锁调整：FR-SEC-05 / ISSUE-SEC-05 功能移除；`credential_sources.py`、`active_key_sources` 字段、`settings_dialog` 凭证源 UI 均已删除
> - 改进项总数由 37 项减少至 36 项
> - S-4 原方案保留作为历史记录，仅标注移除状态
> **v1.2 变更说明**：
> - 基于用户决策删除以下改进项（用户无对应需求）：
>   - A-3 / D-1 配置 schema + 版本 + 迁移（用户不引入 pydantic 迁移机制，配置保留 dataclass）
>   - D-2 多 Provider 代理路由（用户无本地代理多路由需求，维持单 Provider 代理）
>   - U-3 系统通知（用户不需要系统通知）
>   - U-5 可访问性（用户不考虑视障人士支持）
>   - R-2 自动更新（用户不考虑自动更新，均为手动更新）
>   - F-1 阈值告警（用户不做告警）
>   - F-2 用量预算（用户不做超额告警）
> - 相关连锁调整：FR-SEC-01/05、FR-THM-02、FR-CFG-02 依赖去除（不再依赖 schema 升级）
> - 改进项总数由 45 项减少至 37 项
> - v1.1 的移除 MCP Server 功能变更保留

---

## 目录

- [第 0 章 前言与方法论](#第-0-章-前言与方法论)
- [第 1 章 安全与凭证管理](#第-1-章-安全与凭证管理)
- [第 2 章 性能：闪电启动 + 近零占用](#第-2-章-性能闪电启动--近零占用)
- [第 3 章 架构与代码组织](#第-3-章-架构与代码组织)
- [第 4 章 并发与网络](#第-4-章-并发与网络)
- [第 5 章 错误处理与日志体系](#第-5-章-错误处理与日志体系)
- [第 6 章 配置与数据模型](#第-6-章-配置与数据模型)
- [第 7 章 UI/UX](#第-7-章-uiux)
- [第 8 章 主题色改造（莫奈色系 + 扩展接口 + 编辑器）](#第-8-章-主题色改造莫奈色系--扩展接口--编辑器)
- [第 9 章 测试与质量保障](#第-9-章-测试与质量保障)
- [第 10 章 打包与分发](#第-10-章-打包与分发)
- [第 11 章 新功能建议](#第-11-章-新功能建议)
- [第 12 章 技术栈演进（P3，需用户审批）](#第-12-章-技术栈演进p3需用户审批)
- [第 13 章 跨维度协同改进路线图](#第-13-章-跨维度协同改进路线图)
- [第 14 章 里程碑排期建议](#第-14-章-里程碑排期建议)
- [附录 A 改进项汇总表](#附录-a-改进项汇总表)
- [附录 B 风险登记册](#附录-b-风险登记册)

---

## 第 0 章 前言与方法论

### 0.1 项目画像

| 项 | 内容 |
|----|------|
| 版本 | v1.9.3 |
| 语言 | Python 3.10+ |
| UI 框架 | customtkinter（基于 Tkinter） |
| 系统集成 | pystray（托盘）、keyboard（全局热键） |
| 网络 | requests、http.client（usage_proxy） |
| 持久化 | SQLite（usage.db）、JSON（config.json） |
| 可视化 | matplotlib |
| 形态 | Windows 桌面单进程：主窗口 + 悬浮窗 + 系统托盘 + 本地反向代理（用量统计） |
| 规模 | 约 20 个源文件 |
| 分层 | UI 层 / 调度层 / Provider 层 / 数据层 / 工具层 |

### 0.2 体检方法论

- **静态维度**：通读全部源码与测试，识别代码异味、安全隐患、架构耦合
- **动态维度**：基于 [main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) 启动流程与 [scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) 调度模型，分析启动耗时与后台占用来源
- **约束对齐**：每项改进标注是否服务"闪电启动 / 近零占用 / 莫奈主题 / 跨平台 / 安全"等用户核心约束

### 0.3 优先级定义

| 级别 | 含义 | 触发条件 |
|------|------|----------|
| **P0** | 紧急修复 | 安全漏洞、数据丢失风险、崩溃 |
| **P1** | 重要改进 | 架构债务、性能瓶颈、稳定性问题 |
| **P2** | 体验优化 | UX、主题、国际化 |
| **P3** | 长期演进 | 技术栈迁移、重大新功能 |

### 0.4 改进总览矩阵

| 章 | 主题 | P0 | P1 | P2 | P3 | 合计 |
|----|------|----|----|----|----|------|
| 1 | 安全与凭证 | 2 | 1 | 0 | 0 | 3 |
| 2 | 性能 | 0 | 6 | 1 | 0 | 7 |
| 3 | 架构 | 0 | 4 | 0 | 0 | 4 |
| 4 | 并发与网络 | 0 | 4 | 0 | 0 | 4 |
| 5 | 错误处理与日志 | 0 | 3 | 0 | 0 | 3 |
| 6 | 配置与数据模型 | 0 | 0 | 1 | 0 | 1 |
| 7 | UI/UX | 0 | 0 | 4 | 0 | 4 |
| 8 | 主题色改造 | 0 | 0 | 3 | 0 | 3 |
| 9 | 测试与质量保障 | 0 | 2 | 1 | 0 | 3 |
| 10 | 打包与分发 | 0 | 1 | 0 | 0 | 1 |
| 11 | 新功能建议 | 0 | 0 | 0 | 2 | 2 |
| 12 | 技术栈演进 | 0 | 0 | 0 | 1 | 1 |
| — | **合计** | **2** | **21** | **10** | **3** | **36** |

> 矩阵合计 36 项。v1.3 移除 S-4（移除第三方凭证静默读取）较 v1.2 减少 1 项；v1.2 删除 A-3/D-1（配置 schema）、D-2（多 Provider 代理）、U-3（系统通知）、U-5（可访问性）、R-2（自动更新）、F-1（阈值告警）、F-2（用量预算）共 8 项后较 v1.1 减少 8 项。

---

## 第 1 章 安全与凭证管理

### 现状分析

项目处理高敏感数据（API Key），但当前安全基线薄弱：

- [config.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/config.py) 第 70-76 行：`save_config` 将 API Key 以**明文**写入 `config.json`
- [usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) 第 33、74 行：代理在内存中拼接完整流式响应文本用于提取 usage，存在日志/内存泄露风险
- [main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) 第 99-119 行 `_load_active_keys`：读取 `Desktop\auth.json`、`opencode\auth.json` 等第三方凭证文件 ~~**【已移除（v1.3）】** 此问题已通过整体移除凭证源管理功能解决，应用不再读取任何第三方凭证文件~~
- [usage_history.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_history.py) 第 47-49 行：使用 MD5 作为 API Key 指纹（弱哈希）

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| S-1 | API Key 明文存储于 config.json | P0 |
| S-3 | usage_proxy 监听 127.0.0.1 但无鉴权，本机任意进程可借用代理或注入请求 | P0 |
| S-4 | _load_active_keys 静默读取第三方凭证文件，隐私与合规风险 | P0（已移除，功能整体删除） |
| S-5 | MD5 作为 key hash（虽仅去标识，但应升级） | P1 |

### 改进建议

#### 1.1 【S-1, P0】API Key 加密存储

**背景**：config.json 与用户配置同目录，明文 Key 一旦泄露（备份、共享、误传）直接造成账户被盗用。

**方案**：采用 Windows DPAPI（数据保护 API）加密，密钥与当前 Windows 用户绑定。

**实施步骤**：
1. 新增 `credential_store.py`，封装 `encrypt(plaintext) -> bytes` / `decrypt(blob) -> str`，底层调用 `ctypes.windll.crypt32.CryptProtectData` / `CryptUnprotectData`
2. `AccountConfig` 新增 `api_key_enc: str`（base64 存储），`api_key` 改为运行时解密的 `@property`
3. `save_config` 仅写 `api_key_enc`，不再写明文
4. 启动时一次性解密所有 Key 并缓存到内存（受进程生命周期保护）
5. 跨平台回退：非 Windows 使用 [keyring](https://pypi.org/project/keyring/) 库（macOS Keychain / Linux Secret Service）

> **v1.2 调整**：原方案步骤 5"提供迁移逻辑：检测到旧版明文 api_key 字段时自动加密并升级 config"已删除（用户不需要自动迁移功能）。改为：启动时检测到明文 `api_key` 字段时弹窗提示用户重新输入 Key，不做自动加密迁移。

**影响面**：config.py、AccountConfig、所有读取 api_key 的调用点（balance_checker、usage_proxy、main._record_balance_snapshot）

**风险**：DPAPI 与用户绑定，换用户账户需重新输入 Key（可接受）

#### 1.2 【S-3, P0】usage_proxy 鉴权与加固

**背景**：代理监听 127.0.0.1:52848，本机任意进程可借用代理（消耗用户额度）或注入伪造请求。

**方案**：代理协议校验 + 请求白名单。

**实施步骤**：
1. 代理要求请求头携带 `X-Proxy-Token`（独立 token，首次启动生成随机 32 字节，DPAPI 加密存储）
2. 校验失败返回 403
3. 流式响应改为**边转发边解析**（行级状态机），不再 accumulate 整段 `usage_text`，降低内存与日志泄露面
4. 限制 `target_host` 为白名单（5 个 Provider 域名），拒绝任意转发
5. 记录审计日志（脱敏后的 key hash + 请求路径 + 时间），不记录请求/响应体

**影响面**：usage_proxy.py、main.py（代理启动传 token）、config.py（proxy_token_enc 字段）、客户端配置需添加 token

**风险**：现有客户端需更新 base URL 头；白名单可能阻碍自定义 Provider

#### 1.3 【S-4, P0】移除或显式化第三方凭证读取 ｜ 已移除

> **状态变更（2026-08-07）**：本改进项已整体移除。用户决策：仅使用 config.json 中的账户配置查询余额，无需第三方凭证源管理功能。下方方案保留作为历史记录。

**背景**：`_load_active_keys` 静默读取 Desktop 与 opencode 的 auth.json，用户无感知，且 Desktop 路径存在注入风险。

**方案**（历史方案）：改为显式授权机制。

**实施步骤**：
1. 移除默认路径扫描
2. 在设置面板新增"导入凭证源"功能，用户主动选择 auth.json 文件路径
3. 选择后弹窗告知"将读取该文件的 key 字段用于活跃标识"，用户确认后记录路径到 config
4. 后续仅读取用户授权的路径

**影响面**：main.py、settings_dialog.py、config.py（新增 `active_key_sources` 字段）

**风险**：现有依赖该自动行为的用户需手动配置一次

#### 1.4 【S-5, P1】API Key 指纹算法升级

**背景**：MD5 虽仅用于去标识，但碰撞风险与"使用弱哈希"的合规污点存在。

**方案**：升级为 SHA-256 截断前 32 字符，并保留迁移映射表。

**实施步骤**：
1. `usage_history._hash_key` 改用 `hashlib.sha256(...).hexdigest()[:32]`
2. 新增 `migrate_hash` 脚本：遍历 `token_usage` 与 `balance_snapshots`，对历史数据用 MD5 反查原 key（需用户提供 key 列表）重算 SHA-256；或标记旧数据为 `legacy` 不影响新数据
3. 双写一段时间（同时存 MD5 与 SHA-256）保证平滑过渡

**影响面**：usage_history.py、main.py（_record_balance_snapshot）、usage_logger.py

**风险**：历史数据归并复杂，可接受"新数据用新算法，旧数据保留"

---

## 第 2 章 性能：闪电启动 + 近零占用

> **本章为用户核心约束重点章**。目标：冷启动 < 300ms、闲置内存 < 50MB、闲置 CPU < 0.1%。

### 现状分析

**启动耗时来源**（[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py)）：
- 顶部一次性 `import customtkinter`、`keyboard`、`matplotlib`（间接，经 usage_curve_window）
- `App.__init__` 同步：`load_config`、`_load_active_keys`（磁盘 IO）、`UsageHistory()`（SQLite 建表）、`UsageProxy.start()`
- `run()` 同步创建 `MainWindow`（CTk 初始化 + UI 构建）
- 100ms 后 `_deferred_init` 起后台线程，500ms 后启动焦点监视

**后台占用来源**：
- [scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) 第 90-100 行：`_check_all` 每账户新建一个线程，账户多时线程爆炸
- [main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 第 81-107 行 `_focus_check_loop`：500ms 一次 `focus_get` 轮询，持续唤醒主循环
- [usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) 第 66-74 行：流式响应 accumulate 整段 `usage_text`，大响应内存峰值高
- [balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 第 80 行：每次请求新建 `requests.Session`，连接未复用
- [usage_history.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_history.py) 第 67-70 行：每次操作新建 SQLite 连接，无连接池

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| P-1 | 启动期同步 import matplotlib，拖慢首屏 | P1 |
| P-2 | App.__init__ 同步执行磁盘 IO 与 SQLite 建表 | P1 |
| P-3 | scheduler 每账户新建线程，无连接池 | P1 |
| P-4 | _focus_check_loop 500ms 轮询，持续唤醒 | P1 |
| P-5 | usage_proxy 流式 accumulate 全响应 | P1 |
| P-6 | balance_checker 每次新建 Session | P1 |
| P-7 | UsageHistory 无连接复用 | P2 |

### 改进建议

#### 2.1 【P-1, P1】matplotlib 延迟加载

**背景**：matplotlib 首次 import 可达 200-500ms，但仅余额曲线窗口需要。

**方案**：将 matplotlib import 下沉到窗口构造函数内部。

**实施步骤**：
1. [usage_curve_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_curve_window.py) 与 [usage_bar_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_bar_window.py) 顶部移除 `import matplotlib`
2. 在 `__init__` 或首次绘图方法内 `import matplotlib.pyplot as plt`（局部 import）
3. 进一步可选：迁移到 `pyqtgraph`（参见第 12 章技术栈演进），启动更快

**影响面**：usage_curve_window.py、usage_bar_window.py

**风险**：首次打开曲线窗口有 ~300ms 延迟（可接受，且可加 loading 提示）

#### 2.2 【P-2, P1】启动期 IO 与建表异步化

**背景**：`load_config`、`_load_active_keys`、`UsageHistory._init_db` 均为磁盘 IO，阻塞主线程首屏。

**方案**：首屏 UI 先用空配置渲染，后台线程加载真实数据后回填。

**实施步骤**：
1. `App.__init__` 仅创建 `MainWindow`（空账户列表），不调用 `load_config` 的 IO 部分（或改为内存默认值）
2. 后台线程执行：`load_config` → `_load_active_keys` → `UsageHistory._init_db` → `UsageProxy.start`
3. 加载完成后通过 `main_window.after(0, ...)` 回填账户列表并触发首次刷新
4. `_deferred_init` 已有此思路，需把更多初始化移入

**影响面**：main.py、main_window.py（需支持空状态 → 数据回填）

**风险**：首屏 200-400ms 内无数据，需 UI 空状态友好提示

#### 2.3 【P-3, P1】scheduler 改用线程池 + 连接复用

**背景**：当前每账户每轮新建线程，10 账户即 10 线程，开销大且无并发上限。

**方案**：`ThreadPoolExecutor(max_workers=4)` 复用线程；Provider 持有长连接 `requests.Session`。

**实施步骤**：
1. `BalanceScheduler.__init__` 创建 `ThreadPoolExecutor(max_workers=4, thread_name_prefix="balance-check")`
2. `_check_all` 改为 `executor.map(self._do_check, accounts)`
3. `BaseProvider` 持有 `self._session = requests.Session()`，`_make_request` 复用之
4. 每个 Provider 实例独立 Session（按域名隔离连接池）
5. 关闭时 `executor.shutdown(wait=True)` + `session.close()`

**影响面**：scheduler.py、balance_checker.py

**风险**：需注意 Session 线程安全（requests.Session 在多线程下需配合锁或每线程独立）；可改用 `httpx.Client` 异步更优

#### 2.4 【P-4, P1】焦点监视改为事件驱动

**背景**：500ms 轮询 `focus_get` 持续唤醒主循环，违背"近零占用"。

**方案**：改用 Tkinter 的 `<FocusOut>` / `<FocusIn>` 事件 + 短延时确认。

**实施步骤**：
1. `MainWindow` 绑定 `bind_all("<FocusOut>", ...)` 与 `bind_all("<FocusIn>", ...)`
2. 收到 `FocusOut` 后起 300ms `after` 计时器，期间若收到 `FocusIn` 则取消
3. 计时器触发后再校验是否存在子对话框，无则切悬浮窗
4. 移除 `_focus_check_loop` 轮询

**影响面**：main_window.py

**风险**：Tkinter 的 FocusOut 在某些场景误报（如菜单弹出），需用延时+二次校验兜底

#### 2.5 【P-5, P1】usage_proxy 流式行级解析

**背景**：当前 `usage_text += chunk.decode(...)` 累积整段响应，长响应内存峰值高且延迟高。

**方案**：行级状态机，边转发边解析 SSE。

**实施步骤**：
1. 维护 `line_buffer: str`
2. 每个 chunk 写入客户端后，append 到 `line_buffer`，按 `\n` 分割
3. 对完整行检查 `data: ` 前缀与 `usage` 关键字，命中即解析并 `log_usage`，然后清空 buffer 中已处理部分
4. 不再保存完整 `usage_text`

**影响面**：usage_proxy.py

**风险**：跨 chunk 的 SSE 行需正确拼接（行级 buffer 已处理）

#### 2.6 【P-6, P1】balance_checker Session 复用

**方案**：见 2.3，Provider 持有长连接 Session。

#### 2.7 【P-7, P2】UsageHistory 连接复用 + WAL 模式

**背景**：每次查询新建 SQLite 连接，且默认日志模式写入慢。

**方案**：单连接 + WAL + 连接级线程安全。

**实施步骤**：
1. `UsageHistory.__init__` 创建单例 `sqlite3.connect(check_same_thread=False)`，开启 `PRAGMA journal_mode=WAL`、`PRAGMA synchronous=NORMAL`
2. 所有方法共用此连接，加 `threading.Lock` 保护写操作
3. 关闭时 `conn.close()`

**影响面**：usage_history.py

**风险**：单连接 + 锁在并发写时可能成瓶颈，但本应用写频率低（每 60s 一次快照），可接受

#### 2.8 性能基准测试方法

为保证"闪电启动 + 近零占用"可量化验证，建立基准：

**指标**：
- 冷启动时间（双击 exe 到首屏可交互）
- 热启动时间（已缓存状态）
- 闲置内存（5 分钟无操作后）
- 闲置 CPU（5 分钟平均）
- 单次刷新延迟（10 账户）

**工具**：
- 启动：`python -X importtime main.py` 分析 import 耗时
- 内存/CPU：`psutil` 定期采样写入日志
- 刷新延迟：scheduler 内埋点

**门禁**：CI 中运行基准测试，回归 > 10% 则告警（参见第 9 章）

---

## 第 3 章 架构与代码组织

### 现状分析

- [main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) `App` 类职责过重：单实例锁 + IPC + 托盘 + 全局热键 + 主题 + 自启 + 悬浮窗管理 + 余额快照记录（第 252-271 行）
- [main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 使用 `set_refresh_callback` / `set_settings_callback` 等 6 个 setter 注入回调，耦合度高，扩展时需改两处
- [balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 第 181、226 行用 `total.replace(".","").isdigit()` 判断数字，脆弱（负数、科学计数法、千分位均误判）
- [main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) 第 63-73 行 `_create_shortcut` 拼接 PowerShell 脚本，路径含单引号时存在注入风险

> **v1.2 调整**：删除原问题 A-3"config 无 schema/版本/迁移"（用户不引入 pydantic 迁移机制，配置保留 dataclass 方式）。

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| A-1 | App 类职责过重（编排 + 多个基础设施职责） | P1 |
| A-2 | MainWindow 回调注入式耦合 | P1 |
| A-4 | balance_checker 数字判断脆弱 | P1 |
| A-5 | _create_shortcut PowerShell 拼接注入风险 | P1 |

### 改进建议

#### 3.1 【A-1, P1】App 类拆分

**方案**：将 `App` 拆为编排器 + 多个职责单一的管理器。

**目标结构**：

```
App（编排器，仅负责生命周期与协作）
├── LifecycleManager    单实例锁 + IPC
├── TrayManager         系统托盘
├── HotkeyManager       全局热键
├── ThemeManager        主题（含莫奈色扩展，见第 8 章）
├── AutostartManager    开机自启
├── WindowManager       主窗口 ↔ 悬浮窗切换
├── SchedulerManager    调度器封装 + 余额快照记录
└── ProxyManager        usage_proxy 封装
```

**实施步骤**：
1. 先用"抽取类 + 委托"重构，保持 App 接口不变
2. 每个管理器独立可测试（构造函数注入依赖）
3. App 仅负责实例化与连接

**影响面**：main.py 拆分为多个文件

**风险**：重构面广，需配套测试覆盖

#### 3.2 【A-2, P1】MainWindow 改用事件总线或信号

**方案**：引入轻量事件总线（pub/sub），替代 6 个 setter。

**实施步骤**：
1. 新增 `event_bus.py`，提供 `subscribe(event, handler)` / `publish(event, payload)`
2. 定义事件：`refresh_requested`、`settings_changed`、`account_added`、`balance_updated`、`theme_changed`、`provider_registered` 等
3. MainWindow 仅 `publish`，App/调度器/配置层 `subscribe`
4. 移除 `set_*_callback` 系列

**影响面**：main_window.py、main.py、settings_dialog.py

**风险**：事件总线调试稍复杂，需加日志追踪

#### 3.3 【A-4, P1】balance_checker 数字判断健壮化

**方案**：统一用 `try/except float()` + 正则兜底。

**实施步骤**：
1. 新增工具函数 `safe_float(s, default=0.0) -> float`
2. 替换所有 `.replace(".","").isdigit()` 判断
3. `is_available` 改为 `safe_float(total) > 0`

**影响面**：balance_checker.py

**风险**：低

#### 3.4 【A-5, P1】_create_shortcut 改用 COM API 或参数化

**方案**：改用 `win32com.client.ShellLink` 或 PowerShell 参数化调用（不拼接字符串）。

**实施步骤**：
1. 优先用 `pywin32` 的 `ShellLink` 对象（如已依赖则直接用，否则加可选依赖）
2. 回退方案：PowerShell 调用改为 `-ArgumentList` 参数化，禁止字符串插值
3. 路径校验：仅允许绝对路径且不含 `;` `|` 等特殊字符

**影响面**：main.py

**风险**：pywin32 增加依赖体积，可接受（Windows 平台）

---

## 第 4 章 并发与网络

### 现状分析

- [scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) 第 90-100 行：`_check_all` 每账户新建线程，无并发上限，无重试
- [scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) 第 99-100 行：`t.join(timeout=15)` 超时后线程仍在后台运行，长期累积可能"僵尸线程"
- [usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) 第 157 行：`HTTPServer` 单线程，并发请求排队
- [balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 第 103-108 行：仅捕获超时与连接错误，无重试，无退避

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| C-1 | scheduler 无线程池上限 | P1 |
| C-2 | join 超时后线程未真正取消 | P1 |
| C-3 | usage_proxy 单线程瓶颈 | P1 |
| C-4 | balance_checker 无重试与退避 | P1 |

### 改进建议

#### 4.1 【C-1, C-2, P1】scheduler 改 ThreadPoolExecutor + 任务取消

**方案**：见 2.3。补充：用 `Future` 支持取消，超时后 `future.cancel()`（仅未启动的可取消，运行中的依赖 Provider 端超时）。

**实施步骤**：
1. `_check_all` 提交所有 `Future`，`as_completed(futures, timeout=15)` 收集结果
2. 超时的 Future 调用 `cancel()`，记录警告日志
3. Provider 端 `requests` 超时设为 10s（已有），确保单任务不无限挂起

**影响面**：scheduler.py

**风险**：运行中的请求无法强制中断，依赖超时控制

#### 4.2 【C-3, P1】usage_proxy 改 ThreadingHTTPServer

**方案**：`HTTPServer` → `ThreadingHTTPServer`，每请求一线程（请求量低，可接受）。

**实施步骤**：
1. `usage_proxy.py` 第 157 行 `HTTPServer` 改为 `socketserver.ThreadingHTTPServer`
2. 设置 `daemon_threads = True`
3. 配合连接池（Provider 端 Session 复用）降低开销

**影响面**：usage_proxy.py

**风险**：多线程并发写 SQLite，需配合 2.7 的连接锁

#### 4.3 【C-4, P1】balance_checker 重试与退避

**方案**：对网络错误（超时、5xx）指数退避重试，最多 3 次。

**实施步骤**：
1. 引入 `tenacity` 库或自实现重试装饰器
2. 对 `requests.exceptions.Timeout`、`ConnectionError`、`5xx` 状态码重试
3. 退避：1s → 2s → 4s
4. 4xx（含 401/403）不重试
5. 重试耗尽后返回 `BalanceStatus.ERROR`

**影响面**：balance_checker.py

**风险**：重试会增加单次刷新延迟，需在 UI 显示"重试中"状态

---

## 第 5 章 错误处理与日志体系

### 现状分析

- [error_logger.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/error_logger.py) 第 26-44 行：每次异常创建独立 `.log` 文件，文件数无上限，长期运行后 `log/` 目录膨胀
- 无日志分级（DEBUG/INFO/WARN/ERROR）
- 无日志轮转与清理
- [main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) 第 453 行 `os._exit(0)` 强制退出，跳过资源清理与 atexit 钩子

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| E-1 | 每异常一文件，无上限无轮转 | P1 |
| E-2 | 无日志分级与统一 logger | P1 |
| E-3 | os._exit 强制退出跳过清理 | P1 |

### 改进建议

#### 5.1 【E-1, E-2, P1】统一 logging + RotatingFileHandler

**方案**：改用 Python 标准 `logging` + `RotatingFileHandler`。

**实施步骤**：
1. 新增 `log_setup.py`，配置根 logger：
   - `RotatingFileHandler` 单文件 `app.log`，maxBytes=2MB，backupCount=5
   - 格式：`%(asctime)s | %(levelname)s | %(name)s | %(message)s`
   - 分级：DEBUG（文件）/ INFO（控制台，开发时）
2. `error_logger.log_exception` 改为 `logger.exception("source=%s", source, exc_info=exc)`
3. 全项目改用 `logging.getLogger(__name__)`
4. 保留 `log_exception(source, exc)` 兼容签名，内部转 logging

**影响面**：error_logger.py、所有调用 log_exception 处

**风险**：旧 `log/` 目录需手动清理或迁移脚本

#### 5.2 【E-3, P1】移除 os._exit，改优雅退出

**方案**：用 `sys.exit(0)` + atexit 钩子。

**实施步骤**：
1. `App._quit` 末尾 `os._exit(0)` → `sys.exit(0)`
2. 资源清理（scheduler.stop、proxy.stop、tray.stop、keyboard.unhook_all）放在 `atexit.register` 或 try/finally
3. 主循环退出后自然返回 `main()`
4. 若遇 tkinter 死锁，提供 `--force-exit` 命令行开关回退到 `os._exit`

**影响面**：main.py

**风险**：tkinter mainloop 退出后某些资源可能已释放，需测试顺序

---

## 第 6 章 配置与数据模型

### 现状分析

- [config.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/config.py) `SettingsConfig` 仅 5 个字段，扩展新设置需改 dataclass + load + save 三处
- 无配置备份，save 失败时旧配置丢失

> **v1.2 调整**：删除原问题 D-1"配置无 schema/版本/迁移"（同 A-3，用户不引入 pydantic）与 D-2"proxy_target 单值限制"（用户无多 Provider 代理需求）。配置保留 dataclass 方式，新增字段直接添加到 dataclass。

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| D-3 | save 无备份与原子性 | P2 |

### 改进建议

#### 6.1 【D-3, P2】配置原子写入 + 备份

**方案**：写临时文件 + rename + 保留最近 3 份备份。

**实施步骤**：
1. `save_config`：写 `config.json.tmp` → `os.replace(tmp, config.json)`（原子）
2. 写入前若旧文件存在，复制到 `config.json.bak.{n}`，滚动保留 3 份
3. 读取失败时自动回退到最近备份

**影响面**：config.py

**风险**：低

---

## 第 7 章 UI/UX

### 现状分析

- 全中文硬编码，无 i18n
- 快捷键硬编码（`Ctrl+R`、`Ctrl+Shift+B`）
- [main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 焦点丢失自动切悬浮窗，可能干扰用户工作
- 主题硬编码颜色（与第 8 章耦合）

> **v1.2 调整**：删除原问题 U-3"无系统通知"（用户不需要系统通知）与 U-5"无可访问性支持"（用户不考虑视障人士支持）。

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| U-1 | 无 i18n 国际化 | P2 |
| U-2 | 快捷键硬编码不可配置 | P2 |
| U-4 | 焦点丢失自动切悬浮窗易误触 | P2 |
| U-6 | 主题硬编码颜色（与第 8 章耦合） | P2 |

### 改进建议

#### 7.1 【U-1, P2】i18n 国际化

**方案**：引入 `gettext`，提取字符串到 `locales/`。

**实施步骤**：
1. 全项目字符串改用 `_("...")` 包裹
2. 生成 `locales/zh_CN/LC_MESSAGES/app.po`，后续可扩展 `en`
3. 设置面板增加语言切换（重启生效）

**影响面**：所有 UI 文件

**风险**：工作量中等，可分批迁移

#### 7.2 【U-2, P2】快捷键可配置

**方案**：设置面板新增"快捷键"配置区，存入 config。

**实施步骤**：
1. `SettingsConfig` 增加 `hotkeys: dict[str, str]`（action → keystr）
2. 默认值：`toggle_window: "ctrl+shift+b"`、`manual_refresh: "ctrl+r"`
3. 设置面板提供录入控件（捕获按键）
4. 启动时按配置注册

**影响面**：config.py、main.py、settings_dialog.py

**风险**：冲突检测（与系统/其他应用）

#### 7.3 【U-4, P2】焦点丢失行为可配置

**方案**：提供"失焦自动切悬浮窗"开关，默认关闭。

**实施步骤**：
1. `SettingsConfig` 增加 `auto_float_on_focus_loss: bool = False`
2. 设置面板提供开关
3. 默认关闭，改为手动最小化

**影响面**：main_window.py、config.py、settings_dialog.py

**风险**：改变现有用户习惯，需迁移说明

#### 7.4 【U-6, P2】颜色集中管理

见第 8 章主题系统。

---

## 第 8 章 主题色改造（莫奈色系 + 扩展接口 + 编辑器）

> **本章为用户核心约束重点章**。目标：放弃黑色主题，采用莫奈色系，保留主题扩展接口，支持主题编辑器。

### 8.1 现状分析

- customtkinter 仅支持 `dark` / `light` / `system` 三种内置主题
- 颜色硬编码：[floating_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/floating_window.py) 第 42-44 行 `fg_color=("gray95","gray17")`、[main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 第 310 行 `fg_color="#4a9eff"`
- 主题切换仅改 `ctk.set_appearance_mode`，无法自定义色板
- 用户明确要求放弃黑色主题

### 8.2 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| T-1 | 仅 dark/light 两主题，无法满足莫奈色需求 | P2 |
| T-2 | 颜色硬编码散落各处 | P2 |
| T-3 | 无主题扩展接口 | P2 |

### 8.3 主题抽象层设计

#### 8.3.1 架构

```
ThemeManager（单例，App 持有）
├── themes: dict[str, Theme]        已注册主题（含内置 + 用户自定义）
├── current: Theme                  当前生效主题
├── register(theme: Theme)          注册新主题
├── apply(name: str)                应用主题，广播 theme_changed 事件
└── export(path) / import(path)     主题导出/导入（编辑器用）
```

#### 8.3.2 Theme 数据模型

```python
class ThemeLayer(BaseModel):
    """单个语义层颜色，包含亮/暗两套（亮色背景仍可用莫奈浅色）。"""
    background: str       # 主背景
    surface: str          # 卡片/面板背景
    primary: str          # 主操作色（按钮）
    secondary: str        # 次要操作色
    accent: str           # 强调色（高亮、链接）
    text: str             # 主文本
    text_muted: str       # 次要文本
    border: str           # 边框
    success: str          # 成功状态
    warning: str          # 警告状态
    danger: str           # 危险状态

class Theme(BaseModel):
    """完整主题定义。"""
    name: str             # 唯一标识（如 "monet_water_lilies"）
    label: str            # 显示名（如 "莫奈·睡莲"）
    light: ThemeLayer     # 亮色变体
    dark: ThemeLayer      # 暗色变体（莫奈深色，非纯黑）
    ripple_color: str     # 波纹动画色
    description: str = "" # 主题描述
```

#### 8.3.3 主题注册接口

```python
# 内置主题在 themes/ 目录下以 JSON 定义
# themes/monet_water_lilies.json
# themes/monet_impression_sunrise.json
# themes/monet_haystacks.json
# themes/light_classic.json   （保留亮色，可选）

# ThemeManager 启动时扫描 themes/ + 用户目录 ~/.deepseek-monitor/themes/
# 注册顺序：内置 → 用户（同名覆盖）
```

#### 8.3.4 颜色应用机制

- 所有 UI 组件不再硬编码颜色，改用语义 token：`ThemeManager.current.surface` 等
- UI 组件订阅 `theme_changed` 事件，主题切换时重新 `configure(fg_color=...)`
- customtkinter 的 `set_appearance_mode` 仍用于控制亮/暗，但颜色由 ThemeLayer 提供

### 8.4 莫奈色系配色方案（首批 3 套）

#### 8.4.1 莫奈·睡莲（Water Lilies）— 主推

灵感：莫奈《睡莲》系列，柔和的蓝绿与紫粉。

| 语义 | 亮色 | 暗色 |
|------|------|------|
| background | #F5F0E8（米白） | #1A1F2E（深蓝灰，非纯黑） |
| surface | #FFFFFF | #242B3D |
| primary | #5B8AA6（睡莲蓝） | #7BA9C4 |
| secondary | #9CAF88（睡莲叶绿） | #B5C9A3 |
| accent | #C8A2C8（睡莲粉紫） | #D4B5D4 |
| text | #2C3E50 | #E8E4D9 |
| text_muted | #7F8C8D | #A8B0B5 |
| ripple_color | #5B8AA6 | #7BA9C4 |

#### 8.4.2 莫奈·日出印象（Impression, Sunrise）

灵感：莫奈《日出·印象》，橙蓝对比。

| 语义 | 亮色 | 暗色 |
|------|------|------|
| background | #FFF5EB | #1E1A14 |
| surface | #FFFFFF | #2A2419 |
| primary | #E07B39（日出橙） | #F09A5C |
| secondary | #4A6FA5（海面蓝） | #6B8DC4 |
| accent | #F2C849（晨光金） | #FFD96E |
| text | #3D2E1F | #F5E6D3 |
| ripple_color | #E07B39 | #F09A5C |

#### 8.4.3 莫奈·干草垛（Haystacks）

灵感：莫奈《干草垛》，暖金与紫影。

| 语义 | 亮色 | 暗色 |
|------|------|------|
| background | #FAF3E0 | #1F1A14 |
| surface | #FFFFFF | #2B2419 |
| primary | #C9A961（麦秆金） | #E0C481 |
| secondary | #8B7355（干草褐） | #A89279 |
| accent | #7B5E8C（阴影紫） | #9C7DB5 |
| text | #3D2E1F | #F0E4C9 |
| ripple_color | #C9A961 | #E0C481 |

### 8.5 迁移策略

> **v1.2 调整**：由于删除了配置 schema 版本与迁移机制（A-3/D-1），主题字段迁移改为运行时兼容读取。

1. **放弃纯黑 dark 主题，旧字段兼容映射**：v1.10 起不再使用 customtkinter 原生纯黑 dark 主题；`load_config` 读取时若发现旧 `theme: "dark"` / `"light"` 字段，运行时映射到"莫奈·睡莲（暗色变体）"与"莫奈·睡莲（亮色变体）"，确保老用户升级后无纯黑主题、但仍拥有亮/暗两套莫奈色
2. **新增 theme_name 字段**：`SettingsConfig` 新增 `theme_name: str = "monet_water_lilies"`，旧 `theme` 字段在读取时转换（不写入新字段，下次保存时自然替换）
3. **设置面板改造**：主题选择改为下拉列表 + 实时预览缩略色板
4. **README 更新**：展示新主题截图

### 8.6 主题编辑器

#### 8.6.1 功能

- 可视化编辑 ThemeLayer 的所有语义颜色
- 实时预览（小窗口展示按钮/文本/卡片样例）
- 亮/暗双套编辑
- 保存为用户主题（`~/.deepseek-monitor/themes/my_theme.json`）
- 导入/导出 `.json` 主题文件
- 重置为默认

#### 8.6.2 UI 布局

```
┌─────────────────────────────────────────┐
│ 主题编辑器                    [亮/暗切换]│
├──────────────┬──────────────────────────┤
│ 颜色矩阵     │ 预览面板                 │
│ background □ │ ┌──────────────────────┐ │
│ surface   □  │ │ [按钮] [按钮]        │ │
│ primary   □  │ │ 卡片示例文本         │ │
│ ...          │ │ ¥100.50              │ │
│              │ └──────────────────────┘ │
├──────────────┴──────────────────────────┤
│ [保存] [另存] [导出] [导入] [重置]      │
└─────────────────────────────────────────┘
```

#### 8.6.3 实施步骤

1. 新增 `theme_editor.py`，`ThemeEditorDialog`
2. 颜色选择用 `tkinter.colorchooser.askcolor`
3. 预览面板用 customtkinter 组件实时 `configure`
4. 保存写入用户主题目录，ThemeManager 重新扫描
5. 设置面板"主题"区增加"编辑当前主题"按钮入口

### 8.7 影响面

- 新增：`theme_manager.py`、`theme_editor.py`、`themes/*.json`
- 修改：所有 UI 文件（移除硬编码颜色）、config.py（theme_name 字段）、settings_dialog.py（主题选择 + 编辑入口）、main.py（ThemeManager 初始化）

### 8.8 风险

- customtkinter 对自定义颜色的支持边界需验证（部分组件颜色可能无法覆盖）
- 主题切换实时生效需处理已存在的 Toplevel 窗口
- 主题编辑器增加约 300-500 行代码，需测试覆盖

---

## 第 9 章 测试与质量保障

### 现状分析

- 已有 `tests/` 目录，覆盖 balance_checker、config、error_logger、scheduler、usage_history、usage_logger、usage_proxy
- 无 CI 测试执行配置（[.github/workflows/release.yml](file:///d:/#MCP-Serve/deepseek-balance-monitor/.github/workflows/release.yml) 仅构建）
- 无覆盖率统计
- 无 Lint / 类型检查
- 无性能基准测试

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| Q-1 | CI 不跑测试，回归无门禁 | P1 |
| Q-2 | 无覆盖率统计 | P1 |
| Q-3 | 无 Lint / 类型检查 | P2 |

### 改进建议

#### 9.1 【Q-1, Q-2, P1】CI 测试 + 覆盖率门禁

**实施步骤**：
1. 新增 `.github/workflows/test.yml`：push/PR 时跑 `pytest --cov=main --cov-report=xml`
2. 集成 Codecov 或在 PR 评论中显示覆盖率
3. 覆盖率低于 70% 失败（初始阈值，逐步提高）
4. Windows runner（项目为 Windows 优先）

**影响面**：新增 workflow

**风险**：现有测试在 CI 环境可能因 tkinter 依赖失败，需虚拟显示或 mock

#### 9.2 【Q-3, P2】Lint + 类型检查

**实施步骤**：
1. 引入 `ruff`（替代 flake8+black+isort）
2. 引入 `mypy --strict` 渐进式（先宽松，逐步收紧）
3. CI 中执行，失败阻断合并
4. pre-commit 钩子本地校验

**影响面**：新增配置文件、CI

**风险**：现有代码可能大量告警，需批量修复

#### 9.3 性能基准（关联 2.8）

CI 中运行启动时间与内存基准，回归 > 10% 告警。

---

## 第 10 章 打包与分发

### 现状分析

- PyInstaller `--onefile` 模式，启动慢（解压到临时目录）
- 无代码签名，Windows SmartScreen 可能拦截

> **v1.2 调整**：删除原问题 R-2"无自动更新"（用户不考虑自动更新，均为手动更新）。

### 问题清单

| 编号 | 问题 | 严重度 |
|------|------|--------|
| R-1 | onefile 启动慢 | P1 |

### 改进建议

#### 10.1 【R-1, P1】改 onedir 模式 + Nuitka

**方案**：`--onedir` 启动更快；或迁移到 Nuitka 编译为原生代码。

**实施步骤**：
1. 优先尝试 `--onedir`，启动时间预计降 30-50%
2. 进一步用 Nuitka：`nuitka --standalone --onefile --enable-plugin=tk-inter main.py`
3. CI 中对比两种模式的启动基准

**影响面**：[release.yml](file:///d:/#MCP-Serve/deepseek-balance-monitor/.github/workflows/release.yml)

**风险**：onedir 体积略大但启动快；Nuitka 编译耗时

---

## 第 11 章 新功能建议

> **v1.2 调整**：删除原 F-1 阈值告警（用户不做告警）与 F-2 用量预算（用户不做超额告警）。

### 11.1 【F-3, P3】报告导出

余额历史 + 用量统计导出为 PDF/CSV/HTML。

**实施步骤**：
1. 新增"导出报告"菜单
2. 用 `reportlab`（PDF）或 `csv` 模块生成
3. 含余额曲线图、用量柱状图、汇总表

### 11.2 【F-4, P3】多币种聚合

将不同币种余额按汇率换算为单一基准货币显示。

**实施步骤**：
1. 接入汇率 API（如 exchangerate-api）
2. `SettingsConfig` 增加 `base_currency: str = "CNY"`
3. 主窗口/悬浮窗显示换算后总额

---

## 第 12 章 技术栈演进（P3，需用户审批）

> **本章方案需用户审批后方可进入实施**。本章仅作设计与论证。

### 12.1 候选对比结论（已用户确认）

经客观对比 PyQt6/PySide6、Tauri、Flet、Electron、.NET MAUI 与现状，结论：

- **第一推荐**：PyQt6/PySide6 渐进式迁移（已确认）
- **备选**：Tauri 完全重写（已确认保留）
- **不推荐**：Flet、Electron、.NET MAUI、保持现状

### 12.2 主方案：PyQt6/PySide6 渐进式迁移

#### 12.2.1 选型理由

1. **约束平衡最优**：启动中等偏快（可优化到 ~300ms）、内存可优化到 ~40MB、QSS 主题能力满足莫奈色 + 编辑器
2. **迁移成本最低**：用户 PyQt5 精通，UI 重写但业务逻辑（balance_checker / scheduler / usage_history）全部复用
3. **系统集成最强**：QSystemTrayIcon 原生托盘、QShortcut 全局热键、`Qt::Tool | FramelessWindowHint` 稳定悬浮窗
4. **图表性能提升**：pyqtgraph 替代 matplotlib
5. **风险可控**：成熟稳定，文档丰富

#### 12.2.2 迁移阶段

**阶段 1：UI 层迁移（保留业务逻辑）**
- `customtkinter` → `PyQt6` / `PySide6`
- `pystray` → `QSystemTrayIcon`
- `keyboard` → `QShortcut`（全局热键用 `pynput` 或 `global-hotkeys`）
- `matplotlib` → `pyqtgraph`
- 业务逻辑层（balance_checker、scheduler、usage_history、usage_proxy）保持不变

**阶段 2：性能与并发优化**
- `requests` → `httpx`（异步）或 `QNetworkAccessManager`
- `ThreadPoolExecutor` → `asyncio` + `qasync`
- 启动期异步加载（QML 延迟加载思路）

**阶段 3：主题系统重建**
- 第 8 章主题抽象层映射到 QSS
- 莫奈色 QSS 模板生成
- 主题编辑器生成 QSS 实时预览

#### 12.2.3 风险与缓解

| 风险 | 缓解 |
|------|------|
| 迁移期需维护两套 UI | 分支策略：`pyqt-migration` 长期分支，分模块切换 |
| 主题系统需重写 | 第 8 章 Theme 数据模型与 UI 框架解耦，迁移时仅换应用层 |
| 全局热键跨平台差异 | 用 `pynput` 统一抽象 |
| PyInstaller + PyQt 体积大 | 用 Nuitka 编译，压缩 qt 资源 |

### 12.3 备选方案：Tauri 完全重写

#### 12.3.1 适用场景

- 用户追求极致性能（启动 < 200ms、内存 < 30MB）
- 愿意投入 2-3 个月重构
- 计划长期维护 5 年以上

#### 12.3.2 架构

- **前端**：React/Svelte/Vue（CSS 全套，主题最自由）
- **后端**：Rust（Tauri 命令）
- **业务逻辑**：balance_checker / scheduler / usage_proxy 用 Rust 重写（requests → reqwest）

#### 12.3.3 风险

- 全栈重写成本极高
- Rust 学习曲线

### 12.4 决策建议

- **短期（M1~M3）**：在 customtkinter 栈上完成 P0/P1 改进，验证主题系统与性能优化效果
- **中期（M4）**：启动 PyQt6 迁移（阶段 1）
- **长期（M5+）**：评估 Tauri 是否值得，或继续深化 PyQt6

> **本方案需用户审批后方可进入 M4 实施。**

---

## 第 13 章 跨维度协同改进路线图

部分改进项跨多个维度，需协同实施以避免重复劳动或相互冲突。

### 13.1 主题系统协同链（第 2/3/7/8 章）

```
ThemeManager 抽象层（第 8 章）
   │
   ├─ 依赖 → 事件总线（第 3 章 A-2）
   │         └─ UI 组件订阅 theme_changed 事件
   │
   ├─ 协同 → 颜色硬编码移除（第 7 章 U-6）
   │
   └─ 协同 → matplotlib 延迟加载（第 2 章 P-1）
             └─ 图表颜色读取主题 token
```

**实施顺序**：A-2 事件总线 → T-1/T-2/T-3 主题层 → U-6 颜色集中 → P-1 图表主题化

> **v1.2 调整**：删除原"依赖 → 配置 schema 升级（D-1）"链路（用户不引入 schema 迁移）。

### 13.2 安全加固协同链（第 1/3/4 章）

```
DPAPI 加密（S-1）
   │
   ├─ 协同 → proxy 鉴权（S-3）
   │         └─ 独立 token 体系
   │
   └─ 协同 → key hash 升级（S-5）
             └─ usage_proxy / usage_history 同步
```

**实施顺序**：S-1 加密 → S-3 鉴权 → S-5 hash 升级

> **v1.2 调整**：删除原"依赖 → 配置 schema 版本（D-1）"链路。S-1 加密直接在 dataclass 上新增 `api_key_enc` 字段，不依赖 schema 升级。

### 13.3 性能优化协同链（第 2/3/4/5 章）

```
启动异步化（P-2）
   │
   ├─ 依赖 → App 拆分（A-1）
   │         └─ 后台线程职责清晰
   │
   ├─ 协同 → 线程池（P-3 / C-1）
   │
   ├─ 协同 → matplotlib 延迟（P-1）
   │
   └─ 协同 → 优雅退出（E-3）
             └─ 资源清理顺序
```

**实施顺序**：A-1 拆分 → P-2 异步 → P-3/C-1 线程池 → P-1 延迟加载 → E-3 退出

### 13.4 可观测性协同链（第 5/9 章）

```
统一 logging（E-1/E-2）
   │
   ├─ 协同 → 性能基准埋点（第 2.8 节）
   │
   ├─ 协同 → CI 测试（Q-1）
   │         └─ 日志断言
   │
   └─ 协同 → 重试日志（C-4）
```

---

## 第 14 章 里程碑排期建议

> 排期按优先级聚合，每个里程碑对应一个版本。**不包含具体工时估算**（如需可另行评估）。

### M1（v1.10.0）— 安全与稳定性

**目标**：消除所有 P0 安全风险，建立日志基线。

| 改进项 | 来源 |
|--------|------|
| S-1 API Key DPAPI 加密 | 第 1 章 |
| S-3 usage_proxy 鉴权与加固 | 第 1 章 |
| S-4 移除第三方凭证静默读取 | 第 1 章（已移除） |
| E-1/E-2 统一 logging + 轮转 | 第 5 章 |
| A-5 _create_shortcut 注入修复 | 第 3 章 |

**验收**：安全审计通过；日志不再膨胀。

> **v1.2 调整**：删除原"A-3 / D-1 配置 schema + 版本 + 迁移"（用户不引入 pydantic 迁移）。

### M2（v1.11.0）— 性能与并发

**目标**：闪电启动 + 近零占用达标。

| 改进项 | 来源 |
|--------|------|
| P-1 matplotlib 延迟加载 | 第 2 章 |
| P-2 启动期异步化 | 第 2 章 |
| P-3 / C-1 线程池 + Session 复用 | 第 2/4 章 |
| P-4 焦点监视事件驱动 | 第 2 章 |
| P-5 usage_proxy 行级解析 | 第 2 章 |
| C-2 任务取消 | 第 4 章 |
| C-3 ThreadingHTTPServer | 第 4 章 |
| C-4 重试与退避 | 第 4 章 |
| E-3 优雅退出 | 第 5 章 |
| 2.8 性能基准建立 | 第 2 章 |

**验收**：冷启动 < 300ms；闲置内存 < 50MB；闲置 CPU < 0.1%。

### M3（v1.12.0）— 主题与 UX

**目标**：莫奈色主题上线，UX 体验提升。

| 改进项 | 来源 |
|--------|------|
| A-2 事件总线 | 第 3 章 |
| T-1/T-2/T-3 主题抽象层 + 莫奈色 3 套 | 第 8 章 |
| 8.6 主题编辑器 | 第 8 章 |
| U-6 颜色集中管理 | 第 7 章 |
| U-2 快捷键可配置 | 第 7 章 |
| U-4 焦点丢失行为可配置 | 第 7 章 |
| A-4 balance_checker 数字健壮化 | 第 3 章 |
| A-2 Provider 接口抽象与注册表 | 第 3 章 |
| Provider 声明式配置注册/自动发现/校验工具/SDK 文档 | 第 7 章（PRD PROV 模块） |
| P-7 UsageHistory WAL | 第 2 章 |
| D-3 配置原子写入 | 第 6 章 |

**验收**：3 套莫奈色主题可切换；主题编辑器可用；快捷键自定义可用；供应商扩展机制可用。

> **v1.2 调整**：删除原"U-3 系统通知"（用户不需要）与"F-1 阈值告警"（用户不做告警）。

### M4（v2.0.0）— 架构演进与功能扩展

**目标**：App 架构解耦，质量门禁生效。

| 改进项 | 来源 |
|--------|------|
| A-1 App 类拆分 | 第 3 章 |
| S-5 key hash 升级 | 第 1 章 |
| U-1 i18n | 第 7 章 |
| Q-1/Q-2 CI 测试 + 覆盖率 | 第 9 章 |
| Q-3 Lint + 类型检查 | 第 9 章 |
| R-1 onedir/Nuitka 打包 | 第 10 章 |

**验收**：架构分层清晰；CI 门禁生效。

> **v1.2 调整**：删除原"D-2 多 Provider 代理"（用户无多路由需求）、"U-5 可访问性"（用户不考虑）、"R-2 自动更新"（用户不考虑）。

### M5+（v2.x）— 技术栈迁移（需用户审批）

| 改进项 | 来源 |
|--------|------|
| 12.2 PyQt6 渐进迁移阶段 1~3 | 第 12 章 |
| F-3 报告导出 | 第 11 章 |
| F-4 多币种聚合 | 第 11 章 |

**验收**：PyQt6 版本功能与原版对齐；性能指标优于原版。

> **v1.2 调整**：删除原"F-2 用量预算"（用户不做超额告警）。

---

## 附录 A 改进项汇总表

| 编号 | 标题 | 章 | 优先级 | 里程碑 |
|------|------|----|--------|--------|
| S-1 | API Key DPAPI 加密 | 1 | P0 | M1 |
| S-3 | usage_proxy 鉴权与加固 | 1 | P0 | M1 |
| S-4 | 移除第三方凭证静默读取 | 1 | P0 | M1（已移除） |
| S-5 | key hash 升级 SHA-256 | 1 | P1 | M4 |
| P-1 | matplotlib 延迟加载 | 2 | P1 | M2 |
| P-2 | 启动期异步化 | 2 | P1 | M2 |
| P-3 | scheduler 线程池 | 2 | P1 | M2 |
| P-4 | 焦点监视事件驱动 | 2 | P1 | M2 |
| P-5 | usage_proxy 行级解析 | 2 | P1 | M2 |
| P-6 | balance_checker Session 复用 | 2 | P1 | M2 |
| P-7 | UsageHistory WAL | 2 | P2 | M3 |
| A-1 | App 类拆分 | 3 | P1 | M4 |
| A-2 | 事件总线 | 3 | P1 | M3 |
| A-4 | balance_checker 数字健壮化 | 3 | P1 | M3 |
| A-5 | _create_shortcut 注入修复 | 3 | P1 | M1 |
| C-1 | scheduler 线程池上限 | 4 | P1 | M2 |
| C-2 | 任务取消 | 4 | P1 | M2 |
| C-3 | ThreadingHTTPServer | 4 | P1 | M2 |
| C-4 | 重试与退避 | 4 | P1 | M2 |
| E-1 | 统一 logging + 轮转 | 5 | P1 | M1 |
| E-2 | 日志分级 | 5 | P1 | M1 |
| E-3 | 优雅退出 | 5 | P1 | M2 |
| D-3 | 配置原子写入 + 备份 | 6 | P2 | M3 |
| U-1 | i18n | 7 | P2 | M4 |
| U-2 | 快捷键可配置 | 7 | P2 | M3 |
| U-4 | 焦点丢失行为可配置 | 7 | P2 | M3 |
| U-6 | 颜色集中管理 | 7 | P2 | M3 |
| T-1 | 主题抽象层 | 8 | P2 | M3 |
| T-2 | 颜色集中管理 | 8 | P2 | M3 |
| T-3 | 主题扩展接口 | 8 | P2 | M3 |
| Q-1 | CI 测试 | 9 | P1 | M4 |
| Q-2 | 覆盖率门禁 | 9 | P1 | M4 |
| Q-3 | Lint + 类型检查 | 9 | P2 | M4 |
| R-1 | onedir/Nuitka 打包 | 10 | P1 | M4 |
| F-3 | 报告导出 | 11 | P3 | M5+ |
| F-4 | 多币种聚合 | 11 | P3 | M5+ |
| 12.2 | PyQt6 渐进迁移 | 12 | P3 | M5+ |

> **v1.2 删除项**：A-3/D-1（配置 schema）、D-2（多 Provider 代理）、U-3（系统通知）、U-5（可访问性）、R-2（自动更新）、F-1（阈值告警）、F-2（用量预算）。

---

## 附录 B 风险登记册

| 风险 | 概率 | 影响 | 缓解策略 |
|------|------|------|----------|
| DPAPI 加密导致跨用户迁移困难 | 中 | 中 | 提供重新输入 Key 流程；文档说明 |
| 主题切换实时生效不完整 | 中 | 中 | 全组件订阅 theme_changed；测试覆盖 |
| customtkinter 自定义颜色边界 | 中 | 中 | 验证关键组件；必要时换栈（第 12 章） |
| CI 环境无 tkinter 显示 | 高 | 中 | 虚拟显示（xvfb）或 mock UI 层 |
| PyQt6 迁移期双 UI 维护负担 | 高 | 高 | 长期分支 + 分模块切换 + 充分测试 |
| Tauri 重写业务逻辑成本高 | 高 | 高 | 分阶段重写，优先核心模块 |
| 性能基准回归未及时发现 | 中 | 中 | CI 性能门禁 + 告警 |
| 主题编辑器增加复杂度 | 中 | 低 | 限制为高级用户功能；默认主题充分 |
| 自定义 Provider 配置漏洞 | 中 | 中 | 配置校验 + 白名单 |
| python_module 解析器代码执行 | 低 | 高 | 仅信任源启用 + 沙箱 |

> **v1.2 删除项**：删除"配置迁移脚本丢失用户数据"（A-3/D-1 已删除）、"自动更新被中间人攻击"（R-2 已删除）。

---

**文档结束**

> 本方案为全面体检式改进路线图，v1.3 共 36 项改进，按 M1~M5+ 五个里程碑推进。
> 第 12 章技术栈演进需用户审批后方可实施。
> 本方案仅为设计文档，不涉及任何代码改动。
