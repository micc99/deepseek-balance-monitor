# DeepSeek 余额监控 · 产品需求文档（PRD）

> **文档版本**：v1.3
> **文档日期**：2026-08-07
> **适用产品**：deepseek-balance-monitor（当前发布版本 v1.9.3）
> **文档目的**：作为产品规划与 AI 协作交接的权威需求基线，指导 v1.10 ~ v2.x 版本的研发推进
> **配套文档**：[deepseek-balance-monitor_改进方案_v1.2_2026-08-07.md](file:///d:/#MCP-Serve/deepseek-balance-monitor/deepseek-balance-monitor_改进方案_v1.2_2026-08-07.md)（以下简称"改进方案"）
> **语言**：简体中文（技术术语保留英文原文）
> **v1.3 变更说明**：
> - 基于用户决策删除以下需求（用户无对应需求）：
>   - FR-SEC-02 旧版明文配置自动迁移（用户不需要自动迁移）
>   - FR-ARC-03 配置 schema + 版本 + 迁移（用户不引入 pydantic 迁移机制，配置保留 dataclass）
>   - FR-CFG-01 配置 schema/版本/迁移（FR-ARC-03 别名，一并删除）
>   - FR-UX-03 系统通知（用户不需要系统通知）
>   - FR-UX-05 可访问性（用户不考虑视障人士支持）
>   - FR-PKG-02 自动更新（用户不考虑自动更新，均为手动更新）
>   - FR-FEAT-01 阈值告警（用户不做告警）
>   - FR-FEAT-02 用量预算（用户不做超额告警）
>   - FR-NET-04 多 Provider 代理路由（用户无本地代理多路由需求，维持单 Provider 代理）
> - 连锁调整：FR-SEC-01/05、FR-THM-02、FR-CFG-02 依赖去除（不再依赖 FR-ARC-03）
> - 配置 Schema 设计去除 version 字段，保留 dataclass 方式
> - 独立需求由 52 项减少至 43 项，标题项由 55 个减少至 46 个
> - v1.2 的移除 MCP Server 功能变更保留

---

## 0. 文档使用说明（AI 交接必读）

### 0.1 文档定位

本 PRD 是产品视角的**权威需求基线**，描述"做什么"与"做到什么程度"。技术实现细节、迁移步骤、风险分析等"怎么做"的内容，统一在改进方案中。两份文档通过**需求 ID（FR-xxx / NFR-xxx）**与**改进项 ID（S-x / P-x / A-x ...）**相互引用。

### 0.2 ID 命名规范

| 前缀 | 含义 | 示例 |
|------|------|------|
| `FR-SEC-xx` | 功能需求 · 安全模块 | FR-SEC-01 |
| `FR-PFM-xx` | 功能需求 · 性能模块 | FR-PFM-01 |
| `FR-ARC-xx` | 功能需求 · 架构模块 | FR-ARC-01 |
| `FR-NET-xx` | 功能需求 · 并发网络模块 | FR-NET-01 |
| `FR-LOG-xx` | 功能需求 · 日志模块 | FR-LOG-01 |
| `FR-CFG-xx` | 功能需求 · 配置模块 | FR-CFG-02 |
| `FR-UX-xx` | 功能需求 · UX 模块 | FR-UX-01 |
| `FR-THM-xx` | 功能需求 · 主题模块 | FR-THM-01 |
| `FR-PROV-xx` | 功能需求 · 供应商扩展模块 | FR-PROV-01 |
| `FR-QA-xx` | 功能需求 · 质量保障模块 | FR-QA-01 |
| `FR-PKG-xx` | 功能需求 · 打包分发模块 | FR-PKG-01 |
| `FR-FEAT-xx` | 功能需求 · 新功能模块 | FR-FEAT-03 |
| `NFR-xxx` | 非功能需求 | NFR-PERF-01 |

### 0.3 AI 接手指引

接手本项目的 AI 应按以下顺序阅读：

1. **第 1 章 产品概述** — 理解产品定位与目标用户
2. **第 2 章 项目现状** — 了解当前实现与技术债
3. **第 3 章 目标与成功指标** — 明确验收口径
4. **第 4 章 需求总览矩阵** — 全景视图
5. **第 5 章 功能需求** — 按模块逐条阅读，每条含用户故事、当前状态、详细描述、验收标准、优先级、关联改进项、所属里程碑、依赖需求
6. **第 6 章 非功能需求** — 性能/安全/可用性硬性指标
7. **第 7 章 系统设计要点** — 主题系统、配置模型、事件总线、Provider 扩展等关键设计
8. **第 8 章 里程碑规划** — 了解交付节奏
9. **第 9 章 风险与依赖** — 实施前必读
10. **第 10 章 术语表与参考** — 统一用语

**需求结构说明**：

每条需求统一包含以下字段：
- **需求 ID**：唯一标识
- **用户故事**：作为...我希望...以便...
- **当前状态**：现状描述（已有功能/问题/痛点），标注"现状已实现/部分实现/未实现"
- **详细描述**：技术细节、交互流程、边界条件、错误处理
- **验收标准**：AC1~ACn 编号条目，可逐项核对
- **优先级**：P0/P1/P2/P3
- **关联改进项**：改进方案中的 ID
- **所属里程碑**：M1~M5+
- **依赖需求**：前置需求 ID

**执行任务时的引用规则**：
- 实现某需求时，在代码注释或 commit message 中引用需求 ID（如 `实现 FR-SEC-01`）
- 验收时严格按"验收标准"条目逐项核对
- 跨模块协作时，通过"关联改进项"与"依赖需求"字段追溯

### 0.4 优先级与里程碑约定

| 优先级 | 含义 | 默认里程碑 |
|--------|------|------------|
| **P0** | 紧急，安全/数据风险 | M1 |
| **P1** | 重要，架构债/性能瓶颈/稳定性 | M1~M2 |
| **P2** | 体验优化 | M2~M3 |
| **P3** | 长期演进，重大新功能/技术栈迁移 | M4+ |

---

## 1. 产品概述

### 1.1 产品定位

**DeepSeek 余额监控**是一款 Windows 桌面常驻型工具，聚合管理多家 AI API 平台的账户余额与用量，通过主窗口、桌面悬浮窗、系统托盘三种形态为用户提供**实时、低打扰、近零占用**的余额感知能力，并内置本地反向代理，支撑 token 用量统计。

### 1.2 目标用户

| 用户画像 | 核心诉求 |
|----------|----------|
| 多平台 AI API 重度使用者 | 一处查看多平台余额，避免分散登录各控制台 |
| AI 编程开发者（使用 Cursor/Trae/Cline 等） | 通过本地代理统计 token 用量，掌握 API 成本 |
| 关注成本的个人开发者 | 查看历史消耗趋势 |
| 注重桌面体验的用户 | 悬浮窗常驻不挡视线；启动快、不卡机 |

### 1.3 核心价值

1. **聚合**：一个应用管理 5+ AI 平台余额，未来可扩展更多供应商
2. **实时**：定时刷新 + 手动刷新，悬浮窗常驻可见
3. **低打扰**：失焦自动收起、托盘驻留、全局热键唤起
4. **可观测**：余额曲线、用量柱状图、历史快照
5. **近零负担**：闪电启动、低内存、低 CPU
6. **可扩展**：供应商、主题、快捷键均可扩展

### 1.4 产品愿景

成为 AI API 时代的"余额管家"：让用户对多平台 API 成本有**瞬时、可信、可洞察**的感知，并通过主题化、可扩展的形态长期陪伴用户。

---

## 2. 项目现状（交接上下文）

### 2.1 当前版本与技术栈

| 项 | 内容 |
|----|------|
| 版本 | v1.9.3 |
| 语言 | Python 3.10+ |
| UI 框架 | customtkinter（基于 Tkinter） |
| 系统集成 | pystray（托盘）、keyboard（全局热键） |
| 网络 | requests、http.client（usage_proxy） |
| 持久化 | SQLite（usage.db）、JSON（config.json） |
| 可视化 | matplotlib |
| 平台 | Windows（README 提及跨平台构建，但实际仅 Windows 完整可用） |
| 规模 | 约 20 个源文件 |

### 2.2 当前文件结构

```
deepseek-balance-monitor/
├── main/
│   ├── main.py              # 应用入口与 App 编排器
│   ├── main_window.py       # 主窗口
│   ├── floating_window.py   # 悬浮窗
│   ├── balance_checker.py   # 多 Provider 余额查询（硬编码 5 个 Provider）
│   ├── scheduler.py         # 定时刷新调度器
│   ├── config.py            # 配置读写与数据模型
│   ├── animations.py        # 波纹动画
│   ├── instance_lock.py     # 单实例互斥锁
│   ├── error_logger.py      # 异常日志
│   ├── usage_history.py     # SQLite 用量历史
│   ├── usage_logger.py      # 用量记录
│   ├── usage_proxy.py       # 本地反向代理
│   ├── edit_account_dialog.py
│   ├── settings_dialog.py
│   ├── account_row.py
│   ├── usage_curve_window.py
│   ├── usage_bar_window.py
│   ├── requirements.txt
│   └── tests/
├── .github/workflows/release.yml
├── README.md
└── deepseek-balance-monitor_改进方案_v1.2_2026-08-07.md
```

### 2.3 已实现功能（现状基线）

- ✅ 多平台余额查询（DeepSeek、硅基流动、Moonshot、OpenRouter、智谱AI）
- ✅ 主窗口账户管理（增删改查、拖拽排序）
- ✅ 桌面悬浮窗（无边框、置顶、可拖拽、双击恢复、右键菜单）
- ✅ 系统托盘驻留
- ✅ 定时刷新（可配置间隔，最短 10 秒）
- ✅ 开机自启（Windows 启动项快捷方式）
- ✅ 深/浅主题切换（customtkinter 原生）
- ✅ 波纹点击动画
- ✅ 单实例互斥 + IPC 唤起
- ✅ 全局热键 `Ctrl+Shift+B` 切换窗口
- ✅ 本地反向代理统计 token 用量
- ✅ SQLite 用量历史 + 余额快照
- ✅ 余额曲线窗口、用量柱状图窗口

### 2.4 核心技术债（详见改进方案）

1. **安全**：API Key 明文存储；本地代理无鉴权；静默读取第三方凭证
2. **性能**：启动同步加载 matplotlib；调度器每账户新建线程；焦点 500ms 轮询
3. **架构**：App 类职责过重；MainWindow 回调注入耦合
4. **主题**：仅 dark/light；颜色硬编码散落各处；不满足莫奈色需求
5. **可观测**：每异常一文件无轮转；无日志分级；`os._exit` 跳过清理
6. **供应商扩展**：Provider 硬编码于 balance_checker.py 的 PROVIDERS 字典，新增需改源码

---

## 3. 产品目标与成功指标

### 3.1 产品目标（按里程碑）

| 里程碑 | 版本 | 目标 |
|--------|------|------|
| M1 | v1.10.0 | 消除 P0 安全风险，建立日志基线 |
| M2 | v1.11.0 | 达成闪电启动 + 近零占用性能指标 |
| M3 | v1.12.0 | 莫奈色主题上线，UX 体验提升，供应商扩展机制建立 |
| M4 | v2.0.0 | 架构解耦，质量门禁生效 |
| M5+ | v2.x | 技术栈迁移（需用户审批） |

### 3.2 成功指标（可量化）

| 指标类别 | 指标 | 目标值 | 验收方式 |
|----------|------|--------|----------|
| 性能 | 冷启动时间 | < 300ms | `python -X importtime` + 人工计时 |
| 性能 | 热启动时间 | < 150ms | 缓存状态启动计时 |
| 性能 | 闲置内存 | < 50MB | psutil 采样 5 分钟 |
| 性能 | 闲置 CPU | < 0.1% | psutil 采样 5 分钟平均 |
| 性能 | 10 账户单次刷新延迟 | < 5s | scheduler 埋点 |
| 安全 | API Key 存储加密率 | 100% | config.json 检查无明文 |
| 安全 | 本地代理鉴权覆盖率 | 100% | 渗透测试 |
| 质量 | 单元测试覆盖率 | ≥ 70%（初始）/ ≥ 85%（M4 后） | pytest-cov |
| 质量 | CI 门禁生效 | 100% PR | GitHub Actions |
| 体验 | 主题切换实时生效 | 全组件覆盖 | 主题切换测试用例 |
| 体验 | 主题数量 | ≥ 3 套莫奈色 + 编辑器 | 功能验收 |
| 扩展 | 新增供应商无需改源码 | 100% | 添加测试 Provider 验证 |

---

## 4. 需求总览矩阵

### 4.1 功能需求矩阵

| 模块 | 独立需求数 | P0 | P1 | P2 | P3 | 备注 |
|------|--------|----|----|----|----|------|
| 安全（SEC） | 5 | 3 | 2 | 0 | 0 | 含加密/代理鉴权/凭证源/hash 升级/日志脱敏 |
| 性能（PFM） | 8 | 0 | 7 | 1 | 0 | 含延迟加载/异步化/线程池/事件驱动/行级解析/基准/WAL |
| 架构（ARC） | 5 | 0 | 5 | 0 | 0 | 含 App 拆分/事件总线/数字健壮/快捷方式/接口抽象 |
| 并发网络（NET） | 3 | 0 | 3 | 0 | 0 | 含任务取消/多线程服务/重试 |
| 日志（LOG） | 3 | 0 | 3 | 0 | 0 | 含轮转/分级/优雅退出 |
| 配置（CFG） | 1 | 0 | 0 | 1 | 0 | FR-CFG-03=FR-SEC-04 为别名 |
| UX | 4 | 0 | 0 | 4 | 0 | 含 i18n/快捷键/失焦/颜色集中 |
| 主题（THM） | 5 | 0 | 0 | 5 | 0 | 含数据模型/Manager/莫奈色/扩展接口/编辑器 |
| 供应商扩展（PROV） | 4 | 0 | 1 | 3 | 0 | 含注册机制/配置化/自动发现/SDK 文档 |
| 质量保障（QA） | 2 | 0 | 2 | 0 | 0 | FR-QA-03=FR-PFM-07 为别名 |
| 打包分发（PKG） | 1 | 0 | 1 | 0 | 0 | 含打包模式 |
| 新功能（FEAT） | 2 | 0 | 0 | 0 | 2 | 含报告/多币种 |
| **合计** | **43** | **3** | **24** | **14** | **2** | 含 2 个引用别名共 46 个标题项 |

> 矩阵统计**独立需求**43 项；文档中以标题列出的需求项共 46 个（含 FR-CFG-03、FR-QA-03 两个引用别名，指向其他需求，不重复验收）。

### 4.2 非功能需求矩阵

| 类别 | 需求数 |
|------|--------|
| 性能（PERF） | 5 |
| 安全（SEC） | 3 |
| 可用性（USA） | 3 |
| 兼容性（COMP） | 2 |
| 可维护性（MAINT） | 2 |
| **合计** | **15** |

---

## 5. 功能需求

### 5.1 安全模块（SEC）

#### FR-SEC-01 · API Key DPAPI 加密存储

- **用户故事**：作为用户，我希望我的 API Key 以加密形式存储在本地，即使配置文件被他人获取也无法直接读取，以保护我的账户资产安全。
- **当前状态**：**未实现**。[config.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/config.py) 第 70-76 行 `save_config` 将 API Key 以**明文**写入 `config.json`；`AccountConfig.api_key` 字段直接存储明文。风险：配置文件备份/共享/误传/被恶意程序读取即造成所有 Key 泄露。
- **详细描述**：
  - **加密方案**：Windows 平台使用 DPAPI（Data Protection API），通过 `ctypes.windll.crypt32.CryptProtectData` / `CryptUnprotectData` 调用，密钥与当前 Windows 用户账户绑定，无需用户输入密码
  - **存储格式**：加密后的密文经 base64 编码存入 `AccountConfig.api_key_enc` 字段（替代原 `api_key` 明文字段）
  - **运行时解密**：`api_key` 改为 `@property`，首次访问时从 `api_key_enc` 解密并缓存到内存（受进程生命周期保护）
  - **跨平台回退**：非 Windows 平台使用 [keyring](https://pypi.org/project/keyring/) 库（macOS Keychain / Linux Secret Service），抽象为 `CredentialStore` 接口
  - **旧明文配置处理**：启动时检测到明文 `api_key` 字段（且 `api_key_enc` 不存在）时，弹窗提示用户重新输入 Key 并加密保存（不做自动迁移）
  - **边界条件**：
    - 加密失败（如 DPAPI 服务不可用）：降级为明文 + 警告日志，不阻断启动
    - 解密失败（如换用户账户）：弹窗提示"无法解密 API Key，请重新输入"，提供重新输入入口
    - 空 Key：不加密，直接存空字符串
- **验收标准**：
  1. AC1：config.json 中不存在明文 `api_key` 字段，仅存在 `api_key_enc`
  2. AC2：`api_key_enc` 经 DPAPI 加密后 base64 编码
  3. AC3：换 Windows 用户账户后解密失败，弹窗提示并允许重新输入
  4. AC4：解密失败时不崩溃，给出明确错误码与提示
  5. AC5：加密失败时降级为明文并记录 WARN 日志
  6. AC6：检测到旧明文配置时弹窗提示用户重新输入
  7. AC7：单元测试覆盖加密/解密/降级/空值场景
- **优先级**：P0
- **关联改进项**：S-1
- **所属里程碑**：M1
- **依赖需求**：无

> **v1.3 调整**：删除原依赖 FR-ARC-03（配置 schema 升级）。直接在 dataclass 上新增 `api_key_enc` 字段，不依赖 pydantic schema。删除原 FR-SEC-02（旧版明文配置自动迁移），改为检测到旧明文配置时弹窗提示用户重新输入。

#### FR-SEC-04 · usage_proxy 鉴权与目标白名单

- **用户故事**：作为用户，我希望本地反向代理仅接受我授权的客户端请求，且代理目标限定在已知 AI 平台，防止被借用消耗额度或转发到任意主机。
- **当前状态**：**未实现**。[usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) 监听 127.0.0.1:52848 无鉴权；`target_host` 可任意配置（虽有默认值，但无白名单校验）。
- **详细描述**：
  - **请求鉴权**：代理要求请求头携带 `X-Proxy-Token`，与 `SettingsConfig.proxy_token_enc` 解密后的 token 比对（独立 token，恒定时间比较防时序攻击）
  - **令牌管理**：首次启动生成随机 32 字节 token，DPAPI 加密存储；设置面板提供"查看 token"与"重置 token"按钮
  - **目标白名单**：`target_host` 必须在白名单内，白名单默认覆盖 5 个 Provider 域名 + 用户自定义主题目录（FR-PROV-02 注册的 Provider 域名自动加入白名单）
  - **流式响应行级解析**：见 FR-PFM-06，此处仅涉及鉴权与白名单
  - **审计日志**：每次请求记录 key hash + 请求路径 + 时间 + 状态码，**不记录请求/响应体**
  - **错误处理**：
    - 鉴权失败：返回 403 + 审计日志 WARN
    - 白名单拒绝：返回 403 + 审计日志 WARN
    - 目标不可达：返回 502 + 审计日志 ERROR
- **验收标准**：
  1. AC1：未携带正确 token 的请求返回 403
  2. AC2：白名单外的 target_host 返回 403
  3. AC3：审计日志不含请求/响应体
  4. AC4：FR-PROV-02 注册的 Provider 域名自动加入白名单
  5. AC5：设置面板可查看与重置 token
  6. AC6：单元测试覆盖鉴权/白名单/审计/重置
- **优先级**：P0
- **关联改进项**：S-3
- **所属里程碑**：M1
- **依赖需求**：FR-SEC-01、FR-PROV-02

#### FR-SEC-05 · 移除第三方凭证静默读取

- **用户故事**：作为用户，我希望程序不会在我不知情的情况下读取桌面或第三方工具的凭证文件，所有凭证导入需我显式授权。
- **当前状态**：**未实现**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) 第 99-119 行 `_load_active_keys` 默认扫描 `Desktop\auth.json`、`opencode\auth.json`，用户无感知。Desktop 路径存在注入风险（恶意程序可放置伪造文件）。
- **详细描述**：
  - **移除默认扫描**：删除 `_load_active_keys` 中对默认路径的扫描逻辑
  - **显式导入**：设置面板新增"导入凭证源"功能，用户点击后弹出文件选择对话框
  - **授权确认**：选择文件后弹窗告知"将读取该文件的 key 字段用于活跃账户标识（不影响余额查询）"，用户确认后记录路径到 `SettingsConfig.active_key_sources: list[str]`
  - **读取范围**：仅读取用户授权路径，每条路径独立校验存在性
  - **撤销授权**：设置面板可删除已授权路径
- **验收标准**：
  1. AC1：默认不读取任何第三方凭证文件
  2. AC2：设置面板提供"导入凭证源"入口
  3. AC3：导入时弹窗告知用途，用户确认后记录路径
  4. AC4：仅读取授权路径，路径不存在时跳过并告警
  5. AC5：可撤销已授权路径
  6. AC6：单元测试覆盖授权/读取/撤销
- **优先级**：P0
- **关联改进项**：S-4
- **所属里程碑**：M1
- **依赖需求**：无

> **v1.3 调整**：删除原依赖 FR-ARC-03。直接在 dataclass 上新增 `active_key_sources` 字段。

#### FR-SEC-06 · API Key 指纹算法升级

- **用户故事**：作为用户，我希望我的 API Key 指纹使用安全的哈希算法，避免弱哈希带来的合规风险。
- **当前状态**：**部分实现（弱算法）**。[usage_history.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_history.py) 第 47-49 行使用 MD5 截断前 16 位 hex 作为 key 指纹。虽仅用于去标识，但 MD5 存在碰撞风险与"使用弱哈希"的合规污点。
- **详细描述**：
  - **新算法**：`hashlib.sha256(api_key.encode()).hexdigest()[:32]`（截断前 32 字符）
  - **双写过渡**：升级后一段时间内同时存 MD5 与 SHA-256，保证历史数据可查
  - **历史数据迁移**：提供 `migrate_hash.py` 脚本，遍历 `token_usage` 与 `balance_snapshots` 表，对历史数据用 MD5 反查原 key（需用户提供当前 key 列表）重算 SHA-256；或标记旧数据为 `legacy_hash` 不影响新数据查询
  - **配置开关**：`SettingsConfig.hash_algorithm: str = "sha256"`，支持未来再次升级
- **验收标准**：
  1. AC1：新写入数据使用 SHA-256 截断
  2. AC2：双写过渡期历史数据可查
  3. AC3：迁移脚本可用
  4. AC4：单元测试覆盖新旧算法与迁移
- **优先级**：P1
- **关联改进项**：S-5
- **所属里程碑**：M4
- **依赖需求**：无

#### FR-SEC-07 · 日志脱敏

- **用户故事**：作为用户，我希望日志中不出现我的 API Key 明文，避免日志泄露导致 Key 泄露。
- **当前状态**：**部分实现**。[error_logger.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/error_logger.py) 不主动记录 Key，但异常 traceback 中可能包含 Key 字符串（如 balance_checker 的错误消息）。
- **详细描述**：
  - **脱敏过滤器**：在 logging handler 中添加过滤器，正则匹配 `sk-[a-zA-Z0-9]{20,}` 等常见 Key 格式，替换为 `sk-***`
  - **白名单字段**：`api_key_hash`、`masked_key` 字段不脱敏
  - **审计日志**：usage_proxy 审计日志（FR-SEC-04）仅记录 hash
- **验收标准**：
  1. AC1：日志文件扫描无明文 Key
  2. AC2：异常 traceback 中 Key 被脱敏
  3. AC3：hash 字段不被误脱敏
  4. AC4：单元测试覆盖脱敏
- **优先级**：P1
- **关联改进项**：NFR-SEC-03
- **所属里程碑**：M1
- **依赖需求**：FR-LOG-01

### 5.2 性能模块（PFM）

#### FR-PFM-01 · matplotlib 延迟加载

- **用户故事**：作为用户，我希望应用启动迅速，不要为我不常打开的图表功能承担启动耗时。
- **当前状态**：**未实现**。[usage_curve_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_curve_window.py) 与 [usage_bar_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_bar_window.py) 顶部 `import matplotlib`，启动时加载 matplotlib 首次 import 可达 200-500ms。
- **详细描述**：
  - **下沉 import**：将 matplotlib import 从模块顶部移到 `__init__` 或首次绘图方法内（局部 import）
  - **loading 提示**：首次打开曲线/柱状图窗口时显示"加载图表中..."提示
  - **可选优化**：M5+ 迁移到 pyqtgraph（参见第 7.5 节技术栈演进）
- **验收标准**：
  1. AC1：启动时不再 import matplotlib（`-X importtime` 验证）
  2. AC2：冷启动时间下降 ≥ 200ms
  3. AC3：首次打开曲线窗口可正常绘图（< 500ms）
  4. AC4：打开窗口时显示 loading 提示
- **优先级**：P1
- **关联改进项**：P-1
- **所属里程碑**：M2
- **依赖需求**：无

#### FR-PFM-02 · 启动期 IO 与建表异步化

- **用户故事**：作为用户，我希望应用启动后首屏迅速可见，后台数据加载不阻塞界面。
- **当前状态**：**未实现**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) `App.__init__` 同步执行 `load_config`（磁盘读）、`_load_active_keys`（磁盘读）、`UsageHistory()`（SQLite 建表）、`UsageProxy.start()`（端口绑定）。
- **详细描述**：
  - **首屏优先**：`App.__init__` 仅创建 `MainWindow`（空账户列表），不执行磁盘 IO
  - **后台线程**：启动后台线程执行：load_config → 凭证源加载 → UsageHistory 建表 → UsageProxy 启动
  - **数据回填**：后台加载完成后通过 `main_window.after(0, ...)` 回填账户列表并触发首次刷新
  - **空状态 UI**：首屏 200-400ms 内无数据，显示"加载中..."友好提示
  - **错误处理**：后台加载失败时 UI 显示错误状态，不崩溃
