"""
Abgleich mit der Technischen Anlage 1 zu den Richtlinien nach § 302 SGB V,
TP 5 Version 21, Stand 17.02.2025, anzuwenden ab 01.10.2025.

Die Tests halten die Stellen fest, an denen die Prüfung bei einem Abgleich mit
der Anlage nachgebessert wurde. Grundlage ist die Referenzdatei
tests/fixtures/valid_esol_smoke; jeder Test verändert daran genau eine Stelle,
damit im Test nur der Unterschied steht (siehe tests/anlage_basis.py).
"""

import pytest

from schema.schema import SchemaFactory
from tests.anlage_basis import (
    codes,
    echte_dateien,
    ersetzt,
    mit_segment,
    ohne,
    zusammensetzen,
    basis_zeilen,
)
from esol_validator import EsolValidator
from tools.generate_correction import read_esol_file_text


def test_basisdatei_ist_fehlerfrei():
    """Ohne diese Zusicherung sagt kein anderer Test in dieser Datei etwas."""
    assert codes(zusammensetzen(basis_zeilen())) == set()


# --- Meldungen der Prüfstufen 1 und 2 dürfen nicht verschwinden -------------


def test_meldungen_der_stufe_2_erreichen_das_ergebnis():
    """
    Der schwerste Fund des Abgleichs: create_validation_error nahm die Severity
    an vierter Stelle, alle Regeln der Stufen 1 und 2 übergaben dort das
    Segmentkürzel. Damit stand "REC" oder "UNB" in der Severity, get_errors()
    filterte die Meldung heraus, und has_stufe_errors() sah eine fehlerfreie
    Stufe — die Prüfung lief in Stufe 3 weiter, obwohl Kapitel 6.2 der Anlage
    die Abweisung der Datei verlangt.

    Der Test prüft die Wirkung, nicht die Schreibweise: eine Datei ohne FKT
    muss auf Stufe 2 auffallen.
    """
    validator = EsolValidator()
    validator.register_default_rules()
    ergebnis = validator.validate_string(ohne("FKT"))

    assert ergebnis.error_count() > 0
    assert ergebnis.has_stufe_errors(2)
    for fehler in ergebnis.get_errors():
        assert fehler.severity == "error", fehler


def test_stufe_2_bricht_ab_und_stufe_3_laeuft_nicht_mehr():
    """
    Kapitel 6.2: "ist die gesamte Datei zurückzuweisen". Es darf also keine
    Meldung der Stufe 3 mehr kommen, wenn Stufe 2 Fehler hat — sonst steht in
    der Fehlerliste eine Mischung, die den Anwender in die falsche Ecke
    schickt.
    """
    validator = EsolValidator()
    validator.register_default_rules()
    ergebnis = validator.validate_string(ohne("FKT"))

    stufen = {e.stufe for e in ergebnis.get_errors()}
    assert stufen == {2}, stufen


# --- Regel 1.2.1.6: Vorkommen der Segmente ---------------------------------


def test_fehlendes_nad_fehlt_nicht_unbemerkt():
    """NAD ist Muss, 1 je INV (Anlage 1, 5.5.3.1)."""
    assert "1.2.1.6" in codes(ohne("NAD"))


def test_fehlendes_zhe_fehlt_nicht_unbemerkt():
    """ZHE ist Muss, 1 je Abrechnungsfall (Anlage 1, 5.5.3.3)."""
    assert "1.2.1.6" in codes(ohne("ZHE"))


def test_fehlendes_nam_fehlt_nicht_unbemerkt():
    """NAM ist Muss, 1 je SLGA (Anlage 1, 5.5.2)."""
    assert "1.2.1.6" in codes(ohne("NAM"))


def test_zhe_darf_nicht_zweimal_im_block_stehen():
    zeilen = []
    for z in basis_zeilen():
        zeilen.append(z)
        if z.startswith("ZHE"):
            zeilen.append(z)
    assert "1.2.1.6" in codes(zusammensetzen(zeilen))


