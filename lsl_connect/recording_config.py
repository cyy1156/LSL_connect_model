"""
CSV 本地录制配置（FR-31）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@dataclass
class RecordingConfig:
    """对应 default.yaml 的「录制」段。"""

    auto_start: bool = False
    output_dir: str = "data/recordings"
    file_prefix: str = "eeg"
    include_accel: bool = False
    stop_when_acquisition_stops: bool = True
    flush_interval_sec: float = 2.0
    # LSL Inlet 缓冲上限（秒）；录制约 300s，落后过多时 liblsl 会丢最旧样本而非无限涨内存
    lsl_buffer_sec: int = 300


def resolve_output_dir(path_str: str) -> Path:
    p = Path(path_str.strip())
    if not p.is_absolute():
        p = project_root() / p
    return p


def make_recording_path(
    config: RecordingConfig,
    explicit: Optional[Path] = None,
) -> Path:
    if explicit is not None:
        path = Path(explicit)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    out_dir = resolve_output_dir(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return out_dir / f"{config.file_prefix}_{stamp}.csv"
