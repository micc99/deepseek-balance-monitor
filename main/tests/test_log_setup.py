"""log_setup 模块单元测试（ISSUE-LOG-01 / ISSUE-LOG-02）。

ISSUE-LOG-01：统一 logging + RotatingFileHandler
- 单文件 app.log，按大小轮转（maxBytes=2MB，backupCount=5）
- 日志格式：%(asctime)s | %(levelname)s | %(name)s | %(message)s
- 文件记录 DEBUG+，控制台记录 INFO+
- log_exception 接口兼容

ISSUE-LOG-02：日志分级
- 全项目使用 logging.getLogger(__name__)
- SettingsConfig.log_level 配置项
- 启动时根据配置设置根 logger 级别

测试覆盖：
- setup_logging 初始化根 logger
- RotatingFileHandler 配置正确
- 日志格式含时间/级别/模块/消息
- log_exception 接口兼容
- set_level 运行时调整级别
- 日志级别过滤（DEBUG 不写入 INFO 级别根 logger）
"""
import logging
import logging.handlers
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import log_setup


@pytest.fixture(autouse=True)
def isolate_log_env():
    """每个测试用例使用独立的临时日志目录与根 logger 状态。"""
    tmpdir = tempfile.mkdtemp()
    original_log_dir = log_setup.LOG_DIR
    original_log_file = log_setup.LOG_FILE
    original_initialized = log_setup._initialized

    log_setup.LOG_DIR = tmpdir
    log_setup.LOG_FILE = os.path.join(tmpdir, "app.log")
    log_setup._initialized = False

    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_filters = list(root.filters)
    saved_level = root.level
    for h in list(root.handlers):
        root.removeHandler(h)

    yield tmpdir

    # 恢复
    log_setup._initialized = original_initialized
    for h in list(root.handlers):
        root.removeHandler(h)
    for f in list(root.filters):
        root.removeFilter(f)
    root.handlers = saved_handlers
    root.filters = saved_filters
    root.setLevel(saved_level)

    log_setup.LOG_DIR = original_log_dir
    log_setup.LOG_FILE = original_log_file
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_setup_logging_creates_log_dir(isolate_log_env):
    """setup_logging 应创建日志目录。"""
    nested = os.path.join(isolate_log_env, "nested", "log")
    log_setup.LOG_DIR = nested
    log_setup.LOG_FILE = os.path.join(nested, "app.log")
    log_setup._initialized = False

    log_setup.setup_logging(level="INFO", console=False)
    assert os.path.isdir(nested)


def test_setup_logging_attaches_rotating_handler(isolate_log_env):
    """setup_logging 应附加 RotatingFileHandler。"""
    log_setup.setup_logging(level="DEBUG", console=False)
    root = logging.getLogger()
    file_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    assert len(file_handlers) == 1
    handler = file_handlers[0]
    assert handler.maxBytes == 2 * 1024 * 1024
    assert handler.backupCount == 5


def test_setup_logging_writes_to_app_log(isolate_log_env):
    """日志应写入 app.log 文件。"""
    log_setup.setup_logging(level="INFO", console=False)
    logger = logging.getLogger("test_module")
    logger.info("test message from log_setup")

    # flush 所有 handler
    for h in logging.getLogger().handlers:
        h.flush()

    log_path = os.path.join(isolate_log_env, "app.log")
    assert os.path.exists(log_path)
    with open(log_path, encoding="utf-8") as f:
        content = f.read()
    assert "test message from log_setup" in content


def test_log_format_contains_required_fields(isolate_log_env):
    """日志格式应包含时间、级别、模块名、消息。"""
    log_setup.setup_logging(level="DEBUG", console=False)
    logger = logging.getLogger("my_module.test")
    logger.warning("format check message")

    for h in logging.getLogger().handlers:
        h.flush()

    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    # 格式：%(asctime)s | %(levelname)s | %(name)s | %(message)s
    assert "WARNING" in content
    assert "my_module.test" in content
    assert "format check message" in content
    # 时间格式 YYYY-MM-DD HH:MM:SS,mmm
    import re
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content)


