#!/usr/bin/env python3
"""
Import der Kostenträger-Verzeichnisse nach data/kostentraeger.json.

In den ESOL-Dateien stehen an vier Stellen Institutionskennzeichen: im UNB
(Absender/Empfänger) sowie im FKT als IK des Leistungserbringers, des
Kostenträgers und der Krankenkasse. In der Hotline ist eine neunstellige Zahl
ohne Namen wertlos — dieses Skript baut die Nachschlagetabelle dafür.

    python tools/import_kostentraeger.py

Ohne Argumente werden die Dateien in quellen/ genommen. Vier Quellen, in
dieser Rangfolge (die erste, die einen Namen liefert, gewinnt):

  1. quellen/ktr_parsed.json        Kostenträgerdatei nach § 302 SGB V. Die
                                    wichtigste Quelle: sie kennt zusätzlich die
                                    Datenannahmestelle je Kasse — also die
                                    Frage "wohin muss die Datei überhaupt?".
  2. quellen/ktr_heilfuersorge.json Heilfürsorge (Polizei, Bundeswehr, PBeaKK).
  3. quellen/gkvliste.txt           Breites GKV-IK-Verzeichnis (Tab-getrennt).
  4. quellen/bgliste.txt            Unfallversicherungsträger (BG, Unfallkassen,
                                    SVLFG, DVUA-Verbindungsstellen).

Bewusst NICHT übernommen werden Telefon- und Faxnummern aus bgliste.txt: sie
veralten schnell, und eine falsche Nummer, die in der Hotline weitergegeben
wird, ist schlimmer als keine.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Optional

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

STANDARD_QUELLEN = _project_root / "quellen"
STANDARD_ZIEL = _project_root / "data" / "kostentraeger.json"

# Art des Trägers — steuert die Beschriftung in der Anzeige
ART_GKV = "gkv"
ART_UV = "uv"
ART_HEILFUERSORGE = "heilfuersorge"

_ART_TEXT = {
    ART_GKV: "Krankenkasse / Kostenträger",
    ART_UV: "Unfallversicherungsträger",
    ART_HEILFUERSORGE: "Heilfürsorge",
}

# Art der Verknüpfung (VKG) in der Kostenträgerdatei nach § 302 SGB V.
# Nur die Werte, die in den Quelldaten tatsächlich vorkommen und deren
# Bedeutung belegt ist; für alles andere wird nichts geraten.
_VKG_ART = {
    "01": "Kostenträger (Zahlung)",
    "02": "Datenannahmestelle mit Entschlüsselungsbefugnis",
    "03": "Datenannahmestelle ohne Entschlüsselungsbefugnis",
    "09": "Papierannahmestelle",
}


def normalisiere(text: Any) -> str:
    """Randleerzeichen weg, Mehrfach-Leerzeichen zusammenziehen."""
    if text is None:
        return ""
    return " ".join(str(text).replace(" ", " ").split())


def _ist_ik(wert: str) -> bool:
    """Ein IK ist neunstellig numerisch. Alles andere ist ein Kopfzeilenrest."""
    return len(wert) == 9 and wert.isdigit()


def _leer() -> Dict[str, Any]:
    return {
        "name": "",
        "zusatz": "",
        "art": "",
        "plz": "",
        "ort": "",
        "strasse": "",
        "email": "",
        "gueltig_ab": "",
        "gueltig_bis": "",
        "nachfolge_ik": "",
        "annahmestelle": {},
        "quelle": "",
    }


# Quellen, die für die Art des Trägers maßgeblich sind, auch wenn eine
# frühere Quelle den IK schon kannte: gkvliste.txt und die Kostenträgerdatei
# führen auch Unfallversicherungsträger und Heilfürsorgestellen, kennzeichnen
# sie aber nicht als solche. Ohne diese Regel stünde über einer
# Berufsgenossenschaft "Krankenkasse".
_ART_MASSGEBLICH = ("bgliste", "heilfuersorge")


def _uebernehmen(ziel: Dict[str, Any], neu: Dict[str, Any]) -> None:
    """
    Ergänzt fehlende Felder, überschreibt aber nie vorhandene. So gewinnt
    immer die zuerst gelesene (höherwertige) Quelle, ohne dass die späteren
    Verzeichnisse nutzlos werden — sie füllen die Lücken. Einzige Ausnahme ist
    die Art des Trägers, siehe _ART_MASSGEBLICH.
    """
    if neu.get("art") and neu.get("quelle") in _ART_MASSGEBLICH:
        ziel["art"] = neu["art"]

    for schluessel, wert in neu.items():
        if schluessel == "annahmestelle":
            if wert and not ziel.get("annahmestelle"):
                ziel["annahmestelle"] = wert
            continue
        if wert and not ziel.get(schluessel):
            ziel[schluessel] = wert


def lade_ktr_json(pfad: Path, art: str, quelle: str) -> Dict[str, Dict[str, Any]]:
    """
    Liest ktr_parsed.json / ktr_heilfuersorge.json: ein Objekt IK -> Eintrag.

    Die Verknüpfungen VKGDFU (Datenfernübertragung), VKGANS (Papier) und
    VKGZIEL (Zahlung) werden zu einer flachen 'annahmestelle' zusammengefasst.
    """
    with pfad.open("r", encoding="utf-8") as fh:
        daten = json.load(fh)
    if not isinstance(daten, dict):
        raise ValueError(f"{pfad.name}: Wurzelelement ist kein JSON-Objekt")

    ergebnis: Dict[str, Dict[str, Any]] = {}
    for ik, eintrag in daten.items():
        ik = normalisiere(ik)
        if not _ist_ik(ik) or not isinstance(eintrag, dict):
            continue

        ans = eintrag.get("ANS") if isinstance(eintrag.get("ANS"), dict) else {}
        satz = _leer()
        satz.update({
            "name": normalisiere(eintrag.get("Name")),
            "art": art,
            "plz": normalisiere(ans.get("PLZ")),
            "ort": normalisiere(ans.get("Ort")),
            "strasse": normalisiere(ans.get("StrassePostfach")),
            "email": normalisiere(eintrag.get("eMail")),
            "quelle": quelle,
        })
        if normalisiere(eintrag.get("Bundesland")):
            satz["zusatz"] = f"Land {normalisiere(eintrag['Bundesland'])}"

        annahme: Dict[str, Any] = {}
        for feld, name in (("VKGDFU", "dfu"), ("VKGANS", "papier"), ("VKGZIEL", "zahlung")):
            vkg = eintrag.get(feld)
            if not isinstance(vkg, dict):
                continue
            ziel_ik = normalisiere(vkg.get("IK"))
            if not _ist_ik(ziel_ik):
                continue
            vkg_art = normalisiere(vkg.get("Art"))
            annahme[name] = {
                "ik": ziel_ik,
                "art": vkg_art,
                "art_text": _VKG_ART.get(vkg_art, ""),
                "tarifkennzeichen": normalisiere(vkg.get("Tarifkennzeichen")),
            }
        satz["annahmestelle"] = annahme

        if satz["name"]:
            ergebnis[ik] = satz
    return ergebnis


def lade_gkvliste(pfad: Path) -> Dict[str, Dict[str, Any]]:
    """
    Liest gkvliste.txt: Tab-getrennt, Spalten
    Kassen-IK / Kassen Bezeichnung / PLZ / Ort / Straße.
    """
    ergebnis: Dict[str, Dict[str, Any]] = {}
    with pfad.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for zeile in csv.reader(fh, delimiter="\t"):
            if len(zeile) < 2:
                continue
            ik = normalisiere(zeile[0])
            if not _ist_ik(ik):
                continue  # überspringt zugleich die Kopfzeile
            satz = _leer()
            satz.update({
                "name": normalisiere(zeile[1]),
                "art": ART_GKV,
                "plz": normalisiere(zeile[2]) if len(zeile) > 2 else "",
                "ort": normalisiere(zeile[3]) if len(zeile) > 3 else "",
                "strasse": normalisiere(zeile[4]) if len(zeile) > 4 else "",
                "quelle": "gkvliste",
            })
            if satz["name"]:
                ergebnis[ik] = satz
    return ergebnis


def lade_bgliste(pfad: Path) -> Dict[str, Dict[str, Any]]:
    """
    Liest bgliste.txt: Semikolon-getrennt, Spalten
    IK / Nachfolge-IK / Gültig ab / Gültig bis / Name1 / Name2 / Strasse /
    Land / PLZ / Ort / Vorwahl / Tel / Fax / IK-UNIDAV / KIM UNI-DAV.

    Name2 ist die Bezirksverwaltung ("BV Köln", "Hauptverwaltung") und wandert
    nach 'zusatz', damit der Trägername allein in der Kopfzeile stehen kann.
    """
    ergebnis: Dict[str, Dict[str, Any]] = {}
    with pfad.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        for zeile in csv.reader(fh, delimiter=";"):
            if len(zeile) < 5:
                continue
            ik = normalisiere(zeile[0])
            if not _ist_ik(ik):
                continue
            satz = _leer()
            nachfolge = normalisiere(zeile[1])
            satz.update({
                "name": normalisiere(zeile[4]),
                "zusatz": normalisiere(zeile[5]) if len(zeile) > 5 else "",
                "art": ART_UV,
                "strasse": normalisiere(zeile[6]) if len(zeile) > 6 else "",
                "plz": normalisiere(zeile[8]) if len(zeile) > 8 else "",
                "ort": normalisiere(zeile[9]) if len(zeile) > 9 else "",
                "gueltig_ab": normalisiere(zeile[2]),
                "gueltig_bis": normalisiere(zeile[3]),
                "nachfolge_ik": nachfolge if _ist_ik(nachfolge) else "",
                "quelle": "bgliste",
            })
            if len(zeile) > 14 and "@" in normalisiere(zeile[14]):
                satz["email"] = normalisiere(zeile[14])
            if satz["name"]:
                ergebnis[ik] = satz
    return ergebnis


def baue_tabelle(quellen: Path) -> Dict[str, Any]:
    """
    Führt alle vorhandenen Verzeichnisse zusammen. Fehlt eine Datei, wird sie
    übersprungen und im Ergebnis vermerkt — ein unvollständiger Satz Quellen
    soll den Import nicht verhindern.
    """
    reihenfolge = [
        ("ktr_parsed.json", lambda p: lade_ktr_json(p, ART_GKV, "ktr")),
        ("ktr_heilfuersorge.json", lambda p: lade_ktr_json(p, ART_HEILFUERSORGE, "heilfuersorge")),
        # bgliste vor gkvliste: die UV-Träger stehen in beiden Verzeichnissen,
        # aber nur die bgliste kennt Bezirksverwaltung und Gültigkeitszeitraum.
        ("bgliste.txt", lade_bgliste),
        ("gkvliste.txt", lade_gkvliste),
    ]

    traeger: Dict[str, Dict[str, Any]] = {}
    gelesen: Dict[str, int] = {}
    fehlend: list[str] = []

    for dateiname, leser in reihenfolge:
        pfad = quellen / dateiname
        if not pfad.is_file():
            fehlend.append(dateiname)
            continue
        teil = leser(pfad)
        gelesen[dateiname] = len(teil)
        for ik, satz in teil.items():
            if ik in traeger:
                _uebernehmen(traeger[ik], satz)
            else:
                traeger[ik] = satz

    if not traeger:
        raise ValueError(
            "Keine der Kostenträger-Quellen gefunden. Erwartet in "
            f"{quellen}: " + ", ".join(name for name, _ in reihenfolge)
        )

    arten = Counter(satz.get("art", "") for satz in traeger.values())
    mit_annahmestelle = sum(1 for s in traeger.values() if s.get("annahmestelle"))

    return {
        "_hinweis": [
            "Automatisch erzeugt aus den Kostenträger- und IK-Verzeichnissen.",
            "NICHT von Hand bearbeiten — beim nächsten Import wird die Datei überschrieben.",
            "Eigene Korrekturen gehören nach data/codelisten.json unter 'kostentraeger';",
            "die haben Vorrang.",
            "",
            "Erzeugt mit: python tools/import_kostentraeger.py",
            "",
            "Telefon- und Faxnummern werden bewusst nicht übernommen: sie veralten",
            "schnell, und eine falsch weitergegebene Nummer ist schlimmer als keine.",
        ],
        "_quelle": {
            "gelesen": gelesen,
            "fehlende_dateien": fehlend,
            "anzahl_ik": len(traeger),
            "arten": {_ART_TEXT.get(a, a or "ohne Art"): n for a, n in sorted(arten.items())},
            "mit_annahmestelle": mit_annahmestelle,
        },
        "traeger": dict(sorted(traeger.items())),
    }


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Erzeugt data/kostentraeger.json aus den IK-Verzeichnissen in quellen/.",
    )
    parser.add_argument(
        "--quellen", "-q", default=str(STANDARD_QUELLEN),
        help=f"Verzeichnis mit den Quelldateien (Standard: {STANDARD_QUELLEN.name}/)",
    )
    parser.add_argument("--out", "-o", default=str(STANDARD_ZIEL), help="Zieldatei")
    args = parser.parse_args()

    try:
        daten = baue_tabelle(Path(args.quellen))
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        sys.exit(1)

    ziel = Path(args.out)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    quelle = daten["_quelle"]
    print("Kostenträger-Verzeichnisse eingelesen:")
    for name, anzahl in quelle["gelesen"].items():
        print(f"  {anzahl:6}  {name}")
    if quelle["fehlende_dateien"]:
        print(f"  nicht gefunden: {', '.join(quelle['fehlende_dateien'])}")
    print(f"\n  {quelle['anzahl_ik']} Institutionskennzeichen insgesamt")
    for art, anzahl in quelle["arten"].items():
        print(f"    {anzahl:6}  {art}")
    print(f"    {quelle['mit_annahmestelle']:6}  davon mit Datenannahmestelle")
    print(f"\nGeschrieben: {ziel}")


if __name__ == "__main__":
    main()
