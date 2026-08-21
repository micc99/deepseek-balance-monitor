# dsh-balance-plugin · 产品需求文档（PRD）

> **文档版本**：v1.0
> **文档日期**：2026-08-14
> **适用产品**：dsh-balance-plugin（DeepSeek Harness 余额插件，规划中，未发布）
> **文档目的**：作为插件项目的权威需求基线与 AI 协作交接文档，独立于主项目文档体系维护
> **配套文档**：[dsh-balance-plugin_issues_v1.0_2026-08-14.md](file:///d:/#MCP-Serve/deepseek-balance-monitor/dsh-balance-plugin_issues_v1.0_2026-08-14.md)（可执行 Issue 清单，以下简称"Issue 清单"）
> **技术基线**：DeepSeek Harness（DSH）插件框架 —— Cordis（插件 = 导出 `apply` 函数的 TypeScript 模块）
> **语言**：简体中文（技术术语保留英文原文）
> **文档历史**：
> - v1.0（2026-08-14）：初版。内容源自主项目 PRD v1.5 的 5.13 DSH 模块与 M6 里程碑，应用户决策拆分为独立文档体系单独维护

---

## 0. 文档使用说明（AI 交接必读）

### 0.1 项目定位与主项目的关系

**dsh-balance-plugin** 是一个独立的 DeepSeek Harness（Cordis）插件项目，为 dsh-web（DeepSeek Harness Web UI）提供**对话框下方的 DeepSeek API 余额快速查询能力**。

| 维度 | 说明 |
|------|------|
| 形态 | TypeScript Cordis 插件（`dsh-balance-plugin` npm 包） |
| 宿主 | DeepSeek Harness（dsh / dsh-web） |
| 与主项目关系 | **并行交付线，互不依赖**：不引用、不修改 deepseek-balance-monitor（桌面应用）任何代码 |
| 版本号 | 独立语义化版本（v0.x.x），不占用主项目版本序列（主项目为 v1.x/v2.x） |
| 交付节奏 | 独立排期，不与主项目里程碑（M1~M5+）互相阻塞 |

**拆分原因（用户决策）**：DSH 插件与桌面应用技术栈（TypeScript vs Python）、交付物（npm 包 vs Windows exe）、宿主环境（DSH vs Windows 桌面）完全不同，且无代码依赖，故拆分为独立文档体系维护，避免主项目文档膨胀。

**代码参照关系**：插件余额解析逻辑可**参照**（非复用）主项目 [balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 的 DeepSeekProvider（`GET https://api.deepseek.com/user/balance` 响应解析）。

### 0.2 ID 命名规范

| 前缀 | 含义 | 示例 |
|------|------|------|
| `FR-DSH-xx` | 功能需求 | FR-DSH-01 |
| `ISSUE-DSH-xx` | 可执行 Issue（与 FR 一一对应） | ISSUE-DSH-01 |

> ID 前缀 `DSH` 沿用自主项目拆分前定义，保持历史引用可追溯。

### 0.3 AI 接手指引

接手本插件的 AI 应按以下顺序阅读：

1. **第 1 章 产品概述** — 理解定位、用户与范围边界
2. **第 2 章 项目现状** — 了解起点（未实现）
3. **第 3 章 需求总览矩阵** — 全景视图
4. **第 4 章 功能需求** — 按条阅读（用户故事/详细描述/验收标准/优先级/依赖）
5. **第 5 章 版本规划** — 了解交付节奏（v0.1.0 → v0.3.0）
6. **第 6 章 风险与依赖** — 实施前必读
7. **第 7 章 开发规范要点** — Cordis 硬性规则速查
8. 最后阅读 **Issue 清单** 领取工作项

**执行任务时的引用规则**：
- 实现某需求时，在代码注释或 commit message 中引用需求 ID（如 `实现 FR-DSH-01`）
- 验收时严格按"验收标准"条目逐项核对
- 官方开发指南：DeepSeek Harness 插件开发规范（`deepseek-harness-plugin-dev`）

### 0.4 优先级约定

| 优先级 | 含义 |
|--------|------|
| **P1** | 核心，首发必需 |
| **P2** | 重要，首发后跟进 |

---

## 1. 产品概述

### 1.1 产品定位

**dsh-balance-plugin** 是一款 DeepSeek Harness 插件，在 dsh-web 对话输入框**下方常驻显示当前 DeepSeek API 余额**，让用户在编程对话过程中无需切换应用即可掌握 API 成本状态；同时向 agent 注册余额查询工具，让 AI 可直接查询余额辅助用量规划。

**范围边界（本期）**：**仅针对 deepseek-api 优化，不做多 Provider**。多 Provider 支持留待后续版本评估（见 5.3 远期展望）。

### 1.2 目标用户

| 用户画像 | 核心诉求 |
|----------|----------|
| dsh / dsh-web 使用者（DeepSeek API 重度用户） | 编程时快速看到余额，及时充值不中断工作流 |
| agent 工作流用户 | 让 AI 在对话中直接查询余额，规划用量与成本 |

### 1.3 核心价值

1. **零切换**：余额常驻对话框下方，不打断编程心流
2. **双通道**：人看余额栏 + agent 调工具，共用同一缓存数据源
3. **低成本**：缓存 + 可配置刷新间隔 + 手动刷新节流，尊重 DeepSeek API 限流
4. **易安装**：`dsh plugin add` 一条命令启用，配置变更 HMR 生效

### 1.4 非目标（明确不做）

- ❌ 多 Provider 余额查询（硅基流动/Moonshot 等，本期仅 deepseek-api）
- ❌ 余额历史曲线 / 用量统计图表（主项目桌面应用的领域）
- ❌ 阈值告警 / 系统通知（沿用主项目用户决策：不做告警）
- ❌ 与主项目桌面应用的数据互通（互不依赖）

---

## 2. 项目现状

**未实现**。目前无任何 DeepSeek Harness 插件形态的代码。

可参照的资源：
- 主项目 [balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 的 DeepSeekProvider：API 端点与响应解析逻辑（`balance_infos` 字段结构）
- DeepSeek Harness 插件开发规范（`deepseek-harness-plugin-dev`）：Cordis 框架约定

---

## 3. 需求总览矩阵

| 需求 ID | 标题 | 优先级 | 版本 | 依赖 |
|---------|------|--------|------|------|
| FR-DSH-01 | DSH 插件骨架与余额查询服务 | P1 | v0.1.0 | 无 |
| FR-DSH-02 | dsh-web 对话框下方余额显示 | P1 | v0.2.0 | FR-DSH-01 |
| FR-DSH-03 | get_deepseek_balance 工具注册（agent 可调用） | P2 | v0.2.0 | FR-DSH-01 |
| FR-DSH-04 | 插件配置与打包分发 | P1 | v0.3.0 | FR-DSH-01（建议 02/03 完成后交付） |
| **合计** | **4 项** | P1×3 / P2×1 | | |

---

## 4. 功能需求

### FR-DSH-01 · DSH 插件骨架与余额查询服务

- **用户故事**：作为 dsh 用户，我希望安装余额插件后，后台自动查询并缓存当前 DeepSeek API 余额，以便后续 UI 展示与 agent 工具共用同一数据源。
- **当前状态**：**未实现**。
- **详细描述**：
  - **项目形态**：独立 TypeScript 插件项目 `dsh-balance-plugin`（`"type": "module"`），`package.json` 声明 `dsh.bundle.patch` 指向 `cordis.patch.yml`，条目带稳定 id（`dsh-balance`）
  - **服务**：`BalanceService extends Service`，服务名 `dshBalance`（带前缀避免扁平命名空间冲突），通过声明合并扩展 `Context` 接口获得类型
  - **配置**（Schemastery schema，默认值写在 schema，禁止普通对象）：
    - `apiKey`：默认经 cordis.yml `!!js` 标签读环境变量 `DEEPSEEK_API_KEY`（**仅 config 与 disabled 字段内有效**）
    - `refreshIntervalSec`：默认 300（DeepSeek API 有限流约束，不宜过短）
    - `requestTimeoutMs`：默认 10000
  - **查询**：`GET https://api.deepseek.com/user/balance`（`Authorization: Bearer <key>`），传递 AbortSignal 支持取消
  - **解析**：`balance_infos` 数组的 `is_available` / `currency` / `total_balance` / `granted_balance` / `topped_up_balance`
  - **缓存**：内存缓存最近一次结果 + `fetchedAt` 时间戳，UI 与工具共用
  - **资源管理**：定时刷新定时器包进 `ctx.effect()` 并返回 disposer（HMR 卸载自动清理，无残留请求）
  - **错误处理**：401（Key 无效）/ 网络失败 / 超时写入服务状态，不崩溃；apiKey 缺失时明确提示，不发起无效请求
- **验收标准**：
  1. AC1：服务以 `dshBalance` 注册成功，`ctx.dshBalance` 可访问
  2. AC2：定时刷新按配置间隔执行，缓存含 `fetchedAt`
  3. AC3：HMR 卸载后定时器被清理，无残留请求
  4. AC4：401 / 网络错误 / 超时返回结构化错误状态，进程不崩溃
  5. AC5：apiKey 未配置时给出明确提示
  6. AC6：单元测试覆盖查询 / 解析 / 缓存 / 错误场景
- **优先级**：P1
- **所属版本**：v0.1.0
- **依赖需求**：无

### FR-DSH-02 · dsh-web 对话框下方余额显示

- **用户故事**：作为用户，我希望在 dsh-web 对话输入框**下方常驻**看到当前 DeepSeek API 余额，以便无需切换应用即可判断是否需要充值。
- **当前状态**：**未实现**。
- **详细描述**：
  - **前置 Spike**：调研 dsh-web 的 UI 扩展点（状态栏 / 插槽 / 组件注入机制），结论归档；若无官方扩展点，执行备选方案（工具卡片 `presentCall` / `presentResult` 展示，或向 dsh 上游提出扩展点需求）并记录决策
  - **余额栏**：对话框下方常驻显示总额 + 币种 + 最后刷新时间
  - **交互**：手动刷新（节流，如 30s 内仅一次真实请求，其余读缓存）；点击展开明细（granted / topped_up / total）
  - **错误态**：查询失败显示错误原因与重试按钮，不阻塞对话
  - **约束**：不遮挡、不影响输入框与发送按钮的正常交互
- **验收标准**：
  1. AC1：对话框下方常驻显示余额（总额 + 币种）
  2. AC2：显示最后刷新时间，支持手动刷新
  3. AC3：可展开查看 granted / topped_up / total 明细
  4. AC4：查询失败显示错误态与重试入口，不阻塞对话
  5. AC5：Spike 调研结论归档
- **优先级**：P1
- **所属版本**：v0.2.0
- **依赖需求**：FR-DSH-01

### FR-DSH-03 · get_deepseek_balance 工具注册（agent 可调用）

- **用户故事**：作为 agent 使用者，我希望让 AI 在对话中直接查询我的 DeepSeek API 余额，以便规划用量与成本。
- **当前状态**：**未实现**。
- **详细描述**：
  - **注册**：`defineTool` 注册 `name=get_deepseek_balance`（`inject: ['tools']`），参数仅可选 `refresh: boolean`（跳过缓存强制刷新）
  - **规范值**：`output.schema` 设计为程序化 API —— `{ isAvailable, currencies: [{currency, total, granted, toppedUp}], fetchedAt, stale, error? }`；`output.render` 渲染为模型可读文本（含时间戳）
  - **执行约定**：缓存优先（命中不发起真实请求）；强制查询时遵守 `exec.signal`；领域性失败（Key 无效 / 未配置）写入规范值 `error` 字段，仅基础设施故障抛异常
  - **Code Mode**：`await tools.get_deepseek_balance()` 可直接调用
- **验收标准**：
  1. AC1：agent 会话中可调用并返回余额
  2. AC2：返回规范 JSON 值（非自然语言、非 UI 内容块）
  3. AC3：缓存命中不触发真实请求；响应含 `fetchedAt`
  4. AC4：无 apiKey 时返回含 error 的规范值而非抛异常
  5. AC5：Code Mode 调用可用
- **优先级**：P2
- **所属版本**：v0.2.0
- **依赖需求**：FR-DSH-01

### FR-DSH-04 · 插件配置与打包分发

- **用户故事**：作为插件使用者，我希望通过 `dsh plugin add` 一条命令完成安装启用，以便快速获得余额显示能力。
- **当前状态**：**未实现**。
- **详细描述**：
  - **bundle 结构**：`package.json`（`dsh.bundle.patch`）+ `cordis.patch.yml`（稳定 id、按包名引用）+ 构建产物 `lib/`
  - **分发路径**：npm 发布（`pnpm publish` 前构建好 `lib/`，用户免 pnpm `allowBuilds` 授权）或 tarball；git 分发需自包含 `prepare` 脚本
  - **验证**：`dsh plugin --profile <p> add <path>` 本地安装、`dsh --profile <p> --dump-config` 层组合验证、配置变更 HMR 生效（定时器无残留）
  - **文档**：README 覆盖安装 / 配置项 / 故障排查（PENDING 诊断、apiKey 配置、UI 扩展点说明）
- **验收标准**：
  1. AC1：dsh plugin add 本地路径安装成功并生效
  2. AC2：--dump-config 可见插件条目与配置
  3. AC3：配置变更触发 HMR，定时器无残留
  4. AC4：npm 包（或 tarball）分发路径可用
  5. AC5：README 覆盖安装 / 配置 / 常见问题
- **优先级**：P1
- **所属版本**：v0.3.0
- **依赖需求**：FR-DSH-01（建议 FR-DSH-02 / 03 完成后交付）

---

## 5. 版本规划

### 5.1 版本总览

插件采用独立语义化版本，分三个阶段交付：

| 版本 | 主题 | 需求 | 交付物 |
|------|------|------|--------|
| v0.1.0 | 插件骨架与余额查询服务 | FR-DSH-01 | BalanceService 可用（含单元测试），可本地加载调试 |
| v0.2.0 | 余额显示与 agent 工具 | FR-DSH-02、FR-DSH-03 | dsh-web 对话框下方余额栏 + get_deepseek_balance 工具 |
| v0.3.0 | 打包分发 | FR-DSH-04 | npm 包 / tarball，`dsh plugin add` 一条命令安装，README 完备 |

### 5.2 各版本验收标准

**v0.1.0**：
- BalanceService 余额查询服务可用（FR-DSH-01 全部 AC）
- 单元测试通过（查询 / 解析 / 缓存 / 错误场景）

**v0.2.0**：
- dsh-web 对话框下方余额显示可用（FR-DSH-02 全部 AC）
- get_deepseek_balance 工具 agent 可调用（FR-DSH-03 全部 AC）

**v0.3.0**：
- `dsh plugin add` 一条命令完成安装，配置变更 HMR 生效（FR-DSH-04 全部 AC）

### 5.3 远期展望（不在本期范围）

- 多 Provider 支持（硅基流动 / Moonshot / OpenRouter / 智谱等，对齐主项目 PROVIDERS 注册表思路）
- 余额不足提醒（主项目用户决策不做告警，暂不规划）
- 与主项目桌面应用的数据互通（暂无需求）

---

## 6. 风险与依赖

### 6.1 关键风险

| 风险 | 概率 | 影响 | 缓解策略 | 关联需求 |
|------|------|------|----------|----------|
| dsh-web UI 扩展点未文档化 | 高 | 高 | 前置 Spike 调研；备选工具卡片方案（`presentCall` / `presentResult`）；必要时向 dsh 上游提需求 | FR-DSH-02 |
| DeepSeek API 限流 | 低 | 中 | 缓存 + 可配置间隔（默认 300s）+ 手动刷新节流 | FR-DSH-01 |
| Cordis 规范踩坑（PENDING 静默等待 / patch 整体替换 / 服务名冲突） | 中 | 中 | 执行要点已列明；开发检查清单逐项核对 | 全部 |
| 工具组合缺隐式依赖（`dsh-system-prompt`） | 中 | 低 | 联调时确保组合完整 | FR-DSH-03 |

### 6.2 外部依赖

| 依赖 | 用途 | 说明 |
|------|------|------|
| `@deepseek-ai/cordis` | 插件框架（Context / Service） | 核心 |
| `@deepseek-ai/schemastery` | 配置 schema | 核心 |
| `@deepseek-ai/dsh-tools` | 工具注册（defineTool） | FR-DSH-03 |
| `@deepseek-ai/dsh-system-prompt` | 工具组合隐式依赖（systemPrompt 服务提供方） | 联调必需 |
| DeepSeek API（`/user/balance`） | 余额数据源 | 有限流约束 |
| dsh CLI（`dsh plugin add` / `--dump-config`） | 安装与验证 | 分发验证 |

---

## 7. 开发规范要点（Cordis 硬性规则速查）

> 完整规范见 DeepSeek Harness 插件开发规范（`deepseek-harness-plugin-dev`）。以下为高频规则：

1. **插件形态**：导出 `apply(ctx, config)` 函数；可选 `name` 与 `inject`
2. **配置**：必须用 Schemastery schema（禁止普通对象），默认值写在 schema；配置非法 → 插件 FAILED（ValidationError），绝不带不完整配置启动
3. **服务**：`Service` 子类 + 声明合并扩展 `Context` 接口；服务名带自有前缀（`dshBalance`）
4. **资源管理**：一切注册皆副作用（自动清理）；自管资源（定时器/连接）必须包 `ctx.effect()` 并返回 disposer
5. **工具 execute**：返回规范 JSON 值（非内容块）；遵守 `exec.signal`；领域性失败写规范值不抛异常；注册后不可变
6. **展示器**：`presentCall` / `presentResult` 必须是 `(args, result)` 纯函数；UI 格式不进规范值或模型内容
7. **cordis.yml**：条目带稳定 id（否则 HMR 删除重建）；patch 替换 config 是整体替换非深合并
8. **诊断**：插件"无输出"先查 fiber 是否 PENDING（inject 缺提供方会静默等待）
9. **分发**：bundle manifest（`dsh.bundle.patch`）；优先 npm/tarball（免 pnpm `allowBuilds` 授权）

---

**文档结束**

> 本文档独立于主项目（deepseek-balance-monitor）文档体系维护。
> 需求变更时同步更新本文档与 Issue 清单，并递增两侧版本号。
