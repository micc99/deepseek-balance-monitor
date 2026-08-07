"""ISSUE-SEC-04：usage_proxy 鉴权与目标白名单单元测试。

测试覆盖：
- X-Proxy-Token 鉴权（hmac.compare_digest 恒定时间比较）
- target_host 白名单校验
- 审计日志（key hash + 路径 + 状态码，不含请求/响应体）
- token 生成与重置
- 白名单动态扩展（add_to_whitelist）
- DEFAULT_WHITELIST 默认覆盖 5 个 Provider 域名
"""
import hashlib
import hmac
import os
import sys
import threading
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usage_proxy import (
    UsageProxy,
    DEFAULT_WHITELIST,
    _hash_token,
    _hash_api_key,
    PROXY_HOST,
    PROXY_PORT,
    TARGET_HOST,
)
from credential_store import PlainCredentialStore, set_credential_store_for_test


@pytest.fixture(autouse=True)
def use_plain_credential_store():
    """使用 PlainCredentialStore 避免 DPAPI 依赖。"""
    set_credential_store_for_test(PlainCredentialStore())
    yield
    set_credential_store_for_test(None)


class TestDefaultWhitelist:
    """默认白名单应覆盖 5 个内置 Provider 域名。"""

    def test_default_whitelist_contains_providers(self):
        """DEFAULT_WHITELIST 应包含 5 个 Provider 域名。"""
        assert "api.deepseek.com" in DEFAULT_WHITELIST
        assert "api.siliconflow.cn" in DEFAULT_WHITELIST
        assert "api.moonshot.cn" in DEFAULT_WHITELIST
        assert "openrouter.ai" in DEFAULT_WHITELIST
        assert "open.bigmodel.cn" in DEFAULT_WHITELIST

    def test_default_whitelist_size(self):
        """默认白名单应至少有 5 个域名。"""
        assert len(DEFAULT_WHITELIST) >= 5


class TestHashFunctions:
    """_hash_token 与 _hash_api_key 测试。"""

    def test_hash_token_returns_16_hex(self):
        """_hash_token 应返回 16 位 hex 字符串。"""
        h = _hash_token("some-token-value")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_api_key_returns_16_hex(self):
        """_hash_api_key 应返回 16 位 hex 字符串。"""
        h = _hash_api_key("sk-test-key")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_deterministic(self):
        """相同输入应产生相同 hash。"""
        assert _hash_token("abc") == _hash_token("abc")
        assert _hash_api_key("sk-x") == _hash_api_key("sk-x")

    def test_hash_different_for_different_input(self):
        """不同输入应产生不同 hash。"""
        assert _hash_token("abc") != _hash_token("def")
        assert _hash_api_key("sk-x") != _hash_api_key("sk-y")


class TestUsageProxyToken:
    """UsageProxy 鉴权 token 管理测试。"""

    def test_init_generates_token_when_empty(self):
        """首次启动（proxy_token_enc 为空）应自动生成 token。"""
        proxy = UsageProxy(proxy_token_enc="")
        assert proxy.get_proxy_token(), "应生成非空 token"
        assert proxy.token_enc_changed is True, "应标记 token_enc_changed"
        assert proxy.proxy_token_enc, "应生成加密后的 token"

    def test_init_loads_token_from_config(self):
        """proxy_token_enc 已存在时应解密加载。"""
        # 先生成一个 token
        proxy1 = UsageProxy(proxy_token_enc="")
        enc = proxy1.proxy_token_enc
        token = proxy1.get_proxy_token()

        # 用同一个 enc 创建新 proxy，应解密出相同 token
        proxy2 = UsageProxy(proxy_token_enc=enc)
        assert proxy2.get_proxy_token() == token
        assert proxy2.token_enc_changed is False

    def test_reset_proxy_token(self):
        """reset_proxy_token 应生成新 token。"""
        proxy = UsageProxy(proxy_token_enc="")
        old_token = proxy.get_proxy_token()

        new_token = proxy.reset_proxy_token()
        assert new_token != old_token
        assert proxy.get_proxy_token() == new_token
        assert proxy.token_enc_changed is True

    def test_token_is_32_bytes(self):
        """生成的 token 应为 32 字节（secrets.token_urlsafe(32)）。"""
        proxy = UsageProxy(proxy_token_enc="")
        token = proxy.get_proxy_token()
        # token_urlsafe(32) 返回 43 字符的 base64url 编码
        assert len(token) >= 32


