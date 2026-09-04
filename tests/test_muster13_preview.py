import tkinter as tk
import pytest
from gui_muster13_preview import Muster13PreviewFrame

@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()

def test_muster13_preview_frame_initialization(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    assert frame is not None
    assert frame.active_side == "front"
    assert frame.zoom_mode == "fit"
    assert frame.current_beleg is None

def test_muster13_preview_load_beleg(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    sample_beleg = {
        "belegnr": "12345",
        "ik": "104212505",
        "nachname": "Mustermann",
        "vorname": "Erika",
        "geburtstag": "19800101",
        "versichertennummer": "X123456789",
        "versichertenstatus": "10000",
        "bsnr": "123456789",
        "lanr": "987654321",
        "verordnungsdatum": "20251010",
        "zuzahlungskennzeichen": "1",
        "verordnungsart": "1",
        "diagnosegruppe": "WS2",
        "icd10": "M54.5",
        "leitsymptomatik": "Lumbago",
        "brutto": 150.00,
        "zuzahlung_proz": 0.0,
        "zuzahlung_pausch": 0.0,
        "total_zuzahlung": 0.0,
        "positions": [
            {"code": "20501", "tag": "EHE", "anzahl": 6, "einzelbetrag": 25.00, "gesamtbetrag": 150.00, "zuzahlung": 0.0, "datum": "20251011"}
        ]
    }

    frame.load_beleg(sample_beleg, validation_errors=["Fehler Beleg-Nr. 12345"])
    assert frame.current_beleg == sample_beleg
    assert frame.current_rendered_image is not None
    assert frame.lbl_beleg_nr.cget("text") == "Beleg-Nr. 12345"
    assert "Brutto: 150,00 €" in frame.lbl_brutto.cget("text")

def test_muster13_preview_side_switch(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    sample_beleg = {
        "belegnr": "999",
        "nachname": "Tester",
        "vorname": "Hans",
        "brutto": 100.0,
        "total_zuzahlung": 10.0,
        "positions": []
    }
    frame.load_beleg(sample_beleg)

    frame._set_active_side("back")
    assert frame.active_side == "back"
    assert frame.current_rendered_image is not None

    frame._set_active_side("front")
    assert frame.active_side == "front"

def test_muster13_preview_zoom_toggle(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    sample_beleg = {"belegnr": "100", "positions": []}
    frame.load_beleg(sample_beleg)

    frame._toggle_zoom()
    assert frame.zoom_mode == "100"

    frame._toggle_zoom()
    assert frame.zoom_mode == "fit"

def test_muster13_preview_apply_theme(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    sample_beleg = {"belegnr": "200", "positions": []}
    frame.load_beleg(sample_beleg)

    frame.apply_theme("dark")
    frame.apply_theme("light")
