"""M2 集成验证脚本：端到端验证 M2 里程碑关键功能。

验证 M2 的 11 个 Issue 实现情况：
- ISSUE-PFM-01：matplotlib 延迟加载
- ISSUE-PFM-02：启动期 IO 异步化
- ISSUE-PFM-03：scheduler 线程池改造
- ISSUE-PFM-04：Provider Session 长连接复用
- ISSUE-PFM-05：焦点监视改事件驱动
- ISSUE-PFM-06：usage_proxy 流式行级解析
- ISSUE-PFM-07：性能基准测试建立
- ISSUE-NET-01：scheduler 任务取消
- ISSUE-NET-02：usage_proxy ThreadingHTTPServer
- ISSUE-NET-03：balance_checker 重试与退避
- ISSUE-LOG-03：优雅退出

运行方式：
    python scripts/m2_integration_verify.py
"""
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main"))

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    """验证断言并打印结果。

    Args:
        name: 验证项名称
        condition: 是否通过
        detail: 附加详情
    """
    global passed, failed
    status = "✓ PASS" if condition else "✗ FAIL"
    print(f"  [{status}] {name}" + (f" ({detail})" if detail else ""))
    if condition:
        passed += 1
    else:
        failed += 1


print("=" * 70)
print("M2 里程碑集成验证（v1.11.0）· 性能与并发")
print("=" * 70)

# --- 1. ISSUE-PFM-01：matplotlib 延迟加载 ---
print("\n=== ISSUE-PFM-01 matplotlib 延迟加载 ===")
# 清理 matplotlib 缓存
for mod_name in list(sys.modules.keys()):
    if mod_name == "matplotlib" or mod_name.startswith("matplotlib."):
        del sys.modules[mod_name]
if "usage_curve_window" in sys.modules:
    del sys.modules["usage_curve_window"]

import usage_curve_window
check(
    "启动时不 import matplotlib",
    "matplotlib" not in sys.modules,
    "模块加载后 matplotlib 未被 import",
)

# 首次调用后应加载
usage_curve_window._mpl_cache.clear()
mpl = usage_curve_window._ensure_matplotlib()
check(
    "首次绘图时延迟加载 matplotlib",
    "matplotlib" in sys.modules and bool(mpl),
    "调用 _ensure_matplotlib 后 matplotlib 被 import",
)
check("缓存包含 Figure", "Figure" in mpl)
check("缓存包含 FigureCanvasTkAgg", "FigureCanvasTkAgg" in mpl)
check("缓存包含 mdates", "mdates" in mpl)

# --- 2. ISSUE-PFM-02：启动期 IO 异步化 ---
print("\n=== ISSUE-PFM-02 启动期 IO 异步化 ===")
# 验证 App 类的关键属性与方法（不实例化，避免 tkinter 依赖）
import inspect
from main import App
source = inspect.getsource(App.__init__)
check(
    "__init__ 不直接调用 load_config",
    "load_config()" not in source or "load_config" not in source.split("def _background_init")[0],
    "load_config 延迟到 _background_init",
)
check("__init__ 不创建 UsageHistory", "UsageHistory()" not in source, "建表延迟到后台")
check("__init__ 不创建 UsageProxy", "UsageProxy(" not in source, "代理延迟到后台")
check("_background_init 方法存在", hasattr(App, "_background_init"))
check("_on_loaded 方法存在", hasattr(App, "_on_loaded"))
check("_on_load_failed 方法存在", hasattr(App, "_on_load_failed"))

# --- 3. ISSUE-PFM-03：scheduler 线程池改造 ---
print("\n=== ISSUE-PFM-03 scheduler 线程池改造 ===")
from scheduler import BalanceScheduler, _MAX_WORKERS, _CHECK_TIMEOUT
check("max_workers=4", _MAX_WORKERS == 4, f"_MAX_WORKERS={_MAX_WORKERS}")
check("超时阈值=15s", _CHECK_TIMEOUT == 15, f"_CHECK_TIMEOUT={_CHECK_TIMEOUT}")

from config import AppConfig, SettingsConfig
config = AppConfig(settings=SettingsConfig(interval_sec=60))
scheduler = BalanceScheduler(config)
check("scheduler 初始无 executor", scheduler._executor is None)
scheduler.start()
check("start() 后创建 executor", scheduler._executor is not None)
check("executor max_workers=4", scheduler._executor._max_workers == 4)
check("executor 线程名前缀 balance-check", scheduler._executor._thread_name_prefix == "balance-check")
scheduler.stop()
check("stop() 后关闭 executor", scheduler._executor is None)

# --- 4. ISSUE-PFM-04：Provider Session 长连接复用 ---
print("\n=== ISSUE-PFM-04 Provider Session 长连接复用 ===")
from balance_checker import (
    DeepSeekProvider, get_provider, close_all_provider_sessions,
    _POOL_CONNECTIONS, _POOL_MAXSIZE,
)
check("连接池 connections=5", _POOL_CONNECTIONS == 5)
check("连接池 maxsize=10", _POOL_MAXSIZE == 10)

provider = DeepSeekProvider()
check("Provider 持有 threading.local", hasattr(provider, "_thread_local"))
check("Provider 维护 Session 列表", hasattr(provider, "_all_sessions"))

# 验证同线程复用
sessions = []
def worker():
    s1 = provider._get_session()
    s2 = provider._get_session()
    sessions.append(s1 is s2)
t = threading.Thread(target=worker)
t.start()
t.join()
check("同线程复用同一 Session", sessions[0] is True)

