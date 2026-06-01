"""
models — 可插拔脑电模型插件包。
第 10 课：代码内注册；第 11 课改从 models.yaml 加载。
"""

from models.demo_stats import DemoStatsModel

MODEL_REGISTRY = {
    "demo": DemoStatsModel,
}

__all__ = ["MODEL_REGISTRY", "DemoStatsModel"]


