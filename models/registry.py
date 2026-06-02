"""
第 11 课：从 config/models.yaml 加载模型登记表。
支持「类插件（类名）」与「函数插件（入口）」两种方式。
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import numpy as np
import yaml

from models.base import ModelPlugin


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _config_dir() -> Path:
    return _project_root() / "config"


def _load_models_yaml_dict(
    path: Optional[Path] = None,
) -> tuple[Dict[str, Any], str]:
    """
    读取 models YAML（放在 registry 内，避免与 config_loader 循环导入）。
    优先级: 显式路径 > models.yaml > models.example.yaml
    """
    if path is not None:
        p = Path(path)
        if p.is_file():
            cfg_path, msg = p, f"使用指定模型配置: {p}"
        else:
            return {}, f"指定模型配置不存在: {p}"
    else:
        models_yaml = _config_dir() / "models.yaml"
        example_yaml = _config_dir() / "models.example.yaml"
        if models_yaml.is_file():
            cfg_path, msg = models_yaml, f"已加载 {models_yaml.name}"
        elif example_yaml.is_file():
            cfg_path, msg = example_yaml, f"未找到 models.yaml，回退 {example_yaml.name}"
        else:
            return {}, "未找到 models.yaml / models.example.yaml"

    with cfg_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return {}, f"{msg}（内容为空或格式错误）"
    return data, msg


@dataclass
class ModelSpec:
    """一条模型登记记录（来自 models.yaml 顶层键）。"""

    name: str
    description: str
    window_size: int
    hop_size: int
    module: str
    class_name: Optional[str] = None
    entry: Optional[str] = None
    weights_path: Optional[str] = None
    input_format: str = "channels_samples"


def _pick(section: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in section:
            return section[k]
    return default


def _as_int(val: Any, default: int) -> int:
    if val is None:
        return default
    return int(val)


class FunctionModelPlugin(ModelPlugin):
    """把 YAML 里「入口: predict」这类函数包装成 ModelPlugin。"""

    def __init__(
        self,
        spec: ModelSpec,
        predict_fn: Callable[[np.ndarray], Any],
        load_fn: Optional[Callable[[], None]] = None,
    ) -> None:
        self.name = spec.name
        self.window_size = spec.window_size
        self.hop_size = spec.hop_size
        self._predict_fn = predict_fn
        self._load_fn = load_fn
        self.weights_path = spec.weights_path
        self.input_format = spec.input_format

    def load(self) -> None:
        if self._load_fn is not None:
            self._load_fn()

    def predict(self, data: np.ndarray) -> Any:
        if self.input_format == "channels_last":
            data = np.asarray(data).T
        return self._predict_fn(data)


def parse_models_yaml(raw: Dict[str, Any]) -> Dict[str, ModelSpec]:
    """把 YAML 顶层字典解析为 name -> ModelSpec。"""
    registry: Dict[str, ModelSpec] = {}

    for name, section in raw.items():
        if not isinstance(section, dict):
            continue

        module = str(_pick(section, "模块", "module", default="")).strip()
        if not module:
            continue

        window_size = _as_int(
            _pick(section, "窗口采样点数", "window_size"),
            default=250,
        )
        hop_default = max(1, window_size // 2)
        hop_size = _as_int(
            _pick(section, "步长采样点数", "hop_size"),
            default=hop_default,
        )

        spec = ModelSpec(
            name=str(name).strip(),
            description=str(_pick(section, "说明", "description", default="")).strip(),
            window_size=window_size,
            hop_size=hop_size,
            module=module,
            class_name=_pick(section, "类名", "class_name"),
            entry=_pick(section, "入口", "entry"),
            weights_path=_pick(section, "权重文件", "weights_path"),
            input_format=str(
                _pick(section, "输入格式", "input_format", default="channels_samples")
            ).strip(),
        )
        registry[spec.name] = spec

    return registry


def load_registry(
    path: Optional[Path] = None,
) -> tuple[Dict[str, ModelSpec], str]:
    """读取 models.yaml 并解析。返回 (登记表, 说明文字)。"""
    raw, msg = _load_models_yaml_dict(path)
    registry = parse_models_yaml(raw)
    if not registry:
        return {}, f"{msg}（未解析到任何模型条目）"
    return registry, msg


def _resolve_weights_path(spec: ModelSpec) -> Optional[Path]:
    if not spec.weights_path:
        return None
    p = Path(spec.weights_path)
    if p.is_file():
        return p
    p2 = _project_root() / spec.weights_path
    if p2.is_file():
        return p2
    return None


def _apply_spec_to_plugin(plugin: ModelPlugin, spec: ModelSpec) -> ModelPlugin:
    """用 YAML 覆盖窗口/步长/显示名等（操作员改 yaml 即生效）。"""
    plugin.name = spec.name
    plugin.window_size = spec.window_size
    plugin.hop_size = spec.hop_size

    weights = _resolve_weights_path(spec)
    if weights is not None:
        setattr(plugin, "weights_path", str(weights))

    if hasattr(plugin, "input_format"):
        plugin.input_format = spec.input_format

    return plugin


def create_plugin(spec: ModelSpec) -> ModelPlugin:
    """按 ModelSpec 动态 import 并构造可运行的 ModelPlugin。"""
    mod = import_module(spec.module)

    if spec.class_name:
        cls = getattr(mod, str(spec.class_name))
        plugin = cls()
        return _apply_spec_to_plugin(plugin, spec)

    if spec.entry:
        fn = getattr(mod, str(spec.entry))
        load_fn = getattr(mod, "load", None)
        return FunctionModelPlugin(spec, fn, load_fn)

    raise ValueError(
        f"模型 {spec.name!r} 缺少「类名」或「入口」，请检查 models.yaml"
    )
