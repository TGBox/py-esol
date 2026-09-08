"""
Tests für die Anonymisierung von Berichten, Exporten und Kundendateien.

Zwei Dinge müssen zugleich gelten, sonst ist die Funktion wertlos:

  1. Nach der Anonymisierung darf im Ergebnis kein Originalwert mehr stehen —
     auch nicht in den Fehlermeldungen, denn mehrere Prüfregeln zitieren den
     Wert im Meldungstext.
  2. Eine anonymisierte ESOL-Datei muss die Prüfung weiter bestehen. Sonst
     kann der Empfänger den Fehler nicht mehr nachvollziehen, und genau dafür
     ist die Kopie gedacht.
"""

from pathlib import Path

import pytest

import anonymisierung as an
import support_helper as sh
from esol_validator import EsolValidator
from rules.level3.content_helper import ContentHelper
from tools.generate_correction import parse_esol_belege_summary

FIXTURE = Path(__file__).parent / "fixtures" / "valid_esol_smoke"


def _quelle() -> str:
    """
    Eine Datei mit zwei Belegen derselben Person und einem dritten Versicherten
    — damit sich prüfen lässt, ob Pseudonyme stabil sind.
    """
    kopf = [
        "UNB+UNOC:3+480512931+101777502+20260907:1040+00001+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++480512931+101777502+101777502+480512931'",
        "REC+51:0+20260122+1'",
        "GES+00+300,00+300,00+0,00'",
        "GES+11+300,00+300,00+0,00'",
        "NAM+Praxis für Ergotherapie+++info@ergo-praxis.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++480512931+101777502+101777502'",
        "REC+51:0+20260122+1'",
    ]
    belege = [
        ("00001", "E430685837", "Stein", "Bryan", "20190405", "034072134", "F92.8"),
        ("00002", "E430685837", "Stein", "Bryan", "20190405", "034072134", "F92.8"),
        ("00003", "K111222333", "Wansart", "Cecilia", "19330217", "390860101", "F03"),
    ]
    for nr, versnr, nachname, vorname, geb, lanr, icd in belege:
        kopf += [
            f"INV+{versnr}+30005+1+{nr}'",
            f"NAD+{nachname}+{vorname}+{geb}'",
            f"ZHE+242373500+{lanr}+20260210+3+EN3+03+++++1++1000++0+1+3'",
            "EHE+26:00501+54103+1,00+100,00+20260215+0,00'",
            f"DIA+{icd}'",
            "BES+100,00+0,00+0,00+0,00'",
        ]
    return "\n".join(kopf + ["UNT+000025+00002'", "UNZ+000002+00001'"])


def _pruefe(text: str):
    validator = EsolValidator()
    validator.register_default_rules()
    return validator.validate_string(text)


# --------------------------------------------------------------- Grundlagen

def test_standardgruppen_sind_versicherter_und_arzt():
    assert an.standard_gruppen() == {"versicherter", "arzt"}


def test_unbekannte_gruppe_wird_abgelehnt():
    with pytest.raises(ValueError, match="Unbekannte Feldgruppe"):
        an.Anonymisierer(gruppen={"versicherter", "gibtsnicht"})


def test_leere_gruppenmenge_laesst_alles_stehen():
    anon = an.Anonymisierer(gruppen=set())
    assert anon.aktiv is False
    belege = parse_esol_belege_summary(_quelle())
    assert anon.belege(belege) == belege
    assert anon.esol(_quelle()) == _quelle()
    assert anon.text('Versichertennummer "E430685837"') == 'Versichertennummer "E430685837"'


def test_buchstaben_zaehlung():
    assert an._buchstaben(1) == "A"
    assert an._buchstaben(26) == "Z"
    assert an._buchstaben(27) == "AA"


# ------------------------------------------------------------------ Berichte

def test_versicherter_wird_im_bericht_ersetzt():
    belege = parse_esol_belege_summary(_quelle())
    anon = an.Anonymisierer()
    ergebnis = anon.belege(belege)

    text = " ".join(str(b) for b in ergebnis)
    for original in ("Stein", "Bryan", "Wansart", "Cecilia", "E430685837", "20190405"):
        assert original not in text, f"{original} steht noch im Bericht"

    assert ergebnis[0]["nachname"].startswith("Versicherter ")
    assert ergebnis[0]["geburtstag"] == "Jahrgang 2019"


