"""
Tests für die bearbeitbare Vorschau im Korrektur-Editor
(Tab „Vorschau & EDIFACT-Diff").

Grundregel, die hier festgeschrieben wird: was rechts steht, wird gespeichert —
aber nur, wenn es die Validierung besteht. Eine von Hand bearbeitete
Korrekturdatei darf niemals unbemerkt ungültig herausgehen.
"""

import shutil
from pathlib import Path

import pytest

from tools.generate_correction import (
    generate_correction_file,
    pruefe_iso_8859_15,
    read_esol_file_text,
)

FIXTURE = Path(__file__).parent / "fixtures" / "valid_esol_smoke"


# ---------------------------------------------------------------------------
# Reine Logik — läuft auch ohne Tk
# ---------------------------------------------------------------------------

def test_iso_pruefung_erkennt_typografische_zeichen():
    text = 'NAD+Praxis „Neu"+Max+19900101\''
    treffer = pruefe_iso_8859_15(text)
    zeichen = {t[2] for t in treffer}
    assert "„" in zeichen or "“" in zeichen
    # Zeile und Spalte müssen 1-basiert und plausibel sein
    for zeile, spalte, _ in treffer:
        assert zeile == 1
        assert spalte > 0


def test_iso_pruefung_laesst_erlaubte_zeichen_durch():
    # Umlaute, ß und das Eurozeichen sind in ISO-8859-15 enthalten
    assert pruefe_iso_8859_15("NAD+Müster+Märta+Groß'\nTXT+100,00 €'") == []


def test_iso_pruefung_zaehlt_zeilen_richtig():
    text = "UNB+UNOC:3'\nNAD+ok'\nNAD+—'"
    treffer = pruefe_iso_8859_15(text)
    assert len(treffer) == 1
    assert treffer[0][0] == 3


def test_content_override_wird_unveraendert_geschrieben(tmp_path: Path):
    src = tmp_path / "ESOL0118"
    shutil.copy(FIXTURE, src)

    eigener_text = "UNB+UNOC:3+480512931'\nHANDARBEIT+Müster'\nUNZ+000001+00118'\n"
    ziel = generate_correction_file(
        input_path=src,
        target_vk="03",
        selected_belegnr_list=["00001"],
        new_rec_nr="9999",
        out_dir=tmp_path / "out",
        content_override=eigener_text,
    )

    assert ziel.read_text(encoding="iso-8859-15") == eigener_text


def test_ohne_content_override_wird_generiert(tmp_path: Path):
    src = tmp_path / "ESOL0118"
    shutil.copy(FIXTURE, src)

    ziel = generate_correction_file(
        input_path=src,
        target_vk="03",
        selected_belegnr_list=["00001"],
        new_rec_nr="9999",
        out_dir=tmp_path / "out",
    )

    inhalt = ziel.read_text(encoding="iso-8859-15")
    assert "FKT+03+" in inhalt
    assert "HANDARBEIT" not in inhalt


# ---------------------------------------------------------------------------
# Dialogverhalten — braucht Tk
# ---------------------------------------------------------------------------

def _dialog(tmp_path: Path):
    """Baut den Korrektur-Editor auf einer Kopie der Fixture auf."""
    import tkinter as tk

    from vkz_correction_editor import VKZCorrectionEditorDialog

    src = tmp_path / "ESOL0118"
    shutil.copy(FIXTURE, src)

    root = tk.Tk()
    root.withdraw()
    dlg = VKZCorrectionEditorDialog(
        parent=root,
        file_path=str(src),
        selected_belegnr_list=["00001"],
        target_vk="03",
        output_dir=str(tmp_path / "out"),
    )
    dlg._update_diff_preview()
    return root, dlg


@pytest.fixture
def editor(tmp_path: Path):
    try:
        root, dlg = _dialog(tmp_path)
    except Exception as e:
        pytest.skip(f"Tkinter environment not available: {e}")
    try:
        yield dlg
    finally:
        try:
            dlg.destroy()
            root.destroy()
        except Exception:
            pass


def _tippe(dlg, text: str):
    """Simuliert eine Handbearbeitung der rechten Seite."""
    dlg.txt_mod.config(state="normal")
    dlg.txt_mod.delete("1.0", "end")
    dlg.txt_mod.insert("1.0", text)
    dlg._on_mod_text_modified()


def test_standardansicht_ist_die_ganze_datei_und_bearbeitbar(editor):
    assert editor.diff_scope.get() == "datei"
    assert editor.txt_mod.cget("state") == "normal"
    assert editor.manual_content is None

    rechts = editor.txt_mod.get("1.0", "end-1c")
    # Vollständige Korrekturdatei: Umschlag und umgestelltes Verarbeitungskennzeichen
    assert "UNB+UNOC:3" in rechts
    assert "FKT+03+" in rechts
    assert rechts.rstrip().endswith("'")


