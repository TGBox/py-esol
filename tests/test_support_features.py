from pathlib import Path
import tkinter as tk
import pytest
from unittest.mock import patch

from support_helper import (
    translate_error,
    generate_ticket_summary,
    generate_html_report,
    parse_esol_tree_nodes,
)
from gui_beleg_dashboard import BelegDashboardFrame
from gui_recipe_tree import RecipeTreeFrame
from gui_muster13_preview import Muster13PreviewFrame
import main


def test_support_helper_error_translation():
    t1 = translate_error("R_IK_01: Prüfziffer Institutionskennzeichen ungültig")
    assert "Institutionskennzeichen" in t1["title"]
    assert "Tippfehler" in t1["action"]

    t2 = translate_error("R_GES_01: Abweichung im GES-Segment")
    assert "Gesamtsummen" in t2["title"]

    t3 = translate_error("Unbekannter Fehler 99")
    assert "Validierungsfehler" in t3["title"]


def test_support_helper_ticket_summary():
    belege = [
        {
            "belegnr": "00001",
            "nachname": "Muster",
            "vorname": "Max",
            "brutto": 100.0,
            "total_zuzahlung": 20.0,
        }
    ]
    summary = generate_ticket_summary("test.esol", ["R_IK_01: IK ungültig"], belege)

    assert "ESOL SUPPORT-TICKET BERICHT" in summary
    assert "test.esol" in summary
    assert "Muster, Max" in summary
    assert "100,00 €" in summary
    assert "R_IK_01" in summary


def test_support_helper_html_report():
    belege = [
        {
            "belegnr": "00001",
            "nachname": "Muster",
            "vorname": "Max",
            "brutto": 100.0,
            "total_zuzahlung": 20.0,
        }
    ]
    html_doc = generate_html_report("test.esol", ["R_IK_01: IK ungültig"], belege)

    assert "<!DOCTYPE html>" in html_doc
    assert "test.esol" in html_doc
    assert "Muster, Max" in html_doc
    assert "FEHLERHAFT" in html_doc


def test_support_helper_tree_nodes():
    raw_esol = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+100,00+100,00+0,00'",
        "INV+A123456789+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
        "BES+100,00+20,00+10,00+10,00'",
        "UNT+000009+00001'",
        "UNZ+000001+00118'",
    ])

    nodes = parse_esol_tree_nodes(raw_esol)
    assert len(nodes) > 0

    # INV-Blöcke hängen unterhalb ihres Nachrichtenknotens (UNH) -> rekursiv suchen
    inv_node = _find_node(nodes, "INV")
    assert inv_node is not None
    assert "00001" in inv_node["details"]

    # NAD, Leistungen (gruppierte EHE), BES
    child_tags = [c["tag"] for c in inv_node["children"]]
    assert child_tags == ["NAD", "LEISTUNGEN", "BES"]

    # Alle Knoten-IDs müssen eindeutig sein (Treeview-iids)
    ids = []
    _collect_ids(nodes, ids)
    assert len(ids) == len(set(ids))


def _find_node(nodes, tag):
    """Sucht den ersten Knoten mit dem angegebenen Tag rekursiv."""
    for n in nodes:
        if n.get("tag") == tag:
            return n
        found = _find_node(n.get("children") or [], tag)
        if found:
            return found
    return None


def _collect_ids(nodes, out):
    for n in nodes:
        out.append(n["id"])
        _collect_ids(n.get("children") or [], out)


def test_tree_nodes_verordnungsdaten_klartext():
    """ZHE muss als aufklappbarer Klartext-Knoten mit Verordnungsdaten erscheinen."""
    raw_esol = "\n".join([
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+54103+1,00+75,91+20260115+0,00'",
        "EHE+26:00501+54103+1,00+75,91+20260122+0,00'",
        "ZHE+242325300+963752734+20260110+3+EN1+03+++++1++1100++0+1+3'",
        "DIA+F91.9+Störung des Sozialverhaltens'",
        "BES+151,82+10,00+0,00+10,00'",
        "UNT+000010+00002'",
    ])

    nodes = parse_esol_tree_nodes(raw_esol)
    inv = _find_node(nodes, "INV")
    assert inv is not None

    zhe = _find_node([inv], "ZHE")
    assert zhe is not None
    assert "10.01.2026" in zhe["details"]
    assert "242325300" in zhe["details"]

    felder = {c["label"]: c["details"] for c in zhe["children"]}
    assert felder["Verordnungsdatum"] == "10.01.2026"
    assert felder["Betriebsstättennummer (BSNR)"] == "242325300"
    assert felder["Lebenslange Arztnummer (LANR)"] == "963752734"
    assert felder["Leitsymptomatik"].startswith("1100 — a, b")
    assert "Therapiebericht verordnet" in felder["Therapiebericht"]

    # Diagnosen mit Text
    dia = _find_node([inv], "DIA")
    assert dia is not None
    assert "F91.9" in dia["details"]

    # Gleiche Leistung an zwei Terminen -> eine Gruppe mit zwei Terminen
    leist = _find_node([inv], "LEISTUNGEN")
    assert leist is not None
    assert len(leist["children"]) == 1
    assert leist["children"][0]["details"].startswith("2×")
    assert len(leist["children"][0]["children"]) == 2


