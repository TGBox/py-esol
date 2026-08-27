import os
import tkinter as tk
from unittest.mock import patch
import pytest

import main


def test_user_selected_out_dir_flag_behavior():
    try:
        app = main.EsolValidatorGUI()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter environment not available: {e}")

    try:
        # Initially user_selected_out_dir is False
        assert app.user_selected_out_dir is False

        # Simulate selecting files in /path/a
        with patch("tkinter.filedialog.askopenfilenames", return_value=["/path/a/file1.esol"]):
            app._select_files()

        # out_dir_entry should be updated to /path/a and cursor set to end
        assert app.out_dir_entry.get() == "/path/a"
        assert app.path_entry.index(tk.INSERT) == len(app.path_entry.get())
        assert app.out_dir_entry.index(tk.INSERT) == len(app.out_dir_entry.get())
        assert app.user_selected_out_dir is False  # Still False because user didn't pick out_dir manually

        # User explicitly selects output directory /path/custom
        with patch("tkinter.filedialog.askdirectory", return_value="/path/custom"):
            app._select_out_directory()

        assert app.out_dir_entry.get() == "/path/custom"
        assert app.out_dir_entry.index(tk.INSERT) == len("/path/custom")
        assert app.user_selected_out_dir is True

        # Now simulate selecting files in another folder /path/b
        with patch("tkinter.filedialog.askopenfilenames", return_value=["/path/b/file2.esol"]):
            app._select_files()

        # Path entry updated to /path/b/file2.esol
        assert app.path_entry.get() == "/path/b/file2.esol"
        assert app.path_entry.index(tk.INSERT) == len("/path/b/file2.esol")
        # Out dir entry MUST NOT be overwritten, it must stay /path/custom
        assert app.out_dir_entry.get() == "/path/custom"

    finally:
        app.destroy()
