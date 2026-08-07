"""异常日志兼容模块（已弃用，仅作向后兼容）。

历史版本每次异常创建独立 .log 文件，v1.10.0 起统一改用
log_setup.py 的 RotatingFileHandler，单文件 app.log 按大小轮转。

本模块保留 log_exception 接口签名，内部委托给 log_setup.log_exception，
旧调用方无需改动。新代码请直接使用 logging.getLogger(__name__)。
"""
from __future__ import annotations

from log_setup import LOG_DIR, log_exception as _log_exception, setup_logging

# 保留 LOG_DIR 常量供旧测试与外部脚本引用
__all__ = ["LOG_DIR", "log_exception"]


def log_exception(source: str, exc: Exception):
    """记录异常（委托给 log_setup，写入统一 app.log）。"""
    _log_exception(source, exc)
