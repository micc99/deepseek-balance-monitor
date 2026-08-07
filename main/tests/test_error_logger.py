"""error_logger 模块测试（适配 v1.10.0 统一日志系统）。

ISSUE-LOG-01：error_logger 已改为兼容模块，委托给 log_setup.log_exception，
日志统一写入 app.log（RotatingFileHandler），不再每次异常创建独立 .log 文件。

测试覆盖：
- log_exception 接口兼容性
- 日志写入统一 app.log 文件
- 日志内容包含异常类型、消息、traceback、来源
- 多次调用不再产生散落 .log 文件
- 线程安全
"""
import logging
import os
import shutil
import sys
import tempfile
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import error_logger
import log_setup


@pytest.fixture(autouse=True)
def isolate_log_env():
    """每个测试用例使用独立的临时日志目录与根 logger 状态。

    确保测试间互不干扰，且不污染项目实际的 log/ 目录。
    显式调用 setup_logging 初始化，避免依赖 log_exception 的自动初始化
    （pytest caplog 会干扰 root handler 检查）。
    """
    tmpdir = tempfile.mkdtemp()
    # 备份并替换 log_setup 与 error_logger 的 LOG_DIR / LOG_FILE
    original_log_dir = log_setup.LOG_DIR
    original_log_file = log_setup.LOG_FILE
    original_error_log_dir = error_logger.LOG_DIR

    log_setup.LOG_DIR = tmpdir
    log_setup.LOG_FILE = os.path.join(tmpdir, "app.log")
    error_logger.LOG_DIR = tmpdir

    # 重置全局初始化标志，强制下个 setup_logging 重新配置
    log_setup._initialized = False
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_filters = list(root.filters)
    saved_level = root.level
    # 清理所有 handler（含 pytest caplog 注入的）
    for h in list(root.handlers):
        root.removeHandler(h)
    for f in list(root.filters):
        root.removeFilter(f)

    # 显式初始化日志系统（console=False 避免 pytest stdout 干扰）
    log_setup.setup_logging(level="INFO", console=False)

    yield tmpdir

    # 恢复
    log_setup._initialized = False
    for h in list(root.handlers):
        root.removeHandler(h)
    for f in list(root.filters):
        root.removeFilter(f)
    root.handlers = saved_handlers
    root.filters = saved_filters
    root.setLevel(saved_level)

    log_setup.LOG_DIR = original_log_dir
    log_setup.LOG_FILE = original_log_file
    error_logger.LOG_DIR = original_error_log_dir
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_log_exception_writes_to_app_log(isolate_log_env):
    """log_exception 应将日志写入统一的 app.log 文件。"""
    error_logger.log_exception("test_source", ValueError("test error"))
    # flush 所有 handler 确保写入磁盘
    for h in logging.getLogger().handlers:
        h.flush()
    files = os.listdir(isolate_log_env)
    assert "app.log" in files
    # 不应产生独立 .log 文件
    legacy_logs = [f for f in files if f != "app.log" and f.endswith(".log")]
    assert legacy_logs == [], f"存在散落日志文件：{legacy_logs}"


def test_log_exception_no_legacy_pattern(isolate_log_env):
    """log_exception 不应产生 YYYYMMDD_HHMMSS_mmm_source.log 格式文件。"""
    import re
    legacy_pattern = re.compile(r"^\d{8}_\d{6}_\d{3}_.+\.log$")
    error_logger.log_exception("my_module.my_func", RuntimeError("boom"))
    error_logger.log_exception("another.source", OSError("io error"))
    for h in logging.getLogger().handlers:
        h.flush()
    files = os.listdir(isolate_log_env)
    legacy_files = [f for f in files if legacy_pattern.match(f)]
    assert legacy_files == [], f"存在旧格式日志文件：{legacy_files}"


def test_log_content_contains_exception_type(isolate_log_env):
    """app.log 内容应包含异常类型。"""
    error_logger.log_exception("src", TypeError("bad type"))
    for h in logging.getLogger().handlers:
        h.flush()
    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    assert "TypeError" in content


def test_log_content_contains_exception_message(isolate_log_env):
    """app.log 内容应包含异常消息。"""
    error_logger.log_exception("src", ValueError("something went wrong"))
    for h in logging.getLogger().handlers:
        h.flush()
    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    assert "something went wrong" in content


def test_log_content_contains_traceback(isolate_log_env):
    """app.log 内容应包含 traceback。"""
    try:
        raise RuntimeError("tb test")
    except RuntimeError as e:
        error_logger.log_exception("src", e)
    for h in logging.getLogger().handlers:
        h.flush()
    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    assert "Traceback" in content
    assert "RuntimeError" in content


def test_log_content_contains_source(isolate_log_env):
    """app.log 内容应包含异常来源。"""
    error_logger.log_exception("scheduler._do_check", OSError("io error"))
    for h in logging.getLogger().handlers:
        h.flush()
    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    assert "scheduler._do_check" in content


def test_log_exception_creates_log_directory(isolate_log_env):
    """log_exception 应确保日志目录存在（通过 fixture 已初始化，验证 nested 目录场景）。"""
    tmpdir = tempfile.mkdtemp()
    nested = os.path.join(tmpdir, "sub", "log")
    log_setup.LOG_DIR = nested
    log_setup.LOG_FILE = os.path.join(nested, "app.log")
    error_logger.LOG_DIR = nested
    log_setup._initialized = False
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    for h in list(root.handlers):
        root.removeHandler(h)
    try:
        # 显式初始化（避免依赖 log_exception 自动初始化受 pytest caplog 干扰）
        log_setup.setup_logging(level="INFO", console=False)
        error_logger.log_exception("src", Exception("test"))
        # flush 确保写入
        for h in logging.getLogger().handlers:
            h.flush()
        assert os.path.isdir(nested)
        assert os.path.exists(os.path.join(nested, "app.log"))
        # 不应有散落文件
        assert os.listdir(nested) == ["app.log"]
    finally:
        log_setup._initialized = False
        for h in list(root.handlers):
            root.removeHandler(h)
        root.handlers = saved_handlers
        log_setup.LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "log")
        log_setup.LOG_FILE = os.path.join(log_setup.LOG_DIR, "app.log")
        error_logger.LOG_DIR = log_setup.LOG_DIR
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_log_exception_thread_safety(isolate_log_env):
    """多线程并发调用 log_exception 应线程安全，所有异常都写入 app.log。"""
    errors = []

    def worker(i):
        try:
            raise ValueError(f"thread-{i}")
        except ValueError as e:
            error_logger.log_exception(f"thread_{i}", e)
            errors.append(i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 所有线程都完成
    assert len(errors) == 10
    # flush 确保所有日志写入磁盘
    for h in logging.getLogger().handlers:
        h.flush()
    # 所有日志写入同一个 app.log
    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    for i in range(10):
        assert f"thread-{i}" in content


def test_multiple_exceptions_single_file(isolate_log_env):
    """多次调用 log_exception 应追加到同一个 app.log，不创建新文件。"""
    error_logger.log_exception("src1", Exception("error 1"))
    error_logger.log_exception("src2", Exception("error 2"))
    error_logger.log_exception("src3", Exception("error 3"))
    for h in logging.getLogger().handlers:
        h.flush()

    files = os.listdir(isolate_log_env)
    # 只应有 app.log 一个文件
    log_files = [f for f in files if f.endswith(".log")]
    assert log_files == ["app.log"]

    with open(os.path.join(isolate_log_env, "app.log"), encoding="utf-8") as f:
        content = f.read()
    assert "error 1" in content
    assert "error 2" in content
    assert "error 3" in content
