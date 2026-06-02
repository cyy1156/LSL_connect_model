"""根据 models.yaml 动态生成模型板块网格。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from lsl_connect.state import ServiceState
from lsl_connect.ui.event_bus import ModelResult
from lsl_connect.ui.theme import COLORS
from lsl_connect.ui.widgets.model_panel import ModelPanel
from models.registry import ModelSpec


class ModelGrid(ttk.Frame):
    def __init__(
        self,
        master,
        on_start: Callable[[str], None],
        on_stop: Callable[[str], None],
        on_start_all: Callable[[], None],
        on_stop_all: Callable[[], None],
        columns: int = 2,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._on_start = on_start
        self._on_stop = on_stop
        self._columns = columns
        self._panels: Dict[str, ModelPanel] = {}

        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(toolbar, text="模型监测", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="全部启动", command=on_start_all).pack(side=tk.RIGHT, padx=2)
        ttk.Button(toolbar, text="全部停止", command=on_stop_all).pack(side=tk.RIGHT, padx=2)

        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(
            canvas_frame,
            highlightthickness=0,
            bg=COLORS["bg"],
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self._canvas.yview)
        self._inner = ttk.Frame(self._canvas)

        self._inner.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._inner, anchor=tk.NW)
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self._canvas.bind_all("<MouseWheel>", _on_mousewheel)

    def build_from_specs(self, specs: Dict[str, ModelSpec]) -> None:
        for child in self._inner.winfo_children():
            child.destroy()
        self._panels.clear()

        names = sorted(specs.keys())
        for idx, name in enumerate(names):
            panel = ModelPanel(
                self._inner,
                specs[name],
                on_start=self._on_start,
                on_stop=self._on_stop,
            )
            row, col = divmod(idx, self._columns)
            panel.grid(row=row, column=col, padx=6, pady=6, sticky=tk.NSEW)
            self._panels[name] = panel

        for c in range(self._columns):
            self._inner.columnconfigure(c, weight=1)

    def update_all(
        self,
        service_state: ServiceState,
        running_models: List[str],
        latest: Dict[str, ModelResult],
        errors: Dict[str, str],
    ) -> None:
        running_set = set(running_models)
        for name, panel in self._panels.items():
            panel.update_panel(
                service_state=service_state,
                running=name in running_set,
                result=latest.get(name),
                error=errors.get(name),
            )
