"""
Tests für die Verordnungs-Auswertung (verordnung.py) und die editierbaren
Klartext-Tabellen (codelisten.py).
"""

import json
from pathlib import Path

import pytest

import codelisten
import verordnung as vo
from tools.generate_correction import parse_esol_belege_summary

# Ein vollständiger SLLA-Beleg mit ZHE, zwei Diagnosen und Wiederholungsterminen
RAW_BELEG = "\n".join([
    "UNB+UNOC:3+123456789+661430035+20260408:1200+00151+B+SL051293S04+2'",
    "UNH+00001+SLGA:21:0:0'",
    "FKT+01++123456789+101777502+101777502+123456789'",
    "REC+76:0+20260408+1'",
    "GES+00+237,49+237,49+33,77'",
    "NAM+Testpraxis'",
    "UNT+000006+00001'",
    "UNH+00002+SLLA:21:0:0'",
    "FKT+01++123456789+101777502+101777502'",
    "REC+76:0+20260408+1'",
    "INV+Z198653476+50000+1+00062'",
    "NAD+Bail+Ludwig+19460530'",
    "EHE+26:00502+54145+5,00+18,98+20260123+1,90'",
    "EHE+26:00502+54145+5,00+18,98+20260130+1,90'",
    "EHE+26:00502+54003+1,00+47,69+20260123+4,77'",
    "ZHE+273806900+388623551+20260113+3+PS4+05+++++1++1100++0+1+3'",
    "DIA+G30.1'",
    "DIA+F00.1'",
    "BES+237,49+33,77+23,77+10,00'",
    "UNT+000010+00002'",
    "UNZ+000002+00151'",
])


@pytest.fixture
def beleg():
    belege = parse_esol_belege_summary(RAW_BELEG)
    assert len(belege) == 1
    return belege[0]


# ------------------------------------------------------------------ Formatierung

def test_fmt_datum():
    assert vo.fmt_datum("20260113") == "13.01.2026"
    assert vo.fmt_datum("") == ""
    assert vo.fmt_datum("Unsinn") == "Unsinn"


def test_fmt_betrag_deutsch():
    assert vo.fmt_betrag(1234.5) == "1.234,50 €"
    assert vo.fmt_betrag("18,98") == "18,98 €"
    assert vo.fmt_betrag(0) == "0,00 €"


# --------------------------------------------------------------- Leitsymptomatik

def test_leitsymptomatik_einzelne_stellen():
    d = vo.decode_leitsymptomatik("1000")
    assert d["valide"] and d["stellen"] == ["a"]
    assert not d["individuell"]

    d = vo.decode_leitsymptomatik("1100")
    assert d["stellen"] == ["a", "b"]


def test_leitsymptomatik_individuell():
    d = vo.decode_leitsymptomatik("0001")
    assert d["individuell"] is True

    d = vo.decode_leitsymptomatik("9999")
    assert d["individuell"] is True
    assert "patientenindividuell" in d["text"]


def test_leitsymptomatik_ungueltig():
    assert vo.decode_leitsymptomatik("12")["valide"] is False
    assert vo.decode_leitsymptomatik("12ab")["valide"] is False
    assert vo.decode_leitsymptomatik("")["valide"] is False


# -------------------------------------------------------------------- ZHE-Decode

def test_zhe_felder_vollstaendig(beleg):
    z = beleg["verordnung"]
    assert not z.get("fehlt")
    assert z["bsnr"] == "273806900"
    assert z["lanr"] == "388623551"
    assert z["verordnungsdatum"] == "20260113"
    assert z["verordnungsdatum_text"] == "13.01.2026"
    assert z["zuzahlungskennzeichen"] == "3"
    assert z["diagnosegruppe"] == "PS4"
    assert z["verordnungsart"] == "05"
    assert z["therapiebericht"] == "1"
    assert z["leitsymptomatik"] == "1100"
    assert z["heilmittelbereich"] == "1"
    assert z["therapiefrequenz"] == "3"
    assert "BSNR 273806900" in z["arzt_text"]
    assert "LANR 388623551" in z["arzt_text"]