- **验收标准**：
  1. AC1：首屏渲染不等待磁盘 IO
  2. AC2：后台加载完成后回填数据
  3. AC3：首屏空状态有友好提示
  4. AC4：冷启动时间 < 300ms（10 账户场景）
  5. AC5：加载过程中 UI 可交互（按钮可点击）
  6. AC6：后台加载失败时 UI 显示错误状态
- **优先级**：P1
- **关联改进项**：P-2
- **所属里程碑**：M2
- **依赖需求**：无

#### FR-PFM-03 · scheduler 线程池改造

- **用户故事**：作为用户，我希望多账户刷新快速且不创建过多线程，保持后台低占用。
- **当前状态**：**未实现**。[scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) 第 90-100 行 `_check_all` 每账户新建一个 `threading.Thread`，10 账户即 10 线程，无并发上限。
- **详细描述**：
  - **线程池**：`BalanceScheduler.__init__` 创建 `ThreadPoolExecutor(max_workers=4, thread_name_prefix="balance-check")`
  - **任务提交**：`_check_all` 改为 `executor.map(self._do_check, accounts)` 或提交 Future
  - **并发上限**：max_workers=4，避免线程爆炸
  - **优雅关闭**：退出时 `executor.shutdown(wait=True, timeout=5)`
- **验收标准**：
  1. AC1：单轮刷新线程数 ≤ 4
  2. AC2：10 账户刷新延迟 < 5s
  3. AC3：退出时正确关闭 executor
  4. AC4：单元测试覆盖并发与关闭
