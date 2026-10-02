"""
EHE zusammenfassen: gleiche Leistung am gleichen Tag wird über die Anzahl
zusammengefasst (Regel 1.4.1). Anlass: ESOL0083 einer Ergo-Praxis, in der jedes
Zeitintervall einer Blanko-Verordnung als eigenes EHE mit Anzahl 1 stand.
"""

from pathlib import Path

from esol_validator import EsolValidator
from tools.ehe_zusammenfassen import bereinige_datei, zielpfad, zusammenfassen

QUELLE = (
    "UNB+UNOC:3+480806914+104593971+20260128:1106+00084+B+SL080691S01+2'\n"
    "UNH+00001+SLGA:21:0:0'\n"
    "FKT+01++480806914+102171012+102171012+480806914'\n"
    "REC+41:0+20260128+1'\n"
    "GES+00+212,64+232,30+19,66'\n"
    "GES+51+212,64+232,30+19,66'\n"
    "NAM+Praxis+++praxis@example.de'\n"
    "UNT+000007+00001'\n"
    "UNH+00002+SLLA:21:0:0'\n"
    "FKT+01++480806914+102171012+102171012'\n"
    "REC+41:0+20260128+1'\n"
    "INV+K788855693+50000+1+00001'\n"
    "NAD+D´Andrea+Heide+19620525'\n"
    "EHE+26:00502+54145+1,00+19,67+20250905+1,97'\n"
    "EHE+26:00502+54145+1,00+19,67+20250905+1,97'\n"
    "EHE+26:00502+54145+1,00+19,67+20250905+1,97'\n"
    "EHE+26:00502+54145+1,00+18,98+20251001+1,90'\n"
    "EHE+26:00502+54145+1,00+18,98+20251001+1,90'\n"
    "EHE+26:00502+54503+1,00+102,19+20250825+0,00'\n"
    "ZHE+613851500+675458553+20250825+3+PS4+05+++++1++1000++0+1+0'\n"
    "DIA+G30.0'\n"
    "BES+232,30+19,66+9,66+10,00'\n"
    "UNT+000015+00002'\n"
    "UNZ+000002+00084'\n"
)


def test_gleiche_ehe_werden_ueber_anzahl_zusammengefasst():
    neu, bericht = zusammenfassen(QUELLE)

    assert neu.count("EHE+26:00502+54145+3,00+19,67+20250905+1,97'") == 1
    assert neu.count("EHE+26:00502+54145+2,00+18,98+20251001+1,90'") == 1
    assert neu.count("+20250905+") == 1
    assert "EHE+26:00502+54503+1,00+102,19+20250825+0,00'" in neu
    # 15 Segmente - 3 entfernte = 12
    assert "UNT+000012+00002'" in neu
    # erste Nachricht und BES bleiben unverändert
    assert "UNT+000007+00001'" in neu
    assert "BES+232,30+19,66+9,66+10,00'" in neu
    assert bericht[0].startswith("3 EHE-Segment(e) entfernt, 2 zusammengefasst")


def test_reihenfolge_und_zeilenumbrueche_bleiben_erhalten():
    neu, _ = zusammenfassen(QUELLE)
    zeilen = neu.splitlines()
    assert zeilen[13] == "EHE+26:00502+54145+3,00+19,67+20250905+1,97'"
    assert zeilen[14] == "EHE+26:00502+54145+2,00+18,98+20251001+1,90'"
    assert neu.endswith("UNZ+000002+00084'\n")


def test_abweichender_preis_wird_nicht_zusammengefasst():
    text = QUELLE.replace(
        "EHE+26:00502+54145+1,00+18,98+20251001+1,90'\n",
        "EHE+26:00502+54145+1,00+18,98+20251001+1,90'\nEHE+26:00502+54145+1,00+17,00+20251001+1,90'\n",
        1,
    )
    neu, bericht = zusammenfassen(text)
    assert "EHE+26:00502+54145+1,00+17,00+20251001+1,90'" in neu
    assert any("54145 am 20251001" in z and "nicht zusammengefasst" in z for z in bericht)


def test_nichts_zu_tun_laesst_text_unveraendert():
    text = QUELLE.replace("EHE+26:00502+54145+1,00+19,67+20250905+1,97'\n", "", 2)
    text = text.replace("EHE+26:00502+54145+1,00+18,98+20251001+1,90'\n", "", 1)
    neu, bericht = zusammenfassen(text)
    assert neu == text
    assert bericht == []


def test_gleiche_position_in_verschiedenen_belegen_bleibt_getrennt():
    zweiter_beleg = (
        "INV+K111111111+50000+1+00002'\n"
        "NAD+Muster+Max+19700101'\n"
        "EHE+26:00502+54145+1,00+19,67+20250905+1,97'\n"
    )
    text = QUELLE.replace(
        "EHE+26:00502+54145+1,00+18,98+20251001+1,90'\nEHE+26:00502+54145+1,00+18,98+20251001+1,90'\n",
        "EHE+26:00502+54145+1,00+18,98+20251001+1,90'\n" + zweiter_beleg,
        1,
    )
    neu, _ = zusammenfassen(text)
    # Beleg 1: drei -> eins mit 3,00; Beleg 2 behält seine eigene Position
    assert neu.count("+54145+3,00+19,67+20250905+") == 1
    assert neu.count("+54145+1,00+19,67+20250905+") == 1


def test_original_bleibt_kopie_in_bereinigt_als_iso_8859_1(tmp_path: Path):
    quelle = tmp_path / "ESOL0083"
    quelle.write_text(QUELLE, encoding="utf-8")  # so lieferte das Praxisprogramm
    original = quelle.read_bytes()

    ziel, _ = bereinige_datei(quelle)

    assert quelle.read_bytes() == original
    assert ziel == tmp_path / "bereinigt" / "ESOL0083"
    roh = ziel.read_bytes()
    assert b"NAD+D\xb4Andrea" in roh  # ISO-8859-1, nicht UTF-8

    ergebnis = EsolValidator().validate_string(roh.decode("iso-8859-1"))
    assert not [e for e in ergebnis.get_errors() if e.code == "1.4.1"]


def test_ausgabeordner_gleich_quellordner_schreibt_trotzdem_kopie(tmp_path: Path):
    quelle = tmp_path / "ESOL0083"
    assert zielpfad(quelle, tmp_path) == tmp_path / "bereinigt" / "ESOL0083"
    anders = tmp_path / "raus"
    assert zielpfad(quelle, anders) == anders / "ESOL0083"
