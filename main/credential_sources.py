"""凭证源显式授权读取（ISSUE-SEC-05）。

从 main.py 抽离的纯逻辑模块，无 GUI 依赖，便于单元测试。

功能：
- 仅从用户显式授权的凭证源路径读取 key 字段
- 路径安全校验（拒绝相对路径、含 .. 的路径）
- 凭证源读取仅用于"活跃账户标识"，不影响余额查询逻辑
"""
import json
import logging
import os

logger = logging.getLogger(__name__)


def load_authorized_active_keys(config) -> set[str]:
    """仅从用户显式授权的凭证源路径读取 key（ISSUE-SEC-05）。

    旧版本默认扫描 Desktop\\auth.json 等路径，存在用户无感知的风险。
    新版本仅读取 config.settings.active_key_sources 中记录的路径，
    每条路径独立校验存在性，不存在时跳过并告警。

    凭证源读取仅用于"活跃账户标识"，不影响余额查询逻辑。

    参数:
        config: AppConfig 对象，需含 settings.active_key_sources 列表

    返回:
        set[str]: 从授权凭证源中读取到的 key 集合（已去重）
    """
    keys: set[str] = set()
    for path in config.settings.active_key_sources:
        # 路径安全校验：拒绝相对路径与含 .. 的路径
        if not os.path.isabs(path) or ".." in path:
            logger.warning("凭证源路径被拒绝（非绝对路径或含 ..）：%s", path)
            continue
        if not os.path.exists(path):
            logger.warning("凭证源路径不存在，已跳过：%s", path)
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data.values() if isinstance(data, dict) else []:
                if isinstance(entry, dict) and "key" in entry:
                    keys.add(entry["key"])
            logger.info("已从凭证源加载 %d 个 key：%s", len(keys), path)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning("读取凭证源失败：%s，错误：%s", path, e)
            continue
    return keys