- **优先级**：P1
- **关联改进项**：P-3、C-1
- **所属里程碑**：M2
- **依赖需求**：无

#### FR-PFM-04 · Provider Session 长连接复用

- **用户故事**：作为用户，我希望余额查询快速，不因每次新建连接而变慢。
- **当前状态**：**未实现**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 第 80 行每次请求新建 `requests.Session()`，连接未复用，TCP/TLS 握手开销大。
- **详细描述**：
  - **Session 持有**：`BaseProvider` 持有 `self._session = requests.Session()`，实例化时创建
  - **域名隔离**：每个 Provider 实例独立 Session（按域名隔离连接池）
  - **连接池配置**：`adapter = HTTPAdapter(pool_connections=5, pool_maxsize=10)`
  - **关闭**：退出时 `session.close()`
  - **线程安全**：requests.Session 非线程安全，配合 FR-PFM-03 线程池需加锁或每线程独立 Session（推荐 `threading.local`）
- **验收标准**：
  1. AC1：Provider 持有长连接 Session
  2. AC2：连接池命中率提升（可通过日志统计）
  3. AC3：并发请求下 Session 线程安全
  4. AC4：退出时 Session 关闭
  5. AC5：单元测试覆盖复用与关闭
- **优先级**：P1
- **关联改进项**：P-6
- **所属里程碑**：M2
- **依赖需求**：FR-PFM-03

#### FR-PFM-05 · 焦点监视改事件驱动

- **用户故事**：作为用户，我希望应用后台闲置时几乎不消耗 CPU。
- **当前状态**：**未实现**。[main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 第 81-107 行 `_focus_check_loop` 每 500ms 调用 `focus_get` 轮询，持续唤醒主循环，违背"近零占用"。
- **详细描述**：
  - **事件绑定**：`MainWindow` 绑定 `bind_all("<FocusOut>", ...)` 与 `bind_all("<FocusIn>", ...)`
  - **延时确认**：收到 `FocusOut` 后起 300ms `after` 计时器，期间若收到 `FocusIn` 则取消
  - **二次校验**：计时器触发后校验是否存在子对话框（CTkToplevel），有则不切
  - **移除轮询**：删除 `_focus_check_loop`
  - **配置开关**：与 FR-UX-04 协同，可配置是否启用失焦自动切悬浮窗
- **验收标准**：
  1. AC1：闲置 5 分钟 CPU 平均 < 0.1%
  2. AC2：失焦后切悬浮窗行为与原逻辑一致
  3. AC3：误报率不高于原方案
  4. AC4：可通过设置关闭该行为（FR-UX-04）
- **优先级**：P1
- **关联改进项**：P-4
- **所属里程碑**：M2
- **依赖需求**：无

#### FR-PFM-06 · usage_proxy 流式行级解析

- **用户故事**：作为用户，我希望代理在处理长流式响应时内存占用平稳。
- **当前状态**：**未实现**。[usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) 第 66-74 行 `usage_text += chunk.decode(...)` 累积整段响应文本，长响应（> 1MB）内存峰值高。
- **详细描述**：
  - **行级状态机**：维护 `line_buffer: str`，每个 chunk 写入客户端后 append 到 buffer，按 `\n` 分割
  - **SSE 解析**：对完整行检查 `data: ` 前缀与 `usage` 关键字，命中即解析并 `log_usage`，清空已处理部分
  - **跨 chunk 处理**：行级 buffer 正确拼接跨 chunk 的 SSE 行
  - **不再保存完整 usage_text**：内存占用恒定
- **验收标准**：
  1. AC1：长响应（> 1MB）内存峰值下降 ≥ 50%
  2. AC2：usage 提取结果与原方案一致
  3. AC3：跨 chunk 的 SSE 行正确拼接
  4. AC4：单元测试覆盖行级解析
- **优先级**：P1
- **关联改进项**：P-5
- **所属里程碑**：M2
- **依赖需求**：FR-SEC-04

#### FR-PFM-07 · 性能基准测试建立

- **用户故事**：作为维护者，我希望有可量化的性能基准，及时发现性能回归。
- **当前状态**：**未实现**。无性能基准测试方法与 CI 门禁。
- **详细描述**：
  - **指标**：冷启动时间、热启动时间、闲置内存、闲置 CPU、10 账户刷新延迟
  - **工具**：
    - 启动：`python -X importtime main.py` 分析 import 耗时
    - 内存/CPU：`psutil` 定期采样写入日志
    - 刷新延迟：scheduler 内埋点
  - **CI 门禁**：回归 > 10% 告警
  - **基准文档**：结果写入 `docs/performance-baseline.md`
- **验收标准**：
  1. AC1：提供启动时间测量脚本
  2. AC2：提供 psutil 采样脚本
  3. AC3：CI 中执行基准，回归 > 10% 告警
  4. AC4：基准结果写入文档
- **优先级**：P1
- **关联改进项**：2.8
- **所属里程碑**：M2
- **依赖需求**：FR-QA-01

#### FR-PFM-08 · UsageHistory 连接复用 + WAL

- **用户故事**：作为用户，我希望用量历史查询快速且写入不阻塞。
- **当前状态**：**未实现**。[usage_history.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_history.py) 第 67-70 行每次操作新建 `sqlite3.connect`，无连接池，默认日志模式写入慢。
- **详细描述**：
  - **单连接**：`UsageHistory.__init__` 创建单例 `sqlite3.connect(check_same_thread=False)`
  - **WAL 模式**：`PRAGMA journal_mode=WAL`、`PRAGMA synchronous=NORMAL`
  - **线程安全**：所有方法加 `threading.Lock` 保护写操作
  - **关闭**：退出时 `conn.close()`
- **验收标准**：
  1. AC1：开启 WAL 与 NORMAL 同步
  2. AC2：单连接复用，写操作加锁
  3. AC3：并发写不损坏数据
  4. AC4：查询延迟下降（基准对比）
- **优先级**：P2
- **关联改进项**：P-7
- **所属里程碑**：M3
- **依赖需求**：无

### 5.3 架构模块（ARC）

#### FR-ARC-01 · App 类拆分

- **用户故事**：作为维护者，我希望 App 类职责清晰，便于测试与扩展。
- **当前状态**：**未实现**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) `App` 类职责过重：单实例锁 + IPC + 托盘 + 全局热键 + 主题 + 自启 + 悬浮窗管理 + 余额快照记录，约 460 行。
- **详细描述**：
  - **拆分目标**：App 拆为编排器 + 8 个职责单一的管理器
  - **目标结构**：
    ```
    App（编排器，仅生命周期）
    ├── LifecycleManager    单实例锁 + IPC
    ├── TrayManager         系统托盘
    ├── HotkeyManager       全局热键
    ├── ThemeManager        主题（含莫奈色扩展，见 FR-THM-01）
    ├── AutostartManager    开机自启
    ├── WindowManager       主窗口 ↔ 悬浮窗
    ├── SchedulerManager    调度器 + 余额快照
    └── ProxyManager        usage_proxy
    ```
  - **依赖注入**：每个 Manager 构造函数接收依赖（如 config、event_bus）
  - **App 职责**：仅实例化 Manager 与连接事件
