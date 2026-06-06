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
