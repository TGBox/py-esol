"""
Korrektur zu einer Erstabrechnung in TA-Version 20 (Fall ESOL0037, UNB 24.11.2025):
die Korrektur ist eine neue Lieferung mit heutigem Datum und wird in der aktuellen
Version 21 geschrieben. Hochgestuft wird nur 20 -> 21 und nur die
Nachrichtenkennung im UNH.
"""

from esol_validator import EsolValidator
from tools.generate_correction import _unh_auf_aktuelle_version, generate_correction_esol

ORIGINAL_V20 = (
    "UNB+UNOC:3+123456789+661430035+20251124:1105+00038+B+SL030179S11+2'\n"
    "UNH+00001+SLGA:20:0:0'\n"
    "FKT+01++123456789+101777502+101777502+123456789'\n"
    "REC+19:0+20251124+1'\n"
    "GES+00+100,00+100,00+0,00'\n"
    "GES+11+100,00+100,00+0,00'\n"
    "NAM+Praxis Test+++info@example.de'\n"
    "UNT+000007+00001'\n"
    "UNH+00002+SLLA:20:0:0'\n"
    "FKT+01++123456789+101777502+101777502'\n"
    "REC+19:0+20251124+1'\n"
    "INV+A123456789+10000+1+00001'\n"
    "NAD+Muster+Max+19700101'\n"
    "EHE+26:00502+54145+1,00+100,00+20251110+0,00'\n"
    "ZHE+613851500+675458553+20251101+3+PS4+05+++++1++1000++0+1+0'\n"
    "DIA+F32.1'\n"
    "BES+100,00+0,00+0,00+0,00'\n"
    "UNT+000010+00002'\n"
    "UNZ+000002+00038'\n"
)


def test_unh_wird_von_20_auf_21_gehoben():
    assert _unh_auf_aktuelle_version("UNH+00001+SLGA:20:0:0'") == "UNH+00001+SLGA:21:0:0'"
    assert _unh_auf_aktuelle_version("UNH+00002+SLLA:20:0:0'") == "UNH+00002+SLLA:21:0:0'"


def test_andere_versionen_bleiben_unveraendert():
    # 21 ist schon aktuell; für ältere Versionen ist der Schritt nicht bekannt
    assert _unh_auf_aktuelle_version("UNH+00001+SLGA:21:0:0'") == "UNH+00001+SLGA:21:0:0'"
    assert _unh_auf_aktuelle_version("UNH+00001+SLGA:19:0:0'") == "UNH+00001+SLGA:19:0:0'"


def test_korrektur_zu_v20_original_ist_version_21_und_gueltig():
    neu = generate_correction_esol(
        raw_content=ORIGINAL_V20,
        target_vk="02",
        selected_belegnr_list=["00001"],
        new_rec_nr="0201",
        new_rec_date="20261002",
    )
    assert ":20:0:0" not in neu
    assert "UNH+00001+SLGA:21:0:0'" in neu
    assert "UNH+00002+SLLA:21:0:0'" in neu

    v = EsolValidator()
    v.register_default_rules()
    versionsfehler = [
        e for e in v.validate_string(neu).get_errors() if e.code in ("1.1.12", "1.1.13")
    ]
    assert versionsfehler == []
