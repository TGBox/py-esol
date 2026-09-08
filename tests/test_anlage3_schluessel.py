"""
Abgleich mit den Schlüsselverzeichnissen der Anlage 3 zu den Richtlinien nach
§ 302 SGB V, TP 5 Version 21, Stand 19.09.2025, anzuwenden ab 01.10.2025.

Die Tests halten fest, welche Schlüsselausprägungen zulässig sind. Sie arbeiten
auf einer echten, fehlerfreien Datei aus testdata/ und verändern jeweils genau
eine Stelle.

Die Werte in den Erwartungslisten sind aus der Anlage abgeschrieben. Fällt eine
Prüfung um, ist entweder die Regel verändert worden oder eine neue Fassung der
Anlage anzuarbeiten — in beiden Fällen soll es auffallen.
"""

from pathlib import Path

import codelisten
from esol_validator import EsolValidator
from tools.generate_correction import read_esol_file_text

BASIS_DATEI = Path(__file__).resolve().parent.parent / "testdata" / "in" / "ESOL0001"


def _basis():
    return read_esol_file_text(BASIS_DATEI)


def _zusammensetzen(zeilen):
    """Zähler in UNT und UNZ nachziehen, damit nur der geprüfte Fehler bleibt."""
    aus, puffer, anzahl_unh = [], [], 0
    for z in zeilen:
        if z.startswith("UNH"):
            anzahl_unh += 1
            puffer = [z]
        elif z.startswith("UNT"):
            puffer.append(z)
            ref = puffer[0].split("+")[1]
            puffer[-1] = f"UNT+{len(puffer):06d}+{ref}'"
            aus.extend(puffer)
            puffer = []
        elif puffer:
            puffer.append(z)
        elif z.startswith("UNZ"):
            ref = z.split("+")[2].rstrip("'")
            aus.append(f"UNZ+{anzahl_unh:06d}+{ref}'")
        else:
            aus.append(z)
    return "\r\n".join(aus) + "\r\n"


def _codes(text):
    validator = EsolValidator()
    validator.register_default_rules()
    ergebnis = validator.validate_string(text)
    return {e.code for e in ergebnis.get_errors()}


def _warnungen(text):
    validator = EsolValidator()
    validator.register_default_rules()
    ergebnis = validator.validate_string(text)
    return {w.code for w in ergebnis.get_warnings()}


def _ersetzt(alt, neu):
    text = _basis()
    assert alt in text, f"Muster {alt!r} steht nicht in der Basisdatei"
    return _zusammensetzen([z for z in text.replace(alt, neu, 1).split("\r\n") if z])


def _mit_segment(nach_tag, segment):
    zeilen = []
    for z in _basis().split("\r\n"):
        if not z:
            continue
        zeilen.append(z)
        if z.startswith(nach_tag):
            zeilen.append(segment)
    return _zusammensetzen(zeilen)


def test_basisdatei_ist_fehlerfrei():
    assert _codes(_zusammensetzen([z for z in _basis().split("\r\n") if z])) == set()


# --- 8.1.3 Zuzahlung -------------------------------------------------------


def test_zuzahlungskennzeichen_nur_0_bis_5():
    """
    Der Schlüssel besetzt 0 bis 5. Vorher stand in der Regel 0 bis 9; die
    Werte 6 bis 9 gibt es nicht, liefen aber durch.
    """
    for wert in ("0", "1", "2", "3", "4", "5"):
        assert "1.3.9.4" not in _codes(
            _ersetzt("+20260112+0+PS1", f"+20260112+{wert}+PS1")
        ), wert
    for wert in ("6", "7", "8", "9"):
        assert "1.3.9.4" in _codes(
            _ersetzt("+20260112+0+PS1", f"+20260112+{wert}+PS1")
        ), wert


# --- 8.1.12 Kennzeichen Verordnungsart bei Heilmitteln --------------------


def test_verordnungsart_nur_schluesselwerte():
    """
    Anlage 3 besetzt 01 bis 05, 10 und 11; die 99 erlaubt Anlage 1 für
    Fallkonstellationen außerhalb der Heilmittel-Richtlinien. 06 bis 09 und
    12 bis 20 gibt es nicht — die standen vorher in der Regel.
    """
    for wert in ("03", "04", "05", "10", "11", "99"):
        assert "1.3.9.6" not in _codes(_ersetzt("+PS1+03+", f"+PS1+{wert}+")), wert
    for wert in ("06", "07", "12", "20", "77"):
        assert "1.3.9.6" in _codes(_ersetzt("+PS1+03+", f"+PS1+{wert}+")), wert