def test_gui_support_components():
    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter environment not available: {e}")

    try:
        belege = [
            {
                "belegnr": "00001",
                "nachname": "Muster",
                "vorname": "Max",
                "versichertennummer": "A123456789",
                "tarifkennzeichen": "00501",
                "zuzahlungskennzeichen": "3",
                "brutto": 100.0,
                "zuzahlung_proz": 10.0,
                "zuzahlung_pausch": 10.0,
                "total_zuzahlung": 20.0,
                "positions": [
                    {
                        "tag": "EHE",
                        "code": "59702",
                        "datum": "20260115",
                        "anzahl": 1.0,
                        "einzelbetrag": 100.0,
                        "gesamtbetrag": 100.0,
                        "zuzahlung": 10.0,
                    }
                ],
            }
        ]
        errors = ["R_IK_01 in Beleg 00001"]

        # 1. BelegDashboardFrame
        dash = BelegDashboardFrame(root)
        dash.load_data(belege, errors)
        assert dash.lbl_kpi_count.cget("text") == "1"
        assert "100,00" in dash.lbl_kpi_brutto.cget("text")
        dash.destroy()

        # 2. RecipeTreeFrame
        raw_esol = "UNB+UNOC:3+'\nINV+A123456789+31000+1+00001'\nBES+100,00+20,00+10,00+10,00'"
        tree_frame = RecipeTreeFrame(root)
        tree_frame.load_tree(raw_esol)
        tree_frame.focus_beleg("00001")
        tree_frame.destroy()

        # 3. Muster13PreviewFrame
        m13 = Muster13PreviewFrame(root)
        m13.load_beleg(belege[0], errors)
        assert m13.lbl_name.cget("text") == "Muster, Max"
        assert "100,00" in m13.lbl_brutto.cget("text")
        m13.destroy()

    finally:
        root.destroy()


def test_main_gui_support_notebook_integration(tmp_path: Path):
    try:
        app = main.EsolValidatorGUI()
        app.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter environment not available: {e}")

    try:
        assert hasattr(app, "main_notebook")
        assert hasattr(app, "dashboard_view")
        assert hasattr(app, "recipe_tree_view")
        assert hasattr(app, "muster13_view")

        orig_esol = "\n".join([
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
            "UNH+00001+SLGA:21:0:0'",
            "FKT+01++123456789+101777502+101777502+123456789'",
            "REC+51:0+20260122+1'",
            "GES+00+100,00+100,00+0,00'",
            "INV+A123456789+31000+1+00001'",
            "NAD+Muster+Max+19900101'",
            "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
            "BES+100,00+20,00+10,00+10,00'",
            "UNT+000009+00001'",
            "UNZ+000001+00118'",
        ])
        test_file = tmp_path / "test_main_support.esol"
        test_file.write_text(orig_esol, encoding="iso-8859-15")

        app._populate_support_tabs(str(test_file), ["R_IK_01 in Beleg 00001"])

        assert len(app.last_belege_summary) == 1
        assert app.last_belege_summary[0]["belegnr"] == "00001"
        assert app.muster13_view.lbl_name.cget("text") == "Muster, Max"

        # Test ticket summary copy
        with patch.object(app, "clipboard_append") as mock_clip:
            app._copy_ticket_summary()
            mock_clip.assert_called_once()
            args = mock_clip.call_args[0][0]
            assert "SUPPORT-TICKET BERICHT" in args
            assert "Muster, Max" in args

    finally:
        app.destroy()
