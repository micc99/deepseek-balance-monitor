# DeepSeek 余额监控 · 性能基准基线（ISSUE-PFM-07）

> **文档版本**：v1.1
> **创建日期**：2026-08-14
> **最后更新**：2026-08-14
> **关联 Issue**：ISSUE-PFM-01 ~ ISSUE-PFM-08、ISSUE-NET-01 ~ ISSUE-NET-03
> **适用里程碑**：M2（v1.11.0）
> **测量环境**：Windows 10/11，Python 3.10+

> **v1.1 变更说明**：
> - 修复冷启动测量脚本缺陷（原固定 sleep(2) 导致恒为 2004ms，修复后真实值 1341ms）
> - 优化 IPC listener（select.select 替代 settimeout(1) 轮询，降低闲置 CPU 基线）
> - 优化采样脚本（cpu_percent 非阻塞模式，避免测量窗口放大效应）

## 1. 性能指标门禁（NFR-PERF-01 ~ 05）

| 编号 | 指标 | 目标值 | 测量方式 | 状态 |
|------|------|--------|----------|------|
| NFR-PERF-01 | 冷启动时间 | < 300ms（10 账户） | `python -X importtime` + stdout 标记检测 | ✗ 未达标（1341ms） |
| NFR-PERF-02 | 闲置内存 | < 50MB | psutil 采样 5 分钟 | ✓ 达标（平均 30.38 MB） |
| NFR-PERF-03 | 闲置 CPU | < 0.1% | psutil 采样 5 分钟平均 | 待重新测量（脚本已优化） |
| NFR-PERF-04 | 刷新延迟 | 10 账户 < 5s | scheduler 埋点 | ✓ 达标（0.25s） |
| NFR-PERF-05 | 性能回归门禁 | CI 回归 > 10% 告警 | CI 自动执行（待 ISSUE-QA-01） | 待 M4 |

## 2. 测量工具

### 2.1 启动时间测量

```bash
python scripts/measure_startup_time.py
```

输出（同时写入 `main/log/startup_time.log` 和控制台）：
- 冷启动总耗时（通过 `__STARTUP_DONE__` stdout 标记检测，非固定 sleep）
- import 耗时前 20 名模块
- matplotlib 是否在启动时被 import（验证 ISSUE-PFM-01）

### 2.2 资源占用采样

```bash
# 自动查找 main.py 进程
python scripts/sample_resource_usage.py --duration 300 --interval 5

# 指定 PID
python scripts/sample_resource_usage.py --pid 12345 --duration 300 --interval 5
```

依赖：`psutil`（pip install psutil）

输出：日志写入 `main/log/resource_sampling.log`

采样方式：`cpu_percent(interval=None)` 非阻塞模式，返回上次调用以来的平均值，避免测量窗口放大效应。

### 2.3 刷新延迟埋点

scheduler.py 内置埋点，每轮刷新完成后记录 INFO 日志：
```
刷新完成: N 账户, 耗时=X.XXs (目标 < 5s)
```

## 3. M2 优化措施

| Issue | 措施 | 预期收益 | 实测效果 |
|-------|------|----------|----------|
| ISSUE-PFM-01 | matplotlib 延迟加载 | 启动时减少 200-500ms | ✓ matplotlib 未在启动时 import |
| ISSUE-PFM-02 | 启动 IO 异步化 | 首屏渲染 < 200ms | ✓ 首屏立即显示 |
| ISSUE-PFM-03 | 线程池（max_workers=4） | 线程数 ≤ 4，避免爆炸 | ✓ 刷新延迟 0.25s |
| ISSUE-PFM-04 | Session 长连接复用 | 减少 TCP/TLS 握手开销 | ✓ 单元测试通过 |
| ISSUE-PFM-05 | 焦点事件驱动 | 闲置 CPU < 0.1% | ✓ 事件驱动已实现 |
| ISSUE-PFM-06 | 流式行级解析 | 长响应内存峰值下降 ≥ 50% | ✓ 单元测试通过 |
| ISSUE-NET-01 | 任务取消 | 单账户超时不影响其他 | ✓ 单元测试通过 |
| ISSUE-NET-02 | ThreadingHTTPServer | 代理并发不排队 | ✓ 单元测试通过 |
| ISSUE-NET-03 | 重试退避 | 网络抖动自动恢复 | ✓ 单元测试通过 |
| 性能优化 | IPC listener 改 select.select | 闲置 CPU 基线从 ~1% 降至 ~0.1% | 待重新测量 |
| 性能优化 | 采样脚本 cpu_percent 非阻塞 | 避免 1s 测量窗口放大效应 | 待重新测量 |

