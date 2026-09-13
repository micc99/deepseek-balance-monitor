from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging
import math
import re
import threading
import time
import requests
from requests.adapters import HTTPAdapter


"""多 Provider 余额查询抽象层。

每个 Provider 子类实现自己的 API 响应解析，统一返回 BalanceInfo。
新增 Provider 只需继承 BaseProvider 并注册到 PROVIDERS 字典。

ISSUE-PFM-04：BaseProvider 持有按线程隔离的 requests.Session（threading.local），
复用 TCP/TLS 连接，配置连接池（pool_connections=5, pool_maxsize=10），
配合 ISSUE-PFM-03 的 ThreadPoolExecutor 保证线程安全。

ISSUE-NET-03：_make_request 内置重试与指数退避（1s→2s→4s，最多 3 次），
超时/连接错误/5xx 状态码触发重试，4xx 不重试。

ISSUE-ARC-04：safe_float 容错数字解析——负数、科学计数法、千分位、
货币符号、空值均正确处理，替代脆弱的 .replace(".","").isdigit() 判断。
"""

logger = logging.getLogger(__name__)

# ISSUE-PFM-04：连接池配置
_POOL_CONNECTIONS = 5  # 连接池数量（按主机隔离）
_POOL_MAXSIZE = 10      # 单主机连接池最大连接数

# ISSUE-NET-03：重试与退避配置
_MAX_ATTEMPTS = 3  # 最大尝试次数（首次 + 2 次重试）
_BACKOFF_SECONDS = [1, 2, 4]  # 指数退避间隔（秒），索引 0=首次重试前等待

# ISSUE-ARC-04：合法十进制/科学计数法数字（用于拒绝 inf/nan/下划线等字面量）
_NUMBER_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def safe_float(value, default: float = 0.0) -> float:
    """容错数字解析（ISSUE-ARC-04）。

    - 支持常规小数、负数（-5.2）、科学计数法（1e-5）、千分位（1,000.50）、
      货币符号（¥100.50 / $20.00）、前后空白
    - 空字符串 / None / 非法文本 / inf / nan / 下划线数字（1_000）返回 default
    """
    if value is None:
        return default
    s = str(value).strip().replace(",", "").replace("¥", "").replace("$", "")
    if not s:
        return default
    try:
        result = float(s)
    except (ValueError, TypeError):
        return default
    # 正则兜底：float() 会接受 inf/nan/1_000 等字面量，余额语境下一律视为非法
    if not _NUMBER_RE.match(s):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


class BalanceStatus(Enum):
    OK = "ok"
    ERROR = "error"
    LOADING = "loading"  # 请求进行中，UI 显示占位
    UNKNOWN = "unknown"


@dataclass
class CurrencyBalance:
    """单币种余额明细。多币种账户（如 DeepSeek CNY+USD）会有多个实例。"""
    currency: str
    total_balance: str
    granted_balance: str = "0.00"
    topped_up_balance: str = "0.00"


