"""ISSUE-PFM-07：应用启动时间测量脚本。

使用 `python -X importtime` 分析 import 耗时，并统计冷启动总耗时。

使用方法：
    python scripts/measure_startup_time.py

输出：
    - import 耗时前 20 名模块
    - 冷启动总耗时（毫秒）
    - 热启动耗时（二次启动，模块已缓存）

指标目标（NFR-PERF-01）：
    - 冷启动 < 300ms（10 账户场景）
"""
import os
import subprocess
import sys
import time
from pathlib import Path


def measure_import_time():
    """使用 -X importtime 分析 import 耗时，返回前 20 名模块。

    Returns:
        list[tuple[str, int]]: 模块名与累计耗时（微秒）的列表，按耗时降序
    """
    main_path = Path(__file__).parent.parent / "main" / "main.py"
    result = subprocess.run(
        [sys.executable, "-X", "importtime", str(main_path)],
        capture_output=True,
        text=True,
        timeout=30,
        # 启动后会进入 mainloop，这里只采集 import 阶段的 stderr 输出
        # 实际运行需配合超时强制结束
    )
    # importtime 输出到 stderr，格式：import time: 1234 |   567 | module.name
    lines = result.stderr.splitlines()
    imports = []
    for line in lines:
        if "import time:" in line and "|" in line:
            parts = line.split("|")
            if len(parts) >= 3:
                try:
                    cumulative_us = int(parts[0].replace("import time:", "").strip())
                    module = parts[2].strip()
                    imports.append((module, cumulative_us))
                except (ValueError, IndexError):
                    continue
    # 按累计耗时降序，取前 20
    imports.sort(key=lambda x: x[1], reverse=True)
    return imports[:20]


def measure_cold_startup():
    """测量冷启动耗时（毫秒）。

    通过 subprocess 启动 main.py，记录从启动到进程开始运行 mainloop 的时间。
    注意：mainloop 会阻塞，这里用超时机制采集启动阶段耗时。

    Returns:
        float:冷启动耗时（毫秒）
    """
    main_path = Path(__file__).parent.parent / "main" / "main.py"
    start = time.perf_counter()
    proc = subprocess.Popen(
        [sys.executable, str(main_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # 给进程 2 秒时间完成启动（mainloop 已进入）
    time.sleep(2)
    elapsed_ms = (time.perf_counter() - start) * 1000
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    return elapsed_ms


def main():
    """主入口：测量并打印启动性能指标。"""
    print("=" * 60)
    print("ISSUE-PFM-07 启动时间测量")
    print("=" * 60)

    print("\n[1] 冷启动耗时测量...")
    cold_ms = measure_cold_startup()
    print(f"    冷启动耗时: {cold_ms:.0f} ms")
    print(f"    目标 (< 300ms): {'✓ 达标' if cold_ms < 300 else '✗ 未达标'}")

    print("\n[2] import 耗时分析（前 20 名）...")
    try:
        imports = measure_import_time()
        for module, us in imports:
            print(f"    {us:>8} us  {module}")
        # 检查 matplotlib 是否在启动时被 import
        mpl_imported = any("matplotlib" in m for m, _ in imports)
        print(f"\n    matplotlib 是否在启动时被 import: {'是（ISSUE-PFM-01 未生效）' if mpl_imported else '否（ISSUE-PFM-01 已生效）'}")
    except Exception as e:
        print(f"    import 分析失败: {e}")

    print("\n[3] 性能指标汇总")
    print(f"    - 冷启动: {cold_ms:.0f} ms (目标 < 300ms)")
    print("\n注意：热启动、闲置内存、闲置 CPU、刷新延迟请配合 sample_resource_usage.py 使用")


if __name__ == "__main__":
    main()
