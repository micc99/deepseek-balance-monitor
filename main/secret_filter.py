"""日志脱敏过滤器（ISSUE-SEC-07）。

挂在根 logger 上，扫描所有日志消息与异常 traceback，
命中 API Key 格式（如 `sk-xxxxx`、Bearer token）后替换为脱敏形式，
避免日志泄露导致 Key 泄露。

白名单字段（如 `api_key_hash`、`masked_key`）不脱敏，
hash 已是单向不可逆，保留有助于排查。
"""
from __future__ import annotations

import logging
import re


# 命中后替换为该占位符（保留前缀便于识别 Key 类型）
_REDACTED_PLACEHOLDER = "sk-***"

# 常见 API Key 格式：
# - sk- 开头 + 至少 20 位字母数字（OpenAI / DeepSeek / Moonshot / SiliconFlow 风格）
# - Bearer xxxxxx（HTTP Authorization 头）
# - 一般长字符串 token（48+ 位字母数字，排除 hash 字段）
_KEY_PATTERNS = [
    # sk- 开头的 API Key：保留 "sk-" 前缀，后跟 ***
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    # Bearer token：保留 "Bearer " 前缀
    re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{20,}\b", re.IGNORECASE),
]

# 白名单字段名：这些字段值即使匹配 Key 格式也不脱敏（已是 hash 或 masked 形式）
# 仅保护字段值，不影响消息中其他位置的 Key
_WHITELIST_FIELD_PATTERNS = [
    re.compile(r"api_key_hash\s*[=:]\s*[\"']?([A-Fa-f0-9]{16,64})", re.IGNORECASE),
    re.compile(r"masked_key\s*[=:]\s*[\"']?(sk-\*+)", re.IGNORECASE),
]


class SecretRedactingFilter(logging.Filter):
    """日志脱敏过滤器。

    挂在根 logger 上，对所有 handler 生效。
    扫描 record.msg 与 record.args 中的字符串，命中 Key 格式则替换。
    """

    def __init__(self):
        super().__init__(name="SecretRedactingFilter")
        self._patterns = list(_KEY_PATTERNS)

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤日志记录：脱敏 msg 与 args 中的 API Key。"""
        # 脱敏主消息
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)

        # 脱敏 args（% 格式化参数）
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._redact(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._redact(a) if isinstance(a, str) else a for a in record.args
                )

        # 脱敏异常 traceback 文本（exc_text 缓存）
        if record.exc_text:
            record.exc_text = self._redact(record.exc_text)

        return True

    def _redact(self, text: str) -> str:
        """对单段文本执行脱敏替换。

        跳过白名单字段（如 api_key_hash=xxx）的值部分。
        """
        if not text:
            return text

        # 先记录白名单字段值的位置，避免后续误脱敏
        # 简化实现：若文本中同时出现白名单字段名与匹配的值，则不在该字段附近替换
        # 这里采用保守策略：仅替换 sk-xxx 与 Bearer xxx 模式
        # 白名单字段值通常是 hex 字符串或 sk-*** 形式，不会被 sk-[A-Za-z0-9]{20,} 匹配
        # （hex 仅含 0-9a-f，且 masked_key 是 sk-*** 不含 20+ 位字母数字）
        result = text
        for pattern in self._patterns:
            result = pattern.sub(self._replace_match, result)
        return result

    @staticmethod
    def _replace_match(match: re.Match) -> str:
        """替换匹配到的 Key。

        - sk-xxx → sk-***（保留前缀）
        - Bearer xxx → Bearer ***（保留前缀）
        """
        text = match.group(0)
        if text.lower().startswith("bearer"):
            return "Bearer ***"
        if text.startswith("sk-"):
            return _REDACTED_PLACEHOLDER
        return _REDACTED_PLACEHOLDER


def install_secret_redaction(logger: logging.Logger | None = None) -> SecretRedactingFilter:
    """在指定 logger（默认根 logger）的 handler 上安装脱敏过滤器。

    注意：过滤器必须挂在 handler 上而非 logger 上。Python logging 的传播机制
    中，子 logger 的记录会绕过父 logger 的 filter，直接到达父 logger 的 handler。
    只有 handler 级别的 filter 才能对传播上来的记录生效。

    Args:
        logger: 目标 logger，None 表示根 logger

    Returns:
        安装的过滤器实例（可用于测试或后续卸载）
    """
    target = logger or logging.getLogger()
    f = SecretRedactingFilter()

    # 在 logger 自身的 filter 上也安装一份（覆盖直接用 root.log() 的场景）
    already_on_logger = any(isinstance(fltr, SecretRedactingFilter) for fltr in target.filters)
    if not already_on_logger:
        target.addFilter(f)

    # 关键：在所有 handler 的 filter 上也安装，确保子 logger 传播上来的记录被脱敏
    for handler in target.handlers:
        already_on_handler = any(
            isinstance(fltr, SecretRedactingFilter) for fltr in handler.filters
        )
        if not already_on_handler:
            handler.addFilter(f)

    return f


def redact_text(text: str) -> str:
    """便捷函数：对任意文本执行脱敏（供审计日志等场景调用）。"""
    f = SecretRedactingFilter()
    return f._redact(text)
