"""
Tests für die Importer in tools/.

Gearbeitet wird mit winzigen, von Hand gebauten Quelldateien: die Tests sollen
die Umsetzungsregeln festhalten, nicht den Inhalt der echten Stammdaten (das
macht test_stammdaten.py). Wichtig sind vor allem die Fälle, in denen sich die
Quellen widersprechen oder kaputt sind.
"""

import importlib.util
import json
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"


def _modul(name: str):
    """Lädt ein Skript aus tools/ als Modul — die Dateien sind keine Pakete."""
    pfad = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


ktr = _modul("import_kostentraeger")
kbv = _modul("import_kbv_stammdaten")
kat = _modul("import_heilmittelkatalog")
hmp = _modul("import_hmp")


# =========================================================== Kostenträger

def _ktr_quellen(tmp_path: Path) -> Path:
    quellen = tmp_path / "quellen"
    quellen.mkdir()

    (quellen / "ktr_parsed.json").write_text(json.dumps({
        "101777502": {
            "IK": "101777502", "Name": "Musterkasse", "eMail": "da@muster.de",
            "VKGDFU": {"Art": "03", "IK": "661430035", "Tarifkennzeichen": "99"},
            "VKGANS": {}, "VKGZIEL": {"Art": "01", "IK": "101777502"},
            "ANS": {"PLZ": "22305", "Ort": "Hamburg", "StrassePostfach": "Musterweg 1"},
        },
        "kopfzeile": {"Name": "wird ignoriert"},
    }), encoding="utf-8")

    (quellen / "ktr_heilfuersorge.json").write_text(json.dumps({
        "999999901": {
            "IK": "999999901", "Name": "Ärztlicher Dienst", "Bundesland": "BY",
            "eMail": "", "VKGDFU": {}, "VKGANS": {}, "VKGZIEL": {},
            "ANS": {"PLZ": "81669", "Ort": "München", "StrassePostfach": "Rosenheimer Str. 130"},
        },
    }), encoding="utf-8")

    # Die gkvliste führt den UV-Träger mit, aber ohne Kennzeichnung und mit
    # abweichendem Namen — genau der Fall, den bgliste korrigieren muss.
    (quellen / "gkvliste.txt").write_text(
        "Kassen-IK\tKassen Bezeichnung\tPLZ\tOrt\tStraße\n"
        "121192344\tBG Bau Mitte\t51065\tKöln\tEulenbergstr. 13\n"
        "108018132\tAOK Musterland\t71332\tWaiblingen\tSchorndorfer Str. 32\n",
        encoding="utf-8",
    )

    (quellen / "bgliste.txt").write_text(
        'IK;Nachfolge IK;Gültig ab;Gültig bis;Name1;Name2;Strasse;Land;PLZ;Ort-BG;'
        'Vorwahl;Tel-Nr;Fax-Nr;IK-UNIDAV;"KIM UNI-DAV"\n'
        "121192344;;01.01.2016;;BG der Bauwirtschaft;Hauptverwaltung;"
        "Hildegardstr. 29;DE;10715;Berlin;030;857810;85781500;120591481;"
        "dale-uv@dguv.kim.telematik\n",
        encoding="utf-8",
    )
    return quellen


def test_kostentraeger_fuehrt_alle_quellen_zusammen(tmp_path):
    daten = ktr.baue_tabelle(_ktr_quellen(tmp_path))
    traeger = daten["traeger"]
    assert set(traeger) == {"101777502", "999999901", "121192344", "108018132"}
    assert daten["_quelle"]["anzahl_ik"] == 4
    assert daten["_quelle"]["fehlende_dateien"] == []


def test_kostentraeger_ignoriert_nicht_neunstellige_schluessel(tmp_path):
    traeger = ktr.baue_tabelle(_ktr_quellen(tmp_path))["traeger"]
    assert "kopfzeile" not in traeger
    # Die Kopfzeile der gkvliste ist kein IK und darf nicht als Träger landen
    assert "Kassen-IK" not in traeger


def test_bgliste_setzt_art_und_namen_durch(tmp_path):
    """
    Die gkvliste wird nach der bgliste gelesen und darf den UV-Träger nicht
    zur Krankenkasse machen — sonst stünde in der Hotline "Krankenkasse" über
    einer Berufsgenossenschaft.
    """
    eintrag = ktr.baue_tabelle(_ktr_quellen(tmp_path))["traeger"]["121192344"]
    assert eintrag["art"] == ktr.ART_UV
    assert eintrag["name"] == "BG der Bauwirtschaft"
    assert eintrag["zusatz"] == "Hauptverwaltung"
    assert eintrag["gueltig_ab"] == "01.01.2016"
    assert eintrag["quelle"] == "bgliste"


