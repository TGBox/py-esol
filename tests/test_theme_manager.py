import os
import tempfile
import tkinter as tk
from unittest.mock import patch
import pytest

import theme_manager


def test_theme_colors_completeness():
    dark = theme_manager.DARK_COLORS
    light = theme_manager.LIGHT_COLORS

    assert set(dark.keys()) == set(light.keys())
    required_keys = [
        "bg",
        "card_bg",
        "fg",
        "entry_bg",
        "btn_bg",
        "tree_bg",
        "log_bg",
        "log_error",
        "log_ok",
        "log_header",
    ]
    for key in required_keys:
        assert key in dark
        assert dark[key].startswith("#")
        assert light[key].startswith("#")


def test_get_and_set_theme(tmp_path):
    fake_config = tmp_path / "test_config.json"
    with patch.object(theme_manager, "CONFIG_FILE", fake_config):
        # Default should be dark
        assert theme_manager.get_current_theme() == "dark"

        # Change to light
        theme_manager.set_current_theme("light")
        assert theme_manager.get_current_theme() == "light"

        # Change back to dark
        theme_manager.set_current_theme("dark")
        assert theme_manager.get_current_theme() == "dark"


def test_apply_theme_headless():
    try:
        root = tk.Tk()
        root.withdraw()  # Don't show UI window during test
    except Exception as e:
        pytest.skip(f"Tkinter root cannot be initialized in environment: {e}")

    try:
        active_mode = theme_manager.apply_theme(root, mode="dark")
        assert active_mode == "dark"

        colors = theme_manager.get_theme_colors("dark")
        assert colors["bg"] == theme_manager.DARK_COLORS["bg"]

        active_mode_light = theme_manager.apply_theme(root, mode="light")
        assert active_mode_light == "light"
    finally:
        root.destroy()