# --- 8.1.11 Kennzeichen Verordnungsbesonderheiten ------------------------


def test_verordnungsbesonderheiten_nur_schluesselwerte():
    """Besetzt sind 1, 2, 3, 4, 7, 8 und 9 — es gibt keine 0, 5 oder 6."""
    for wert in ("1", "2", "3", "4", "7", "8", "9"):
        assert "1.3.9.12" not in _codes(
            _ersetzt("+PS1+03+++++1", f"+PS1+03+{wert}++++1")
        ), wert
    for wert in ("0", "5", "6"):
        assert "1.3.9.12" in _codes(
            _ersetzt("+PS1+03+++++1", f"+PS1+03+{wert}++++1")
        ), wert


# --- 8.1.2 und 8.1.2.1 ---------------------------------------------------


def test_unfallkennzeichen_nur_1_bis_3():
    for wert in ("1", "2", "3"):
        assert "1.3.9.13" not in _codes(
            _ersetzt("+PS1+03+++++1", f"+PS1+03++{wert}+++1")
        ), wert
    for wert in ("0", "4", "9"):
        assert "1.3.9.13" in _codes(
            _ersetzt("+PS1+03+++++1", f"+PS1+03++{wert}+++1")
        ), wert


def test_bvg_ser_nur_die_sechs():
    assert "1.3.9.14" not in _codes(_ersetzt("+PS1+03+++++1", "+PS1+03+++6++1"))
    for wert in ("1", "5", "7"):
        assert "1.3.9.14" in _codes(
            _ersetzt("+PS1+03+++++1", f"+PS1+03+++{wert}++1")
        ), wert


def test_behandlungsbeginn_wird_nur_angemahnt():
    """
    Anlage 1 zum ZHE: "Dieses Feld wird nicht mehr gefüllt. Das Feld wird als
    Leerfeld übermittelt." Ein gefülltes Feld macht die Datei nicht ungültig,
    soll aber auffallen — daher eine Warnung und kein Fehler.
    """
    text = _ersetzt("+PS1+03+++++1", "+PS1+03++++20250101+1")
    assert "1.3.9.15" in _warnungen(text)
    assert _codes(text) == set()


# --- 8.1.5.1 und 8.1.14: Abrechnungscode und Leistungsbereich ------------


def test_abrechnungscode_muss_zum_leistungsbereich_passen():
    """
    Anlage 3, Abschnitt 8.1.14 ordnet die Abrechnungscodes den
    Sammelgruppenschlüsseln zu. Die Basisdatei weist im UNB "B" (Heilmittel)
    aus; dort sind 21-29 und 71-74 zulässig.
    """
    for wert in ("21", "22", "26", "29", "71", "74"):
        assert "1.3.8.7" not in _codes(
            _ersetzt("EHE+26:00501+54103+", f"EHE+{wert}:00501+54103+")
        ), wert
    # 15 ist Hilfsmittel (A), 50 Hebammen (F), B1 Modellvorhaben (S)
    for wert in ("15", "50", "B1"):
        assert "1.3.8.7" in _codes(
            _ersetzt("EHE+26:00501+54103+", f"EHE+{wert}:00501+54103+")
        ), wert


# --- 8.2.1 Abrechnungspositionsnummer für Heilmittel ---------------------


def test_positionsnummer_genau_fuenfstellig():
    """
    Anlage 3, Abschnitt 8.2.1 gibt die Schlüsselgröße mit 5 Stellen an, Anlage
    1 formuliert es als Pflicht: "Es muss die vertraglich vereinbarte
    5-stellige bundeseinheitliche Positionsnummer übermittelt werden." Geprüft
    wurde vorher nur die Obergrenze.
    """
    for wert in ("541", "5410"):
        assert "1.3.8.2" in _codes(
            _ersetzt("EHE+26:00501+54103+", f"EHE+26:00501+{wert}+")
        ), wert

    # Zu lang fällt schon auf Stufe 2 auf (Feldlänge, Regel 1.2.2.6). Die
    # Prüfung bricht dort ab, Stufe 3 läuft nicht mehr — deshalb steht hier
    # nicht 1.3.8.2.
    assert "1.2.2.6" in _codes(
        _ersetzt("EHE+26:00501+54103+", "EHE+26:00501+541034+")
    )


