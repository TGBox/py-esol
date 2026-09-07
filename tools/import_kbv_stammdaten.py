#!/usr/bin/env python3
"""
Import der KBV-Heilmittelstammdateien nach data/.

Zwei Dateien, zwei Zieldateien:

  sdhm  (Heilmittelstammdatei)     -> data/diagnosegruppen.json
        Die 44 Diagnosegruppen, gegliedert nach den fünf Kapiteln des
        Heilmittelkatalogs. Das ist die maßgebliche Quelle für den Klartext
        zum 5. ZHE-Feld.

  sdhma (Stammdatei Heilmittelanlagen) -> data/verordnungsbedarf.json
        ICD-10-Codes mit Langfristigem Heilmittelbedarf (Anlage 2) bzw.
        Besonderem Verordnungsbedarf (Anlage 3), samt zulässigen
        Diagnosegruppen, Altersgrenzen und KV-Geltungsbereich. Damit lässt
        sich am DIA-Segment erklären, warum eine Verordnung
        Verordnungsbesonderheiten trägt.

    python tools/import_kbv_stammdaten.py

Ohne Argumente werden die neuesten sdhm*/sdhma*-Dateien in quellen/ genommen.

Zur Zeichenkodierung: die Dateien deklarieren im XML-Prolog ISO-8859-15,
enthalten tatsächlich aber UTF-8-Bytes. Der Parser liest deshalb "MaÃŸnahmen"
statt "Maßnahmen". repariere_kodierung() dreht das zurück — nur dann, wenn das
Ergebnis sauber dekodierbar ist, damit korrekt kodierte Dateien unangetastet
bleiben.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

STANDARD_QUELLEN = _project_root / "quellen"
ZIEL_DIAGNOSEGRUPPEN = _project_root / "data" / "diagnosegruppen.json"
ZIEL_VERORDNUNGSBEDARF = _project_root / "data" / "verordnungsbedarf.json"

# Anlagen der Heilmittel-Richtlinie, wie die Stammdatei sie schlüsselt
_ANLAGE_TEXT = {
    "LHM": "Langfristiger Heilmittelbedarf (Anlage 2)",
    "BVB": "Besonderer Verordnungsbedarf (Anlage 3)",
}


def repariere_kodierung(text: str) -> str:
    """
    Dreht doppelt kodierte Umlaute zurück ("MaÃŸnahmen" -> "Maßnahmen").

    Die KBV-Dateien deklarieren ISO-8859-15, liefern aber UTF-8. Der Rückweg
    ist: die falsch dekodierten Zeichen wieder zu Bytes machen und als UTF-8
    lesen. Schlägt das fehl, war die Datei richtig kodiert — dann bleibt der
    Text unverändert.
    """
    if not text or not any(c in text for c in "ÂÃ"):
        return text
    for kodierung in ("iso-8859-15", "latin-1"):
        try:
            return text.encode(kodierung).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return text


def normalisiere(text: Any) -> str:
    """Kodierung reparieren, Sonderleerzeichen glätten, Rand trimmen."""
    if text is None:
        return ""
    text = repariere_kodierung(str(text))
    for zeichen, ersatz in ((" ", " "), (" ", " "), (" ", " "),
                            ("–", "-"), ("—", "-")):
        text = text.replace(zeichen, ersatz)
    return " ".join(text.split())


def _lokal(tag: str) -> str:
    """'{urn:ehd/001}kapitel' -> 'kapitel' — die Dateien nutzen zwei Namensräume."""
    return tag.split("}")[-1]


def _finde_alle(element: ET.Element, name: str) -> List[ET.Element]:
    """Sucht namensraum-unabhängig im gesamten Teilbaum."""
    return [e for e in element.iter() if _lokal(e.tag) == name]


def _kopf(root: ET.Element) -> Dict[str, str]:
    """Version, Gültigkeitszeitraum und Erstellungsdatum aus dem ehd-Header."""
    info: Dict[str, str] = {}
    for name, schluessel in (("version", "version"),
                             ("service_tmr", "gueltig"),
                             ("origination_dttm", "erstellt"),
                             ("interface.nm", "schnittstelle")):
        treffer = _finde_alle(root, name)
        if treffer:
            info[schluessel] = normalisiere(treffer[0].get("V", ""))
    return info


# ---------------------------------------------------------------------------
# sdhm — Diagnosegruppen
# ---------------------------------------------------------------------------

def parse_sdhm(xml_pfad: Path) -> Dict[str, Any]:
    """
    Liest die Heilmittelstammdatei und liefert die Struktur für
    data/diagnosegruppen.json.
    """
    try:
        root = ET.parse(xml_pfad).getroot()
    except ET.ParseError as e:
        raise ValueError(f"{xml_pfad.name} ist keine gültige XML-Datei: {e}") from e

    kapitel_elemente = _finde_alle(root, "kapitel")
    if not kapitel_elemente:
        raise ValueError(
            f"{xml_pfad.name} enthält keine <kapitel>-Elemente. "
            "Ist das wirklich die KBV-Heilmittelstammdatei (SDHM)?"
        )

    gruppen: Dict[str, Dict[str, str]] = {}
    kapitel_liste: List[Dict[str, Any]] = []

    for nummer, kap in enumerate(kapitel_elemente, start=1):
        kapitel_name = normalisiere(kap.get("V") or kap.get("DN") or "")
        # Der Kapitelname beginnt mit der römischen Zahl ("I. Maßnahmen der
        # Physiotherapie"). Die trennen wir ab, damit der Bereichsname allein
        # in der Anzeige stehen kann.
        roemisch, _, rest = kapitel_name.partition(". ")
        bereich = normalisiere(rest) or kapitel_name

        codes: List[str] = []
        for dg in _finde_alle(kap, "diagnosegruppe"):
            code = normalisiere(dg.get("V"))
            bezeichnung = normalisiere(dg.get("DN"))
            if not code or not bezeichnung:
                continue
            if code not in gruppen:
                gruppen[code] = {
                    "bezeichnung": bezeichnung,
                    "bereich": bereich,
                    "kapitel": roemisch if roemisch != kapitel_name else "",
                    "kapitel_nummer": str(nummer),
                }
                codes.append(code)

        kapitel_liste.append({
            "nummer": str(nummer),
            "kapitel": roemisch if roemisch != kapitel_name else "",
            "bereich": bereich,
            "diagnosegruppen": codes,
        })

    return {
        "_hinweis": [
            "Automatisch erzeugt aus der KBV-Heilmittelstammdatei (SDHM).",
            "NICHT von Hand bearbeiten — beim nächsten Import wird die Datei überschrieben.",
            "Eigene Bezeichnungen gehören nach data/codelisten.json unter",
            "'diagnosegruppe'; die haben Vorrang.",
            "",
            "Erzeugt mit: python tools/import_kbv_stammdaten.py",
            "",
            "'kapitel_nummer' ist die laufende Nummer des Kapitels im",
            "Heilmittelkatalog (I..V -> 1..5). Sie ist NICHT ohne Weiteres der",
            "Schlüssel des 16. ZHE-Feldes: in echten Abrechnungsdateien steht dort",
            "bei einer Ergotherapie-Verordnung (Kapitel IV) eine 1. Der",
            "Zusammenhang ist ungeklärt und wird deshalb nirgends verwendet.",
        ],
        "_quelle": {
            "datei": xml_pfad.name,
            **_kopf(root),
            "anzahl_diagnosegruppen": len(gruppen),
            "anzahl_kapitel": len(kapitel_liste),
        },
        "kapitel": kapitel_liste,
        "diagnosegruppen": dict(sorted(gruppen.items())),
    }


# ---------------------------------------------------------------------------
# sdhma — Verordnungsbedarf je ICD-Code
# ---------------------------------------------------------------------------

def _altersgrenze(element: ET.Element) -> str:
    """'<untere_altersgrenze V="18" U="a"/>' -> '18 Jahre'."""
    wert = normalisiere(element.get("V"))
    if not wert:
        return ""
    einheit = normalisiere(element.get("U"))
    text = {"a": "Jahre", "mo": "Monate", "d": "Tage", "wk": "Wochen"}.get(einheit, einheit)
    return f"{wert} {text}".strip()


def parse_sdhma(xml_pfad: Path) -> Dict[str, Any]:
    """
    Liest die Stammdatei Heilmittelanlagen und liefert die Struktur für
    data/verordnungsbedarf.json: ICD-Code -> Liste von Einträgen.

    Ein ICD-Code kann mehrfach vorkommen (verschiedene Anlagen, verschiedene
    KV-Bereiche), deshalb ist der Wert immer eine Liste.
    """
    try:
        root = ET.parse(xml_pfad).getroot()
    except ET.ParseError as e:
        raise ValueError(f"{xml_pfad.name} ist keine gültige XML-Datei: {e}") from e

    bedarfe = _finde_alle(root, "verordnungsbedarf")
    if not bedarfe:
        raise ValueError(
            f"{xml_pfad.name} enthält keine <verordnungsbedarf>-Elemente. "
            "Ist das wirklich die KBV-Stammdatei Heilmittelanlagen (SDHMA)?"
        )

    nach_icd: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    anlagen: Counter = Counter()
    bereiche: Counter = Counter()
    ohne_icd = 0

    for bedarf in bedarfe:
        icds = [normalisiere(e.get("V")) for e in _finde_alle(bedarf, "icd_code")]
        icds = [i for i in icds if i]
        if not icds:
            ohne_icd += 1
            continue

        kv = sorted({normalisiere(e.get("V")) for e in _finde_alle(bedarf, "geltungsbereich_kv")} - {""})

        for hm in _finde_alle(bedarf, "heilmittel"):
            anlage_el = _finde_alle(hm, "anlage_heilmittelvereinbarung")
            anlage = normalisiere(anlage_el[0].get("V")) if anlage_el else ""
            hinweis_el = _finde_alle(hm, "hinweistext")
            hinweis = normalisiere(hinweis_el[0].get("V")) if hinweis_el else ""

            kapitel: List[Dict[str, Any]] = []
            for kap in _finde_alle(hm, "kapitel"):
                bereich = normalisiere(kap.get("DN"))
                gruppen = sorted({
                    normalisiere(dg.get("V"))
                    for dg in _finde_alle(kap, "diagnosegruppe")
                } - {""})
                if bereich or gruppen:
                    kapitel.append({
                        "kapitel": normalisiere(kap.get("V")),
                        "bereich": bereich,
                        "diagnosegruppen": gruppen,
                    })
                    if bereich:
                        bereiche[bereich] += 1

            eintrag: Dict[str, Any] = {"anlage": anlage, "anlage_text": _ANLAGE_TEXT.get(anlage, "")}
            if hinweis:
                eintrag["hinweis"] = hinweis
            if kapitel:
                eintrag["kapitel"] = kapitel
            if kv:
                eintrag["geltungsbereich_kv"] = kv
            for name, schluessel in (("untere_altersgrenze", "alter_ab"),
                                     ("obere_altersgrenze", "alter_bis"),
                                     ("zeitraum_akutereignis", "zeitraum_akutereignis")):
                treffer = _finde_alle(hm, name)
                if treffer:
                    wert = _altersgrenze(treffer[0])
                    if wert:
                        eintrag[schluessel] = wert
            sekundaer = sorted({
                normalisiere(e.get("V")) for e in _finde_alle(hm, "sekundaercode")
            } - {""})
            if sekundaer:
                eintrag["sekundaercode"] = sekundaer

            if anlage:
                anlagen[anlage] += 1
            for icd in icds:
                # Denselben Eintrag nicht zweimal am gleichen ICD ablegen
                if eintrag not in nach_icd[icd]:
                    nach_icd[icd].append(eintrag)

    return {
        "_hinweis": [
            "Automatisch erzeugt aus der KBV-Stammdatei Heilmittelanlagen (SDHMA).",
            "NICHT von Hand bearbeiten — beim nächsten Import wird die Datei überschrieben.",
            "",
            "Erzeugt mit: python tools/import_kbv_stammdaten.py",
            "",
            "Aufbau: 'icd' bildet einen ICD-10-Code auf eine Liste von Einträgen ab.",
            "Mehrere Einträge entstehen, wenn ein Code in mehreren Anlagen oder nur in",
            "einzelnen KV-Bereichen gilt.",
            "",
            "'geltungsbereich_kv' nennt die KV-Bereiche, in denen der Eintrag gilt.",
            "Fehlt das Feld, gilt der Eintrag bundesweit. Die Klartexte zu den",
            "KV-Bereichsnummern sind noch nicht hinterlegt.",
            "",
            "Diese Liste sagt, was verordnungsfähig war — sie ersetzt keine Prüfung",
            "der Verordnung und ist an einen Gültigkeitsstand gebunden (siehe _quelle).",
        ],
        "_quelle": {
            "datei": xml_pfad.name,
            **_kopf(root),
            "anzahl_icd": len(nach_icd),
            "anzahl_verordnungsbedarfe": len(bedarfe),
            "ohne_icd_code": ohne_icd,
            "anlagen": {f"{k} — {_ANLAGE_TEXT.get(k, k)}": v for k, v in sorted(anlagen.items())},
            "heilmittelbereiche": dict(sorted(bereiche.items())),
        },
        "icd": {k: v for k, v in sorted(nach_icd.items())},
    }


# ---------------------------------------------------------------------------

def _neueste(quellen: Path, praefix: str, ausschluss: str = "") -> Optional[Path]:
    """
    Neueste Datei mit dem Präfix. 'sdhm' würde auch 'sdhma' treffen, deshalb
    lässt sich ein Ausschluss-Präfix angeben.
    """
    treffer = [
        p for p in sorted(quellen.glob(f"{praefix}*.xml"))
        if not (ausschluss and p.name.lower().startswith(ausschluss))
    ]
    return treffer[-1] if treffer else None


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Erzeugt data/diagnosegruppen.json und data/verordnungsbedarf.json "
                    "aus den KBV-Heilmittelstammdateien.",
    )
    parser.add_argument("--quellen", "-q", default=str(STANDARD_QUELLEN),
                        help=f"Verzeichnis mit den XML-Dateien (Standard: {STANDARD_QUELLEN.name}/)")
    parser.add_argument("--sdhm", help="Pfad zur Heilmittelstammdatei (überschreibt die Suche)")
    parser.add_argument("--sdhma", help="Pfad zur Stammdatei Heilmittelanlagen")
    args = parser.parse_args()

    quellen = Path(args.quellen)
    sdhm = Path(args.sdhm) if args.sdhm else _neueste(quellen, "sdhm", ausschluss="sdhma")
    sdhma = Path(args.sdhma) if args.sdhma else _neueste(quellen, "sdhma")

    if not sdhm and not sdhma:
        print(f"Fehler: keine sdhm*/sdhma*-XML in {quellen} gefunden.", file=sys.stderr)
        sys.exit(2)

    geschrieben = 0
    for pfad, parser_fn, ziel, was in (
        (sdhm, parse_sdhm, ZIEL_DIAGNOSEGRUPPEN, "Diagnosegruppen"),
        (sdhma, parse_sdhma, ZIEL_VERORDNUNGSBEDARF, "Verordnungsbedarf"),
    ):
        if not pfad:
            print(f"Übersprungen: keine Quelldatei für {was}.")
            continue
        if not pfad.is_file():
            print(f"Fehler: Datei nicht gefunden: {pfad}", file=sys.stderr)
            sys.exit(2)
        try:
            daten = parser_fn(pfad)
        except ValueError as e:
            print(f"Fehler: {e}", file=sys.stderr)
            sys.exit(1)

        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(json.dumps(daten, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        geschrieben += 1

        q = daten["_quelle"]
        print(f"{was} eingelesen: {q['datei']}")
        print(f"  Schnittstelle {q.get('schnittstelle', '?')} Version {q.get('version', '?')}"
              f", gültig {q.get('gueltig', '?')}")
        if was == "Diagnosegruppen":
            print(f"  {q['anzahl_diagnosegruppen']} Diagnosegruppen in {q['anzahl_kapitel']} Kapiteln")
            for kap in daten["kapitel"]:
                print(f"    {len(kap['diagnosegruppen']):4}  {kap['kapitel']}. {kap['bereich']}")
        else:
            print(f"  {q['anzahl_icd']} ICD-Codes aus {q['anzahl_verordnungsbedarfe']} Verordnungsbedarfen")
            for anlage, anzahl in q["anlagen"].items():
                print(f"    {anzahl:4}  {anlage}")
            if q["ohne_icd_code"]:
                print(f"    {q['ohne_icd_code']:4}  Einträge ohne ICD-Code übersprungen")
        print(f"  Geschrieben: {ziel}\n")

    if geschrieben:
        print("Im Programm über 'Codelisten neu laden' im Verordnungsblatt aktivieren.")


if __name__ == "__main__":
    main()
