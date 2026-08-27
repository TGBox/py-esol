import json
import os
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_FILE = Path.home() / ".pyesol_config.json"

DARK_COLORS: Dict[str, str] = {
    "bg": "#1e1e2e",
    "card_bg": "#28283d",
    "fg": "#cdd6f4",
    "fg_subdued": "#a6adc8",
    "entry_bg": "#181825",
    "entry_fg": "#cdd6f4",
    "btn_bg": "#313244",
    "btn_fg": "#cdd6f4",
    "btn_active_bg": "#45475a",
    "tree_bg": "#181825",
    "tree_fg": "#cdd6f4",
    "tree_heading_bg": "#313244",
    "tree_heading_fg": "#cdd6f4",
    "select_bg": "#45475a",
    "select_fg": "#ffffff",
    "log_bg": "#11111b",
    "log_fg": "#cdd6f4",
    "log_header": "#89b4fa",
    "log_error": "#f38ba8",
    "log_ok": "#a6e3a1",
}

LIGHT_COLORS: Dict[str, str] = {
    "bg": "#f4f4f6",
    "card_bg": "#ffffff",
    "fg": "#1c1c1e",
    "fg_subdued": "#666666",
    "entry_bg": "#ffffff",
    "entry_fg": "#1c1c1e",
    "btn_bg": "#e5e5ea",
    "btn_fg": "#1c1c1e",
    "btn_active_bg": "#d1d1d6",
    "tree_bg": "#ffffff",
    "tree_fg": "#1c1c1e",
    "tree_heading_bg": "#e5e5ea",
    "tree_heading_fg": "#1c1c1e",
    "select_bg": "#007aff",
    "select_fg": "#ffffff",
    "log_bg": "#ffffff",
    "log_fg": "#1c1c1e",
    "log_header": "#1976d2",
    "log_error": "#d32f2f",
    "log_ok": "#388e3c",
}


def load_config() -> Dict[str, Any]:
    """Loads configuration from user's home directory config file."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """Saves configuration to user's home directory config file."""
    try:
        data = load_config()
        data.update(config)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save config to {CONFIG_FILE}: {e}", file=sys.stderr)


def get_current_theme() -> str:
    """Returns 'dark' or 'light' based on saved configuration (default: 'dark')."""
    config = load_config()
    return config.get("theme", "dark")


def set_current_theme(mode: str) -> None:
    """Saves the theme mode ('dark' or 'light')."""
    save_config({"theme": mode})


def get_theme_colors(mode: Optional[str] = None) -> Dict[str, str]:
    """Returns color dictionary for given mode or current active mode."""
    if mode is None:
        mode = get_current_theme()
    return DARK_COLORS if mode == "dark" else LIGHT_COLORS


def apply_theme(root: tk.Tk | tk.Toplevel, mode: Optional[str] = None) -> str:
    """
    Applies TTK style and root window background colors based on mode.
    Returns active theme mode ('dark' or 'light').
    """
    if mode is None:
        mode = get_current_theme()

    colors = get_theme_colors(mode)

    # Apply root background
    root.configure(bg=colors["bg"])

    # Configure TTK Styles
    style = ttk.Style(root)
    
    # Use 'clam' theme if available for consistent styling across platforms
    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")

    # Frame & LabelFrame
    style.configure("TFrame", background=colors["bg"])
    style.configure("TLabelframe", background=colors["card_bg"], bordercolor=colors["btn_bg"])
    style.configure("TLabelframe.Label", background=colors["card_bg"], foreground=colors["fg"], font=("Segoe UI", 9, "bold"))

    # Labels
    style.configure("TLabel", background=colors["card_bg"], foreground=colors["fg"])

    # Buttons
    style.configure(
        "TButton",
        background=colors["btn_bg"],
        foreground=colors["btn_fg"],
        bordercolor=colors["btn_bg"],
        focusthickness=0,
        focuscolor=colors["select_bg"],
        padding=4,
    )
    style.map(
        "TButton",
        background=[("active", colors["btn_active_bg"]), ("disabled", colors["bg"])],
        foreground=[("disabled", colors["fg_subdued"])],
    )

    # Checkbuttons & Radiobuttons
    style.configure(
        "TCheckbutton",
        background=colors["card_bg"],
        foreground=colors["fg"],
        indicatorbackground=colors["entry_bg"],
        indicatorforeground=colors["fg"],
    )
    style.map(
        "TCheckbutton",
        background=[("active", colors["card_bg"])],
        indicatorbackground=[("selected", colors["select_bg"])],
    )

    style.configure(
        "TRadiobutton",
        background=colors["card_bg"],
        foreground=colors["fg"],
        indicatorbackground=colors["entry_bg"],
        indicatorforeground=colors["fg"],
    )
    style.map(
        "TRadiobutton",
        background=[("active", colors["card_bg"])],
        indicatorbackground=[("selected", colors["select_bg"])],
    )

    # Entries & Spinboxes
    style.configure(
        "TEntry",
        fieldbackground=colors["entry_bg"],
        foreground=colors["entry_fg"],
        insertcolor=colors["entry_fg"],
        bordercolor=colors["btn_bg"],
    )
    style.configure(
        "TSpinbox",
        fieldbackground=colors["entry_bg"],
        foreground=colors["entry_fg"],
        arrowcolor=colors["fg"],
        bordercolor=colors["btn_bg"],
    )

    # Combobox
    style.configure(
        "TCombobox",
        fieldbackground=colors["entry_bg"],
        background=colors["btn_bg"],
        foreground=colors["entry_fg"],
        arrowcolor=colors["fg"],
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", colors["entry_bg"])],
        foreground=[("readonly", colors["entry_fg"])],
    )

    # Treeview
    style.configure(
        "Treeview",
        background=colors["tree_bg"],
        foreground=colors["tree_fg"],
        fieldbackground=colors["tree_bg"],
        bordercolor=colors["btn_bg"],
        rowheight=24,
    )
    style.map(
        "Treeview",
        background=[("selected", colors["select_bg"])],
        foreground=[("selected", colors["select_fg"])],
    )

    style.configure(
        "Treeview.Heading",
        background=colors["tree_heading_bg"],
        foreground=colors["tree_heading_fg"],
        bordercolor=colors["btn_bg"],
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", colors["btn_active_bg"])],
    )

    # Scrollbar
    style.configure(
        "TScrollbar",
        background=colors["btn_bg"],
        troughcolor=colors["bg"],
        arrowcolor=colors["fg"],
        bordercolor=colors["bg"],
    )

    # Progressbar
    style.configure(
        "TProgressbar",
        troughcolor=colors["entry_bg"],
        background=colors["select_bg"],
        bordercolor=colors["bg"],
    )

    # Notebook & Tabs
    style.configure(
        "TNotebook",
        background=colors["bg"],
        bordercolor=colors["btn_bg"],
        tabmargins=[2, 5, 2, 0],
    )
    style.configure(
        "TNotebook.Tab",
        background=colors["btn_bg"],
        foreground=colors["btn_fg"],
        bordercolor=colors["btn_bg"],
        padding=[12, 5],
        font=("Segoe UI", 9, "bold"),
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", colors["card_bg"]), ("active", colors["btn_active_bg"])],
        foreground=[("selected", colors["fg"]), ("active", colors["fg"])],
    )

    # PanedWindow
    style.configure(
        "TPanedwindow",
        background=colors["bg"],
        sashcolor=colors["btn_bg"],
    )

    return mode
