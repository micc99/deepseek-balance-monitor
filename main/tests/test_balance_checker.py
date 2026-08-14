import json
import os
import sys
import pytest
import responses

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from balance_checker import (
    BalanceStatus, BalanceInfo, CurrencyBalance,
    DeepSeekProvider, SiliconFlowProvider, MoonshotProvider,
    OpenRouterProvider, ZhipuProvider,
    get_provider, register_provider, get_provider_list, BaseProvider,
)


class TestDeepSeekProvider:
    def test_parse_response_success(self):
        provider = DeepSeekProvider()
        data = {
            "is_available": True,
            "balance_infos": [
                {"currency": "CNY", "total_balance": "50.00", "granted_balance": "10.00", "topped_up_balance": "40.00"}
            ]
        }
        result = provider._parse_response(data)
        assert result.status == BalanceStatus.OK
        assert result.is_available is True
        assert len(result.balances) == 1
        assert result.balances[0].currency == "CNY"
        assert result.balances[0].total_balance == "50.00"

    def test_parse_response_empty(self):
        provider = DeepSeekProvider()
        data = {"is_available": False, "balance_infos": []}
        result = provider._parse_response(data)
        assert result.status == BalanceStatus.OK
        assert result.is_available is False
        assert result.balances == []

    @responses.activate
    def test_check_balance_success(self):
        provider = DeepSeekProvider()
        responses.add(
            responses.GET,
            "https://api.deepseek.com/user/balance",
            json={"is_available": True, "balance_infos": [{"currency": "CNY", "total_balance": "100.00"}]},
            status=200,
        )
        result = provider.check_balance("sk-test")
        assert result.status == BalanceStatus.OK
        assert result.balances[0].total_balance == "100.00"

    @responses.activate
    def test_check_balance_401(self):
        provider = DeepSeekProvider()
        responses.add(
            responses.GET,
            "https://api.deepseek.com/user/balance",
            json={},
            status=401,
        )
        result = provider.check_balance("sk-test")
        assert result.status == BalanceStatus.ERROR
        assert "401" in result.error_message

    @responses.activate
    def test_check_balance_timeout(self):
        import requests
        provider = DeepSeekProvider()
        def raise_timeout(request):
            raise requests.exceptions.Timeout()
        responses.add_callback(
            responses.GET,
            "https://api.deepseek.com/user/balance",
            callback=raise_timeout,
        )
        result = provider.check_balance("sk-test")
        assert result.status == BalanceStatus.ERROR
        assert "超时" in result.error_message


class TestSiliconFlowProvider:
    def test_parse_response(self):
        provider = SiliconFlowProvider()
        data = {"data": {"totalBalance": "200.00", "chargeBalance": "100.00", "grantedBalance": "100.00"}}
        result = provider._parse_response(data)
        assert result.status == BalanceStatus.OK
        assert result.balances[0].total_balance == "200.00"
        assert result.balances[0].currency == "CNY"


class TestMoonshotProvider:
    def test_parse_response(self):
        provider = MoonshotProvider()
        data = {"data": {"available_balance": "300.00"}}
        result = provider._parse_response(data)
        assert result.status == BalanceStatus.OK
        assert result.balances[0].total_balance == "300.00"


class TestOpenRouterProvider:
    def test_parse_response(self):
        provider = OpenRouterProvider()
        data = {"data": {"credits": "25.50", "usage": "10.00"}}
        result = provider._parse_response(data)
        assert result.status == BalanceStatus.OK
        assert result.balances[0].total_balance == "25.50"
        assert result.balances[0].currency == "USD"


class TestZhipuProvider:
    def test_parse_response(self):
        provider = ZhipuProvider()
        data = {"data": {"total_balance": "0.00"}}
        result = provider._parse_response(data)
        assert result.status == BalanceStatus.OK
        assert result.balances[0].total_balance == "0.00"


class TestBalanceInfo:
    def test_total_display_single_cny(self):
        info = BalanceInfo(
            is_available=True,
            balances=[CurrencyBalance(currency="CNY", total_balance="50.50")],
            status=BalanceStatus.OK,
        )
        assert info.total_display == "¥50.50"

    def test_total_display_single_usd(self):
        info = BalanceInfo(
            is_available=True,
            balances=[CurrencyBalance(currency="USD", total_balance="10.00")],
            status=BalanceStatus.OK,
        )
        assert info.total_display == "$10.00"

    def test_total_display_mixed(self):
        info = BalanceInfo(
            is_available=True,
            balances=[
                CurrencyBalance(currency="CNY", total_balance="100.00"),
                CurrencyBalance(currency="USD", total_balance="20.00"),
            ],
            status=BalanceStatus.OK,
        )
        assert "¥100.00" in info.total_display
        assert "$20.00" in info.total_display

    def test_total_display_empty(self):
        info = BalanceInfo(status=BalanceStatus.UNKNOWN)
        assert info.total_display == "N/A"

    def test_primary_balance(self):
        info = BalanceInfo(
            balances=[CurrencyBalance(currency="CNY", total_balance="99.99")],
            status=BalanceStatus.OK,
        )
        assert info.primary_balance is not None
        assert info.primary_balance.total_balance == "99.99"