# --- 8.1.17 Art der Genehmigung (SKZ) ------------------------------------


def test_art_der_genehmigung():
    """
    Für Heilmittel ist allein B2 besetzt. B1 führt die Anlage als nicht
    belegt, und die erste Stelle muss zum Leistungsbereich der Datei passen.
    """
    assert _codes(_mit_segment("DIA", "SKZ+GEN-4711+20260101+B2'")) == set()
    assert "1.3.14.3" in _codes(_mit_segment("DIA", "SKZ+GEN-4711+20260101+B1'"))
    assert "1.3.14.3" in _codes(_mit_segment("DIA", "SKZ+GEN-4711+20260101+XX'"))
    assert "1.3.14.4" in _codes(_mit_segment("DIA", "SKZ+GEN-4711+20260101+A2'"))
    assert "1.3.14.2" in _codes(_mit_segment("DIA", "SKZ+GEN-4711+20261332+B2'"))


# --- 8.1.6 Summenstatus --------------------------------------------------


def test_summenstatus_folgt_der_ersten_ziffer():
    """
    "Die zweite bis fünfte Ziffer im Feld Versichertenstatus wird bei der
    Kennzeichnung der Summenstatus nicht berücksichtigt."
    """
    from rules.level3.content_helper import ContentHelper

    assert ContentHelper.summenstatus("10000") == "11"
    assert ContentHelper.summenstatus("10005") == "11"
    assert ContentHelper.summenstatus("30000") == "31"
    assert ContentHelper.summenstatus("50032") == "51"
    assert ContentHelper.summenstatus("70000") == "99"
    assert ContentHelper.summenstatus("") == "99"
    assert ContentHelper.summenstatus(None) == "99"


def test_ges_statuszeile_gegen_die_belege():
    """
    Regel 1.3.13.7. Anlage 1 zum GES-Segment: "Die Betragssumme des
    Versichertenstatus (SLGA) entspricht den Summen der Abrechnungsfälle
    (SLLA), die diesen Status beinhalten." Stimmen die Beträge in der Summe,
    stehen aber in der falschen Statuszeile, fiel das vorher nicht auf.
    """
    datei = Path(__file__).resolve().parent.parent / "testdata" / "in" / "ESOL0004"
    text = read_esol_file_text(datei)
    assert _codes(text) == set()

    vertauscht = (
        text.replace("GES+31+1520,60+1520,60+0,00'", "GES+31+1747,75+1908,42+160,67'")
            .replace("GES+51+1747,75+1908,42+160,67'", "GES+51+1520,60+1520,60+0,00'")
    )
    assert "1.3.13.7" in _codes(vertauscht)


def test_korrektur_bucht_den_rentner_in_die_eigene_statuszeile():
    """
    Der Fehler beim Erzeugen: der Summenstatus wurde aus den GES-Zeilen der
    Ursprungsdatei geraten statt aus dem Versichertenstatus des Belegs. Eine
    Datei ohne GES+51 buchte den Rentner unter "31" (Angehörige).
    """
    from tools.generate_correction import generate_correction_esol

    original = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+200,00+200,00+0,00'",
        "GES+31+200,00+200,00+0,00'",
        "NAM+Praxis+++info@praxis.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+30000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
        "ZHE+110178400+906716934+20250528+3+EN1+04+++++1++1110++0+1+2'",
        "DIA+F98.9'",
        "BES+100,00+10,00+10,00+0,00'",
        "INV+B987654321+50000+1+00002'",
        "NAD+Rentner+Rita+19400101'",
        "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
        "ZHE+110178400+906716934+20250528+3+EN1+04+++++1++1110++0+1+2'",
        "DIA+F98.9'",
        "BES+100,00+10,00+10,00+0,00'",
        "UNT+000016+00002'",
        "UNZ+000002+00118'",
    ])

    neu = generate_correction_esol(original, target_vk="02", new_rec_nr="900")
    ges = [z for z in neu.replace("\r\n", "\n").split("\n") if z.startswith("GES")]

    assert "GES+31+90,00+100,00+10,00'" in ges, ges
    assert "GES+51+90,00+100,00+10,00'" in ges, ges
    assert _codes(neu) == set()


