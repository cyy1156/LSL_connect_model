"""顶栏服务状态。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict

from lsl_connect.state import ServiceState
from lsl_connect.ui.theme import COLORS, state_color


class StatusBar(ttk.Frame):
    def __init__(self, master, **kwargs) -> None:
        padding = kwargs.pop("padding", (12, 8))
        super().__init__(master, style="StatusBar.TFrame", padding=padding, **kwargs)

        self._state_var = tk.StringVar(value="IDLE")
        self._source_var = tk.StringVar(value="")
        self._detail_var = tk.StringVar(value="")

        self._dot = tk.Label(self, text="●", font=("Segoe UI", 14), bg=COLORS["card_bg"])
        self._dot.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Label(self, textvariable=self._state_var, style="StatusState.TLabel", width=10).pack(
            side=tk.LEFT
        )
        ttk.Label(self, textvariable=self._source_var, style="StatusState.TLabel", width=12).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        ttk.Label(self, textvariable=self._detail_var, style="StatusDetail.TLabel").pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

    def update_status(self, state: ServiceState, status: Dict[str, Any]) -> None:
        self._state_var.set(state.value)
        self._dot.configure(fg=state_color(state.value))

        source = status.get("serial_port", "—")
        gui = "GUI推流 ON" if status.get("gui_streaming_enabled") else "GUI推流 OFF"
        self._source_var.set(str(source))

        filt = "ON" if status.get("filter_enabled") else "OFF"
        if status.get("recording_active"):
            rec_n = status.get("recording_samples", 0)
            rec_path = status.get("recording_path") or "?"
            rec_name = str(rec_path).split("\\")[-1].split("/")[-1]
            rec_txt = f"REC {rec_name} ({rec_n})"
        else:
            rec_txt = "REC OFF"
        labels = status.get("eeg_channel_labels") or []
        ch_hint = " · ".join(labels[:4])
        if len(labels) > 4:
            ch_hint += " …"
        self._detail_var.set(
            f"{status.get('sample_rate_hz')} Hz  ·  "
            f"{status.get('channel_count')} ch  ·  "
            f"已推送 {status.get('samples_pushed', 0)}  ·  "
            f"滤波 {filt}  ·  {gui}  ·  {rec_txt}  ·  {ch_hint}"
        )
