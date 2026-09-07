"""
Tests für den Import der GKV-Heilmittelpreisstammdatei (tools/import_hmp.py)
und die Auflösung der maskierten ersten Stelle in codelisten.py.

Fachlicher Kern, der hier festgeschrieben wird: die Stammdatei führt Positionen
nach § 125 (Regelversorgung) mit 'X' als erster Stelle (X4103), abgerechnet
werden sie mit der Stelle des Heilmittelbereichs (54103). Ohne diese Auflösung
bleiben genau die Positionen ohne Klartext, die am häufigsten vorkommen.
"""

import json
from pathlib import Path

import pytest

import codelisten
from tools.import_hmp import normalisiere, parse_hmp

# Ausschnitt einer echten HMP-Datei: je eine Position nach § 125a (echter Code)
# und nach § 125 (maskierter Code), plus ein Eintrag ohne Bezeichnung.
HMP_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<HMPRoot HMP_Version="3.0" HMP_Gueltig_ab="2024-01-01" Schema_Version="3.2">
    <HMP>
        <HMP4>54145</HMP4>
        <Heilmittelbereich>Ergotherapie</Heilmittelbereich>
        <Bezeichnung>Psychisch-funktionelle Behandlung: Einzelbehandlung zum Vertrag nach § 125a SGB V</Bezeichnung>
        <Gueltig_ab>2026-07-01</Gueltig_ab>
        <Hoechstpreis>19.76</Hoechstpreis>
        <Bemerkungen>Preis gemäß Vertrag nach § 125a SGB V Blankoversorgung ab 01.07.2026</Bemerkungen>
    </HMP>
    <HMP>
        <HMP4>X4103</HMP4>
        <Heilmittelbereich>Ergotherapie</Heilmittelbereich>
        <Bezeichnung>Sensomotorisch-perzeptive Behandlung: Einzelbehandlung </Bezeichnung>
        <Gueltig_ab>2026-01-01</Gueltig_ab>
        <Hoechstpreis>79.03</Hoechstpreis>
        <Bemerkungen>Preis gemäß Vertrag nach § 125 SGB V ab 01.01.2026</Bemerkungen>
    </HMP>
    <HMP>
        <HMP4>X9999</HMP4>
        <Heilmittelbereich>Physiotherapie</Heilmittelbereich>
        <Bezeichnung></Bezeichnung>
        <Gueltig_ab>2026-01-01</Gueltig_ab>
        <Hoechstpreis>0</Hoechstpreis>
        <Bemerkungen></Bemerkungen>
    </HMP>
