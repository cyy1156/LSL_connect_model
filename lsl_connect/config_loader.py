"""
第 9 课：从 config/default.yaml 加载配置。
缺文件时回退 default.example.yaml，再回退代码默认值。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from lsl_connect.acquisition_work import AcquisitionConfig
from lsl_connect.board import BoardConfig
from lsl_connect.eeg_labels import format_eeg_labels_yaml_block, parse_eeg_channel_labels
from lsl_connect.lsl_streams import DEFAULT_EEG_LABELS, LslStreamConfig
from lsl_connect.preprocessing import PreprocessConfig
from lsl_connect.recording_config import RecordingConfig
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
    acq = _section(raw, "采集")
    lsl_sec = _section(raw, "lsl")
    gui_sec = _section(raw, "gui推流")
    if not gui_sec:
        gui_sec = _section(raw, "gui_streaming")
    rec_sec = _section(raw, "录制")
    if not rec_sec:
        rec_sec = _section(raw, "recording")

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

    buffer_size = int(_pick(acq, "单批上限", "buffer_size", "batch_max", default=25))
    quiet = _as_bool(_pick(acq, "后台安静", "quiet"), default=True)

    gui_streaming_enabled = _as_bool(
        _pick(gui_sec, "启用", "enabled", "gui_streaming_enabled"),
        default=False,
    )
    gui_stream_ip = str(
        _pick(gui_sec, "ip", "gui_stream_ip", default="225.1.1.1")
    ).strip()
    gui_stream_port = int(
        _pick(gui_sec, "端口", "port", "gui_stream_port", default=6677)
    )

    board = BoardConfig(
        serial_port=serial_port,
        use_synthetic=use_synthetic,
        cyton_eeg_count=channel_count,
        gui_streaming_enabled=gui_streaming_enabled,
        gui_stream_ip=gui_stream_ip,
        gui_stream_port=gui_stream_port,
    )
    preprocess = PreprocessConfig(
        sample_rate=sample_rate,
        filter_enabled=filter_enabled,
        bandpass_low_hz=bandpass_low,
        bandpass_high_hz=bandpass_high,
        notch_low_hz=notch_low,
        notch_high_hz=notch_high,
    )
    eeg_labels = parse_eeg_channel_labels(lsl_sec, channel_count, _pick)
    lsl = LslStreamConfig(
        sample_rate=sample_rate,
        channel_count=channel_count,
        use_synthetic=use_synthetic,
        eeg_labels=eeg_labels,
    )
    acquisition = AcquisitionConfig(
        buffer_size=buffer_size,
        quiet=quiet,
        stats_every_n_batches=0 if quiet else 20,
    )

    recording = RecordingConfig(
        auto_start=_as_bool(_pick(rec_sec, "启用", "enabled", "auto_start"), default=False),
        output_dir=str(
            _pick(rec_sec, "保存目录", "output_dir", default="data/recordings")
        ).strip(),
        file_prefix=str(_pick(rec_sec, "文件前缀", "file_prefix", default="eeg")).strip(),
        include_accel=_as_bool(
            _pick(rec_sec, "包含加速度", "include_accel"), default=False
        ),
        stop_when_acquisition_stops=_as_bool(
            _pick(rec_sec, "停止采集时自动停录", "stop_when_acquisition_stops"),
            default=True,
        ),
        flush_interval_sec=float(
            _pick(rec_sec, "flush间隔秒", "flush_interval_sec", default=2.0)
        ),
        lsl_buffer_sec=int(
            _pick(rec_sec, "lsl缓冲秒", "lsl_buffer_sec", default=300)
        ),
    )

    _ = _pick(lsl_sec, "eeg流名称", "eeg_stream_name")
    _ = _pick(lsl_sec, "加速度流名称", "accel_stream_name")
    return ServiceManagerConfig(
        board_config=board,
        lsl=lsl,
        preprocess=preprocess,
        acquisition=acquisition,
        recording=recording,
    ), msg


def save_default_config(
    config: ServiceManagerConfig,
    path: Optional[Path] = None,
) -> Tuple[bool, str]:
    """
    将当前 ServiceManagerConfig 写回 config/default.yaml。
    供 UI「保存配置」使用。
    """
    target = path or (config_dir() / "default.yaml")
    bc = config.board_config
    pp = config.preprocess
    acq = config.acquisition
    rec = config.recording
    lsl = config.lsl
    labels = list(lsl.eeg_labels or DEFAULT_EEG_LABELS[: lsl.channel_count])
    labels_yaml = format_eeg_labels_yaml_block(labels)

    content = f"""# =============================================================================
# 采集服务默认配置 — 可由控制台 UI「保存配置」更新
# =============================================================================

串口: {bc.serial_port}
使用合成板: {'true' if bc.use_synthetic else 'false'}          # true：无硬件测试
采样率: {pp.sample_rate}
通道数: {bc.cyton_eeg_count}

滤波:
  启用: {'true' if pp.filter_enabled else 'false'}
  带通低频_hz: {pp.bandpass_low_hz}
  带通高频_hz: {pp.bandpass_high_hz}
  陷波低频_hz: {pp.notch_low_hz}
  陷波高频_hz: {pp.notch_high_hz}

采集:
  单批上限: {acq.buffer_size}
  后台安静: {'true' if acq.quiet else 'false'}

lsl:
  eeg流名称: OpenBCI_EEG
  加速度流名称: OpenBCI_Accel
  # 顺序 = CH1…CH{len(labels)} 数据列（与 CSV 表头一致）
{labels_yaml}

gui推流:
  启用: {'true' if bc.gui_streaming_enabled else 'false'}
  ip: {bc.gui_stream_ip}
  端口: {bc.gui_stream_port}

录制:
  启用: {'true' if rec.auto_start else 'false'}
  保存目录: {rec.output_dir}
  文件前缀: {rec.file_prefix}
  包含加速度: {'true' if rec.include_accel else 'false'}
  停止采集时自动停录: {'true' if rec.stop_when_acquisition_stops else 'false'}
  flush间隔秒: {rec.flush_interval_sec}
  lsl缓冲秒: {rec.lsl_buffer_sec}
"""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return True, f"已保存到 {target.name}"
    except OSError as exc:
        return False, f"保存失败: {exc}"


def resolve_models_config_path(
    explicit: Optional[Path] = None,
) -> Tuple[Optional[Path], str]:
    """
    查找 models.yaml。
    优先级: 显式路径 > models.yaml > models.example.yaml
    """
    if explicit is not None:
        p = Path(explicit)
        if p.is_file():
            return p, f"使用指定模型配置: {p}"
        return None, f"指定模型配置不存在: {p}"

    models_yaml = config_dir() / "models.yaml"
    example_yaml = config_dir() / "models.example.yaml"

    if models_yaml.is_file():
        return models_yaml, f"已加载 {models_yaml.name}"
    if example_yaml.is_file():
        return example_yaml, f"未找到 models.yaml，回退 {example_yaml.name}"
    return None, "未找到 models.yaml / models.example.yaml"


# 兼容旧拼写
resolve_models_condig_path = resolve_models_config_path


def load_models_yaml_dict(path: Optional[Path] = None) -> Tuple[Dict[str, Any], str]:
    """读取 models YAML 为字典；不存在则返回空字典。"""
    from models.registry import _load_models_yaml_dict

    return _load_models_yaml_dict(path)
