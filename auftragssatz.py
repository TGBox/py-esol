"""
Auftragssatz (.auf) lesen, prüfen und den Versandweg bestimmen.

Zu jeder ESOL-Nutzdatendatei gehört ein Auftragssatz mit 348 Zeichen
(Richtlinien für den Datenaustausch im Gesundheits- und Sozialwesen). Steht
darin etwas anderes als in der Nutzdatendatei, weist die Annahmestelle die
Lieferung ab, bevor der Inhalt überhaupt geprüft wird. Dieses Modul zeigt die
Felder im Klartext und prüft:

  - Länge und Kennung des Auftragssatzes,
  - Dateiname und logischen Dateinamen gegen die Nutzdatendatei,
  - Dateigröße im Auftragssatz gegen die tatsächliche Datei,
  - Absender und Empfänger gegen den UNB (auch: vertauscht),
  - Empfänger gegen die Datenannahmestelle laut Kostenträgerdatei,

und gibt aus, an welche Annahmestelle und Mailadresse die Datei gehen müsste.

Das Feld-Layout ist dasselbe, das tools/generate_auf.py schreibt.
Nur Codes, deren Bedeutung belegt ist, bekommen einen Klartext; alles andere
wird roh angezeigt statt geraten.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import codelisten
from parser.segment_tokenizer import SegmentTokenizer
from rules.level3.content_helper import ContentHelper

SATZLAENGE = 348

FEHLER = "FEHLER"
WARNUNG = "WARNUNG"
HINWEIS = "HINWEIS"
OK = "OK"

# (Schlüssel, erste Stelle, Länge, Beschriftung) — Stellen ab 1 gezählt
FELDER: List[Tuple[str, int, int, str]] = [
    ("kennung", 1, 6, "Identifikator"),
    ("version", 7, 2, "Version"),
    ("laenge", 9, 8, "Länge des Auftragssatzes"),
    ("sequenz", 17, 3, "Sequenznummer"),
    ("dateiname", 20, 8, "Dateiname (Verfahren + Transfer-Nr.)"),
    ("spezifikation", 28, 5, "Spezifikation"),
    ("absender_eigner", 33, 15, "Absender (Eigner)"),
    ("absender_physisch", 48, 15, "Absender (physikalisch)"),
    ("empfaenger_nutzer", 63, 15, "Empfänger (Nutzer)"),
    ("empfaenger_physisch", 78, 15, "Empfänger (physikalisch)"),
    ("fehler_nummer", 93, 6, "Fehler-Nummer"),
    ("fehler_massnahme", 99, 6, "Fehler-Maßnahme"),
    ("logischer_name", 105, 11, "Logischer Dateiname"),
    ("erstellt", 116, 14, "Erstellt"),
    ("gesendet", 130, 14, "Gesendet"),
    ("empfangen_1", 144, 14, "Empfangen (Start)"),
    ("empfangen_2", 158, 14, "Empfangen (Ende)"),
    ("dateiversion", 172, 6, "Dateiversion"),
    ("korrektur", 178, 1, "Korrektur"),
    ("groesse_nutzdaten", 179, 12, "Dateigröße Nutzdaten"),
    ("groesse_uebertragen", 191, 12, "Dateigröße übertragen"),
    ("zeichensatz", 203, 2, "Zeichensatz"),
    ("komprimierung", 205, 2, "Komprimierung"),
    ("verschluesselung", 207, 2, "Verschlüsselung"),
    ("signatur", 209, 2, "Elektronische Unterschrift"),
    ("uebertragungsweg", 230, 1, "Übertragungsweg"),
]

# Felder, die in der Klartextanzeige erscheinen (der Rest ist Technik)
ANZEIGE = [
    "dateiname", "absender_eigner", "absender_physisch", "empfaenger_nutzer",
    "empfaenger_physisch", "logischer_name", "erstellt", "gesendet",
    "groesse_nutzdaten", "groesse_uebertragen", "zeichensatz",
    "komprimierung", "verschluesselung", "fehler_nummer",
]

# Belegt durch die Richtlinien bzw. tools/generate_auf.py
_ZEICHENSATZ = {"I1": "ISO-8859-1", "I5": "ISO-8859-15"}
_KEINE = {"00": "keine"}

_IK_FELDER = ("absender_eigner", "absender_physisch",
              "empfaenger_nutzer", "empfaenger_physisch")


@dataclass
class Befund:
    stufe: str
    text: str


@dataclass
class Bericht:
    auf_pfad: Path
    nutz_pfad: Optional[Path]
    felder: Dict[str, str] = field(default_factory=dict)
    befunde: List[Befund] = field(default_factory=list)
    versand: List[str] = field(default_factory=list)

    def add(self, stufe: str, text: str) -> None:
        self.befunde.append(Befund(stufe, text))

    @property
    def hat_fehler(self) -> bool:
        return any(b.stufe == FEHLER for b in self.befunde)


# ---------------------------------------------------------------------------
# Dateien finden und lesen
# ---------------------------------------------------------------------------

def finde_auftragssatz(nutz_pfad: Path) -> Optional[Path]:
    """`<Datei>.auf` neben der Nutzdatendatei, Groß-/Kleinschreibung egal."""
    nutz_pfad = Path(nutz_pfad)
    gesucht = (nutz_pfad.name + ".auf").lower()
    try:
        for kandidat in nutz_pfad.parent.iterdir():
            if kandidat.name.lower() == gesucht and kandidat.is_file():
                return kandidat
    except OSError:
        return None
    return None


def finde_nutzdatei(auf_pfad: Path) -> Optional[Path]:
    """Die Nutzdatendatei zu `<Datei>.auf` (Endung abschneiden)."""
    auf_pfad = Path(auf_pfad)
    if auf_pfad.suffix.lower() != ".auf":
        return None
    kandidat = auf_pfad.with_suffix("")
    return kandidat if kandidat.is_file() else None


def lese_felder(roh: bytes) -> Dict[str, str]:
    text = roh.decode("iso-8859-1")
    return {name: text[start - 1:start - 1 + laenge]
            for name, start, laenge, _ in FELDER}


def _zahl(wert: str) -> Optional[int]:
    wert = wert.strip()
    return int(wert) if wert.isdigit() else None


def _zeit(wert: str) -> str:
    """JHJJMMTThhmmss -> TT.MM.JJJJ hh:mm:ss; Nullen = leer."""
    w = wert.strip()
    if not w.strip("0"):
        return ""
    if len(w) == 14 and w.isdigit():
        return f"{w[6:8]}.{w[4:6]}.{w[0:4]} {w[8:10]}:{w[10:12]}:{w[12:14]}"
    return w


def _code(wert: str, tabelle: Dict[str, str]) -> str:
    w = wert.strip()
    if w in tabelle:
        return f"{w} ({tabelle[w]})"
    return f"{w} (Bedeutung nicht hinterlegt)" if w else "—"


def klartext(name: str, wert: str) -> str:
    if name in _IK_FELDER:
        return codelisten.describe_ik(wert.strip())
    if name in ("erstellt", "gesendet"):
        return _zeit(wert) or "—"
    if name in ("groesse_nutzdaten", "groesse_uebertragen"):
        zahl = _zahl(wert)
        return f"{zahl} Bytes" if zahl is not None else repr(wert)
    if name == "zeichensatz":
        return _code(wert, _ZEICHENSATZ)
    if name in ("komprimierung", "verschluesselung"):
        return _code(wert, _KEINE)
    if name == "fehler_nummer":
        return wert.strip() if wert.strip("0 ") else "—"
    return wert.strip() or "—"


# ---------------------------------------------------------------------------
# Nutzdatendatei
# ---------------------------------------------------------------------------

@dataclass
class _Nutzdaten:
    groesse: int
    crlf: int
    unb_absender: str
    unb_empfaenger: str
    unb_zeit: str
    logischer_name: str
    le_ik: str
    kostentraeger: List[str]


def _lese_nutzdaten(pfad: Path) -> _Nutzdaten:
    roh = pfad.read_bytes()
    text = roh.decode("iso-8859-1")
    tok = SegmentTokenizer()
    segmente = [tok.parse_segment(s) for s in tok.tokenize_segments(text)]
    unb = next((s for s in segmente if s.get("tag") == "UNB"), None)
    if unb is None:
        raise ValueError("Kein UNB-Segment in der Nutzdatendatei.")
    g = ContentHelper.get_field
    kostentraeger: List[str] = []
    le_ik = ""
    for seg in segmente:
        if seg.get("tag") != "FKT":
            continue
        le_ik = le_ik or (g(seg, 2) or "").strip()
        ik = (g(seg, 3) or "").strip()
        if ik and ik not in kostentraeger:
            kostentraeger.append(ik)
    return _Nutzdaten(
        groesse=len(roh),
        crlf=roh.count(b"\r\n"),
        unb_absender=(g(unb, 1) or "").strip(),
        unb_empfaenger=(g(unb, 2) or "").strip(),
        unb_zeit=f"{g(unb, 3, 0) or ''}{g(unb, 3, 1) or ''}".strip(),
        logischer_name=(g(unb, 6) or "").strip(),
        le_ik=le_ik,
        kostentraeger=kostentraeger,
    )


# ---------------------------------------------------------------------------
# Versandweg laut Kostenträgerdatei
# ---------------------------------------------------------------------------

def datenannahmestelle(kostentraeger_ik: str, max_schritte: int = 4
                       ) -> Tuple[Dict[str, str], List[str]]:
    """
    DFÜ-Annahmestelle zu einem Kostenträger-IK.

    Viele Kassen-IKs haben in der Kostenträgerdatei keine eigene Annahmestelle,
    sondern verweisen auf ein anderes Kostenträger-IK (Verknüpfung "Zahlung"),
    das sie dann hat — z. B. BARMER 104080005 -> 104940005 -> DDG. Dem Verweis
    wird hier gefolgt. Rückgabe: (Annahmestelle, Weg der IKs).
    """
    weg = [kostentraeger_ik]
    ik = kostentraeger_ik
    for _ in range(max_schritte):
        stelle = codelisten.annahmestelle(ik, "dfu")
        if stelle.get("ik"):
            return stelle, weg
        naechstes = codelisten.annahmestelle(ik, "zahlung").get("ik", "")
        if not naechstes or naechstes in weg:
            break
        weg.append(naechstes)
        ik = naechstes
    return {}, weg


def _versand_zeilen(kostentraeger_ik: str, stelle: Dict[str, str],
                    weg: List[str]) -> List[str]:
    zeilen = [f"Kostenträger: {codelisten.describe_ik(kostentraeger_ik)}"]
    if len(weg) > 1:
        zeilen.append("  verweist in der Kostenträgerdatei auf: "
                      + " -> ".join(weg[1:]))
    if not stelle:
        zeilen.append("  Keine Datenannahmestelle in der Kostenträgerdatei "
                      "gefunden — bitte in der aktuellen Kostenträgerdatei "
                      "nachsehen.")
        return zeilen
    text = codelisten.describe_ik(stelle["ik"])
    if stelle.get("art_text"):
        text += f" [{stelle['art_text']}]"
    zeilen.append(f"  Datenannahmestelle (DFÜ): {text}")
    eintrag = codelisten.kostentraeger(stelle["ik"])
    if eintrag.get("email"):
        zeilen.append(f"  Mailadresse: {eintrag['email']}")
    else:
        zeilen.append("  Mailadresse: nicht in der Kostenträgerdatei")
    anschrift = ", ".join(p for p in [
        str(eintrag.get("strasse", "")).strip(),
        f"{eintrag.get('plz', '')} {eintrag.get('ort', '')}".strip(),
    ] if p)
    if anschrift:
        zeilen.append(f"  Anschrift: {anschrift}")
    return zeilen


# ---------------------------------------------------------------------------
# Prüfung
# ---------------------------------------------------------------------------

def _pruefe_groesse(b: Bericht, nutz: _Nutzdaten, nutz_pfad: Path) -> None:
    f = b.felder
    soll_nutz = _zahl(f["groesse_nutzdaten"])
    soll_ueb = _zahl(f["groesse_uebertragen"])
    ist = nutz.groesse
    if soll_nutz is None or soll_ueb is None:
        b.add(FEHLER, "Dateigröße im Auftragssatz ist keine Zahl "
                      f"({f['groesse_nutzdaten']!r} / {f['groesse_uebertragen']!r}).")
        return

    unveraendert = (f["verschluesselung"].strip() in ("00", "")
                    and f["komprimierung"].strip() in ("00", ""))
    if unveraendert:
        if soll_nutz == ist and soll_ueb == ist:
            b.add(OK, f"Dateigröße stimmt ({ist} Bytes).")
            return
        laut_auf = (f"{soll_nutz}" if soll_nutz == soll_ueb
                    else f"{soll_nutz} / {soll_ueb}")
        b.add(FEHLER, f"Dateigröße passt nicht: Auftragssatz {laut_auf} "
                      f"Bytes, Datei {ist} Bytes (Differenz "
                      f"{ist - soll_nutz:+d}).")
        if nutz.crlf and soll_nutz == ist - nutz.crlf:
            b.add(HINWEIS, "Die Datei ist genau um die Zahl ihrer Windows-"
                           "Zeilenumbrüche (CR LF) größer. Sie wurde "
                           "vermutlich nach dem Erstellen des Auftragssatzes "
                           "in einem Editor gespeichert.")
        elif soll_nutz != soll_ueb:
            b.add(HINWEIS, "Die beiden Größenfelder unterscheiden sich, obwohl "
                           "laut Auftragssatz weder komprimiert noch "
                           "verschlüsselt wurde.")
        _hinweis_juenger(b, nutz_pfad)
        return

    # Verschlüsselt oder komprimiert: Nutzdaten = Original, übertragen = Datei
    if ist == soll_ueb:
        b.add(OK, f"Dateigröße stimmt mit der übertragenen Größe überein "
                  f"({ist} Bytes; unverschlüsselt {soll_nutz} Bytes).")
    elif ist == soll_nutz:
        b.add(HINWEIS, f"Die Datei hat die unverschlüsselte Größe ({ist} "
                       f"Bytes). Laut Auftragssatz wird sie verschlüsselt bzw. "
                       f"komprimiert mit {soll_ueb} Bytes übertragen — die "
                       f"Abweichung ist dann kein Fehler.")
    else:
        b.add(FEHLER, f"Dateigröße passt nicht: Auftragssatz {soll_nutz} "
                      f"(unverschlüsselt) / {soll_ueb} (übertragen) Bytes, "
                      f"Datei {ist} Bytes.")
        _hinweis_juenger(b, nutz_pfad)


def _hinweis_juenger(b: Bericht, nutz_pfad: Path) -> None:
    try:
        if os.path.getmtime(nutz_pfad) > os.path.getmtime(b.auf_pfad) + 2:
            b.add(HINWEIS, "Laut Änderungsdatum wurde die Nutzdatendatei "
                           "nach dem Auftragssatz gespeichert — vermutlich "
                           "nachträglich geändert. Auftragssatz neu erstellen.")
    except OSError:
        pass


def _pruefe_ik(b: Bericht, nutz: _Nutzdaten) -> List[str]:
    f = {k: b.felder[k].strip() for k in _IK_FELDER}
    absender = {f["absender_eigner"], f["absender_physisch"]}
    empfaenger = {f["empfaenger_nutzer"], f["empfaenger_physisch"]}

    vertauscht = (nutz.unb_empfaenger in absender
                  and (nutz.unb_absender in empfaenger
                       or (nutz.le_ik and nutz.le_ik in empfaenger)))
    if vertauscht:
        b.add(FEHLER, "Absender und Empfänger sind im Auftragssatz vertauscht: "
                      f"als Absender steht die Annahmestelle "
                      f"{codelisten.describe_ik(nutz.unb_empfaenger)}.")
    else:
        if nutz.unb_absender in absender:
            b.add(OK, "Absender passt zum UNB der Nutzdatendatei.")
        else:
            b.add(FEHLER, f"Absender im Auftragssatz ({' / '.join(sorted(absender))}) "
                          f"passt nicht zum UNB-Absender {nutz.unb_absender}.")
        if f["empfaenger_physisch"] == nutz.unb_empfaenger:
            b.add(OK, "Empfänger passt zum UNB der Nutzdatendatei.")
        else:
            b.add(FEHLER, f"Empfänger im Auftragssatz "
                          f"({f['empfaenger_physisch'] or 'leer'}) passt nicht "
                          f"zum UNB-Empfänger {nutz.unb_empfaenger}.")
        if f["empfaenger_nutzer"] != f["empfaenger_physisch"]:
            b.add(HINWEIS, "Empfänger (Nutzer) und Empfänger (physikalisch) "
                           "unterscheiden sich.")
    return [f["empfaenger_physisch"]]


def _pruefe_routing(b: Bericht, nutz: _Nutzdaten, auf_empfaenger: str) -> None:
    if not nutz.kostentraeger:
        b.add(WARNUNG, "Kein Kostenträger-IK im FKT gefunden — Versandweg "
                       "nicht bestimmbar.")
        return
    stellen: Dict[str, List[str]] = {}
    for kt in nutz.kostentraeger:
        stelle, weg = datenannahmestelle(kt)
        b.versand.extend(_versand_zeilen(kt, stelle, weg))
        if stelle.get("ik"):
            stellen.setdefault(stelle["ik"], []).append(kt)

    if not stellen:
        b.add(WARNUNG, "Datenannahmestelle laut Kostenträgerdatei unbekannt.")
        return
    if len(stellen) > 1:
        b.add(FEHLER, "Die Datei enthält Rechnungen für verschiedene "
                      "Datenannahmestellen: "
                      + ", ".join(codelisten.describe_ik(ik) for ik in stellen)
                      + ". Je Annahmestelle ist eine eigene Lieferung nötig.")
        return
    soll = next(iter(stellen))
    pruefen = {"Auftragssatz": auf_empfaenger, "UNB": nutz.unb_empfaenger}
    abweichend = [wo for wo, ik in pruefen.items() if ik != soll]
    if not abweichend:
        b.add(OK, "Empfänger ist die Datenannahmestelle laut "
                  "Kostenträgerdatei.")
    else:
        b.add(FEHLER, f"Empfänger ({' / '.join(abweichend)}: "
                      f"{codelisten.describe_ik(pruefen[abweichend[0]])}) ist "
                      f"nicht die Datenannahmestelle laut Kostenträgerdatei "
                      f"({codelisten.describe_ik(soll)}). Falls die "
                      f"Kostenträgerdatei veraltet ist, mit dem aktuellen "
                      f"Stand abgleichen.")


def pruefe(pfad: Path) -> Bericht:
    """
    Prüft einen Auftragssatz. `pfad` darf die .auf-Datei oder die
    Nutzdatendatei sein; die jeweils andere wird daneben gesucht.
    """
    pfad = Path(pfad)
    if pfad.suffix.lower() == ".auf":
        auf_pfad, nutz_pfad = pfad, finde_nutzdatei(pfad)
    else:
        auf_pfad, nutz_pfad = finde_auftragssatz(pfad), pfad
        if auf_pfad is None:
            b = Bericht(auf_pfad=Path(str(pfad) + ".auf"), nutz_pfad=pfad)
            b.add(WARNUNG, f"Kein Auftragssatz {pfad.name}.auf neben der "
                           f"Datei gefunden.")
            return b

    b = Bericht(auf_pfad=auf_pfad, nutz_pfad=nutz_pfad)
    roh = auf_pfad.read_bytes()
    b.felder = lese_felder(roh)
    f = b.felder

    # Aufbau
    verlaesslich = len(roh) == SATZLAENGE
    if not verlaesslich:
        extra = ""
        if roh.endswith((b"\r\n", b"\n")) and len(roh.rstrip(b"\r\n")) == SATZLAENGE:
            extra = " Am Ende steht ein Zeilenumbruch, der nicht hingehört."
        b.add(FEHLER, f"Auftragssatz hat {len(roh)} statt {SATZLAENGE} "
                      f"Zeichen — die Felder ab der Abweichung sind "
                      f"verschoben und unten nicht verlässlich.{extra}")
    else:
        b.add(OK, f"Länge {SATZLAENGE} Zeichen.")
    if f["kennung"] != "500000" or _zahl(f["laenge"]) != SATZLAENGE:
        b.add(FEHLER, f"Kopf des Auftragssatzes ungültig "
                      f"(Kennung {f['kennung']!r}, Länge {f['laenge']!r}).")
    zs = f["zeichensatz"].strip()
    if verlaesslich and zs != "I1":
        b.add(HINWEIS, f"Zeichensatz {_code(zs, _ZEICHENSATZ)} — "
                       f"ESOL-Dateien sind ISO-8859-1 (I1).")
    if f["fehler_nummer"].strip("0 "):
        b.add(WARNUNG, f"Im Auftragssatz ist eine Fehler-Nummer eingetragen: "
                       f"{f['fehler_nummer'].strip()}.")

    if nutz_pfad is None:
        b.add(WARNUNG, f"Nutzdatendatei {auf_pfad.with_suffix('').name} nicht "
                       f"gefunden — nur der Auftragssatz wurde geprüft.")
        return b

    try:
        nutz = _lese_nutzdaten(nutz_pfad)
    except (OSError, ValueError) as exc:
        b.add(FEHLER, f"Nutzdatendatei nicht lesbar: {exc}")
        return b

    if not verlaesslich:
        # Verschobene Felder würden nur Folgefehler erzeugen. Der Versandweg
        # kommt aus der Nutzdatendatei und ist trotzdem verlässlich.
        _pruefe_routing(b, nutz, f["empfaenger_physisch"].strip())
        return b

    if f["dateiname"].strip() == nutz_pfad.name:
        b.add(OK, "Dateiname passt.")
    else:
        b.add(FEHLER, f"Dateiname im Auftragssatz ({f['dateiname'].strip()!r}) "
                      f"passt nicht zur Datei {nutz_pfad.name}.")
    if f["logischer_name"].strip() == nutz.logischer_name:
        b.add(OK, "Logischer Dateiname passt zum UNB.")
    else:
        b.add(FEHLER, f"Logischer Dateiname im Auftragssatz "
                      f"({f['logischer_name'].strip()!r}) passt nicht zum UNB "
                      f"({nutz.logischer_name!r}).")

    _pruefe_groesse(b, nutz, nutz_pfad)
    empfaenger = _pruefe_ik(b, nutz)
    _pruefe_routing(b, nutz, empfaenger[0])
    return b


# ---------------------------------------------------------------------------
# Ausgabe
# ---------------------------------------------------------------------------

_BESCHRIFTUNG = {name: text for name, _, _, text in FELDER}


def bericht_text(b: Bericht) -> str:
    zeilen = [f"Auftragssatz: {b.auf_pfad.name}"]
    if b.felder:
        zeilen.append("")
        breite = max(len(_BESCHRIFTUNG[n]) for n in ANZEIGE) + 1
        for name in ANZEIGE:
            zeilen.append(f"  {(_BESCHRIFTUNG[name] + ':').ljust(breite)} "
                          f"{klartext(name, b.felder[name])}")
    zeilen.append("")
    zeilen.append("Prüfung:")
    for befund in b.befunde:
        zeilen.append(f"  {befund.stufe:<8}{befund.text}")
    if b.versand:
        zeilen.append("")
        zeilen.append("Versand laut Kostenträgerdatei:")
        zeilen.extend(f"  {z}" for z in b.versand)
    return "\n".join(zeilen) + "\n"