- **验收标准**：
  1. AC1：App 类行数减少 ≥ 60%
  2. AC2：每个 Manager 可独立实例化与测试
  3. AC3：App 仅负责实例化与连接
  4. AC4：现有功能行为不变（回归测试通过）
  5. AC5：依赖注入友好
- **优先级**：P1
- **关联改进项**：A-1
- **所属里程碑**：M4
- **依赖需求**：FR-ARC-02

#### FR-ARC-02 · 事件总线

- **用户故事**：作为维护者，我希望模块间通过事件解耦，新增功能无需改动多处。
- **当前状态**：**未实现**。[main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 使用 `set_refresh_callback` / `set_settings_callback` 等 6 个 setter 注入回调，耦合度高。
- **详细描述**：
  - **轻量实现**：新增 `event_bus.py`，提供 `subscribe(event, handler)` / `publish(event, payload)`
  - **事件定义**：
    - `refresh_requested`：用户请求刷新
    - `settings_changed`：设置变更
    - `account_added` / `account_deleted` / `account_updated`
    - `balance_updated`：余额刷新完成
    - `theme_changed`：主题切换
    - `provider_registered`：新 Provider 注册（FR-PROV-01）
  - **调试**：事件流转记录 DEBUG 日志
- **验收标准**：
  1. AC1：MainWindow 不再持有 setter 回调
  2. AC2：事件总线支持 subscribe/publish
  3. AC3：事件含来源与负载
  4. AC4：单元测试覆盖事件流转
  5. AC5：DEBUG 日志可追踪事件
- **优先级**：P1
- **关联改进项**：A-2
- **所属里程碑**：M3
- **依赖需求**：无

#### FR-ARC-04 · balance_checker 数字判断健壮化

- **用户故事**：作为用户，我希望余额显示准确，不因负数或科学计数法误判。
- **当前状态**：**未实现（脆弱判断）**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 第 181、226 行用 `total.replace(".","").isdigit()` 判断数字，负数、科学计数法、千分位均误判。
- **详细描述**：
  - **工具函数**：新增 `safe_float(s, default=0.0) -> float`，用 `try/except float()` + 正则兜底
  - **替换范围**：所有 `.replace(".","").isdigit()` 判断改为 `safe_float`
  - **is_available 判断**：改为 `safe_float(total) > 0`
  - **边界值**：负数、科学计数法（1e-5）、千分位（1,000.50）、空字符串、None
- **验收标准**：
  1. AC1：新增 `safe_float` 工具函数
  2. AC2：所有数字判断改用该函数
  3. AC3：负数、科学计数法、千分位正确处理
  4. AC4：单元测试覆盖边界值
- **优先级**：P1
- **关联改进项**：A-4
- **所属里程碑**：M3
- **依赖需求**：无

#### FR-ARC-05 · _create_shortcut 注入修复

- **用户故事**：作为用户，我希望开机自启快捷方式创建安全，无注入风险。
- **当前状态**：**未实现（存在注入风险）**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) 第 63-73 行 `_create_shortcut` 拼接 PowerShell 脚本，路径含单引号时存在注入风险。
- **详细描述**：
  - **优先方案**：改用 `pywin32` 的 `win32com.client.ShellLink` 对象（如已依赖则直接用）
  - **回退方案**：PowerShell 调用改为 `-ArgumentList` 参数化，禁止字符串插值
  - **路径校验**：仅允许绝对路径，不含 `;` `|` `&` 等特殊字符
- **验收标准**：
  1. AC1：路径含单引号、空格、特殊字符时正常工作
  2. AC2：无字符串拼接 PowerShell 命令
  3. AC3：路径校验仅允许绝对路径
  4. AC4：单元测试覆盖特殊字符
- **优先级**：P1
- **关联改进项**：A-5
- **所属里程碑**：M1
- **依赖需求**：无

#### FR-ARC-06 · Provider 接口抽象与注册表

- **用户故事**：作为维护者，我希望新增供应商时只需实现接口并注册，无需修改核心代码。
- **当前状态**：**部分实现（硬编码注册）**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 第 233-239 行 `PROVIDERS` 字典硬编码 5 个 Provider，新增需改源码并重新打包。
- **详细描述**：
  - **抽象接口**：`BaseProvider` 已存在（ABC），保持不变
  - **注册表改造**：`PROVIDERS` 字典改为运行时可扩展，提供 `register_provider(provider)` API（已存在）
  - **与 FR-PROV-01 协同**：FR-PROV-01 实现配置化注册，FR-ARC-06 提供底层注册表机制
- **验收标准**：
  1. AC1：`register_provider` API 可用
  2. AC2：运行时注册的 Provider 立即生效（无需重启）
  3. AC3：单元测试覆盖动态注册
- **优先级**：P1
- **关联改进项**：A-2
- **所属里程碑**：M3
- **依赖需求**：FR-PROV-01

### 5.4 并发网络模块（NET）

#### FR-NET-01 · scheduler 任务取消

- **用户故事**：作为用户，我希望刷新超时的账户不会无限挂起，影响后续刷新。
- **当前状态**：**未实现**。[scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) 第 99-100 行 `t.join(timeout=15)` 超时后线程仍在后台运行，长期累积可能"僵尸线程"。
- **详细描述**：
  - **Future 提交**：`_check_all` 提交所有 `Future`
  - **超时收集**：`as_completed(futures, timeout=15)` 收集结果
  - **取消**：超时的 Future 调用 `cancel()`（仅未启动的可取消，运行中的依赖 Provider 端 `requests` 超时）
  - **日志**：记录 WARN 日志（账户 UID + 超时秒数）
- **验收标准**：
  1. AC1：单账户超时不影响其他账户
  2. AC2：超时 Future 调用 cancel
  3. AC3：记录警告日志
  4. AC4：单元测试覆盖超时场景
- **优先级**：P1
- **关联改进项**：C-2
- **所属里程碑**：M2
- **依赖需求**：FR-PFM-03

#### FR-NET-02 · usage_proxy ThreadingHTTPServer

- **用户故事**：作为用户，我希望代理能并发处理多个请求，不排队。
- **当前状态**：**未实现**。[usage_proxy.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/usage_proxy.py) 第 157 行 `HTTPServer` 单线程，并发请求排队。
- **详细描述**：
  - **多线程服务**：`HTTPServer` → `socketserver.ThreadingHTTPServer`
  - **daemon 线程**：`daemon_threads = True`
  - **连接池**：配合 FR-PFM-04 Provider Session 复用降低开销
  - **SQLite 并发**：配合 FR-PFM-08 WAL 模式支撑并发写
- **验收标准**：
  1. AC1：并发请求不排队
  2. AC2：daemon_threads = True
  3. AC3：并发写 SQLite 不损坏
  4. AC4：单元测试覆盖并发
- **优先级**：P1
- **关联改进项**：C-3
- **所属里程碑**：M2
- **依赖需求**：无

#### FR-NET-03 · balance_checker 重试与退避

- **用户故事**：作为用户，我希望网络抖动时余额查询自动重试，不轻易报错。
- **当前状态**：**未实现**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 第 103-108 行仅捕获超时与连接错误，无重试，无退避。
- **详细描述**：
  - **重试库**：引入 `tenacity` 或自实现重试装饰器
  - **重试条件**：`requests.exceptions.Timeout`、`ConnectionError`、`5xx` 状态码
  - **退避策略**：指数退避 1s → 2s → 4s，最多 3 次
  - **不重试**：4xx（含 401/403）
  - **UI 状态**：重试中 UI 显示"重试中..."状态
  - **耗尽处理**：重试耗尽返回 `BalanceStatus.ERROR`，error_message 标注"重试 N 次后失败"
- **验收标准**：
  1. AC1：超时/连接错误/5xx 重试，退避 1s→2s→4s
  2. AC2：4xx 不重试
  3. AC3：重试中 UI 显示"重试中"状态
  4. AC4：重试耗尽返回 ERROR
  5. AC5：单元测试覆盖重试逻辑
- **优先级**：P1
- **关联改进项**：C-4
- **所属里程碑**：M2
- **依赖需求**：FR-PFM-04

### 5.5 日志模块（LOG）

#### FR-LOG-01 · 统一 logging + RotatingFileHandler

