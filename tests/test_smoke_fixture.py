"""
Prüft die Referenzdatei tests/fixtures/valid_esol_smoke.

Diese Datei ist der kleinste vollständige, gültige ESOL-Vorgang (SLGA + SLLA
mit einem Beleg) und wird an zwei Stellen gebraucht:

  * hier, als End-to-End-Test der Validierungs-Engine mit einer bekannt
    gültigen Eingabedatei — die übrigen Tests prüfen fast nur, dass Fehler
    erkannt werden;
  * im CI-Build, als Rauchtest der fertigen py-esol.exe. Läuft die
    Validierung dort durch, sind Regelwerk, Schema und Parser vollständig
    im PyInstaller-Bundle enthalten.

Schlägt dieser Test fehl, ist entweder eine Regel strenger geworden (dann die
Fixture anpassen) oder eine Regel kaputt.
"""

from pathlib import Path

import pytest

from esol_validator import EsolValidator
from tools.generate_correction import parse_esol_belege_summary, read_esol_file_text

FIXTURE = Path(__file__).parent / "fixtures" / "valid_esol_smoke"


def test_fixture_existiert():
    assert FIXTURE.is_file(), (
        "tests/fixtures/valid_esol_smoke fehlt — die Datei wird auch vom "
        "CI-Rauchtest der EXE gebraucht."
    )


def test_fixture_ist_iso_8859_15_mit_crlf():
    roh = FIXTURE.read_bytes()
    # Muss sich strikt als ISO-8859-15 lesen lassen (echte ESOL-Vorgabe)
    roh.decode("iso-8859-15")
    assert b"\r\n" in roh, "ESOL-Dateien verwenden CRLF"


def test_fixture_ist_ohne_fehler_und_warnungen_gueltig():
    validator = EsolValidator()
    validator.register_default_rules()
    validator.set_max_stufe(4)

    ergebnis = validator.validate(str(FIXTURE))

    assert ergebnis.error_count() == 0, [str(e) for e in ergebnis.get_errors()]
    # Auch warnungsfrei: die IKs in der Fixture haben gültige Prüfziffern.
    assert ergebnis.warning_count() == 0, [str(w) for w in ergebnis.get_warnings()]
    assert ergebnis.is_valid()


def test_fixture_enthaelt_einen_auswertbaren_beleg():
    belege = parse_esol_belege_summary(read_esol_file_text(FIXTURE))

    assert len(belege) == 1
    beleg = belege[0]

    assert beleg["belegnr"] == "00001"
    assert beleg["nachname"] == "Muster"
    assert beleg["brutto"] == pytest.approx(100.0)
    assert beleg["total_zuzahlung"] == pytest.approx(20.0)

    # Verordnungsdaten müssen vollständig ausgewertet sein
    z = beleg["verordnung"]
    assert not z.get("fehlt")
    assert z["verordnungsdatum"] == "20250528"
    assert z["diagnosegruppe"] == "EN1"
    assert z["leitsymptomatik"] == "1110"
    assert [d["code"] for d in beleg["diagnosen"]] == ["F98.9"]