def test_slga_braucht_mindestens_zwei_ges():
    """
    GES ist mit 2-9 angegeben: ein GES für den Summenstatus 00 und mindestens
    eines je Versichertenstatus (Anlage 1, 5.5.2).
    """
    zeilen, gesehen = [], False
    for z in basis_zeilen():
        if z.startswith("GES"):
            if not gesehen:
                gesehen = True
                zeilen.append(z)
        else:
            zeilen.append(z)
    assert "1.2.1.6" in codes(zusammensetzen(zeilen))


def test_bes_und_gzf_schliessen_sich_aus():
    assert "1.2.1.6" in codes(mit_segment("BES", "GZF+10,00+10,00+0,00'"))


# --- Regel 1.2.2.8: überzählige Felder -------------------------------------


def test_ueberzaehliges_feld_im_segment():
    """
    Kapitel 6.2 verlangt die Prüfung des Vorkommens der Felder. Ein Segment mit
    mehr Feldern als vorgesehen entsteht durch ein '+' zu viel oder durch ein
    mitgeschlepptes Feld aus einem anderen Leistungsbereich.
    """
    assert "1.2.2.8" in codes(ersetzt("++0+1+2'", "++0+1+2+00501'"))


# --- Feldbeschreibung gegen die Anlage -------------------------------------

# Aus den Feldtabellen der Anlage abgeschrieben: (Name in der Anlage,
# Anz. Stellen, Nachkommastellen, Feldtyp, Feldart). Die Anlage zählt das
# Segmentkennzeichen als Feld 1, das Schema beginnt beim ersten Datenfeld —
# hier steht die Zählung des Schemas.
ANLAGE_ZHE = [
    ("Betriebsstättennummer", 9, None, "AN", "M"),
    ("Lebenslange Arztnummer", 9, None, "AN", "M"),
    ("Verordnungsdatum", 8, None, "N", "M"),
    ("Zuzahlungskennzeichen", 1, None, "N", "M"),
    ("Diagnosegruppe / Indikationsgruppe", 4, None, "AN", "M"),
    ("Kennzeichen Verordnungsart bei Heilmitteln", 2, None, "N", "M"),
    ("Kennzeichen Verordnungsbesonderheiten", 1, None, "N", "K"),
    ("Unfallkennzeichen", 1, None, "N", "K"),
    ("Kennzeichen BVG/Sonstiges/SER", 1, None, "N", "K"),
    ("Behandlungsbeginn", None, None, None, "K"),   # "Feld wird nicht mehr gefüllt"
    ("Therapiebericht angefordert", 1, None, "N", "K"),
    ("Hausbesuch", 1, None, "N", "K"),
    ("Leitsymptomatik", 4, None, "AN", "M"),
    ("Patientenindividuelle Leitsymptomatik", 70, None, "AN", "K"),
    ("Dringlicher Behandlungsbedarf", 1, None, "N", "M"),
    ("Heilmittel-Bereich", 1, None, "N", "K"),
    ("Therapiefrequenz", 1, None, "N", "M"),
]

ANLAGE_BES_B = [
    ("Gesamtbetrag Brutto", 10, 2, "N", "M"),
    ("Gesamtbetrag gesetzliche Zuzahlung", 10, 2, "N", "K"),
    ("Gesamtbetrag prozentuale Zuzahlung", 10, 2, "N", "K"),
    ("pauschaler Zuzahlungsbetrag", 10, 2, "N", "K"),
    ("Pauschale Korrekturabzug", 10, 2, "N", "K"),
]

ANLAGE_GZF = [
    ("Gesamtbetrag Forderung gesetzliche Zuzahlung", 10, 2, "N", "M"),
    ("Gesamtbetrag Forderung prozentuale Zuzahlung", 10, 2, "N", "K"),
    ("Forderung pauschaler Zuzahlungsbetrag", 10, 2, "N", "K"),
]