- **用户故事**：作为用户，我希望日志文件不无限膨胀，占用磁盘。
- **当前状态**：**未实现**。[error_logger.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/error_logger.py) 第 26-44 行每次异常创建独立 `.log` 文件，文件数无上限，长期运行后 `log/` 目录膨胀。
- **详细描述**：
  - **新模块**：新增 `log_setup.py`，配置根 logger
  - **Handler**：`RotatingFileHandler` 单文件 `app.log`，maxBytes=2MB，backupCount=5
  - **格式**：`%(asctime)s | %(levelname)s | %(name)s | %(message)s`
  - **分级**：DEBUG（文件）/ INFO（控制台，开发时）
  - **兼容**：`log_exception(source, exc)` 接口保留，内部转 `logger.exception`
  - **旧日志清理**：提供 `cleanup_old_logs.py` 脚本清理 `log/` 目录
- **验收标准**：
  1. AC1：日志写入 app.log，按大小轮转
  2. AC2：保留 5 份备份
  3. AC3：log_exception 接口保留兼容
  4. AC4：旧 log/ 目录提供清理脚本
- **优先级**：P1
- **关联改进项**：E-1
- **所属里程碑**：M1
- **依赖需求**：无

#### FR-LOG-02 · 日志分级

- **用户故事**：作为维护者，我希望日志有分级，便于排查问题。
- **当前状态**：**未实现**。无日志分级，所有异常同等对待。
- **详细描述**：
  - **标准 logger**：全项目改用 `logging.getLogger(__name__)`
  - **级别**：DEBUG / INFO / WARN / ERROR
  - **输出**：文件记录 DEBUG+，控制台 INFO+（开发时）
  - **配置**：可通过 `SettingsConfig.log_level: str = "INFO"` 调整
- **验收标准**：
  1. AC1：所有模块使用标准 logger
  2. AC2：文件 DEBUG+，控制台 INFO+
  3. AC3：格式含时间、级别、模块、消息
  4. AC4：可通过配置调整级别
- **优先级**：P1
- **关联改进项**：E-2
- **所属里程碑**：M1
- **依赖需求**：FR-LOG-01

#### FR-LOG-03 · 优雅退出

- **用户故事**：作为用户，我希望退出应用时资源正确释放，不残留进程。
- **当前状态**：**未实现**。[main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) 第 453 行 `os._exit(0)` 强制退出，跳过资源清理与 atexit 钩子。
- **详细描述**：
  - **移除 os._exit**：`App._quit` 末尾 `os._exit(0)` → `sys.exit(0)`
  - **资源清理**：scheduler.stop、proxy.stop、tray.stop、keyboard.unhook_all 放在 `atexit.register` 或 try/finally
  - **退出顺序**：先停止调度器 → 停止代理 → 停止托盘 → 销毁窗口 → unhook 热键 → sys.exit
  - **回退开关**：提供 `--force-exit` 命令行开关回退到 `os._exit`（应对 tkinter 死锁）
- **验收标准**：
  1. AC1：退出后无残留进程
  2. AC2：scheduler/proxy/tray/keyboard 正确停止
  3. AC3：`--force-exit` 回退开关可用
  4. AC4：退出测试通过
- **优先级**：P1
- **关联改进项**：E-3
- **所属里程碑**：M2
- **依赖需求**：无

### 5.6 配置模块（CFG）

#### FR-CFG-02 · 配置原子写入 + 备份

- **用户故事**：作为用户，我希望配置写入失败时不丢失旧配置。
- **当前状态**：**未实现**。[config.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/config.py) `save_config` 直接覆盖写入，写入失败（磁盘满、权限）时旧配置丢失。
- **详细描述**：
  - **原子写入**：`save_config` 写 `config.json.tmp` → `os.replace(tmp, config.json)`（原子操作）
  - **备份**：写入前若旧文件存在，复制到 `config.json.bak.{n}`，滚动保留 3 份
  - **回退**：读取失败时自动回退到最近备份
- **验收标准**：
  1. AC1：写入用 `os.replace` 原子操作
  2. AC2：保留最近 3 份 .bak
  3. AC3：读取失败回退到备份
  4. AC4：单元测试覆盖写入失败与回退
- **优先级**：P2
- **关联改进项**：D-3
- **所属里程碑**：M3
- **依赖需求**：无

> **v1.3 调整**：删除原依赖 FR-ARC-03。独立实现原子写入，不依赖 schema 升级。

#### FR-CFG-03 · 凭证源显式管理

- 见 FR-SEC-04（active_key_sources 字段）。

### 5.7 UX 模块

#### FR-UX-01 · 国际化（i18n）

- **用户故事**：作为非中文用户，我希望应用支持多语言切换。
- **当前状态**：**未实现**。全中文硬编码，无 i18n。
- **详细描述**：
  - **gettext**：引入 `gettext`，全项目字符串改用 `_("...")` 包裹
  - **语言包**：生成 `locales/zh_CN/LC_MESSAGES/app.po`（默认），后续扩展 `en`
  - **切换**：设置面板增加语言切换（重启生效）
- **验收标准**：
  1. AC1：全项目 UI 字符串改用 `_("...")`
  2. AC2：提供 zh_CN 与 en 语言包
  3. AC3：设置面板可切换语言（重启生效）
  4. AC4：切换后所有界面文本更新
- **优先级**：P2
- **关联改进项**：U-1
- **所属里程碑**：M4
- **依赖需求**：无

#### FR-UX-02 · 快捷键可配置

- **用户故事**：作为用户，我希望自定义快捷键，避免与其他应用冲突。
- **当前状态**：**未实现（硬编码）**。快捷键硬编码（`Ctrl+R`、`Ctrl+Shift+B`），不可配置。
- **详细描述**：
  - **配置字段**：`SettingsConfig.hotkeys: dict[str, str]`（action → keystr）
  - **默认值**：`toggle_window: "ctrl+shift+b"`、`manual_refresh: "ctrl+r"`
  - **设置面板**：提供录入控件（捕获按键）
  - **冲突检测**：检测与系统/其他应用冲突并提示
- **验收标准**：
  1. AC1：默认快捷键不变
  2. AC2：设置面板可录入新快捷键
  3. AC3：冲突检测提示
  4. AC4：重启后生效
- **优先级**：P2
- **关联改进项**：U-2
- **所属里程碑**：M3
- **依赖需求**：无

#### FR-UX-04 · 焦点丢失行为可配置

- **用户故事**：作为用户，我希望控制失焦是否自动切悬浮窗，避免误触。
- **当前状态**：**未实现（强制开启）**。失焦自动切悬浮窗不可配置，可能干扰用户工作。
- **详细描述**：
  - **配置字段**：`SettingsConfig.auto_float_on_focus_loss: bool = False`
  - **默认值**：False（关闭），改为手动最小化
  - **设置面板**：提供开关
  - **即时生效**：开关切换立即生效
- **验收标准**：
  1. AC1：默认关闭，需手动最小化
  2. AC2：设置面板提供开关
  3. AC3：开关切换立即生效
- **优先级**：P2
- **关联改进项**：U-4
- **所属里程碑**：M3
- **依赖需求**：FR-PFM-05

#### FR-UX-06 · 颜色集中管理

- **用户故事**：作为主题开发者，我希望颜色集中在主题层定义，UI 组件不硬编码。
- **当前状态**：**未实现（硬编码散落）**。颜色硬编码：[floating_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/floating_window.py) 第 42-44 行、[main_window.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main_window.py) 第 310 行等。
- **详细描述**：
  - **语义 token**：所有 UI 组件移除硬编码颜色，改用 `ThemeManager.current.surface` 等语义 token
  - **订阅事件**：UI 组件订阅 `theme_changed` 事件，主题切换时重新 `configure(fg_color=...)`
  - **customtkinter 适配**：`set_appearance_mode` 仍用于控制亮/暗，但颜色由 ThemeLayer 提供
- **验收标准**：
  1. AC1：UI 文件中无硬编码颜色字面量
  2. AC2：颜色统一从 ThemeManager.current 读取
  3. AC3：主题切换实时生效
- **优先级**：P2
- **关联改进项**：U-6
- **所属里程碑**：M3
- **依赖需求**：FR-THM-01

### 5.8 主题模块（THM）

#### FR-THM-01 · 主题数据模型与 ThemeManager

- **用户故事**：作为用户，我希望切换不同主题色，而非仅 dark/light。
- **当前状态**：**未实现**。customtkinter 仅支持 dark/light/system 三种内置主题；颜色硬编码散落各处。
- **详细描述**：
  - **数据模型**：新增 `Theme` 与 `ThemeLayer` pydantic 模型（详见第 7.1 节）
  - **ThemeManager**：单例，App 持有，提供 `register`/`apply`/`export`/`import` API
  - **事件广播**：`apply(name)` 后广播 `theme_changed` 事件
  - **UI 订阅**：UI 组件订阅事件后重新 `configure` 颜色
- **验收标准**：
  1. AC1：ThemeManager 单例可用
  2. AC2：Theme/ThemeLayer 数据模型完整
  3. AC3：register/apply API 可用
  4. AC4：apply 后广播 theme_changed 事件
  5. AC5：UI 组件订阅事件后实时更新颜色
- **优先级**：P2
- **关联改进项**：T-1
- **所属里程碑**：M3
- **依赖需求**：FR-ARC-02

#### FR-THM-02 · 莫奈色主题内置

- **用户故事**：作为用户，我希望应用提供莫奈风格的精美主题。
- **当前状态**：**未实现**。仅 dark/light，无莫奈色。用户明确要求放弃黑色主题。
- **详细描述**：
  - **3 套主题**：睡莲、日出印象、干草垛（配色方案见第 7.1 节）
  - **亮/暗双变体**：每套主题含亮色与暗色（莫奈深色，非纯黑）
  - **放弃纯黑**：不再使用 customtkinter 原生纯黑 dark 主题
  - **旧字段兼容映射**：`load_config` 读取时若发现旧 `theme: "dark"` / `"light"` 字段，运行时映射到"莫奈·睡莲（暗/亮变体）"（不依赖 schema 迁移，下次保存时自然替换为 `theme_name` 字段）
  - **对比度**：主题切换后对比度达标（WCAG AA）
- **验收标准**：
  1. AC1：3 套主题 JSON 文件存在于 themes/ 目录
  2. AC2：每套主题含亮/暗双变体
  3. AC3：主题切换后界面美观、对比度达标
  4. AC4：放弃纯黑 dark 主题
  5. AC5：旧 dark/light 配置运行时映射到莫奈变体
- **优先级**：P2
- **关联改进项**：T-2
- **所属里程碑**：M3
- **依赖需求**：FR-THM-01

> **v1.3 调整**：删除原依赖 FR-ARC-03。旧主题字段改为运行时兼容读取，不依赖 schema 迁移机制。

#### FR-THM-03 · 主题扩展接口（用户自定义主题）

- **用户故事**：作为主题开发者，我希望通过 JSON 文件扩展自定义主题。
- **当前状态**：**未实现**。无主题扩展机制。
- **详细描述**：
  - **目录扫描**：ThemeManager 启动时扫描内置 `themes/` + 用户目录 `~/.deepseek-monitor/themes/`
  - **覆盖规则**：用户主题同名覆盖内置
  - **格式校验**：JSON 文件格式错误时降级处理（跳过该主题 + WARN 日志）
  - **热加载**：支持运行时重新扫描（编辑器保存后立即生效）
