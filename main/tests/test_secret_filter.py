"""secret_filter 模块单元测试（ISSUE-SEC-07）。

ISSUE-SEC-07：日志脱敏
- 正则匹配常见 Key 格式：sk-xxx、Bearer token
- 命中后替换为 sk-***（保留前缀）
- 白名单字段不脱敏：api_key_hash、masked_key
- 异常 traceback 中的 Key 被脱敏

测试覆盖：
- sk-xxx 格式脱敏
- Bearer token 脱敏
- 短字符串不误脱敏
- 白名单字段保留
- traceback 脱敏
- install_secret_redaction 安装与去重
- redact_text 便捷函数
"""
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from secret_filter import (
    SecretRedactingFilter,
    install_secret_redaction,
    redact_text,
)


class TestSecretRedactingFilter:
    """SecretRedactingFilter 单元测试。"""

    def setup_method(self):
        self.f = SecretRedactingFilter()

    def test_redact_sk_key(self):
        """sk- 开头的 API Key 应被脱敏为 sk-***。"""
        text = "Authorization: sk-abcdef1234567890abcdef1234567890"
        result = self.f._redact(text)
        assert "sk-abcdef1234567890" not in result
        assert "sk-***" in result

    def test_redact_bearer_token(self):
        """Bearer token 应被脱敏为 Bearer ***。"""
        text = "Authorization: Bearer abcdef1234567890abcdef1234567890"
        result = self.f._redact(text)
        assert "Bearer abcdef" not in result
        assert "Bearer ***" in result

    def test_redact_bearer_case_insensitive(self):
        """Bearer 大小写不敏感。"""
        text = "auth: bearer abcdef1234567890abcdef1234567890"
        result = self.f._redact(text)
        assert "bearer abcdef" not in result
        assert "Bearer ***" in result or "bearer ***" in result

    def test_short_string_not_redacted(self):
        """短于 20 位的字符串不应被脱敏。"""
        text = "my key is sk-short"
        result = self.f._redact(text)
        assert result == text

    def test_empty_text(self):
        """空字符串不应被脱敏。"""
        assert self.f._redact("") == ""

    def test_multiple_keys_in_text(self):
        """同一段文本中多个 Key 都应被脱敏。"""
        text = "key1=sk-aaa1234567890abcdef1234567890 key2=sk-bbb1234567890abcdef1234567890"
        result = self.f._redact(text)
        assert "sk-aaa1234567890" not in result
        assert "sk-bbb1234567890" not in result
        assert result.count("sk-***") == 2

    def test_no_key_in_text(self):
        """无 Key 的文本不应被修改。"""
        text = "this is a normal log message without any keys"
        result = self.f._redact(text)
        assert result == text

    def test_hash_field_not_redacted(self):
        """api_key_hash 字段值（hex 字符串）不应被误脱敏。"""
        # hex 字符串不含 sk- 前缀，不会被 sk- 模式匹配
        text = "api_key_hash=abcdef0123456789abcdef0123456789"
        result = self.f._redact(text)
        assert result == text

    def test_masked_key_field_not_redacted(self):
        """masked_key 字段（sk-*** 形式）不应被脱敏。"""
        text = "masked_key=sk-***"
        result = self.f._redact(text)
        # sk-*** 不匹配 sk-[A-Za-z0-9]{20,}，不会被替换
        assert result == text


