#!/usr/bin/env python3
"""
Import der GKV-Heilmittelpreisstammdatei (HMP) nach data/heilmittelpreise.json.

Der GKV-Spitzenverband veröffentlicht die Heilmittelpreise nach § 125 und
§ 125a SGB V als XML (HMPRoot/HMP). Dieses Skript zieht daraus die
Bezeichnungen der Abrechnungspositionsnummern, damit im Verordnungsblatt und
im Rezept-Baum Klartext statt nur der Nummer steht.

    python tools/import_hmp.py "HMP Stand 01.07.2026.xml"
    python tools/import_hmp.py neu.xml --out data/heilmittelpreise.json

BEWUSST NICHT ÜBERNOMMEN werden die Höchstpreise. Der Haftungsausschluss der
Stammdatei sagt ausdrücklich, sie sei "nicht zu Abrechnungszwecken bestimmt";
maßgeblich sind die Vergütungsvereinbarungen nach § 125/§ 125a. In einem
Support-Werkzeug, das Abrechnungsdateien prüft, würde ein Höchstpreis neben
einem abgerechneten Betrag zwangsläufig als Soll-Ist-Vergleich gelesen — und
genau das schließt die Quelle aus.

Zur maskierten ersten Stelle: Positionen nach § 125 (Regelversorgung) führt die
Stammdatei mit 'X' als erster Stelle (z. B. X4103). In der Abrechnung steht dort
die Stelle des Heilmittelbereichs (54103 für Ergotherapie). Die Auflösung
passiert beim Nachschlagen in codelisten.py, nicht hier — so bleibt diese Datei
eine unverfälschte Abbildung der Quelle.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Dict

# Projektwurzel in sys.path, damit das Skript auch direkt aufrufbar ist
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

STANDARD_ZIEL = _project_root / "data" / "heilmittelpreise.json"

# Felder, die je HMP-Eintrag erwartet werden
_PFLICHTFELDER = ("HMP4", "Heilmittelbereich", "Bezeichnung")

# Zeichen, die die Quelldatei mitbringt und die in der Anzeige stören.
#   U+00A0  geschütztes Leerzeichen — steht in 25 Bezeichnungen zwischen '§'
#           und der Zahl. Unsichtbar, aber die Volltextsuche im Rezept-Baum
#           findet damit "§ 125a" nicht mehr.
#   U+2013  Gedankenstrich — lässt sich nicht in ISO-8859-15 speichern und
#           würde beim Export von Berichten stören.
_ZEICHEN_ERSATZ = {
    "\u00a0": " ",
    "\u2009": " ",
    "\u202f": " ",
    "\u2013": "-",
    "\u2014": "-",
}


def normalisiere(text: str) -> str:
    """
    Räumt die Textfelder der Quelldatei auf: Sonderzeichen ersetzen,
    Mehrfach-Leerzeichen zusammenziehen, Rand trimmen. Der fachliche Inhalt
    bleibt unverändert — es geht nur um Zeichen, die in der Anzeige und in der
    Suche Ärger machen.
    """
    if not text:
        return ""
    for zeichen, ersatz in _ZEICHEN_ERSATZ.items():
        text = text.replace(zeichen, ersatz)
    return " ".join(text.split())


def parse_hmp(xml_pfad: Path) -> Dict[str, Any]:
    """
    Liest eine HMP-XML und liefert die Struktur für heilmittelpreise.json.

    Wirft ValueError, wenn die Datei nicht wie eine HMP-Stammdatei aussieht —
    besser ein klarer Abbruch als eine stillschweigend halbleere Zieldatei.
    """
    try:
        baum = ET.parse(xml_pfad)
    except ET.ParseError as e:
        raise ValueError(f"{xml_pfad.name} ist keine gültige XML-Datei: {e}") from e

    root = baum.getroot()
    if root.tag != "HMPRoot":
        raise ValueError(
            f"Unerwartetes Wurzelelement <{root.tag}> — erwartet <HMPRoot>. "
            f"Ist das wirklich die Heilmittelpreisstammdatei des GKV-Spitzenverbands?"
        )

    eintraege = root.findall("HMP")
    if not eintraege:
        raise ValueError("Die Datei enthält keine <HMP>-Einträge.")

    positionen: Dict[str, Dict[str, str]] = {}
    bereiche: Counter = Counter()
    staende: Counter = Counter()
    uebersprungen = 0
    doppelt: list[str] = []

    for eintrag in eintraege:
        werte = {feld: normalisiere(eintrag.findtext(feld) or "") for feld in _PFLICHTFELDER}
        code = werte["HMP4"]
        if not code or not werte["Bezeichnung"]:
            uebersprungen += 1
            continue

        gueltig_ab = (eintrag.findtext("Gueltig_ab") or "").strip()
        bemerkungen = normalisiere(eintrag.findtext("Bemerkungen") or "")

        # Rechtsgrundlage aus den Bemerkungen ableiten — sie unterscheidet
        # Regelversorgung von Blankoversorgung und erklärt, warum es zu einer
        # Leistung zwei Positionsnummern gibt.
        if "125a" in bemerkungen:
            grundlage = "125a"
        elif "125" in bemerkungen:
            grundlage = "125"
        else:
            grundlage = ""

        if code in positionen:
            doppelt.append(code)

        positionen[code] = {
            "bezeichnung": werte["Bezeichnung"],
            "bereich": werte["Heilmittelbereich"],
            "grundlage": grundlage,
            "gueltig_ab": gueltig_ab,
        }
        bereiche[werte["Heilmittelbereich"]] += 1
        if gueltig_ab:
            staende[gueltig_ab] += 1

    return {
        "_hinweis": [
            "Automatisch erzeugt aus der Heilmittelpreisstammdatei des GKV-Spitzenverbands.",
            "NICHT von Hand bearbeiten — beim nächsten Import wird die Datei überschrieben.",
            "Eigene Bezeichnungen gehören nach data/codelisten.json; die haben Vorrang.",
            "",
            "Erzeugt mit: python tools/import_hmp.py <HMP-XML>",
            "",
            "Höchstpreise sind bewusst NICHT enthalten: die Quelle ist laut ihrem",
            "Haftungsausschluss nicht zu Abrechnungszwecken bestimmt.",
            "",
            "Codes mit 'X' an erster Stelle sind Positionen nach § 125 (Regelversorgung);",
            "in der Abrechnung steht dort die Stelle des Heilmittelbereichs (X4103 -> 54103).",
            "Die Auflösung passiert beim Nachschlagen in codelisten.py.",
        ],
        "_quelle": {
            "datei": xml_pfad.name,
            "hmp_version": root.attrib.get("HMP_Version", ""),
            "schema_version": root.attrib.get("Schema_Version", ""),
            "hmp_gueltig_ab": root.attrib.get("HMP_Gueltig_ab", ""),
            "anzahl_positionen": len(positionen),
            "heilmittelbereiche": dict(sorted(bereiche.items())),
            "gueltigkeitsstaende": dict(sorted(staende.items())),
        },
        "positionen": dict(sorted(positionen.items())),
        "_uebersprungen": uebersprungen,
        "_doppelte_codes": sorted(set(doppelt)),
    }


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Erzeugt data/heilmittelpreise.json aus der GKV-Heilmittelpreisstammdatei (XML).",
    )
    parser.add_argument("xml", help="Pfad zur HMP-XML des GKV-Spitzenverbands")
    parser.add_argument(
        "--out", "-o", default=str(STANDARD_ZIEL),
        help=f"Zieldatei (Standard: {STANDARD_ZIEL.relative_to(_project_root)})",
    )
    args = parser.parse_args()

    xml_pfad = Path(args.xml)
    if not xml_pfad.is_file():
        print(f"Fehler: Datei nicht gefunden: {xml_pfad}", file=sys.stderr)
        sys.exit(2)

    try:
        daten = parse_hmp(xml_pfad)
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)

    ziel = Path(args.out)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(
        json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    quelle = daten["_quelle"]
    print(f"Heilmittelpreisstammdatei eingelesen: {xml_pfad.name}")
    print(f"  HMP-Version {quelle['hmp_version']} / Schema {quelle['schema_version']}")
    print(f"  {quelle['anzahl_positionen']} Positionsnummern")
    for bereich, anzahl in quelle["heilmittelbereiche"].items():
        print(f"    {anzahl:4}  {bereich}")
    print(f"  Gültigkeitsstände: {', '.join(quelle['gueltigkeitsstaende'])}")
    if daten["_uebersprungen"]:
        print(f"  {daten['_uebersprungen']} Einträge ohne Code oder Bezeichnung übersprungen")
    if daten["_doppelte_codes"]:
        print(f"  Achtung: doppelte Codes: {', '.join(daten['_doppelte_codes'])}")
    print(f"\nGeschrieben: {ziel}")
    print("Im Programm über 'Codelisten neu laden' im Verordnungsblatt aktivieren.")


if __name__ == "__main__":
    main()
