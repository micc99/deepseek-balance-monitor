"""ISSUE-PFM-07：应用资源占用采样脚本。

定期采样目标进程的内存与 CPU 占用，写入日志文件，用于验证 NFR-PERF-02/03：
    - 闲置内存 < 50MB
    - 闲置 CPU < 0.1%

使用方法：
    python scripts/sample_resource_usage.py [--pid PID] [--duration 300] [--interval 5]

若不指定 --pid，则尝试查找名为 main.py 的进程。

依赖：psutil（pip install psutil）
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# 配置日志
LOG_DIR = Path(__file__).parent.parent / "main" / "log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "resource_sampling.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def find_target_pid():
    """查找名为 main.py 的进程 PID。

    Returns:
        int | None: 找到的 PID，未找到返回 None
    """
    try:
        import psutil
    except ImportError:
        logger.error("psutil 未安装，请运行: pip install psutil")
        return None

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            if any("main.py" in str(arg) for arg in cmdline):
                logger.info("找到目标进程: PID=%d, cmdline=%s", proc.info["pid"], cmdline)
                return proc.info["pid"]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def sample_process(pid: int, duration: int, interval: int):
    """采样目标进程的内存与 CPU 占用。

    Args:
        pid:       目标进程 PID
        duration:  采样总时长（秒）
        interval:  采样间隔（秒）
    """
    try:
        import psutil
    except ImportError:
        logger.error("psutil 未安装，请运行: pip install psutil")
        return

    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        logger.error("进程 %d 不存在", pid)
        return

    logger.info("开始采样: PID=%d, 时长=%ds, 间隔=%ds", pid, duration, interval)
    logger.info("目标: 闲置内存 < 50MB, 闲置 CPU < 0.1%")

    samples = []
    start = time.time()
    while time.time() - start < duration:
        try:
            mem_info = proc.memory_info()
            rss_mb = mem_info.rss / (1024 * 1024)
            cpu_percent = proc.cpu_percent(interval=1)
            samples.append((rss_mb, cpu_percent))
            logger.info(
                "采样: RSS=%.2f MB, CPU=%.3f%% (目标: RSS<50MB, CPU<0.1%%)",
                rss_mb, cpu_percent,
            )
        except psutil.NoSuchProcess:
            logger.warning("进程 %d 已退出", pid)
            break
        time.sleep(max(0, interval - 1))  # cpu_percent 已等待 1 秒

    if not samples:
        logger.warning("无有效采样数据")
        return

    # 汇总统计
    rss_values = [s[0] for s in samples]
    cpu_values = [s[1] for s in samples]
    avg_rss = sum(rss_values) / len(rss_values)
    avg_cpu = sum(cpu_values) / len(cpu_values)
    max_rss = max(rss_values)
    max_cpu = max(cpu_values)

    logger.info("=" * 60)
    logger.info("采样汇总 (%d 次, %ds)", len(samples), duration)
    logger.info("  内存 RSS: 平均=%.2f MB, 峰值=%.2f MB (目标 < 50MB)", avg_rss, max_rss)
    logger.info("  CPU:     平均=%.3f%%, 峰值=%.3f%% (目标 < 0.1%%)", avg_cpu, max_cpu)
    logger.info("  内存达标: %s", "✓" if avg_rss < 50 else "✗")
    logger.info("  CPU 达标: %s", "✓" if avg_cpu < 0.1 else "✗")
    logger.info("日志已写入: %s", LOG_FILE)


def main():
    """主入口：解析参数并启动采样。"""
    parser = argparse.ArgumentParser(description="ISSUE-PFM-07 资源占用采样")
    parser.add_argument("--pid", type=int, default=None, help="目标进程 PID（默认自动查找）")
    parser.add_argument("--duration", type=int, default=300, help="采样总时长（秒，默认 300）")
    parser.add_argument("--interval", type=int, default=5, help="采样间隔（秒，默认 5）")
    args = parser.parse_args()

    pid = args.pid or find_target_pid()
    if pid is None:
        logger.error("未找到目标进程，请通过 --pid 指定，或先启动 main.py")
        sys.exit(1)

    sample_process(pid, args.duration, args.interval)


if __name__ == "__main__":
    main()
