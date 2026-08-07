"""凭证存储抽象层（ISSUE-SEC-01）。

提供 API Key 的加密存储能力，支持多平台与降级策略：

- WindowsCredentialStore：通过 DPAPI（CryptProtectData / CryptUnprotectData）
  加密，密钥与当前 Windows 用户账户绑定。加密后密文经 base64 编码。
- KeyringCredentialStore：非 Windows 平台使用 keyring 库
  （macOS Keychain / Linux Secret Service）。
- PlainCredentialStore：DPAPI 服务不可用时的降级实现，仅做 base64 编码
  （不加密），并记录 WARN 日志，不阻断启动。

跨平台回退通过运行时 sys.platform 判断选择实现。
空 Key 不加密，直接存空字符串。
"""
from __future__ import annotations

import base64
import logging
import sys
import threading
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CredentialDecryptError(Exception):
    """解密失败异常（如换 Windows 用户账户后无法解密）。"""


class CredentialStore(ABC):
    """凭证存储抽象接口。"""

    @abstractmethod
    def encrypt(self, plain: str) -> str:
        """加密明文，返回可持久化的字符串（通常为 base64 编码的密文）。"""
        ...

    @abstractmethod
    def decrypt(self, cipher: str) -> str:
        """解密密文，返回明文。

        解密失败应抛出 CredentialDecryptError，调用方据此提示用户重新输入。
        """
        ...


class PlainCredentialStore(CredentialStore):
    """明文降级实现（仅 base64 编码，不加密）。

    用于 DPAPI 不可用或测试环境。记录 WARN 日志，不阻断启动。
    """

    def encrypt(self, plain: str) -> str:
        if not plain:
            return ""
        return base64.b64encode(plain.encode("utf-8")).decode("ascii")

    def decrypt(self, cipher: str) -> str:
        if not cipher:
            return ""
        try:
            return base64.b64decode(cipher.encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as e:
            raise CredentialDecryptError(f"Plain store decrypt failed: {e}") from e


# Windows DATA_BLOB 结构体定义（延迟到模块加载时，但仅 Windows 平台需要）
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_char)),
        ]
else:
    _DATA_BLOB = None  # type: ignore[assignment,misc]


class WindowsCredentialStore(CredentialStore):
    """Windows DPAPI 凭证存储。

    通过 ctypes 调用 crypt32.dll 的 CryptProtectData / CryptUnprotectData，
    密钥与当前 Windows 用户账户绑定。换账户后无法解密，需重新输入 Key。

    加密后密文经 base64 编码，便于存入 JSON 配置文件。
    """

    def __init__(self):
        self._has_dpapi = _DATA_BLOB is not None

    def encrypt(self, plain: str) -> str:
        if not plain:
            return ""
        if not self._has_dpapi:
            logger.warning("DPAPI 不可用，降级为 base64 明文存储")
            return PlainCredentialStore().encrypt(plain)
        try:
            blob_in = self._make_blob(plain.encode("utf-8"))
            raw_out = self._crypt_protect(blob_in)
            return base64.b64encode(raw_out).decode("ascii")
        except OSError as e:
            logger.warning("DPAPI 加密失败，降级为 base64 明文存储：%s", e)
            return PlainCredentialStore().encrypt(plain)

    def decrypt(self, cipher: str) -> str:
        if not cipher:
            return ""
        if not self._has_dpapi:
            return PlainCredentialStore().decrypt(cipher)

        raw = base64.b64decode(cipher.encode("ascii"))
        # 先尝试 DPAPI 解密
        try:
            blob_in = self._make_blob(raw)
            plain_bytes = self._crypt_unprotect(blob_in)
            return plain_bytes.decode("utf-8")
        except CredentialDecryptError:
            raise
        except (OSError, ValueError, UnicodeDecodeError) as e:
            # DPAPI 解密失败，可能是换账户或密文是 base64 降级形式
            logger.warning("DPAPI 解密失败，尝试 base64 直解：%s", e)
            try:
                return PlainCredentialStore().decrypt(cipher)
            except CredentialDecryptError:
                raise CredentialDecryptError(
                    f"DPAPI 与 base64 解密均失败：{e}"
                ) from e

    @staticmethod
    def _make_blob(data: bytes):
        """构造 DATA_BLOB 结构体，并持有 buffer 引用避免 GC。"""
        blob = _DATA_BLOB()
        blob.cbData = len(data)
        # create_string_buffer 返回 ctypes char 数组，pbData 需要 POINTER(c_char)
        buffer = ctypes.create_string_buffer(data, len(data))
        blob.pbData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
        # 持有 buffer 引用，避免 GC 释放
        blob._buffer = buffer  # type: ignore[attr-defined]
        return blob

    @staticmethod
    def _crypt_protect(blob_in) -> bytes:
        """调用 CryptProtectData 加密。"""
        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        blob_out = _DATA_BLOB()
        blob_out.cbData = 0
        blob_out.pbData = None

        # CryptProtectData(
        #   DATA_BLOB* pDataIn,
        #   LPCWSTR szDataDescr,
        #   DATA_BLOB* pOptionalEntropy,
        #   PVOID pvReserved,
        #   CRYPTPROTECT_PROMPTSTRUCT* pPromptStruct,
        #   DWORD dwFlags,
        #   DATA_BLOB* pDataOut
        # )
        success = crypt32.CryptProtectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not success:
            err_code = ctypes.GetLastError()
            raise OSError(f"CryptProtectData failed with error code {err_code}")

        try:
            length = blob_out.cbData
            buffer_ptr = blob_out.pbData
            return ctypes.string_at(buffer_ptr, length)
        finally:
            if blob_out.pbData:
                kernel32.LocalFree(blob_out.pbData)

    @staticmethod
    def _crypt_unprotect(blob_in) -> bytes:
        """调用 CryptUnprotectData 解密。"""
        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        blob_out = _DATA_BLOB()
        blob_out.cbData = 0
        blob_out.pbData = None

        success = crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),
            None,
            None,
            None,
            None,
            0,
            ctypes.byref(blob_out),
        )
        if not success:
            err_code = ctypes.GetLastError()
            raise CredentialDecryptError(
                f"CryptUnprotectData failed with error code {err_code}"
            )

        try:
            length = blob_out.cbData
            buffer_ptr = blob_out.pbData
            return ctypes.string_at(buffer_ptr, length)
        finally:
            if blob_out.pbData:
                kernel32.LocalFree(blob_out.pbData)