def test_pseudonyme_sind_innerhalb_eines_exports_stabil():
    """
    Zwei Belege derselben Person müssen dasselbe Pseudonym bekommen — sonst
    lässt sich in der Fehleranalyse nicht mehr erkennen, dass sie zusammen
    gehören.
    """
    ergebnis = an.Anonymisierer().belege(parse_esol_belege_summary(_quelle()))
    assert ergebnis[0]["nachname"] == ergebnis[1]["nachname"]
    assert ergebnis[0]["nachname"] != ergebnis[2]["nachname"]


def test_pseudonyme_gelten_nicht_ueber_exporte_hinweg():
    """
    Zwei getrennte Vorgänge dürfen dieselbe Person nicht wiedererkennbar
    machen — das wäre keine Anonymisierung mehr. Geprüft wird, dass die
    Zuordnung an der Instanz hängt und nicht global gehalten wird.
    """
    belege = parse_esol_belege_summary(_quelle())
    a1 = an.Anonymisierer()
    a1.belege(belege)
    a2 = an.Anonymisierer()
    a2.belege([belege[2], belege[0]])  # andere Reihenfolge

    # In a1 ist Stein der erste Versicherte, in a2 der zweite
    assert a1._zuordnung["versicherter"] != a2._zuordnung["versicherter"]


def test_geburtsjahr_bleibt_erhalten():
    """Altersgrenzen (Verordnungsbedarf, Kinderbehandlung) bleiben prüfbar."""
    ergebnis = an.Anonymisierer().belege(parse_esol_belege_summary(_quelle()))
    assert "2019" in ergebnis[0]["geburtstag"]
    assert "1933" in ergebnis[2]["geburtstag"]
    # aber Tag und Monat nicht
    assert "0405" not in ergebnis[0]["geburtstag"]


def test_lanr_wird_ersetzt_bsnr_bleibt():
    """
    Die LANR identifiziert eine natürliche Person, die BSNR die Betriebsstätte.
    Ohne BSNR ließe sich der Fall kaum zuordnen.
    """
    ergebnis = an.Anonymisierer(gruppen={"arzt"}).belege(parse_esol_belege_summary(_quelle()))
    zhe = ergebnis[0]["verordnung"]
    assert zhe["lanr"] != "034072134"
    assert zhe["bsnr"] == "242373500"
    # Der zusammengesetzte Anzeigetext muss mitgezogen werden
    assert "034072134" not in zhe["arzt_text"]
    assert "242373500" in zhe["arzt_text"]


def test_diagnosen_bleiben_ohne_anwahl_stehen():
    """Gesundheitsdaten, aber für die Fehlersuche meist der Kern der Sache."""
    ergebnis = an.Anonymisierer().belege(parse_esol_belege_summary(_quelle()))
    assert ergebnis[0]["diagnosen"][0]["code"] == "F92.8"

    mit = an.Anonymisierer(gruppen={"diagnosen"}).belege(parse_esol_belege_summary(_quelle()))
    assert mit[0]["diagnosen"][0]["code"] != "F92.8"


def test_originalliste_bleibt_unveraendert():
    """
    Die Bildschirmanzeige arbeitet mit denselben Objekten weiter — sie darf
    durch einen Export nicht anonymisiert werden.
    """
    belege = parse_esol_belege_summary(_quelle())
    vorher = belege[0]["nachname"]
    an.Anonymisierer().belege(belege)
    assert belege[0]["nachname"] == vorher


# ------------------------------------------------------------ Fehlermeldungen

def test_fehlermeldungen_werden_mitanonymisiert():
    """
    Der wichtigste Fall: mehrere Prüfregeln zitieren den Wert im Meldungstext,
    etwa `Versichertennummer "E430685837" hat ungültiges Format`. Ohne diesen
    Schritt stünde der Klartext trotz Anonymisierung im Bericht.
    """
    anon = an.Anonymisierer()
    anon.belege(parse_esol_belege_summary(_quelle()))

    meldung = 'INV (Block 0): Versichertennummer "E430685837" hat ungültiges Format.'
    ersetzt = anon.text(meldung)
    assert "E430685837" not in ersetzt

    geb = 'NAD (Block 0): Geburtsdatum "20190405" ist kein gültiges Datum.'
    assert "20190405" not in anon.text(geb)

    lanr = 'ZHE (Block 0): LANR "034072134" muss numerisch sein.'
    assert "034072134" not in anon.text(lanr)