</HMPRoot>
"""


@pytest.fixture
def hmp_json(tmp_path: Path, monkeypatch):
    """Importiert die Beispiel-XML und schaltet codelisten.py darauf um."""
    xml = tmp_path / "HMP Stand 01.07.2026.xml"
    xml.write_text(HMP_XML, encoding="utf-8")

    daten = parse_hmp(xml)
    ziel = tmp_path / "heilmittelpreise.json"
    ziel.write_text(json.dumps(daten, ensure_ascii=False), encoding="utf-8")

    # Eigene Codelisten leeren, damit nur die HMP-Quelle greift
    leer = tmp_path / "codelisten.json"
    leer.write_text(json.dumps({"positionsnummern": {"*": {}}}), encoding="utf-8")

    monkeypatch.setenv("PY_ESOL_HEILMITTELPREISE", str(ziel))
    monkeypatch.setenv("PY_ESOL_CODELISTEN", str(leer))
    codelisten.reload()
    try:
        yield daten
    finally:
        monkeypatch.delenv("PY_ESOL_HEILMITTELPREISE", raising=False)
        monkeypatch.delenv("PY_ESOL_CODELISTEN", raising=False)
        codelisten.reload()


# ------------------------------------------------------------- Normalisierung

def test_normalisiere_ersetzt_geschuetztes_leerzeichen():
    """
    Die GKV-Datei setzt zwischen '§' und der Zahl ein geschütztes Leerzeichen
    (U+00A0). Unsichtbar — aber die Volltextsuche im Rezept-Baum findet damit
    "§ 125a" nicht.
    """
    assert normalisiere("Vertrag nach \u00a7\u00a0125a SGB V") == "Vertrag nach \u00a7 125a SGB V"
    assert normalisiere("nach \u00a7\u00a0125a") == "nach \u00a7 125a"
    assert "\u00a0" not in normalisiere("a\u00a0b\u00a0c")


def test_normalisiere_ersetzt_gedankenstriche():
    """Gedankenstriche lassen sich nicht in ISO-8859-15 speichern."""
    assert normalisiere("Gruppe \u20133 \u2013 6 Patienten") == "Gruppe -3 - 6 Patienten"
    assert normalisiere("A \u2014 B") == "A - B"


def test_normalisiere_zieht_leerraum_zusammen():
    assert normalisiere("  viel    Luft \n dazwischen  ") == "viel Luft dazwischen"
    assert normalisiere("") == ""
    assert normalisiere(None) == ""


def test_normalisierte_bezeichnungen_sind_iso_speicherbar():
    """
    Nach dem Import muss jede Bezeichnung in ISO-8859-15 schreibbar sein —
    sonst scheitert der HTML-/Ticket-Export an einem Zeichen aus der Quelle.
    Das Eurozeichen ist erlaubt, es gehört zu ISO-8859-15.
    """
    import codelisten
    codelisten.reload()
    if not codelisten.hmp_source_path():
        pytest.skip("data/heilmittelpreise.json nicht vorhanden")

    for code, eintrag in codelisten.load_hmp()["positionen"].items():
        try:
            eintrag["bezeichnung"].encode("iso-8859-15")
        except UnicodeEncodeError as e:
            pytest.fail(f"{code}: {eintrag['bezeichnung']!r} nicht speicherbar ({e})")


# --------------------------------------------------------------------- Import

def test_import_liest_metadaten(hmp_json):
    q = hmp_json["_quelle"]
    assert q["hmp_version"] == "3.0"
    assert q["schema_version"] == "3.2"
    assert q["datei"] == "HMP Stand 01.07.2026.xml"
    assert q["anzahl_positionen"] == 2  # der Eintrag ohne Bezeichnung fällt raus
    assert q["heilmittelbereiche"] == {"Ergotherapie": 2}


def test_import_ueberspringt_eintraege_ohne_bezeichnung(hmp_json):
    assert "X9999" not in hmp_json["positionen"]
    assert hmp_json["_uebersprungen"] == 1


def test_import_leitet_rechtsgrundlage_ab(hmp_json):
    assert hmp_json["positionen"]["54145"]["grundlage"] == "125a"
    assert hmp_json["positionen"]["X4103"]["grundlage"] == "125"


def test_import_normalisiert_die_bezeichnungen(hmp_json):
    """Die Beispiel-XML enthält '§ 125a' mit normalem Leerzeichen — nach dem
    Import darf nirgends ein geschütztes Leerzeichen stehen."""
    for eintrag in hmp_json["positionen"].values():
        assert "\u00a0" not in eintrag["bezeichnung"]
        assert "  " not in eintrag["bezeichnung"]
        assert eintrag["bezeichnung"] == eintrag["bezeichnung"].strip()


def test_import_uebernimmt_keine_preise(hmp_json):
    """Die Quelle ist laut Haftungsausschluss nicht zu Abrechnungszwecken bestimmt."""
    roh = json.dumps(hmp_json)
    assert "19.76" not in roh
    assert "79.03" not in roh
    assert "Hoechstpreis" not in roh
    for eintrag in hmp_json["positionen"].values():
        assert "preis" not in " ".join(eintrag.keys()).lower()


def test_import_bricht_bei_falschem_wurzelelement_ab(tmp_path: Path):
    fremd = tmp_path / "fremd.xml"
    fremd.write_text("<Irgendwas><A/></Irgendwas>", encoding="utf-8")
    with pytest.raises(ValueError, match="HMPRoot"):
        parse_hmp(fremd)


def test_import_bricht_bei_kaputter_xml_ab(tmp_path: Path):
    kaputt = tmp_path / "kaputt.xml"
    kaputt.write_text("<HMPRoot><HMP>", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_hmp(kaputt)


def test_import_bricht_bei_leerer_stammdatei_ab(tmp_path: Path):
    leer = tmp_path / "leer.xml"
    leer.write_text('<?xml version="1.0"?><HMPRoot/>', encoding="utf-8")
    with pytest.raises(ValueError, match="keine <HMP>"):
        parse_hmp(leer)


# ------------------------------------------------------- Auflösung der X-Maske

def test_echter_code_wird_direkt_gefunden(hmp_json):
    info = codelisten.position_info("54145", "26")
    assert info["quelle"] == "hmp"
    assert info["hmp_code"] == "54145"
    assert info["grundlage"] == "125a"
    assert "Psychisch-funktionelle" in info["bezeichnung"]


def test_maskierter_code_wird_ueber_x_gefunden(hmp_json):
    """54103 muss über X4103 auflösen — das ist der Kern der Einbindung."""
    info = codelisten.position_info("54103", "26")
    assert info["quelle"] == "hmp"
    assert info["hmp_code"] == "X4103"
    assert info["grundlage"] == "125"
    assert info["bezeichnung"].startswith("Sensomotorisch-perzeptive")


def test_x_aufloesung_gilt_fuer_jede_erste_stelle(hmp_json):
    """
    Die erste Stelle steht für den Heilmittelbereich. Die Auflösung darf nicht
    auf die 5 (Ergotherapie) festgenagelt sein.
    """
    for code in ("14103", "24103", "94103"):
        assert codelisten.position_info(code, "26")["hmp_code"] == "X4103"


def test_unbekannter_code_wird_nicht_geraten(hmp_json):
    info = codelisten.position_info("77777", "26")
    assert info["bezeichnung"] == ""
    assert info["quelle"] == ""
    assert codelisten.describe_position("77777", "26") == f"77777 ({codelisten.KEIN_KLARTEXT})"


def test_eigene_pflege_hat_vorrang(tmp_path: Path, monkeypatch, hmp_json):
    """Ein selbst hinterlegter Text muss die Stammdatei überstimmen."""
    eigene = tmp_path / "eigene.json"
    eigene.write_text(json.dumps({
        "positionsnummern": {"26": {"54145": "Eigene Bezeichnung"}}
    }), encoding="utf-8")

    monkeypatch.setenv("PY_ESOL_CODELISTEN", str(eigene))
    codelisten.reload()

    info = codelisten.position_info("54145", "26")
    assert info["bezeichnung"] == "Eigene Bezeichnung"
    assert info["quelle"] == "codelisten"

    # Ein Code, den nur die Stammdatei kennt, kommt weiter von dort
    assert codelisten.position_info("54103", "26")["quelle"] == "hmp"


def test_nicht_existenter_env_pfad_faellt_auf_projektdatei_zurueck(tmp_path: Path, monkeypatch):
    """
    Zeigt PY_ESOL_HEILMITTELPREISE auf eine nicht vorhandene Datei, wird die
    nächste Kandidatendatei genommen (im Entwicklungsbaum data/, im Build die
    Datei neben der EXE). Nichts darf abbrechen.
    """
    monkeypatch.setenv("PY_ESOL_HEILMITTELPREISE", str(tmp_path / "gibtsnicht.json"))
    codelisten.reload()
    try:
        assert isinstance(codelisten.load_hmp(), dict)
        # Kein Absturz, und die Beschreibung ist in jedem Fall ein Einzeiler
        assert isinstance(codelisten.hmp_beschreibung(), str)
    finally:
        monkeypatch.delenv("PY_ESOL_HEILMITTELPREISE", raising=False)
        codelisten.reload()


def test_defekte_hmp_datei_bricht_nichts(tmp_path: Path, monkeypatch):
    """Eine unlesbare Stammdatei darf die GUI nicht abschießen."""
    kaputt = tmp_path / "heilmittelpreise.json"
    kaputt.write_text("{ das ist kein JSON", encoding="utf-8")

    monkeypatch.setenv("PY_ESOL_HEILMITTELPREISE", str(kaputt))
    codelisten.reload()
    try:
        assert isinstance(codelisten.load_hmp(), dict)
        # Der Ladefehler wird gemeldet statt verschluckt
        assert codelisten.last_error() is not None
        assert isinstance(codelisten.describe_position("54103", "26"), str)
    finally:
        monkeypatch.delenv("PY_ESOL_HEILMITTELPREISE", raising=False)
        codelisten.reload()


def test_kurzer_code_bricht_x_aufloesung_nicht(hmp_json):
    """
    Ein einstelliger Code darf keine IndexError-Falle sein.

    Aufgelöst werden darf er trotzdem: das Gebührenverzeichnis für
    Heilpraktiker in data/heilmittelkatalog.json führt die Nummern 1 bis 8.
    Für ESOL ist das folgenlos — Abrechnungspositionsnummern nach § 302 sind
    immer fünfstellig, ein einstelliger Code kommt dort nicht vor. Der Test
    hält nur fest, dass die X-Maske ('X' + Rest) bei Länge 1 nicht zuschlägt
    und nichts wirft.
    """
    einstellig = codelisten.position_info("5", "26")
    # hmp_code nennt den Code, unter dem der Eintrag gefunden wurde. Bei Länge 1
    # darf das nur der Code selbst sein, niemals eine X-Variante.
    assert einstellig["hmp_code"] in ("", "5")
    assert not einstellig["hmp_code"].startswith("X")
    assert einstellig["quelle"] in ("", "katalog")

    leer = codelisten.position_info("", "26")
    assert leer["bezeichnung"] == ""
    assert leer["quelle"] == ""


# --------------------------------------------- Ausgelieferte Projektdatei

def test_projektdatei_deckt_die_testdaten_ab():
    """
    Die im Projekt liegende heilmittelpreise.json muss alle Positionsnummern
    der Testdaten abdecken. Schlägt das fehl, ist der Import veraltet.
    """
    codelisten.reload()
    if not codelisten.hmp_source_path():
        pytest.skip("data/heilmittelpreise.json nicht vorhanden (Import noch nicht gelaufen)")

    # Positionsnummern, die in testdata/in vorkommen (Ergotherapie, Abrechnungscode 26)
    codes = ["54002", "54003", "54102", "54103", "54104", "54105", "54142",
             "54144", "54145", "54251", "54503", "59702", "59741", "59952",
             "59953", "59973", "59974"]

    ohne = [c for c in codes if not codelisten.lookup_position(c, "26")]
    assert ohne == [], f"Ohne Klartext: {ohne}"


# ------------------------------------------------- Paragrafenhinweis in der GUI

def test_grundlage_zusatz_nur_wenn_er_etwas_beitraegt():
    """
    Die § 125a-Bezeichnungen tragen den Paragrafen schon im Text — dann wäre
    ein zusätzlicher Marker doppelt. Bei § 125 fehlt er im Text und ist die
    einzige Unterscheidung zur Blankoversorgung.
    """
    import verordnung as vo

    assert vo.grundlage_zusatz(
        "Psychisch-funktionelle Behandlung: Einzelbehandlung zum Vertrag nach § 125a SGB V",
        "125a") == ""
    assert vo.grundlage_zusatz(
        "Sensomotorisch-perzeptive Behandlung: Einzelbehandlung", "125") \
        == "§ 125 (Regelversorgung)"
    assert vo.grundlage_zusatz(
        "Versorgungsbezogene Pauschale je Blankoverordnung", "125a") \
        == "§ 125a (Blankoversorgung)"
    assert vo.grundlage_zusatz("Irgendwas", "") == ""


def test_grundlage_zusatz_toleriert_geschuetztes_leerzeichen():
    """Falls eine nicht normalisierte Bezeichnung durchkommt."""
    import verordnung as vo
    assert vo.grundlage_zusatz("Vertrag nach \u00a7\u00a0125a SGB V", "125a") == ""
