from pathlib import Path
from tools.generate_correction import generate_correction_esol, generate_correction_file, parse_esol_belege_summary
from esol_validator import EsolValidator


def test_vk02_granular_position_and_price_edit(tmp_path: Path):
    orig_esol = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+100,00+100,00+0,00'",
        "GES+31+100,00+100,00+0,00'",
        "NAM+Physio Praxis+++info@physio.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "ZHE+110178400+906716934+20250528+3+EN1+04+++++1++1110++0+1+2+00501'",
        "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
        "DIA+F98.9'",
        "BES+100,00+20,00+10,00+10,00'",
        "UNT+000010+00002'",
        "UNZ+000002+00118'",
    ])

    orig_file = tmp_path / "orig_esol_vk02.txt"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    # Modify position: change price from 100,00 to 120,00 and quantity to 2
    beleg_mods = {
        "00001": {
            "tarifkennzeichen": "00501",
            "zuzahlungskennzeichen": "3",
            "positions": [
                {
                    "tag": "EHE",
                    "code": "59702",
                    "tarif_kz": "00501",
                    "datum": "20260115",
                    "anzahl": 2.0,
                    "einzelbetrag": 120.00,
                    "zuzahlung": 12.00,
                }
            ],
        }
    }

    res_file = generate_correction_file(
        orig_file,
        target_vk="02",
        selected_belegnr_list=["00001"],
        new_rec_nr="05200",
        new_rec_date="20260325",
        beleg_modifications=beleg_mods,
    )

    assert res_file.exists()
    content = res_file.read_text(encoding="iso-8859-15")

    # Check FKT changed to VK 02
    assert "FKT+02+" in content

    # Check URI segment inserted (Belegnummer unverändert aus dem Original)
    assert "URI+123456789+51:1+20260122+00001'" in content

    # Check modified EHE segment: 2 * 120.00 = 240.00 total brutto, 2 * 12.00 = 24.00 total co-payment
    assert "EHE+26:00501+59702+2,00+120,00+20260115+12,00'" in content

    # Check recalculated BES segment: Brutto 240.00, Total Zuz 34.00, Proz Zuz 24.00, Pausch Zuz 10.00
    assert "BES+240,00+34,00+24,00+10,00'" in content

    # Check recalculated GES segment: Status 31 Rechnungsbetrag 206.00, Brutto 240.00, Zuzahlung 34.00
    assert "GES+31+206,00+240,00+34,00'" in content

    # Validate generated file syntax and rules
    validator = EsolValidator()
    validator.register_default_rules()
    res = validator.validate_string(content)
    assert res.is_valid(), f"Expected valid VK02 file, got errors: {res.get_errors()}"


def test_vk02_add_and_delete_positions(tmp_path: Path):
    orig_esol = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+100,00+100,00+0,00'",
        "GES+31+100,00+100,00+0,00'",
        "NAM+Physio Praxis+++info@physio.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "ZHE+110178400+906716934+20250528+3+EN1+04+++++1++1110++0+1+2+00501'",
        "EHE+26:00501+59702+1,00+50,00+20260115+5,00'",
        "DIA+F98.9'",
        "BES+50,00+15,00+5,00+10,00'",
        "UNT+000010+00002'",
        "UNZ+000002+00118'",
    ])

    orig_file = tmp_path / "orig_esol_add_del.txt"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    # Add a second position (ENF / Hausbesuch) and update first position
    beleg_mods = {
        "00001": {
            "positions": [
                {
                    "tag": "EHE",
                    "code": "59702",
                    "tarif_kz": "00501",
                    "datum": "20260115",
                    "anzahl": 1.0,
                    "einzelbetrag": 50.00,
                    "zuzahlung": 5.00,
                },
                {
                    "tag": "ENF",
                    "code": "29901",
                    "tarif_kz": "00501",
                    "datum": "20260115",
                    "anzahl": 1.0,
                    "einzelbetrag": 30.00,
                    "zuzahlung": 3.00,
                },
            ]
        }
    }

    res_file = generate_correction_file(
        orig_file,
        target_vk="02",
        selected_belegnr_list=["00001"],
        beleg_modifications=beleg_mods,
    )

    content = res_file.read_text(encoding="iso-8859-15")

    # Verify both positions exist
    assert "EHE+26:00501+59702+" in content
    assert "ENF+01+26:00501+29901+" in content

    # Total Brutto: 50 + 30 = 80.00. Total Zuzahlung: 5 + 3 + 10 = 18.00. Proz Zuz: 8.00. Pausch Zuz: 10.00
    assert "BES+80,00+18,00+8,00+10,00'" in content

    # Validate whole file
    validator = EsolValidator()
    validator.register_default_rules()
    res = validator.validate_string(content)
    assert res.is_valid(), f"Expected valid VK02 file, got errors: {res.get_errors()}"