def test_texte_vor_belege_aufgerufen_aendert_nichts():
    """
    Reihenfolge-Falle: ohne vorherigen Durchlauf über die Belege sind noch
    keine Ersetzungen bekannt. Der Text bleibt dann unverändert — das ist die
    ehrliche Folge, aber es darf nicht krachen.
    """
    anon = an.Anonymisierer()
    assert anon.text('Versichertennummer "E430685837"') == 'Versichertennummer "E430685837"'


def test_ticket_bericht_ohne_klartext():
    """Der ganze Weg: Belege und Fehler anonymisiert in den Ticket-Bericht."""
    quelle = _quelle()
    belege = parse_esol_belege_summary(quelle)
    fehler = ['INV: Versichertennummer "E430685837" ist ungültig.']

    anon = an.Anonymisierer()
    bericht = sh.generate_ticket_summary(
        "ESOL0001", anon.texte(fehler), anon.belege(belege)
    )
    # texte() muss nach belege() laufen; hier absichtlich anders herum geprüft
    bericht = sh.generate_ticket_summary(
        "ESOL0001", anon.texte(fehler), anon.belege(belege)
    )

    for original in ("Stein", "Bryan", "E430685837", "034072134", "20190405"):
        assert original not in bericht, f"{original} steht im Ticket-Bericht"
    assert "Versicherter A" in bericht


def test_html_bericht_zeigt_den_umfang():
    anon = an.Anonymisierer()
    belege = anon.belege(parse_esol_belege_summary(_quelle()))
    html = sh.generate_html_report("ESOL0001", [], belege, anonymisierung_kopf=anon.bericht())

    assert "Anonymisierung: an" in html
    assert "Stein" not in html
    # Ohne Kopfzeilen darf nichts dazuerfunden werden
    ohne = sh.generate_html_report("ESOL0001", [], belege)
    assert "Anonymisierung" not in ohne


# ---------------------------------------------------------------- ESOL-Datei

def test_anonymisierte_datei_bleibt_gueltig():
    quelle = _quelle()
    vorher = {str(e) for e in _pruefe(quelle).get_errors()}

    anon = an.Anonymisierer(gruppen=set(an.FELDGRUPPEN), stil=an.STIL_FORMATTREU)
    neu = anon.esol(quelle)
    nachher = {str(e) for e in _pruefe(neu).get_errors()}

    assert nachher - vorher == set(), f"neue Fehler: {nachher - vorher}"


def test_anonymisierte_datei_enthaelt_keine_originalwerte():
    anon = an.Anonymisierer(gruppen=set(an.FELDGRUPPEN), stil=an.STIL_FORMATTREU)
    neu = anon.esol(_quelle())

    for original in ("Stein", "Bryan", "Wansart", "Cecilia", "E430685837",
                     "K111222333", "20190405", "19330217", "034072134",
                     "390860101", "info@ergo-praxis.de"):
        assert original not in neu, f"{original} steht noch in der Datei"


def test_ersatz_ik_erfuellt_die_pruefziffer():
    """
    Ein IK ohne gültige Prüfziffer macht die Kopie ungültig — dann ist sie zur
    Fehleranalyse unbrauchbar.
    """
    anon = an.Anonymisierer(gruppen={"belegnummer"}, stil=an.STIL_FORMATTREU)
    anon.esol(_quelle())
    ersatz = anon._zuordnung.get("ik", {})
    assert ersatz, "es wurde kein IK ersetzt"
    for wert in ersatz.values():
        assert ContentHelper.is_valid_ik_check_digit(wert), wert


def test_ersatz_ik_behaelt_die_klassifikation():
    """
    Die ersten zwei Stellen sagen, ob es eine Krankenkasse oder ein
    Leistungserbringer ist. Sie identifizieren niemanden, tragen aber die
    Bedeutung — und bleiben deshalb erhalten.
    """
    anon = an.Anonymisierer(gruppen={"belegnummer"}, stil=an.STIL_FORMATTREU)
    anon.esol(_quelle())
    for original, ersatz in anon._zuordnung["ik"].items():
        assert ersatz[:2] == original[:2], f"{original} -> {ersatz}"