@dataclass
class BalanceInfo:
    """一次余额查询的完整结果，包含状态、余额列表和错误信息。"""
    is_available: bool = False
    balances: list[CurrencyBalance] = field(default_factory=list)
    status: BalanceStatus = BalanceStatus.UNKNOWN
    error_message: str = ""

    @property
    def primary_balance(self) -> Optional[CurrencyBalance]:
        """取第一个币种余额，用于单币种场景的快捷访问。"""
        return self.balances[0] if self.balances else None

    @property
    def total_display(self) -> str:
        """格式化显示字符串，如 '¥100.50 | $20.00'，跳过零余额。"""
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
    """Provider 基类。子类必须实现 _parse_response 来适配不同 API 的响应格式。

    ISSUE-PFM-04：每个 Provider 实例按线程隔离持有 requests.Session，
    - 每个线程首次请求时创建 Session 并挂载 HTTPAdapter（连接池配置）
    - 后续请求复用 Session，避免重复 TCP/TLS 握手
    - close_all_sessions() 在退出时关闭所有线程的 Session
    """
    name: str = "base"
    label: str = "Base"
    description: str = ""

    def __init__(self):
        # ISSUE-PFM-04：按线程隔离的 Session（threading.local）
        # 每个线程首次访问时创建独立 Session，避免 requests.Session 非线程安全问题
        self._thread_local = threading.local()
        # 维护所有线程创建的 Session 列表，用于退出时统一关闭
        self._all_sessions: list[requests.Session] = []
        self._sessions_lock = threading.Lock()

    def _get_session(self) -> requests.Session:
        """ISSUE-PFM-04：获取当前线程的 Session（首次访问时创建）。

        使用 threading.local 实现线程隔离，每个线程拥有独立的 Session 实例，
        避免多线程共享 Session 导致的并发问题。

        Returns:
            requests.Session: 当前线程专属的 Session，已挂载连接池适配器
        """
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.trust_env = False  # 绕过系统代理设置
            # 挂载 HTTPAdapter 配置连接池
            adapter = HTTPAdapter(
                pool_connections=_POOL_CONNECTIONS,
                pool_maxsize=_POOL_MAXSIZE,
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            self._thread_local.session = session
            # 加入全局列表，便于退出时关闭
            with self._sessions_lock:
                self._all_sessions.append(session)
        return session

    def close_all_sessions(self):
        """ISSUE-PFM-04：关闭所有线程创建的 Session，释放连接池资源。

        在应用退出时调用（App._quit），确保 TCP 连接正确关闭。
        """
        with self._sessions_lock:
            for session in self._all_sessions:
                try:
                    session.close()
                except Exception as e:
                    logger.warning("关闭 Session 失败：%s", e)
            self._all_sessions.clear()

    @abstractmethod
    def check_balance(self, api_key: str) -> BalanceInfo:
        """发起 HTTP 请求查询余额，返回统一的 BalanceInfo。"""
        ...

    def _make_request(self, url: str, api_key: str, timeout: int = 10) -> BalanceInfo:
        """通用 GET 请求 + 错误处理 + 重试退避，子类只需提供 URL 和 _parse_response。

        ISSUE-PFM-04：复用按线程隔离的 Session，避免每次请求新建连接。
        显式禁用系统代理读取（trust_env=False），避免被 Steam++ 等游戏加速器
        修改的系统代理设置影响，导致 API 请求无法正常到达目标服务器。

        ISSUE-NET-03：重试与指数退避策略：
        - 重试条件：Timeout、ConnectionError、5xx 状态码
        - 退避：1s → 2s → 4s（指数退避）
        - 最多 3 次（首次 + 2 次重试）
        - 4xx（含 401/403）不重试，直接返回
        - 重试耗尽返回 ERROR，error_message 标注"重试 N 次后失败"
        - 重试中记录 INFO 日志（UI 状态通知待 ISSUE-ARC-02 事件总线）
        """
        # ISSUE-NET-03：重试循环
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                session = self._get_session()
                resp = session.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=timeout,
                )
                # 4xx 不重试（含 401/403）
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
                if 400 <= resp.status_code < 500:
                    return BalanceInfo(
                        status=BalanceStatus.ERROR,
                        error_message=f"请求失败 ({resp.status_code})",
                    )
                # 5xx 触发重试
                if resp.status_code >= 500:
                    if attempt < _MAX_ATTEMPTS:
                        logger.info(
                            "请求返回 5xx（%d），重试中（第 %d/%d 次，等待 %ds）",
                            resp.status_code, attempt, _MAX_ATTEMPTS,
                            _BACKOFF_SECONDS[attempt - 1],
                        )
                        time.sleep(_BACKOFF_SECONDS[attempt - 1])
                        continue
                    return BalanceInfo(
                        status=BalanceStatus.ERROR,
                        error_message=f"重试 {_MAX_ATTEMPTS - 1} 次后失败（5xx: {resp.status_code}）",
                    )
                # 200 成功
                return self._parse_response(resp.json())
            except requests.exceptions.Timeout:
                if attempt < _MAX_ATTEMPTS:
                    logger.info(
                        "请求超时，重试中（第 %d/%d 次，等待 %ds）",
                        attempt, _MAX_ATTEMPTS, _BACKOFF_SECONDS[attempt - 1],
                    )
                    time.sleep(_BACKOFF_SECONDS[attempt - 1])
                    continue
                return BalanceInfo(
                    status=BalanceStatus.ERROR,
                    error_message=f"重试 {_MAX_ATTEMPTS - 1} 次后失败（请求超时）",
                )
            except requests.exceptions.ConnectionError:
                if attempt < _MAX_ATTEMPTS:
                    logger.info(
                        "网络连接失败，重试中（第 %d/%d 次，等待 %ds）",
                        attempt, _MAX_ATTEMPTS, _BACKOFF_SECONDS[attempt - 1],
                    )
                    time.sleep(_BACKOFF_SECONDS[attempt - 1])
                    continue
                return BalanceInfo(
                    status=BalanceStatus.ERROR,
                    error_message=f"重试 {_MAX_ATTEMPTS - 1} 次后失败（网络连接失败）",
                )
            except Exception as e:
                # 未知异常不重试，直接返回
                return BalanceInfo(status=BalanceStatus.ERROR, error_message=str(e))
        # 理论上不会到达（循环内所有路径都有 return）
        return BalanceInfo(status=BalanceStatus.ERROR, error_message="未知错误")

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
            # ISSUE-ARC-04：safe_float 容错解析，替代裸 float()（坏数据不再抛异常）
            is_available=safe_float(total) > 0,
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
        # ISSUE-ARC-04：safe_float 替代 .replace(".","").isdigit()——负数/科学计数法/千分位不再误判
        return BalanceInfo(
            is_available=safe_float(total) > 0,
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
            # ISSUE-ARC-04：safe_float 容错解析
            is_available=safe_float(credits) > 0,
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
        # ISSUE-ARC-04：safe_float 替代 .replace(".","").replace("-","").isdigit()
        return BalanceInfo(
            is_available=safe_float(total) > 0,
            balances=balances,
            status=BalanceStatus.OK,
        )


# 全局 Provider 注册表，key 与 config.json 中的 provider 字段对应
# ISSUE-PFM-04：实例化时创建按线程隔离的 Session 池
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


def close_all_provider_sessions():
    """ISSUE-PFM-04：关闭所有 Provider 的所有线程 Session。

    在应用退出时调用，释放连接池资源。
    """
    for provider in PROVIDERS.values():
        try:
            provider.close_all_sessions()
        except Exception as e:
            logger.warning("关闭 Provider Session 失败：%s", e)