def test_kostentraeger_uebernimmt_keine_telefonnummern(tmp_path):
    eintrag = ktr.baue_tabelle(_ktr_quellen(tmp_path))["traeger"]["121192344"]
    text = json.dumps(eintrag, ensure_ascii=False)
    for nummer in ("857810", "85781500", "030"):
        assert nummer not in text


def test_kostentraeger_annahmestelle_wird_flach_abgelegt(tmp_path):
    eintrag = ktr.baue_tabelle(_ktr_quellen(tmp_path))["traeger"]["101777502"]
    dfu = eintrag["annahmestelle"]["dfu"]
    assert dfu["ik"] == "661430035"
    assert dfu["art"] == "03"
    assert "Entschlüsselungsbefugnis" in dfu["art_text"]
    assert "papier" not in eintrag["annahmestelle"], "leeres VKGANS erzeugt keinen Eintrag"


def test_kostentraeger_bundesland_landet_im_zusatz(tmp_path):
    eintrag = ktr.baue_tabelle(_ktr_quellen(tmp_path))["traeger"]["999999901"]
    assert eintrag["zusatz"] == "Land BY"
    assert eintrag["art"] == ktr.ART_HEILFUERSORGE


def test_kostentraeger_ohne_quellen_wirft(tmp_path):
    leer = tmp_path / "leer"
    leer.mkdir()
    with pytest.raises(ValueError, match="Keine der Kostenträger-Quellen"):
        ktr.baue_tabelle(leer)


def test_kostentraeger_teilweise_vorhandene_quellen(tmp_path):
    quellen = _ktr_quellen(tmp_path)
    (quellen / "bgliste.txt").unlink()
    daten = ktr.baue_tabelle(quellen)
    assert "bgliste.txt" in daten["_quelle"]["fehlende_dateien"]
    # Ohne bgliste bleibt der UV-Träger als gkv gekennzeichnet — das ist die
    # ehrliche Folge einer fehlenden Quelle, kein Fehler.
    assert daten["traeger"]["121192344"]["art"] == ktr.ART_GKV


# ============================================================ KBV-Stammdaten

_SDHM = """<?xml version="1.0" encoding="ISO-8859-15"?>
<ehd ehd_version="1.40" xmlns="urn:ehd/001">
  <header>
    <interface.nm V="Heilmittelstammdatei"/>
    <version V="2.10"/>
    <service_tmr V="2024-10-01.."/>
  </header>
  <body><sdhm_stammdaten>
    <kapitel V="I. Maßnahmen der Physiotherapie">
      <diagnosegruppe V="WS" DN="Wirbelsäulenerkrankungen"/>
      <diagnosegruppe V="SO1" DN="Störung der Dickdarmfunktion"/>
      <diagnosegruppe V="LEER" DN=""/>
    </kapitel>
    <kapitel V="IV. Maßnahmen der Ergotherapie">
      <diagnosegruppe V="EN3" DN="Periphere Nervenläsionen"/>
    </kapitel>
  </sdhm_stammdaten></body>
</ehd>
"""

_SDHMA = """<?xml version="1.0" encoding="ISO-8859-15"?>
<ehd:ehd ehd_version="1.40" xmlns:ehd="urn:ehd/001" xmlns="urn:ehd/sdhma/001">
  <ehd:header>
    <ehd:interface.nm V="sdhma-Stammdatei"/>
    <ehd:version V="1.30"/>
    <ehd:service_tmr V="2022-01-01.."/>
  </ehd:header>
  <ehd:body><sdhma_stammdaten><verordnungsbedarf_liste>
    <verordnungsbedarf>
      <geltungsbereich_kv V="38"/>
      <heilmittel_liste><heilmittel>
        <anlage_heilmittelvereinbarung V="LHM" DN="Langfristiger Heilmittelbedarf"/>
        <hinweistext V="Nur bei schwerer Ausprägung"/>
        <untere_altersgrenze V="18" U="a"/>
        <sekundaercode V="G82.4"/>
        <kapitel_liste><kapitel V="IV" DN="Maßnahmen der Ergotherapie">
          <diagnosegruppe_liste>
            <diagnosegruppe V="EN1" DN="ZNS-Erkrankungen"/>
            <diagnosegruppe V="EN3" DN="Periphere Nervenläsionen"/>
          </diagnosegruppe_liste>
        </kapitel></kapitel_liste>
      </heilmittel></heilmittel_liste>
      <icd_code V="G81.1"/>
      <icd_code V="G81.9"/>
    </verordnungsbedarf>
    <verordnungsbedarf>
      <heilmittel_liste><heilmittel>
        <anlage_heilmittelvereinbarung V="BVB" DN="Besondere Verordnungsbedarfe"/>
        <kapitel_liste><kapitel V="I" DN="Physiotherapie"><diagnosegruppe_liste>
          <diagnosegruppe V="ZN" DN="ZNS"/>
        </diagnosegruppe_liste></kapitel></kapitel_liste>
      </heilmittel></heilmittel_liste>
    </verordnungsbedarf>
  </verordnungsbedarf_liste></sdhma_stammdaten></ehd:body>
</ehd:ehd>
"""


