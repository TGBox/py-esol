#!/usr/bin/env python3
"""
Import der Positionsverzeichnisse nach data/heilmittelkatalog.json.

Diese Datei ist die dritte und letzte Fallback-Ebene für den Klartext zu einer
Abrechnungspositionsnummer. Die Reihenfolge beim Nachschlagen ist:

  1. data/codelisten.json        eigene Pflege, hat immer Vorrang
  2. data/heilmittelpreise.json  GKV-Heilmittelpreisstammdatei (§ 125 / § 125a)
  3. data/heilmittelkatalog.json diese Datei — deckt ab, was in der
                                 GKV-Stammdatei nicht steht: Kurort- und
                                 Bäderleistungen, BG/UV-Positionen,
                                 Heilpraktiker-Gebührenverzeichnis

    python tools/import_heilmittelkatalog.py

Ohne Argumente werden die Dateien in quellen/ genommen:

  codes.csv            X-Codes des Heilmittelkatalogs mit Leistungstext (~680)
  heilmittelpreise.csv X-Codes mit Bezeichnung und Kapitel 1..5
  codesgroups.csv      zweistellige Leistungsgruppen ("12 = Manuelle Therapie")
  bgleistungen.csv     Positionen der UV-Träger (Physio/Ergo)
  bgleistungen_alt.csv älterer Stand derselben Liste, füllt Lücken
  heilmittelleistungen_heilpraktiker.csv  Gebührenverzeichnis für Heilpraktiker

PREISE WERDEN BEWUSST NICHT ÜBERNOMMEN. Genauso wie bei der
GKV-Heilmittelpreisstammdatei gilt: in einem Werkzeug, das Abrechnungsdateien
prüft, würde ein Listenpreis neben einem abgerechneten Betrag zwangsläufig als
Soll-Ist-Vergleich gelesen. Maßgeblich sind die Vergütungsvereinbarungen, nicht
diese Listen. Die Preisspalten werden deshalb eingelesen und verworfen.

heilmittelleistungen_physio.csv wird NICHT eingelesen: dort ist die
'code'-Spalte identisch mit der Bezeichnung ("KG;KG;24.08;Physiotherapie"), es
gibt also keine Positionsnummer, die sich nachschlagen ließe.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

STANDARD_QUELLEN = _project_root / "quellen"
STANDARD_ZIEL = _project_root / "data" / "heilmittelkatalog.json"

# Kapitel 1..5 aus heilmittelpreise.csv. Dieselbe Gliederung wie im
# Heilmittelkatalog der KBV (dort römisch I..V).
_KAPITEL_BEREICH = {
    "1": "Maßnahmen der Physiotherapie",
    "2": "Maßnahmen der Podologischen Therapie",
    "3": "Maßnahmen der Stimm-, Sprech-, Sprach- und Schlucktherapie",
    "4": "Maßnahmen der Ergotherapie",
    "5": "Maßnahmen der Ernährungstherapie",
}


def normalisiere(text: Any) -> str:
    """Sonderleerzeichen glätten, Gedankenstriche ersetzen, Rand trimmen."""
    if text is None:
        return ""
    text = str(text)
    for zeichen, ersatz in ((" ", " "), (" ", " "), (" ", " "),
                            ("–", "-"), ("—", "-")):
        text = text.replace(zeichen, ersatz)
    return " ".join(text.split())


def _lese_csv(pfad: Path) -> Iterable[Dict[str, str]]:
    """
    Liest eine semikolongetrennte CSV mit Kopfzeile. Die Quelldateien sind
    teils UTF-8, teils ISO-8859-15 — deshalb wird beides versucht.
    """
    for kodierung in ("utf-8-sig", "utf-8", "iso-8859-15"):
        try:
            with pfad.open("r", encoding=kodierung, newline="") as fh:
                zeilen = list(csv.DictReader(fh, delimiter=";"))
            return zeilen
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{pfad.name}: Zeichenkodierung nicht erkannt")


def _setze(ziel: Dict[str, Dict[str, str]], code: str, eintrag: Dict[str, str],
           doppelt: List[str]) -> None:
    """
    Legt einen Eintrag ab. Ein bereits vorhandener Klartext wird nicht
    überschrieben — die zuerst gelesene Quelle gewinnt —, aber leere Felder
    werden ergänzt.
    """
    code = normalisiere(code)
    if not code or not eintrag.get("bezeichnung"):
        return
    vorhanden = ziel.get(code)
    if vorhanden is None:
        ziel[code] = {k: v for k, v in eintrag.items() if v}
        return
    if vorhanden.get("bezeichnung") != eintrag["bezeichnung"]:
        doppelt.append(code)
    for schluessel, wert in eintrag.items():
        if wert and not vorhanden.get(schluessel):
            vorhanden[schluessel] = wert


def lade_heilmittelpreise_csv(pfad: Path, ziel: Dict[str, Dict[str, str]],
                              doppelt: List[str]) -> int:
    """
    kapitel;hmcode;preis;bezeichnung

    Wird vor codes.csv gelesen: die Bezeichnungen sind ausformuliert
    ("Krankengymnastik: Einzelbehandlung"), während codes.csv oft nur den
    Zusatz zur Leistungsgruppe nennt ("bei motorischen Störungen"). Die
    Preisspalte wird verworfen.
    """
    anzahl = 0
    for zeile in _lese_csv(pfad):
        code = normalisiere(zeile.get("hmcode"))
        bezeichnung = normalisiere(zeile.get("bezeichnung"))
        if not code or not bezeichnung:
            continue
        kapitel = normalisiere(zeile.get("kapitel"))
        _setze(ziel, code, {
            "bezeichnung": bezeichnung,
            "bereich": _KAPITEL_BEREICH.get(kapitel, ""),
            "kapitel": kapitel,
            "quelle": "heilmittelpreise",
        }, doppelt)
        anzahl += 1
    return anzahl


def lade_codes_csv(pfad: Path, ziel: Dict[str, Dict[str, str]],
                   doppelt: List[str]) -> int:
    """
    code;hmcode;leistung

    Der Leistungstext ist häufig nur der Zusatz zur Leistungsgruppe. Die
    Gruppe steckt in den Stellen 2-3 des X-Codes (X4102 -> Gruppe 41) und wird
    beim Nachschlagen aus 'leistungsgruppen' davorgesetzt.
    """
    anzahl = 0
    for zeile in _lese_csv(pfad):
        code = normalisiere(zeile.get("hmcode") or zeile.get("code"))
        bezeichnung = normalisiere(zeile.get("leistung"))
        if not code or not bezeichnung or bezeichnung.upper() == "UNBESETZT":
            continue
        _setze(ziel, code, {
            "bezeichnung": bezeichnung,
            "gruppe": code[1:3] if len(code) >= 3 else "",
            "quelle": "heilmittelkatalog",
        }, doppelt)
        anzahl += 1
    return anzahl


def lade_bgleistungen(pfad: Path, ziel: Dict[str, Dict[str, str]],
                      doppelt: List[str]) -> int:
    """
    bezeichnung;code;einzelpreis;gruppe;hmcode

    Eigener Nummernkreis der Unfallversicherungsträger (8401, 9401, 11.1.).
    'gruppe' ist hier bereits ein Klartext ("BG-Leistung Physio"), 'hmcode'
    eine Gruppennummer aus einer anderen Zählung und deshalb ungenutzt.
    Die Preisspalte wird verworfen.
    """
    anzahl = 0
    for zeile in _lese_csv(pfad):
        code = normalisiere(zeile.get("code"))
        bezeichnung = normalisiere(zeile.get("bezeichnung"))
        if not code or not bezeichnung:
            continue
        _setze(ziel, code, {
            "bezeichnung": bezeichnung,
            "bereich": normalisiere(zeile.get("gruppe")),
            "quelle": "bg",
        }, doppelt)
        anzahl += 1
    return anzahl


def lade_heilpraktiker(pfad: Path, ziel: Dict[str, Dict[str, str]],
                       doppelt: List[str]) -> int:
    """
    code;bezeichnung;einzelpreis;gruppe

    Gebührenverzeichnis für Heilpraktiker. Die Preisspalte wird verworfen.
    """
    anzahl = 0
    for zeile in _lese_csv(pfad):
        code = normalisiere(zeile.get("code"))
        bezeichnung = normalisiere(zeile.get("bezeichnung"))
        if not code or not bezeichnung:
            continue
        _setze(ziel, code, {
            "bezeichnung": bezeichnung,
            "bereich": normalisiere(zeile.get("gruppe")),
            "quelle": "heilpraktiker",
        }, doppelt)
        anzahl += 1
    return anzahl


def lade_leistungsgruppen(pfad: Path) -> Dict[str, str]:
    """
    id;group

    Zweistellige Leistungsgruppen des Heilmittelkatalogs. Die Quelldatei hat
    Zeilenumbrüche mitten in den Bezeichnungen ("Nagelspangenbehand lung") —
    die werden hier nicht repariert, weil sich nicht sicher entscheiden lässt,
    wo ein Leerzeichen hingehört und wo nicht.

    Die letzte Zeile der Quelldatei ist "99;44" — ein offensichtlicher
    Datenfehler (die 99 ist schon mit "Hausbesuch/Wegegeld" belegt). Rein
    numerische Bezeichnungen werden deshalb verworfen.
    """
    gruppen: Dict[str, str] = {}
    for zeile in _lese_csv(pfad):
        code = normalisiere(zeile.get("id"))
        bezeichnung = normalisiere(zeile.get("group"))
        if not code or not bezeichnung or bezeichnung.isdigit():
            continue
        gruppen.setdefault(code, bezeichnung)
    return gruppen


def baue_katalog(quellen: Path) -> Dict[str, Any]:
    positionen: Dict[str, Dict[str, str]] = {}
    doppelt: List[str] = []
    gelesen: Dict[str, int] = {}
    fehlend: List[str] = []
    leistungsgruppen: Dict[str, str] = {}

    reihenfolge = [
        ("heilmittelpreise.csv", lade_heilmittelpreise_csv),
        ("codes.csv", lade_codes_csv),
        ("bgleistungen.csv", lade_bgleistungen),
        ("bgleistungen_alt.csv", lade_bgleistungen),
        ("heilmittelleistungen_heilpraktiker.csv", lade_heilpraktiker),
    ]

    for dateiname, leser in reihenfolge:
        pfad = quellen / dateiname
        if not pfad.is_file():
            fehlend.append(dateiname)
            continue
        gelesen[dateiname] = leser(pfad, positionen, doppelt)

    gruppen_pfad = quellen / "codesgroups.csv"
    if gruppen_pfad.is_file():
        leistungsgruppen = lade_leistungsgruppen(gruppen_pfad)
        gelesen["codesgroups.csv"] = len(leistungsgruppen)
    else:
        fehlend.append("codesgroups.csv")

    if not positionen:
        raise ValueError(
            f"Keine Positionsverzeichnisse in {quellen} gefunden. Erwartet: "
            + ", ".join(name for name, _ in reihenfolge)
        )

    quellen_zaehler = Counter(p.get("quelle", "") for p in positionen.values())

    return {
        "_hinweis": [
            "Automatisch erzeugt aus den Positionsverzeichnissen in quellen/.",
            "NICHT von Hand bearbeiten — beim nächsten Import wird die Datei überschrieben.",
            "Eigene Bezeichnungen gehören nach data/codelisten.json unter",
            "'positionsnummern'; die haben Vorrang.",
            "",
            "Erzeugt mit: python tools/import_heilmittelkatalog.py",
            "",
            "PREISE SIND BEWUSST NICHT ENTHALTEN. Maßgeblich für die Abrechnung sind",
            "die Vergütungsvereinbarungen, nicht diese Listen; ein Listenpreis neben",
            "einem abgerechneten Betrag würde als Soll-Ist-Vergleich gelesen.",
            "",
            "Dies ist die dritte Fallback-Ebene hinter codelisten.json und der",
            "GKV-Heilmittelpreisstammdatei. Sie deckt vor allem ab, was dort fehlt:",
            "Kurort- und Bäderleistungen (X6xxx/X7xxx), BG/UV-Positionen und das",
            "Gebührenverzeichnis für Heilpraktiker.",
            "",
            "'leistungsgruppen' schlüsselt die 2. und 3. Stelle eines X-Codes auf",
            "(X4102 -> Gruppe 41). Die Bezeichnungen stammen unverändert aus der",
            "Quelldatei, in der einige Wörter durch Zeilenumbrüche getrennt sind.",
        ],
        "_quelle": {
            "gelesen": gelesen,
            "fehlende_dateien": fehlend,
            "anzahl_positionen": len(positionen),
            "nach_quelle": dict(sorted(quellen_zaehler.items())),
            "anzahl_leistungsgruppen": len(leistungsgruppen),
        },
        "positionen": dict(sorted(positionen.items())),
        "leistungsgruppen": dict(sorted(leistungsgruppen.items())),
        "_abweichende_bezeichnungen": sorted(set(doppelt)),
    }


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Erzeugt data/heilmittelkatalog.json aus den Positionsverzeichnissen.",
    )
    parser.add_argument("--quellen", "-q", default=str(STANDARD_QUELLEN),
                        help=f"Verzeichnis mit den Quelldateien (Standard: {STANDARD_QUELLEN.name}/)")
    parser.add_argument("--out", "-o", default=str(STANDARD_ZIEL), help="Zieldatei")
    args = parser.parse_args()

    try:
        daten = baue_katalog(Path(args.quellen))
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)

    ziel = Path(args.out)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    q = daten["_quelle"]
    print("Positionsverzeichnisse eingelesen:")
    for name, anzahl in q["gelesen"].items():
        print(f"  {anzahl:6}  {name}")
    if q["fehlende_dateien"]:
        print(f"  nicht gefunden: {', '.join(q['fehlende_dateien'])}")
    print(f"\n  {q['anzahl_positionen']} Positionsnummern insgesamt")
    for quelle, anzahl in q["nach_quelle"].items():
        print(f"    {anzahl:6}  {quelle}")
    print(f"  {q['anzahl_leistungsgruppen']} Leistungsgruppen")
    if daten["_abweichende_bezeichnungen"]:
        codes = daten["_abweichende_bezeichnungen"]
        print(f"\n  {len(codes)} Codes mit abweichender Bezeichnung zwischen den Quellen")
        print(f"    (erste gelesene gewinnt): {', '.join(codes[:12])}"
              + (" ..." if len(codes) > 12 else ""))
    print(f"\nGeschrieben: {ziel}")


if __name__ == "__main__":
    main()