def test_vk02_segment_order_and_deleted_positions(tmp_path: Path):
    orig_esol = "\n".join([
        "UNB+UNOC:3+480512931+107436557+20260819:1330+00400+B+SL05'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+02++480512931+103724272+103724272+480512931'",
        "REC+400:0+20260819+1'",
        "GES+00+696,35+773,82+77,47'",
        "GES+11+696,35+773,82+77,47'",
        "NAM+Praxis fuer Ergotherapie und N+++info@ergotherapie-rom.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+02++480512931+103724272+103724272'",
        "REC+400:0+20260819+1'",
        "INV+D952924656+10000+1+00122'",
        "URI+480512931+105:122+20260505+122'",
        "NAD+Schneider+Britta+19690930'",
        "EHE+26:00502+54145+6,00+18,98+20251204+1,90'",
        "EHE+26:00502+54145+6,00+18,98+20251218+1,90'",
        "EHE+26:00502+59741+1,00+1,20+20251113+0,00'",
        "EHE+26:00502+54503+1,00+47,69+20251204+4,77'",
        "ZHE+243203100+512378658+20251113+2+PS3+05+++++1++1000++0+'",
        "DIA+F33.1'",
        "BES+276,64+28,57+18,57+10,00'",
        "UNT+000014+00002'",
        "UNZ+000002+00400'",
    ])

    orig_file = tmp_path / "orig_esol_order.txt"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    # Keep only 2 positions (59741 and 54503 modified to 98.59)
    beleg_mods = {
        "00122": {
            "tarifkennzeichen": "00502",
            "zuzahlungskennzeichen": "2",
            "positions": [
                {
                    "tag": "EHE",
                    "code": "59741",
                    "tarif_kz": "00502",
                    "datum": "20251204",
                    "anzahl": 1.0,
                    "einzelbetrag": 1.20,
                    "zuzahlung": 0.00,
                },
                {
                    "tag": "EHE",
                    "code": "54503",
                    "tarif_kz": "00502",
                    "datum": "20251204",
                    "anzahl": 1.0,
                    "einzelbetrag": 98.59,
                    "zuzahlung": 0.00,
                },
            ],
        }
    }

    res_file = generate_correction_file(
        orig_file,
        target_vk="02",
        selected_belegnr_list=["00122"],
        beleg_modifications=beleg_mods,
    )

    content = res_file.read_text(encoding="iso-8859-15")
    lines = [line.strip() for line in content.splitlines() if line.strip()]

    # Verify original deleted 54145 position is NOT in output
    assert "54145" not in content

    # Verify EHE segments are in exact EDIFACT position order (after NAD, before ZHE and DIA)
    nad_idx = next(i for i, line in enumerate(lines) if line.startswith("NAD+"))
    ehe1_idx = next(i for i, line in enumerate(lines) if "59741" in line)
    ehe2_idx = next(i for i, line in enumerate(lines) if "54503" in line)
    zhe_idx = next(i for i, line in enumerate(lines) if line.startswith("ZHE+"))
    dia_idx = next(i for i, line in enumerate(lines) if line.startswith("DIA+"))
    bes_idx = next(i for i, line in enumerate(lines) if line.startswith("BES+"))

    assert nad_idx < ehe1_idx < ehe2_idx < zhe_idx < dia_idx < bes_idx

    # Check recalculated sums: 1.20 + 98.59 = 99.79 Brutto. Co-payment = 10.00 pausch. Netto = 89.79
    assert "BES+99,79+10,00+0,00+10,00'" in content
    assert "GES+00+89,79+99,79+10,00'" in content

    # Validate file
    validator = EsolValidator()
    validator.register_default_rules()
    res = validator.validate_string(content)
    assert res.is_valid(), f"Expected valid VK02 file, got errors: {res.get_errors()}"


