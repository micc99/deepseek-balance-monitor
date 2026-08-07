"""统一日志配置模块。

使用 logging.handlers.RotatingFileHandler 替代旧的散落 .log 文件，
单文件 app.log，按大小轮转（maxBytes=2MB，backupCount=5），
避免长期运行后 log/ 目录膨胀。

日志格式：%(asctime)s | %(levelname)s | %(name)s | %(message)s
文件记录 DEBUG 级别，控制台记录 INFO 级别（开发时）。

兼容入口：log_exception(source, exc) 内部转 logger.exception，
保留旧调用方无需改动。
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_MAX_BYTES = 2 * 1024 * 1024  # 2MB
_BACKUP_COUNT = 5
_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

# 全局初始化守卫，避免重复添加 handler
_initialized = False
_logger_lock = logging.threading.Lock()


def setup_logging(level: str = "INFO", console: bool = True) -> logging.Logger:
    """初始化根 logger，配置 RotatingFileHandler 与（可选）Console handler。

    同时安装日志脱敏过滤器（ISSUE-SEC-07），扫描所有日志消息中的 API Key
    并替换为 `sk-***`，避免日志泄露。

    Args:
        level:   根 logger 级别（"DEBUG" / "INFO" / "WARN" / "ERROR"）
        console: 是否附加控制台 handler（开发时 True，打包后可 False）

    Returns:
        根 logger 实例
    """
    global _initialized
    with _logger_lock:
        root = logging.getLogger()

        # 清理可能存在的旧 handler，避免重复
        if _initialized:
            for h in list(root.handlers):
                root.removeHandler(h)

        os.makedirs(LOG_DIR, exist_ok=True)

        formatter = logging.Formatter(_LOG_FORMAT)

        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        if console:
            console_handler = logging.StreamHandler(stream=sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            root.addHandler(console_handler)

        # 安装日志脱敏过滤器（ISSUE-SEC-07）
        # 延迟导入避免循环依赖
        try:
            from secret_filter import install_secret_redaction
            install_secret_redaction(root)
        except ImportError:
            pass

        # 解析级别字符串
        level_value = _parse_level(level)
        root.setLevel(level_value)

        _initialized = True
        root.debug("Logging initialized: level=%s, file=%s", level, LOG_FILE)
        return root


def _parse_level(level: str) -> int:
    """将级别字符串解析为 logging 模块的数值。"""
    mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return mapping.get(str(level).upper(), logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """便捷获取 logger，等价于 logging.getLogger(name)。"""
    return logging.getLogger(name)


def log_exception(source: str, exc: Exception):
    """兼容旧 error_logger 接口：将异常通过标准 logger 记录。

    Args:
        source: 异常来源描述（如模块名.方法名），作为 logger 名称的一部分
        exc:    捕获到的异常对象
    """
    logger = logging.getLogger(f"exception.{source}")
    if not logger.handlers and not logging.getLogger().handlers:
        # 若日志系统未初始化（例如早期错误），先做兜底初始化
        setup_logging()
    logger.error(
        "Exception in %s: %s: %s",
        source,
        type(exc).__name__,
        exc,
        exc_info=(type(exc), exc, exc.__traceback__),
    )


def set_level(level: str):
    """运行时调整根 logger 级别。"""
    logging.getLogger().setLevel(_parse_level(level))