# --- Codelisten ----------------------------------------------------------


def test_codelisten_deckung_mit_den_pruefregeln():
    """
    Klartextliste und Prüfregel müssen dieselben Schlüsselwerte kennen. Sonst
    zeigt die Anzeige "kein Klartext hinterlegt" für einen Wert, den die
    Prüfung zulässt, oder umgekehrt.
    """
    from rules.level3.zhe_content_rule import ZheContentRule

    daten = codelisten.load()
    paare = [
        ("zuzahlungskennzeichen", ZheContentRule.VALID_ZUZAHLUNGSKZ),
        ("verordnungsart", ZheContentRule.VALID_VERORDNUNGSART),
        ("verordnungsbesonderheiten", ZheContentRule.VALID_VERORDNUNGSBESONDERHEIT),
        ("unfallkennzeichen", ZheContentRule.VALID_UNFALLKENNZEICHEN),
        ("bvg_sonstiges_ser", ZheContentRule.VALID_BVG_SER),
    ]
    for liste, erlaubt in paare:
        assert set(daten[liste]) == set(erlaubt), (
            f"{liste}: Codeliste {sorted(daten[liste])} != Regel {sorted(erlaubt)}"
        )


def test_sondertarif_bereiche_aus_der_anlage():
    """
    Anlage 3, Abschnitt 8.1.5.2 definiert die 3.-5. Stelle in Bereichen. Das in
    den Echtdateien durchgehend verwendete "501" fällt unter "alle übrigen
    Kombinationen" und hatte vorher keinen Text.
    """
    assert codelisten.lookup("sondertarif", "000") == "ohne Besonderheiten"
    assert codelisten.lookup("sondertarif", "A90") == "ohne Besonderheiten"
    assert "Kostenvoranschlag" in codelisten.lookup("sondertarif", "099")
    assert "nicht besetzt" in codelisten.lookup("sondertarif", "091")
    assert "nicht besetzt" in codelisten.lookup("sondertarif", "U00")
    assert "Sondertarifvereinbarung" in codelisten.lookup("sondertarif", "501")
    # Was keine drei Stellen hat, ist kein Sondertarif
    assert codelisten.lookup("sondertarif", "12") == ""


# --- 8.1.18 Beleginformation ---------------------------------------------


def test_beleginformation_nur_0_bis_2():
    """
    Der Schlüssel besetzt 0 (keine Belegübermittlung), 1 (per Post) und
    2 (elektronisch). Vorher stand in der Regel 0 bis 9.
    """
    for wert in ("0", "1", "2"):
        assert "1.3.5.3" not in _codes(
            _ersetzt("+30000+1+00037", f"+30000+{wert}+00037")
        ), wert
    for wert in ("3", "5", "9"):
        assert "1.3.5.3" in _codes(
            _ersetzt("+30000+1+00037", f"+30000+{wert}+00037")
        ), wert


# --- 8.1.6 Summenstatus als Schlüsselwert --------------------------------


def test_summenstatus_muss_schluesselwert_sein():
    for wert in ("11", "31", "51", "99"):
        assert "1.3.13.8" not in _codes(_ersetzt("GES+31+", f"GES+{wert}+")), wert
    for wert in ("42", "12", "01"):
        assert "1.3.13.8" in _codes(_ersetzt("GES+31+", f"GES+{wert}+")), wert


# --- 8.1.5.2 Tarifbereich ------------------------------------------------


def test_tarifbereich_muss_vergeben_sein():
    """
    Belegt sind 00-25, 50-75, 90 und 91-99. Die Bereiche 26-49 und 76-89
    führt die Anlage als "noch zu vergeben".
    """
    for wert in ("00", "08", "25", "50", "75", "90", "99"):
        assert "1.3.8.8" not in _codes(
            _ersetzt("EHE+26:00501+", f"EHE+26:{wert}501+")
        ), wert
    for wert in ("26", "30", "49", "76", "89"):
        assert "1.3.8.8" in _codes(
            _ersetzt("EHE+26:00501+", f"EHE+26:{wert}501+")
        ), wert