def test_vk02_copayment_pauschale_toggle(tmp_path: Path):
    orig_esol = "\n".join([
        "UNB+UNOC:3+480512931+107436557+20260819:1330+00400+B+SL05'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+02++480512931+103724272+103724272+480512931'",
        "REC+400:0+20260819+1'",
        "GES+00+100,00+100,00+0,00'",
        "GES+11+100,00+100,00+0,00'",
        "NAM+Praxis fuer Ergotherapie und N+++info@ergotherapie-rom.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+02++480512931+103724272+103724272'",
        "REC+400:0+20260819+1'",
        "INV+D952924656+10000+1+00122'",
        "URI+480512931+105:122+20260505+122'",
        "NAD+Schneider+Britta+19690930'",
        "EHE+26:00502+59741+1,00+100,00+20251204+0,00'",
        "ZHE+243203100+512378658+20251113+2+PS3+05+++++1++1000++0+'",
        "DIA+F33.1'",
        "BES+100,00+10,00+0,00+10,00'",
        "UNT+000011+00002'",
        "UNZ+000002+00400'",
    ])

    orig_file = tmp_path / "orig_esol_pausch.txt"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    # Set zuzahlung_pausch to 0.0 (patient already paid 10 € pauschale)
    beleg_mods = {
        "00122": {
            "tarifkennzeichen": "00502",
            "zuzahlungskennzeichen": "2",
            "zuzahlung_pausch": 0.0,
            "positions": [
                {
                    "tag": "EHE",
                    "code": "59741",
                    "tarif_kz": "00502",
                    "datum": "20251204",
                    "anzahl": 1.0,
                    "einzelbetrag": 100.00,
                    "zuzahlung": 0.00,
                }
            ],
        }
    }

    res_file = generate_correction_file(
        orig_file,
        target_vk="02",
        selected_belegnr_list=["00122"],
        beleg_modifications=beleg_mods,
    )

    content = res_file.read_text(encoding="iso-8859-15")

    # When 10 € pauschale is 0.0, total co-payment is 0.00, Netto is 100.00
    assert "BES+100,00+0,00+0,00+0,00'" in content
    assert "GES+00+100,00+100,00+0,00'" in content

    # Validate file
    validator = EsolValidator()
    validator.register_default_rules()
    res = validator.validate_string(content)
    assert res.is_valid(), f"Expected valid VK02 file, got errors: {res.get_errors()}"


def test_dialog_rec_nr_and_german_date_moved_to_second_dialog(tmp_path: Path):
    import tkinter as tk
    import pytest
    from gui_correction_dialog import CorrectionSelectionDialog
    from vkz_correction_editor import VKZCorrectionEditorDialog

    try:
        root = tk.Tk()
        root.withdraw()
    except Exception as e:
        pytest.skip(f"Tkinter environment not available: {e}")

    orig_esol = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+100,00+100,00+0,00'",
        "NAM+Praxis+++info@praxis.de'",
        "UNT+000006+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "ZHE+110178400+906716934+20250528+3+EN1+04+++++1++1110++0+1+2+00501'",
        "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
        "BES+100,00+20,00+10,00+10,00'",
        "UNT+000009+00002'",
        "UNZ+000002+00118'",
    ])

    orig_file = tmp_path / "test_dialog_move.esol"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    try:
        # 1. Verify First Dialog no longer has rec_nr_entry and rec_date_entry
        dlg1 = CorrectionSelectionDialog(root, str(orig_file))
        assert not hasattr(dlg1, "rec_nr_entry")
        assert not hasattr(dlg1, "rec_date_entry")
        dlg1.destroy()

        # 2. Verify Second Dialog has entry_rec_nr and entry_rec_date in German format (DD.MM.YYYY)
        dlg2 = VKZCorrectionEditorDialog(
            parent=root,
            file_path=str(orig_file),
            selected_belegnr_list=["00001"],
            target_vk="03",
        )
        assert hasattr(dlg2, "entry_rec_nr")
        assert hasattr(dlg2, "entry_rec_date")

        # German date format display
        raw_date_displayed = dlg2.entry_rec_date.get()
        assert "." in raw_date_displayed
        parts = raw_date_displayed.split(".")
        assert len(parts) == 3
        assert len(parts[0]) == 2 and len(parts[1]) == 2 and len(parts[2]) == 4

        # Edit date in German format: 15.09.2026
        dlg2.entry_rec_date.delete(0, "end")
        dlg2.entry_rec_date.insert(0, "15.09.2026")
        assert dlg2.get_current_rec_date_iso() == "20260915"

        # Edit invoice number
        dlg2.entry_rec_nr.delete(0, "end")
        dlg2.entry_rec_nr.insert(0, "RE9999Z")
        assert dlg2.get_current_rec_nr() == "RE9999Z"

        dlg2.destroy()
    finally:
        root.destroy()





