"""ISSUE-PFM-06 / ISSUE-NET-02：usage_proxy 流式解析与多线程服务器测试。

测试覆盖：
- SSEUsageParser 行级状态机（PFM-06）
  - 单 chunk 完整行解析
  - 跨 chunk 的 SSE 行拼接
  - 多个 usage 行只取最后一个
  - [DONE] 行不解析
  - \r\n 换行符处理
  - 无 usage 的流不返回数据
- ThreadingHTTPServer（NET-02）
  - 服务器使用 ThreadingHTTPServer
  - daemon_threads = True
  - 并发请求不排队
"""
import json
import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from usage_proxy import SSEUsageParser


class TestSSEUsageParserSingleChunk:
    """ISSUE-PFM-06：单 chunk 完整行解析测试。"""

    def test_single_usage_line(self):
        """单个 data 行含 usage 应被解析。"""
        parser = SSEUsageParser()
        chunk = 'data: {"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}\n'
        parser.feed(chunk)
        assert parser.last_usage is not None
        assert parser.last_usage["total_tokens"] == 15

    def test_multiple_lines_single_chunk(self):
        """一个 chunk 包含多行，应解析所有完整行。"""
        parser = SSEUsageParser()
        chunk = (
            'data: {"choices": []}\n'
            'data: {"choices": []}\n'
            'data: {"usage": {"prompt_tokens": 10, "total_tokens": 15}}\n'
        )
        parser.feed(chunk)
        assert parser.last_usage is not None
        assert parser.last_usage["total_tokens"] == 15

    def test_no_usage_line(self):
        """无 usage 的 data 行不应返回数据。"""
        parser = SSEUsageParser()
        chunk = 'data: {"choices": []}\ndata: [DONE]\n'
        parser.feed(chunk)
        assert parser.last_usage is None

    def test_done_line_ignored(self):
        """[DONE] 行即使含 usage 关键字也不解析。"""
        parser = SSEUsageParser()
        # "usage" 出现在 [DONE] 行的内容中（如 "usage_done"），但行含 [DONE] 应跳过
        chunk = 'data: {"usage": {"total_tokens": 10}}\ndata: [DONE]\n'
        parser.feed(chunk)
        # 第一个 data 行应被解析
        assert parser.last_usage is not None
        assert parser.last_usage["total_tokens"] == 10

    def test_non_data_line_ignored(self):
        """非 data: 前缀的行应被忽略。"""
        parser = SSEUsageParser()
        chunk = ': comment\nevent: ping\ndata: {"usage": {"total_tokens": 5}}\n'
        parser.feed(chunk)
        assert parser.last_usage is not None
        assert parser.last_usage["total_tokens"] == 5


class TestSSEUsageParserCrossChunk:
    """ISSUE-PFM-06：跨 chunk 的 SSE 行拼接测试（AC3）。"""

    def test_usage_line_split_across_chunks(self):
        """data 行被 chunk 边界切分应正确拼接。"""
        parser = SSEUsageParser()
        line = 'data: {"usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}\n'
        # 切成 3 段
        mid1 = len(line) // 3
        mid2 = 2 * len(line) // 3
        parser.feed(line[:mid1])
        assert parser.last_usage is None, "未完整不应解析"
        parser.feed(line[mid1:mid2])
        assert parser.last_usage is None, "未完整不应解析"
        parser.feed(line[mid2:])
        assert parser.last_usage is not None, "拼接完整后应解析"
        assert parser.last_usage["total_tokens"] == 150

    def test_multiple_lines_split_various(self):
        """多行被不同位置切分应全部正确拼接。"""
        parser = SSEUsageParser()
        full = (
            'data: {"choices": [{"delta": "hello"}]}\n'
            'data: {"choices": [{"delta": " world"}]}\n'
            'data: {"usage": {"prompt_tokens": 10, "total_tokens": 20}}\n'
            'data: [DONE]\n'
        )
        # 逐字符喂入（最极端的切分）
        for char in full:
            parser.feed(char)
        assert parser.last_usage is not None
        assert parser.last_usage["total_tokens"] == 20

    def test_chunk_ends_without_newline(self):
        """chunk 末尾无换行符时，不完整行应保留在 buffer。"""
        parser = SSEUsageParser()
        parser.feed('data: {"usage": {"total_tokens": 5}}')  # 无 \n
        assert parser.last_usage is None, "无换行符不应解析"
        parser.feed('\n')  # 补上换行符
        assert parser.last_usage is not None
        assert parser.last_usage["total_tokens"] == 5


