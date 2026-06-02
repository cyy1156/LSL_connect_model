"""
models — 可插拔脑电模型插件包。
第 10 课：代码内注册；第 11 课：从 config/models.yaml 加载。
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from models.demo_stats import DemoStatsModel
from models.registry import ModelSpec, create_plugin, load_registry

_registry_cache: Optional[Dict[str, ModelSpec]] = None
_registry_msg: str = ""


def get_model_registry(reload: bool = False) -> Tuple[Dict[str, ModelSpec], str]:
    """获取模型登记表（启动时加载，quit 后重启可 reload）。"""
    global _registry_cache, _registry_msg
    if _registry_cache is None or reload:
        _registry_cache, _registry_msg = load_registry()
    return _registry_cache, _registry_msg


__all__ = [
    "DemoStatsModel",
    "ModelSpec",
    "create_plugin",
    "get_model_registry",
    "load_registry",
]