- **验收标准**：
  1. AC1：用户主题目录被扫描
  2. AC2：JSON 格式主题文件可加载
  3. AC3：同名用户主题覆盖内置
  4. AC4：格式错误时降级处理
  5. AC5：热加载可用
- **优先级**：P2
- **关联改进项**：T-3
- **所属里程碑**：M3
- **依赖需求**：FR-THM-01

#### FR-THM-04 · 主题编辑器

- **用户故事**：作为用户，我希望可视化编辑主题颜色并实时预览。
- **当前状态**：**未实现**。无主题编辑器。
- **详细描述**：
  - **功能**：可视化编辑 ThemeLayer 所有语义颜色、亮/暗双套编辑、实时预览、保存为用户主题、导入/导出 JSON、重置
  - **UI 布局**：颜色矩阵 + 预览面板 + 操作按钮（详见第 7.1.4 节）
  - **颜色选择**：`tkinter.colorchooser.askcolor`
  - **实时预览**：预览面板用 customtkinter 组件实时 `configure`
  - **保存**：写入用户主题目录，ThemeManager 重新扫描
- **验收标准**：
  1. AC1：可编辑 ThemeLayer 所有语义颜色
  2. AC2：亮/暗双套编辑
  3. AC3：实时预览（按钮/文本/卡片样例）
  4. AC4：保存到用户主题目录
  5. AC5：导入/导出 JSON
  6. AC6：重置为默认
- **优先级**：P2
- **关联改进项**：8.6
- **所属里程碑**：M3
- **依赖需求**：FR-THM-01、FR-THM-03

#### FR-THM-05 · 主题切换实时生效

- **用户故事**：作为用户，我希望切换主题后所有窗口立即更新颜色，无需重启。
- **当前状态**：**未实现**。当前主题切换仅改 `ctk.set_appearance_mode`，已打开的 Toplevel 窗口不更新。
- **详细描述**：
  - **全组件订阅**：所有 UI 组件（含主窗口、悬浮窗、对话框、图表窗口）订阅 `theme_changed` 事件
  - **Toplevel 处理**：主题切换时遍历所有已存在的 Toplevel 重新着色
  - **图表适配**：matplotlib/pyqtgraph 图表颜色读取主题 token
- **验收标准**：
  1. AC1：切换主题后主窗口立即更新
  2. AC2：已打开的 Toplevel 窗口立即更新
  3. AC3：图表窗口颜色同步
  4. AC4：无残留旧颜色
- **优先级**：P2
- **关联改进项**：T-1
- **所属里程碑**：M3
- **依赖需求**：FR-THM-01

### 5.9 供应商扩展模块（PROV）

> **本模块为 v1.1 新增**，支持未来适配更多供应商。

#### FR-PROV-01 · Provider 声明式配置注册