def _schreibe(tmp_path: Path, name: str, inhalt: str) -> Path:
    """
    Schreibt die Fixture als UTF-8, obwohl der XML-Prolog ISO-8859-15
    behauptet — genau so liefert die KBV ihre Dateien. Erst dadurch sieht der
    Parser die verfälschten Umlaute, die repariere_kodierung() zurückdrehen
    muss. Die Fixtures selbst enthalten deshalb echte Umlaute, keine
    vorweggenommene Verfälschung.
    """
    pfad = tmp_path / name
    pfad.write_bytes(inhalt.encode("utf-8"))
    return pfad


# Die verfälschten Formen sind hier absichtlich als Escape-Sequenzen
# geschrieben. Sie entstehen, wenn UTF-8-Bytes als ISO-8859-15 gelesen werden:
# 'ß' ist UTF-8 C3 9F und wird damit zu 'Ã'. Wer die Verfälschung
# nach Augenmaß hinschreibt ("MaÃŸnahmen" mit U+0178), trifft andere Bytes und
# testet etwas, das in echten Dateien nicht vorkommt.
@pytest.mark.parametrize("kaputt,erwartet", [
    ("MaÃnahmen", "Maßnahmen"),
    ("WirbelsÃ¤ulenerkrankungen", "Wirbelsäulenerkrankungen"),
    ("StÃ¶rung", "Störung"),
    ("NervenlÃ¤sionen", "Nervenläsionen"),
    ("AussprÃ¤gung", "Aussprägung"),
])
def test_repariere_kodierung(kaputt, erwartet):
    assert kbv.repariere_kodierung(kaputt) == erwartet


def test_repariere_kodierung_laesst_korrekten_text_in_ruhe():
    for text in ("Maßnahmen der Physiotherapie", "Wirbelsäulenerkrankungen", "", "ABC"):
        assert kbv.repariere_kodierung(text) == text


def test_sdhm_liest_kapitel_und_diagnosegruppen(tmp_path):
    daten = kbv.parse_sdhm(_schreibe(tmp_path, "sdhm.xml", _SDHM))
    gruppen = daten["diagnosegruppen"]
    assert set(gruppen) == {"WS", "SO1", "EN3"}
    assert gruppen["WS"]["bezeichnung"] == "Wirbelsäulenerkrankungen"
    assert gruppen["WS"]["bereich"] == "Maßnahmen der Physiotherapie"
    assert gruppen["WS"]["kapitel"] == "I"
    assert gruppen["EN3"]["kapitel"] == "IV"
    # Die Kapitelnummer ist die laufende Nummer, nicht die römische Zahl
    assert gruppen["EN3"]["kapitel_nummer"] == "2"


def test_sdhm_ueberspringt_gruppen_ohne_bezeichnung(tmp_path):
    daten = kbv.parse_sdhm(_schreibe(tmp_path, "sdhm.xml", _SDHM))
    assert "LEER" not in daten["diagnosegruppen"]


def test_sdhm_wirft_bei_falscher_datei(tmp_path):
    pfad = _schreibe(tmp_path, "sdhm.xml", '<?xml version="1.0"?><etwas/>')
    with pytest.raises(ValueError, match="keine <kapitel>"):
        kbv.parse_sdhm(pfad)


def test_sdhm_wirft_bei_kaputtem_xml(tmp_path):
    pfad = _schreibe(tmp_path, "sdhm.xml", "<ehd><nicht geschlossen>")
    with pytest.raises(ValueError, match="keine gültige XML"):
        kbv.parse_sdhm(pfad)


