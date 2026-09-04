"""YAML 配置加载器 —— 全项目唯一入口，带进程级缓存

各模块不再需要自行定位 config 路径（历史上 6 处各写一遍
`Path(__file__).parent.parent.parent / "config" / ...`）。
"""

import threading
from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).parent

_lock = threading.Lock()
_cache: dict[str, dict] = {}


def load_yaml(name: str) -> dict:
    """按文件名加载 config/ 下的 YAML，结果进程级缓存"""
    with _lock:
        if name not in _cache:
            path = _CONFIG_DIR / name
            with open(path, encoding="utf-8") as f:
                _cache[name] = yaml.safe_load(f)
        return _cache[name]


def get_agents_config() -> dict:
    """agents.yaml —— 各 agent 的 system prompt 配置"""
    return load_yaml("agents.yaml")


def get_rss_sources() -> list[dict]:
    """rss_sources.yaml 的 sources 列表"""
    return load_yaml("rss_sources.yaml")["sources"]


def clear_config_cache() -> None:
    """清空缓存（测试用）"""
    with _lock:
        _cache.clear()