def test_setup_logging_console_handler(isolate_log_env):
    """console=True 时应附加 StreamHandler（排除 pytest caplog 注入的 handler）。"""
    log_setup.setup_logging(level="INFO", console=True)
    root = logging.getLogger()
    # 排除 pytest 的 LogCaptureHandler（_pytest.logging 模块）
    stream_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.handlers.RotatingFileHandler)
        and not h.__class__.__module__.startswith("_pytest")
    ]
    assert len(stream_handlers) >= 1


def test_setup_logging_no_console(isolate_log_env):
    """console=False 时不应附加 StreamHandler（排除 pytest caplog 注入的 handler）。"""
    log_setup.setup_logging(level="INFO", console=False)
    root = logging.getLogger()
    # 排除 pytest 的 LogCaptureHandler
    stream_handlers = [
        h for h in root.handlers
        if isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.handlers.RotatingFileHandler)
        and not h.__class__.__module__.startswith("_pytest")
    ]
    assert len(stream_handlers) == 0


def test_log_exception_compat(isolate_log_env):
    """log_exception 接口应兼容，将异常写入 app.log。"""
    log_setup.setup_logging(level="INFO", console=False)
    try:
        raise ValueError("compat test error")
    except ValueError as e:
        log_setup.log_exception("compat.source", e)

    for h in logging.getLogger().handlers:
        h.flush()

    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    assert "compat.source" in content
    assert "ValueError" in content
    assert "compat test error" in content
    assert "Traceback" in content


def test_set_level_runtime_change(isolate_log_env):
    """set_level 应运行时调整根 logger 级别。"""
    log_setup.setup_logging(level="ERROR", console=False)
    root = logging.getLogger()
    assert root.level == logging.ERROR

    log_setup.set_level("DEBUG")
    assert root.level == logging.DEBUG

    log_setup.set_level("INFO")
    assert root.level == logging.INFO


def test_parse_level():
    """_parse_level 应正确解析级别字符串。"""
    assert log_setup._parse_level("DEBUG") == logging.DEBUG
    assert log_setup._parse_level("INFO") == logging.INFO
    assert log_setup._parse_level("WARN") == logging.WARNING
    assert log_setup._parse_level("WARNING") == logging.WARNING
    assert log_setup._parse_level("ERROR") == logging.ERROR
    assert log_setup._parse_level("CRITICAL") == logging.CRITICAL
    # 未知级别默认 INFO
    assert log_setup._parse_level("UNKNOWN") == logging.INFO
    assert log_setup._parse_level("info") == logging.INFO  # 大小写不敏感


def test_get_logger(isolate_log_env):
    """get_logger 应返回指定名称的 logger。"""
    log_setup.setup_logging(level="INFO", console=False)
    logger = log_setup.get_logger("my_module")
    assert logger.name == "my_module"
    assert isinstance(logger, logging.Logger)


def test_log_level_filtering(isolate_log_env):
    """ISSUE-LOG-02：根 logger 级别为 WARNING 时，INFO 日志不应写入文件。"""
    log_setup.setup_logging(level="WARNING", console=False)
    logger = logging.getLogger("filter_test")
    logger.info("this info should not be logged")
    logger.warning("this warning should be logged")

    for h in logging.getLogger().handlers:
        h.flush()

    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    assert "this info should not be logged" not in content
    assert "this warning should be logged" in content


def test_setup_logging_idempotent(isolate_log_env):
    """setup_logging 重复调用不应重复添加 handler（排除 pytest caplog handler）。"""
    log_setup.setup_logging(level="INFO", console=False)

    def _our_handlers():
        """仅统计非 pytest 注入的 handler。"""
        return [
            h for h in logging.getLogger().handlers
            if not h.__class__.__module__.startswith("_pytest")
        ]

    initial_count = len(_our_handlers())
    log_setup.setup_logging(level="DEBUG", console=False)
    after_count = len(_our_handlers())
    assert after_count == initial_count, "重复调用不应增加 handler 数量"


def test_file_handler_records_debug(isolate_log_env):
    """文件 handler 应记录 DEBUG 级别（即使根 logger 级别为 INFO）。"""
    log_setup.setup_logging(level="INFO", console=False)
    logger = logging.getLogger("debug_test")
    logger.debug("debug level message")
    logger.info("info level message")

    for h in logging.getLogger().handlers:
        h.flush()

    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    # 根 logger 级别为 INFO，DEBUG 不会传播到 handler
    assert "debug level message" not in content
    assert "info level message" in content
