"""
录制质量评估：对比采集推送量与 CSV 写入量，估算丢包率。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class RecordingStopReport:
    """停录后的质量报告，供 UI 弹窗与 meta.json。"""

    samples_written: int = 0
    samples_pushed_during: int = 0
    estimated_gap_samples: int = 0
    missing_vs_lsl: int = 0
    drop_rate_pct: float = 0.0
    duration_sec: float = 0.0
    expected_by_duration: int = 0
    sample_rate_hz: int = 250
    path: Optional[str] = None
    severity: str = "ok"  # ok | warn | bad

    def to_dict(self) -> Dict[str, Any]:
        return {
            "samples_written": self.samples_written,
            "samples_pushed_during_recording": self.samples_pushed_during,
            "estimated_gap_samples": self.estimated_gap_samples,
            "missing_vs_lsl": self.missing_vs_lsl,
            "drop_rate_pct": round(self.drop_rate_pct, 3),
            "duration_sec": round(self.duration_sec, 2),
            "expected_by_duration": self.expected_by_duration,
            "sample_rate_hz": self.sample_rate_hz,
            "severity": self.severity,
        }

    def summary_message(self) -> str:
        lines = [
            f"CSV 已写入: {self.samples_written} 行",
            f"采集推送(录制时段): {self.samples_pushed_during} 样本",
            f"相对 LSL 缺口: {self.missing_vs_lsl} 样本",
            f"估算丢包率: {self.drop_rate_pct:.2f}%",
            f"时间戳缺口估计: {self.estimated_gap_samples} 样本",
            f"录制时长: {self.duration_sec:.1f} s（按采样率约需 {self.expected_by_duration} 行）",
        ]
        if self.path:
            lines.append(f"文件: {self.path}")
        return "\n".join(lines)

    def popup_title(self) -> str:
        if self.severity == "bad":
            return "录制停录 — 丢包较多"
        if self.severity == "warn":
            return "录制停录 — 有少量丢包"
        return "录制停录 — 质量正常"


def compute_recording_quality(
    *,
    samples_written: int,
    samples_pushed_baseline: int,
    samples_pushed_now: int,
    estimated_gap_samples: int,
    sample_rate_hz: int,
    started_at: Optional[float],
    stopped_at: Optional[float] = None,
    csv_path: Optional[str] = None,
    warn_drop_pct: float = 1.0,
    bad_drop_pct: float = 5.0,
) -> RecordingStopReport:
    """
    对比「录制时段内 Outlet 推送量」与「CSV 行数」。
    missing_vs_lsl = pushed_during - written（不含 gap 重复计数时取较大提示）
    """
    stopped_at = stopped_at or time.time()
    pushed_during = max(0, int(samples_pushed_now) - int(samples_pushed_baseline))
    written = max(0, int(samples_written))
    gaps = max(0, int(estimated_gap_samples))

    missing_lsl = max(0, pushed_during - written)
    drop_rate = (100.0 * missing_lsl / pushed_during) if pushed_during > 0 else 0.0

    duration = 0.0
    if started_at is not None:
        duration = max(0.0, stopped_at - started_at)
    fs = max(1, int(sample_rate_hz))
    expected = int(duration * fs)

    severity = "ok"
    if drop_rate >= bad_drop_pct or (expected > 0 and written < expected * 0.9):
        severity = "bad"
    elif drop_rate >= warn_drop_pct or gaps > fs * 2:
        severity = "warn"

    return RecordingStopReport(
        samples_written=written,
        samples_pushed_during=pushed_during,
        estimated_gap_samples=gaps,
        missing_vs_lsl=missing_lsl,
        drop_rate_pct=drop_rate,
        duration_sec=duration,
        expected_by_duration=expected,
        sample_rate_hz=fs,
        path=str(csv_path) if csv_path else None,
        severity=severity,
    )


def patch_meta_quality(csv_path: str | Path, quality: Dict[str, Any]) -> None:
    """在已有 .meta.json 中追加 quality 字段。"""
    meta_path = Path(csv_path).with_suffix(".meta.json")
    if not meta_path.is_file():
        return
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            payload = {}
        payload["quality"] = quality
        meta_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError):
        pass
