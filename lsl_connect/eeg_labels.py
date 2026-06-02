"""
EEG 通道名称解析与校验（顺序 = CH1…CHn = CSV 列顺序）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from lsl_connect.lsl_streams import DEFAULT_EEG_LABELS


def parse_eeg_channel_labels(
    lsl_sec: Dict[str, Any],
    channel_count: int,
    pick_fn,
) -> List[str]:
    """从 lsl 配置段解析通道标签。pick_fn 为 config_loader._pick。"""
    raw = pick_fn(
        lsl_sec,
        "eeg通道标签",
        "eeg_labels",
        "eeg_channel_labels",
        "通道名称",
    )
    if raw is None:
        return list(DEFAULT_EEG_LABELS[:channel_count])

    if isinstance(raw, str):
        text = raw.replace("，", ",")
        parts = [p.strip() for p in text.split(",") if p.strip()]
    elif isinstance(raw, list):
        parts = [str(p).strip() for p in raw if str(p).strip()]
    else:
        return list(DEFAULT_EEG_LABELS[:channel_count])

    return _normalize_label_count(parts, channel_count)


def _normalize_label_count(parts: List[str], channel_count: int) -> List[str]:
    if not parts:
        return list(DEFAULT_EEG_LABELS[:channel_count])
    if len(parts) < channel_count:
        tail = DEFAULT_EEG_LABELS[len(parts) : channel_count]
        parts = parts + list(tail)
    elif len(parts) > channel_count:
        parts = parts[:channel_count]
    return parts


def validate_eeg_channel_labels(
    labels: List[str],
    channel_count: int,
) -> Tuple[bool, str]:
    if len(labels) != channel_count:
        return False, f"需要 {channel_count} 个通道名，当前 {len(labels)} 个"
    seen: set[str] = set()
    for label in labels:
        name = label.strip()
        if not name:
            return False, "通道名不能为空"
        if "," in name or "，" in name:
            return False, f"通道名不能含逗号: {name!r}"
        if name in seen:
            return False, f"通道名重复: {name}"
        seen.add(name)
    return True, ""


def labels_from_text(text: str, channel_count: int) -> List[str]:
    parts = [p.strip() for p in text.replace("，", ",").split(",") if p.strip()]
    return _normalize_label_count(parts, channel_count)


def labels_to_display_text(labels: List[str]) -> str:
    return ", ".join(labels)


def format_eeg_labels_yaml_block(labels: List[str]) -> str:
    lines = ["  eeg通道标签:"]
    for lb in labels:
        lines.append(f"    - {lb}")
    return "\n".join(lines)