def test_zhe_fehlt_wird_erkannt():
    raw = "\n".join([
        "UNH+00002+SLLA:21:0:0'",
        "INV+A1+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+54103+1,00+10,00+20260115+0,00'",
        "BES+10,00+0,00+0,00+0,00'",
    ])
    b = parse_esol_belege_summary(raw)[0]
    assert b["verordnung"]["fehlt"] is True
    stufen = [h["stufe"] for h in b["verordnung_hinweise"]]
    assert "fehler" in stufen


# ------------------------------------------------------------ Diagnosen / SKZ / Kontext

def test_diagnosen_werden_gesammelt(beleg):
    codes = [d["code"] for d in beleg["diagnosen"]]
    assert codes == ["G30.1", "F00.1"]


def test_diagnosetext_wird_uebernommen():
    raw = "\n".join([
        "UNH+00002+SLLA:21:0:0'",
        "INV+A1+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+54103+1,00+10,00+20260115+0,00'",
        "ZHE+111111111+222222222+20260101+0+EN1+03+++++1++1000++0+1+1'",
        "DIA+F91.9+Störung des Sozialverhaltens'",
        "BES+10,00+0,00+0,00+0,00'",
    ])
    b = parse_esol_belege_summary(raw)[0]
    assert b["diagnosen"][0]["text"] == "Störung des Sozialverhaltens"


def test_nachrichtenkontext_wird_uebernommen(beleg):
    assert beleg["kostentraeger_ik"] == "101777502"
    assert beleg["leistungserbringer_ik"] == "123456789"
    assert beleg["verarbeitungskennzeichen"] == "01"
    assert beleg["rechnungsnummer"] == "76"
    assert beleg["rechnungsdatum"] == "20260408"


# ------------------------------------------------------------ Positionsgruppierung

def test_positionen_werden_gruppiert(beleg):
    gruppen = beleg["positionsgruppen"]
    # 54145 zweimal (gleicher Einzelbetrag) -> eine Gruppe; 54003 -> eigene Gruppe
    assert len(gruppen) == 2

    g145 = next(g for g in gruppen if g["code"] == "54145")
    assert g145["anzahl_termine"] == 2
    assert g145["menge_gesamt"] == 10.0
    assert g145["betrag_gesamt"] == pytest.approx(189.80)
    assert g145["zuzahlung_gesamt"] == pytest.approx(19.00)
    assert g145["datum_von"] == "20260123"
    assert g145["datum_bis"] == "20260130"
    assert g145["zeitraum_text"] == "23.01.2026 – 30.01.2026"
    assert len(g145["termine"]) == 2


def test_gruppensummen_entsprechen_bes(beleg):
    summe = round(sum(g["betrag_gesamt"] for g in beleg["positionsgruppen"]), 2)
    assert summe == pytest.approx(beleg["brutto"])


def test_unterschiedliche_einzelbetraege_bleiben_getrennt():
    positions = [
        {"tag": "EHE", "code": "54103", "abr_code": "26", "tarif_kz": "00501",
         "datum": "20260101", "anzahl": 1.0, "einzelbetrag": 10.0,
         "gesamtbetrag": 10.0, "zuzahlung": 0.0, "zuzahlung_gesamt": 0.0},
        {"tag": "EHE", "code": "54103", "abr_code": "26", "tarif_kz": "00501",
         "datum": "20260102", "anzahl": 1.0, "einzelbetrag": 12.0,
         "gesamtbetrag": 12.0, "zuzahlung": 0.0, "zuzahlung_gesamt": 0.0},
    ]
    gruppen = vo.gruppiere_positionen(positions)
    assert len(gruppen) == 2