def test_sdhma_bildet_jeden_icd_auf_seine_eintraege_ab(tmp_path):
    daten = kbv.parse_sdhma(_schreibe(tmp_path, "sdhma.xml", _SDHMA))
    icd = daten["icd"]
    assert set(icd) == {"G81.1", "G81.9"}
    eintrag = icd["G81.1"][0]
    assert eintrag["anlage"] == "LHM"
    assert eintrag["anlage_text"] == "Langfristiger Heilmittelbedarf (Anlage 2)"
    assert eintrag["hinweis"] == "Nur bei schwerer Ausprägung"
    assert eintrag["alter_ab"] == "18 Jahre"
    assert eintrag["sekundaercode"] == ["G82.4"]
    assert eintrag["geltungsbereich_kv"] == ["38"]
    assert eintrag["kapitel"][0]["diagnosegruppen"] == ["EN1", "EN3"]


def test_sdhma_zaehlt_eintraege_ohne_icd_code(tmp_path):
    daten = kbv.parse_sdhma(_schreibe(tmp_path, "sdhma.xml", _SDHMA))
    assert daten["_quelle"]["ohne_icd_code"] == 1
    assert daten["_quelle"]["anzahl_icd"] == 2


def test_sdhma_wirft_bei_falscher_datei(tmp_path):
    pfad = _schreibe(tmp_path, "sdhma.xml", '<?xml version="1.0"?><etwas/>')
    with pytest.raises(ValueError, match="keine <verordnungsbedarf>"):
        kbv.parse_sdhma(pfad)


def test_altersgrenze_einheiten(tmp_path):
    import xml.etree.ElementTree as ET
    for wert, einheit, erwartet in (("18", "a", "18 Jahre"), ("6", "mo", "6 Monate"),
                                    ("3", "wk", "3 Wochen"), ("", "a", "")):
        el = ET.Element("x", {"V": wert, "U": einheit})
        assert kbv._altersgrenze(el) == erwartet


# ========================================================= Heilmittelkatalog

def _kat_quellen(tmp_path: Path) -> Path:
    quellen = tmp_path / "quellen"
    quellen.mkdir()
    (quellen / "heilmittelpreise.csv").write_text(
        "kapitel;hmcode;preis;bezeichnung\n"
        "4;X4102;43.56;Motorisch-funktionelle Behandlung: Einzelbehandlung\n"
        "2;X8010;30.7;Podologische Behandlung (klein)\n"
        "4;X4405;;Schiene ohne Kostenvoranschlag\n",
        encoding="utf-8",
    )
    (quellen / "codes.csv").write_text(
        "code;hmcode;leistung\n"
        "X4102;X4102;bei motorischen Störungen\n"
        "X4201;X4201;je Teilnehmer\n"
        "X6001;X6001;Kurmassage/Ganzmassage\n"
        "X9922;X9922;UNBESETZT\n",
        encoding="utf-8",
    )
    (quellen / "codesgroups.csv").write_text(
        "id;group\n42;Gruppenbehandlung\n41;Einzelbehandlung\n99;44\n",
        encoding="utf-8",
    )
    (quellen / "bgleistungen.csv").write_text(
        "bezeichnung;code;einzelpreis;gruppe;hmcode\n"
        "Massage;8401;22.47;BG-Leistung Physio;1\n",
        encoding="utf-8",
    )
    (quellen / "heilmittelleistungen_heilpraktiker.csv").write_text(
        "code;bezeichnung;einzelpreis;gruppe\n"
        "34.1;Chiropraktische Behandlung;18.00;HP Gelenkbehandlung\n",
        encoding="utf-8",
    )
    return quellen


def test_katalog_uebernimmt_keine_preise(tmp_path):
    daten = kat.baue_katalog(_kat_quellen(tmp_path))
    text = json.dumps(daten, ensure_ascii=False)
    for preis in ("43.56", "30.7", "22.47", "18.00"):
        assert preis not in text, f"Preis {preis} darf nicht importiert werden"
    for eintrag in daten["positionen"].values():
        assert "preis" not in eintrag and "einzelpreis" not in eintrag


def test_katalog_heilmittelpreise_gewinnt_vor_codes_csv(tmp_path):
    """
    Beide Quellen kennen X4102. heilmittelpreise.csv hat den ausformulierten
    Text, codes.csv nur den Zusatz — die erste Quelle muss gewinnen.
    """
    daten = kat.baue_katalog(_kat_quellen(tmp_path))
    eintrag = daten["positionen"]["X4102"]
    assert eintrag["bezeichnung"] == "Motorisch-funktionelle Behandlung: Einzelbehandlung"
    assert eintrag["quelle"] == "heilmittelpreise"
    assert "X4102" in daten["_abweichende_bezeichnungen"]


def test_katalog_leitet_bereich_aus_dem_kapitel_ab(tmp_path):
    positionen = kat.baue_katalog(_kat_quellen(tmp_path))["positionen"]
    assert positionen["X8010"]["bereich"] == "Maßnahmen der Podologischen Therapie"
    assert positionen["X8010"]["kapitel"] == "2"


