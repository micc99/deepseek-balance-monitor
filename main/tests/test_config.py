"""config 模块测试（适配 v1.10.0 加密存储）。

ISSUE-SEC-01：AccountConfig.api_key 已改为内存明文（运行时使用），
持久化字段改为 api_key_enc（DPAPI 加密 + base64 编码）。
save_config 仅写入 api_key_enc，不写入明文 api_key。
load_config 检测旧版明文配置时标记 needs_reinput，不自动迁移。

测试覆盖：
- AccountConfig 自动加密 api_key 到 api_key_enc
- save_config 不写入明文 api_key
- load_config 从 api_key_enc 解密到 api_key
- 旧版明文配置检测（needs_reinput）
- uid 自动生成与保留
- mask_api_key 脱敏函数
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config as config_module
from config import AccountConfig, AppConfig, SettingsConfig, WindowConfig
from config import load_config, save_config, mask_api_key
from credential_store import (
    PlainCredentialStore,
    set_credential_store_for_test,
)


@pytest.fixture(autouse=True)
def use_plain_credential_store():
    """每个测试用例使用 PlainCredentialStore（base64 编码，无 DPAPI 依赖）。

    确保测试在无 DPAPI 环境（如 CI / 非 Windows）也能运行，
    且加密解密可逆，便于断言。
    """
    set_credential_store_for_test(PlainCredentialStore())
    yield
    set_credential_store_for_test(None)


def test_load_config_returns_defaults_when_file_missing():
    config_module.CONFIG_PATH = "/nonexistent/path/config.json"
    try:
        config = load_config()
        assert isinstance(config, AppConfig)
        assert config.accounts == []
        assert config.settings.interval_sec == 60
        assert config.settings.theme == "dark"
    finally:
        config_module.CONFIG_PATH = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "config.json"
        )


def test_save_and_load_roundtrip():
    """加密存储往返：save → load 后 api_key 应可还原。"""
    config = AppConfig(
        accounts=[
            AccountConfig(label="Test1", api_key="sk-test1234", provider="deepseek"),
            AccountConfig(label="Test2", api_key="sk-test5678", provider="siliconflow"),
        ],
        settings=SettingsConfig(interval_sec=30, theme="light", autostart=False),
    )

    tmpfile = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
    try:
        tmpfile.close()
        config_module.CONFIG_PATH = tmpfile.name
        save_config(config)

        # 验证 config.json 中无明文 api_key
        with open(tmpfile.name, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for acc in raw["accounts"]:
            assert "api_key" not in acc, "config.json 不应包含明文 api_key 字段"
            assert "api_key_enc" in acc, "config.json 应包含 api_key_enc 字段"
            assert acc["api_key_enc"], "api_key_enc 不应为空"

        loaded = load_config()
        assert len(loaded.accounts) == 2
        assert loaded.accounts[0].label == "Test1"
        # 解密后 api_key 应可还原
        assert loaded.accounts[0].api_key == "sk-test1234"
        assert loaded.accounts[1].api_key == "sk-test5678"
        assert loaded.settings.interval_sec == 30
        assert loaded.settings.theme == "light"
        assert loaded.settings.autostart is False
    finally:
        config_module.CONFIG_PATH = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "config.json"
        )
        if os.path.exists(tmpfile.name):
            os.unlink(tmpfile.name)


def test_save_config_no_plaintext_api_key():
    """ISSUE-SEC-01 AC1：config.json 中不存在明文 api_key 字段。"""
    config = AppConfig(
        accounts=[AccountConfig(label="T", api_key="sk-secret-key-xxxx", provider="deepseek")],
    )
    tmpfile = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
    try:
        tmpfile.close()
        config_module.CONFIG_PATH = tmpfile.name
        save_config(config)

        with open(tmpfile.name, "r", encoding="utf-8") as f:
            content = f.read()
        # 不应出现明文 key
        assert "sk-secret-key-xxxx" not in content
        assert "api_key" not in content or '"api_key_enc"' in content
    finally:
        config_module.CONFIG_PATH = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "config.json"
        )
        if os.path.exists(tmpfile.name):
            os.unlink(tmpfile.name)


def test_account_config_auto_encrypt():
    """AccountConfig 传入 api_key 明文时应自动加密到 api_key_enc。"""
    acc = AccountConfig(label="T", api_key="sk-plain-key-xxxxx")
    assert acc.api_key == "sk-plain-key-xxxxx"
    assert acc.api_key_enc, "api_key_enc 应非空"
    assert acc.api_key_enc != "sk-plain-key-xxxxx", "密文不应等于明文"


def test_account_config_auto_decrypt():
    """AccountConfig 传入 api_key_enc 时应自动解密到 api_key。"""
    plain = "sk-original-key-abc"
    enc = PlainCredentialStore().encrypt(plain)
    acc = AccountConfig(label="T", api_key_enc=enc)
    assert acc.api_key == plain
    assert acc.api_key_enc == enc


def test_account_config_empty_key_not_encrypted():
    """空 Key 不加密，api_key_enc 应为空字符串。"""
    acc = AccountConfig(label="T", api_key="")
    assert acc.api_key == ""
    assert acc.api_key_enc == ""


def test_account_config_needs_reinput_on_decrypt_failure():
    """ISSUE-SEC-01 AC3/AC4：解密失败时应标记 needs_reinput。"""
    # 使用无效密文（非 base64 或解密失败）
    acc = AccountConfig(label="T", api_key_enc="!!!invalid-cipher!!!")
    assert acc.needs_reinput is True
    assert acc.api_key == ""


def test_load_config_detects_legacy_plaintext():
    """ISSUE-SEC-01 AC6：检测旧版明文配置时标记 needs_reinput，不自动迁移。"""
    tmpfile = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
    try:
        # 写入旧版明文配置格式
        legacy_data = {
            "accounts": [
                {"label": "Legacy", "api_key": "sk-legacy-plain-key", "provider": "deepseek", "uid": "legacy001"}
            ],
            "window": {},
            "settings": {"interval_sec": 60, "theme": "dark"},
        }
        tmpfile.write(json.dumps(legacy_data))
        tmpfile.close()
        config_module.CONFIG_PATH = tmpfile.name

        config = load_config()
        assert len(config.accounts) == 1
        acc = config.accounts[0]
        assert acc.label == "Legacy"
        assert acc.needs_reinput is True, "旧版明文配置应标记 needs_reinput"
        # 不应加载明文 key 到内存
        assert acc.api_key == ""
        assert acc.api_key_enc == ""
    finally:
        config_module.CONFIG_PATH = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "config.json"
        )
        if os.path.exists(tmpfile.name):
            os.unlink(tmpfile.name)


def test_load_config_with_encrypted_key():
    """load_config 从 api_key_enc 加载并解密。"""
    plain = "sk-loaded-key-12345"
    enc = PlainCredentialStore().encrypt(plain)
    tmpfile = tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json", encoding="utf-8")
    try:
        new_data = {
            "accounts": [
                {"label": "Enc", "api_key_enc": enc, "provider": "deepseek", "uid": "enc001"}
            ],
            "window": {},
            "settings": {"interval_sec": 60, "theme": "dark"},
        }
        tmpfile.write(json.dumps(new_data))
        tmpfile.close()
        config_module.CONFIG_PATH = tmpfile.name

        config = load_config()
        acc = config.accounts[0]
        assert acc.api_key == plain
        assert acc.api_key_enc == enc
        assert acc.needs_reinput is False
    finally:
        config_module.CONFIG_PATH = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "config.json"
        )
        if os.path.exists(tmpfile.name):
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
    acc = AccountConfig(label="Test", api_key="sk-test")
    assert acc.uid is not None
    assert len(acc.uid) == 8


def test_account_config_uid_preserved():
    acc = AccountConfig(label="Test", api_key="sk-test", uid="myuid123")
    assert acc.uid == "myuid123"


def test_settings_config_defaults():
    """SettingsConfig 默认值应包含新增字段。"""
    s = SettingsConfig()
    assert s.interval_sec == 60
    assert s.theme == "dark"
    assert s.proxy_target == "api.deepseek.com"
    assert s.log_level == "INFO"
    assert s.active_key_sources == []
    assert s.proxy_token_enc == ""


def test_update_api_key_method():
    """AccountConfig.update_api_key 应显式更新并加密。"""
    acc = AccountConfig(label="T", api_key="")
    acc.update_api_key("sk-new-key-xxxxx")
    assert acc.api_key == "sk-new-key-xxxxx"
    assert acc.api_key_enc
    assert acc.needs_reinput is False
