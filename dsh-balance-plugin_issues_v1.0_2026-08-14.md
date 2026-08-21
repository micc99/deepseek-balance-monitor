# dsh-balance-plugin · 可执行 Issue 清单

> **文档版本**：v1.0
> **文档日期**：2026-08-14
> **源 PRD**：[dsh-balance-plugin_PRD_v1.0_2026-08-14.md](file:///d:/#MCP-Serve/deepseek-balance-monitor/dsh-balance-plugin_PRD_v1.0_2026-08-14.md)
> **文档目的**：将 PRD 需求拆分为可直接领取执行的工作项（Issue），每个 Issue 含任务清单、验收标准、依赖关系与执行要点
> **语言**：简体中文（技术术语保留英文原文）
> **命名规范**：`ISSUE-DSH-<序号>`，与 PRD 需求 ID（`FR-DSH-xx`）一一对应
> **文档历史**：
> - v1.0（2026-08-14）：初版。内容源自主项目 Issue 清单 v1.3 的 M6 章节，应用户决策拆分为独立文档体系单独维护
> **官方开发指南**：DeepSeek Harness 插件开发规范（`deepseek-harness-plugin-dev`）

---

## 0. 文档使用说明

### 0.1 Issue 字段说明

每个 Issue 统一包含以下字段：

| 字段 | 说明 |
|------|------|
| **Issue ID** | 唯一标识，对应 PRD 需求 ID（`ISSUE-DSH-01` ↔ `FR-DSH-01`） |
| **标题** | 一句话描述任务目标 |
| **版本 / 优先级** | 所属插件版本（v0.1.0 ~ v0.3.0）/ P1~P2 |
| **依赖需求** | 前置完成的 Issue ID（无依赖则标注"无"） |
| **用户故事** | 作为...我希望...以便... |
| **当前状态** | 现状描述 |
| **任务清单** | 可执行的子任务（checkbox） |
| **验收标准** | AC1~ACn 条目，逐项核对 |
| **执行要点** | 技术细节、边界条件、风险提示 |

### 0.2 执行流程

1. 按**版本顺序**推进（v0.1.0 → v0.2.0 → v0.3.0）
2. 领取 Issue 前先检查**依赖需求**是否已完成
3. 实现时在代码注释与 commit message 中引用 Issue ID
4. 完成后逐条核对**验收标准**并勾选
5. 每个版本发布前跑完整测试（见第 6 章测试要求）

### 0.3 Issue 统计概览

| 版本 | 主题 | Issue 数 | P1 | P2 |
|------|------|----------|----|----|
| v0.1.0 | 插件骨架与余额查询服务 | 1 | 1 | 0 |
| v0.2.0 | 余额显示与 agent 工具 | 2 | 1 | 1 |
| v0.3.0 | 打包分发 | 1 | 1 | 0 |
| **合计** | — | **4** | **3** | **1** |

---

## 1. v0.1.0 · 插件骨架与余额查询服务

### ISSUE-DSH-01 · DSH 插件骨架与余额查询服务

- **版本 / 优先级**：v0.1.0 / P1
- **依赖需求**：无
- **对应 PRD 需求**：FR-DSH-01

#### 用户故事
作为 dsh 用户，我希望安装余额插件后，后台自动查询并缓存当前 DeepSeek API 余额，以便后续 UI 展示与 agent 工具共用同一数据源。

#### 当前状态
**未实现**。无 DeepSeek Harness 插件形态；余额查询能力仅存在于主项目 Python 桌面应用（[balance_checker.py](file:///d:/#MCP-Serve/deepseek-balance-monitor/main/balance_checker.py) 的 DeepSeekProvider，可作解析逻辑参照）。

#### 任务清单
- [ ] 创建独立插件项目 `dsh-balance-plugin`（TypeScript，`"type": "module"`）
- [ ] `package.json` 声明 `dsh.bundle.patch` 指向 `cordis.patch.yml`
- [ ] `cordis.patch.yml` 提供 insert 条目（**稳定 id: dsh-balance**，插件行按包名引用）
- [ ] 实现 `BalanceService extends Service`（服务名 `dshBalance`，通过声明合并扩展 `Context` 接口获得类型）
- [ ] `Config` 用 Schemastery schema（禁止普通对象）：`apiKey`（默认经 `!!js` 读环境变量 `DEEPSEEK_API_KEY`）、`refreshIntervalSec`（默认 300）、`requestTimeoutMs`（默认 10000）
- [ ] 调用 `GET https://api.deepseek.com/user/balance`（`Authorization: Bearer <key>`），传递 AbortSignal 支持取消
- [ ] 解析 `balance_infos`：`is_available` / `currency` / `total_balance` / `granted_balance` / `topped_up_balance`
- [ ] 内存缓存最近一次查询结果（余额 + `fetchedAt` 时间戳），UI 与工具共用
- [ ] 定时刷新定时器包进 `ctx.effect()` 并返回 disposer（HMR 卸载自动清理，无残留请求）
- [ ] 错误处理：401（Key 无效）/ 网络失败 / 超时写入服务状态，不崩溃
- [ ] apiKey 缺失时插件给出明确提示（不发起无效请求）
- [ ] 编写单元测试：查询 / 解析 / 缓存 / 错误场景（mock fetch）

#### 验收标准
- [ ] AC1：BalanceService 以 `dshBalance` 服务名注册成功，`ctx.dshBalance` 可访问
- [ ] AC2：定时刷新按配置间隔执行，缓存结果含 `fetchedAt` 时间戳
- [ ] AC3：HMR 卸载插件后定时器被清理（无残留请求）
- [ ] AC4：401 / 网络错误 / 超时返回结构化错误状态，进程不崩溃
- [ ] AC5：apiKey 未配置时给出明确提示
- [ ] AC6：单元测试覆盖查询 / 解析 / 缓存 / 错误场景

#### 执行要点
- 服务名带前缀避免冲突（`dshBalance` 而非 `balance`，扁平命名空间）
- Cordis 规范：Config 必须为 Schemastery schema，默认值写在 schema 中；配置非法 → 插件 FAILED（ValidationError），绝不带不完整配置启动
- 所有注册经 `ctx` 完成；自管资源（定时器）必须 `ctx.effect()`
- 环境变量读取用 cordis.yml 的 `!!js` 标签（**仅 config 与 disabled 字段内有效**）
- DeepSeek API 有限流约束，刷新间隔默认 300s，不宜过短

---

## 2. v0.2.0 · 余额显示与 agent 工具

### ISSUE-DSH-02 · dsh-web 对话框下方余额显示

- **版本 / 优先级**：v0.2.0 / P1
- **依赖需求**：ISSUE-DSH-01
- **对应 PRD 需求**：FR-DSH-02

#### 用户故事
作为用户，我希望在 dsh-web 对话输入框**下方常驻**看到当前 DeepSeek API 余额，以便无需切换应用即可判断是否需要充值。

#### 当前状态
**未实现**。dsh-web 无余额展示能力。

#### 任务清单
- [ ] **前置 Spike**：调研 dsh-web 的 UI 扩展点（状态栏 / 插槽 / 组件注入机制），产出调研结论并归档（插件 README 或 docs）
- [ ] 若存在官方 UI 扩展点：实现对话框下方余额栏（总额 + 币种 + 最后刷新时间）
- [ ] 若无官方扩展点：执行备选方案（工具卡片 `presentCall` / `presentResult` 展示，或向 dsh 上游提出扩展点需求），并记录决策
- [ ] 手动刷新入口（点击余额栏触发即时查询）
- [ ] 点击展开明细：赠送余额（granted）/ 充值余额（topped_up）/ 总额（total）
- [ ] 查询失败显示错误态（Key 无效 / 网络失败）与重试按钮
- [ ] 余额栏不遮挡、不影响输入框与发送按钮的正常交互
- [ ] 编写 UI 手动验收清单（dsh-web 无 headless 测试环境时的替代验证）

#### 验收标准
- [ ] AC1：对话框下方常驻显示当前 DeepSeek API 余额（总额 + 币种）
- [ ] AC2：显示最后刷新时间，支持手动刷新
- [ ] AC3：可展开查看 granted / topped_up / total 明细
- [ ] AC4：查询失败显示错误态与重试入口，不阻塞对话
- [ ] AC5：Spike 调研结论归档

#### 执行要点
- dsh-web 的常驻 UI 扩展机制在插件开发规范中未完全文档化，**Spike 是本 Issue 的前置硬依赖**，结论直接影响实现路径
- 若走工具卡片路径：`presentCall` / `presentResult` 必须是 `(args, result)` 的**纯函数**（不做 I/O、不读会话状态、不用时钟/随机数）；UI 格式不得进入规范值或模型内容
- 手动刷新需节流（如 30s 内仅一次真实请求，其余读缓存），避免触发 DeepSeek API 限流

### ISSUE-DSH-03 · get_deepseek_balance 工具注册（agent 可调用）

- **版本 / 优先级**：v0.2.0 / P2
- **依赖需求**：ISSUE-DSH-01
- **对应 PRD 需求**：FR-DSH-03

#### 用户故事
作为 agent 使用者，我希望让 AI 在对话中直接查询我的 DeepSeek API 余额，以便规划用量与成本。

#### 当前状态
**未实现**。

#### 任务清单
- [ ] `defineTool` 注册工具 `name=get_deepseek_balance`（`inject: ['tools']`）
- [ ] `parameters`：仅可选 `refresh: boolean`（是否跳过缓存强制刷新）
- [ ] `output.schema` 设计为程序化 API 规范值：`{ isAvailable, currencies: [{currency, total, granted, toppedUp}], fetchedAt, stale, error? }`
- [ ] `output.render` 将规范值渲染为模型可读文本（含数据时间戳）
- [ ] `execute` 优先读缓存；`refresh=true` 时强制查询并遵守 `exec.signal`
- [ ] 领域性失败（Key 无效 / 未配置）写入规范值 `error` 字段；仅基础设施故障抛异常
- [ ] 工具最小组合联调：`dsh-tools` + `@deepseek-ai/dsh-system-prompt`（隐式依赖）+ 本插件
- [ ] 编写单元测试：缓存读取 / 强制刷新 / 错误规范值 / Code Mode 调用

#### 验收标准
- [ ] AC1：agent 会话中可调用 get_deepseek_balance 并获得余额
- [ ] AC2：返回规范 JSON 值（非自然语言、非 UI 内容块）
- [ ] AC3：缓存命中时不触发真实 API 请求；响应含 fetchedAt 时间戳
- [ ] AC4：无 apiKey 时返回含 error 的规范值而非抛异常
- [ ] AC5：Code Mode（`await tools.get_deepseek_balance()`）可用

#### 执行要点
- 遵守 execute 硬性规则：返回规范值、遵守 `exec.signal`、注册后不可变（热替换需 dispose 后重注册）
- UI 格式（console 围栏 / diff 等）不得进入规范值或模型内容
- 工具组合必须包含 `@deepseek-ai/dsh-system-prompt`（`dsh-tools` 注入 `systemPrompt` 服务的提供方）

---

## 3. v0.3.0 · 打包分发

### ISSUE-DSH-04 · 插件配置与打包分发

- **版本 / 优先级**：v0.3.0 / P1
- **依赖需求**：ISSUE-DSH-01（建议 ISSUE-DSH-02 / 03 完成后交付）
- **对应 PRD 需求**：FR-DSH-04

#### 用户故事
作为插件使用者，我希望通过 `dsh plugin add` 一条命令完成安装启用，以便快速获得余额显示能力。

#### 当前状态
**未实现**。

#### 任务清单
- [ ] bundle 结构完备：`package.json`（`dsh.bundle.patch`）+ `cordis.patch.yml` + 构建产物 `lib/`
- [ ] `cordis.patch.yml` 条目带稳定 id，插件行按包名引用（Node 模块解析）
- [ ] npm 发布路径：`pnpm publish` 前构建好 `lib/`（用户免 pnpm `allowBuilds` 授权）
- [ ] 本地安装验证：`dsh plugin --profile <p> add ./dsh-balance-plugin`
- [ ] `dsh --profile <p> --dump-config` 验证层组合正确
- [ ] 配置变更 HMR 验证：修改 `refreshIntervalSec` 后插件自动重载（卸载旧实例加载新实例）
- [ ] 插件 README：安装 / 配置项 / 故障排查（PENDING 诊断、apiKey 配置、UI 扩展点说明）
- [ ] 版本号与变更记录（初始 0.1.0，随各版本发布递增）

#### 验收标准
- [ ] AC1：dsh plugin add 本地路径安装成功并生效
- [ ] AC2：--dump-config 可见插件条目与配置
- [ ] AC3：配置变更触发 HMR，定时器无残留
- [ ] AC4：npm 包（或 tarball）分发路径可用
- [ ] AC5：README 覆盖安装 / 配置 / 常见问题

#### 执行要点
- patch 替换目标行时 `config` 是**整体替换非深合并**，覆盖行必须重述该行全部键
- 条目必须带稳定 id，否则每次配置编辑都被视为删除重建重新挂载
- 插件"无输出"先查 fiber 是否 PENDING（inject 缺提供方会静默等待）
- git 分发需自包含 `prepare` 脚本 + 用户侧 pnpm `allowBuilds` 授权；优先 npm/tarball 路径

---

## 4. Issue 依赖关系图

```
ISSUE-DSH-01 (v0.1.0 · 骨架 + 余额查询服务)
├── ISSUE-DSH-02 (v0.2.0 · dsh-web 对话框下方余额显示，前置 Spike 调研 UI 扩展点)
├── ISSUE-DSH-03 (v0.2.0 · get_deepseek_balance 工具注册)
└── ISSUE-DSH-04 (v0.3.0 · 打包分发，建议 02/03 完成后交付)
```

---

## 5. 执行建议

### 5.1 推荐执行顺序

1. **v0.1.0 基础**
   - ISSUE-DSH-01（骨架 + 余额服务，含单元测试）
2. **v0.2.0 展示与工具**（02 与 03 可并行）
   - ISSUE-DSH-01 → ISSUE-DSH-02（Spike 调研 UI 扩展点 → 余额栏实现）
   - ISSUE-DSH-01 → ISSUE-DSH-03（工具注册 + 组合联调）
3. **v0.3.0 分发收尾**
   - ISSUE-DSH-02 / 03 → ISSUE-DSH-04（bundle 打包 + 安装验证 + README）

### 5.2 并行执行提示

- ISSUE-DSH-02 与 ISSUE-DSH-03 均只依赖 ISSUE-DSH-01，二者可并行开发
- ISSUE-DSH-04 依赖 ISSUE-DSH-01（硬依赖），但建议 02/03 完成后交付（保证首发功能完整）
- 本插件项目与主项目（deepseek-balance-monitor 桌面应用）**完全独立**，可随时穿插推进，互不阻塞

---

## 6. 测试要求

每个 Issue 完成后需进行：

- **单元测试**：覆盖 Issue 内新增逻辑（服务查询/解析/缓存/错误、工具规范值/缓存/取消）
- **集成测试**：与依赖 Issue 联调（如工具组合 `dsh-tools` + `dsh-system-prompt` + 本插件）
- **手动验收**：dsh-web 无 headless 测试环境时的替代验证（按各 Issue 手动验收清单执行）
- **回归测试**：HMR 卸载/重载后无资源残留

测试通过后方可执行 Git commit 并发布对应版本。

---

**文档结束**

> 本文档独立于主项目（deepseek-balance-monitor）文档体系维护。
> 每个 Issue 完成后在任务清单与验收标准中勾选，并递增本文档版本号。