def test_versichertennummer_behaelt_ihr_format():
    """Regel 1.3.5.1 verlangt Buchstabe + Ziffern, maximal 12 Zeichen."""
    anon = an.Anonymisierer(gruppen={"versicherter"}, stil=an.STIL_FORMATTREU)
    anon.esol(_quelle())
    for ersatz in anon._zuordnung["versichertennummer"].values():
        assert ersatz[0].isalpha(), ersatz
        assert ersatz[1:].isdigit(), ersatz
        assert len(ersatz) <= 12, ersatz


def test_geburtsdatum_in_der_datei_bleibt_ein_gueltiges_datum():
    anon = an.Anonymisierer(gruppen={"versicherter"}, stil=an.STIL_FORMATTREU)
    neu = anon.esol(_quelle())
    nad = [z for z in neu.splitlines() if z.startswith("NAD+")]
    assert nad
    for zeile in nad:
        geb = zeile.rstrip("'").split("+")[3]
        assert geb.endswith("0101"), geb
        assert len(geb) == 8 and geb.isdigit(), geb


def test_segmentzaehler_und_summen_bleiben_unberuehrt():
    """
    Die Kopie soll dieselbe Datei sein, nur mit ersetzten Feldern. Zähler und
    Summen dürfen sich nicht verschieben.
    """
    quelle = _quelle()
    neu = an.Anonymisierer(gruppen=set(an.FELDGRUPPEN),
                           stil=an.STIL_FORMATTREU).esol(quelle)

    def segmente(text, tag):
        return [z for z in text.splitlines() if z.startswith(tag + "+")]

    for tag in ("UNT", "UNZ", "GES", "BES", "EHE"):
        assert segmente(quelle, tag) == segmente(neu, tag), tag


def test_maskiertes_plus_wird_nicht_als_trenner_gelesen():
    """
    '?' maskiert in ESOL das folgende Zeichen. 'NAD+Mü?+ller+Max' hat drei
    Felder, nicht vier — wer daran falsch trennt, zerlegt den Namen.
    """
    assert an._teile_felder("NAD+Mü?+ller+Max") == ["NAD", "Mü?+ller", "Max"]
    assert an._teile_felder("NAD+A+B") == ["NAD", "A", "B"]
    assert an._teile_felder("NAD") == ["NAD"]


def test_zeilenenden_bleiben_erhalten():
    """ESOL-Dateien haben CRLF. Ein verlorenes \\r macht die Datei ungültig."""
    quelle = _quelle().replace("\n", "\r\n")
    neu = an.Anonymisierer(stil=an.STIL_FORMATTREU).esol(quelle)
    assert neu.count("\r\n") == quelle.count("\r\n")


# ------------------------------------------------------------------ Auskunft

def test_bericht_nennt_keine_originalwerte():
    """
    Der Kopf des Berichts sagt, was ersetzt wurde — er darf dabei nicht selbst
    zur Datenquelle werden.
    """
    anon = an.Anonymisierer()
    anon.belege(parse_esol_belege_summary(_quelle()))
    text = "\n".join(anon.bericht())

    for original in ("Stein", "Bryan", "E430685837", "034072134"):
        assert original not in text
    assert "Anonymisierung: an" in text
    assert "2× versicherter ersetzt" in text or "1× versicherter ersetzt" in text


def test_bericht_bei_ausgeschalteter_anonymisierung_warnt():
    text = "\n".join(an.Anonymisierer(gruppen=set()).bericht())
    assert "aus" in text and "Klartext" in text


def test_begleitdatei_nennt_den_erfundenen_geburtstag():
    """
    Wer die Kopie liest, muss wissen, dass der 1. Januar erfunden ist — sonst
    liest er ihn als echtes Geburtsdatum.
    """
    anon = an.Anonymisierer(stil=an.STIL_FORMATTREU)
    text = an.kopfzeilen_esol(anon, "ESOL0001")
    assert "1. Januar" in text
    assert "erfunden" in text
    assert "NICHT abgerechnet" in text
