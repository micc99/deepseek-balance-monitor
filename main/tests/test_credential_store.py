"""credential_store 模块单元测试（ISSUE-SEC-01）。

测试覆盖：
- PlainCredentialStore：base64 编码/解码、空值、解密失败
- WindowsCredentialStore：DPAPI 加密/解密（Windows 平台）、降级策略
- KeyringCredentialStore：keyring 库不可用时降级
- 全局单例：get_credential_store / set_credential_store_for_test
- 便捷函数：encrypt_api_key / decrypt_api_key
- CredentialDecryptError 异常
"""
import base64
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from credential_store import (
    CredentialStore,
    CredentialDecryptError,
    PlainCredentialStore,
    WindowsCredentialStore,
    KeyringCredentialStore,
    get_credential_store,
    set_credential_store_for_test,
    encrypt_api_key,
    decrypt_api_key,
)


class TestPlainCredentialStore:
    """PlainCredentialStore（base64 编码，不加密）。"""

    def test_encrypt_returns_base64(self):
        """加密后应为 base64 字符串，可解码还原。"""
        store = PlainCredentialStore()
        plain = "sk-test-key-12345"
        cipher = store.encrypt(plain)
        assert cipher != plain
        assert base64.b64decode(cipher.encode("ascii")).decode("utf-8") == plain

    def test_decrypt_returns_plaintext(self):
        """解密应还原明文。"""
        store = PlainCredentialStore()
        plain = "sk-original-key-abc"
        cipher = store.encrypt(plain)
        assert store.decrypt(cipher) == plain

    def test_encrypt_empty_returns_empty(self):
        """空 Key 不加密，返回空字符串。"""
        store = PlainCredentialStore()
        assert store.encrypt("") == ""

    def test_decrypt_empty_returns_empty(self):
        """空密文返回空字符串。"""
        store = PlainCredentialStore()
        assert store.decrypt("") == ""

    def test_decrypt_invalid_raises_error(self):
        """无效密文应抛出 CredentialDecryptError。"""
        store = PlainCredentialStore()
        with pytest.raises(CredentialDecryptError):
            store.decrypt("!!!invalid-base64!!!")

    def test_roundtrip_unicode(self):
        """Unicode 字符串加密解密往返。"""
        store = PlainCredentialStore()
        plain = "sk-测试-key-🔑"
        cipher = store.encrypt(plain)
        assert store.decrypt(cipher) == plain


class TestWindowsCredentialStore:
    """WindowsCredentialStore（DPAPI 加密）。

    在 Windows 平台使用真实 DPAPI，非 Windows 平台降级为 base64。
    """

    @pytest.fixture
    def store(self):
        return WindowsCredentialStore()

    def test_encrypt_decrypt_roundtrip(self, store):
        """加密解密往返应还原明文。"""
        plain = "sk-dpapi-test-key-12345"
        cipher = store.encrypt(plain)
        assert cipher, "密文不应为空"
        assert cipher != plain, "密文不应等于明文"
        assert store.decrypt(cipher) == plain

    def test_encrypt_empty(self, store):
        """空 Key 不加密。"""
        assert store.encrypt("") == ""

    def test_decrypt_empty(self, store):
        """空密文返回空字符串。"""
        assert store.decrypt("") == ""

    def test_decrypt_invalid_cipher_raises(self, store):
        """无效密文应抛出 CredentialDecryptError 或包含错误信息。"""
        # 完全无效的密文
        with pytest.raises((CredentialDecryptError, Exception)):
            store.decrypt("!!!not-valid-base64-or-dpapi!!!")

    def test_encrypt_then_decrypt_multiple_keys(self, store):
        """多个不同 Key 加密解密互不干扰。"""
        keys = [f"sk-key-{i:03d}-abcdefg" for i in range(5)]
        pairs = [(k, store.encrypt(k)) for k in keys]
        for plain, cipher in pairs:
            assert store.decrypt(cipher) == plain


class TestKeyringCredentialStore:
    """KeyringCredentialStore（非 Windows 平台）。"""

    def test_encrypt_decrypt_fallback_to_plain(self):
        """keyring 不可用时降级为 PlainCredentialStore。"""
        store = KeyringCredentialStore()
        plain = "sk-keyring-test-key"
        cipher = store.encrypt(plain)
        # 即使 keyring 可用，当前实现也降级为 base64
        assert store.decrypt(cipher) == plain

    def test_encrypt_empty(self):
        store = KeyringCredentialStore()
        assert store.encrypt("") == ""


class TestGlobalStore:
    """全局单例与便捷函数。"""

    def setup_method(self):
        """每个测试前清理全局单例。"""
        set_credential_store_for_test(None)

    def teardown_method(self):
        """每个测试后清理全局单例。"""
        set_credential_store_for_test(None)

    def test_get_credential_store_returns_singleton(self):
        """get_credential_store 应返回单例。"""
        s1 = get_credential_store()
        s2 = get_credential_store()
        assert s1 is s2

    def test_set_credential_store_for_test_injects_mock(self):
        """set_credential_store_for_test 应注入自定义实现。"""
        mock_store = PlainCredentialStore()
        set_credential_store_for_test(mock_store)
        assert get_credential_store() is mock_store

    def test_set_credential_store_for_test_none_resets(self):
        """传 None 应恢复默认实现。"""
        set_credential_store_for_test(PlainCredentialStore())
        set_credential_store_for_test(None)
        s = get_credential_store()
        # 应该是默认实现（WindowsCredentialStore on win32, KeyringCredentialStore otherwise）
        assert s is not None

    def test_encrypt_api_key_convenience(self):
        """encrypt_api_key 便捷函数应调用全局 store。"""
        set_credential_store_for_test(PlainCredentialStore())
        plain = "sk-convenience-test"
        cipher = encrypt_api_key(plain)
        assert cipher
        assert cipher != plain

    def test_decrypt_api_key_convenience(self):
        """decrypt_api_key 便捷函数应调用全局 store。"""
        set_credential_store_for_test(PlainCredentialStore())
        plain = "sk-convenience-decrypt"
        cipher = encrypt_api_key(plain)
        assert decrypt_api_key(cipher) == plain

    def test_encrypt_api_key_empty(self):
        """空 Key 不加密。"""
        set_credential_store_for_test(PlainCredentialStore())
        assert encrypt_api_key("") == ""

    def test_decrypt_api_key_empty(self):
        """空密文返回空。"""
        set_credential_store_for_test(PlainCredentialStore())
        assert decrypt_api_key("") == ""
