import os
import pytest
from pathlib import Path

from tools.generate_begleitzettel import generate_begleitzettel_pdf
from gui_begleitzettel_dialog import extract_begleitzettel_defaults


def test_generate_begleitzettel_pdf(tmp_path):
    out_pdf = str(tmp_path / "test_begleitzettel.pdf")
    data = {
        "absender_name": "Praxis Dr. Test",
        "absender_strasse": "Musterstraße 42",
        "absender_plz_ort": "12345 Musterstadt",
        "absender_telefon": "01234 56789",
        "absender_email": "praxis@test.de",
        "absender_fensterzeile": "Praxis Dr. Test Musterstraße 42 . 12345 Musterstadt",
        "empfaenger_zeile1": "Abrechnungszentrum Nord",
        "empfaenger_zeile2": "Hauptstraße 100",
        "empfaenger_zeile3": "54321 Testort",
        "ik_kostentraeger": "109876543",
        "name_krankenkasse": "AOK Bayern",
        "ik_rechnungssteller": "987654321",
        "name_rechnungssteller": "Praxis Dr. Test",
        "rechnungsnummer": "2026-0001",
        "rechnungsdatum": "27.08.2026",
        "erste_belegnummer": "1001",
        "letzte_belegnummer": "1010",
        "anzahl_urbelege": "10",
    }

    res_path = generate_begleitzettel_pdf(data, out_pdf)
    assert os.path.exists(res_path)
    assert os.path.getsize(res_path) > 1000


def test_extract_begleitzettel_defaults_nonexistent():
    defaults = extract_begleitzettel_defaults(Path("nonexistent_file.txt"))
    assert defaults["ik_kostentraeger"] == ""
    assert defaults["rechnungsnummer"] == ""
    assert defaults["anzahl_urbelege"] == "0"


def test_extract_begleitzettel_defaults_sample(tmp_path):
    sample_esol = (
        "UNB+UNOA:2+987654321:00+108310400:00+260827:1200+1'\n"
        "UNH+1+SLD:0:1:0'\n"
        "FKT+01+20260042+20260827'\n"
        "INV+123456789+00++101'\n"
        "INV+123456790+00++102'\n"
        "UNT+5+1'\n"
        "UNZ+1+1'\n"
    )
    esol_file = tmp_path / "test.esol"
    esol_file.write_text(sample_esol, encoding="utf-8")

    defaults = extract_begleitzettel_defaults(esol_file)
    assert defaults["ik_rechnungssteller"] == "987654321"
    assert defaults["ik_kostentraeger"] == "108310400"
    assert defaults["rechnungsnummer"] == "20260042"
    assert defaults["erste_belegnummer"] == "101"
    assert defaults["letzte_belegnummer"] == "102"
    assert defaults["anzahl_urbelege"] == "2"