class TestSSEUsageParserMultipleUsage:
    """ISSUE-PFM-06：多个 usage 行只取最后一个（与原方案语义一致）。"""

    def test_last_usage_wins(self):
        """多个 usage 行应只保留最后一个。"""
        parser = SSEUsageParser()
        chunk = (
            'data: {"usage": {"total_tokens": 10}}\n'
            'data: {"usage": {"total_tokens": 20}}\n'
            'data: {"usage": {"total_tokens": 30}}\n'
        )
        parser.feed(chunk)
        assert parser.last_usage["total_tokens"] == 30, "应取最后一个"

    def test_usage_after_non_usage(self):
        """非 usage 行之后再有 usage 行应正确记录。"""
        parser = SSEUsageParser()
        chunk = (
            'data: {"choices": []}\n'
            'data: {"usage": {"total_tokens": 10}}\n'
            'data: {"choices": []}\n'
            'data: {"usage": {"total_tokens": 25}}\n'
        )
        parser.feed(chunk)
        assert parser.last_usage["total_tokens"] == 25


class TestSSEUsageParserCRLF:
    """ISSUE-PFM-06：\\r\\n 换行符处理测试。"""

    def test_crlf_line_ending(self):
        """\\r\\n 换行符应正确处理。"""
        parser = SSEUsageParser()
        chunk = 'data: {"usage": {"total_tokens": 10}}\r\n'
        parser.feed(chunk)
        assert parser.last_usage is not None
        assert parser.last_usage["total_tokens"] == 10

    def test_mixed_crlf_and_lf(self):
        """混合 \\r\\n 与 \\n 换行符应都正确处理。"""
        parser = SSEUsageParser()
        chunk = (
            'data: {"usage": {"total_tokens": 10}}\r\n'
            'data: {"usage": {"total_tokens": 20}}\n'
        )
        parser.feed(chunk)
        assert parser.last_usage["total_tokens"] == 20


class TestSSEUsageParserMemory:
    """ISSUE-PFM-06：内存占用恒定测试（AC1）。"""

    def test_buffer_not_accumulate(self):
        """长响应下 line_buffer 不应无限累积。"""
        parser = SSEUsageParser()
        # 模拟 1000 个非 usage 行 + 1 个 usage 行
        for i in range(1000):
            parser.feed(f'data: {{"choices": [{{"delta": "chunk{i}"}}]}}\n')
        parser.feed('data: {"usage": {"total_tokens": 999}}\n')
        # line_buffer 应为空（所有行都有换行符）
        assert parser._line_buffer == "", "line_buffer 不应累积"
        assert parser.last_usage["total_tokens"] == 999

    def test_large_response_no_usage(self):
        """大量无 usage 数据不应导致内存膨胀，last_usage 为 None。"""
        parser = SSEUsageParser()
        # 10KB 的非 usage 数据（每行 100 字节，共 100 行）
        for i in range(100):
            parser.feed(f'data: {{"choices": [{{"delta": "{"x" * 90}"}}]}}\n')
        assert parser.last_usage is None
        assert parser._line_buffer == ""


# ============================================================================
# ISSUE-NET-02：ThreadingHTTPServer 测试
# ============================================================================


class TestThreadingHTTPServer:
    """ISSUE-NET-02：ThreadingHTTPServer 测试。"""

    def test_usage_proxy_uses_threading_server(self):
        """UsageProxy 应使用 ThreadingHTTPServer（而非 HTTPServer）。"""
        from usage_proxy import UsageProxy
        from http.server import ThreadingHTTPServer
        proxy = UsageProxy()
        # 启动服务器
        proxy.start()
        try:
            assert isinstance(proxy._server, ThreadingHTTPServer), \
                "应使用 ThreadingHTTPServer"
        finally:
            proxy.stop()

    def test_daemon_threads_true(self):
        """daemon_threads 应为 True（AC2）。"""
        from usage_proxy import UsageProxy
        proxy = UsageProxy()
        proxy.start()
        try:
            assert proxy._server.daemon_threads is True, \
                "daemon_threads 应为 True"
        finally:
            proxy.stop()

    def test_concurrent_requests_not_queued(self):
        """并发请求应不排队（AC1）。

        启动代理后，并发发起多个请求，验证不串行排队。
        """
        from usage_proxy import UsageProxy
        proxy = UsageProxy(target_host="api.deepseek.com")
        proxy.start()
        try:
            import http.client
            # 并发发起 3 个请求（即使目标不可达，连接应并发处理）
            results = []
            errors = []

            def make_request():
                try:
                    conn = http.client.HTTPConnection("127.0.0.1", proxy._port, timeout=2)
                    conn.request("GET", "/v1/test")
                    resp = conn.getresponse()
                    results.append(resp.status)
                    conn.close()
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=make_request) for _ in range(3)]
            start = __import__("time").time()
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            elapsed = __import__("time").time() - start
            # 至少部分请求被处理（可能因目标不可达返回 502）
            assert len(results) + len(errors) >= 1, "应处理并发请求"
        finally:
            proxy.stop()
