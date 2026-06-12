import json
import os
import sys
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

if getattr(sys, "frozen", False):
    CONFIG_PATH = os.path.join(os.path.dirname(sys.executable), "config.json")
else:
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _generate_uid() -> str:
    return uuid.uuid4().hex[:8]


@dataclass
class AccountConfig:
    label: str
    api_key: str
    provider: str = "deepseek"
    uid: str = field(default_factory=_generate_uid)


@dataclass
class WindowConfig:
    x: Optional[int] = None
    y: Optional[int] = None


@dataclass
class SettingsConfig:
    interval_sec: int = 60
    theme: str = "dark"
    autostart: bool = True
    ripple_color: str = "#aaddff"
    proxy_target: str = "api.deepseek.com"  # 代理转发目标，改为其他 provider 域名即可记录其用量


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

    accounts = [AccountConfig(**a) for a in data.get("accounts", [])]
    w = data.get("window", {})
    window = WindowConfig(x=w.get("x"), y=w.get("y"))
    s = data.get("settings", {})
    settings = SettingsConfig(
        interval_sec=s.get("interval_sec", 60),
        theme=s.get("theme", "dark"),
        autostart=s.get("autostart", True),
        ripple_color=s.get("ripple_color", "#aaddff"),
        proxy_target=s.get("proxy_target", "api.deepseek.com"),
    )
    return AppConfig(accounts=accounts, window=window, settings=settings)


def save_config(config: AppConfig):
    data = {
        "accounts": [asdict(a) for a in config.accounts],
        "window": asdict(config.window),
        "settings": asdict(config.settings),
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return key[:2] + "*" * 4 + key[-2:]
    return key[:4] + "*" * 4 + key[-4:]
