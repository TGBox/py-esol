"""
Tests für die importierten Stammdaten und ihre Auflösung in codelisten.py.

Getestet wird gegen die tatsächlich im Projekt liegenden data/*.json — die
Importer selbst haben eigene Tests mit gebauten Miniquellen. Damit schlägt hier
an, wenn ein Import die Datei kaputt schreibt oder ein Feld umbenennt.
"""

import json
from pathlib import Path

import pytest

import codelisten
import verordnung as vo

DATA = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(autouse=True)
def frische_quellen():
    """
    Jeder Test soll die Dateien aus data/ sehen, nicht einen Cache aus einem
    vorherigen Test, der Umgebungsvariablen gesetzt hatte.
    """
    codelisten.reload()
    yield
    codelisten.reload()


# --------------------------------------------------------------- Dateien da?

@pytest.mark.parametrize("name", [
    "codelisten.json",
    "heilmittelpreise.json",
    "heilmittelkatalog.json",
    "kostentraeger.json",
    "diagnosegruppen.json",
    "verordnungsbedarf.json",
])
def test_datendatei_ist_gueltiges_json(name):
    pfad = DATA / name
    assert pfad.is_file(), f"{name} fehlt — passenden Importer in tools/ ausführen"
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    assert isinstance(daten, dict) and daten


def test_alle_quellen_werden_gefunden():
    assert codelisten.source_path() is not None
    assert codelisten.hmp_source_path() is not None
    assert codelisten.katalog_source_path() is not None
    assert codelisten.kostentraeger_source_path() is not None
    assert codelisten.diagnosegruppen_source_path() is not None
    assert codelisten.verordnungsbedarf_source_path() is not None
    assert codelisten.last_error() is None


def test_quellen_beschreibung_nennt_jede_quelle():
    zeilen = codelisten.quellen_beschreibung()
    assert len(zeilen) == 5
    text = " | ".join(zeilen)
    for stichwort in ("Positionsbezeichnungen", "Heilmittelkatalog",
                      "Institutionskennzeichen", "Diagnosegruppen", "Verordnungsbedarf"):
        assert stichwort in text


# ---------------------------------------------------------- Diagnosegruppen

def test_diagnosegruppen_kommen_aus_der_kbv_stammdatei():
    info = codelisten.diagnosegruppe_info("EN3")
    assert info["quelle"] == "kbv"
    assert info["bezeichnung"] == "Periphere Nervenläsionen / Muskelerkrankungen"
    assert info["bereich"] == "Maßnahmen der Ergotherapie"
    assert info["kapitel"] == "IV"


def test_alle_44_diagnosegruppen_haben_bereich_und_bezeichnung():
    tabelle = codelisten.load_diagnosegruppen()["diagnosegruppen"]
    assert len(tabelle) == 44
    for code, eintrag in tabelle.items():
        assert eintrag["bezeichnung"].strip(), code
        assert eintrag["bereich"].strip(), code


def test_kodierung_der_kbv_datei_ist_repariert():
    """
    Die KBV-XML deklariert ISO-8859-15, enthält aber UTF-8. Ohne Reparatur
    stünde hier "MaÃŸnahmen".
    """
    tabelle = codelisten.load_diagnosegruppen()["diagnosegruppen"]
    bereiche = {e["bereich"] for e in tabelle.values()}
    assert "Maßnahmen der Ergotherapie" in bereiche
    for bereich in bereiche:
        assert "Ã" not in bereich and "Â" not in bereich


def test_describe_diagnosegruppe_ergaenzt_den_bereich():
    text = codelisten.describe_diagnosegruppe("EN1")
    assert text.startswith("EN1 — ")
    assert text.endswith("[Ergotherapie]")
    # Kapitel II heißt im Original "Maßnahmen der Podologischen Therapie" —
    # ein schlichtes Abschneiden ergäbe den Genitiv.
    assert codelisten.describe_diagnosegruppe("UI1").endswith("[Podologie]")