def _vergleiche(tag, kontext, erwartet):
    definition = SchemaFactory.create().get(tag, kontext)
    assert definition is not None, f"{tag} fehlt im Schema"
    assert definition.field_count() == len(erwartet), (
        f"{tag}: Schema hat {definition.field_count()} Felder, "
        f"die Anlage {len(erwartet)}"
    )
    for i, (name, laenge, dezimal, typ, art) in enumerate(erwartet):
        feld = definition.get_field(i)
        if laenge is not None:
            assert feld.get("maxLen") == laenge, f"{tag} Feld {i+1} ({name}): Länge"
            assert (feld.get("decimals") or None) == dezimal, \
                f"{tag} Feld {i+1} ({name}): Nachkommastellen"
            assert feld.get("type") == typ, f"{tag} Feld {i+1} ({name}): Feldtyp"
        assert feld.get("art") == art, f"{tag} Feld {i+1} ({name}): Feldart"


def test_zhe_entspricht_der_anlage():
    _vergleiche("ZHE", "SLLA", ANLAGE_ZHE)


def test_bes_entspricht_der_anlage():
    _vergleiche("BES", "SLLA", ANLAGE_BES_B)


def test_gzf_entspricht_der_anlage():
    _vergleiche("GZF", "SLLA", ANLAGE_GZF)


# --- Kapitel 5.1 Absatz 9: Länge numerischer Felder ------------------------


def test_minuszeichen_und_komma_zaehlen_nicht_zur_laenge():
    """
    "Das Minuszeichen und das Dezimalzeichen werden bei der Ermittlung der
    maximalen Länge eines Datenelementwertes nicht mitgezählt."

    BES.Gesamtbetrag Brutto ist mit ..10,2 angegeben: acht Ganz- und zwei
    Nachkommastellen. "99999999,99" hat elf Zeichen, aber zehn Ziffern und ist
    damit zulässig; eine Ziffer mehr nicht.
    """
    assert "1.2.2.6" not in codes(ersetzt("BES+100,00+", "BES+99999999,99+"))
    assert "1.2.2.6" in codes(ersetzt("BES+100,00+", "BES+999999999,99+"))


def test_buchstabe_in_numerischem_feld_faellt_auf():
    """Kapitel 6.2 nennt genau diesen Fall als Grund zur Abweisung."""
    assert "1.2.2.5" in codes(ersetzt("+20250528+0+EN1", "+2025X528+0+EN1"))


# --- EVO: Mindestlänge der eVO-ID ------------------------------------------


def test_evo_id_mindestlaenge():
    """
    Die Anlage gibt für EVO.eVO-ID "22..256" an, also eine Mindestlänge:
    "Mindestens anzugeben ist die 22-stellige eID aus der eVerordnung." Es ist
    die einzige Mindestlängenangabe der ganzen Anlage; das Schema kannte den
    Begriff vorher nicht und ließ jede Länge bis 256 durch.
    """
    assert "1.2.2.6" not in codes(mit_segment("NAD", f"EVO+{'A' * 22}'"))
    assert "1.2.2.6" in codes(mit_segment("NAD", f"EVO+{'A' * 21}'"))
    assert "1.2.2.6" not in codes(mit_segment("NAD", f"EVO+{'A' * 256}'"))
    assert "1.2.2.6" in codes(mit_segment("NAD", f"EVO+{'A' * 257}'"))


# --- Gegenprobe auf echten Dateien ----------------------------------------


@pytest.mark.skipif(not echte_dateien(), reason="testdata/in liegt nicht vor")
def test_echte_dateien_bleiben_ohne_neue_befunde():
    """
    Die Gegenprobe zu allem oben: keine der nachgebesserten Regeln darf auf
    echten Abrechnungsdateien anschlagen. Bekannt und unverändert sind allein
    die Aufhebungszeichen-Fehler (1.2.3.1) in drei Dateien.

    testdata/ liegt nicht im Repository — im CI wird dieser Test übersprungen.
    """
    unerwartet = {}
    for pfad in echte_dateien():
        gefunden = codes(read_esol_file_text(pfad)) - {"1.2.3.1"}
        if gefunden:
            unerwartet[pfad.name] = sorted(gefunden)
    assert unerwartet == {}, unerwartet
