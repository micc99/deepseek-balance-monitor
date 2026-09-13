from __future__ import annotations

import logging

from config import AppConfig
from usage_proxy import UsageProxy


"""本地用量代理生命周期（ISSUE-ARC-01，原 App 内联逻辑收编）。

端口约定（AGENTS.md §6.5）：代理固定 127.0.0.1:52848，硬编码于 usage_proxy。
"""

logger = logging.getLogger(__name__)


class ProxyManager:
    """UsageProxy 的创建/启停与 token 访问。"""

    def __init__(self):
        self._proxy: UsageProxy | None = None
        self._proxy_url: str = ""
        self.token_enc_changed: bool = False

    def start(self, config: AppConfig) -> str:
        """创建并启动代理（端口绑定，磁盘外 IO），返回代理 URL。

        UsageProxy 仅在后台加载线程中创建（PFM-02：App.__init__ 不得
        出现 UsageProxy( 构造，集成验证断言）。
        """
        self._proxy = UsageProxy(
            target_host=config.settings.proxy_target,
            proxy_token_enc=config.settings.proxy_token_enc,
        )
        self.token_enc_changed = self._proxy.token_enc_changed
        self._proxy.start()
        self._proxy_url = self._proxy.proxy_url
        return self._proxy_url

    def stop(self) -> None:
        if self._proxy is not None:
            self._proxy.stop()
            self._proxy = None

    @property
    def proxy_url(self) -> str:
        return self._proxy_url

    @property
    def proxy_token_enc(self) -> str:
        return self._proxy.proxy_token_enc if self._proxy else ""

    def get_proxy_token(self) -> str:
        """代理鉴权 token 提供者（注入设置面板展示 hash，SEC-04）。"""
        return self._proxy.get_proxy_token() if self._proxy else ""
