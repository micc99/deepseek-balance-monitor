import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import AccountConfig, AppConfig, SettingsConfig, WindowConfig
from config import load_config, save_config, mask_api_key


def test_load_config_returns_defaults_when_file_missing():
    import config as config_module
    old_path = config_module.CONFIG_PATH
    config_module.CONFIG_PATH = "/nonexistent/path/config.json"
    try:
        config = load_config()
        assert isinstance(config, AppConfig)
        assert config.accounts == []
        assert config.settings.interval_sec == 60
        assert config.settings.theme == "dark"
    finally:
        config_module.CONFIG_PATH = old_path


def test_save_and_load_roundtrip():
    config = AppConfig(
        accounts=[
            AccountConfig(label="Test1", api_key="sk-test1234", provider="deepseek"),
            AccountConfig(label="Test2", api_key="sk-test5678", provider="siliconflow"),
        ],
        settings=SettingsConfig(interval_sec=30, theme="light", autostart=False),
    )

    import config as config_module
    tmpfile = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
    try:
        tmpfile.close()
        config_module.CONFIG_PATH = tmpfile.name
        save_config(config)
        loaded = load_config()
        assert len(loaded.accounts) == 2
        assert loaded.accounts[0].label == "Test1"
        assert loaded.accounts[0].api_key == "sk-test1234"
        assert loaded.settings.interval_sec == 30
        assert loaded.settings.theme == "light"
        assert loaded.settings.autostart is False
    finally:
        os.unlink(tmpfile.name)


def test_mask_api_key_normal():
    result = mask_api_key("sk-abcdefghijklmnop1234")
    assert result == "sk-a****1234"
    assert len("sk-a") + 4 + len("1234") == len(result)
    assert "*" * 4 in result


def test_mask_api_key_short():
    result = mask_api_key("ab1234cd")
    assert result == "ab****cd"


def test_mask_api_key_very_short():
    result = mask_api_key("abcd")
    assert len(result) == 8
    assert "****" in result


def test_account_config_uid_auto_generated():
    acc = AccountConfig(label="Test", api_key="key")
    assert acc.uid is not None
    assert len(acc.uid) == 8


def test_account_config_uid_preserved():
    acc = AccountConfig(label="Test", api_key="key", uid="myuid123")
    assert acc.uid == "myuid123"