def test_behandlungsuebersicht(beleg):
    ub = beleg["behandlung"]
    assert ub["anzahl_positionen"] == 3
    assert ub["anzahl_behandlungstage"] == 2  # 23.01. und 30.01.
    assert ub["zeitraum_text"] == "23.01.2026 – 30.01.2026"


# --------------------------------------------------------------- Plausibilität

def _beleg_mit_zhe(zhe_segment: str, extra: str = "") -> dict:
    raw = "\n".join([
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "INV+A1+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+54103+1,00+100,00+20260115+1,00'",
        zhe_segment,
        "DIA+F91.9'",
        extra or "BES+100,00+11,00+1,00+10,00'",
    ])
    return parse_esol_belege_summary(raw)[0]


def test_hinweis_behandlung_vor_verordnung():
    b = _beleg_mit_zhe("ZHE+111111111+222222222+20260201+3+EN1+03+++++1++1000++0+1+1'")
    texte = " ".join(h["text"] for h in b["verordnung_hinweise"])
    assert "VOR dem" in texte


def test_hinweis_zuzahlungsbefreit_aber_zuzahlung():
    b = _beleg_mit_zhe("ZHE+111111111+222222222+20260101+1+EN1+03+++++1++1000++0+1+1'")
    hinweise = [h for h in b["verordnung_hinweise"] if h["stufe"] == "fehler"]
    assert any("befreit" in h["text"] for h in hinweise)


def test_hinweis_fehlende_diagnose():
    raw = "\n".join([
        "UNH+00002+SLLA:21:0:0'",
        "INV+A1+31000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+54103+1,00+10,00+20260115+0,00'",
        "ZHE+111111111+222222222+20260101+0+EN1+03+++++1++1000++0+1+1'",
        "BES+10,00+0,00+0,00+0,00'",
    ])
    b = parse_esol_belege_summary(raw)[0]
    assert any("DIA" in h["text"] for h in b["verordnung_hinweise"])


def test_hinweis_fehlende_pflichtfelder():
    b = _beleg_mit_zhe("ZHE+++20260101+0+EN1+03+++++1++1000++0+1+1'")
    texte = " ".join(h["text"] for h in b["verordnung_hinweise"])
    assert "BSNR" in texte and "LANR" in texte


def test_keine_hinweise_bei_plausibler_verordnung():
    b = _beleg_mit_zhe("ZHE+111111111+222222222+20260101+3+EN1+03+++++1++1000++0+1+1'")
    fehler = [h for h in b["verordnung_hinweise"] if h["stufe"] == "fehler"]
    assert fehler == []


# ----------------------------------------------------------------- Codelisten

def test_codelisten_datei_ist_lesbar():
    path = codelisten.source_path()
    assert path is not None, "data/codelisten.json wurde nicht gefunden"
    assert codelisten.last_error() is None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assert "verordnungsart" in data
    assert "positionsnummern" in data


def test_codelisten_describe_ohne_klartext():
    # Verordnungsarten sind absichtlich ohne Bezeichnung vorbelegt
    text = codelisten.describe("verordnungsart", "03")
    assert text.startswith("03")
    assert codelisten.KEIN_KLARTEXT in text


def test_codelisten_describe_mit_klartext():
    text = codelisten.describe("zuzahlungskennzeichen", "1")
    assert "Zuzahlungsbefreit" in text


def test_codelisten_describe_leer():
    assert codelisten.describe("verordnungsart", "") == "—"
    assert codelisten.describe("verordnungsart", None, leer_text="n/a") == "n/a"


def test_codelisten_unbekannter_code_wird_nicht_geraten():
    text = codelisten.describe("diagnosegruppe", "ZZ9")
    assert text == f"ZZ9 ({codelisten.KEIN_KLARTEXT})"


