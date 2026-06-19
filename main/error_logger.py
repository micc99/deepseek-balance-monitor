import os
import threading
import time
import traceback
from datetime import datetime


"""异常日志记录模块。

每次调用 log_exception() 在 LOG_DIR 下创建独立的 .log 文件，
文件名为时间戳 + 来源模块，内容包含完整 traceback。
线程安全，自动创建目录。
"""

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log")
_lock = threading.Lock()


def log_exception(source: str, exc: Exception):
    """记录异常到独立的 log 文件。

    Args:
        source: 异常来源描述（如模块名.方法名）
        exc: 捕获到的异常对象
    """
    now = datetime.now()
    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{now.microsecond // 1000:03d}_{source}.log"
    filepath = os.path.join(LOG_DIR, filename)

    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    content = (
        f"{'=' * 40}\n"
        f"时间: {now.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
        f"来源: {source}\n"
        f"异常类型: {type(exc).__name__}\n"
        f"异常消息: {exc}\n"
        f"{'=' * 40}\n"
        f"{tb}"
    )

    with _lock:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
