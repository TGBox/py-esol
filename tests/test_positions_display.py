import os
import sys
import tkinter as tk
from unittest.mock import MagicMock
import pytest

import codelisten
import support_helper as sh
from vkz_correction_editor import PositionSearchDialog, PositionEditDialog
from gui_beleg_dashboard import BelegDashboardFrame
from main import EsolValidatorGUI


def test_codelisten_alle_positionen():
    all_pos = codelisten.alle_positionen()
    assert len(all_pos) > 0

    first = all_pos[0]
    assert "code" in first
    assert "bezeichnung" in first
    assert "bereich" in first
    assert "quelle" in first

    # Test filtering by code (e.g. 54103 matches X4103 in GKV catalogue)
    filtered_code = codelisten.alle_positionen("54103")
    assert len(filtered_code) > 0
    assert any("4103" in p["code"] for p in filtered_code)

    # Test filtering by partial description
    filtered_text = codelisten.alle_positionen("sensomotorisch")
    assert len(filtered_text) > 0
    assert all("sensomotorisch" in p["bezeichnung"].lower() or "sensomotorisch" in p["bereich"].lower() or "sensomotorisch" in p["code"].lower() for p in filtered_text)


def test_support_helper_positions_segment_summary():
    # EHE segment with composite 26:00501 and code 54103
    fields = [["26", "00501"], "54103", "1,00", "45,50", "20260116", "4,55"]
    summary = sh._segment_summary("EHE", fields)
    assert "54103" in summary
    # Clear text should be appended
    assert "Sensomotorisch" in summary
    assert "45,50" in summary


def test_support_helper_positions_zusatz_children():
    ids = sh._IdGen()
    fields = [["26", "00501"], "54103", "1,00", "45,50", "20260116", "4,55"]
    children = sh._zusatz_children(ids, "EHE", fields)
    assert len(children) >= 1
    assert children[0]["label"] == "Leistungsbezeichnung"
    assert "Sensomotorisch" in children[0]["details"]


def test_position_search_dialog():
    root = tk.Tk()
    root.withdraw()
    try:
        dlg = PositionSearchDialog(root, initial_search="54103")
        assert len(dlg.tree.get_children()) > 0
        dlg.destroy()
    finally:
        root.destroy()


def test_position_edit_dialog_live_lookup():
    root = tk.Tk()
    root.withdraw()
    try:
        dlg = PositionEditDialog(root, position_data={"code": "54103", "tarif_kz": "00501"})
        assert "Sensomotorisch" in dlg.lbl_code_desc.cget("text")
        dlg.destroy()
    finally:
        root.destroy()


def test_beleg_dashboard_positions_tab_and_text():
    root = tk.Tk()
    root.withdraw()
    try:
        dash = BelegDashboardFrame(root)
        beleg = {
            "belegnr": "12345",
            "nachname": "Mustermann",
            "vorname": "Max",
            "versichertennummer": "A123456789",
            "tarifkennzeichen": "00501",
            "brutto": 45.50,
            "total_zuzahlung": 4.55,
            "positions": [
                {
                    "tag": "EHE",
                    "code": "54103",
                    "tarif_kz": "00501",
                    "datum": "20260116",
                    "anzahl": 1.0,
                    "einzelbetrag": 45.50,
                    "gesamtbetrag": 45.50,
                    "zuzahlung": 4.55,
                    "zuzahlung_gesamt": 4.55,
                }
            ],
        }
        dash.load_data([beleg], [])

        # Select the item
        dash.beleg_tree.selection_set("12345")
        dash._on_beleg_selected(None)

        # Check positions treeview
        pos_items = dash.beleg_pos_tree.get_children()
        assert len(pos_items) == 1
        vals = dash.beleg_pos_tree.item(pos_items[0], "values")
        assert vals[0] == "EHE"
        assert vals[1] == "54103"
        assert "Sensomotorisch" in vals[2]

        # Check info box content
        content = dash.info_box.get("1.0", tk.END)
        assert "54103: Sensomotorisch-perzeptive Behandlung" in content
    finally:
        root.destroy()


def test_main_gui_fullscreen_toggle():
    app = EsolValidatorGUI()
    app.withdraw()
    try:
        assert app.is_fullscreen is False
        app._toggle_fullscreen()
        assert app.is_fullscreen is True
        app._toggle_fullscreen()
        assert app.is_fullscreen is False
    finally:
        app.destroy()