def test_codelisten_position_nach_abrechnungscode(tmp_path, monkeypatch):
    eigene = tmp_path / "codelisten.json"
    eigene.write_text(json.dumps({
        "positionsnummern": {
            "*": {"59702": "Allgemeine Position"},
            "26": {"54103": "Ergo-Einzelbehandlung"},
        }
    }), encoding="utf-8")

    # Auch die HMP-Quelle leeren — sonst greift der Rückfall auf die
    # GKV-Stammdatei und 54103 löst dort über X4103 auf.
    leere_hmp = tmp_path / "heilmittelpreise.json"
    leere_hmp.write_text(json.dumps({"positionen": {}}), encoding="utf-8")

    monkeypatch.setenv("PY_ESOL_CODELISTEN", str(eigene))
    monkeypatch.setenv("PY_ESOL_HEILMITTELPREISE", str(leere_hmp))
    codelisten.reload()
    try:
        assert codelisten.lookup_position("54103", "26") == "Ergo-Einzelbehandlung"
        assert codelisten.lookup_position("59702", "26") == "Allgemeine Position"
        # Mit Abrechnungscode 99 greift die eigene Staffelung nicht mehr; dann
        # bleibt der Heilmittelkatalog als dritte Ebene, der 54103 über die
        # X-Maske als X4103 kennt. Geprüft wird deshalb, dass NICHT die
        # Ergo-spezifische eigene Bezeichnung herauskommt.
        assert codelisten.lookup_position("54103", "99") != "Ergo-Einzelbehandlung"
        assert codelisten.describe_position("99999", "26").endswith(
            f"({codelisten.KEIN_KLARTEXT})"
        )
    finally:
        monkeypatch.delenv("PY_ESOL_CODELISTEN", raising=False)
        monkeypatch.delenv("PY_ESOL_HEILMITTELPREISE", raising=False)
        codelisten.reload()


def test_codelisten_defekte_datei_bricht_nicht(tmp_path, monkeypatch):
    kaputt = tmp_path / "codelisten.json"
    kaputt.write_text("{ das ist kein JSON", encoding="utf-8")

    monkeypatch.setenv("PY_ESOL_CODELISTEN", str(kaputt))
    codelisten.reload()
    try:
        # Fällt auf die Projektdatei zurück oder liefert leere Tabellen —
        # in beiden Fällen darf nichts geworfen werden.
        assert isinstance(codelisten.load(), dict)
        assert codelisten.describe("verordnungsart", "03").startswith("03")
    finally:
        monkeypatch.delenv("PY_ESOL_CODELISTEN", raising=False)
        codelisten.reload()


# ------------------------------------------------------- Schema-Feldbenennung

def test_segment_field_rows_nutzt_schema():
    rows = vo.segment_field_rows("ZHE", ["243203100", "933473451", "20260116", "3", "PS3"])
    namen = [r["name"] for r in rows]
    assert namen[0] == "Betriebsstättennummer"
    assert namen[2] == "Verordnungsdatum"
    assert namen[4] == "Diagnosegruppe"


def test_segment_field_rows_kontextsegment_fkt():
    # FKT ist nur kontextspezifisch registriert -> Namen müssen dennoch auflösen
    rows = vo.segment_field_rows("FKT", ["01", "", "123456789", "101777502"], message_type="SLLA")
    namen = {r["index"]: r["name"] for r in rows}
    assert namen["1"] == "Verarbeitungskennzeichen"
    assert "Kostenträger" in namen["4"]


def test_segment_field_rows_composite_wird_aufgeschluesselt():
    rows = vo.segment_field_rows("EHE", [["26", "00501"], "54103", "1,00"])
    assert "Abrechnungscode: 26" in rows[0]["value"]
    assert "Tarifkennzeichen: 00501" in rows[0]["value"]


# ---------------------------------------------------------------- Textausgabe

def test_verordnung_textzeilen(beleg):
    text = "\n".join(vo.verordnung_textzeilen(beleg))
    assert "13.01.2026" in text
    assert "BSNR 273806900" in text
    assert "G30.1" in text
    assert "Behandlungszeitraum" in text


# ------------------------------------------------- Schlüssel aus Anlage 3 TP 5

