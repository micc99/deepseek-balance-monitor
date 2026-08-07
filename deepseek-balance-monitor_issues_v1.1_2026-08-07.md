# DeepSeek 余额监控 · 可执行 Issue 清单

> **文档版本**：v1.1
> **文档日期**：2026-08-07
> **源 PRD**：[deepseek-balance-monitor_PRD_v1.3_2026-08-07.md](file:///d:/#MCP-Serve/deepseek-balance-monitor/deepseek-balance-monitor_PRD_v1.3_2026-08-07.md)
> **配套改进方案**：[deepseek-balance-monitor_改进方案_v1.2_2026-08-07.md](file:///d:/#MCP-Serve/deepseek-balance-monitor/deepseek-balance-monitor_改进方案_v1.2_2026-08-07.md)
> **文档目的**：将 PRD 中的需求拆分为可直接领取执行的工作项（Issue），每个 Issue 含任务清单、验收标准、依赖关系与执行要点
> **语言**：简体中文（技术术语保留英文原文）
> **命名规范**：`ISSUE-<模块缩写>-<序号>`，与 PRD 需求 ID 一一对应
> **v1.1 变更说明**：
> - 基于用户决策删除以下 Issue（用户无对应需求）：
>   - ISSUE-ARC-03 配置 schema + 版本 + 迁移（用户不引入 pydantic 迁移机制，配置保留 dataclass）
>   - ISSUE-SEC-02 旧版明文配置自动迁移（用户不需要自动迁移，改为检测到旧明文时提示重新输入）
>   - ISSUE-UX-03 系统通知（用户不需要系统通知）
>   - ISSUE-UX-05 可访问性（用户不考虑视障人士支持）
>   - ISSUE-PKG-02 自动更新（用户不考虑自动更新，均为手动更新）
>   - ISSUE-FEAT-01 阈值告警（用户不做告警）
>   - ISSUE-FEAT-02 用量预算（用户不做超额告警）
>   - ISSUE-NET-04 多 Provider 代理路由（用户无本地代理多路由需求，维持单 Provider 代理）
> - 连锁调整：ISSUE-SEC-01/05、ISSUE-THM-02、ISSUE-CFG-02 依赖去除（不再依赖 ISSUE-ARC-03）
> - 配置模型去除 version 字段，保留 dataclass 方式
> - 别名 FR-CFG-01（原指向 ISSUE-ARC-03）一并删除
> - Issue 总数由 57 项减少至 50 项（含 6 项非功能/风险跟踪）
> - v1.0 的源 PRD 引用由 v1.2 更新为 v1.3

---

## 0. 文档使用说明

### 0.1 Issue 字段说明

每个 Issue 统一包含以下字段：

| 字段 | 说明 |
|------|------|
| **Issue ID** | 唯一标识，对应 PRD 需求 ID（如 `ISSUE-SEC-01` ↔ `FR-SEC-01`） |
| **标题** | 一句话描述任务目标 |
| **里程碑 / 优先级** | M1~M5+ / P0~P3 |
| **模块** | 功能模块归属 |
| **依赖需求** | 前置完成的 Issue ID（无依赖则标注"无"） |
| **关联改进项** | 改进方案中的 ID（S-x / P-x / A-x 等） |
| **用户故事** | 作为...我希望...以便... |
| **当前状态** | 现状描述与痛点 |
| **任务清单** | 可执行的子任务（checkbox） |
| **验收标准** | AC1~ACn 条目，逐项核对 |
| **执行要点** | 技术细节、边界条件、风险提示 |

### 0.2 执行流程

1. 按**里程碑顺序**推进（M1 → M2 → M3 → M4 → M5+）
2. 同一里程碑内按**优先级**排序（P0 → P1 → P2 → P3）
3. 领取 Issue 前先检查**依赖需求**是否已完成
4. 实现时在代码注释与 commit message 中引用 Issue ID
5. 完成后逐条核对**验收标准**并勾选
6. 跨 Issue 协作时通过"关联改进项"与"依赖需求"字段追溯

### 0.3 Issue 统计概览

| 里程碑 | 版本 | Issue 数 | P0 | P1 | P2 | P3 |
|--------|------|----------|----|----|----|----|
| M1 | v1.10.0 | 7 | 3 | 4 | 0 | 0 |
| M2 | v1.11.0 | 11 | 0 | 11 | 0 | 0 |
| M3 | v1.12.0 | 17 | 0 | 4 | 13 | 0 |
| M4 | v2.0.0 | 6 | 0 | 4 | 2 | 0 |
| M5+ | v2.x | 3 | 0 | 0 | 0 | 3 |
| 非功能/风险跟踪 | — | 6 | — | — | — | — |
| **合计** | — | **50** | **3** | **23** | **15** | **3** |

> 说明：PRD 中 2 个引用别名（FR-CFG-03=FR-SEC-04、FR-QA-03=FR-PFM-07）不单独建立 Issue，在对应主 Issue 中标注。ISSUE-MIGRATE-PyQt6 为改进方案衍生的技术栈迁移 Issue，不直接对应 PRD 功能需求 ID。功能 Issue 共 44 项（43 项 PRD 映射 + 1 项迁移评估），加 6 项非功能/风险跟踪合计 50 项。

---

## 1. M1 里程碑（v1.10.0）· 安全与稳定性

> **里程碑目标**：消除 P0 安全风险，建立配置与日志基线
> **验收口径**：所有 P0 安全需求完成、日志脱敏完成、统一日志系统、快捷方式注入修复、安全审计通过

### ISSUE-SEC-01 · API Key DPAPI 加密存储

- **里程碑 / 优先级**：M1 / P0
- **模块**：安全（SEC）
- **依赖需求**：无
- **关联改进项**：S-1

> **v1.1 调整**：删除原依赖 ISSUE-ARC-03（配置 schema 升级）。直接在 dataclass 上新增 `api_key_enc` 字段，不依赖 pydantic schema。删除原 ISSUE-SEC-02（旧版明文配置自动迁移），改为检测到旧明文配置时弹窗提示用户重新输入。

#### 用户故事
作为用户，我希望我的 API Key 以加密形式存储在本地，即使配置文件被他人获取也无法直接读取，以保护我的账户资产安全。

#### 当前状态
**已完成**。[config.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/config.py) `save_config` 将 API Key 以**明文**写入 `config.json`；`AccountConfig.api_key` 字段直接存储明文。风险：配置文件备份/共享/误传/被恶意程序读取即造成所有 Key 泄露。

#### 任务清单
- [x] 新建 `main/credential_store.py`，定义 `CredentialStore` 抽象接口（`encrypt(plain) -> str` / `decrypt(cipher) -> str`）
- [x] 实现 `WindowsCredentialStore`：通过 `ctypes.windll.crypt32.CryptProtectData` / `CryptUnprotectData` 调用 DPAPI，密钥与当前 Windows 用户账户绑定
- [x] 加密后密文经 base64 编码
- [x] 实现 `KeyringCredentialStore`：非 Windows 平台使用 [keyring](https://pypi.org/project/keyring/) 库（macOS Keychain / Linux Secret Service）
- [x] `AccountConfig` 新增 `api_key_enc: str` 字段（dataclass 直接新增），移除明文 `api_key` 字段
- [x] `api_key` 改为 `@property`，首次访问时从 `api_key_enc` 解密并缓存到内存
- [x] 加密失败（DPAPI 服务不可用）时降级为明文 + WARN 日志，不阻断启动
- [x] 解密失败（换用户账户）时弹窗提示"无法解密 API Key，请重新输入"，提供重新输入入口
- [x] **旧版明文配置检测**：`load_config` 检测到 `api_key` 字段存在且 `api_key_enc` 不存在时，弹窗提示用户"检测到旧版明文配置，请重新输入 API Key"，不自动迁移
- [x] 空 Key 不加密，直接存空字符串
- [x] 编写单元测试覆盖加密/解密/降级/空值/旧版检测场景

#### 验收标准
- [x] AC1：config.json 中不存在明文 `api_key` 字段，仅存在 `api_key_enc`
- [x] AC2：`api_key_enc` 经 DPAPI 加密后 base64 编码
- [x] AC3：换 Windows 用户账户后解密失败，弹窗提示并允许重新输入
- [x] AC4：解密失败时不崩溃，给出明确错误码与提示
- [x] AC5：加密失败时降级为明文并记录 WARN 日志
- [x] AC6：检测到旧版明文配置时弹窗提示用户重新输入（不自动迁移）
- [x] AC7：单元测试覆盖加密/解密/降级/空值/旧版检测场景

#### 执行要点
- DPAPI 调用需注意 `DWORD` 返回值与 `GetLastError` 处理
- 内存缓存的明文 Key 受进程生命周期保护，退出时清空
- 跨平台回退通过运行时 `sys.platform` 判断选择实现
- 旧版明文配置不自动迁移，用户需手动重新输入 Key（用户决策：不做自动迁移）

---

### ISSUE-SEC-04 · usage_proxy 鉴权与目标白名单

- **里程碑 / 优先级**：M1 / P0
- **模块**：安全（SEC）
- **依赖需求**：ISSUE-SEC-01、ISSUE-PROV-02（白名单同步）
- **关联改进项**：S-3
- **别名**：FR-CFG-03 中的 `active_key_sources` 字段在 ISSUE-SEC-05 实现

#### 用户故事
作为用户，我希望本地反向代理仅接受我授权的客户端请求，且代理目标限定在已知 AI 平台，防止被借用消耗额度或转发到任意主机。

#### 当前状态
**已完成**。[usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) 监听 127.0.0.1:52848 无鉴权；`target_host` 可任意配置（虽有默认值，但无白名单校验）。

#### 任务清单
- [x] 代理请求头校验 `X-Proxy-Token`，与 `SettingsConfig.proxy_token_enc` 解密后的 token 比对
- [x] 使用 `hmac.compare_digest` 恒定时间比较防止时序攻击
- [x] 首次启动生成随机 32 字节 token（`secrets.token_bytes(32)`），DPAPI 加密存储
- [x] 设置面板新增"查看 token"与"重置 token"按钮
- [x] `target_host` 白名单校验，默认覆盖 5 个 Provider 域名
- [x] 白名单支持动态扩展：FR-PROV-02 注册的 Provider 域名自动加入白名单
- [x] 审计日志：每次请求记录 key hash + 请求路径 + 时间 + 状态码，**不记录请求/响应体**
- [x] 鉴权失败返回 403 + 审计日志 WARN
- [x] 白名单拒绝返回 403 + 审计日志 WARN
- [x] 目标不可达返回 502 + 审计日志 ERROR
- [x] 编写单元测试覆盖鉴权/白名单/审计/重置

#### 验收标准
- [x] AC1：未携带正确 token 的请求返回 403
- [x] AC2：白名单外的 target_host 返回 403
- [x] AC3：审计日志不含请求/响应体
- [x] AC4：FR-PROV-02 注册的 Provider 域名自动加入白名单
- [x] AC5：设置面板可查看与重置 token
- [x] AC6：单元测试覆盖鉴权/白名单/审计/重置

#### 执行要点
- token 重置后需通知所有客户端更新（或文档提示用户手动更新）
- 白名单数据结构建议 `set[str]`，支持 O(1) 查找
- 注意 ISSUE-PROV-02 在 M3 才完成，白名单动态扩展部分可先实现接口，待 PROV-02 完成后联调
- 维持单 Provider 代理（用户决策：不做多 Provider 代理路由）

---

### ISSUE-SEC-05 · 移除第三方凭证静默读取 ｜ 已移除（用户决策：仅使用 config.json 账户配置，无需第三方凭证源）

- **里程碑 / 优先级**：M1 / P0
- **模块**：安全（SEC）
- **依赖需求**：无
- **关联改进项**：S-4

> **v1.1 调整**：删除原依赖 ISSUE-ARC-03。直接在 dataclass 上新增 `active_key_sources` 字段。

> **状态变更（2026-08-07）**：本 Issue 已整体移除，不再实现凭证源管理功能。用户决策：仅使用 config.json 中的账户配置查询余额，无需读取第三方凭证文件。下方任务清单与验收标准保留作为历史记录。

#### 用户故事
作为用户，我希望程序不会在我不知情的情况下读取桌面或第三方工具的凭证文件，所有凭证导入需我显式授权。

#### 当前状态
**已移除（用户决策：仅使用 config.json 账户配置，无需第三方凭证源）**。本 Issue 整体移除，不再实现凭证源管理功能，下方任务清单与验收标准保留作为历史记录。

历史现状（移除前）：[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) `_load_active_keys` 默认扫描 `Desktop\auth.json`、`opencode\auth.json`，用户无感知。Desktop 路径存在注入风险（恶意程序可放置伪造文件）。

#### 任务清单
- [x] 删除 `_load_active_keys` 中对默认路径的扫描逻辑
- [x] `SettingsConfig` 新增 `active_key_sources: list[str]` 字段（dataclass 直接新增，默认空列表）
- [x] 设置面板新增"导入凭证源"功能，点击后弹出文件选择对话框
- [x] 选择文件后弹窗告知"将读取该文件的 key 字段用于活跃账户标识（不影响余额查询）"
- [x] 用户确认后记录路径到 `active_key_sources`
- [x] 仅读取用户授权路径，每条路径独立校验存在性，不存在时跳过并告警
- [x] 设置面板支持删除已授权路径（撤销授权）
- [x] 编写单元测试覆盖授权/读取/撤销

#### 验收标准
- [x] AC1：默认不读取任何第三方凭证文件
- [x] AC2：设置面板提供"导入凭证源"入口
- [x] AC3：导入时弹窗告知用途，用户确认后记录路径
- [x] AC4：仅读取授权路径，路径不存在时跳过并告警
- [x] AC5：可撤销已授权路径
- [x] AC6：单元测试覆盖授权/读取/撤销

#### 执行要点
- 凭证源读取仅用于"活跃账户标识"，不影响余额查询逻辑
- 文件路径校验：拒绝相对路径、拒绝含 `..` 的路径

---

### ISSUE-SEC-07 · 日志脱敏

- **里程碑 / 优先级**：M1 / P1
- **模块**：安全（SEC）
- **依赖需求**：ISSUE-LOG-01
- **关联改进项**：NFR-SEC-03

#### 用户故事
作为用户，我希望日志中不出现我的 API Key 明文，避免日志泄露导致 Key 泄露。

#### 当前状态
**已完成**。[error_logger.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/error_logger.py) 不主动记录 Key，但异常 traceback 中可能包含 Key 字符串（如 balance_checker 的错误消息）。

#### 任务清单
- [x] 在 logging handler 中添加 `logging.Filter` 过滤器
- [x] 正则匹配常见 Key 格式：`sk-[a-zA-Z0-9]{20,}`、Bearer token 等
- [x] 命中后替换为 `sk-***`（保留前缀便于识别类型）
- [x] 白名单字段不脱敏：`api_key_hash`、`masked_key`
- [x] usage_proxy 审计日志（ISSUE-SEC-04）仅记录 hash
- [x] 编写单元测试覆盖脱敏（明文替换、白名单保留、traceback 处理）

#### 验收标准
- [x] AC1：日志文件扫描无明文 Key
- [x] AC2：异常 traceback 中 Key 被脱敏
- [x] AC3：hash 字段不被误脱敏
- [x] AC4：单元测试覆盖脱敏

#### 执行要点
- 过滤器挂在根 logger 上，确保所有 handler 生效
- 正则规则可配置化，便于后续扩展新 Key 格式

---

### ISSUE-LOG-01 · 统一 logging + RotatingFileHandler

- **里程碑 / 优先级**：M1 / P1
- **模块**：日志（LOG）
- **依赖需求**：无
- **关联改进项**：E-1

#### 用户故事
作为用户，我希望日志文件不无限膨胀，占用磁盘。

#### 当前状态
**已完成**。[error_logger.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/error_logger.py) 每次异常创建独立 `.log` 文件，文件数无上限，长期运行后 `log/` 目录膨胀。

#### 任务清单
- [x] 新建 `main/log_setup.py`，配置根 logger
- [x] 使用 `logging.handlers.RotatingFileHandler`，单文件 `app.log`，maxBytes=2MB，backupCount=5
- [x] 日志格式：`%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- [x] 文件记录 DEBUG 级别，控制台记录 INFO 级别（开发时）
- [x] 保留 `log_exception(source, exc)` 接口兼容，内部转 `logger.exception`
- [x] 提供 `scripts/cleanup_old_logs.py` 脚本清理旧 `log/` 目录下的散落文件
- [x] 编写单元测试验证轮转行为

#### 验收标准
- [x] AC1：日志写入 app.log，按大小轮转
- [x] AC2：保留 5 份备份
- [x] AC3：log_exception 接口保留兼容
- [x] AC4：旧 log/ 目录提供清理脚本

#### 执行要点
- 应用入口 `main.py` 启动时调用 `log_setup.setup_logging()` 初始化
- 旧 `error_logger.py` 的散落文件由清理脚本一次性处理

---

### ISSUE-LOG-02 · 日志分级

- **里程碑 / 优先级**：M1 / P1
- **模块**：日志（LOG）
- **依赖需求**：ISSUE-LOG-01
- **关联改进项**：E-2

#### 用户故事
作为维护者，我希望日志有分级，便于排查问题。

#### 当前状态
**已完成**。无日志分级，所有异常同等对待。

#### 任务清单
- [x] 全项目改用 `logging.getLogger(__name__)` 获取 logger
- [x] 明确日志级别使用规范：DEBUG（调试）/ INFO（关键流程）/ WARN（可恢复异常）/ ERROR（不可恢复异常）
- [x] 文件记录 DEBUG+，控制台记录 INFO+（开发时）
- [x] `SettingsConfig` 新增 `log_level: str = "INFO"` 配置项
- [x] 启动时根据配置设置根 logger 级别
- [x] 审计关键流程日志：配置加载、Provider 注册、主题切换、刷新请求
- [x] 编写单元测试验证级别过滤

#### 验收标准
- [x] AC1：所有模块使用标准 logger
- [x] AC2：文件 DEBUG+，控制台 INFO+
- [x] AC3：格式含时间、级别、模块、消息
- [x] AC4：可通过配置调整级别

#### 执行要点
- 替换 `print` 与 `error_logger.log_exception` 调用为标准 logger
- 避免 logger 命名冲突，统一用 `__name__`

---

### ISSUE-ARC-05 · _create_shortcut 注入修复

- **里程碑 / 优先级**：M1 / P1
- **模块**：架构（ARC）
- **依赖需求**：无
- **关联改进项**：A-5

#### 用户故事
作为用户，我希望开机自启快捷方式创建安全，无注入风险。

#### 当前状态
**已完成**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) `_create_shortcut` 拼接 PowerShell 脚本，路径含单引号时存在注入风险。

#### 任务清单
- [x] 优先方案：改用 `pywin32` 的 `win32com.client.ShellLink` 对象创建快捷方式
- [x] 若 `pywin32` 未依赖，回退方案：PowerShell 调用改为 `-ArgumentList` 参数化，禁止字符串插值
- [x] 路径校验：仅允许绝对路径，不含 `;` `|` `&` 等特殊字符
- [x] 编写单元测试覆盖特殊字符（单引号、空格、中文路径、Unicode）

#### 验收标准
- [x] AC1：路径含单引号、空格、特殊字符时正常工作
- [x] AC2：无字符串拼接 PowerShell 命令
- [x] AC3：路径校验仅允许绝对路径
- [x] AC4：单元测试覆盖特殊字符

#### 执行要点
- 推荐引入 `pywin32` 作为正式依赖，提升 Windows 集成质量
- 校验函数独立，便于复用与测试

---

## 2. M2 里程碑（v1.11.0）· 性能与并发

> **里程碑目标**：达成闪电启动 + 近零占用性能指标
> **验收口径**：冷启动 < 300ms、闲置内存 < 50MB、闲置 CPU < 0.1%、10 账户刷新 < 5s、性能基准建立、优雅退出

### ISSUE-PFM-01 · matplotlib 延迟加载

- **里程碑 / 优先级**：M2 / P1
- **模块**：性能（PFM）
- **依赖需求**：无
- **关联改进项**：P-1

#### 用户故事
作为用户，我希望应用启动迅速，不要为我不常打开的图表功能承担启动耗时。

#### 当前状态
**未实现**。[usage_curve_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_curve_window.py) 与 [usage_bar_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_bar_window.py) 顶部 `import matplotlib`，启动时加载 matplotlib 首次 import 可达 200-500ms。

#### 任务清单
- [ ] 将 `usage_curve_window.py` 与 `usage_bar_window.py` 顶部的 `import matplotlib` 下沉到 `__init__` 或首次绘图方法内（局部 import）
- [ ] 首次打开曲线/柱状图窗口时显示"加载图表中..."提示
- [ ] 使用 `python -X importtime main.py` 验证启动时不再 import matplotlib
- [ ] 编写测试验证首次打开窗口可正常绘图（< 500ms）

#### 验收标准
- [ ] AC1：启动时不再 import matplotlib（`-X importtime` 验证）
- [ ] AC2：冷启动时间下降 ≥ 200ms
- [ ] AC3：首次打开曲线窗口可正常绘图（< 500ms）
- [ ] AC4：打开窗口时显示 loading 提示

#### 执行要点
- 局部 import 仅在首次调用时执行，后续访问已缓存的模块对象
- M5+ 可评估迁移到 pyqtgraph（参见 PRD 第 7.5 节）

---

### ISSUE-PFM-02 · 启动期 IO 与建表异步化

- **里程碑 / 优先级**：M2 / P1
- **模块**：性能（PFM）
- **依赖需求**：无（建议参考 ISSUE-ARC-01，但可在现有 App 结构内先行实现）
- **关联改进项**：P-2

#### 用户故事
作为用户，我希望应用启动后首屏迅速可见，后台数据加载不阻塞界面。

#### 当前状态
**未实现**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) `App.__init__` 同步执行 `load_config`（磁盘读）、`_load_active_keys`（磁盘读）、`UsageHistory()`（SQLite 建表）、`UsageProxy.start()`（端口绑定）。

#### 任务清单
- [ ] `App.__init__` 仅创建 `MainWindow`（空账户列表），不执行磁盘 IO
- [ ] 启动后台线程执行：load_config → 凭证源加载 → UsageHistory 建表 → UsageProxy 启动
- [ ] 后台加载完成后通过 `main_window.after(0, ...)` 回填账户列表并触发首次刷新
- [ ] 首屏空状态 UI：200-400ms 内无数据，显示"加载中..."友好提示
- [ ] 后台加载失败时 UI 显示错误状态，不崩溃
- [ ] 编写测试验证首屏渲染不等待磁盘 IO、加载过程中 UI 可交互

#### 验收标准
- [ ] AC1：首屏渲染不等待磁盘 IO
- [ ] AC2：后台加载完成后回填数据
- [ ] AC3：首屏空状态有友好提示
- [ ] AC4：冷启动时间 < 300ms（10 账户场景）
- [ ] AC5：加载过程中 UI 可交互（按钮可点击）
- [ ] AC6：后台加载失败时 UI 显示错误状态

#### 执行要点
- tkinter 主线程不可被后台线程直接操作 UI，必须通过 `after` 调度
- 后台线程异常需捕获并通过事件总线/回调通知主线程

---

### ISSUE-PFM-03 · scheduler 线程池改造

- **里程碑 / 优先级**：M2 / P1
- **模块**：性能（PFM）
- **依赖需求**：无
- **关联改进项**：P-3、C-1

#### 用户故事
作为用户，我希望多账户刷新快速且不创建过多线程，保持后台低占用。

#### 当前状态
**未实现**。[scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) `_check_all` 每账户新建一个 `threading.Thread`，10 账户即 10 线程，无并发上限。

#### 任务清单
- [ ] `BalanceScheduler.__init__` 创建 `ThreadPoolExecutor(max_workers=4, thread_name_prefix="balance-check")`
- [ ] `_check_all` 改为 `executor.map(self._do_check, accounts)` 或提交 Future
- [ ] 并发上限 max_workers=4，避免线程爆炸
- [ ] 退出时 `executor.shutdown(wait=True, timeout=5)`
- [ ] 编写单元测试覆盖并发与关闭

#### 验收标准
- [ ] AC1：单轮刷新线程数 ≤ 4
- [ ] AC2：10 账户刷新延迟 < 5s
- [ ] AC3：退出时正确关闭 executor
- [ ] AC4：单元测试覆盖并发与关闭

#### 执行要点
- 与 ISSUE-NET-01（任务取消）协同，Future 模式便于超时取消
- 与 ISSUE-PFM-04（Session 复用）协同，注意 requests.Session 线程安全

---

### ISSUE-PFM-04 · Provider Session 长连接复用

- **里程碑 / 优先级**：M2 / P1
- **模块**：性能（PFM）
- **依赖需求**：ISSUE-PFM-03
- **关联改进项**：P-6

#### 用户故事
作为用户，我希望余额查询快速，不因每次新建连接而变慢。

#### 当前状态
**未实现**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 每次请求新建 `requests.Session()`，连接未复用，TCP/TLS 握手开销大。

#### 任务清单
- [ ] `BaseProvider` 持有 `self._session = requests.Session()`，实例化时创建
- [ ] 每个 Provider 实例独立 Session（按域名隔离连接池）
- [ ] 配置 `HTTPAdapter(pool_connections=5, pool_maxsize=10)` 挂载到 Session
- [ ] 退出时 `session.close()`
- [ ] requests.Session 非线程安全，配合 ISSUE-PFM-03 线程池需加锁或每线程独立 Session（推荐 `threading.local`）
- [ ] 编写单元测试覆盖复用与关闭

#### 验收标准
- [ ] AC1：Provider 持有长连接 Session
- [ ] AC2：连接池命中率提升（可通过日志统计）
- [ ] AC3：并发请求下 Session 线程安全
- [ ] AC4：退出时 Session 关闭
- [ ] AC5：单元测试覆盖复用与关闭

#### 执行要点
- 线程安全方案优先选 `threading.local`，每个线程独立 Session 实例
- 连接池命中率可通过 `adapter.poolmanager.pools` 统计（DEBUG 日志）

---

### ISSUE-PFM-05 · 焦点监视改事件驱动

- **里程碑 / 优先级**：M2 / P1
- **模块**：性能（PFM）
- **依赖需求**：无（与 ISSUE-UX-04 协同，事件驱动可先行实现，配置开关后续补充）
- **关联改进项**：P-4

#### 用户故事
作为用户，我希望应用后台闲置时几乎不消耗 CPU。

#### 当前状态
**未实现**。[main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) `_focus_check_loop` 每 500ms 调用 `focus_get` 轮询，持续唤醒主循环，违背"近零占用"。

#### 任务清单
- [ ] `MainWindow` 绑定 `bind_all("<FocusOut>", ...)` 与 `bind_all("<FocusIn>", ...)`
- [ ] 收到 `FocusOut` 后起 300ms `after` 计时器，期间若收到 `FocusIn` 则取消
- [ ] 计时器触发后校验是否存在子对话框（CTkToplevel），有则不切
- [ ] 删除 `_focus_check_loop` 轮询逻辑
- [ ] 与 ISSUE-UX-04 协同，可配置是否启用失焦自动切悬浮窗
- [ ] 编写测试验证闲置 CPU 与失焦切换行为

#### 验收标准
- [ ] AC1：闲置 5 分钟 CPU 平均 < 0.1%
- [ ] AC2：失焦后切悬浮窗行为与原逻辑一致
- [ ] AC3：误报率不高于原方案
- [ ] AC4：可通过设置关闭该行为（ISSUE-UX-04）

#### 执行要点
- 300ms 计时器用于过滤快速焦点切换（如点击子对话框时的瞬时 FocusOut）
- 子对话框校验避免误切

---

### ISSUE-PFM-06 · usage_proxy 流式行级解析

- **里程碑 / 优先级**：M2 / P1
- **模块**：性能（PFM）
- **依赖需求**：ISSUE-SEC-04
- **关联改进项**：P-5
- **别名**：FR-QA-03 指向 ISSUE-PFM-07（性能基准）

#### 用户故事
作为用户，我希望代理在处理长流式响应时内存占用平稳。

#### 当前状态
**未实现**。[usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) `usage_text += chunk.decode(...)` 累积整段响应文本，长响应（> 1MB）内存峰值高。

#### 任务清单
- [ ] 维护 `line_buffer: str`，每个 chunk 写入客户端后 append 到 buffer
- [ ] 按 `\n` 分割 buffer，对完整行检查 `data: ` 前缀与 `usage` 关键字
- [ ] 命中 `usage` 即解析并 `log_usage`，清空已处理部分
- [ ] 正确拼接跨 chunk 的 SSE 行
- [ ] 不再保存完整 `usage_text`，内存占用恒定
- [ ] 编写单元测试覆盖行级解析（含跨 chunk 场景）

#### 验收标准
- [ ] AC1：长响应（> 1MB）内存峰值下降 ≥ 50%
- [ ] AC2：usage 提取结果与原方案一致
- [ ] AC3：跨 chunk 的 SSE 行正确拼接
- [ ] AC4：单元测试覆盖行级解析

#### 执行要点
- 行级状态机需处理 `\r\n` 与 `\n` 两种换行符
- 测试用例应覆盖 SSE 行被 chunk 边界切分的场景

---

### ISSUE-PFM-07 · 性能基准测试建立

- **里程碑 / 优先级**：M2 / P1
- **模块**：性能（PFM）+ 质量保障（QA）
- **依赖需求**：ISSUE-QA-01（CI 基础）
- **关联改进项**：2.8

#### 用户故事
作为维护者，我希望有可量化的性能基准，及时发现性能回归。

#### 当前状态
**未实现**。无性能基准测试方法与 CI 门禁。

#### 任务清单
- [ ] 定义指标：冷启动时间、热启动时间、闲置内存、闲置 CPU、10 账户刷新延迟
- [ ] 编写启动时间测量脚本：`python -X importtime main.py` 分析 import 耗时
- [ ] 编写 psutil 采样脚本：定期采样内存/CPU 写入日志
- [ ] scheduler 内埋点统计刷新延迟
- [ ] CI 中执行基准，回归 > 10% 告警
- [ ] 基准结果写入 `docs/performance-baseline.md`

#### 验收标准
- [ ] AC1：提供启动时间测量脚本
- [ ] AC2：提供 psutil 采样脚本
- [ ] AC3：CI 中执行基准，回归 > 10% 告警
- [ ] AC4：基准结果写入文档

#### 执行要点
- 基准测试需在稳定环境运行，CI 噪声大时取多次中位数
- 与 ISSUE-QA-01 协同，性能基准作为 CI 的一个 job

---

### ISSUE-NET-01 · scheduler 任务取消

- **里程碑 / 优先级**：M2 / P1
- **模块**：并发网络（NET）
- **依赖需求**：ISSUE-PFM-03
- **关联改进项**：C-2

#### 用户故事
作为用户，我希望刷新超时的账户不会无限挂起，影响后续刷新。

#### 当前状态
**未实现**。[scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) `t.join(timeout=15)` 超时后线程仍在后台运行，长期累积可能"僵尸线程"。

#### 任务清单
- [ ] `_check_all` 提交所有 `Future` 到线程池
- [ ] 使用 `concurrent.futures.as_completed(futures, timeout=15)` 收集结果
- [ ] 超时的 Future 调用 `cancel()`（仅未启动的可取消，运行中的依赖 Provider 端 `requests` 超时）
- [ ] 记录 WARN 日志（账户 UID + 超时秒数）
- [ ] 编写单元测试覆盖超时场景

#### 验收标准
- [ ] AC1：单账户超时不影响其他账户
- [ ] AC2：超时 Future 调用 cancel
- [ ] AC3：记录警告日志
- [ ] AC4：单元测试覆盖超时场景

#### 执行要点
- `cancel()` 仅能取消未启动的 Future，运行中任务需依赖 `requests` 的 `timeout` 参数
- 超时阈值（15s）可配置化

---

### ISSUE-NET-02 · usage_proxy ThreadingHTTPServer

- **里程碑 / 优先级**：M2 / P1
- **模块**：并发网络（NET）
- **依赖需求**：无（与 ISSUE-PFM-08 协同，多线程服务可先行实现，WAL 后续补充以支撑并发写）
- **关联改进项**：C-3

#### 用户故事
作为用户，我希望代理能并发处理多个请求，不排队。

#### 当前状态
**未实现**。[usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) `HTTPServer` 单线程，并发请求排队。

#### 任务清单
- [ ] `HTTPServer` → `socketserver.ThreadingHTTPServer`
- [ ] 设置 `daemon_threads = True`，主进程退出时子线程自动结束
- [ ] 配合 ISSUE-PFM-04 Provider Session 复用降低开销
- [ ] 配合 ISSUE-PFM-08 WAL 模式支撑并发写
- [ ] 编写单元测试覆盖并发请求

#### 验收标准
- [ ] AC1：并发请求不排队
- [ ] AC2：daemon_threads = True
- [ ] AC3：并发写 SQLite 不损坏
- [ ] AC4：单元测试覆盖并发

#### 执行要点
- ThreadingHTTPServer 每请求一线程，需注意线程数上限（可用信号量控制）
- 与 ISSUE-PFM-08 联调确保 SQLite 并发写安全

---

### ISSUE-NET-03 · balance_checker 重试与退避

- **里程碑 / 优先级**：M2 / P1
- **模块**：并发网络（NET）
- **依赖需求**：ISSUE-PFM-04
- **关联改进项**：C-4

#### 用户故事
作为用户，我希望网络抖动时余额查询自动重试，不轻易报错。

#### 当前状态
**未实现**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 仅捕获超时与连接错误，无重试，无退避。

#### 任务清单
- [ ] 引入 `tenacity` 依赖（或自实现重试装饰器）
- [ ] 定义重试条件：`requests.exceptions.Timeout`、`ConnectionError`、`5xx` 状态码
- [ ] 退避策略：指数退避 1s → 2s → 4s，最多 3 次
- [ ] 4xx（含 401/403）不重试
- [ ] 重试中 UI 显示"重试中..."状态
- [ ] 重试耗尽返回 `BalanceStatus.ERROR`，error_message 标注"重试 N 次后失败"
- [ ] 编写单元测试覆盖重试逻辑

#### 验收标准
- [ ] AC1：超时/连接错误/5xx 重试，退避 1s→2s→4s
- [ ] AC2：4xx 不重试
- [ ] AC3：重试中 UI 显示"重试中"状态
- [ ] AC4：重试耗尽返回 ERROR
- [ ] AC5：单元测试覆盖重试逻辑

#### 执行要点
- tenacity 的 `@retry` 装饰器配置 `stop_after_attempt(3)` + `wait_exponential(multiplier=1, min=1, max=4)`
- UI 状态通过事件总线通知（ISSUE-ARC-02 完成后）

---

### ISSUE-LOG-03 · 优雅退出

- **里程碑 / 优先级**：M2 / P1
- **模块**：日志（LOG）
- **依赖需求**：无
- **关联改进项**：E-3

#### 用户故事
作为用户，我希望退出应用时资源正确释放，不残留进程。

#### 当前状态
**未实现**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) `os._exit(0)` 强制退出，跳过资源清理与 atexit 钩子。

#### 任务清单
- [ ] 移除 `App._quit` 末尾的 `os._exit(0)`，改为 `sys.exit(0)`
- [ ] 将 scheduler.stop、proxy.stop、tray.stop、keyboard.unhook_all 放在 `atexit.register` 或 try/finally
- [ ] 退出顺序：先停止调度器 → 停止代理 → 停止托盘 → 销毁窗口 → unhook 热键 → sys.exit
- [ ] 提供 `--force-exit` 命令行开关回退到 `os._exit`（应对 tkinter 死锁）
- [ ] 编写退出测试验证无残留进程

#### 验收标准
- [ ] AC1：退出后无残留进程
- [ ] AC2：scheduler/proxy/tray/keyboard 正确停止
- [ ] AC3：`--force-exit` 回退开关可用
- [ ] AC4：退出测试通过

#### 执行要点
- tkinter 主循环退出可能死锁，`--force-exit` 作为应急开关
- atexit 钩子执行顺序与注册顺序相反，注意依赖

---

## 3. M3 里程碑（v1.12.0）· 主题/UX/供应商扩展

> **里程碑目标**：莫奈色主题上线，UX 体验提升，供应商扩展机制建立
> **验收口径**：3 套莫奈色主题、主题编辑器、主题扩展接口、主题切换实时生效、快捷键可配置、供应商扩展机制、放弃纯黑 dark 主题

### ISSUE-ARC-02 · 事件总线

- **里程碑 / 优先级**：M3 / P1
- **模块**：架构（ARC）
- **依赖需求**：无
- **关联改进项**：A-2

#### 用户故事
作为维护者，我希望模块间通过事件解耦，新增功能无需改动多处。

#### 当前状态
**未实现**。[main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 使用 `set_refresh_callback` / `set_settings_callback` 等 6 个 setter 注入回调，耦合度高。

#### 任务清单
- [ ] 新建 `main/event_bus.py`，实现 `EventBus` 类，提供 `subscribe(event, handler)` / `publish(event, payload)` API
- [ ] 定义事件常量：`refresh_requested`、`settings_changed`、`account_added`、`account_deleted`、`account_updated`、`balance_updated`、`theme_changed`、`provider_registered`
- [ ] 事件含来源与负载字段
- [ ] 事件流转记录 DEBUG 日志
- [ ] 重构 MainWindow，移除 6 个 setter 回调，改用事件订阅
- [ ] 编写单元测试覆盖事件流转

#### 验收标准
- [ ] AC1：MainWindow 不再持有 setter 回调
- [ ] AC2：事件总线支持 subscribe/publish
- [ ] AC3：事件含来源与负载
- [ ] AC4：单元测试覆盖事件流转
- [ ] AC5：DEBUG 日志可追踪事件

#### 执行要点
- 事件总线实现需线程安全（后台线程 publish 到主线程订阅）
- 主线程 UI 更新通过 `main_window.after` 调度

---

### ISSUE-ARC-06 · Provider 接口抽象与注册表

- **里程碑 / 优先级**：M3 / P1
- **模块**：架构（ARC）
- **依赖需求**：ISSUE-PROV-01
- **关联改进项**：A-2

#### 用户故事
作为维护者，我希望新增供应商时只需实现接口并注册，无需修改核心代码。

#### 当前状态
**部分实现（硬编码注册）**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) `PROVIDERS` 字典硬编码 5 个 Provider，新增需改源码并重新打包。

#### 任务清单
- [ ] 保持 `BaseProvider` 抽象接口不变（已存在 ABC）
- [ ] 将 `PROVIDERS` 字典改造为运行时可扩展的注册表
- [ ] 提供 `register_provider(provider)` API（已存在，确认可用性）
- [ ] 运行时注册的 Provider 立即生效（无需重启）
- [ ] 注册成功后广播 `provider_registered` 事件，UI 更新 Provider 下拉列表
- [ ] 编写单元测试覆盖动态注册

#### 验收标准
- [ ] AC1：`register_provider` API 可用
- [ ] AC2：运行时注册的 Provider 立即生效（无需重启）
- [ ] AC3：单元测试覆盖动态注册

#### 执行要点
- 与 ISSUE-PROV-01 协同：PROV-01 实现配置化注册，本 Issue 提供底层注册表机制
- 注册表需线程安全（多线程加载 Provider 配置）

---

### ISSUE-ARC-04 · balance_checker 数字判断健壮化

- **里程碑 / 优先级**：M3 / P1
- **模块**：架构（ARC）
- **依赖需求**：无
- **关联改进项**：A-4

#### 用户故事
作为用户，我希望余额显示准确，不因负数或科学计数法误判。

#### 当前状态
**未实现（脆弱判断）**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 用 `total.replace(".","").isdigit()` 判断数字，负数、科学计数法、千分位均误判。

#### 任务清单
- [ ] 新增 `safe_float(s, default=0.0) -> float` 工具函数，用 `try/except float()` + 正则兜底
- [ ] 替换所有 `.replace(".","").isdigit()` 判断为 `safe_float`
- [ ] `is_available` 判断改为 `safe_float(total) > 0`
- [ ] 处理边界值：负数、科学计数法（1e-5）、千分位（1,000.50）、空字符串、None
- [ ] 编写单元测试覆盖边界值

#### 验收标准
- [ ] AC1：新增 `safe_float` 工具函数
- [ ] AC2：所有数字判断改用该函数
- [ ] AC3：负数、科学计数法、千分位正确处理
- [ ] AC4：单元测试覆盖边界值

#### 执行要点
- 千分位需先去除逗号再 `float()`
- 工具函数放置在 `main/utils.py` 或 `balance_checker.py` 顶部

---

### ISSUE-THM-01 · 主题数据模型与 ThemeManager

- **里程碑 / 优先级**：M3 / P2
- **模块**：主题（THM）
- **依赖需求**：ISSUE-ARC-02
- **关联改进项**：T-1

#### 用户故事
作为用户，我希望切换不同主题色，而非仅 dark/light。

#### 当前状态
**未实现**。customtkinter 仅支持 dark/light/system 三种内置主题；颜色硬编码散落各处。

#### 任务清单
- [ ] 新建 `main/theme_models.py`，定义 `ThemeLayer` 与 `Theme` dataclass 模型（字段见 PRD 第 7.1.2 节）
- [ ] 新建 `main/theme_manager.py`，实现 `ThemeManager` 单例
- [ ] App 持有 ThemeManager 实例
- [ ] 实现 `register(theme)` / `apply(name)` / `export(path)` / `import(path)` API
- [ ] `apply(name)` 后通过事件总线广播 `theme_changed` 事件
- [ ] UI 组件订阅事件后重新 `configure` 颜色
- [ ] 编写单元测试覆盖注册/应用/事件广播

#### 验收标准
- [ ] AC1：ThemeManager 单例可用
- [ ] AC2：Theme/ThemeLayer 数据模型完整
- [ ] AC3：register/apply API 可用
- [ ] AC4：apply 后广播 theme_changed 事件
- [ ] AC5：UI 组件订阅事件后实时更新颜色

#### 执行要点
- 数据模型字段参考 PRD 第 7.1.2 节（background/surface/primary/secondary/accent/text/text_muted/border/success/warning/danger）
- ThemeManager 单例避免全局变量，通过 App 注入
- 使用 dataclass 而非 pydantic（用户决策：配置保留 dataclass）

---

### ISSUE-THM-02 · 莫奈色主题内置

- **里程碑 / 优先级**：M3 / P2
- **模块**：主题（THM）
- **依赖需求**：ISSUE-THM-01
- **关联改进项**：T-2

> **v1.1 调整**：删除原依赖 ISSUE-ARC-03（配置 schema 迁移）。旧 `theme: "dark"` / `"light"` 配置改为运行时兼容处理，不依赖 schema 版本迁移机制。

#### 用户故事
作为用户，我希望应用提供莫奈风格的精美主题。

#### 当前状态
**未实现**。仅 dark/light，无莫奈色。用户明确要求放弃黑色主题。

#### 任务清单
- [ ] 创建 `themes/` 目录，存放内置主题 JSON 文件
- [ ] 实现 3 套莫奈色主题：睡莲（Water Lilies）、日出印象（Impression, Sunrise）、干草垛（Haystacks）
- [ ] 配色方案严格遵循 PRD 第 7.1.3 节
- [ ] 每套主题含亮色与暗色变体（莫奈深色，非纯黑）
- [ ] 放弃 customtkinter 原生纯黑 dark 主题
- [ ] **运行时兼容旧主题字段**：`load_config` 读取到旧 `theme: "dark"` 时映射为"莫奈·睡莲（暗变体）"，`theme: "light"` 映射为"莫奈·睡莲（亮变体）"；不依赖版本迁移机制，直接在加载时兼容处理
- [ ] 主题切换后对比度达标（WCAG AA）
- [ ] 编写测试验证主题加载、旧字段兼容与对比度

#### 验收标准
- [ ] AC1：3 套主题 JSON 文件存在于 themes/ 目录
- [ ] AC2：每套主题含亮/暗双变体
- [ ] AC3：主题切换后界面美观、对比度达标
- [ ] AC4：放弃纯黑 dark 主题
- [ ] AC5：旧 dark/light 配置运行时兼容映射到莫奈变体（无需版本迁移机制）

#### 执行要点
- 对比度检测可用 `wcag-contrast-ratio` 库或在线工具验证
- 旧主题字段兼容在 `load_config` 中直接处理，读取时判断 `theme` 值并映射，无需 pydantic 迁移

---

### ISSUE-THM-03 · 主题扩展接口（用户自定义主题）

- **里程碑 / 优先级**：M3 / P2
- **模块**：主题（THM）
- **依赖需求**：ISSUE-THM-01
- **关联改进项**：T-3

#### 用户故事
作为主题开发者，我希望通过 JSON 文件扩展自定义主题。

#### 当前状态
**未实现**。无主题扩展机制。

#### 任务清单
- [ ] ThemeManager 启动时扫描内置 `themes/` + 用户目录 `~/.deepseek-monitor/themes/`
- [ ] 用户主题同名覆盖内置主题
- [ ] JSON 文件格式错误时降级处理（跳过该主题 + WARN 日志）
- [ ] 支持运行时重新扫描（编辑器保存后立即生效，热加载）
- [ ] 编写单元测试覆盖扫描/加载/覆盖/降级

#### 验收标准
- [ ] AC1：用户主题目录被扫描
- [ ] AC2：JSON 格式主题文件可加载
- [ ] AC3：同名用户主题覆盖内置
- [ ] AC4：格式错误时降级处理
- [ ] AC5：热加载可用

#### 执行要点
- 热加载可用 `watchdog` 库监听目录变化（可选）
- 用户目录路径用 `os.path.expanduser("~/.deepseek-monitor/themes/")`

---

### ISSUE-THM-04 · 主题编辑器

- **里程碑 / 优先级**：M3 / P2
- **模块**：主题（THM）
- **依赖需求**：ISSUE-THM-01、ISSUE-THM-03
- **关联改进项**：8.6

#### 用户故事
作为用户，我希望可视化编辑主题颜色并实时预览。

#### 当前状态
**未实现**。无主题编辑器。

#### 任务清单
- [ ] 新建 `main/theme_editor_window.py`
- [ ] 可视化编辑 ThemeLayer 所有语义颜色（亮/暗双套编辑）
- [ ] 颜色选择使用 `tkinter.colorchooser.askcolor`
- [ ] 实时预览面板用 customtkinter 组件实时 `configure`（按钮/文本/卡片样例）
- [ ] 保存到用户主题目录，ThemeManager 重新扫描
- [ ] 导入/导出 JSON
- [ ] 重置为默认
- [ ] UI 布局参考 PRD 第 7.1.4 节（颜色矩阵 + 预览面板 + 操作按钮）
- [ ] 编写测试验证保存与加载

#### 验收标准
- [ ] AC1：可编辑 ThemeLayer 所有语义颜色
- [ ] AC2：亮/暗双套编辑
- [ ] AC3：实时预览（按钮/文本/卡片样例）
- [ ] AC4：保存到用户主题目录
- [ ] AC5：导入/导出 JSON
- [ ] AC6：重置为默认

#### 执行要点
- 颜色矩阵用 Grid 布局，每行一个语义颜色 + 颜色块按钮
- 预览面板实时响应颜色变化

---

### ISSUE-THM-05 · 主题切换实时生效

- **里程碑 / 优先级**：M3 / P2
- **模块**：主题（THM）
- **依赖需求**：ISSUE-THM-01
- **关联改进项**：T-1

#### 用户故事
作为用户，我希望切换主题后所有窗口立即更新颜色，无需重启。

#### 当前状态
**未实现**。当前主题切换仅改 `ctk.set_appearance_mode`，已打开的 Toplevel 窗口不更新。

#### 任务清单
- [ ] 所有 UI 组件（含主窗口、悬浮窗、对话框、图表窗口）订阅 `theme_changed` 事件
- [ ] 主题切换时遍历所有已存在的 Toplevel 重新着色
- [ ] matplotlib/pyqtgraph 图表颜色读取主题 token
- [ ] 维护已打开 Toplevel 窗口的弱引用列表，便于遍历
- [ ] 编写测试验证切换后无残留旧颜色

#### 验收标准
- [ ] AC1：切换主题后主窗口立即更新
- [ ] AC2：已打开的 Toplevel 窗口立即更新
- [ ] AC3：图表窗口颜色同步
- [ ] AC4：无残留旧颜色

#### 执行要点
- Toplevel 窗口列表用 `weakref.WeakSet` 避免内存泄漏
- 图表颜色需在绘图时读取主题 token，切换后重绘

---

### ISSUE-UX-02 · 快捷键可配置

- **里程碑 / 优先级**：M3 / P2
- **模块**：UX
- **依赖需求**：无
- **关联改进项**：U-2

#### 用户故事
作为用户，我希望自定义快捷键，避免与其他应用冲突。

#### 当前状态
**未实现（硬编码）**。快捷键硬编码（`Ctrl+R`、`Ctrl+Shift+B`），不可配置。

#### 任务清单
- [ ] `SettingsConfig` 新增 `hotkeys: dict[str, str]` 字段（action → keystr）
- [ ] 默认值：`toggle_window: "ctrl+shift+b"`、`manual_refresh: "ctrl+r"`
- [ ] 设置面板提供录入控件（捕获按键）
- [ ] 冲突检测：检测与系统/其他应用冲突并提示
- [ ] 重启后生效
- [ ] 编写测试验证配置加载与冲突检测

#### 验收标准
- [ ] AC1：默认快捷键不变
- [ ] AC2：设置面板可录入新快捷键
- [ ] AC3：冲突检测提示
- [ ] AC4：重启后生效

#### 执行要点
- `keyboard` 库的 `add_hotkey` 支持运行时修改，但需先 `unhook_all` 旧绑定
- 冲突检测可调用系统 API 或简单提示用户自行确认

---

### ISSUE-UX-04 · 焦点丢失行为可配置

- **里程碑 / 优先级**：M3 / P2
- **模块**：UX
- **依赖需求**：ISSUE-PFM-05
- **关联改进项**：U-4

#### 用户故事
作为用户，我希望控制失焦是否自动切悬浮窗，避免误触。

#### 当前状态
**未实现（强制开启）**。失焦自动切悬浮窗不可配置，可能干扰用户工作。

#### 任务清单
- [ ] `SettingsConfig` 新增 `auto_float_on_focus_loss: bool = False`
- [ ] 默认值 False（关闭），改为手动最小化
- [ ] 设置面板提供开关
- [ ] 开关切换立即生效（无需重启）
- [ ] 与 ISSUE-PFM-05 的事件驱动逻辑协同
- [ ] 编写测试验证开关生效

#### 验收标准
- [ ] AC1：默认关闭，需手动最小化
- [ ] AC2：设置面板提供开关
- [ ] AC3：开关切换立即生效

#### 执行要点
- 开关状态通过事件总线广播给 MainWindow
- 关闭时 `FocusOut` 事件不触发切悬浮窗

---

### ISSUE-UX-06 · 颜色集中管理

- **里程碑 / 优先级**：M3 / P2
- **模块**：UX
- **依赖需求**：ISSUE-THM-01
- **关联改进项**：U-6

#### 用户故事
作为主题开发者，我希望颜色集中在主题层定义，UI 组件不硬编码。

#### 当前状态
**未实现（硬编码散落）**。颜色硬编码：[floating_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/floating_window.py)、[main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 等。

#### 任务清单
- [ ] 移除所有 UI 组件中的硬编码颜色字面量
- [ ] 改用 `ThemeManager.current.surface` 等语义 token
- [ ] UI 组件订阅 `theme_changed` 事件，主题切换时重新 `configure(fg_color=...)`
- [ ] `set_appearance_mode` 仍用于控制亮/暗，但颜色由 ThemeLayer 提供
- [ ] 编写测试验证 UI 文件中无硬编码颜色字面量

#### 验收标准
- [ ] AC1：UI 文件中无硬编码颜色字面量
- [ ] AC2：颜色统一从 ThemeManager.current 读取
- [ ] AC3：主题切换实时生效

#### 执行要点
- 可用正则扫描 `#[0-9a-fA-F]{6}` 字面量辅助排查
- customtkinter 组件的 `fg_color` / `bg_color` 等参数改用语义 token

---

### ISSUE-PROV-01 · Provider 声明式配置注册

- **里程碑 / 优先级**：M3 / P1
- **模块**：供应商扩展（PROV）
- **依赖需求**：ISSUE-ARC-06
- **关联改进项**：A-2

#### 用户故事
作为用户/第三方开发者，我希望通过 JSON 配置文件注册新供应商，无需修改源码。

#### 当前状态
**未实现（硬编码）**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) `PROVIDERS` 字典硬编码 5 个 Provider，新增需改源码、重新打包。

#### 任务清单
- [ ] 创建 `providers/` 内置配置目录
- [ ] 定义 JSON 配置格式（参考 PRD 第 7.4.2 节）：name、label、description、api、parser、proxy_target
- [ ] 实现 `JsonPathProvider`：从 JSON 配置实例化，调用 API + json_path 解析
- [ ] 实现 `Jinja2Provider`：使用 Jinja2 模板转换响应（复杂场景）
- [ ] 引入 `jinja2` 依赖
- [ ] 配置加载后调用 `register_provider` 注册
- [ ] 注册成功后广播 `provider_registered` 事件，UI 更新 Provider 下拉列表
- [ ] 配置格式错误时降级处理 + WARN 日志
- [ ] 用户目录覆盖内置同名 Provider
- [ ] `python_module` 解析器：自定义 Python 模块（高级场景，需信任源，沙箱执行）
- [ ] 编写单元测试覆盖加载/注册/降级

#### 验收标准
- [ ] AC1：JSON 配置文件可加载并注册 Provider
- [ ] AC2：`json_path` 解析器支持简单路径提取
- [ ] AC3：注册后 UI 下拉列表立即更新
- [ ] AC4：配置格式错误时降级处理 + WARN 日志
- [ ] AC5：用户目录覆盖内置同名 Provider
- [ ] AC6：单元测试覆盖加载/注册/降级

#### 执行要点
- `python_module` 解析器存在代码执行风险，仅信任源启用 + 沙箱（参考 PRD 第 9.1 节风险）
- json_path 解析可用 `jmespath` 或简单 `dict.get` 链

---

### ISSUE-PROV-02 · Provider 自动发现

- **里程碑 / 优先级**：M3 / P2
- **模块**：供应商扩展（PROV）
- **依赖需求**：ISSUE-PROV-01
- **关联改进项**：A-2

#### 用户故事
作为用户，我希望放入新 Provider 配置文件后重启即可使用，无需额外操作。

#### 当前状态
**未实现**。Provider 需手动注册。

#### 任务清单
- [ ] 启动时扫描 `providers/` 与 `~/.deepseek-monitor/providers/` 目录下所有 `.json` 文件
- [ ] JSON 文件自动注册到 PROVIDERS 注册表
- [ ] 同名 Provider 后加载的覆盖先加载的
- [ ] 注册的 Provider 域名自动加入 usage_proxy 白名单（与 ISSUE-SEC-04 联调）
- [ ] 热加载（可选）：运行时监听目录变化（用 `watchdog` 库），新文件放入即注册
- [ ] 编写单元测试覆盖扫描与注册

#### 验收标准
- [ ] AC1：启动时自动扫描 providers 目录
- [ ] AC2：JSON 文件自动注册
- [ ] AC3：域名自动加入白名单
- [ ] AC4：热加载可用（可选，watchdog）
- [ ] AC5：单元测试覆盖扫描与注册

#### 执行要点
- 热加载为可选项，M3 可先实现启动扫描，热加载后续补充
- 白名单同步通过事件总线 `provider_registered` 事件通知 usage_proxy

---

### ISSUE-PROV-03 · Provider 配置校验与测试工具

- **里程碑 / 优先级**：M3 / P2
- **模块**：供应商扩展（PROV）
- **依赖需求**：ISSUE-PROV-01
- **关联改进项**：—

#### 用户故事
作为第三方开发者，我希望有工具校验我的 Provider 配置是否正确。

#### 当前状态
**未实现**。无配置校验工具。

#### 任务清单
- [ ] 实现 `python -m provider_validator <config.json>` 命令行工具
- [ ] 校验 JSON 格式合法性
- [ ] 校验必填字段完整性（name、label、api.url、parser）
- [ ] 校验 URL 可达性（可选 ping）
- [ ] 校验解析器语法正确性
- [ ] 提供 `--test` 模式：用测试 API Key 实际调用并验证解析结果
- [ ] 错误信息清晰可定位（行号、字段名、错误类型）
- [ ] 编写测试覆盖校验工具

#### 验收标准
- [ ] AC1：命令行校验工具可用
- [ ] AC2：校验 JSON 格式与字段完整性
- [ ] AC3：`--test` 模式实际调用验证
- [ ] AC4：错误信息清晰可定位

#### 执行要点
- 工具入口放在 `main/provider_validator.py`，支持 `python -m` 调用
- 校验规则与 ISSUE-PROV-01 的配置加载共享 schema

---

### ISSUE-PROV-04 · Provider SDK 文档与示例

- **里程碑 / 优先级**：M3 / P2
- **模块**：供应商扩展（PROV）
- **依赖需求**：ISSUE-PROV-01
- **关联改进项**：—

#### 用户故事
作为第三方开发者，我希望有文档指导我开发自定义 Provider。

#### 当前状态
**未实现**。无 Provider 开发文档。

#### 任务清单
- [ ] 编写 `docs/provider-sdk.md` 文档
- [ ] 文档内容：Provider 配置格式说明
- [ ] 文档内容：解析器类型说明（json_path / jinja2 / python_module）
- [ ] 文档内容：完整示例（3 个：简单 JSON、嵌套 JSON、自定义模块）
- [ ] 文档内容：调试技巧
- [ ] 文档内容：发布流程（提交到社区仓库或自托管）
- [ ] 创建 `providers/examples/` 目录，含 3 个示例配置
- [ ] 文档含截图/代码高亮

#### 验收标准
- [ ] AC1：文档完整，覆盖配置/解析器/示例/调试
- [ ] AC2：3 个示例配置可用
- [ ] AC3：文档含截图/代码高亮

#### 执行要点
- 文档遵循项目既有 README 风格
- 示例配置需通过 ISSUE-PROV-03 的校验工具验证

---

### ISSUE-PFM-08 · UsageHistory 连接复用 + WAL

- **里程碑 / 优先级**：M3 / P2
- **模块**：性能（PFM）
- **依赖需求**：无
- **关联改进项**：P-7

#### 用户故事
作为用户，我希望用量历史查询快速且写入不阻塞。

#### 当前状态
**未实现**。[usage_history.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_history.py) 每次操作新建 `sqlite3.connect`，无连接池，默认日志模式写入慢。

#### 任务清单
- [ ] `UsageHistory.__init__` 创建单例 `sqlite3.connect(check_same_thread=False)`
- [ ] 开启 WAL 模式：`PRAGMA journal_mode=WAL`
- [ ] 设置 `PRAGMA synchronous=NORMAL`
- [ ] 所有方法加 `threading.Lock` 保护写操作
- [ ] 退出时 `conn.close()`
- [ ] 编写测试验证并发写不损坏数据

#### 验收标准
- [ ] AC1：开启 WAL 与 NORMAL 同步
- [ ] AC2：单连接复用，写操作加锁
- [ ] AC3：并发写不损坏数据
- [ ] AC4：查询延迟下降（基准对比）

#### 执行要点
- WAL 模式下 SQLite 支持并发读，但写仍需串行（Lock 保护）
- 与 ISSUE-NET-02 联调确保多线程代理并发写安全

---

### ISSUE-CFG-02 · 配置原子写入 + 备份

- **里程碑 / 优先级**：M3 / P2
- **模块**：配置（CFG）
- **依赖需求**：无
- **关联改进项**：D-3

> **v1.1 调整**：删除原依赖 ISSUE-ARC-03。配置原子写入与备份机制独立实现，不依赖 schema 版本迁移。

#### 用户故事
作为用户，我希望配置写入失败时不丢失旧配置。

#### 当前状态
**未实现**。[config.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/config.py) `save_config` 直接覆盖写入，写入失败（磁盘满、权限）时旧配置丢失。

#### 任务清单
- [ ] `save_config` 写 `config.json.tmp` 临时文件
- [ ] 使用 `os.replace(tmp, config.json)` 原子操作替换
- [ ] 写入前若旧文件存在，复制到 `config.json.bak.{n}`，滚动保留 3 份
- [ ] 读取失败时自动回退到最近备份
- [ ] 编写单元测试覆盖写入失败与回退

#### 验收标准
- [ ] AC1：写入用 `os.replace` 原子操作
- [ ] AC2：保留最近 3 份 .bak
- [ ] AC3：读取失败回退到备份
- [ ] AC4：单元测试覆盖写入失败与回退

#### 执行要点
- `os.replace` 在 Windows 上是原子操作（同盘内）
- 备份滚动策略：最新的为 `.bak.0`，依次后移

---

## 4. M4 里程碑（v2.0.0）· 架构演进与功能

> **里程碑目标**：架构解耦，新功能上线，质量门禁生效
> **验收口径**：App 类拆分完成、CI 测试门禁生效、覆盖率 ≥ 85%

### ISSUE-ARC-01 · App 类拆分

- **里程碑 / 优先级**：M4 / P1
- **模块**：架构（ARC）
- **依赖需求**：ISSUE-ARC-02
- **关联改进项**：A-1

#### 用户故事
作为维护者，我希望 App 类职责清晰，便于测试与扩展。

#### 当前状态
**未实现**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) `App` 类职责过重：单实例锁 + IPC + 托盘 + 全局热键 + 主题 + 自启 + 悬浮窗管理 + 余额快照记录，约 460 行。

#### 任务清单
- [ ] 拆分 App 为编排器 + 8 个职责单一的管理器（参考 PRD 第 7.5 节）
- [ ] 新建 `main/managers/lifecycle_manager.py`：单实例锁 + IPC
- [ ] 新建 `main/managers/tray_manager.py`：系统托盘
- [ ] 新建 `main/managers/hotkey_manager.py`：全局热键
- [ ] 新建 `main/managers/theme_manager.py`：主题（含莫奈色扩展，与 ISSUE-THM-01 协同）
- [ ] 新建 `main/managers/autostart_manager.py`：开机自启
- [ ] 新建 `main/managers/window_manager.py`：主窗口 ↔ 悬浮窗
- [ ] 新建 `main/managers/scheduler_manager.py`：调度器 + 余额快照
- [ ] 新建 `main/managers/proxy_manager.py`：usage_proxy
- [ ] 每个 Manager 构造函数接收依赖（依赖注入，如 config、event_bus）
- [ ] App 仅负责实例化 Manager 与连接事件
- [ ] 编写回归测试确保现有功能行为不变
- [ ] 编写每个 Manager 的独立单元测试

#### 验收标准
- [ ] AC1：App 类行数减少 ≥ 60%
- [ ] AC2：每个 Manager 可独立实例化与测试
- [ ] AC3：App 仅负责实例化与连接
- [ ] AC4：现有功能行为不变（回归测试通过）
- [ ] AC5：依赖注入友好

#### 执行要点
- 拆分需保持现有功能行为不变，建议分阶段迁移（先抽离无依赖的 Manager）
- 依赖注入通过构造函数参数，避免服务定位器模式

---

### ISSUE-SEC-06 · API Key 指纹算法升级

- **里程碑 / 优先级**：M4 / P1
- **模块**：安全（SEC）
- **依赖需求**：无
- **关联改进项**：S-5

#### 用户故事
作为用户，我希望我的 API Key 指纹使用安全的哈希算法，避免弱哈希带来的合规风险。

#### 当前状态
**部分实现（弱算法）**。[usage_history.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_history.py) 使用 MD5 截断前 16 位 hex 作为 key 指纹。虽仅用于去标识，但 MD5 存在碰撞风险与"使用弱哈希"的合规污点。

#### 任务清单
- [ ] 新算法：`hashlib.sha256(api_key.encode()).hexdigest()[:32]`（截断前 32 字符）
- [ ] 双写过渡：升级后一段时间内同时存 MD5 与 SHA-256，保证历史数据可查
- [ ] 编写 `scripts/migrate_hash.py` 迁移脚本
- [ ] 迁移脚本遍历 `token_usage` 与 `balance_snapshots` 表，对历史数据用 MD5 反查原 key（需用户提供当前 key 列表）重算 SHA-256
- [ ] 或标记旧数据为 `legacy_hash` 不影响新数据查询
- [ ] `SettingsConfig` 新增 `hash_algorithm: str = "sha256"` 配置开关
- [ ] 编写单元测试覆盖新旧算法与迁移

#### 验收标准
- [ ] AC1：新写入数据使用 SHA-256 截断
- [ ] AC2：双写过渡期历史数据可查
- [ ] AC3：迁移脚本可用
- [ ] AC4：单元测试覆盖新旧算法与迁移

#### 执行要点
- 双写过渡期建议 1-2 个版本，过渡期结束后移除 MD5
- 迁移脚本需用户交互（提供 key 列表），非自动化

---

### ISSUE-QA-01 · CI 测试 + 覆盖率门禁

- **里程碑 / 优先级**：M4 / P1
- **模块**：质量保障（QA）
- **依赖需求**：无
- **关联改进项**：Q-1、Q-2

#### 用户故事
作为维护者，我希望 PR 合并前自动跑测试，防止回归。

#### 当前状态
**未实现**。[.github/workflows/release.yml](file:///d:/#MCP-Serve/deepseek-balance-monitor/.github/workflows/release.yml) 仅构建，不跑测试。无覆盖率统计。

#### 任务清单
- [ ] 新建 `.github/workflows/test.yml` workflow
- [ ] push/PR 时跑 `pytest --cov=main --cov-report=xml`
- [ ] 覆盖率初始阈值 70%，M4 后 85%
- [ ] runner 使用 Windows（项目为 Windows 优先）
- [ ] 集成 Codecov 或 PR 评论显示覆盖率
- [ ] CI 环境无显示，用虚拟显示或 mock UI 层处理 tkinter
- [ ] 编写测试配置文件 `pytest.ini` 或 `pyproject.toml`

#### 验收标准
- [ ] AC1：push/PR 触发测试
- [ ] AC2：覆盖率 < 70% 失败
- [ ] AC3：Windows runner
- [ ] AC4：覆盖率报告显示在 PR 评论

#### 执行要点
- tkinter 在 CI 无显示环境下需 `xvfb` 或 mock，Windows runner 可用 `pyvirtualdisplay`
- 覆盖率阈值渐进提升，避免一次性卡死合并

---

### ISSUE-PKG-01 · 打包模式优化

- **里程碑 / 优先级**：M4 / P1
- **模块**：打包分发（PKG）
- **依赖需求**：无
- **关联改进项**：R-1

#### 用户故事
作为用户，我希望应用启动快，安装包不过大。

#### 当前状态
**未实现（onefile 慢）**。PyInstaller `--onefile` 模式，启动慢（解压到临时目录）。

#### 任务清单
- [ ] 优先实现 `--onedir` 模式，启动更快（预计降 30-50%）
- [ ] 评估 Nuitka 备选：`nuitka --standalone --onefile --enable-plugin=tk-inter main.py` 编译为原生代码
- [ ] CI 中对比两种模式启动基准
- [ ] 更新 `release.yml` 工作流支持新模式
- [ ] 编写打包测试验证启动时间

#### 验收标准
- [ ] AC1：onedir 模式启动时间下降 ≥ 30%
- [ ] AC2：或 Nuitka 编译成功
- [ ] AC3：CI 中对比基准

#### 执行要点
- onedir 模式安装包较大但启动快，权衡用户需求
- Nuitka 编译时间长，CI 需缓存中间产物

---

### ISSUE-UX-01 · 国际化（i18n）

- **里程碑 / 优先级**：M4 / P2
- **模块**：UX
- **依赖需求**：无
- **关联改进项**：U-1

#### 用户故事
作为非中文用户，我希望应用支持多语言切换。

#### 当前状态
**未实现**。全中文硬编码，无 i18n。

#### 任务清单
- [ ] 引入 `gettext` 标准库
- [ ] 全项目 UI 字符串改用 `_("...")` 包裹
- [ ] 生成 `locales/zh_CN/LC_MESSAGES/app.po`（默认），后续扩展 `en`
- [ ] 设置面板增加语言切换（重启生效）
- [ ] 编写测试验证字符串包裹完整性

#### 验收标准
- [ ] AC1：全项目 UI 字符串改用 `_("...")`
- [ ] AC2：提供 zh_CN 与 en 语言包
- [ ] AC3：设置面板可切换语言（重启生效）
- [ ] AC4：切换后所有界面文本更新

#### 执行要点
- 字符串包裹工作量大，建议用脚本辅助扫描硬编码中文字符串
- 语言包编译为 `.mo` 文件，运行时加载

---

### ISSUE-QA-02 · Lint + 类型检查

- **里程碑 / 优先级**：M4 / P2
- **模块**：质量保障（QA）
- **依赖需求**：ISSUE-QA-01
- **关联改进项**：Q-3

#### 用户故事
作为维护者，我希望代码风格统一，类型错误早发现。

#### 当前状态
**未实现**。无 Lint、无类型检查。

#### 任务清单
- [ ] 引入 `ruff` 替代 flake8+black+isort
- [ ] 引入 `mypy` 渐进式收紧（先宽松 `--ignore-missing-imports`，逐步 `--strict`）
- [ ] 配置 `pre-commit` 本地钩子
- [ ] CI 中加入 ruff 与 mypy 检查，失败阻断合并
- [ ] 编写 `pyproject.toml` 配置 ruff 与 mypy

#### 验收标准
- [ ] AC1：ruff 检查通过
- [ ] AC2：mypy 渐进式收紧
- [ ] AC3：pre-commit 钩子
- [ ] AC4：CI 失败阻断合并

#### 执行要点
- ruff 配置参考官方推荐规则集（`E`、`F`、`I`、`N` 等）
- mypy 收紧分阶段：先 `--ignore-missing-imports`，再 `--disallow-untyped-defs`

---

## 5. M5+ 里程碑（v2.x）· 技术栈迁移与新功能

> **里程碑目标**：技术栈迁移（需用户审批）与新功能上线
> **验收口径**：PyQt6 迁移阶段 1 完成（需用户审批）、报告导出、多币种聚合可用

### ISSUE-FEAT-03 · 报告导出

- **里程碑 / 优先级**：M5+ / P3
- **模块**：新功能（FEAT）
- **依赖需求**：无
- **关联改进项**：F-3

#### 用户故事
作为用户，我希望导出余额历史与用量统计报告。

#### 当前状态
**未实现**。无报告导出功能。

#### 任务清单
- [ ] 引入 `reportlab` 依赖（PDF 生成）
- [ ] 支持 PDF / CSV / HTML 三种格式导出
- [ ] 报告内容：余额曲线图、用量柱状图、汇总表
- [ ] CSV 使用标准库 `csv` 模块
- [ ] HTML 使用模板引擎或字符串拼接
- [ ] 设置面板或菜单提供导出入口
- [ ] 编写测试验证导出文件格式正确

#### 验收标准
- [ ] AC1：可导出 PDF（含图表）
- [ ] AC2：可导出 CSV
- [ ] AC3：可导出 HTML
- [ ] AC4：报告含余额曲线、用量柱状图、汇总表

#### 执行要点
- PDF 图表需将 matplotlib 图形嵌入 reportlab
- 导出过程异步执行，避免阻塞 UI

---

### ISSUE-FEAT-04 · 多币种聚合

- **里程碑 / 优先级**：M5+ / P3
- **模块**：新功能（FEAT）
- **依赖需求**：无
- **关联改进项**：F-4

#### 用户故事
作为用户，我希望不同币种余额按汇率换算为单一基准货币显示总额。

#### 当前状态
**未实现**。多币种余额分别显示，无换算。

#### 任务清单
- [ ] 接入汇率 API（如 exchangerate-api）
- [ ] `SettingsConfig` 新增 `base_currency: str = "CNY"`
- [ ] 汇率定时刷新（每日或每启动时）
- [ ] 主窗口/悬浮窗显示换算后总额
- [ ] 支持切换基准货币
- [ ] 编写测试验证换算逻辑

#### 验收标准
- [ ] AC1：支持 CNY/USD 互转
- [ ] AC2：汇率定时刷新
- [ ] AC3：主窗口/悬浮窗显示换算总额
- [ ] AC4：可切换基准货币

#### 执行要点
- 汇率 API 有免费额度限制，需缓存汇率数据
- 换算精度保留 2 位小数

---

### ISSUE-MIGRATE-PyQt6 · 技术栈迁移评估与启动

- **里程碑 / 优先级**：M5+ / P3（需用户审批后启动）
- **模块**：架构（ARC）
- **依赖需求**：M4 完成
- **关联改进项**：PRD 第 7.6 节

#### 用户故事
作为维护者，我希望评估并启动 PyQt6 迁移，提升 UI 性能与可维护性。

#### 当前状态
**未实现**。当前使用 customtkinter（基于 Tkinter），主题能力有限，维护放缓。

#### 任务清单
- [ ] M3 完成后评估是否启动 M4 迁移（决策点）
- [ ] 用户审批后启动迁移
- [ ] 主方案：PyQt6/PySide6 渐进迁移（UI 重写，业务逻辑复用）
- [ ] 备选：Tauri 完全重写（追求极致性能时）
- [ ] 长期分支 + 分模块切换策略
- [ ] 阶段 1：核心窗口迁移（主窗口、悬浮窗）
- [ ] 编写迁移前后性能与体验对比报告

#### 验收标准
- [ ] AC1：用户审批后启动
- [ ] AC2：阶段 1 核心窗口迁移完成
- [ ] AC3：迁移前后性能对比报告

#### 执行要点
- **此 Issue 需用户审批后方可实施**，不可擅自启动
- 迁移期间双 UI 维护成本高，建议分模块切换而非长期分支并行
- 参考改进方案第 12 章详细迁移步骤

---

## 6. 非功能需求与风险跟踪

> 非功能需求作为硬性指标，贯穿各里程碑验收；风险跟踪 Issue 用于持续监控关键风险。

### NFR-PERF-01~05 · 性能指标门禁

- **适用里程碑**：M2 起强制
- **关联 Issue**：ISSUE-PFM-01~08、ISSUE-PFM-07

| 编号 | 指标 | 目标值 | 测量方式 |
|------|------|--------|----------|
| NFR-PERF-01 | 冷启动时间 | < 300ms（10 账户） | `python -X importtime` + 人工计时 |
| NFR-PERF-02 | 闲置内存 | < 50MB | psutil 采样 5 分钟 |
| NFR-PERF-03 | 闲置 CPU | < 0.1% | psutil 采样 5 分钟平均 |
| NFR-PERF-04 | 刷新延迟 | 10 账户 < 5s | scheduler 埋点 |
| NFR-PERF-05 | 性能回归门禁 | CI 回归 > 10% 告警 | CI 自动执行 |

#### 任务清单
- [ ] M2 验收时逐项测量并记录
- [ ] 每次发版前回归验证
- [ ] 不达标时阻断发版

---

### NFR-SEC-01~03 · 安全指标门禁

- **适用里程碑**：M1 起强制
- **关联 Issue**：ISSUE-SEC-01/04/07

| 编号 | 指标 | 目标值 | 测量方式 |
|------|------|--------|----------|
| NFR-SEC-01 | 凭证存储 | API Key 100% 加密存储，config.json 无明文 | 文件检查 + 单元测试 |
| NFR-SEC-02 | 服务鉴权 | usage_proxy 100% 鉴权 | 渗透测试 + 单元测试 |
| NFR-SEC-03 | 日志脱敏 | 日志中不含 API Key 明文，仅含 hash | 日志文件扫描 |

#### 任务清单
- [ ] M1 验收时逐项测量
- [ ] 安全审计通过后方可发版

---

### NFR-USA-01~03 · 可用性指标门禁

- **适用里程碑**：M2 起强制（NFR-USA-01 现状已满足）
- **关联 Issue**：ISSUE-NET-03、ISSUE-LOG-03

| 编号 | 指标 | 目标值 | 测量方式 |
|------|------|--------|----------|
| NFR-USA-01 | 单实例保证 | 同一时刻仅一个进程运行 | 双开测试 |
| NFR-USA-02 | 异常不崩溃 | 单账户查询失败不影响其他账户与 UI | 异常注入测试 |
| NFR-USA-03 | 资源正确释放 | 退出后无残留进程与锁 | 退出后任务管理器检查 |

---

### NFR-COMP-01~02 · 兼容性指标门禁

- **适用里程碑**：始终
- **关联 Issue**：ISSUE-QA-01

| 编号 | 指标 | 目标值 | 测量方式 |
|------|------|--------|----------|
| NFR-COMP-01 | Windows 版本 | 支持 Windows 10/11 | 多版本虚拟机测试 |
| NFR-COMP-02 | Python 版本 | 支持 Python 3.10+ | 多版本 CI 矩阵 |

---

### NFR-MAINT-01~02 · 可维护性指标门禁

- **适用里程碑**：M4 起强制
- **关联 Issue**：ISSUE-QA-01、ISSUE-QA-02

| 编号 | 指标 | 目标值 | 测量方式 |
|------|------|--------|----------|
| NFR-MAINT-01 | 测试覆盖率 | ≥ 70%（M4 前）/ ≥ 85%（M4 后） | pytest-cov |
| NFR-MAINT-02 | 代码风格 | ruff 与 mypy 检查通过 | CI |

---

### ISSUE-RISK-01 · 关键风险跟踪

- **适用里程碑**：贯穿全程
- **关联 Issue**：所有含风险的 Issue

#### 风险清单

| 风险 | 概率 | 影响 | 缓解策略 | 关联 Issue |
|------|------|------|----------|------------|
| DPAPI 加密导致跨用户迁移困难 | 中 | 中 | 提供重新输入 Key 流程 | ISSUE-SEC-01 |
| 旧版明文配置无法自动迁移 | 中 | 中 | 弹窗提示用户重新输入 Key | ISSUE-SEC-01 |
| 主题切换实时生效不完整 | 中 | 中 | 全组件订阅事件 + 测试 | ISSUE-THM-05 |
| customtkinter 自定义颜色边界 | 中 | 中 | 验证关键组件，必要时换栈 | ISSUE-THM-01 |
| CI 环境无 tkinter 显示 | 高 | 中 | 虚拟显示或 mock | ISSUE-QA-01 |
| PyQt6 迁移期双 UI 维护 | 高 | 高 | 长期分支 + 分模块切换 | ISSUE-MIGRATE-PyQt6 |
| 自定义 Provider 配置漏洞 | 中 | 中 | 配置校验 + 白名单 | ISSUE-PROV-01 |
| python_module 解析器代码执行 | 低 | 高 | 仅信任源启用 + 沙箱 | ISSUE-PROV-01 |

> **v1.1 调整**：移除与已删除 Issue 相关的风险（配置迁移丢失数据、自动更新被中间人攻击）。

#### 任务清单
- [ ] 每个里程碑验收时复查风险清单
- [ ] 新增风险时更新本 Issue
- [ ] 高影响风险（PyQt6 迁移）需用户审批缓解方案

---

## 7. Issue 依赖关系图

### 7.1 关键依赖链

```
ISSUE-LOG-01 (统一日志)
├── ISSUE-LOG-02 (日志分级)
└── ISSUE-SEC-07 (日志脱敏)

ISSUE-SEC-01 (DPAPI 加密，无依赖)
└── ISSUE-SEC-04 (代理鉴权) ── 依赖 ── ISSUE-PROV-02 (白名单同步)

ISSUE-SEC-05 (凭证源，无依赖)

ISSUE-PFM-03 (线程池)
├── ISSUE-PFM-04 (Session 复用)
│   └── ISSUE-NET-03 (重试退避)
└── ISSUE-NET-01 (任务取消)

ISSUE-SEC-04 (代理鉴权)
└── ISSUE-PFM-06 (流式解析)

ISSUE-ARC-02 (事件总线)
├── ISSUE-THM-01 (ThemeManager)
│   ├── ISSUE-THM-02 (莫奈色，运行时兼容旧主题字段)
│   ├── ISSUE-THM-03 (主题扩展)
│   ├── ISSUE-THM-04 (主题编辑器)
│   ├── ISSUE-THM-05 (实时生效)
│   └── ISSUE-UX-06 (颜色集中)
└── ISSUE-ARC-01 (App 拆分)

ISSUE-ARC-06 (Provider 注册表)
└── ISSUE-PROV-01 (声明式配置)
    ├── ISSUE-PROV-02 (自动发现)
    ├── ISSUE-PROV-03 (校验工具)
    └── ISSUE-PROV-04 (SDK 文档)

ISSUE-PFM-05 (事件驱动焦点)
└── ISSUE-UX-04 (失焦可配置)

ISSUE-QA-01 (CI 测试)
├── ISSUE-QA-02 (Lint)
└── ISSUE-PFM-07 (性能基准)
```

> **v1.1 调整**：
> - 移除 ISSUE-ARC-03 依赖链（原为 SEC-01/SEC-05/THM-02/CFG-02/NET-04 的前置依赖）
> - 移除 ISSUE-SEC-02（旧版明文配置自动迁移）依赖链
> - 移除 ISSUE-UX-03 → ISSUE-FEAT-01 依赖链
> - ISSUE-SEC-01、ISSUE-SEC-05、ISSUE-THM-02、ISSUE-CFG-02 依赖改为"无"或仅依赖 ISSUE-THM-01

### 7.2 别名映射

| PRD 需求 ID | 对应 Issue ID | 说明 |
|-------------|---------------|------|
| FR-CFG-03 | ISSUE-SEC-04 | 凭证源显式管理（active_key_sources 字段） |
| FR-QA-03 | ISSUE-PFM-07 | 性能基准 CI 门禁 |

> **v1.1 调整**：移除 FR-CFG-01 → ISSUE-ARC-03 别名映射（两者均已删除）。

---

## 8. 执行建议

### 8.1 推荐执行顺序

1. **M1 安全基线**
   - ISSUE-LOG-01 → ISSUE-LOG-02 → ISSUE-SEC-07
   - ISSUE-SEC-01（无依赖，可先行；含旧版明文配置检测提示）
   - ISSUE-SEC-04（白名单接口先行，PROV-02 联调待 M3）
   - ISSUE-SEC-05、ISSUE-ARC-05（独立可并行）

2. **M2 性能并发**
   - ISSUE-PFM-01、ISSUE-PFM-02（独立可并行）
   - ISSUE-PFM-03 → ISSUE-PFM-04 → ISSUE-NET-03
   - ISSUE-PFM-03 → ISSUE-NET-01
   - ISSUE-SEC-04 → ISSUE-PFM-06
   - ISSUE-NET-02（与 ISSUE-PFM-08 联调）
   - ISSUE-LOG-03、ISSUE-PFM-05（独立）

3. **M3 主题/UX/供应商**
   - ISSUE-ARC-02（事件总线，多 Issue 依赖）
   - ISSUE-THM-01 → ISSUE-THM-02/03/04/05
   - ISSUE-ARC-06 → ISSUE-PROV-01 → ISSUE-PROV-02/03/04
   - ISSUE-PFM-05 → ISSUE-UX-04
   - ISSUE-CFG-02（独立）

4. **M4 架构演进**
   - ISSUE-ARC-02 → ISSUE-ARC-01（App 拆分依赖事件总线）
   - ISSUE-QA-01 → ISSUE-QA-02、ISSUE-PFM-07
   - ISSUE-SEC-06、ISSUE-PKG-01、ISSUE-UX-01（独立）

5. **M5+ 新功能**（需用户审批）
   - ISSUE-MIGRATE-PyQt6（用户审批后启动）
   - ISSUE-FEAT-03、ISSUE-FEAT-04（独立可并行）

> **v1.1 调整**：
> - M1 不再以 ISSUE-ARC-03 为起点（已删除），SEC-01 无依赖可直接开始
> - M3 移除 ISSUE-UX-03 ↔ ISSUE-FEAT-01 协同（两者均已删除）
> - M4 移除 ISSUE-NET-04、ISSUE-PKG-02（均已删除）

### 8.2 并行执行提示

- 同一里程碑内无依赖关系的 Issue 可并行开发
- 不同里程碑的 Issue 原则上不并行（避免基础未稳）
- 跨 Issue 协作通过事件总线（ISSUE-ARC-02）解耦

### 8.3 测试要求

依据用户偏好，每个 Issue 完成后需进行：
- **冒烟测试**：核心流程可用
- **单元测试**：覆盖 Issue 内新增逻辑
- **集成测试**：与依赖 Issue 联调
- **回归测试**：现有功能不破坏

测试通过后方可执行 Git commit。

---

**文档结束**

> 本 Issue 清单基于 PRD v1.3 拆分，与改进方案 v1.2 配套使用。
> 每个 Issue 完成后在任务清单与验收标准中勾选，并更新本文档版本号。
> 技术栈迁移 Issue（ISSUE-MIGRATE-PyQt6）需用户审批后方可实施。
