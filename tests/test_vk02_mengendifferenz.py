"""
VKZ 02 — Nachforderung einer Mengendifferenz (Anlage 1, TP 5, V21, 7.4.1).

Anlass: Praxen haben bei Blankoverordnungen je Termin eine Einheit zu wenig
eingetragen. Nachgefordert werden darf nach 7.4.1 nur die Differenz — nicht der
ganze Beleg noch einmal.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from esol_validator import EsolValidator
from tools.generate_correction import (
    generate_correction_esol,
    mengendifferenz_modifikationen,
    parse_esol_belege_summary,
    vk02_unveraenderte_belege,
)

PROJEKT = Path(__file__).resolve().parent.parent

# Zwei Belege:
#   00001 Blanko Ergo — Bedarfsanalyse, Pauschale, zwei Termine mit je 3 Zeitintervallen
#   00002 Regelversorgung — keine Zeitintervall-Position
QUELLE = "\n".join([
    "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
    "UNH+00001+SLGA:21:0:0'",
    "FKT+01++123456789+101777502+101777502+123456789'",
    "REC+51:0+20260122+1'",
    "GES+00+322,88+369,64+46,76'",
    "GES+31+322,88+369,64+46,76'",
    "NAM+Ergo Praxis+++info@ergo.de'",
    "UNT+000007+00001'",
    "UNH+00002+SLLA:21:0:0'",
    "FKT+01++123456789+101777502+101777502'",
    "REC+51:0+20260122+1'",
    "INV+A123456789+30000+1+00001'",
    "NAD+Muster+Max+19900101'",
    "EHE+26:00502+54003+1,00+49,43+20260105+4,94'",
    "EHE+26:00502+54503+1,00+102,19+20260105+0,00'",
    "EHE+26:00502+54142+3,00+19,67+20260105+1,97'",
    "EHE+26:00502+54142+3,00+19,67+20260112+1,97'",
    "ZHE+110178400+906716934+20251228+3+EN1+04+++++1++1110++0+1+2'",
    "DIA+F98.9'",
    "BES+269,64+26,76+16,76+10,00'",
    "INV+A987654321+30000+1+00002'",
    "NAD+Beispiel+Erika+19800202'",
    "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
    "ZHE+110178400+906716934+20251228+3+EN1+04+++++1++1110++0+1+2'",
    "DIA+F98.9'",
    "BES+100,00+20,00+10,00+10,00'",
    "UNT+000019+00002'",
    "UNZ+000002+00118'",
]) + "\n"


def _segmente(text: str, tag: str):
    return [z for z in text.splitlines() if z.startswith(tag + "+")]


def _validiere(text: str):
    v = EsolValidator()
    v.register_default_rules()
    return v.validate_string(text)


def test_quelle_ist_gueltig():
    res = _validiere(QUELLE)
    assert res.is_valid(), res.get_errors()


def test_nur_zeitintervall_positionen_mit_differenzmenge():
    mods, bericht = mengendifferenz_modifikationen(QUELLE, differenz=1)

    assert set(mods) == {"00001"}
    pos = mods["00001"]["positions"]
    assert [p["code"] for p in pos] == ["54142", "54142"]
    assert [p["datum"] for p in pos] == ["20260105", "20260112"]
    assert all(p["anzahl"] == 1.0 for p in pos)
    # Preis und Zuzahlung je Einheit wie im Original, Tarif ebenso
    assert all(p["einzelbetrag"] == 19.67 and p["zuzahlung"] == 1.97 for p in pos)
    assert all(p["tarif_kz"] == "00502" and p["abr_code"] == "26" for p in pos)
    # keine erneute Zuzahlung je Verordnung
    assert mods["00001"]["zuzahlung_pausch"] == 0.0

    b1 = next(b for b in bericht if b["belegnr"] == "00001")
    assert b1["entfernt"] == ["54003", "54503"]
    assert not b1["ausgelassen"]
    b2 = next(b for b in bericht if b["belegnr"] == "00002")
    assert b2["ausgelassen"]


def test_erzeugte_datei_enthaelt_nur_die_differenz():
    mods, bericht = mengendifferenz_modifikationen(QUELLE, differenz=1)
    belege = [b["belegnr"] for b in bericht if not b["ausgelassen"]]
    text = generate_correction_esol(
        QUELLE, target_vk="02", selected_belegnr_list=belege,
        new_rec_nr="0201", new_rec_date="20261001", beleg_modifications=mods,
    )

    assert _segmente(text, "FKT")[0].startswith("FKT+02+")
    assert _segmente(text, "EHE") == [
        "EHE+26:00502+54142+1,00+19,67+20260105+1,97'",
        "EHE+26:00502+54142+1,00+19,67+20260112+1,97'",
    ]
    # Brutto 2 x 19,67; Zuzahlung nur prozentual 2 x 1,97; Pauschale 0
    assert _segmente(text, "BES") == ["BES+39,34+3,94+3,94+0,00'"]
    assert "GES+00+35,40+39,34+3,94'" in text
    # Beleg 00002 ist nicht drin
    assert "00002'" not in "".join(_segmente(text, "INV"))
    assert len(_segmente(text, "URI")) == 1

    res = _validiere(text)
    assert res.is_valid(), res.get_errors()


def test_differenz_zwei():
    mods, _ = mengendifferenz_modifikationen(QUELLE, selected_belegnr_list=["00001"], differenz=2)
    text = generate_correction_esol(QUELLE, target_vk="02", selected_belegnr_list=["00001"],
                                    beleg_modifications=mods)
    assert _segmente(text, "BES") == ["BES+78,68+7,88+7,88+0,00'"]
    assert _validiere(text).is_valid()


def test_differenz_muss_positiv_sein():
    with pytest.raises(ValueError):
        mengendifferenz_modifikationen(QUELLE, differenz=0)


def test_ohne_positionsliste_wird_nicht_geraten():
    with pytest.raises(ValueError, match="Zeitintervall"):
        mengendifferenz_modifikationen(QUELLE, zeitintervall_codes=[])


def test_positionsliste_liegt_im_projekt():
    import codelisten
    codes = codelisten.zeitintervall_positionen()
    assert "54142" in codes
    # einmalige Positionen dürfen nicht in der Liste stehen
    for einmalig in ("54003", "54503", "59741", "59973", "59974"):
        assert einmalig not in codes


def test_unveraenderte_belege_werden_erkannt():
    treffer = vk02_unveraenderte_belege(QUELLE)
    assert {t["belegnr"] for t in treffer} == {"00001", "00002"}

    mods, _ = mengendifferenz_modifikationen(QUELLE, selected_belegnr_list=["00001"])
    treffer = vk02_unveraenderte_belege(QUELLE, selected_belegnr_list=["00001"],
                                        beleg_modifications=mods)
    assert treffer == []


def test_bearbeitet_aber_identisch_zaehlt_als_unveraendert():
    beleg = next(b for b in parse_esol_belege_summary(QUELLE) if b["belegnr"] == "00002")
    mods = {"00002": {"positions": beleg["positions"]}}
    treffer = vk02_unveraenderte_belege(QUELLE, ["00002"], mods)
    assert len(treffer) == 1 and "identisch" in treffer[0]["grund"]


def test_kommandozeile(tmp_path: Path):
    src = tmp_path / "ESOL0200"
    src.write_text(QUELLE, encoding="iso-8859-1")
    out = tmp_path / "out"
    r = subprocess.run(
        [sys.executable, str(PROJEKT / "tools" / "generate_correction.py"), str(src),
         "-t", "02", "--mengendifferenz", "1", "--new-rec-nr", "0201", "-o", str(out)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    assert "Beleg 00002: keine Zeitintervall-Position" in r.stdout
    text = (out / "ESOL0201").read_text(encoding="iso-8859-1")
    assert _segmente(text, "BES") == ["BES+39,34+3,94+3,94+0,00'"]


def test_kommandozeile_warnt_ohne_mengendifferenz(tmp_path: Path):
    src = tmp_path / "ESOL0200"
    src.write_text(QUELLE, encoding="iso-8859-1")
    r = subprocess.run(
        [sys.executable, str(PROJEKT / "tools" / "generate_correction.py"), str(src),
         "-t", "02", "-o", str(tmp_path / "out")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    assert "WARNUNG" in r.stdout and "7.4.1" in r.stdout


def test_mengendifferenz_nur_bei_vkz_02(tmp_path: Path):
    src = tmp_path / "ESOL0200"
    src.write_text(QUELLE, encoding="iso-8859-1")
    r = subprocess.run(
        [sys.executable, str(PROJEKT / "tools" / "generate_correction.py"), str(src),
         "-t", "04", "--mengendifferenz", "1"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# Editor — braucht Tk
# ---------------------------------------------------------------------------

@pytest.fixture
def editor(tmp_path: Path):
    try:
        import tkinter as tk
        from vkz_correction_editor import VKZCorrectionEditorDialog

        src = tmp_path / "ESOL0200"
        src.write_text(QUELLE, encoding="iso-8859-1")
        root = tk.Tk()
        root.withdraw()
        dlg = VKZCorrectionEditorDialog(
            parent=root, file_path=str(src), selected_belegnr_list=["00001", "00002"],
            target_vk="02", output_dir=str(tmp_path / "out"),
        )
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


def test_editor_setzt_mengendifferenz_fuer_alle_belege(editor):
    editor._apply_mengendifferenz(differenz=1, nachfragen=False)

    assert editor.selected_belegnr_list == ["00001"]
    assert not editor.beleg_tree.exists("00002")
    assert set(editor.modifications) == {"00001"}
    assert editor.var_pausch.get() is False

    vorschau = editor._generiere_vorschau(nur_aktiver_beleg=False)
    assert _segmente(vorschau, "BES") == ["BES+39,34+3,94+3,94+0,00'"]
    assert vk02_unveraenderte_belege(
        editor.raw_content, editor.selected_belegnr_list, editor.modifications
    ) == []


def test_editor_warnt_vor_unveraenderten_belegen(editor, monkeypatch):
    from tkinter import messagebox

    gefragt = []
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: gefragt.append(a) or False)
    assert editor._bestaetige_unveraenderte_belege(ist_handarbeit=False) is False
    assert gefragt and "7.4.1" in gefragt[0][1]

    gefragt.clear()
    editor._apply_mengendifferenz(differenz=1, nachfragen=False)
    assert editor._bestaetige_unveraenderte_belege(ist_handarbeit=False) is True
    assert not gefragt
