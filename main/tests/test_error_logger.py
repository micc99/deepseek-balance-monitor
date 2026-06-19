import os
import re
import sys
import tempfile
import threading
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import error_logger


@pytest.fixture(autouse=True)
def isolate_log_dir():
    tmpdir = tempfile.mkdtemp()
    original_dir = error_logger.LOG_DIR
    error_logger.LOG_DIR = tmpdir
    yield tmpdir
    error_logger.LOG_DIR = original_dir
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_log_exception_creates_file(isolate_log_dir):
    error_logger.log_exception("test_source", ValueError("test error"))
    files = os.listdir(isolate_log_dir)
    assert len(files) == 1
    assert files[0].endswith(".log")


def test_log_file_name_contains_timestamp(isolate_log_dir):
    error_logger.log_exception("my_module.my_func", RuntimeError("boom"))
    files = os.listdir(isolate_log_dir)
    pattern = r"^\d{8}_\d{6}_\d{3}_my_module\.my_func\.log$"
    assert re.match(pattern, files[0])


def test_log_file_contains_exception_type(isolate_log_dir):
    error_logger.log_exception("src", TypeError("bad type"))
    files = os.listdir(isolate_log_dir)
    with open(os.path.join(isolate_log_dir, files[0]), encoding="utf-8") as f:
        content = f.read()
    assert "异常类型: TypeError" in content


def test_log_file_contains_exception_message(isolate_log_dir):
    error_logger.log_exception("src", ValueError("something went wrong"))
    files = os.listdir(isolate_log_dir)
    with open(os.path.join(isolate_log_dir, files[0]), encoding="utf-8") as f:
        content = f.read()
    assert "异常消息: something went wrong" in content


def test_log_file_contains_traceback(isolate_log_dir):
    try:
        raise RuntimeError("tb test")
    except RuntimeError as e:
        error_logger.log_exception("src", e)
    files = os.listdir(isolate_log_dir)
    with open(os.path.join(isolate_log_dir, files[0]), encoding="utf-8") as f:
        content = f.read()
    assert "Traceback" in content
    assert "RuntimeError" in content


def test_log_file_contains_source(isolate_log_dir):
    error_logger.log_exception("scheduler._do_check", OSError("io error"))
    files = os.listdir(isolate_log_dir)
    with open(os.path.join(isolate_log_dir, files[0]), encoding="utf-8") as f:
        content = f.read()
    assert "来源: scheduler._do_check" in content


def test_log_exception_creates_directory():
    tmpdir = tempfile.mkdtemp()
    nested = os.path.join(tmpdir, "sub", "log")
    error_logger.LOG_DIR = nested
    try:
        error_logger.log_exception("src", Exception("test"))
        assert os.path.isdir(nested)
        assert len(os.listdir(nested)) == 1
    finally:
        error_logger.LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "log")
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_log_exception_thread_safety(isolate_log_dir):
    errors = []

    def worker(i):
        try:
            raise ValueError(f"thread-{i}")
        except ValueError as e:
            error_logger.log_exception(f"thread_{i}", e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    files = os.listdir(isolate_log_dir)
    assert len(files) == 10
    names = set(files)
    assert len(names) == 10


def test_log_exception_different_errors_different_files(isolate_log_dir):
    error_logger.log_exception("src1", Exception("error 1"))
    time.sleep(0.01)
    error_logger.log_exception("src2", Exception("error 2"))
    time.sleep(0.01)
    error_logger.log_exception("src3", Exception("error 3"))

    files = os.listdir(isolate_log_dir)
    assert len(files) == 3
    assert len(set(files)) == 3