class TestFilterIntegration:
    """过滤器与 logging 系统集成测试。"""

    def test_filter_attached_to_logger(self):
        """filter 方法应返回 True，允许日志通过。"""
        f = SecretRedactingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="key=sk-abcdef1234567890abcdef1234567890",
            args=None,
            exc_info=None,
        )
        assert f.filter(record) is True
        assert "sk-abcdef" not in record.msg
        assert "sk-***" in record.msg

    def test_filter_redacts_args(self):
        """filter 应脱敏 args 中的字符串。"""
        f = SecretRedactingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="key=%s",
            args=("sk-abcdef1234567890abcdef1234567890",),
            exc_info=None,
        )
        f.filter(record)
        assert "sk-abcdef1234567890" not in record.args[0]
        assert "sk-***" in record.args[0]

    def test_filter_redacts_dict_args(self):
        """filter 应脱敏 dict 类型 args 中的字符串值。"""
        f = SecretRedactingFilter()
        # LogRecord 的 args 期望 tuple；单元素 dict 需包装为 tuple
        # 当 args 为 (dict,) 时，LogRecord 会自动解包为 dict
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="%(key)s",
            args=({"key": "sk-abcdef1234567890abcdef1234567890"},),
            exc_info=None,
        )
        # LogRecord 会将 (dict,) 解包为 dict
        assert isinstance(record.args, dict)
        f.filter(record)
        assert "sk-abcdef1234567890" not in record.args["key"]
        assert "sk-***" in record.args["key"]

    def test_filter_redacts_exc_text(self):
        """filter 应脱敏 exc_text（traceback 文本）。"""
        f = SecretRedactingFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error occurred",
            args=None,
            exc_info=None,
        )
        record.exc_text = "Traceback: sk-abcdef1234567890abcdef1234567890"
        f.filter(record)
        assert "sk-abcdef1234567890" not in record.exc_text

    def test_end_to_end_child_logger_redaction(self, tmp_path):
        """端到端验证：子 logger 记录的明文 Key 应在日志文件中被脱敏。

        此测试覆盖 ISSUE-SEC-07 的核心场景：secret_filter 安装在 root logger
        的 handler 上后，子 logger（如 'scheduler'、'balance_checker'）记录的
        含 Key 消息在写入文件前应被脱敏。
        """
        import io
        root = logging.getLogger()
        # 清理现有 handler/filter，搭建干净环境
        saved_handlers = list(root.handlers)
        saved_filters = list(root.filters)
        saved_level = root.level
        for h in list(root.handlers):
            root.removeHandler(h)
        for f in list(root.filters):
            root.removeFilter(f)

        try:
            stream = io.StringIO()
            handler = logging.StreamHandler(stream)
            handler.setLevel(logging.DEBUG)
            root.addHandler(handler)
            root.setLevel(logging.DEBUG)

            # 安装脱敏过滤器（应挂在 handler 上）
            install_secret_redaction(root)

            # 通过子 logger 记录含 Key 的消息
            child = logging.getLogger("integration.child")
            child.info("API Key: sk-abcdefghijklmnop1234567890abcdefghijklmnop")
            child.info("Bearer xyz1234567890abcdef1234567890")

            handler.flush()
            output = stream.getvalue()

            # 明文 Key 不应出现在输出中
            assert "sk-abcdefghijklmnop" not in output, "子 logger 的明文 sk-key 未被脱敏"
            assert "Bearer xyz1234567890" not in output, "子 logger 的 Bearer token 未被脱敏"
            # 脱敏占位符应出现
            assert "sk-***" in output
            assert "Bearer ***" in output
        finally:
            for h in list(root.handlers):
                root.removeHandler(h)
            root.handlers = saved_handlers
            root.filters = saved_filters
            root.setLevel(saved_level)


class TestInstallSecretRedaction:
    """install_secret_redaction 函数测试。"""

    def test_install_on_root_logger(self):
        """install_secret_redaction 应在根 logger 上安装过滤器。"""
        root = logging.getLogger()
        # 清理已有过滤器
        original_filters = list(root.filters)
        for f in list(root.filters):
            if isinstance(f, SecretRedactingFilter):
                root.removeFilter(f)
        try:
            install_secret_redaction(root)
            assert any(isinstance(f, SecretRedactingFilter) for f in root.filters)
        finally:
            for f in list(root.filters):
                if isinstance(f, SecretRedactingFilter):
                    root.removeFilter(f)
            root.filters = original_filters

    def test_install_default_to_root(self):
        """不传 logger 时应安装到根 logger。"""
        root = logging.getLogger()
        original_filters = list(root.filters)
        for f in list(root.filters):
            if isinstance(f, SecretRedactingFilter):
                root.removeFilter(f)
        try:
            install_secret_redaction()
            assert any(isinstance(f, SecretRedactingFilter) for f in root.filters)
        finally:
            for f in list(root.filters):
                if isinstance(f, SecretRedactingFilter):
                    root.removeFilter(f)
            root.filters = original_filters

    def test_install_idempotent(self):
        """重复安装不应在 logger 或 handler 上添加多个过滤器。"""
        root = logging.getLogger()
        original_logger_filters = list(root.filters)
        original_handler_filters = {h: list(h.filters) for h in root.handlers}
        # 清理 root 与各 handler 上已有的 SecretRedactingFilter
        for f in list(root.filters):
            if isinstance(f, SecretRedactingFilter):
                root.removeFilter(f)
        for h in root.handlers:
            for f in list(h.filters):
                if isinstance(f, SecretRedactingFilter):
                    h.removeFilter(f)
        try:
            install_secret_redaction(root)
            install_secret_redaction(root)
            # logger 上至多 1 个
            logger_count = sum(1 for f in root.filters if isinstance(f, SecretRedactingFilter))
            assert logger_count == 1, f"logger 上应有 1 个过滤器，实际 {logger_count}"
            # 每个 handler 上至多 1 个
            for h in root.handlers:
                handler_count = sum(1 for f in h.filters if isinstance(f, SecretRedactingFilter))
                assert handler_count == 1, f"handler {h} 上应有 1 个过滤器，实际 {handler_count}"
        finally:
            for f in list(root.filters):
                if isinstance(f, SecretRedactingFilter):
                    root.removeFilter(f)
            for h in root.handlers:
                for f in list(h.filters):
                    if isinstance(f, SecretRedactingFilter):
                        h.removeFilter(f)
            root.filters = original_logger_filters
            for h in root.handlers:
                h.filters = original_handler_filters.get(h, list(h.filters))


class TestRedactText:
    """redact_text 便捷函数测试。"""

    def test_redact_text_sk_key(self):
        result = redact_text("key=sk-abcdef1234567890abcdef1234567890")
        assert "sk-***" in result
        assert "sk-abcdef1234567890" not in result

    def test_redact_text_bearer(self):
        result = redact_text("Bearer abcdef1234567890abcdef1234567890")
        assert "Bearer ***" in result

    def test_redact_text_no_key(self):
        result = redact_text("normal text")
        assert result == "normal text"