def test_zuzahlungskennzeichen_entspricht_anlage_3():
    """
    Die Klartexte müssen wörtlich Abschnitt 8.1.3 der Anlage 3 zu TP 5
    entsprechen. Zuvor stand hier eine falsche Auslegung ("Zuzahlung
    entrichtet" / "nicht entrichtet") — genau das darf in der Hotline nicht
    passieren, deshalb ist die Zuordnung ab jetzt festgenagelt.
    """
    assert codelisten.lookup("zuzahlungskennzeichen", "0") == "Keine gesetzliche Zuzahlung"
    assert codelisten.lookup("zuzahlungskennzeichen", "1") == "Zuzahlungsbefreit"
    assert codelisten.lookup("zuzahlungskennzeichen", "2") == (
        "Keine Zuzahlung trotz schriftlicher Zahlungsaufforderung"
    )
    assert codelisten.lookup("zuzahlungskennzeichen", "3") == "Zuzahlungspflichtig"
    assert codelisten.lookup("zuzahlungskennzeichen", "4").startswith(
        "Übergang zuzahlungspflichtig zu zuzahlungsfrei"
    )
    assert codelisten.lookup("zuzahlungskennzeichen", "5").startswith(
        "Übergang zuzahlungsfrei zu zuzahlungspflichtig"
    )


def test_zuzahlungskennzeichen_kennt_nur_0_bis_5():
    """Die Anlage besetzt genau 0-5. Erfundene Schlüssel dürfen nicht auftauchen."""
    tabelle = codelisten.load().get("zuzahlungskennzeichen", {})
    assert sorted(tabelle) == ["0", "1", "2", "3", "4", "5"]


def test_unfall_und_bvg_nur_besetzte_schluessel():
    # 8.1.2 besetzt 1-3 (kein 0), 8.1.2.1 nur die 6.
    assert sorted(codelisten.load().get("unfallkennzeichen", {})) == ["1", "2", "3"]
    assert sorted(codelisten.load().get("bvg_sonstiges_ser", {})) == ["6"]
    assert codelisten.lookup("unfallkennzeichen", "1").startswith("Arbeitsunfall")
    assert codelisten.lookup("bvg_sonstiges_ser", "6") == "BVG/SER"


def test_verarbeitungskennzeichen_klartext():
    assert codelisten.lookup("verarbeitungskennzeichen", "01") == "Abrechnung ohne Besonderheiten"
    assert codelisten.lookup("verarbeitungskennzeichen", "02") == "Nachforderung"
    assert codelisten.lookup("verarbeitungskennzeichen", "03") == "Zuzahlungsforderung"
    assert codelisten.lookup("verarbeitungskennzeichen", "04") == "Korrekturrechnung"
    assert codelisten.lookup("verarbeitungskennzeichen", "10") == "Wiederaufnahme"


def test_summenstatus_und_rechnungsart():
    assert codelisten.lookup("summenstatus", "00") == "Gesamtsumme aller Status"
    assert codelisten.lookup("summenstatus", "51") == "Rentner"
    assert codelisten.lookup("rechnungsart", "1").startswith("Abrechnung von Leistungserbringer")


def test_abrechnungscode_heilmittelbereich():
    assert codelisten.lookup("abrechnungscode", "22") == "Krankengymnast / Physiotherapeut"
    assert codelisten.lookup("abrechnungscode", "26") == "Ergotherapeut"
    assert codelisten.lookup("abrechnungscode", "71") == "Podologen"
    # Hilfsmittel-Codes sind in dieser Fassung bewusst nicht hinterlegt
    assert codelisten.lookup("abrechnungscode", "11") == ""