# ------------------------------------------- VKZ 03: Bruttobetrag als Schalter

def _vk03_quelle() -> str:
    """Ein Beleg mit echter Zuzahlung — sonst ist am Brutto nichts zu sehen."""
    return "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+845,20+950,10+104,90'",
        "GES+11+845,20+950,10+104,90'",
        "NAM+Ergo Praxis+++info@ergo.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+11000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "ZHE+243203100+565059558+20260116+3+PS3+03+++++1++1000++0+1+3'",
        "EHE+26:00501+54105+10,00+94,89+20260122+9,49'",
        "EHE+26:00501+59702+1,00+1,20+20260116+0,00'",
        "DIA+F98.9'",
        "BES+950,10+104,90+94,90+10,00'",
        "UNT+000012+00002'",
        "UNZ+000002+00118'",
    ])


def _segmente(text: str, tag: str) -> list:
    return [s for s in text.replace("\r\n", "\n").split("\n") if s.startswith(tag + "+")]


def test_vk03_standard_nullt_die_bruttobetraege(tmp_path: Path):
    """
    Der Standard von generate_correction_esol bleibt das Nullen — daran hängt
    die Kommandozeile und der Stapellauf aus der GUI.
    """
    neu = generate_correction_esol(_vk03_quelle(), target_vk="03")

    for ges in _segmente(neu, "GES"):
        felder = ges.rstrip("'").split("+")
        assert felder[3] == "0,00", f"Gesamtbruttobetrag nicht genullt: {ges}"

    # BES ist durch GZF ersetzt, das Bruttofeld also verschwunden
    assert _segmente(neu, "BES") == []
    assert _segmente(neu, "GZF") == ["GZF+104,90+94,90+10,00'"]


def test_vk03_ohne_nullen_behaelt_den_bruttobetrag(tmp_path: Path):
    """
    Mit brutto_nullen=False bleibt die Summe der Leistungspositionen im
    GES-Segment sichtbar. Am Rechnungsbetrag und an GZF ändert sich nichts.
    """
    neu = generate_correction_esol(_vk03_quelle(), target_vk="03", brutto_nullen=False)

    for ges in _segmente(neu, "GES"):
        felder = ges.rstrip("'").split("+")
        assert felder[3] == "950,10", f"Gesamtbruttobetrag fehlt: {ges}"
        # Rechnungsbetrag bleibt die Zuzahlung — daran ändert der Schalter nichts
        assert felder[2] == "104,90"

    assert _segmente(neu, "GZF") == ["GZF+104,90+94,90+10,00'"]


def test_vk03_bes_wird_immer_durch_gzf_ersetzt(tmp_path: Path):
    """
    BES bleibt in keinem der beiden Fälle stehen. Beide naheliegenden
    Alternativen zerstören die Zahlen und sind deshalb ausgeschlossen:

      BES neben GZF  -> Zuzahlung wird doppelt gezählt (Regel 1.3.13.6)
      BES statt GZF  -> GZF fehlt, das bei VK 03 verlangt ist (Regel 1.3.12.1)
    """
    for nullen in (True, False):
        neu = generate_correction_esol(_vk03_quelle(), target_vk="03", brutto_nullen=nullen)
        assert _segmente(neu, "BES") == [], f"brutto_nullen={nullen}"
        assert len(_segmente(neu, "GZF")) == 1, f"brutto_nullen={nullen}"


def test_vk03_ohne_nullen_verletzt_genau_eine_regel(tmp_path: Path):
    """
    Der Schalter weicht bewusst von Regel 1.3.13.5 ab. Er darf aber keine
    weitere Regel verletzen — insbesondere müssen die Zuzahlungssummen
    weiterhin aufgehen (1.3.13.6).
    """
    neu = generate_correction_esol(_vk03_quelle(), target_vk="03", brutto_nullen=False)

    validator = EsolValidator()
    validator.register_default_rules()
    ergebnis = validator.validate_string(neu)

    meldungen = [str(e) for e in ergebnis.get_errors()]
    assert meldungen, "ohne Nullen muss 1.3.13.5 anschlagen"
    for meldung in meldungen:
        assert "1.3.13.5" in meldung, f"unerwartete Regelverletzung: {meldung}"


