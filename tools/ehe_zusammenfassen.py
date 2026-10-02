#!/usr/bin/env python3
"""
EHE zusammenfassen — fasst gleiche Leistungen am gleichen Tag über die Anzahl zusammen.

Manche Praxisprogramme schreiben bei Blanko-Verordnungen jedes Zeitintervall als
eigenes EHE-Segment mit Anzahl 1. Das verletzt Regel 1.4.1 (gleiche Position am
gleichen Tag im selben Beleg) und erzeugt die Warnung 1.3.8.7.

Zusammengefasst werden nur EHE-Segmente desselben Belegs (INV-Block), die in
allen Feldern außer der Anzahl übereinstimmen — also gleicher Tarif, gleiche
Position, gleicher Einzelpreis, gleiches Datum, gleiche Zuzahlung je Einheit.
Das erste Segment bleibt an seiner Stelle und erhält die Summe der Anzahlen, die
übrigen entfallen. Die Beträge im BES ändern sich dadurch nicht; der
Segmentzähler im UNT wird angepasst.

Gleiche Position am gleichen Tag mit abweichendem Preis o. Ä. wird NICHT
angefasst, sondern im Bericht gemeldet.

Das Original bleibt immer unverändert. Ohne --out-dir (oder wenn der Ausgabeordner
der Quellordner ist) landet die bereinigte Datei unter <Quellordner>/bereinigt/,
mit gleichem Dateinamen und in ISO-8859-1.

Nutzung:
  python ehe_zusammenfassen.py <datei> [<datei> ...] [--out-dir ORDNER]
"""

import argparse
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.generate_correction import pruefe_iso_8859_1, read_esol_file_text

UNTERORDNER = "bereinigt"

# Ein Segment endet am ersten nicht maskierten Apostroph; "?" maskiert das
# folgende Zeichen. Der Leerraum danach (Zeilenumbruch) bleibt erhalten.
_SEGMENT_RE = re.compile(r"((?:\?.|[^'?])*)'([ \t\r\n]*)", re.S)
_TRENNER_RE = re.compile(r"(?<!\?)\+")


def _segmente(text: str) -> Tuple[List[Tuple[str, str]], str]:
    """Zerlegt den Text in (Segment, folgender Leerraum). Rest = Text nach dem letzten Segment."""
    teile: List[Tuple[str, str]] = []
    pos = 0
    for m in _SEGMENT_RE.finditer(text):
        if m.start() != pos:
            break
        teile.append((m.group(1), m.group(2)))
        pos = m.end()
    return teile, text[pos:]


def _elemente(segment: str) -> List[str]:
    # Unmaskierte "+" trennen; ein "?" vor "+" bleibt Teil des Werts. "??+"
    # (maskiertes Fragezeichen vor Trenner) kommt in EHE-Segmenten nicht vor.
    return _TRENNER_RE.split(segment)


def _zahl(wert: str) -> Optional[Decimal]:
    try:
        return Decimal(wert.replace(",", "."))
    except InvalidOperation:
        return None


def _formatiere(zahl: Decimal, vorlage: str) -> str:
    """Schreibt die Zahl mit so vielen Nachkommastellen wie die Vorlage ("1,00" -> 2)."""
    stellen = len(vorlage.split(",", 1)[1]) if "," in vorlage else 0
    text = f"{zahl:.{stellen}f}"
    return text.replace(".", ",")