- **用户故事**：作为用户/第三方开发者，我希望通过 JSON 配置文件注册新供应商，无需修改源码。
- **当前状态**：**未实现（硬编码）**。[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 第 233-239 行 `PROVIDERS` 字典硬编码 5 个 Provider，新增需改源码、重新打包。
- **详细描述**：
  - **配置目录**：`providers/` 内置 + `~/.deepseek-monitor/providers/` 用户自定义
  - **配置格式**：JSON 声明式，包含元数据与 API 规格
  - **配置示例**：
    ```json
    {
      "name": "my_provider",
      "label": "我的供应商",
      "description": "自定义 AI 平台",
      "api": {
        "url": "https://api.my-provider.com/v1/balance",
        "method": "GET",
        "auth_header": "Authorization",
        "auth_prefix": "Bearer ",
        "timeout": 10
      },
      "parser": {
        "type": "json_path",
        "balance_path": "data.balance",
        "currency": "CNY",
        "is_available_rule": "> 0"
      },
      "proxy_target": "api.my-provider.com"
    }
    ```
  - **解析器类型**：
    - `json_path`：JSON 路径提取（简单场景）
    - `jinja2`：Jinja2 模板（复杂转换）
    - `python_module`：自定义 Python 模块（高级场景，需信任源）
  - **运行时注册**：加载配置后调用 `register_provider` 注册
  - **事件广播**：注册成功后广播 `provider_registered` 事件，UI 更新 Provider 下拉列表
- **验收标准**：
  1. AC1：JSON 配置文件可加载并注册 Provider
  2. AC2：`json_path` 解析器支持简单路径提取
  3. AC3：注册后 UI 下拉列表立即更新
  4. AC4：配置格式错误时降级处理 + WARN 日志
  5. AC5：用户目录覆盖内置同名 Provider
  6. AC6：单元测试覆盖加载/注册/降级
- **优先级**：P1
- **关联改进项**：A-2
- **所属里程碑**：M3
- **依赖需求**：FR-ARC-06

#### FR-PROV-02 · Provider 自动发现

- **用户故事**：作为用户，我希望放入新 Provider 配置文件后重启即可使用，无需额外操作。
- **当前状态**：**未实现**。Provider 需手动注册。
- **详细描述**：
  - **启动扫描**：启动时扫描 `providers/` 与 `~/.deepseek-monitor/providers/` 目录下所有 `.json` 文件
  - **热加载**：运行时监听目录变化（可选，用 `watchdog` 库），新文件放入即注册
  - **去重**：同名 Provider 后加载的覆盖先加载的
  - **白名单同步**：注册的 Provider 域名自动加入 usage_proxy 白名单（FR-SEC-04）
- **验收标准**：
  1. AC1：启动时自动扫描 providers 目录
  2. AC2：JSON 文件自动注册
  3. AC3：域名自动加入白名单
  4. AC4：热加载可用（可选，watchdog）
  5. AC5：单元测试覆盖扫描与注册
- **优先级**：P2
- **关联改进项**：A-2
- **所属里程碑**：M3
- **依赖需求**：FR-PROV-01

#### FR-PROV-03 · Provider 配置校验与测试工具

- **用户故事**：作为第三方开发者，我希望有工具校验我的 Provider 配置是否正确。
- **当前状态**：**未实现**。无配置校验工具。
- **详细描述**：
  - **校验工具**：`python -m provider_validator <config.json>` 命令行工具
  - **校验内容**：
    - JSON 格式合法性
    - 必填字段完整性（name、label、api.url、parser）
    - URL 可达性（可选 ping）
    - 解析器语法正确性
  - **测试工具**：提供 `--test` 模式，用测试 API Key 实际调用并验证解析结果
- **验收标准**：
  1. AC1：命令行校验工具可用
  2. AC2：校验 JSON 格式与字段完整性
  3. AC3：`--test` 模式实际调用验证
  4. AC4：错误信息清晰可定位
- **优先级**：P2
- **关联改进项**：—
- **所属里程碑**：M3
- **依赖需求**：FR-PROV-01

#### FR-PROV-04 · Provider SDK 文档与示例

- **用户故事**：作为第三方开发者，我希望有文档指导我开发自定义 Provider。
- **当前状态**：**未实现**。无 Provider 开发文档。
- **详细描述**：
  - **文档**：`docs/provider-sdk.md`，包含：
    - Provider 配置格式说明
    - 解析器类型说明（json_path / jinja2 / python_module）
    - 完整示例（3 个：简单 JSON、嵌套 JSON、自定义模块）
    - 调试技巧
    - 发布流程（提交到社区仓库或自托管）
  - **示例包**：`providers/examples/` 含 3 个示例配置
- **验收标准**：
  1. AC1：文档完整，覆盖配置/解析器/示例/调试
  2. AC2：3 个示例配置可用
  3. AC3：文档含截图/代码高亮
- **优先级**：P2
- **关联改进项**：—
- **所属里程碑**：M3
- **依赖需求**：FR-PROV-01

### 5.10 质量保障模块（QA）

#### FR-QA-01 · CI 测试 + 覆盖率门禁

- **用户故事**：作为维护者，我希望 PR 合并前自动跑测试，防止回归。
- **当前状态**：**未实现**。[.github/workflows/release.yml](file:///d:/#MCP-Serve/deepseek-balance-monitor/.github/workflows/release.yml) 仅构建，不跑测试。无覆盖率统计。
- **详细描述**：
  - **新 workflow**：`.github/workflows/test.yml`，push/PR 时跑 `pytest --cov=main --cov-report=xml`
  - **覆盖率**：初始阈值 70%，M4 后 85%
  - **runner**：Windows（项目为 Windows 优先）
  - **报告**：集成 Codecov 或 PR 评论显示覆盖率
  - **tkinter 处理**：CI 环境无显示，用虚拟显示或 mock UI 层
- **验收标准**：
  1. AC1：push/PR 触发测试
  2. AC2：覆盖率 < 70% 失败
  3. AC3：Windows runner
  4. AC4：覆盖率报告显示在 PR 评论
- **优先级**：P1
- **关联改进项**：Q-1、Q-2
- **所属里程碑**：M4
- **依赖需求**：无

#### FR-QA-02 · Lint + 类型检查

- **用户故事**：作为维护者，我希望代码风格统一，类型错误早发现。
- **当前状态**：**未实现**。无 Lint、无类型检查。
- **详细描述**：
  - **ruff**：替代 flake8+black+isort
  - **mypy**：渐进式收紧（先宽松 `--ignore-missing-imports`，逐步 `--strict`）
  - **pre-commit**：本地钩子
  - **CI**：失败阻断合并
- **验收标准**：
  1. AC1：ruff 检查通过
  2. AC2：mypy 渐进式收紧
  3. AC3：pre-commit 钩子
  4. AC4：CI 失败阻断合并
- **优先级**：P2
- **关联改进项**：Q-3
- **所属里程碑**：M4
- **依赖需求**：FR-QA-01

#### FR-QA-03 · 性能基准 CI 门禁

- 见 FR-PFM-07。

### 5.11 打包分发模块（PKG）

#### FR-PKG-01 · 打包模式优化

- **用户故事**：作为用户，我希望应用启动快，安装包不过大。
- **当前状态**：**未实现（onefile 慢）**。PyInstaller `--onefile` 模式，启动慢（解压到临时目录）。
- **详细描述**：
  - **onedir 优先**：`--onedir` 启动更快（预计降 30-50%）
  - **Nuitka 备选**：`nuitka --standalone --onefile --enable-plugin=tk-inter main.py` 编译为原生代码
  - **CI 对比**：两种模式启动基准对比
- **验收标准**：
  1. AC1：onedir 模式启动时间下降 ≥ 30%
  2. AC2：或 Nuitka 编译成功
  3. AC3：CI 中对比基准
- **优先级**：P1
- **关联改进项**：R-1
- **所属里程碑**：M4
- **依赖需求**：无

### 5.12 新功能模块（FEAT）

#### FR-FEAT-03 · 报告导出

- **用户故事**：作为用户，我希望导出余额历史与用量统计报告。
- **当前状态**：**未实现**。无报告导出功能。
- **详细描述**：
  - **格式**：PDF / CSV / HTML
  - **内容**：余额曲线图、用量柱状图、汇总表
  - **库**：`reportlab`（PDF）、`csv`（CSV）
- **验收标准**：
  1. AC1：可导出 PDF（含图表）
  2. AC2：可导出 CSV
  3. AC3：可导出 HTML
  4. AC4：报告含余额曲线、用量柱状图、汇总表
- **优先级**：P3
- **关联改进项**：F-3
- **所属里程碑**：M5+
- **依赖需求**：无

#### FR-FEAT-04 · 多币种聚合

- **用户故事**：作为用户，我希望不同币种余额按汇率换算为单一基准货币显示总额。
- **当前状态**：**未实现**。多币种余额分别显示，无换算。
- **详细描述**：
  - **汇率 API**：接入 exchangerate-api
  - **配置**：`SettingsConfig.base_currency: str = "CNY"`
  - **展示**：主窗口/悬浮窗显示换算后总额
- **验收标准**：
  1. AC1：支持 CNY/USD 互转
  2. AC2：汇率定时刷新
  3. AC3：主窗口/悬浮窗显示换算总额
  4. AC4：可切换基准货币
- **优先级**：P3
- **关联改进项**：F-4
- **所属里程碑**：M5+
- **依赖需求**：无

---

## 6. 非功能需求

### 6.1 性能（PERF）

#### NFR-PERF-01 · 冷启动时间
- **指标**：冷启动 < 300ms（10 账户场景）
- **测量**：`python -X importtime main.py` + 人工计时双击 exe 到首屏可交互
- **适用**：M2 起强制

#### NFR-PERF-02 · 闲置内存
- **指标**：闲置 5 分钟内存 < 50MB
- **测量**：psutil 采样
- **适用**：M2 起强制

#### NFR-PERF-03 · 闲置 CPU
- **指标**：闲置 5 分钟 CPU 平均 < 0.1%
- **测量**：psutil 采样
- **适用**：M2 起强制

#### NFR-PERF-04 · 刷新延迟
- **指标**：10 账户单次刷新 < 5s
- **测量**：scheduler 埋点
- **适用**：M2 起强制

#### NFR-PERF-05 · 性能回归门禁
- **指标**：CI 性能基准回归 > 10% 告警
- **测量**：CI 自动执行
- **适用**：M2 起强制

### 6.2 安全（SEC）

#### NFR-SEC-01 · 凭证存储
- **指标**：API Key 100% 加密存储，config.json 无明文
- **测量**：文件检查 + 单元测试
- **适用**：M1 起强制

#### NFR-SEC-02 · 服务鉴权
- **指标**：usage_proxy 100% 鉴权
- **测量**：渗透测试 + 单元测试
- **适用**：M1 起强制

#### NFR-SEC-03 · 日志脱敏
- **指标**：日志中不含 API Key 明文，仅含 hash
- **测量**：日志文件扫描
- **适用**：M1 起强制

### 6.3 可用性（USA）

#### NFR-USA-01 · 单实例保证
- **指标**：同一时刻仅一个进程运行
- **测量**：双开测试
- **适用**：现状已满足，保持

#### NFR-USA-02 · 异常不崩溃
- **指标**：单账户查询失败不影响其他账户与 UI
- **测量**：异常注入测试
- **适用**：M2 起强制

#### NFR-USA-03 · 资源正确释放
- **指标**：退出后无残留进程与锁
- **测量**：退出后任务管理器检查
- **适用**：M2 起强制

### 6.4 兼容性（COMP）

#### NFR-COMP-01 · Windows 版本
- **指标**：支持 Windows 10/11
- **测量**：多版本虚拟机测试
- **适用**：始终

#### NFR-COMP-02 · Python 版本
- **指标**：支持 Python 3.10+
- **测量**：多版本 CI 矩阵
- **适用**：始终

### 6.5 可维护性（MAINT）

#### NFR-MAINT-01 · 测试覆盖率
- **指标**：≥ 70%（M4 前）/ ≥ 85%（M4 后）
- **测量**：pytest-cov
- **适用**：M4 起强制

#### NFR-MAINT-02 · 代码风格
- **指标**：ruff 与 mypy 检查通过
- **测量**：CI
- **适用**：M4 起强制

---

## 7. 系统设计要点

### 7.1 主题系统设计

#### 7.1.1 架构

```
ThemeManager（单例，App 持有）
├── themes: dict[str, Theme]        已注册主题（内置 + 用户自定义）
├── current: Theme                  当前生效主题
├── register(theme: Theme)          注册新主题
├── apply(name: str)                应用主题，广播 theme_changed 事件
└── export(path) / import(path)     主题导出/导入（编辑器用）
```

#### 7.1.2 数据模型

```python
class ThemeLayer(BaseModel):
    """单个语义层颜色，包含亮/暗两套。"""
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

#### 7.1.3 莫奈色配色方案（首批 3 套）

**莫奈·睡莲（Water Lilies）— 主推**

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

**莫奈·日出印象（Impression, Sunrise）**

| 语义 | 亮色 | 暗色 |
|------|------|------|
| background | #FFF5EB | #1E1A14 |
| surface | #FFFFFF | #2A2419 |
| primary | #E07B39（日出橙） | #F09A5C |
| secondary | #4A6FA5（海面蓝） | #6B8DC4 |
| accent | #F2C849（晨光金） | #FFD96E |
| text | #3D2E1F | #F5E6D3 |
| ripple_color | #E07B39 | #F09A5C |

**莫奈·干草垛（Haystacks）**

| 语义 | 亮色 | 暗色 |
|------|------|------|
| background | #FAF3E0 | #1F1A14 |
| surface | #FFFFFF | #2B2419 |
| primary | #C9A961（麦秆金） | #E0C481 |
| secondary | #8B7355（干草褐） | #A89279 |
| accent | #7B5E8C（阴影紫） | #9C7DB5 |
| text | #3D2E1F | #F0E4C9 |
| ripple_color | #C9A961 | #E0C481 |

#### 7.1.4 主题编辑器 UI

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

### 7.2 配置数据模型

> **v1.3 调整**：由于删除了 FR-ARC-03（pydantic schema 升级），配置保留 dataclass 方式。新增字段直接添加到 dataclass。无 `version` 字段（不做版本迁移）。

```python
@dataclass
class AccountConfig:
    label: str
    api_key_enc: str              # DPAPI 加密后 base64（FR-SEC-01）
    provider: str = "deepseek"    # 支持 FR-PROV-01 注册的自定义 Provider
    uid: str                      # 自动生成

@dataclass
class SettingsConfig:
    interval_sec: int = 60        # ≥ 10
    theme_name: str = "monet_water_lilies"  # 主题名（FR-THM-02）
    autostart: bool = True
    ripple_color: str = "#5B8AA6"
    hotkeys: dict[str, str] = field(default_factory=lambda: {  # 可配置快捷键（FR-UX-02）
        "toggle_window": "ctrl+shift+b",
        "manual_refresh": "ctrl+r",
    })
    auto_float_on_focus_loss: bool = False  # 失焦行为（FR-UX-04）
    language: str = "zh_CN"                 # i18n（FR-UX-01）
    proxy_token_enc: str = ""               # 代理鉴权 token（FR-SEC-04）
    active_key_sources: list[str] = field(default_factory=list)  # 凭证源（FR-SEC-05）
    hash_algorithm: str = "sha256"          # hash 算法（FR-SEC-06）
    log_level: str = "INFO"                 # 日志级别（FR-LOG-02）
    base_currency: str = "CNY"              # 基准货币（FR-FEAT-04）

@dataclass
class AppConfig:
    accounts: list[AccountConfig] = field(default_factory=list)
    window: WindowConfig = field(default_factory=WindowConfig)
    settings: SettingsConfig = field(default_factory=SettingsConfig)
```

> **v1.3 删除字段**：`version`（FR-ARC-03 删除）、`proxy_targets`（FR-NET-04 删除）、`notify_threshold`/`notify_on_error`（FR-UX-03 删除）、`font_scale`（FR-UX-05 删除）、`alert_threshold`（FR-FEAT-01 删除）、`budgets`（FR-FEAT-02 删除）。

### 7.3 事件总线设计

```python
# event_bus.py
class EventBus:
    def subscribe(self, event: str, handler: Callable): ...
    def publish(self, event: str, payload: Any): ...

# 事件定义
EVENT_REFRESH_REQUESTED = "refresh_requested"
EVENT_SETTINGS_CHANGED = "settings_changed"
EVENT_ACCOUNT_ADDED = "account_added"
EVENT_BALANCE_UPDATED = "balance_updated"
EVENT_THEME_CHANGED = "theme_changed"
EVENT_PROVIDER_REGISTERED = "provider_registered"  # FR-PROV-01
```

### 7.4 供应商扩展设计

#### 7.4.1 架构

```
ProviderLoader（启动时扫描）
├── 内置目录 providers/*.json
├── 用户目录 ~/.deepseek-monitor/providers/*.json
├── 加载 → 校验 → 注册到 PROVIDERS
└── 广播 provider_registered 事件

BaseProvider（抽象接口，已存在）
├── check_balance(api_key) -> BalanceInfo
└── _parse_response(data) -> BalanceInfo

JsonPathProvider（FR-PROV-01 新增）
├── 从 JSON 配置实例化
├── check_balance: 调用 API + json_path 解析
└── 支持简单路径提取

Jinja2Provider（FR-PROV-01 新增）
├── 从 JSON 配置实例化
└── 使用 Jinja2 模板转换响应
```

#### 7.4.2 配置格式

```json
{
  "name": "my_provider",
  "label": "我的供应商",
  "description": "自定义 AI 平台",
  "api": {
    "url": "https://api.my-provider.com/v1/balance",
    "method": "GET",
    "auth_header": "Authorization",
    "auth_prefix": "Bearer ",
    "timeout": 10
  },
  "parser": {
    "type": "json_path",
    "balance_path": "data.balance",
    "currency": "CNY",
    "is_available_rule": "> 0"
  },
  "proxy_target": "api.my-provider.com"
}
```

### 7.5 App 架构目标

```
App（编排器，仅生命周期）
├── LifecycleManager    单实例锁 + IPC
├── TrayManager         系统托盘
├── HotkeyManager       全局热键
├── ThemeManager        主题（含莫奈色扩展）
├── AutostartManager    开机自启
├── WindowManager       主窗口 ↔ 悬浮窗
├── SchedulerManager    调度器 + 余额快照
├── ProxyManager        usage_proxy
└── ProviderLoader      供应商加载（FR-PROV-01）
```

### 7.6 技术栈演进路径（需用户审批）

- **主方案**：PyQt6/PySide6 渐进迁移（UI 重写，业务逻辑复用）
- **备选**：Tauri 完全重写（追求极致性能时）
- **决策点**：M3 完成后评估是否启动 M4 迁移
- 详见改进方案第 12 章

---

## 8. 里程碑规划

### 8.1 里程碑总览

| 里程碑 | 版本 | 主题 | 关键需求 |
|--------|------|------|----------|
| M1 | v1.10.0 | 安全与稳定性 | FR-SEC-01/04/05/07、FR-ARC-05、FR-LOG-01~02 |
| M2 | v1.11.0 | 性能与并发 | FR-PFM-01~07、FR-NET-01~03、FR-LOG-03 |
| M3 | v1.12.0 | 主题/UX/供应商扩展 | FR-THM-01~05、FR-UX-02/04/06、FR-ARC-02/04/06、FR-PROV-01~04、FR-PFM-08、FR-CFG-02 |
| M4 | v2.0.0 | 架构演进与功能 | FR-ARC-01、FR-SEC-06、FR-UX-01、FR-QA-01~02、FR-PKG-01 |
| M5+ | v2.x | 技术栈迁移与新功能 | PyQt6 迁移（需审批）、FR-FEAT-03~04 |

### 8.2 M1（v1.10.0）验收标准

- 所有 P0 安全需求完成（FR-SEC-01/04/05）
- 日志脱敏完成（FR-SEC-07）
- 统一日志系统（FR-LOG-01~02）
- 快捷方式注入修复（FR-ARC-05）
- 安全审计通过

> **v1.3 调整**：删除原"配置 schema 升级，旧配置自动迁移（FR-ARC-03/FR-SEC-02）"。

### 8.3 M2（v1.11.0）验收标准

- 冷启动 < 300ms（NFR-PERF-01）
- 闲置内存 < 50MB（NFR-PERF-02）
- 闲置 CPU < 0.1%（NFR-PERF-03）
- 10 账户刷新 < 5s（NFR-PERF-04）
- 性能基准建立（FR-PFM-07）
- 优雅退出（FR-LOG-03）

### 8.4 M3（v1.12.0）验收标准

- 3 套莫奈色主题可用（FR-THM-02）
- 主题编辑器可用（FR-THM-04）
- 主题扩展接口可用（FR-THM-03）
- 主题切换实时生效（FR-THM-05）
- 快捷键可配置（FR-UX-02）
- 供应商扩展机制可用（FR-PROV-01~04）
- 放弃纯黑 dark 主题

> **v1.3 调整**：删除原"系统通知可用（FR-UX-03）"与"阈值告警可用（FR-FEAT-01）"。

### 8.5 M4（v2.0.0）验收标准

- App 类拆分完成（FR-ARC-01）
- CI 测试门禁生效（FR-QA-01）
- 覆盖率 ≥ 85%（NFR-MAINT-01）

> **v1.3 调整**：删除原"自动更新可用（FR-PKG-02）"与"多 Provider 代理路由（FR-NET-04）"。

### 8.6 M5+（v2.x）验收标准

- PyQt6 迁移阶段 1 完成（需用户审批）
- 报告导出、多币种聚合可用

> **v1.3 调整**：删除原"用量预算（FR-FEAT-02）"。

---

## 9. 风险与依赖

### 9.1 关键风险

| 风险 | 概率 | 影响 | 缓解 | 关联需求 |
|------|------|------|------|----------|
| DPAPI 加密导致跨用户迁移困难 | 中 | 中 | 提供重新输入 Key 流程 | FR-SEC-01 |
| 主题切换实时生效不完整 | 中 | 中 | 全组件订阅事件 + 测试 | FR-THM-05 |
| customtkinter 自定义颜色边界 | 中 | 中 | 验证关键组件，必要时换栈 | FR-THM-01 |
| CI 环境无 tkinter 显示 | 高 | 中 | 虚拟显示或 mock | FR-QA-01 |
| PyQt6 迁移期双 UI 维护 | 高 | 高 | 长期分支 + 分模块切换 | 第 7.6 节 |
| 自定义 Provider 配置漏洞 | 中 | 中 | 配置校验 + 白名单 | FR-PROV-01 |
| python_module 解析器代码执行 | 低 | 高 | 仅信任源启用 + 沙箱 | FR-PROV-01 |

> **v1.3 删除项**：删除"配置迁移丢失数据"（FR-ARC-03 已删除）、"自动更新被中间人攻击"（FR-PKG-02 已删除）。

### 9.2 外部依赖

| 依赖 | 用途 | 风险 |
|------|------|------|
| customtkinter | UI 框架 | 维护放缓，主题能力有限 |
| pystray | 系统托盘 | 跨平台行为差异 |
| keyboard | 全局热键 | 权限要求，部分杀软误报 |
| matplotlib | 图表 | 启动慢，待替换 |
| keyring | 非 Windows 凭证 | 新增依赖 |
| tenacity | 重试退避 | 新增依赖 |
| ruff/mypy | 代码质量 | 新增开发依赖 |
| jinja2 | Provider 解析器 | 新增依赖（FR-PROV-01） |

> **v1.3 删除项**：删除 pydantic（FR-ARC-03 已删除，主题模型仍可选使用但不作为配置 schema 强制依赖）。

### 9.3 关键决策点

| 决策点 | 时机 | 决策内容 |
|--------|------|----------|
| DPAPI vs keyring | M1 启动前 | 确认 Windows 优先策略 |
| 主题切换实时生效方案 | M3 启动前 | 验证 customtkinter 边界 |
| Provider 解析器支持 python_module | M3 启动前 | 安全风险评估 |
| PyQt6 迁移启动 | M3 完成后 | 用户审批是否启动 M4 迁移 |
| Nuitka vs PyInstaller | M4 启动前 | 打包模式选择 |

---

## 10. 术语表与参考

### 10.1 术语表

| 术语 | 含义 |
|------|------|
| Provider | AI API 平台提供商（DeepSeek、硅基流动等），含内置与自定义 |
| 悬浮窗 | 无边框置顶小窗口，主窗口最小化后显示 |
| usage_proxy | 本地反向代理，拦截 API 调用统计 token 用量 |
| DPAPI | Windows Data Protection API，与用户绑定的加密 |
| WAL | SQLite Write-Ahead Logging，提升并发写性能 |
| 莫奈色 | 灵感来自莫奈画作的配色方案，非纯黑 |
| ThemeLayer | 主题的语义颜色层（亮/暗各一套） |
| ThemeManager | 主题管理单例，负责注册/应用/广播主题 |
| ProviderLoader | 供应商加载器，扫描配置文件注册 Provider |
| JsonPathProvider | 基于 JSON 路径的声明式 Provider 实现 |

### 10.2 参考文档

- [改进方案 v1.2](file:///d:/#MCP-Serve/deepseek-balance-monitor/deepseek-balance-monitor_改进方案_v1.2_2026-08-07.md) — 技术实现细节、迁移步骤、风险分析
- [README.md](file:///d:/#MCP-Serve/deepseek-balance-monitor/README.md) — 项目说明
- [main.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/main.py) — 应用入口
- [config.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/config.py) — 配置模型
- [balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) — Provider 层
- [scheduler.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/scheduler.py) — 调度器

### 10.3 需求追溯矩阵（需求 ID → 改进项 ID）

| 需求 ID | 改进项 ID | 需求 ID | 改进项 ID |
|---------|-----------|---------|-----------|
| FR-SEC-01 | S-1 | FR-UX-01 | U-1 |
| FR-SEC-04 | S-3 | FR-UX-02 | U-2 |
| FR-SEC-05 | S-4 | FR-UX-04 | U-4 |
| FR-SEC-06 | S-5 | FR-UX-06 | U-6 |
| FR-SEC-07 | NFR-SEC-03 | FR-THM-01 | T-1 |
| FR-PFM-01 | P-1 | FR-THM-02 | T-2 |
| FR-PFM-02 | P-2 | FR-THM-03 | T-3 |
| FR-PFM-03 | P-3/C-1 | FR-THM-04 | 8.6 |
| FR-PFM-04 | P-6 | FR-THM-05 | T-1 |
| FR-PFM-05 | P-4 | FR-PROV-01 | A-2 |
| FR-PFM-06 | P-5 | FR-PROV-02 | A-2 |
| FR-PFM-07 | 2.8 | FR-PROV-03 | — |
| FR-PFM-08 | P-7 | FR-PROV-04 | — |
| FR-ARC-01 | A-1 | FR-QA-01 | Q-1/Q-2 |
| FR-ARC-02 | A-2 | FR-QA-02 | Q-3 |
| FR-ARC-04 | A-4 | FR-PKG-01 | R-1 |
| FR-ARC-05 | A-5 | FR-FEAT-03 | F-3 |
| FR-ARC-06 | A-2 | FR-FEAT-04 | F-4 |
| FR-NET-01 | C-2 | FR-CFG-02 | D-3 |
| FR-NET-02 | C-3 | FR-CFG-03 | S-4 |
| FR-NET-03 | C-4 | | |
| FR-LOG-01 | E-1 | | |
| FR-LOG-02 | E-2 | | |
| FR-LOG-03 | E-3 | | |

> **v1.3 删除项**：FR-SEC-02（S-1 迁移部分）、FR-ARC-03（A-3/D-1）、FR-CFG-01（A-3/D-1 别名）、FR-UX-03（U-3）、FR-UX-05（U-5）、FR-PKG-02（R-2）、FR-FEAT-01（F-1）、FR-FEAT-02（F-2）、FR-NET-04（D-2）。

---

## 11. AI 交接 Checklist

接手本项目的 AI 在开始工作前应完成以下检查：

- [ ] 已阅读本文档第 0 章"文档使用说明"
- [ ] 已阅读改进方案对应章节
- [ ] 已阅读相关源码文件（第 2.2 节文件结构）
- [ ] 已确认当前所在里程碑与负责的需求 ID
- [ ] 已阅读需求的"当前状态"字段，了解现状
- [ ] 已确认需求的依赖关系（依赖需求字段）
- [ ] 已确认验收标准（AC 条目）
- [ ] 已确认关联的非功能需求（NFR）
- [ ] 已确认风险与缓解策略（第 9 章）
- [ ] 实现时在代码注释与 commit message 中引用需求 ID
- [ ] 完成后逐条核对验收标准

---

**文档结束**

> 本 PRD 为产品需求权威基线，与改进方案配套使用。
> 任何需求变更需同步更新本文档与改进方案，并升级版本号。
> 技术栈迁移（第 7.6 节）需用户审批后方可实施。
> v1.3 变更：删除 9 项需求（FR-SEC-02、FR-ARC-03、FR-CFG-01、FR-UX-03、FR-UX-05、FR-PKG-02、FR-FEAT-01、FR-FEAT-02、FR-NET-04），独立需求由 52 项减少至 43 项。