# 验证关闭
provider._get_session()
check("创建 Session 后列表非空", len(provider._all_sessions) >= 1)
provider.close_all_sessions()
check("close_all_sessions 后列表清空", len(provider._all_sessions) == 0)

# --- 5. ISSUE-PFM-05：焦点监视改事件驱动 ---
print("\n=== ISSUE-PFM-05 焦点监视改事件驱动 ===")
from main_window import MainWindow
check("_focus_check_loop 已删除", not hasattr(MainWindow, "_focus_check_loop"))
check("start_focus_monitor 存在", hasattr(MainWindow, "start_focus_monitor"))
check("_on_focus_in 存在", hasattr(MainWindow, "_on_focus_in"))
check("_on_focus_out 存在", hasattr(MainWindow, "_on_focus_out"))
check("_on_focus_loss_confirmed 存在", hasattr(MainWindow, "_on_focus_loss_confirmed"))

# --- 6. ISSUE-PFM-06：usage_proxy 流式行级解析 ---
print("\n=== ISSUE-PFM-06 usage_proxy 流式行级解析 ===")
from usage_proxy import SSEUsageParser

# 跨 chunk 拼接测试
parser = SSEUsageParser()
line = 'data: {"usage": {"prompt_tokens": 100, "total_tokens": 150}}\n'
mid = len(line) // 2
parser.feed(line[:mid])
check("跨 chunk 未完整时不解析", parser.last_usage is None)
parser.feed(line[mid:])
check("跨 chunk 拼接后正确解析", parser.last_usage is not None)
check("usage 内容正确", parser.last_usage["total_tokens"] == 150)

# 内存恒定测试
parser2 = SSEUsageParser()
for i in range(100):
    parser2.feed(f'data: {{"choices": [{{"delta": "{i}"}}]}}\n')
check("长响应 line_buffer 不累积", parser2._line_buffer == "")

# --- 7. ISSUE-PFM-07：性能基准测试建立 ---
print("\n=== ISSUE-PFM-07 性能基准测试建立 ===")
scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
check(
    "启动时间测量脚本存在",
    os.path.exists(os.path.join(scripts_dir, "measure_startup_time.py")),
)
check(
    "资源采样脚本存在",
    os.path.exists(os.path.join(scripts_dir, "sample_resource_usage.py")),
)
docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs")
check(
    "性能基准文档存在",
    os.path.exists(os.path.join(docs_dir, "performance-baseline.md")),
)
# scheduler 埋点
import inspect
scheduler_source = inspect.getsource(BalanceScheduler._check_all)
check("scheduler 埋点记录刷新延迟", "刷新完成" in scheduler_source)

# --- 8. ISSUE-NET-01：scheduler 任务取消 ---
print("\n=== ISSUE-NET-01 scheduler 任务取消 ===")
check(
    "_check_all 使用 as_completed",
    "as_completed" in scheduler_source,
)
check(
    "_check_all 使用 Future cancel",
    ".cancel()" in scheduler_source,
)
check(
    "超时记录 WARN 日志",
    "超时" in scheduler_source and "logger.warning" in scheduler_source,
)

# --- 9. ISSUE-NET-02：usage_proxy ThreadingHTTPServer ---
print("\n=== ISSUE-NET-02 usage_proxy ThreadingHTTPServer ===")
from usage_proxy import UsageProxy
from http.server import ThreadingHTTPServer
proxy = UsageProxy()
proxy.start()
try:
    check(
        "使用 ThreadingHTTPServer",
        isinstance(proxy._server, ThreadingHTTPServer),
    )
    check("daemon_threads=True", proxy._server.daemon_threads is True)
finally:
    proxy.stop()

# --- 10. ISSUE-NET-03：balance_checker 重试与退避 ---
print("\n=== ISSUE-NET-03 balance_checker 重试与退避 ===")
from balance_checker import _MAX_ATTEMPTS, _BACKOFF_SECONDS
check("最大尝试次数=3", _MAX_ATTEMPTS == 3, f"_MAX_ATTEMPTS={_MAX_ATTEMPTS}")
check("退避序列 [1, 2, 4]", _BACKOFF_SECONDS == [1, 2, 4], f"_BACKOFF_SECONDS={_BACKOFF_SECONDS}")

import inspect
make_request_source = inspect.getsource(DeepSeekProvider._make_request)
check("4xx 不重试", "400 <= resp.status_code < 500" in make_request_source)
check("5xx 触发重试", ">= 500" in make_request_source)
check("Timeout 重试", "Timeout" in make_request_source)
check("ConnectionError 重试", "ConnectionError" in make_request_source)
check("重试耗尽标注次数", "重试" in make_request_source and "次后失败" in make_request_source)

# --- 11. ISSUE-LOG-03：优雅退出 ---
print("\n=== ISSUE-LOG-03 优雅退出 ===")
quit_source = inspect.getsource(App._quit)
check("移除 os._exit 作为默认", "sys.exit(0)" in quit_source)
check("--force-exit 应急开关", "--force-exit" in quit_source and "os._exit" in quit_source)
check("scheduler 可选停止", "if self.scheduler is not None" in quit_source)
check("usage_proxy 可选停止", "if self._usage_proxy is not None" in quit_source)
check("关闭 Provider Session", "close_all_provider_sessions" in quit_source)

# --- 汇总 ---
print("\n" + "=" * 70)
print(f"集成验证结果: {passed} 通过, {failed} 失败")
print("=" * 70)
if failed > 0:
    sys.exit(1)
print("M2 里程碑集成验证全部通过")