def test_katalog_uebernimmt_unbesetzte_codes_nicht(tmp_path):
    assert "X9922" not in kat.baue_katalog(_kat_quellen(tmp_path))["positionen"]


def test_katalog_leistungsgruppen_ohne_datenfehler(tmp_path):
    """Die Quelldatei enthält die Zeile "99;44" — eine Zahl ist keine Gruppe."""
    gruppen = kat.baue_katalog(_kat_quellen(tmp_path))["leistungsgruppen"]
    assert gruppen == {"41": "Einzelbehandlung", "42": "Gruppenbehandlung"}


def test_katalog_kennt_bg_und_heilpraktiker_nummernkreise(tmp_path):
    positionen = kat.baue_katalog(_kat_quellen(tmp_path))["positionen"]
    assert positionen["8401"]["quelle"] == "bg"
    assert positionen["8401"]["bereich"] == "BG-Leistung Physio"
    assert positionen["34.1"]["quelle"] == "heilpraktiker"


def test_katalog_ohne_quellen_wirft(tmp_path):
    leer = tmp_path / "leer"
    leer.mkdir()
    with pytest.raises(ValueError, match="Keine Positionsverzeichnisse"):
        kat.baue_katalog(leer)


def test_katalog_liest_iso_8859_15(tmp_path):
    quellen = tmp_path / "q"
    quellen.mkdir()
    (quellen / "codes.csv").write_text(
        "code;hmcode;leistung\nX0107;X0107;Bindegewebsmassage für Rücken\n",
        encoding="iso-8859-15",
    )
    positionen = kat.baue_katalog(quellen)["positionen"]
    assert positionen["X0107"]["bezeichnung"] == "Bindegewebsmassage für Rücken"


# ==================================================== HMP: mehrere Dateien

_HMP_KOPF = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<HMPRoot HMP_Version="3.0" Schema_Version="3.2">')


def _hmp_datei(tmp_path: Path, name: str, eintraege: str) -> Path:
    pfad = tmp_path / name
    pfad.write_text(_HMP_KOPF + eintraege + "</HMPRoot>", encoding="utf-8")
    return pfad


def test_hmp_mehrere_dateien_erste_gewinnt(tmp_path):
    neu = _hmp_datei(tmp_path, "neu.xml",
                     "<HMP><HMP4>54142</HMP4><Heilmittelbereich>Ergotherapie</Heilmittelbereich>"
                     "<Bezeichnung>Neue Fassung zum Vertrag nach § 125a SGB V</Bezeichnung>"
                     "<Gueltig_ab>2026-07-01</Gueltig_ab></HMP>")
    alt = _hmp_datei(tmp_path, "alt.xml",
                     "<HMP><HMP4>54142</HMP4><Heilmittelbereich>Ergotherapie</Heilmittelbereich>"
                     "<Bezeichnung>Alte Fassung</Bezeichnung>"
                     "<Gueltig_ab>2025-08-01</Gueltig_ab></HMP>"
                     "<HMP><HMP4>54999</HMP4><Heilmittelbereich>Ergotherapie</Heilmittelbereich>"
                     "<Bezeichnung>Nur in der alten Datei</Bezeichnung></HMP>")

    daten = hmp.parse_mehrere([neu, alt])
    positionen = daten["positionen"]
    assert positionen["54142"]["bezeichnung"].startswith("Neue Fassung")
    assert positionen["54999"]["bezeichnung"] == "Nur in der alten Datei"
    assert "54142" in daten["_doppelte_codes"]
    assert [q["datei"] for q in daten["_quelle"]["dateien"]] == ["neu.xml", "alt.xml"]
    assert daten["_quelle"]["datei"] == "neu.xml + alt.xml"
    assert daten["_quelle"]["anzahl_positionen"] == 2


def test_hmp_einzelne_datei_bleibt_kompatibel(tmp_path):
    eine = _hmp_datei(tmp_path, "eine.xml",
                      "<HMP><HMP4>X4103</HMP4><Heilmittelbereich>Ergotherapie</Heilmittelbereich>"
                      "<Bezeichnung>Sensomotorisch-perzeptive Behandlung</Bezeichnung></HMP>")
    daten = hmp.parse_mehrere([eine])
    assert daten["_quelle"]["datei"] == "eine.xml"
    assert daten["_quelle"]["hmp_version"] == "3.0"
    assert daten["positionen"]["X4103"]["bereich"] == "Ergotherapie"
