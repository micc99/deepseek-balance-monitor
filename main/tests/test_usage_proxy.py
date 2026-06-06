import json
import os
import sys
import pytest
import responses

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestUsageProxyConfig:
    def test_default_host_port(self):
        from usage_proxy import PROXY_HOST, PROXY_PORT
        assert PROXY_HOST == "127.0.0.1"
        assert PROXY_PORT == 52848

    def test_target_host(self):
        from usage_proxy import TARGET_HOST
        assert TARGET_HOST == "api.deepseek.com"

    def test_usage_proxy_create(self):
        from usage_proxy import UsageProxy
        proxy = UsageProxy()
        assert proxy._host == "127.0.0.1"
        assert proxy._port == 52848

    def test_proxy_url(self):
        from usage_proxy import UsageProxy
        proxy = UsageProxy(host="127.0.0.1", port=52848)
        assert proxy.proxy_url == "http://127.0.0.1:52848/v1"


class TestOptionHandler:
    def test_options_response(self):
        import io
        from usage_proxy import _Handler

        class MockReq:
            def __init__(self):
                self.headers = {}
                self.path = "/v1/chat/completions"
            def makefile(self, mode, bufsize=0):
                return io.BytesIO()
            def settimeout(self, timeout):
                pass

        handler = _Handler(MockReq(), ("127.0.0.1", 12345), None)
        handler.send_response = lambda code: None
        handler.send_header = lambda k, v: None
        handler.end_headers = lambda: None

        handler.do_OPTIONS()


class TestLogUsageIntegration:
    def test_log_usage_with_valid_dict(self):
        import usage_logger
        import tempfile
        import sqlite3

        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "usage.db")
        usage_logger._USAGE_DB_DIR = tmpdir
        usage_logger._USAGE_DB_PATH = db_path
        usage_logger._ensure_db_path()

        usage_logger.log_usage("sk-test-key", {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "total_tokens": 700,
        })

        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT * FROM token_usage").fetchall()
        assert len(rows) == 1
        assert rows[0][3] == 500

        usage_logger._USAGE_DB_DIR = os.path.join(os.path.expandvars("%APPDATA%"), "DeepSeekBalanceMonitor")
        usage_logger._USAGE_DB_PATH = os.path.join(usage_logger._USAGE_DB_DIR, "usage.db")
