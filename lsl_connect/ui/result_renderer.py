"""
将 ModelPlugin.predict 返回值格式化为 ModelResult。
"""

from __future__ import annotations

import time
from typing import Any

from lsl_connect.ui.event_bus import ModelResult


def render_model_result(model_name: str, raw: Any) -> ModelResult:
    """按统一规则把 predict 输出转为 UI 可显示结构。"""
    ts = time.time()
    summary = ""
    fields: dict[str, str] = {}

    if isinstance(raw, dict):
        if "mean_uv" in raw and "std_uv" in raw:
            mean_uv = raw.get("mean_uv")
            std_uv = raw.get("std_uv")
            summary = f"mean={float(mean_uv):.2f} uV"
            fields["std_uv"] = f"{float(std_uv):.2f} uV"
            for k, v in raw.items():
                if k not in ("mean_uv", "std_uv"):
                    fields[k] = _fmt_value(v)
        elif "label" in raw and "score" in raw:
            label = raw.get("label")
            score = raw.get("score")
            summary = f"{label} ({float(score):.2f})"
            for k, v in raw.items():
                fields[k] = _fmt_value(v)
        else:
            keys = list(raw.keys())
            if keys:
                first = keys[0]
                summary = f"{first}={_fmt_value(raw[first])}"
            else:
                summary = "OK"
            for k, v in raw.items():
                fields[k] = _fmt_value(v)
    else:
        summary = str(raw)

    return ModelResult(
        model_name=model_name,
        timestamp=ts,
        raw=raw,
        summary=summary,
        fields=fields,
    )


def _fmt_value(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)
