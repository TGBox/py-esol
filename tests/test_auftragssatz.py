"""Tests für auftragssatz.py — Auftragssatz-Prüfung und Versandweg."""

import os
from pathlib import Path

import pytest

import auftragssatz
import codelisten
from auftragssatz import FEHLER, HINWEIS, OK
from tools.generate_auf import generate_auf

LE = "480512931"
ANNAHME = "661430035"
KASSE = "109938503"        # hat eine eigene DFÜ-Annahmestelle
KASSE_VERWEIS = "104080005"  # verweist auf ein anderes Kostenträger-IK
KASSE_ZIEL = "104940005"
ANDERE_ANNAHME = "660510336"

# Kleine Kostenträgerdatei, damit die Tests nicht vom eingespielten Stand abhängen
_KTR = {
    KASSE: {"name": "TEST-BKK", "annahmestelle": {
        "dfu": {"ik": ANNAHME, "art_text": "Datenannahmestelle ohne Entschlüsselungsbefugnis"}}},
    KASSE_VERWEIS: {"name": "TEST-KASSE", "annahmestelle": {
        "zahlung": {"ik": KASSE_ZIEL}}},
    KASSE_ZIEL: {"name": "TEST-KASSE", "annahmestelle": {
        "dfu": {"ik": ANDERE_ANNAHME}}},
    ANNAHME: {"name": "Annahmestelle A", "email": "annahme@example.org",
              "plz": "04310", "ort": "Leipzig"},
    ANDERE_ANNAHME: {"name": "Annahmestelle B", "email": "b@example.org"},
}


@pytest.fixture(autouse=True)
def kostentraegerdatei(monkeypatch):
    monkeypatch.setattr(codelisten, "kostentraeger",
                        lambda ik: dict(_KTR.get(str(ik or "").strip(), {})))


def _esol(tmp_path: Path, name="ESOL0179", empfaenger=ANNAHME,
          kostentraeger=(KASSE,), zeilenende="\n") -> Path:
    segmente = [f"UNB+UNOC:3+{LE}+{empfaenger}+20260323:1040+00118+B+SL030179S03+2'"]
    for nr, kt in enumerate(kostentraeger, start=1):
        segmente += [
            f"UNH+0000{nr}+SLGA:21:0:0'",
            f"FKT+01++{LE}+{kt}+{kt}+{LE}'",
            "REC+51:0+20260122+1'",
            f"UNT+000004+0000{nr}'",
        ]
    segmente.append("UNZ+000001+00118'")
    pfad = tmp_path / name
    pfad.write_bytes(zeilenende.join(segmente).encode("iso-8859-1") + zeilenende.encode())
    return pfad


def _stufen(bericht, stufe):
    return [b.text for b in bericht.befunde if b.stufe == stufe]


def test_stimmiger_auftragssatz_hat_keine_fehler(tmp_path):
    esol = _esol(tmp_path)
    generate_auf(esol)
    bericht = auftragssatz.pruefe(esol)
    assert _stufen(bericht, FEHLER) == []
    assert any("Datenannahmestelle laut" in t for t in _stufen(bericht, OK))
    text = auftragssatz.bericht_text(bericht)
    assert "annahme@example.org" in text
    assert "Annahmestelle A" in text


def test_auf_datei_als_eingabe_findet_nutzdatei(tmp_path):
    esol = _esol(tmp_path)
    auf = generate_auf(esol)
    bericht = auftragssatz.pruefe(auf)
    assert bericht.nutz_pfad == esol
    assert not bericht.hat_fehler


def test_grossbuchstaben_endung_wird_gefunden(tmp_path):
    esol = _esol(tmp_path)
    auf = generate_auf(esol)
    auf.rename(tmp_path / "ESOL0179.AUF")
    assert auftragssatz.finde_auftragssatz(esol).name == "ESOL0179.AUF"


def test_fehlender_auftragssatz_ist_warnung(tmp_path):
    bericht = auftragssatz.pruefe(_esol(tmp_path))
    assert not bericht.hat_fehler
    assert "Kein Auftragssatz" in bericht.befunde[0].text