def zusammenfassen(text: str) -> Tuple[str, List[str]]:
    """
    Fasst gleiche EHE-Segmente zusammen.
    Rückgabe: (neuer Text, Bericht). Der Bericht ist leer, wenn nichts zu tun war.
    """
    teile, rest = _segmente(text)
    bericht: List[str] = []

    entfernen: set = set()
    neue_anzahl: Dict[int, Tuple[Decimal, str]] = {}
    unt_korrektur: Dict[int, int] = {}  # Index des UNT -> Anzahl entfernter Segmente

    beleg_nr = ""
    gruppen: Dict[Tuple[str, ...], int] = {}        # Schlüssel -> Index des ersten EHE
    erste_je_tag: Dict[Tuple[str, str], int] = {}  # (Position, Datum) -> erster EHE-Index
    entfernt_in_nachricht = 0

    for i, (segment, _) in enumerate(teile):
        el = _elemente(segment.strip())
        tag = el[0]

        if tag == "UNH":
            entfernt_in_nachricht = 0
            gruppen, erste_je_tag = {}, {}
        elif tag == "INV":
            beleg_nr = el[4] if len(el) > 4 else ""
            gruppen, erste_je_tag = {}, {}
        elif tag == "UNT":
            if entfernt_in_nachricht:
                unt_korrektur[i] = entfernt_in_nachricht
        elif tag == "EHE" and len(el) >= 6:
            anzahl = _zahl(el[3])
            schluessel = tuple(el[:3] + el[4:])
            position, datum = el[2], el[5]

            if anzahl is not None and schluessel in gruppen:
                erster = gruppen[schluessel]
                if erster not in neue_anzahl:
                    vorlage = _elemente(teile[erster][0].strip())[3]
                    neue_anzahl[erster] = (_zahl(vorlage), vorlage)
                summe, vorlage = neue_anzahl[erster]
                neue_anzahl[erster] = (summe + anzahl, vorlage)
                entfernen.add(i)
                entfernt_in_nachricht += 1
                continue

            if (position, datum) in erste_je_tag:
                bericht.append(
                    f"Beleg {beleg_nr or '?'}: Position {position} am {datum} kommt mehrfach vor, "
                    f"unterscheidet sich aber in Preis, Zuzahlung o. Ä. - nicht zusammengefasst."
                )
            else:
                erste_je_tag[(position, datum)] = i
            gruppen[schluessel] = i

    if not entfernen:
        return text, bericht

    zusammengefasst: List[str] = []
    stuecke: List[str] = []
    for i, (segment, leerraum) in enumerate(teile):
        if i in entfernen:
            continue
        if i in neue_anzahl:
            el = _elemente(segment)
            summe, vorlage = neue_anzahl[i]
            alt = el[3]
            el[3] = _formatiere(summe, vorlage)
            segment = "+".join(el)
            zusammengefasst.append(f"Position {el[2]} am {el[5]}: Anzahl {alt} -> {el[3]}")
        elif i in unt_korrektur:
            el = _elemente(segment)
            alt = el[1]
            el[1] = str(int(alt) - unt_korrektur[i]).zfill(len(alt))
            segment = "+".join(el)
        stuecke.append(segment + "'" + leerraum)

    bericht = (
        [f"{len(entfernen)} EHE-Segment(e) entfernt, {len(neue_anzahl)} zusammengefasst:"]
        + [f"  {z}" for z in zusammengefasst]
        + bericht
    )
    return "".join(stuecke) + rest, bericht


def zielpfad(quelle: Path, out_dir: Optional[Path]) -> Path:
    """Das Original wird nie überschrieben: ohne eigenen Ausgabeordner -> Unterordner 'bereinigt'."""
    if out_dir is None or out_dir.resolve() == quelle.parent.resolve():
        out_dir = quelle.parent / UNTERORDNER
    return out_dir / quelle.name


def bereinige_datei(quelle: Path, out_dir: Optional[Path] = None) -> Tuple[Optional[Path], List[str]]:
    """Schreibt die bereinigte Fassung. Rückgabe (Zielpfad oder None, wenn nichts zu tun war; Bericht)."""
    text = read_esol_file_text(quelle)
    neu, bericht = zusammenfassen(text)
    if neu == text:
        return None, bericht

    nicht_speicherbar = pruefe_iso_8859_1(neu)
    if nicht_speicherbar:
        zeile, spalte, zeichen = nicht_speicherbar[0]
        raise ValueError(
            f"Zeile {zeile}, Spalte {spalte}: '{zeichen}' (U+{ord(zeichen):04X}) "
            f"lässt sich nicht in ISO-8859-1 speichern."
        )

    ziel = zielpfad(quelle, out_dir)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(neu.encode("iso-8859-1"))
    return ziel, bericht


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Fasst gleiche EHE-Positionen am gleichen Tag über die Anzahl zusammen."
    )
    parser.add_argument("dateien", nargs="+", help="ESOL-Dateien")
    parser.add_argument("--out-dir", "-o", default=None, help="Ausgabeordner (Standard: <Quellordner>/bereinigt)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir) if args.out_dir else None
    fehler = False
    for name in args.dateien:
        quelle = Path(name)
        if not quelle.is_file():
            print(f"FEHLER: Datei nicht gefunden: {quelle}")
            fehler = True
            continue
        try:
            ziel, bericht = bereinige_datei(quelle, out_dir)
        except Exception as e:
            print(f"FEHLER: {quelle.name}: {e}")
            fehler = True
            continue
        for zeile in bericht:
            print(zeile)
        if ziel is None:
            print(f"{quelle.name}: keine gleichen EHE-Positionen gefunden - nichts geändert.")
        else:
            print(f"Bereinigte Datei geschrieben: {ziel}")
            print("Das Original ist unverändert.")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
