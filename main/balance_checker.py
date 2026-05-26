from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import requests


class BalanceStatus(Enum):
    OK = "ok"
    ERROR = "error"
    LOADING = "loading"
    UNKNOWN = "unknown"


@dataclass
class CurrencyBalance:
    currency: str
    total_balance: str
    granted_balance: str = "0.00"
    topped_up_balance: str = "0.00"


@dataclass
class BalanceInfo:
    is_available: bool = False
    balances: list[CurrencyBalance] = field(default_factory=list)
    status: BalanceStatus = BalanceStatus.UNKNOWN
    error_message: str = ""

    @property
    def primary_balance(self) -> Optional[CurrencyBalance]:
        return self.balances[0] if self.balances else None

    @property
    def total_display(self) -> str:
        if not self.balances:
            return "N/A"
        parts = []
        for b in self.balances:
            try:
                value = float(b.total_balance)
                if value == 0:
                    continue
            except (ValueError, TypeError):
                continue
            currency_symbol = "¥" if b.currency == "CNY" else "$"
            parts.append(f"{currency_symbol}{b.total_balance}")
        return " | ".join(parts) if parts else "¥0.00"


class BaseProvider(ABC):
    name: str = "base"
    label: str = "Base"
    description: str = ""

    @abstractmethod
    def check_balance(self, api_key: str) -> BalanceInfo:
        ...

    def _make_request(self, url: str, api_key: str, timeout: int = 10) -> BalanceInfo:
        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=timeout,
            )
            if resp.status_code == 401:
                return BalanceInfo(
                    status=BalanceStatus.ERROR,
                    error_message="API Key 无效 (401)",
                )
            if resp.status_code == 403:
                return BalanceInfo(
                    status=BalanceStatus.ERROR,
                    error_message="无权限 (403)",
                )
            if resp.status_code != 200:
                return BalanceInfo(
                    status=BalanceStatus.ERROR,
                    error_message=f"请求失败 ({resp.status_code})",
                )
            return self._parse_response(resp.json())
        except requests.exceptions.Timeout:
            return BalanceInfo(status=BalanceStatus.ERROR, error_message="请求超时")
        except requests.exceptions.ConnectionError:
            return BalanceInfo(status=BalanceStatus.ERROR, error_message="网络连接失败")
        except Exception as e:
            return BalanceInfo(status=BalanceStatus.ERROR, error_message=str(e))

    def _parse_response(self, data: dict) -> BalanceInfo:
        raise NotImplementedError


class DeepSeekProvider(BaseProvider):
    name = "deepseek"
    label = "DeepSeek"
    description = "深度求索官方"
    URL = "https://api.deepseek.com/user/balance"

    def check_balance(self, api_key: str) -> BalanceInfo:
        return self._make_request(self.URL, api_key)

    def _parse_response(self, data: dict) -> BalanceInfo:
        balances = [
            CurrencyBalance(
                currency=b.get("currency", ""),
                total_balance=b.get("total_balance", "0.00"),
                granted_balance=b.get("granted_balance", "0.00"),
                topped_up_balance=b.get("topped_up_balance", "0.00"),
            )
            for b in data.get("balance_infos", [])
        ]
        return BalanceInfo(
            is_available=data.get("is_available", False),
            balances=balances,
            status=BalanceStatus.OK,
        )


class SiliconFlowProvider(BaseProvider):
    name = "siliconflow"
    label = "硅基流动"
    description = "第三方聚合平台"
    URL = "https://api.siliconflow.cn/v1/user/info"

    def check_balance(self, api_key: str) -> BalanceInfo:
        return self._make_request(self.URL, api_key)

    def _parse_response(self, data: dict) -> BalanceInfo:
        inner = data.get("data", data)
        total = str(inner.get("totalBalance", inner.get("balance", "0")))
        charged = str(inner.get("chargeBalance", "0"))
        granted = str(inner.get("grantedBalance", "0"))
        balances = [CurrencyBalance(
            currency="CNY",
            total_balance=total,
            topped_up_balance=charged,
            granted_balance=granted,
        )]
        return BalanceInfo(
            is_available=float(total) > 0,
            balances=balances,
            status=BalanceStatus.OK,
        )


class MoonshotProvider(BaseProvider):
    name = "moonshot"
    label = "月之暗面 Kimi"
    description = "Moonshot AI 官方"
    URL = "https://api.moonshot.cn/v1/users/me/balance"

    def check_balance(self, api_key: str) -> BalanceInfo:
        return self._make_request(self.URL, api_key)

    def _parse_response(self, data: dict) -> BalanceInfo:
        inner = data.get("data", data)
        total = str(inner.get("available_balance", inner.get("balance", "0")))
        balances = [CurrencyBalance(currency="CNY", total_balance=total)]
        return BalanceInfo(
            is_available=float(total) > 0 if total.replace(".", "").isdigit() else True,
            balances=balances,
            status=BalanceStatus.OK,
        )


class OpenRouterProvider(BaseProvider):
    name = "openrouter"
    label = "OpenRouter"
    description = "国际聚合平台"
    URL = "https://openrouter.ai/api/v1/auth/key"

    def check_balance(self, api_key: str) -> BalanceInfo:
        return self._make_request(self.URL, api_key)

    def _parse_response(self, data: dict) -> BalanceInfo:
        inner = data.get("data", data)
        credits = str(inner.get("credits", "0"))
        usage = str(inner.get("usage", "0"))
        balances = [CurrencyBalance(
            currency="USD",
            total_balance=credits,
            topped_up_balance=credits,
        )]
        return BalanceInfo(
            is_available=float(credits) > 0,
            balances=balances,
            status=BalanceStatus.OK,
        )


class ZhipuProvider(BaseProvider):
    name = "zhipu"
    label = "智谱AI (GLM)"
    description = "智谱华章官方"
    URL = "https://open.bigmodel.cn/api/paas/v4/billing/info"

    def check_balance(self, api_key: str) -> BalanceInfo:
        return self._make_request(self.URL, api_key)

    def _parse_response(self, data: dict) -> BalanceInfo:
        inner = data.get("data", data)
        total = str(inner.get("total_balance", inner.get("balance", "0")))
        balances = [CurrencyBalance(currency="CNY", total_balance=total)]
        return BalanceInfo(
            is_available=float(total) > 0 if total.replace(".", "").replace("-", "").isdigit() else True,
            balances=balances,
            status=BalanceStatus.OK,
        )


PROVIDERS: dict[str, BaseProvider] = {
    "deepseek": DeepSeekProvider(),
    "siliconflow": SiliconFlowProvider(),
    "moonshot": MoonshotProvider(),
    "openrouter": OpenRouterProvider(),
    "zhipu": ZhipuProvider(),
}


def get_provider(name: str) -> BaseProvider:
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider: {name}")
    return PROVIDERS[name]


def register_provider(provider: BaseProvider):
    PROVIDERS[provider.name] = provider


def get_provider_list() -> list[tuple[str, str, str]]:
    return [(p.name, p.label, p.description) for p in PROVIDERS.values()]
