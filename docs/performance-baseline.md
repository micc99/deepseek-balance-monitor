# DeepSeek 余额监控 · 性能基准基线（ISSUE-PFM-07）

> **文档版本**：v1.0
> **创建日期**：2026-08-14
> **关联 Issue**：ISSUE-PFM-01 ~ ISSUE-PFM-08、ISSUE-NET-01 ~ ISSUE-NET-03
> **适用里程碑**：M2（v1.11.0）
> **测量环境**：Windows 10/11，Python 3.10+

## 1. 性能指标门禁（NFR-PERF-01 ~ 05）

| 编号 | 指标 | 目标值 | 测量方式 | 状态 |
|------|------|--------|----------|------|
| NFR-PERF-01 | 冷启动时间 | < 300ms（10 账户） | `python -X importtime` + 人工计时 | 待测量 |
| NFR-PERF-02 | 闲置内存 | < 50MB | psutil 采样 5 分钟 | 待测量 |
| NFR-PERF-03 | 闲置 CPU | < 0.1% | psutil 采样 5 分钟平均 | 待测量 |
| NFR-PERF-04 | 刷新延迟 | 10 账户 < 5s | scheduler 埋点 | 待测量 |
| NFR-PERF-05 | 性能回归门禁 | CI 回归 > 10% 告警 | CI 自动执行（待 ISSUE-QA-01） | 待 M4 |

## 2. 测量工具

### 2.1 启动时间测量

```bash
python scripts/measure_startup_time.py
```

输出：
- import 耗时前 20 名模块
- 冷启动总耗时
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

### 2.3 刷新延迟埋点

scheduler.py 内置埋点，每轮刷新完成后记录 INFO 日志：
```
刷新完成: N 账户, 耗时=X.XXs (目标 < 5s)
```

## 3. M2 优化措施

| Issue | 措施 | 预期收益 |
|-------|------|----------|
| ISSUE-PFM-01 | matplotlib 延迟加载 | 启动时减少 200-500ms |
| ISSUE-PFM-02 | 启动 IO 异步化 | 首屏渲染 < 200ms |
| ISSUE-PFM-03 | 线程池（max_workers=4） | 线程数 ≤ 4，避免爆炸 |
| ISSUE-PFM-04 | Session 长连接复用 | 减少 TCP/TLS 握手开销 |
| ISSUE-PFM-05 | 焦点事件驱动 | 闲置 CPU < 0.1% |
| ISSUE-PFM-06 | 流式行级解析 | 长响应内存峰值下降 ≥ 50% |
| ISSUE-NET-01 | 任务取消 | 单账户超时不影响其他 |
| ISSUE-NET-02 | ThreadingHTTPServer | 代理并发不排队 |
| ISSUE-NET-03 | 重试退避 | 网络抖动自动恢复 |

## 4. 基准测量结果

> **说明**：以下为 M2 完成后的基准测量结果，需在稳定环境运行 3 次取中位数。
> 实际数值待人工测量后填入。

### 4.1 冷启动时间

| 测量次数 | 耗时（ms） | 是否达标（< 300ms） |
|----------|-----------|---------------------|
| 第 1 次  | 待测量    | -                   |
| 第 2 次  | 待测量    | -                   |
| 第 3 次  | 待测量    | -                   |
| 中位数   | 待测量    | -                   |

### 4.2 闲置资源占用（5 分钟采样）

| 指标     | 平均值 | 峰值 | 是否达标 |
|----------|--------|------|----------|
| 内存 RSS | 待测量 MB | 待测量 MB | -（< 50MB） |
| CPU 占用 | 待测量 %  | 待测量 %  | -（< 0.1%） |

### 4.3 刷新延迟（10 账户场景）

| 测量次数 | 耗时（s） | 是否达标（< 5s） |
|----------|-----------|-------------------|
| 第 1 次  | 待测量    | -                 |
| 第 2 次  | 待测量    | -                 |
| 第 3 次  | 待测量    | -                 |
| 中位数   | 待测量    | -                 |

## 5. CI 集成（待 M4 ISSUE-QA-01）

性能基准作为 CI 的一个 job，回归 > 10% 告警：
- 启动时间测量
- 资源占用采样（缩短至 60s）
- 刷新延迟统计

CI 环境噪声大时取多次中位数。

## 6. 回归验证清单

每次发版前需验证：
- [ ] 冷启动 < 300ms
- [ ] 闲置内存 < 50MB
- [ ] 闲置 CPU < 0.1%
- [ ] 10 账户刷新 < 5s
- [ ] 不达标时阻断发版

---

**文档结束**

> 本文档随 M2 里程碑完成建立，后续发版前需更新测量结果。
> CI 自动执行部分待 M4 ISSUE-QA-01 完成后集成。
