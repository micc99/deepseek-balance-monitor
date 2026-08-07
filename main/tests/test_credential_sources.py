"""ISSUE-SEC-05：凭证源显式授权单元测试。

测试覆盖：
- load_authorized_active_keys 仅从授权路径读取
- 路径安全校验（拒绝相对路径、含 .. 的路径）
- 路径不存在时跳过并告警
- 凭证源文件格式解析（dict 含 key 字段）
- 默认不读取任何第三方凭证文件
- SettingsConfig.active_key_sources 字段
"""
import json
import logging
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import AppConfig, SettingsConfig, AccountConfig
from credential_sources import load_authorized_active_keys as _load_authorized_active_keys


def _make_config(sources: list[str]) -> AppConfig:
    """构造含 active_key_sources 的配置。"""
    return AppConfig(
        accounts=[],
        settings=SettingsConfig(active_key_sources=list(sources)),
    )


def _write_cred_file(path: str, data: dict):
    """写入凭证源 JSON 文件。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


class TestLoadAuthorizedActiveKeys:
    """_load_authorized_active_keys 函数测试。"""

    def test_empty_sources_returns_empty_set(self):
        """ISSUE-SEC-05 AC1：默认不读取任何第三方凭证文件。"""
        config = _make_config([])
        keys = _load_authorized_active_keys(config)
        assert keys == set()

    def test_loads_keys_from_authorized_path(self, tmp_path):
        """应从授权路径读取 key 字段。"""
        cred_file = tmp_path / "auth.json"
        _write_cred_file(str(cred_file), {
            "account1": {"key": "sk-key-from-source-1"},
            "account2": {"key": "sk-key-from-source-2"},
        })

        config = _make_config([str(cred_file)])
        keys = _load_authorized_active_keys(config)
        assert "sk-key-from-source-1" in keys
        assert "sk-key-from-source-2" in keys
        assert len(keys) == 2

    def test_relative_path_rejected(self, tmp_path, caplog):
        """相对路径应被拒绝。"""
        config = _make_config(["relative/path/auth.json"])
        with caplog.at_level(logging.WARNING):
            keys = _load_authorized_active_keys(config)
        assert keys == set()
        assert any("非绝对路径" in r.getMessage() or ".." in r.getMessage() for r in caplog.records)

    def test_path_with_dotdot_rejected(self, caplog):
        """含 .. 的路径应被拒绝。"""
        if sys.platform == "win32":
            path = "C:\\app\\..\\secret.json"
        else:
            path = "/app/../secret.json"
        config = _make_config([path])
        with caplog.at_level(logging.WARNING):
            keys = _load_authorized_active_keys(config)
        assert keys == set()

    def test_nonexistent_path_skipped(self, caplog):
        """ISSUE-SEC-05 AC4：路径不存在时跳过并告警。"""
        if sys.platform == "win32":
            path = "C:\\nonexistent\\path\\auth.json"
        else:
            path = "/nonexistent/path/auth.json"
        config = _make_config([path])
        with caplog.at_level(logging.WARNING):
            keys = _load_authorized_active_keys(config)
        assert keys == set()
        assert any("不存在" in r.getMessage() for r in caplog.records)

    def test_invalid_json_skipped(self, tmp_path, caplog):
        """JSON 格式错误时应跳过并告警。"""
        cred_file = tmp_path / "bad.json"
        cred_file.write_text("!!!not valid json!!!", encoding="utf-8")
        config = _make_config([str(cred_file)])
        with caplog.at_level(logging.WARNING):
            keys = _load_authorized_active_keys(config)
        assert keys == set()

    def test_multiple_sources_merged(self, tmp_path):
        """多个授权路径的 key 应合并。"""
        file1 = tmp_path / "auth1.json"
        file2 = tmp_path / "auth2.json"
        _write_cred_file(str(file1), {"a": {"key": "sk-key-1"}})
        _write_cred_file(str(file2), {"b": {"key": "sk-key-2"}, "c": {"key": "sk-key-3"}})

        config = _make_config([str(file1), str(file2)])
        keys = _load_authorized_active_keys(config)
        assert keys == {"sk-key-1", "sk-key-2", "sk-key-3"}

    def test_duplicate_keys_deduplicated(self, tmp_path):
        """相同 key 应去重。"""
        file1 = tmp_path / "auth1.json"
        file2 = tmp_path / "auth2.json"
        _write_cred_file(str(file1), {"a": {"key": "sk-dup-key"}})
        _write_cred_file(str(file2), {"b": {"key": "sk-dup-key"}})

        config = _make_config([str(file1), str(file2)])
        keys = _load_authorized_active_keys(config)
        assert keys == {"sk-dup-key"}

    def test_entries_without_key_ignored(self, tmp_path):
        """无 key 字段的条目应被忽略。"""
        cred_file = tmp_path / "auth.json"
        _write_cred_file(str(cred_file), {
            "with_key": {"key": "sk-has-key"},
            "without_key": {"other_field": "value"},
            "not_dict": "string-value",
        })
        config = _make_config([str(cred_file)])
        keys = _load_authorized_active_keys(config)
        assert keys == {"sk-has-key"}

    def test_non_dict_top_level_ignored(self, tmp_path):
        """顶层非 dict 结构应返回空集。"""
        cred_file = tmp_path / "auth.json"
        cred_file.write_text(json.dumps(["list", "not", "dict"]), encoding="utf-8")
        config = _make_config([str(cred_file)])
        keys = _load_authorized_active_keys(config)
        assert keys == set()

    def test_mixed_valid_invalid_sources(self, tmp_path, caplog):
        """混合有效与无效路径：有效路径仍应被读取。"""
        valid_file = tmp_path / "valid.json"
        _write_cred_file(str(valid_file), {"a": {"key": "sk-valid-key"}})

        if sys.platform == "win32":
            invalid_path = "C:\\nonexistent\\bad.json"
        else:
            invalid_path = "/nonexistent/bad.json"

        config = _make_config([str(valid_file), invalid_path])
        with caplog.at_level(logging.WARNING):
            keys = _load_authorized_active_keys(config)
        assert "sk-valid-key" in keys


class TestSettingsConfigActiveKeySources:
    """SettingsConfig.active_key_sources 字段测试。"""

    def test_default_empty_list(self):
        """默认 active_key_sources 应为空列表。"""
        s = SettingsConfig()
        assert s.active_key_sources == []

    def test_persists_through_save_load(self, tmp_path):
        """active_key_sources 应能通过 save_config / load_config 持久化。"""
        import config as config_module
        from config import save_config, load_config
        from credential_store import PlainCredentialStore, set_credential_store_for_test

        set_credential_store_for_test(PlainCredentialStore())
        try:
            cfg_path = tmp_path / "config.json"
            config_module.CONFIG_PATH = str(cfg_path)
            config = AppConfig(
                accounts=[],
                settings=SettingsConfig(
                    active_key_sources=["C:\\path1.json", "C:\\path2.json"],
                ),
            )
            save_config(config)

            loaded = load_config()
            assert loaded.settings.active_key_sources == ["C:\\path1.json", "C:\\path2.json"]
        finally:
            set_credential_store_for_test(None)
            config_module.CONFIG_PATH = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "config.json"
            )

    def test_list_mutation_does_not_affect_config(self):
        """传入 list 应被复制，外部修改不影响配置。"""
        external = ["path1.json"]
        s = SettingsConfig(active_key_sources=external)
        external.append("path2.json")
        assert s.active_key_sources == ["path1.json"]