def test_groessenabweichung(tmp_path):
    esol = _esol(tmp_path)
    generate_auf(esol)
    with esol.open("ab") as fh:
        fh.write(b"X" * 10)
    bericht = auftragssatz.pruefe(esol)
    assert any("Dateigröße passt nicht" in t and "+10" in t
               for t in _stufen(bericht, FEHLER))


def test_crlf_nach_dem_erstellen_wird_erkannt(tmp_path):
    esol = _esol(tmp_path)
    generate_auf(esol)
    esol.write_bytes(esol.read_bytes().replace(b"\n", b"\r\n"))
    bericht = auftragssatz.pruefe(esol)
    assert bericht.hat_fehler
    assert any("Zeilenumbrüche" in t for t in _stufen(bericht, HINWEIS))


def test_verschluesselt_mit_unverschluesselter_datei_ist_kein_fehler(tmp_path):
    esol = _esol(tmp_path)
    auf = generate_auf(esol)
    satz = auf.read_text(encoding="iso-8859-1")
    groesse = esol.stat().st_size
    # Stellen 191-202 übertragene Größe, 207-208 Verschlüsselung
    satz = satz[:190] + f"{groesse + 5000:012d}" + satz[202:206] + "03" + satz[208:]
    auf.write_text(satz, encoding="iso-8859-1")
    bericht = auftragssatz.pruefe(esol)
    assert _stufen(bericht, FEHLER) == []
    assert any("unverschlüsselte Größe" in t for t in _stufen(bericht, HINWEIS))


def test_absender_und_empfaenger_vertauscht(tmp_path):
    esol = _esol(tmp_path)
    auf = generate_auf(esol)
    satz = auf.read_text(encoding="iso-8859-1")
    absender, empfaenger = LE.ljust(15), ANNAHME.ljust(15)
    satz = satz[:32] + empfaenger * 2 + absender * 2 + satz[92:]
    auf.write_text(satz, encoding="iso-8859-1")
    bericht = auftragssatz.pruefe(esol)
    assert any("vertauscht" in t for t in _stufen(bericht, FEHLER))


def test_falsche_annahmestelle_laut_kostentraegerdatei(tmp_path):
    esol = _esol(tmp_path, empfaenger=ANDERE_ANNAHME)
    generate_auf(esol)
    bericht = auftragssatz.pruefe(esol)
    fehler = _stufen(bericht, FEHLER)
    assert len(fehler) == 1
    assert "nicht die Datenannahmestelle" in fehler[0]
    assert ANNAHME in fehler[0]


def test_verweis_auf_anderes_kostentraeger_ik_wird_verfolgt(tmp_path):
    esol = _esol(tmp_path, empfaenger=ANDERE_ANNAHME, kostentraeger=(KASSE_VERWEIS,))
    generate_auf(esol)
    bericht = auftragssatz.pruefe(esol)
    assert not bericht.hat_fehler
    assert any(KASSE_ZIEL in z for z in bericht.versand)


def test_verschiedene_annahmestellen_in_einer_datei(tmp_path):
    esol = _esol(tmp_path, kostentraeger=(KASSE, KASSE_VERWEIS))
    generate_auf(esol)
    bericht = auftragssatz.pruefe(esol)
    assert any("verschiedene" in t for t in _stufen(bericht, FEHLER))


def test_falsche_satzlaenge_meldet_nur_einen_fehler(tmp_path):
    esol = _esol(tmp_path)
    auf = generate_auf(esol)
    satz = auf.read_text(encoding="iso-8859-1")
    auf.write_text(satz[:30] + "XXXXX" + satz[30:], encoding="iso-8859-1")
    bericht = auftragssatz.pruefe(esol)
    fehler = _stufen(bericht, FEHLER)
    assert len(fehler) == 1 and "353 statt 348" in fehler[0]
    assert bericht.versand  # Versandweg kommt trotzdem aus der Nutzdatendatei


def test_nutzdatei_juenger_als_auftragssatz(tmp_path):
    esol = _esol(tmp_path)
    auf = generate_auf(esol)
    with esol.open("ab") as fh:
        fh.write(b"X")
    alt = os.path.getmtime(esol) - 100
    os.utime(auf, (alt, alt))
    bericht = auftragssatz.pruefe(esol)
    assert any("Änderungsdatum" in t for t in _stufen(bericht, HINWEIS))
