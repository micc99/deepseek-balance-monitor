"""旧版散落 .log 文件清理脚本。

旧版 error_logger.py 每次异常创建独立 .log 文件，长期运行后 log/ 目录
会堆积大量形如 `YYYYMMDD_HHMMSS_mmm_source.log` 的散落文件。

统一日志系统（log_setup.py）改用单一 app.log + 轮转，本脚本用于一次性
清理旧的散落文件，仅保留 app.log 与其轮转备份。

用法：
    python scripts/cleanup_old_logs.py            # 预览（dry-run）
    python scripts/cleanup_old_logs.py --execute  # 实际删除
    python scripts/cleanup_old_logs.py --log-dir /custom/path
"""
from __future__ import annotations

import argparse
import os
import re
import sys

# 默认指向 main/log/
_DEFAULT_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "main", "log",
)

# 旧版散落文件名格式：YYYYMMDD_HHMMSS_mmm_source.log
_LEGACY_PATTERN = re.compile(r"^\d{8}_\d{6}_\d{3}_.+\.log$")

# 新版统一日志相关文件，需保留
_KEEP_PATTERN = re.compile(r"^app\.log(\.\d+)?$")


def find_legacy_logs(log_dir: str) -> list[str]:
    """扫描目录下所有旧版散落 .log 文件（不含 app.log 及其轮转备份）。"""
    if not os.path.isdir(log_dir):
        return []
    legacy_files = []
    for name in os.listdir(log_dir):
        if _KEEP_PATTERN.match(name):
            continue
        if _LEGACY_PATTERN.match(name):
            legacy_files.append(os.path.join(log_dir, name))
    return sorted(legacy_files)


def main():
    parser = argparse.ArgumentParser(description="清理旧版散落 .log 文件")
    parser.add_argument("--log-dir", default=_DEFAULT_LOG_DIR,
                        help=f"日志目录（默认：{_DEFAULT_LOG_DIR}）")
    parser.add_argument("--execute", action="store_true",
                        help="实际执行删除（默认 dry-run 仅预览）")
    args = parser.parse_args()

    legacy_files = find_legacy_logs(args.log_dir)
    if not legacy_files:
        print(f"[OK] {args.log_dir} 下无旧版散落 .log 文件")
        return 0

    print(f"[发现] {len(legacy_files)} 个旧版散落文件：")
    total_size = 0
    for f in legacy_files:
        size = os.path.getsize(f)
        total_size += size
        print(f"  - {os.path.basename(f)}  ({size:,} bytes)")

    print(f"\n[合计] {total_size:,} bytes")

    if not args.execute:
        print("\n[DRY-RUN] 未指定 --execute，仅预览，不删除文件")
        return 0

    deleted = 0
    for f in legacy_files:
        try:
            os.remove(f)
            deleted += 1
        except OSError as e:
            print(f"[失败] {f}: {e}")
    print(f"\n[完成] 已删除 {deleted}/{len(legacy_files)} 个文件")
    return 0 if deleted == len(legacy_files) else 1


if __name__ == "__main__":
    sys.exit(main())
