"""
控制台 UI 视觉主题（ttk + 少量 tk 配色）。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg": "#f4f6f9",
    "header_bg": "#1a5276",
    "header_fg": "#ffffff",
    "accent": "#2874a6",
    "success": "#1e8449",
    "warning": "#b7950b",
    "error": "#c0392b",
    "muted": "#5d6d7e",
    "card_bg": "#ffffff",
    "border": "#d5d8dc",
}


def apply_theme(root: tk.Tk) -> ttk.Style:
    root.configure(bg=COLORS["bg"])
    style = ttk.Style(root)
    for name in ("vista", "xpnative", "clam"):
        try:
            style.theme_use(name)
            break
        except tk.TclError:
            continue

    style.configure(".", font=("Segoe UI", 10), background=COLORS["bg"])
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("TLabel", background=COLORS["bg"])
    style.configure("TLabelframe", background=COLORS["bg"])
    style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground=COLORS["accent"])
    style.configure("TButton", padding=(10, 4))
    style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"), foreground=COLORS["header_fg"], background=COLORS["accent"])
    style.map(
        "Accent.TButton",
        background=[("active", "#1f618d"), ("disabled", COLORS["border"])],
        foreground=[("disabled", "#aeb6bf")],
    )
    style.configure("Header.TFrame", background=COLORS["header_bg"])
    style.configure("HeaderTitle.TLabel", background=COLORS["header_bg"], foreground=COLORS["header_fg"], font=("Segoe UI", 15, "bold"))
    style.configure("HeaderSub.TLabel", background=COLORS["header_bg"], foreground="#d6eaf8", font=("Segoe UI", 9))
    style.configure("StatusBar.TFrame", background=COLORS["card_bg"], relief="solid", borderwidth=1)
    style.configure("StatusState.TLabel", background=COLORS["card_bg"], font=("Segoe UI", 11, "bold"))
    style.configure("StatusDetail.TLabel", background=COLORS["card_bg"], foreground=COLORS["muted"])
    style.configure("Card.TLabelframe", background=COLORS["card_bg"])
    style.configure("Card.TLabelframe.Label", background=COLORS["card_bg"], foreground=COLORS["accent"])
    style.configure("CardInner.TFrame", background=COLORS["card_bg"])
    style.configure("CardInner.TLabel", background=COLORS["card_bg"])
    style.configure("CardSummary.TLabel", background=COLORS["card_bg"], font=("Segoe UI", 12, "bold"), foreground=COLORS["accent"])
    style.configure("CardMeta.TLabel", background=COLORS["card_bg"], foreground=COLORS["muted"], font=("Segoe UI", 9))
    style.configure("Running.TLabel", background=COLORS["card_bg"], foreground=COLORS["success"], font=("Segoe UI", 10, "bold"))
    style.configure("Stopped.TLabel", background=COLORS["card_bg"], foreground=COLORS["muted"])
    style.configure("ErrorText.TLabel", background=COLORS["card_bg"], foreground=COLORS["error"])
    return style


def state_color(state_value: str) -> str:
    if state_value == "RUNNING":
        return COLORS["success"]
    if state_value == "ERROR":
        return COLORS["error"]
    if state_value == "STARTING":
        return COLORS["warning"]
    return COLORS["muted"]