## 4. 基准测量结果

> **说明**：以下为 M2 完成后的基准测量结果，需在稳定环境运行 3 次取中位数。

### 4.1 冷启动时间

| 测量次数 | 耗时（ms） | 是否达标（< 300ms） | 备注 |
| -------- | ---------- | ------------------- | ---- |
| 第 1 次  | 1446       | 否                  | 首次测量（修复测量脚本后） |
| 第 2 次  | 1341       | 否                  | 二次测量（关闭遗留进程后） |
| 第 3 次  | 待测量     | -                   | -    |
| 中位数   | ~1394      | 否                  | -    |

**未达标根因分析**：
- `requests.adapters` import 耗时 374ms（最大 import 开销）
- `darkdetect` import 耗时 52ms
- `_tkinter` import 耗时 15ms
- import 阶段总耗时约 500-600ms，加上 mainloop 初始化约 700-800ms

**后续优化方向**（方案 5，待评估）：
- 将 `import requests` 延迟到首次余额查询时（类似 PFM-01 matplotlib 延迟加载）
- 预期收益：冷启动减少 ~400ms，降至 ~900-1000ms
- 仍无法达到 300ms 目标（tkinter + customtkinter 本身约 300ms）
- 300ms 目标可能需要重新评估（或考虑 PyQt6 迁移，见 ISSUE-MIGRATE-PyQt6）

### 4.2 闲置资源占用（5 分钟采样）

> **注意**：以下数据使用旧版采样脚本（cpu_percent interval=1）测量，存在测量窗口放大效应。
> 新版采样脚本（cpu_percent interval=None）已部署，待重新测量获取准确数据。

| 指标     | 平均值    | 峰值     | 是否达标 |
| -------- | --------- | -------- | -------- |
| 内存 RSS | 30.38 MB  | 81.74 MB | 平均达标，峰值未达标 |
| CPU 占用 | 3.738%    | 28.100%  | 否（含测量放大效应） |

**CPU 未达标根因分析**：
1. ~~IPC listener 1s 超时轮询~~（已修复，改用 select.select）
2. ~~采样脚本 cpu_percent(interval=1) 测量窗口放大~~（已修复，改用 interval=None）
3. scheduler 60s 间隔刷新瞬时 CPU 峰值（正常行为，非闲置状态）
4. 28.1% 峰值出现在 scheduler 刷新时刻（非真实闲置）

**内存峰值 81.74 MB 根因**：
- 启动时 `_background_init` 并发执行多个重操作（DPAPI 解密 + SQLite 建表 + 代理绑定 + 首次刷新）
- 启动完成后内存降至 26 MB（临时对象被 GC 回收）
- 后续可通过方案 4（错峰初始化）优化

### 4.3 刷新延迟（10 账户场景）

| 测量次数 | 耗时（s） | 是否达标（< 5s） |
| -------- | --------- | ---------------- |
| 第 1 次  | 0.25      | 是               |
| 第 2 次  | 0.29      | 是               |
| 第 3 次  | 0.21      | 是               |
| 中位数   | 0.25      | 是               |

**达标分析**：刷新延迟 0.25s 远低于 5s 目标，ThreadPoolExecutor(max_workers=4) + Session 复用效果显著。

## 5. 待重新测量项

以下指标需使用优化后的测量工具重新测量：

- [ ] 闲置 CPU（使用新采样脚本，预期 < 0.5%）
- [ ] 闲置内存峰值（IPC 优化后预期下降）
- [ ] 冷启动时间（3 次取中位数）

## 6. CI 集成（待 M4 ISSUE-QA-01）

性能基准作为 CI 的一个 job，回归 > 10% 告警：
- 启动时间测量
- 资源占用采样（缩短至 60s）
- 刷新延迟统计

CI 环境噪声大时取多次中位数。

## 7. 回归验证清单

每次发版前需验证：
- [ ] 冷启动 < 300ms（当前 1341ms，需进一步优化或重新评估目标）
- [ ] 闲置内存 < 50MB（平均达标）
- [ ] 闲置 CPU < 0.1%（待重新测量）
- [ ] 10 账户刷新 < 5s（达标）
- [ ] 不达标时阻断发版

---

**文档结束**

> 本文档随 M2 里程碑完成建立，后续发版前需更新测量结果。
> CI 自动执行部分待 M4 ISSUE-QA-01 完成后集成。
> 冷启动 300ms 目标可能需要重新评估（tkinter 框架本身约 300ms 开销）。
