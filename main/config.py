import json
import logging
import os
import sys
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from credential_store import (
    encrypt_api_key,
    decrypt_api_key,
    CredentialDecryptError,
)

if getattr(sys, "frozen", False):
    CONFIG_PATH = os.path.join(os.path.dirname(sys.executable), "config.json")
else:
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

logger = logging.getLogger(__name__)


def _generate_uid() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class AccountConfig:
    """账户配置。

    API Key 加密存储（ISSUE-SEC-01）：
    - api_key_enc: 加密后的密文（base64 编码），持久化到 config.json
    - api_key:     内存中的明文，仅在运行时使用，不持久化
    - needs_reinput: 检测到旧版明文配置或解密失败时标记，UI 据此提示用户重新输入
    """
    label: str
    api_key: str = ""  # 内存明文（运行时使用，不持久化）
    api_key_enc: str = ""  # 加密密文（持久化到 config.json）
    provider: str = "deepseek"
    uid: str = field(default_factory=_generate_uid)
    needs_reinput: bool = field(default=False, repr=False)

    def __post_init__(self):
        """构造后同步 api_key 与 api_key_enc。

        - 若调用方传入 api_key 明文（如 EditAccountDialog），自动加密到 api_key_enc
        - 若调用方传入 api_key_enc（如 load_config 读取），自动解密到 api_key
        - 空 Key 不加密
        """
        # 若明文已给但密文为空，加密明文
        if self.api_key and not self.api_key_enc:
            try:
                self.api_key_enc = encrypt_api_key(self.api_key)
            except Exception as e:
                logger.warning("API Key 加密失败，明文降级存储：%s", e)
                self.api_key_enc = self.api_key  # 降级：明文当密文存（兼容）
        # 若密文已给但明文为空，尝试解密
        elif self.api_key_enc and not self.api_key:
            try:
                self.api_key = decrypt_api_key(self.api_key_enc)
            except CredentialDecryptError as e:
                logger.warning("API Key 解密失败，标记需重新输入：%s", e)
                self.needs_reinput = True
                self.api_key = ""
            except Exception as e:
                logger.warning("API Key 解密异常，标记需重新输入：%s", e)
                self.needs_reinput = True
                self.api_key = ""

    def update_api_key(self, plain: str):
        """显式更新 API Key（自动加密）。"""
        self.api_key = plain
        self.api_key_enc = encrypt_api_key(plain) if plain else ""
        self.needs_reinput = False


@dataclass
class WindowConfig:
    x: Optional[int] = None
    y: Optional[int] = None


@dataclass
class SettingsConfig:
    interval_sec: int = 60
    # ISSUE-THM-02：theme 存主题身份（themes/*.json 的 name 字段），
    # 亮/暗由 theme_mode 表达；旧配置的 theme:"dark"/"light" 在 load_config 运行时映射
    theme: str = "monet_water_lilies"
    theme_mode: str = "dark"  # 亮/暗模式："light" / "dark"（theme_models.MODE_* 值）
    autostart: bool = True
    ripple_color: str = "#aaddff"
    proxy_target: str = "api.deepseek.com"  # 代理转发目标，改为其他 provider 域名即可记录其用量
    log_level: str = "INFO"  # 日志级别：DEBUG / INFO / WARN / ERROR
    # usage_proxy 鉴权 token（DPAPI 加密后的 base64 字符串，ISSUE-SEC-04）
    proxy_token_enc: str = ""


@dataclass
class AppConfig:
    accounts: list[AccountConfig] = field(default_factory=list)
    window: WindowConfig = field(default_factory=WindowConfig)
    settings: SettingsConfig = field(default_factory=SettingsConfig)


def load_config() -> AppConfig:
    if not os.path.exists(CONFIG_PATH):
        return AppConfig()

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    accounts = []
    for a in data.get("accounts", []):
        # ISSUE-SEC-01：检测旧版明文配置（有 api_key 无 api_key_enc）
        # 不自动迁移，标记 needs_reinput 让 UI 提示用户重新输入
        if "api_key" in a and "api_key_enc" not in a:
            logger.warning("检测到旧版明文配置（账户 %s），需重新输入 API Key", a.get("label"))
            accounts.append(AccountConfig(
                label=a.get("label", ""),
                api_key="",  # 不加载明文 key
                api_key_enc="",
                provider=a.get("provider", "deepseek"),
                uid=a.get("uid", _generate_uid()),
                needs_reinput=True,
            ))
        else:
            accounts.append(AccountConfig(
                label=a.get("label", ""),
                api_key="",
                api_key_enc=a.get("api_key_enc", ""),
                provider=a.get("provider", "deepseek"),
                uid=a.get("uid", _generate_uid()),
            ))

    w = data.get("window", {})
    window = WindowConfig(x=w.get("x"), y=w.get("y"))
    s = data.get("settings", {})
    # ISSUE-THM-02：旧主题字段运行时兼容映射（无需版本迁移机制）。
    # 旧 theme 值 "dark"/"light" 表达的是亮暗模式 → 映射为莫奈·睡莲（对应变体）；
    # 新格式 theme=主题身份 + theme_mode=亮暗，直接透传。
    legacy_theme = s.get("theme", "")
    if legacy_theme in ("dark", "light"):
        theme_name = "monet_water_lilies"
        theme_mode = legacy_theme
        logger.info("检测到旧版主题配置 theme=%s，映射为莫奈·睡莲（%s 变体）", legacy_theme, legacy_theme)
    else:
        theme_name = legacy_theme or "monet_water_lilies"
        theme_mode = s.get("theme_mode", "dark")
    settings = SettingsConfig(
        interval_sec=s.get("interval_sec", 60),
        theme=theme_name,
        theme_mode=theme_mode,
        autostart=s.get("autostart", True),
        ripple_color=s.get("ripple_color", "#aaddff"),
        proxy_target=s.get("proxy_target", "api.deepseek.com"),
        log_level=s.get("log_level", "INFO"),
        proxy_token_enc=s.get("proxy_token_enc", ""),
    )
    return AppConfig(accounts=accounts, window=window, settings=settings)


def save_config(config: AppConfig):
    """持久化配置到 config.json。

    ISSUE-SEC-01：仅写入 api_key_enc（加密），不写入明文 api_key。
    """
    accounts_data = []
    for a in config.accounts:
        # 同步：若 api_key 有变更但 api_key_enc 未更新，重新加密
        if a.api_key and not a.api_key_enc:
            try:
                a.api_key_enc = encrypt_api_key(a.api_key)
            except Exception as e:
                logger.warning("保存时 API Key 加密失败，明文降级：%s", e)
                a.api_key_enc = a.api_key
        accounts_data.append({
            "label": a.label,
            "api_key_enc": a.api_key_enc,
            "provider": a.provider,
            "uid": a.uid,
        })

    data = {
        "accounts": accounts_data,
        "window": asdict(config.window),
        "settings": asdict(config.settings),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return key[:2] + "*" * 4 + key[-2:]
    return key[:4] + "*" * 4 + key[-4:]