class TestProviderRegistry:
    def test_get_provider_valid(self):
        provider = get_provider("deepseek")
        assert isinstance(provider, DeepSeekProvider)

    def test_get_provider_invalid(self):
        with pytest.raises(ValueError):
            get_provider("nonexistent")

    def test_get_provider_list(self):
        providers = get_provider_list()
        assert len(providers) >= 5
        names = [p[0] for p in providers]
        assert "deepseek" in names
        assert "siliconflow" in names


# ============================================================================
# ISSUE-PFM-04：Provider Session 长连接复用测试
# ============================================================================


class TestProviderSessionReuse:
    """ISSUE-PFM-04：Provider Session 长连接复用测试。"""

    def test_provider_has_thread_local(self):
        """BaseProvider 实例应持有 threading.local（AC1：Provider 持有长连接 Session）。"""
        provider = DeepSeekProvider()
        assert hasattr(provider, "_thread_local"), "应持有 threading.local"
        assert hasattr(provider, "_all_sessions"), "应维护 Session 列表"

    def test_get_session_returns_same_instance_per_thread(self):
        """同一线程多次 _get_session 应返回同一 Session 实例（复用）。"""
        import threading
        provider = DeepSeekProvider()
        results = {}

        def worker():
            s1 = provider._get_session()
            s2 = provider._get_session()
            results["same"] = (s1 is s2)

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert results["same"] is True, "同线程应复用同一 Session"

    def test_get_session_returns_different_per_thread(self):
        """不同线程应获得独立 Session（线程隔离）。"""
        import threading
        provider = DeepSeekProvider()
        sessions = {}

        def worker(tid):
            sessions[tid] = provider._get_session()

        t1 = threading.Thread(target=worker, args=(1,))
        t2 = threading.Thread(target=worker, args=(2,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert sessions[1] is not sessions[2], "不同线程应有独立 Session"

    def test_session_has_http_adapter(self):
        """Session 应挂载 HTTPAdapter（连接池配置）。"""
        provider = DeepSeekProvider()
        session = provider._get_session()
        adapter = session.get_adapter("https://api.deepseek.com")
        from requests.adapters import HTTPAdapter
        assert isinstance(adapter, HTTPAdapter), "应挂载 HTTPAdapter"

    def test_session_trust_env_false(self):
        """Session 应禁用系统代理读取（trust_env=False）。"""
        provider = DeepSeekProvider()
        session = provider._get_session()
        assert session.trust_env is False, "应禁用系统代理"

    def test_close_all_sessions(self):
        """close_all_sessions() 应关闭所有线程的 Session（AC4）。"""
        provider = DeepSeekProvider()
        # 创建几个 Session
        provider._get_session()
        assert len(provider._all_sessions) >= 1
        provider.close_all_sessions()
        assert len(provider._all_sessions) == 0, "关闭后 Session 列表应清空"

    def test_close_all_provider_sessions_global(self):
        """close_all_provider_sessions() 应关闭所有全局 Provider 的 Session。"""
        # 先创建一些 Session
        for p_name in ["deepseek", "siliconflow"]:
            get_provider(p_name)._get_session()
        # 关闭所有
        from balance_checker import close_all_provider_sessions
        close_all_provider_sessions()
        # 验证已清空
        for p in [get_provider("deepseek"), get_provider("siliconflow")]:
            assert len(p._all_sessions) == 0


# ============================================================================
# ISSUE-NET-03：balance_checker 重试与退避测试
# ============================================================================


class TestBalanceCheckerRetry:
    """ISSUE-NET-03：重试与退避测试。"""

    def test_401_no_retry(self, monkeypatch):
        """401 状态码不应触发重试（AC2：4xx 不重试）。"""
        sleep_calls = []
        monkeypatch.setattr("balance_checker.time.sleep", lambda s: sleep_calls.append(s))

        provider = DeepSeekProvider()
        call_count = {"n": 0}

        @responses.activate
        def run():
            def callback(request):
                call_count["n"] += 1
                return (401, {}, json.dumps({}))

            responses.add_callback(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                callback=callback,
            )
            result = provider.check_balance("sk-test")
            assert result.status == BalanceStatus.ERROR
            assert "401" in result.error_message
            assert call_count["n"] == 1, "401 不应重试"
            assert len(sleep_calls) == 0, "401 不应有退避等待"

        run()

    def test_timeout_retries(self, monkeypatch):
        """超时应触发重试（AC1：超时重试，退避 1s→2s→4s）。"""
        sleep_calls = []
        monkeypatch.setattr("balance_checker.time.sleep", lambda s: sleep_calls.append(s))

        provider = DeepSeekProvider()
        call_count = {"n": 0}

        @responses.activate
        def run():
            import requests as req
            def callback(request):
                call_count["n"] += 1
                raise req.exceptions.Timeout()

            responses.add_callback(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                callback=callback,
            )
            result = provider.check_balance("sk-test")
            assert result.status == BalanceStatus.ERROR
            assert "重试" in result.error_message, "应标注重试耗尽"
            # 首次 + 2 次重试 = 3 次
            assert call_count["n"] == 3, f"应尝试 3 次，实际 {call_count['n']}"
            # 退避：1s, 2s（最后一次不等待）
            assert sleep_calls == [1, 2], f"退避应为 [1, 2]，实际 {sleep_calls}"

        run()

    def test_5xx_retries(self, monkeypatch):
        """5xx 状态码应触发重试（AC1：5xx 重试）。"""
        sleep_calls = []
        monkeypatch.setattr("balance_checker.time.sleep", lambda s: sleep_calls.append(s))

        provider = DeepSeekProvider()
        call_count = {"n": 0}

        @responses.activate
        def run():
            def callback(request):
                call_count["n"] += 1
                return (500, {}, json.dumps({"error": "server error"}))

            responses.add_callback(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                callback=callback,
            )
            result = provider.check_balance("sk-test")
            assert result.status == BalanceStatus.ERROR
            assert "重试" in result.error_message
            assert "500" in result.error_message
            assert call_count["n"] == 3
            assert sleep_calls == [1, 2]

        run()

    def test_connection_error_retries(self, monkeypatch):
        """ConnectionError 应触发重试（AC1：ConnectionError 重试）。"""
        sleep_calls = []
        monkeypatch.setattr("balance_checker.time.sleep", lambda s: sleep_calls.append(s))

        provider = DeepSeekProvider()
        call_count = {"n": 0}

        @responses.activate
        def run():
            import requests as req
            def callback(request):
                call_count["n"] += 1
                raise req.exceptions.ConnectionError()

            responses.add_callback(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                callback=callback,
            )
            result = provider.check_balance("sk-test")
            assert result.status == BalanceStatus.ERROR
            assert "重试" in result.error_message
            assert "网络连接" in result.error_message
            assert call_count["n"] == 3

        run()

    def test_success_after_retry(self, monkeypatch):
        """首次失败重试后成功应返回 OK。"""
        monkeypatch.setattr("balance_checker.time.sleep", lambda s: None)

        provider = DeepSeekProvider()
        call_count = {"n": 0}

        @responses.activate
        def run():
            import requests as req
            def callback(request):
                call_count["n"] += 1
                if call_count["n"] < 3:
                    raise req.exceptions.Timeout()
                return (200, {}, json.dumps({
                    "is_available": True,
                    "balance_infos": [{"currency": "CNY", "total_balance": "100.00"}],
                }))

            responses.add_callback(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                callback=callback,
            )
            result = provider.check_balance("sk-test")
            assert result.status == BalanceStatus.OK
            assert call_count["n"] == 3, "前 2 次失败，第 3 次成功"
            assert result.balances[0].total_balance == "100.00"

        run()

    def test_retry_exhausted_returns_error(self, monkeypatch):
        """重试耗尽应返回 ERROR 并标注次数（AC4）。"""
        monkeypatch.setattr("balance_checker.time.sleep", lambda s: None)

        provider = DeepSeekProvider()

        @responses.activate
        def run():
            import requests as req
            def callback(request):
                raise req.exceptions.Timeout()

            responses.add_callback(
                responses.GET,
                "https://api.deepseek.com/user/balance",
                callback=callback,
            )
            result = provider.check_balance("sk-test")
            assert result.status == BalanceStatus.ERROR
            assert "重试 2 次后失败" in result.error_message

        run()
