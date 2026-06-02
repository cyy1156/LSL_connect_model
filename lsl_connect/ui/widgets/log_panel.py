"""系统日志面板。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List

from lsl_connect.ui.theme import COLORS
from lsl_connect.ui.controllers.app_controller import AppController
from lsl_connect.ui.event_bus import LogEntry


class LogPanel(ttk.LabelFrame):
    def __init__(self, master, height: int = 10, **kwargs) -> None:
        padding = kwargs.pop("padding", 8)
        super().__init__(master, text="系统日志", padding=padding, style="Card.TLabelframe", **kwargs)

        self._text = tk.Text(
            self,
            height=height,
            wrap=tk.WORD,
            state=tk.DISABLED,
            font=("Consolas", 9),
            bg=COLORS["card_bg"],
            relief=tk.FLAT,
            padx=6,
            pady=4,
        )
        scroll = ttk.Scrollbar(self, command=self._text.yview)
        self._text.configure(yscrollcommand=scroll.set)

        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._text.tag_configure("ERROR", foreground="red")
        self._text.tag_configure("WARN", foreground="#b8860b")
        self._text.tag_configure("INFO", foreground="black")

    def append_logs(self, entries: List[LogEntry]) -> None:
        if not entries:
            return
        self._text.configure(state=tk.NORMAL)
        for entry in entries:
            ts = AppController.format_time(entry.timestamp)
            tag = entry.level if entry.level in ("ERROR", "WARN", "INFO") else "INFO"
            self._text.insert(tk.END, f"[{ts}] {entry.message}\n", tag)
        self._text.see(tk.END)
        self._text.configure(state=tk.DISABLED)
