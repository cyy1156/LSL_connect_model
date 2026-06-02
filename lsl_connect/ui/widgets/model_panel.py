"""单模型监测卡片。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from lsl_connect.state import ServiceState
from lsl_connect.ui.controllers.app_controller import AppController
from lsl_connect.ui.event_bus import ModelResult
from models.registry import ModelSpec


class ModelPanel(ttk.LabelFrame):
    def __init__(
        self,
        master,
        spec: ModelSpec,
        on_start: Callable[[str], None],
        on_stop: Callable[[str], None],
        **kwargs,
    ) -> None:
        title = spec.name
        if spec.description:
            title = f"{spec.name} — {spec.description}"
        padding = kwargs.pop("padding", 10)
        super().__init__(
            master,
            text=title,
            padding=padding,
            style="Card.TLabelframe",
            **kwargs,
        )

        self._spec = spec
        self._on_start = on_start
        self._on_stop = on_stop
        self._name = spec.name

        top = ttk.Frame(self, style="CardInner.TFrame")
        top.pack(fill=tk.X)

        self._status_var = tk.StringVar(value="○ 已停止")
        self._status_lbl = ttk.Label(
            top,
            textvariable=self._status_var,
            style="Stopped.TLabel",
            width=12,
        )
        self._status_lbl.pack(side=tk.LEFT)

        self._btn_start = ttk.Button(
            top, text="启动", width=8, command=lambda: self._on_start(self._name)
        )
        self._btn_start.pack(side=tk.LEFT, padx=2)
        self._btn_stop = ttk.Button(
            top, text="停止", width=8, command=lambda: self._on_stop(self._name)
        )
        self._btn_stop.pack(side=tk.LEFT, padx=2)

        ttk.Label(
            self,
            text=f"窗口 {spec.window_size}  |  步长 {spec.hop_size}",
            style="CardMeta.TLabel",
        ).pack(anchor=tk.W, pady=(6, 2))

        self._summary_var = tk.StringVar(value="—")
        ttk.Label(self, textvariable=self._summary_var, style="CardSummary.TLabel").pack(
            anchor=tk.W
        )

        self._fields_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self._fields_var, style="CardMeta.TLabel").pack(
            anchor=tk.W
        )

        self._time_var = tk.StringVar(value="更新: —")
        ttk.Label(self, textvariable=self._time_var, style="CardMeta.TLabel").pack(
            anchor=tk.W, pady=(2, 0)
        )

        self._error_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self._error_var, style="ErrorText.TLabel").pack(
            anchor=tk.W, pady=(4, 0)
        )

    @property
    def model_name(self) -> str:
        return self._name

    def update_panel(
        self,
        service_state: ServiceState,
        running: bool,
        result: Optional[ModelResult],
        error: Optional[str],
    ) -> None:
        can_run_model = service_state == ServiceState.RUNNING

        if running:
            self._status_var.set("● 运行中")
            self._status_lbl.configure(style="Running.TLabel")
        else:
            self._status_var.set("○ 已停止")
            self._status_lbl.configure(style="Stopped.TLabel")

        self._btn_start.state(
            ["!disabled"] if (can_run_model and not running) else ["disabled"]
        )
        self._btn_stop.state(["!disabled"] if running else ["disabled"])

        if error:
            self._error_var.set(error)
        else:
            self._error_var.set("")

        if result is not None:
            self._summary_var.set(result.summary)
            if result.fields:
                parts = [f"{k}: {v}" for k, v in result.fields.items()]
                self._fields_var.set("  |  ".join(parts[:6]))
            else:
                self._fields_var.set("")
            self._time_var.set(f"更新: {AppController.format_time(result.timestamp)}")
        elif not running:
            self._summary_var.set("—")
            self._fields_var.set("")
            self._time_var.set("更新: —")