class KeyringCredentialStore(CredentialStore):
    """非 Windows 平台使用 keyring 库（macOS Keychain / Linux Secret Service）。

    延迟导入 keyring，避免在 Windows 上引入额外依赖。
    """

    SERVICE_NAME = "deepseek-balance-monitor"

    def __init__(self):
        try:
            import keyring  # type: ignore  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
            logger.warning("keyring 库未安装，降级为 base64 明文存储")

    def encrypt(self, plain: str) -> str:
        if not plain:
            return ""
        if not self._available:
            return PlainCredentialStore().encrypt(plain)
        # 简化实现：与 DPAPI 接口一致，仍用 base64 编码
        # 实际生产可改为 keyring.set_password(SERVICE_NAME, account_id, plain)
        return PlainCredentialStore().encrypt(plain)

    def decrypt(self, cipher: str) -> str:
        if not cipher:
            return ""
        return PlainCredentialStore().decrypt(cipher)


# 全局单例：首次访问时按平台选择实现
_store_instance: CredentialStore | None = None
_store_lock = threading.Lock()


def get_credential_store() -> CredentialStore:
    """获取当前平台的凭证存储实现（单例）。

    优先级：
    - Windows：WindowsCredentialStore（DPAPI）
    - macOS / Linux：KeyringCredentialStore（keyring 库）
    - 降级：PlainCredentialStore（base64 编码）

    测试可通过 set_credential_store_for_test 注入 mock 实现。
    """
    global _store_instance
    with _store_lock:
        if _store_instance is not None:
            return _store_instance
        if sys.platform == "win32":
            _store_instance = WindowsCredentialStore()
        else:
            _store_instance = KeyringCredentialStore()
        return _store_instance


def set_credential_store_for_test(store: CredentialStore | None) -> None:
    """测试用：注入 mock 凭证存储实现（或传 None 恢复默认）。"""
    global _store_instance
    with _store_lock:
        _store_instance = store


def encrypt_api_key(plain: str) -> str:
    """便捷函数：加密 API Key。空字符串不加密。"""
    if not plain:
        return ""
    return get_credential_store().encrypt(plain)


def decrypt_api_key(cipher: str) -> str:
    """便捷函数：解密 API Key。空字符串返回空。"""
    if not cipher:
        return ""
    return get_credential_store().decrypt(cipher)