def test_vk03_positionen_bleiben_in_beiden_faellen_unveraendert(tmp_path: Path):
    """
    Der Schalter betrifft nur die Summen. Die EHE-Zeilen selbst behalten ihre
    Einzelbeträge — die nullt weiterhin nur der Button 'Preise nullen'.
    """
    erwartet = [
        "EHE+26:00501+54105+10,00+94,89+20260122+9,49'",
        "EHE+26:00501+59702+1,00+1,20+20260116+0,00'",
    ]
    for nullen in (True, False):
        neu = generate_correction_esol(_vk03_quelle(), target_vk="03", brutto_nullen=nullen)
        assert _segmente(neu, "EHE") == erwartet, f"brutto_nullen={nullen}"


def test_vk03_segmentzaehler_stimmt_in_beiden_faellen(tmp_path: Path):
    """
    Ohne Nullen kommt BES hinzu — der UNT-Zähler der Nachricht muss das
    mitzählen, sonst weist das Abrechnungszentrum die Datei ab.
    """
    for nullen in (True, False):
        neu = generate_correction_esol(_vk03_quelle(), target_vk="03", brutto_nullen=nullen)
        zeilen = [z for z in neu.replace("\r\n", "\n").split("\n") if z.strip()]

        # Segmente der zweiten Nachricht: von ihrem UNH bis zu ihrem UNT
        start = next(i for i, z in enumerate(zeilen) if z.startswith("UNH+00002"))
        ende = next(i for i, z in enumerate(zeilen) if i > start and z.startswith("UNT+"))
        tatsaechlich = ende - start + 1

        gezaehlt = int(zeilen[ende].rstrip("'").split("+")[1])
        assert gezaehlt == tatsaechlich, (
            f"brutto_nullen={nullen}: UNT sagt {gezaehlt}, gezählt {tatsaechlich}"
        )

    # Der Schalter ändert nur einen Feldwert, kein Segment kommt hinzu oder
    # fällt weg — die Segmentzähler müssen also identisch sein.
    mit = generate_correction_esol(_vk03_quelle(), target_vk="03", brutto_nullen=True)
    ohne = generate_correction_esol(_vk03_quelle(), target_vk="03", brutto_nullen=False)
    assert _segmente(mit, "UNT") == _segmente(ohne, "UNT")
    assert _segmente(mit, "UNZ") == _segmente(ohne, "UNZ")


def test_vk03_standardfassung_ist_gueltig(tmp_path: Path):
    """
    Die Fassung mit genullten Beträgen muss die vollständige Prüfung bestehen —
    das ist die, die die Kommandozeile erzeugt.
    """
    neu = generate_correction_esol(_vk03_quelle(), target_vk="03", brutto_nullen=True)
    validator = EsolValidator()
    validator.register_default_rules()
    ergebnis = validator.validate_string(neu)
    assert ergebnis.is_valid(), [str(e) for e in ergebnis.get_errors()]


def test_vk03_schalter_wirkt_auch_ueber_generate_correction_file(tmp_path: Path):
    quelle = tmp_path / "ESOL_VK03"
    quelle.write_text(_vk03_quelle(), encoding="iso-8859-15")

    mit = generate_correction_file(
        input_path=quelle, output_path=tmp_path / "mit", target_vk="03"
    ).read_text(encoding="iso-8859-15")
    ohne = generate_correction_file(
        input_path=quelle, output_path=tmp_path / "ohne", target_vk="03",
        brutto_nullen=False,
    ).read_text(encoding="iso-8859-15")

    def ges_brutto(text: str) -> set:
        return {s.rstrip("'").split("+")[3] for s in _segmente(text, "GES")}

    assert ges_brutto(mit) == {"0,00"}
    assert ges_brutto(ohne) == {"950,10"}


def test_andere_vkz_bleiben_vom_schalter_unberuehrt(tmp_path: Path):
    """
    brutto_nullen ist ausdrücklich nur für VKZ 03 gedacht. Bei 02, 04 und 10
    darf der Parameter nichts verändern.
    """
    for vk in ("02", "04", "10"):
        a = generate_correction_esol(_vk03_quelle(), target_vk=vk, brutto_nullen=True)
        b = generate_correction_esol(_vk03_quelle(), target_vk=vk, brutto_nullen=False)
        assert a == b, f"VKZ {vk} reagiert auf brutto_nullen"