def test_belegansicht_ist_nur_lesbar(editor):
    editor.diff_scope.set("beleg")
    editor._on_diff_scope_changed()

    assert editor.txt_mod.cget("state") == "disabled"
    assert "Vergleich" in editor.frame_mod.cget("text")
    assert "Ganze Datei" in editor.lbl_diff_status.cget("text")


def test_handbearbeitung_wird_erkannt_und_angezeigt(editor):
    original = editor.txt_mod.get("1.0", "end-1c")
    _tippe(editor, original.replace("Physio Praxis", "Praxis Neu"))

    assert editor.manual_content is not None
    assert "Praxis Neu" in editor.manual_content
    assert "HANDBEARBEITET" in editor.frame_mod.cget("text")
    assert "NICHT enthalten" in editor.lbl_diff_status.cget("text")


def test_handbearbeitung_ueberlebt_neuaufbau_der_vorschau(editor):
    """
    Eine Änderung an Positionen darf die Handarbeit nicht stillschweigend
    überschreiben — sonst ist die Arbeit weg, ohne dass es jemand merkt.
    """
    original = editor.txt_mod.get("1.0", "end-1c")
    _tippe(editor, original.replace("Physio Praxis", "Praxis Neu"))

    editor._update_diff_preview()

    assert "Praxis Neu" in editor.txt_mod.get("1.0", "end-1c")
    assert editor.manual_content is not None


def test_gueltige_handfassung_wird_zum_speichern_freigegeben(editor):
    original = editor.txt_mod.get("1.0", "end-1c")
    _tippe(editor, original.replace("Physio Praxis", "Praxis Neu"))

    ergebnis = editor._pruefe_und_bestaetige_handarbeit()

    assert isinstance(ergebnis, str)
    assert "Praxis Neu" in ergebnis


def test_kaputter_unt_zaehler_blockiert_das_speichern(editor, dialog_protokoll):
    original = editor.txt_mod.get("1.0", "end-1c")
    _tippe(editor, original.replace("UNT+000007", "UNT+000099"))

    assert editor._pruefe_und_bestaetige_handarbeit() is False
    assert dialog_protokoll.wurde_aufgerufen("showerror")


def test_nicht_speicherbares_zeichen_blockiert(editor, dialog_protokoll):
    original = editor.txt_mod.get("1.0", "end-1c")
    _tippe(editor, original.replace("Physio Praxis", "Praxis „Neu“"))

    assert editor._pruefe_und_bestaetige_handarbeit() is False
    assert dialog_protokoll.wurde_aufgerufen("showerror")


def test_leere_handfassung_blockiert(editor, dialog_protokoll):
    _tippe(editor, "   ")

    assert editor._pruefe_und_bestaetige_handarbeit() is False
    assert dialog_protokoll.wurde_aufgerufen("showerror")


def test_ohne_handarbeit_wird_regulaer_generiert(editor):
    assert editor._pruefe_und_bestaetige_handarbeit() is None


def test_generieren_schreibt_die_handfassung(editor, tmp_path: Path):
    original = editor.txt_mod.get("1.0", "end-1c")
    _tippe(editor, original.replace("Physio Praxis", "Praxis Neu"))

    editor._generate_correction()

    out_dir = tmp_path / "out"
    erzeugt = list(out_dir.iterdir())
    assert len(erzeugt) == 1, [p.name for p in erzeugt]

    inhalt = erzeugt[0].read_text(encoding="iso-8859-15")
    assert "Praxis Neu" in inhalt
    # Und die Datei muss weiterhin gültig sein
    from esol_validator import EsolValidator

    validator = EsolValidator()
    validator.register_default_rules()
    assert validator.validate_string(inhalt).is_valid()


def test_generieren_schreibt_nichts_bei_ungueltiger_handfassung(editor, tmp_path: Path,
                                                                dialog_protokoll):
    original = editor.txt_mod.get("1.0", "end-1c")
    _tippe(editor, original.replace("UNT+000007", "UNT+000099"))

    editor._generate_correction()

    out_dir = tmp_path / "out"
    vorhanden = list(out_dir.iterdir()) if out_dir.exists() else []
    assert vorhanden == [], f"Es wurde trotz Fehler geschrieben: {vorhanden}"
    assert dialog_protokoll.wurde_aufgerufen("showerror")


def test_neu_generieren_verwirft_die_handarbeit(editor, dialog_protokoll):
    original = editor.txt_mod.get("1.0", "end-1c")
    _tippe(editor, original.replace("Physio Praxis", "Praxis Neu"))
    assert editor.manual_content is not None

    # Die conftest-Fixture beantwortet askyesno mit True
    editor._regenerate_diff_preview()

    assert editor.manual_content is None
    assert "Praxis Neu" not in editor.txt_mod.get("1.0", "end-1c")
    assert "HANDBEARBEITET" not in editor.frame_mod.cget("text")