def test_eigene_pflege_ueberstimmt_die_kbv_stammdatei(tmp_path, monkeypatch):
    eigene = tmp_path / "codelisten.json"
    eigene.write_text(
        json.dumps({"diagnosegruppe": {"EN3": "Unsere eigene Formulierung"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PY_ESOL_CODELISTEN", str(eigene))
    codelisten.reload()
    info = codelisten.diagnosegruppe_info("EN3")
    assert info["quelle"] == "codelisten"
    assert info["bezeichnung"] == "Unsere eigene Formulierung"


def test_abweichungen_sind_dokumentiert_aber_nicht_wirksam():
    """
    Die frühere, abweichende Fassung der Diagnosegruppen steht als
    Dokumentation in codelisten.json — sie darf aber nicht nachgeschlagen
    werden.
    """
    daten = codelisten.load()
    assert daten["diagnosegruppe"] == {}
    abweichungen = daten["_abweichungen_diagnosegruppe"]
    assert "SO1" in abweichungen
    assert "Haut" in abweichungen["SO1"]
    # Nachgeschlagen wird die KBV-Fassung
    assert codelisten.lookup("diagnosegruppe", "SO1") == "Störung der Dickdarmfunktion"


def test_der_zhe_klartext_nutzt_die_neue_quelle():
    zhe = vo.decode_zhe(["243203100", "819473253", "20260116", "1", "EN1", "04"])
    assert "ZNS-Erkrankungen" in zhe["diagnosegruppe_text"]
    assert zhe["diagnosegruppe_bereich"] == "Maßnahmen der Ergotherapie"


# ------------------------------------------------------ Institutionskennzeichen

def test_ik_wird_zum_kassennamen_aufgeloest():
    eintrag = codelisten.kostentraeger("101777502")
    assert eintrag["name"] == "TECHNIKER KRANKENKASSE"
    assert eintrag["art"] == "gkv"
    assert eintrag["art_text"] == "Krankenkasse / Kostenträger"
    assert eintrag["ort"] == "Hamburg"


def test_unfallversicherungstraeger_werden_als_solche_erkannt():
    """
    Die UV-Träger stehen auch in der gkvliste, dort aber ohne Kennzeichnung.
    Ohne Sonderregel stünde über einer Berufsgenossenschaft "Krankenkasse".
    """
    eintrag = codelisten.kostentraeger("121192344")
    assert eintrag["art"] == "uv"
    assert eintrag["art_text"] == "Unfallversicherungsträger"
    assert eintrag["name"] == "BG der Bauwirtschaft"
    assert eintrag["zusatz"] == "Hauptverwaltung"


def test_heilfuersorge_wird_als_solche_erkannt():
    assert codelisten.kostentraeger("999999905")["art"] == "heilfuersorge"


def test_unbekanntes_ik_wird_nicht_geraten():
    """
    Leistungserbringer-IKs stehen in keinem Kostenträgerverzeichnis. Das ist
    der Normalfall und muss ausdrücklich als solcher erscheinen.
    """
    assert codelisten.kostentraeger("480512931") == {}
    assert codelisten.ik_name("480512931") == ""
    assert codelisten.describe_ik("480512931") == f"480512931 ({codelisten.KEIN_IK_EINTRAG})"


def test_describe_ik_bei_leerem_wert():
    assert codelisten.describe_ik("") == "—"
    assert codelisten.describe_ik(None) == "—"
    assert codelisten.describe_ik("", leer_text="") == ""


def test_describe_ik_haengt_die_bezirksverwaltung_an():
    assert codelisten.describe_ik("120390887") == \
        "120390887 — BG der Bauwirtschaft, Region Nord"


def test_describe_ik_verschweigt_die_herkunftsangabe():
    """
    'Land HH' ist eine Spalte der Quelldatei, keine Organisationseinheit —
    hinter dem Namen hätte das nichts zu suchen.
    """
    assert codelisten.describe_ik("999999905") == "999999905 — Polizei Hamburg Heilfürsorge"


def test_annahmestelle_wird_mitgeliefert():
    stelle = codelisten.annahmestelle("108036123", "dfu")
    assert stelle["ik"] == "107436557"
    assert stelle["art"] == "03"
    assert "Entschlüsselungsbefugnis" in stelle["art_text"]
    assert codelisten.annahmestelle("480512931") == {}


def test_ik_zeilen_enthalten_anschrift_und_annahmestelle():
    zeilen = codelisten.ik_zeilen("108036123")
    text = "\n".join(zeilen)
    assert zeilen[0].startswith("108036123 — ")
    assert "Stuttgart" in text
    assert "Datenannahmestelle (DFÜ): 107436557" in text
    assert codelisten.ik_zeilen("480512931") == []


def test_eigener_kassenname_ueberstimmt_das_verzeichnis(tmp_path, monkeypatch):
    eigene = tmp_path / "codelisten.json"
    eigene.write_text(
        json.dumps({"kostentraeger": {"101777502": "TK (Hausname)"}}), encoding="utf-8"
    )
    monkeypatch.setenv("PY_ESOL_CODELISTEN", str(eigene))
    codelisten.reload()
    eintrag = codelisten.kostentraeger("101777502")
    assert eintrag["name"] == "TK (Hausname)"
    assert eintrag["quelle"] == "codelisten"
    # Anschrift und Annahmestelle bleiben aus dem Verzeichnis erhalten
    assert eintrag["ort"] == "Hamburg"


# ------------------------------------------------------------- ICD-Codes

@pytest.mark.parametrize("eingabe,code,sicherheit", [
    ("G35.30", "G35.30", ""),
    ("F90.0 G", "F90.0", "G"),
    ("F89G", "F89", "G"),
    ("  M54.5  ", "M54.5", ""),
    ("G35.1-", "G35.1-", ""),
    ("f03v", "F03", "V"),
    ("", "", ""),
    ("Unsinn", "Unsinn", ""),
])
def test_normalisiere_icd(eingabe, code, sicherheit):
    assert codelisten.normalisiere_icd(eingabe) == (code, sicherheit)


def test_verordnungsbedarf_exakter_treffer():
    ergebnis = codelisten.verordnungsbedarf("G35.30")
    assert ergebnis["genau"] is True
    assert ergebnis["quelle_code"] == "G35.30"
    assert ergebnis["anlagen"] == ["BVB"]
    assert "Besonderer Verordnungsbedarf" in ergebnis["text"]


def test_verordnungsbedarf_beachtet_die_diagnosesicherheit():
    ergebnis = codelisten.verordnungsbedarf("F90.0 G")
    assert ergebnis["sicherheit"] == "G"
    assert ergebnis["treffer"], "das Zusatzkennzeichen darf den Treffer nicht verhindern"


def test_verordnungsbedarf_meldet_unterformen():
    """
    Im DIA-Segment steht teils nur die Gruppe (G35), die Stammdatei führt aber
    nur die Endstellen. Dann muss die Anzeige sagen, dass der Eintrag zu den
    Unterformen gehört — und nicht einfach behaupten, G35 selbst stünde drin.
    """
    ergebnis = codelisten.verordnungsbedarf("G35")
    assert ergebnis["treffer"] == []
    assert ergebnis["genau"] is False
    assert len(ergebnis["unterformen"]) >= 5
    assert "nicht für G35 selbst" in ergebnis["text"]
    assert "Unterformen" in ergebnis["text"]


def test_verordnungsbedarf_ohne_eintrag_bleibt_leer():
    for icd in ("G30.1", "M54.5", "F92.8", "", "XYZ"):
        ergebnis = codelisten.verordnungsbedarf(icd)
        assert ergebnis["text"] == "", icd
        assert ergebnis["anlagen"] == [], icd


def test_verordnungsbedarf_zeilen_nennen_diagnosegruppen_und_stand():
    zeilen = codelisten.verordnungsbedarf_zeilen("G81.1")
    text = "\n".join(zeilen)
    assert "Besonderer Verordnungsbedarf" in text
    assert "Maßnahmen der Ergotherapie: EN1" in text
    assert "Stand der Stammdatei" in text
    assert codelisten.verordnungsbedarf_zeilen("M54.5") == []


def test_icd_kandidaten_reihenfolge():
    assert codelisten._icd_kandidaten("G35.30")[:4] == \
        ["G35.30", "G35.30-", "G35.3", "G35.3-"]
    assert codelisten._icd_kandidaten("G35") == ["G35", "G35.-"]


# ------------------------------------------------------- Positionsnummern

def test_positionsnummer_dritte_ebene_heilmittelkatalog():
    """
    Kurort- und Bäderleistungen stehen nicht in der GKV-Stammdatei, aber im
    Heilmittelkatalog.
    """
    info = codelisten.position_info("X6001")
    assert info["quelle"] == "katalog"
    assert info["bezeichnung"] == "Kurmassage/Ganzmassage"


def test_positionsnummer_bg_und_heilpraktiker():
    assert codelisten.position_info("9401")["quelle"] == "katalog"
    assert "Massage" in codelisten.lookup_position("9401")
    assert codelisten.lookup_position("34.1") == "Chiropraktische Behandlung"


def test_gkv_stammdatei_gewinnt_vor_dem_katalog():
    """
    54103 löst über die X-Maske in beiden Quellen auf. Die GKV-Stammdatei ist
    die für die Abrechnung gültige und muss vorgehen.
    """
    info = codelisten.position_info("54103", "26")
    assert info["quelle"] == "hmp"
    assert info["hmp_code"] == "X4103"
    assert info["bezeichnung"] == "Sensomotorisch-perzeptive Behandlung: Einzelbehandlung"


def test_unbekannte_positionsnummer_wird_nicht_geraten():
    assert codelisten.lookup_position("99999", "26") == ""
    assert codelisten.describe_position("99999", "26") == \
        f"99999 ({codelisten.KEIN_KLARTEXT})"


def test_leistungsgruppe_wird_vorangestellt():
    """
    codes.csv nennt zu X4102 nur "bei motorischen Störungen". Ohne die
    Leistungsgruppe davor ist das kein brauchbarer Klartext. Der Test greift
    nur, wenn die GKV-Stammdatei den Code nicht schon kennt.
    """
    eintrag = codelisten.katalog_position("X4201")
    assert eintrag, "X4201 sollte im Heilmittelkatalog stehen"
    if eintrag["bezeichnung"].lower().startswith("je "):
        assert eintrag.get("gruppe_text")
        assert eintrag["bezeichnung"].startswith(eintrag["gruppe_text"])


# --------------------------------------------------- Robustheit der Quellen

def test_fehlende_zusatzquellen_brechen_nichts(tmp_path, monkeypatch):
    """
    Wer die EXE ohne die Importdateien weitergibt, soll ein funktionierendes
    Programm bekommen — nur ohne Klartexte.
    """
    fehlt = tmp_path / "gibt-es-nicht.json"
    for var in ("PY_ESOL_KOSTENTRAEGER", "PY_ESOL_DIAGNOSEGRUPPEN",
                "PY_ESOL_VERORDNUNGSBEDARF", "PY_ESOL_HEILMITTELKATALOG"):
        monkeypatch.setenv(var, str(fehlt))
    codelisten.reload()
    # Fällt auf die Projektdateien zurück; entscheidend ist, dass nichts wirft.
    assert isinstance(codelisten.kostentraeger("101777502"), dict)
    assert isinstance(codelisten.verordnungsbedarf("G35.30"), dict)
    assert isinstance(codelisten.diagnosegruppe_info("EN1"), dict)


def test_defekte_zusatzquelle_bricht_nichts(tmp_path, monkeypatch):
    kaputt = tmp_path / "kostentraeger.json"
    kaputt.write_text("{ kein JSON", encoding="utf-8")
    monkeypatch.setenv("PY_ESOL_KOSTENTRAEGER", str(kaputt))
    codelisten.reload()
    assert isinstance(codelisten.kostentraeger("101777502"), dict)


def test_leere_zusatzquelle_liefert_keinen_klartext(tmp_path, monkeypatch):
    leer = tmp_path / "leer.json"
    leer.write_text("{}", encoding="utf-8")
    for var in ("PY_ESOL_KOSTENTRAEGER", "PY_ESOL_DIAGNOSEGRUPPEN",
                "PY_ESOL_VERORDNUNGSBEDARF", "PY_ESOL_HEILMITTELKATALOG",
                "PY_ESOL_HEILMITTELPREISE", "PY_ESOL_CODELISTEN"):
        monkeypatch.setenv(var, str(leer))
    codelisten.reload()
    assert codelisten.describe_ik("101777502") == f"101777502 ({codelisten.KEIN_IK_EINTRAG})"
    assert codelisten.verordnungsbedarf("G35.30")["text"] == ""
    assert codelisten.describe_diagnosegruppe("EN1") == f"EN1 ({codelisten.KEIN_KLARTEXT})"
    assert codelisten.describe_position("54103", "26") == f"54103 ({codelisten.KEIN_KLARTEXT})"
    assert codelisten.quellen_beschreibung() == []


def test_bereich_kurz():
    assert codelisten.bereich_kurz("Maßnahmen der Podologischen Therapie") == "Podologie"
    assert codelisten.bereich_kurz("Etwas Unbekanntes") == "Etwas Unbekanntes"
    assert codelisten.bereich_kurz("") == ""
    assert codelisten.bereich_kurz(None) == ""
