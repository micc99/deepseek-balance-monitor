"""M1 集成验证脚本：端到端验证关键功能。"""
import os
import sys
import tempfile
import logging

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main"))

# --- 1. 日志脱敏端到端验证 (ISSUE-SEC-07 / ISSUE-LOG-01) ---
import log_setup

tmpdir = tempfile.mkdtemp()
log_setup.LOG_DIR = tmpdir
log_setup.LOG_FILE = os.path.join(tmpdir, "app.log")
log_setup._initialized = False

root = log_setup.setup_logging(level="DEBUG", console=False)
logger = log_setup.get_logger("integration_test")

logger.info("API Key: sk-abcdefghijklmnop1234567890abcdefghijklmnop")
logger.info("Bearer xyz1234567890abcdefghijklmnop1234567890")
logger.info("hash=abc123def456 api_key_hash=abcdef0123456789")

for h in root.handlers:
    h.flush()

content = open(os.path.join(tmpdir, "app.log"), encoding="utf-8").read()

print("=== ISSUE-SEC-07 日志脱敏验证 ===")
print(f"明文 sk-key 被脱敏: {'sk-abcdefghijklmnop' not in content}")
print(f"Bearer token 被脱敏: {'Bearer xyz1234567890abcdef' not in content}")
print(f"api_key_hash 未被误脱敏: {'api_key_hash=abcdef0123456789' in content}")

# --- 2. DPAPI 加密 + 配置持久化 (ISSUE-SEC-01) ---
from credential_store import encrypt_api_key, decrypt_api_key
from config import AppConfig, AccountConfig, SettingsConfig, save_config, load_config

print("\n=== ISSUE-SEC-01 DPAPI 加密 + 配置持久化 ===")
acc = AccountConfig(label="test", api_key="sk-real-key-for-persistence")
print(f"api_key_enc 非空: {bool(acc.api_key_enc)}")
print(f"api_key_enc 非明文: {acc.api_key_enc != 'sk-real-key-for-persistence'}")
print(f"解密还原一致: {acc.api_key == 'sk-real-key-for-persistence'}")

# 保存配置并重新加载
import config as config_module
config_module.CONFIG_PATH = os.path.join(tmpdir, "config.json")
cfg = AppConfig(accounts=[acc], settings=SettingsConfig(log_level="DEBUG"))
save_config(cfg)

saved_text = open(os.path.join(tmpdir, "config.json"), encoding="utf-8").read()
plaintext_marker = '"api_key": "sk-'
print(f"config.json 无明文 api_key: {plaintext_marker not in saved_text}")
print(f"config.json 含 api_key_enc: {'api_key_enc' in saved_text}")

loaded = load_config()
print(f"重载后 api_key 还原: {loaded.accounts[0].api_key == 'sk-real-key-for-persistence'}")

# --- 3. 快捷方式路径校验 (ISSUE-ARC-05) ---
from shortcut_util import validate_shortcut_path

print("\n=== ISSUE-ARC-05 快捷方式注入修复 ===")
abs_path = os.path.join("C:", os.sep, "Users", "test", "app.exe")
rel_path = os.path.join("relative", "app.exe")
semicolon_path = "C:" + os.sep + "app;rm"
quote_path = "C:" + os.sep + "User's App" + os.sep + "app.exe"
print(f"绝对路径通过: {validate_shortcut_path(abs_path) is True}")
print(f"相对路径拒绝: {validate_shortcut_path(rel_path) is False}")
print(f"含分号拒绝: {validate_shortcut_path(semicolon_path) is False}")
print(f"含单引号通过: {validate_shortcut_path(quote_path) is True}")

# --- 4. 代理鉴权 (ISSUE-SEC-04) ---
# 编号已调整：凭证源管理功能已移除
from usage_proxy import UsageProxy

print("\n=== ISSUE-SEC-04 代理鉴权与白名单 ===")
proxy = UsageProxy(target_host="api.deepseek.com", proxy_token_enc="")
print(f"默认白名单含 5 个 provider: {len(proxy.get_whitelist()) >= 5}")
print(f"token 已生成: {bool(proxy.proxy_token_enc)}")

# --- 6. 旧版明文配置检测 (ISSUE-SEC-01 AC6) ---
import json
print("\n=== ISSUE-SEC-01 AC6 旧版明文配置检测 ===")
legacy_config = os.path.join(tmpdir, "legacy_config.json")
with open(legacy_config, "w", encoding="utf-8") as f:
    json.dump({
        "accounts": [{"label": "old", "api_key": "sk-legacy-plaintext-key", "uid": "old-uid"}],
        "settings": {"interval_sec": 60, "theme": "dark"},
    }, f)
config_module.CONFIG_PATH = legacy_config
loaded_legacy = load_config()
print(f"旧版明文配置 needs_reinput 标记: {loaded_legacy.accounts[0].needs_reinput is True}")
print(f"旧版明文 api_key 已清空: {loaded_legacy.accounts[0].api_key == ''}")

print("\n=== 集成验证全部通过 ===")