class TestUsageProxyWhitelist:
    """UsageProxy 白名单管理测试。"""

    def test_default_whitelist_loaded(self):
        """新建 proxy 应加载默认白名单。"""
        proxy = UsageProxy()
        whitelist = proxy.get_whitelist()
        assert "api.deepseek.com" in whitelist
        assert "api.siliconflow.cn" in whitelist

    def test_add_to_whitelist(self):
        """add_to_whitelist 应动态添加域名。"""
        proxy = UsageProxy()
        proxy.add_to_whitelist("custom.api.example.com")
        assert "custom.api.example.com" in proxy.get_whitelist()

    def test_whitelist_returns_copy(self):
        """get_whitelist 应返回副本，修改不影响内部状态。"""
        proxy = UsageProxy()
        wl = proxy.get_whitelist()
        wl.add("malicious.host")
        assert "malicious.host" not in proxy.get_whitelist()

    def test_whitelist_thread_safe(self):
        """并发添加域名应线程安全。"""
        proxy = UsageProxy()
        threads = []
        for i in range(10):
            t = threading.Thread(
                target=proxy.add_to_whitelist,
                args=(f"host{i}.example.com",),
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        wl = proxy.get_whitelist()
        for i in range(10):
            assert f"host{i}.example.com" in wl


class TestHandlerAuth:
    """_Handler 鉴权逻辑测试（通过 mock 请求头）。"""

    def _make_handler_with_token(self, token: str):
        """构造一个绑定了 token 的 _Handler mock 实例。"""
        proxy = UsageProxy(proxy_token_enc="")
        # 强制设置 token
        proxy._token_cache = token

        from usage_proxy import _Handler
        handler = _Handler.__new__(_Handler)
        handler.proxy_ref = proxy
        handler.headers = {}
        handler.path = "/v1/chat/completions"
        return handler, proxy

    def test_check_auth_no_token_configured(self):
        """未配置 token 时应放行（兼容旧版）。"""
        from usage_proxy import _Handler
        handler = _Handler.__new__(_Handler)
        handler.proxy_ref = None  # 无 proxy_ref
        assert handler._check_auth() is True

    def test_check_auth_missing_header(self):
        """缺少 X-Proxy-Token 头应鉴权失败。"""
        handler, proxy = self._make_handler_with_token("expected-token")
        handler.headers = {}
        assert handler._check_auth() is False

    def test_check_auth_wrong_token(self):
        """错误的 token 应鉴权失败。"""
        handler, proxy = self._make_handler_with_token("expected-token")
        handler.headers = {"X-Proxy-Token": "wrong-token"}
        assert handler._check_auth() is False

    def test_check_auth_correct_token(self):
        """正确的 token 应鉴权通过。"""
        handler, proxy = self._make_handler_with_token("expected-token")
        handler.headers = {"X-Proxy-Token": "expected-token"}
        assert handler._check_auth() is True

    def test_check_auth_constant_time_compare(self):
        """应使用 hmac.compare_digest 恒定时间比较（防时序攻击）。"""
        handler, proxy = self._make_handler_with_token("expected-token")
        handler.headers = {"X-Proxy-Token": "expected-token"}
        with patch("usage_proxy.hmac.compare_digest", wraps=hmac.compare_digest) as mock_cmp:
            result = handler._check_auth()
            mock_cmp.assert_called_once_with("expected-token", "expected-token")
            assert result is True

    def test_check_auth_empty_token_configured(self):
        """配置的 token 为空时应放行。"""
        from usage_proxy import _Handler
        proxy = UsageProxy()
        proxy._token_cache = ""  # 空 token
        handler = _Handler.__new__(_Handler)
        handler.proxy_ref = proxy
        handler.headers = {}
        assert handler._check_auth() is True


class TestHandlerWhitelist:
    """_Handler 白名单校验逻辑测试。"""

    def _make_handler(self, whitelist: set):
        from usage_proxy import _Handler
        proxy = UsageProxy()
        proxy._whitelist = set(whitelist)
        handler = _Handler.__new__(_Handler)
        handler.proxy_ref = proxy
        return handler

    def test_check_whitelist_no_proxy_ref(self):
        """无 proxy_ref 时应放行（单元测试场景）。"""
        from usage_proxy import _Handler
        handler = _Handler.__new__(_Handler)
        handler.proxy_ref = None
        assert handler._check_whitelist("any.host.com") is True

    def test_check_whitelist_in_whitelist(self):
        """target_host 在白名单中应通过。"""
        handler = self._make_handler({"api.deepseek.com"})
        assert handler._check_whitelist("api.deepseek.com") is True

    def test_check_whitelist_not_in_whitelist(self):
        """target_host 不在白名单中应拒绝。"""
        handler = self._make_handler({"api.deepseek.com"})
        assert handler._check_whitelist("malicious.host.com") is False

    def test_check_whitelist_empty_whitelist(self):
        """空白名单应放行（兼容）。"""
        handler = self._make_handler(set())
        assert handler._check_whitelist("any.host.com") is True


class TestAuditLog:
    """审计日志测试（ISSUE-SEC-04 AC3）。"""

    def _make_handler(self, api_key: str, path: str):
        from usage_proxy import _Handler
        handler = _Handler.__new__(_Handler)
        handler.proxy_ref = None
        handler.path = path
        handler.headers = {}
        return handler

    def test_audit_log_records_key_hash(self, caplog):
        """审计日志应记录 key hash，不记录明文 key。"""
        import logging
        handler = self._make_handler("sk-secret-key-12345", "/v1/chat/completions")
        with caplog.at_level(logging.INFO, logger="usage_proxy"):
            handler._audit_log("sk-secret-key-12345", 200, "ok")
        # 日志中不应出现明文 key
        for record in caplog.records:
            assert "sk-secret-key-12345" not in record.getMessage()
            # 应出现 key hash
            if "proxy_audit" in record.getMessage():
                assert _hash_api_key("sk-secret-key-12345") in record.getMessage()

    def test_audit_log_records_path_and_status(self, caplog):
        """审计日志应记录请求路径与状态码。"""
        import logging
        handler = self._make_handler("sk-test", "/v1/completions")
        with caplog.at_level(logging.INFO, logger="usage_proxy"):
            handler._audit_log("sk-test", 403, "auth_failed")
        found = False
        for record in caplog.records:
            msg = record.getMessage()
            if "proxy_audit" in msg:
                assert "/v1/completions" in msg
                assert "403" in msg
                assert "auth_failed" in msg
                found = True
        assert found, "应记录审计日志"

    def test_audit_log_anonymous_for_empty_key(self, caplog):
        """无 API Key 时审计日志应记录 anonymous。"""
        import logging
        handler = self._make_handler("", "/v1/chat/completions")
        with caplog.at_level(logging.INFO, logger="usage_proxy"):
            handler._audit_log("", 200, "ok")
        found = False
        for record in caplog.records:
            msg = record.getMessage()
            if "proxy_audit" in msg:
                assert "anonymous" in msg
                found = True
        assert found

    def test_audit_log_no_request_body(self, caplog):
        """审计日志不应包含请求体内容。"""
        import logging
        handler = self._make_handler("sk-test", "/v1/chat/completions")
        with caplog.at_level(logging.INFO, logger="usage_proxy"):
            handler._audit_log("sk-test", 200, "ok")
        for record in caplog.records:
            msg = record.getMessage()
            # 不应出现 body / prompt / completion 等关键字段
            assert "prompt_tokens" not in msg
            assert "completion_tokens" not in msg
            assert "messages" not in msg


class TestUsageProxyConfig:
    """UsageProxy 基础配置测试。"""

    def test_default_host_port(self):
        assert PROXY_HOST == "127.0.0.1"
        assert PROXY_PORT == 52848

    def test_default_target_host(self):
        assert TARGET_HOST == "api.deepseek.com"

    def test_usage_proxy_create(self):
        proxy = UsageProxy()
        assert proxy._host == "127.0.0.1"
        assert proxy._port == 52848

    def test_proxy_url(self):
        proxy = UsageProxy(host="127.0.0.1", port=52848)
        assert proxy.proxy_url == "http://127.0.0.1:52848/v1"

    def test_custom_target_host(self):
        """应支持自定义 target_host。"""
        proxy = UsageProxy(target_host="api.siliconflow.cn")
        assert proxy._target_host == "api.siliconflow.cn"