def test_diagnosegruppen_aller_fuenf_bereiche():
    """
    Maßgeblich sind seit dem Import der KBV-Heilmittelstammdatei die
    Bezeichnungen in data/diagnosegruppen.json, nicht mehr die Liste in
    codelisten.json. Der Bereich steht dort in einem eigenen Feld, statt dem
    Klartext vorangestellt zu sein.
    """
    tabelle = codelisten.load_diagnosegruppen().get("diagnosegruppen", {})
    for code in ("WS", "EX", "SO5", "SB3", "EN1", "PS4", "ST1", "SP6", "RE2",
                 "DF", "QF", "UI1", "SAS", "CF"):
        assert tabelle.get(code), f"Diagnosegruppe {code} fehlt"

    assert codelisten.diagnosegruppe_info("EN1")["bereich"] == "Maßnahmen der Ergotherapie"
    assert codelisten.diagnosegruppe_info("SP4")["bereich"] == \
        "Maßnahmen der Stimm-, Sprech-, Sprach- und Schlucktherapie"
    assert codelisten.diagnosegruppe_info("DF")["bereich"] == \
        "Maßnahmen der Podologischen Therapie"

    # EE1/EE2 gab es nur in der früheren, abweichenden Fassung — die KBV
    # schlüsselt die Ernährungstherapie mit SAS und CF.
    assert not tabelle.get("EE1")
    assert "EE1" in codelisten.load()["_abweichungen_diagnosegruppe"]


def test_offene_listen_bleiben_leer():
    """
    Verordnungsart, Verordnungsbesonderheiten, Heilmittelbereich,
    Therapiefrequenz und Genehmigungsart sind noch nicht belegt. Der Test hält
    fest, dass dort NICHTS geraten wurde — er schlägt an, sobald jemand die
    Listen füllt, und ist dann bewusst zu streichen.
    """
    daten = codelisten.load()
    for liste in ("verordnungsart", "verordnungsbesonderheiten",
                  "heilmittelbereich", "therapiefrequenz"):
        werte = [v for v in daten.get(liste, {}).values() if str(v).strip()]
        assert werte == [], f"{liste} enthält jetzt Klartexte — Test anpassen"
    assert daten.get("genehmigungsart") == {}


def test_unbekannter_code_zeigt_kein_klartext():
    # Der Kern der Absprache: nie raten.
    assert codelisten.describe("verordnungsart", "04") == f"04 ({codelisten.KEIN_KLARTEXT})"
    assert codelisten.describe("diagnosegruppe", "XX9") == f"XX9 ({codelisten.KEIN_KLARTEXT})"


# ------------------------------------------------- Leistungserbringergruppe

def test_leistungserbringergruppe_zerlegt_7_stellen():
    leg = vo.leistungserbringergruppe("26", "00501")
    assert leg["abr_code"] == "26"
    assert leg["abr_text"] == "Ergotherapeut"
    assert leg["tarifbereich"] == "00"
    assert leg["tarifbereich_text"].startswith("Bundeseinheitlicher Tarif")
    assert leg["sondertarif"] == "501"
    # 501 ist in der erfassten Fassung der Anlage nicht benannt -> nichts raten
    assert leg["sondertarif_text"] == ""
    assert "Ergotherapeut" in leg["text"]
    assert "Sondertarif 501" in leg["text"]


def test_leistungserbringergruppe_kostenvoranschlag():
    leg = vo.leistungserbringergruppe("22", "00099")
    assert leg["sondertarif"] == "099"
    assert "Kostenvoranschlag" in leg["sondertarif_text"]


def test_leistungserbringergruppe_unbekannter_abrechnungscode():
    leg = vo.leistungserbringergruppe("11", "00000")
    assert leg["abr_text"] == ""
    assert codelisten.KEIN_KLARTEXT in leg["text"]


def test_leistungserbringergruppe_leer():
    leg = vo.leistungserbringergruppe("", "")
    assert leg["text"] == ""
    assert leg["tarifbereich"] == "" and leg["sondertarif"] == ""


def test_leistungserbringergruppe_teilweise():
    # Nur Abrechnungscode, kein Tarifkennzeichen
    leg = vo.leistungserbringergruppe("26", "")
    assert leg["text"] == "26 — Ergotherapeut"
