"""
第 9 课：从 config/default.yaml 加载配置。
缺文件时回退 default.example.yaml，再回退代码默认值。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

from lsl_connect.acquisition_work import  AcquisitionConfig
from lsl_connect.board import  BoardConfig
from lsl_connect.lsl_streams import LslStreamConfig
from lsl_connect.preprocessing import PreprocessConfig
from lsl_connect.service_manager import ServiceManagerConfig

def project_root() -> Path:
    """项目根目录（lsl_connect 的上一级）。"""
    return Path(__file__).parent.parent

def config_dir() -> Path:
    return project_root() / "config"

def resolve_config_path(explicit: Optional[Path] = None) -> Tuple[Optional[Path],str]:
    """
       查找配置文件。返回 (路径或 None, 说明文字)。
       优先级: 显式路径 > default.yaml > default.example.yaml
    """
    if explicit is not None:
        p =Path(explicit)
        if p.is_file():
            return p, f"使用指定配置；{p}"
        return None,f"指定配置不存在：{p}"

    default_yaml = config_dir() / "default.yaml"
    example_yaml = config_dir() / "default.example.yaml"

    if default_yaml.is_file():
        return default_yaml,f"已加载 {default_yaml.name}"
    if example_yaml.is_file():
        return example_yaml,f"未找到 default.yaml，回退 {example_yaml.name}"
    return None, "未找到 YAML，使用代码内置默认值"

def load_yaml_dict(path:Optional[Path]=None) ->Tuple[ Dict[str, Any],str]:
    """读取 YAML 为字典；文件不存在则返回空字典。"""
    cfg_path,msg = resolve_config_path(path)
    if cfg_path is None:
        return {},msg

    with cfg_path.open("r",encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data,dict):
        return {},f"{msg}（内容为空或格式错误，使用默认值）"
    return data,msg

def _section(data:Dict[str,Any],key:str) -> Dict[str, Any]:
    """取子字典，不是 dict 则返回 {}。"""
    val =data.get(key)
    return val if isinstance(val,dict) else {}

def _pick(data:Dict[str,Any],*keys:str,default:Any =None) -> Any:
    """按多个候选键取值（支持中英文键名）。"""
    for k in keys:
        if k in data:
            return data[k]
    return default

def _as_bool(val:Any,default: bool=False) -> bool:
    if val is None:
        return default
    if isinstance(val,bool):
        return val
    if isinstance(val,(int,float)):
        return bool(val)
    s=str(val).strip().lower()
    return s in("1", "true", "yes", "on", "是", "启用")

def build_service_manager_config(
    path:Optional[Path] = None,
) -> Tuple[ServiceManagerConfig,str]:
    """
      从 YAML 构建 ServiceManagerConfig。
      返回 (配置对象, 加载说明)。
    """
    raw, msg = load_yaml_dict(path)
    filt = _section(raw, "滤波")
    acq = _section(raw,"采集")
    lsl_sec=_section(raw,"lsl")

    use_synthetic =_as_bool(
        _pick(raw,"使用合成板","use_synthetic"),
        default=False,
    )
    serial_port=str(_pick(raw,"串口","serial_port",default="COM10")).strip()
    sample_rate =int(_pick(raw,"采样率","sample_rate",default=250))
    channel_count=int(_pick(raw,"通道数","channel_count",default=8))

    filter_enabled = _as_bool(
        _pick(filt,"启用","enabled","filter_enabled"),
        default=True,
    )

    bandpass_low = float(_pick(filt, "带通低频_hz", "bandpass_low_hz", default=0.5))
    bandpass_high = float(_pick(filt, "带通高频_hz", "bandpass_high_hz", default=45.0))
    notch_low = float(_pick(filt, "陷波低频_hz", "notch_low_hz", default=49.0))
    notch_high = float(_pick(filt, "陷波高频_hz", "notch_high_hz", default=51.0))

    buffer_size =int(_pick(acq,"单批上限","buffer_size","batch_max",default=25))
    quiet =_as_bool(_pick(acq,"后台安静","quiet"),default=True)

    board = BoardConfig(
        serial_port=serial_port,
        use_synthetic=use_synthetic,
        cyton_eeg_count=channel_count,
    )
    preprocess = PreprocessConfig(
        sample_rate=sample_rate,
        filter_enabled=filter_enabled,
        bandpass_low_hz=bandpass_low,
        bandpass_high_hz=bandpass_high,
        notch_low_hz=notch_low,
        notch_high_hz=notch_high,
    )
    lsl = LslStreamConfig(
        sample_rate=sample_rate,
        channel_count=channel_count,
        use_synthetic=use_synthetic,
    )
    acquisition = AcquisitionConfig(
        buffer_size=buffer_size,
        quiet=quiet,
        stats_every_n_batches=0 if quiet else 20,
    )
    # lsl 流名暂存入说明（第 9 课 create_outlets 仍用代码常量）
    _ = _pick(lsl_sec, "eeg流名称", "eeg_stream_name")
    _ = _pick(lsl_sec, "加速度流名称", "accel_stream_name")
    return ServiceManagerConfig(
        board_config=board,
        lsl=lsl,
        preprocess=preprocess,
        acquisition=acquisition,
    ), msg


