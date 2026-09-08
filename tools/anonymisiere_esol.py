#!/usr/bin/env python3
"""
Erzeugt eine anonymisierte Kopie einer ESOL-Abrechnungsdatei.

Zweck: eine Kundendatei an Kollegen oder den Hersteller geben können, ohne
Patientendaten mitzuschicken. Die Kopie bleibt strukturell dieselbe Datei —
Segmentfolge, Zähler und Summen sind unverändert, nur die personenbezogenen
Felder sind ersetzt. Damit lässt sich der Fehler daran genauso nachvollziehen
wie am Original.

    python tools/anonymisiere_esol.py ESOL0253
    python tools/anonymisiere_esol.py ESOL0253 --gruppen versicherter arzt diagnosen
    python tools/anonymisiere_esol.py ESOL0253 --out-dir anonym --alle

Ohne --gruppen werden die Standardgruppen genommen (Versicherter, Arzt).
Neben der Datei entsteht eine Begleitdatei <name>.anonym.txt, die festhält,
was ersetzt wurde — ESOL selbst kennt keine Kommentare, jede Hinweiszeile in
der Datei wäre ein ungültiges Segment.

DIE KOPIE DARF NICHT ABGERECHNET WERDEN. Sie enthält erfundene Namen, eine
erfundene Versichertennummer und einen erfundenen Geburtstag (nur das
Geburtsjahr stammt aus dem Original).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import anonymisierung  # noqa: E402
from esol_validator import EsolValidator  # noqa: E402
from tools.generate_correction import read_esol_file_text  # noqa: E402


def anonymisiere_datei(
    quelle: Path,
    ziel: Path,
    gruppen=None,
    begleitdatei: bool = True,
) -> tuple:
    """
    Schreibt die anonymisierte Kopie und liefert (Zielpfad, Anonymisierer).

    Die Kopie wird nach dem Schreiben geprüft: wird sie durch die
    Anonymisierung ungültig, ist der Ersatzwert schuld und nicht die
    Quelldatei — das soll auffallen und nicht beim Empfänger landen.
    """
    inhalt = read_esol_file_text(quelle)
    anon = anonymisierung.Anonymisierer(
        gruppen=gruppen, stil=anonymisierung.STIL_FORMATTREU
    )
    neu = anon.esol(inhalt)

    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(neu, encoding="iso-8859-15")

    if begleitdatei:
        ziel.with_suffix(ziel.suffix + ".anonym.txt").write_text(
            anonymisierung.kopfzeilen_esol(anon, quelle.name), encoding="utf-8"
        )

    return ziel, anon


def _pruefe(text: str):
    validator = EsolValidator()
    validator.register_default_rules()
    return validator.validate_string(text)


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Erzeugt eine anonymisierte Kopie einer ESOL-Datei zur Fehleranalyse.",
    )
    parser.add_argument("input_file", help="Die ESOL-Datei")
    parser.add_argument("--out-dir", help="Zielverzeichnis (Standard: neben der Quelldatei)")
    parser.add_argument(
        "--gruppen", nargs="+", choices=sorted(anonymisierung.FELDGRUPPEN),
        help="Welche Feldgruppen ersetzt werden (Standard: "
             + ", ".join(sorted(anonymisierung.standard_gruppen())) + ")",
    )
    parser.add_argument("--alle", action="store_true",
                        help="Alle Feldgruppen ersetzen")
    parser.add_argument("--ohne-begleitdatei", action="store_true",
                        help="Keine .anonym.txt neben der Kopie schreiben")
    args = parser.parse_args()

    quelle = Path(args.input_file)
    if not quelle.is_file():
        print(f"Fehler: Datei nicht gefunden: {quelle}", file=sys.stderr)
        sys.exit(2)

    if args.alle:
        gruppen = set(anonymisierung.FELDGRUPPEN)
    elif args.gruppen:
        gruppen = set(args.gruppen)
    else:
        gruppen = None

    ziel_dir = Path(args.out_dir) if args.out_dir else quelle.parent
    ziel = ziel_dir / f"{quelle.name}_anonym"

    vorher = _pruefe(read_esol_file_text(quelle))
    ziel, anon = anonymisiere_datei(
        quelle, ziel, gruppen, begleitdatei=not args.ohne_begleitdatei
    )
    nachher = _pruefe(ziel.read_text(encoding="iso-8859-15"))

    print(f"Anonymisierte Kopie: {ziel}")
    for zeile in anon.bericht():
        print(f"  {zeile}")

    print(f"\nPrüfung: Original {vorher.error_count()} Fehler, "
          f"Kopie {nachher.error_count()} Fehler")
    neue = {str(e) for e in nachher.get_errors()} - {str(e) for e in vorher.get_errors()}
    if neue:
        # Zwei Ursachen sind möglich und von hier aus nicht zu unterscheiden:
        #   1. Ein Ersatzwert passt nicht — dann ist die Kopie unbrauchbar.
        #   2. Ein Fehler war vorher VERDECKT. Die Prüfung bricht nach einer
        #      Stufe ab; ein Syntaxfehler auf Stufe 2 verhindert also, dass
        #      Stufe 3 überhaupt läuft. Enthält ein Name ein kaputtes '?'
        #      (häufig eine verstümmelte Umlaut-Kodierung), verschwindet der
        #      Syntaxfehler mit dem Namen — und die Inhaltsprüfung meldet, was
        #      dahinter lag. Belegt an testdata/in/ESOL0167.
        print("\nHinweis: die Kopie zeigt Fehler, die das Original nicht zeigte:",
              file=sys.stderr)
        for e in sorted(neue):
            print(f"  {e}", file=sys.stderr)
        stufe12 = [e for e in vorher.get_errors() if str(e).startswith(("ERROR [1.1", "ERROR [1.2"))]
        if stufe12:
            print("\nDas Original hatte Fehler auf Stufe 1/2 — die Prüfung brach dort ab.",
                  file=sys.stderr)
            print("Die Meldungen oben waren daher vermutlich schon vorher vorhanden,",
                  file=sys.stderr)
            print("nur von der abgebrochenen Prüfung verdeckt.", file=sys.stderr)
        else:
            print("\nDas Original war auf Stufe 1/2 fehlerfrei — hier ist eher ein",
                  file=sys.stderr)
            print("Ersatzwert schuld. Die Kopie vor der Weitergabe prüfen.", file=sys.stderr)
        sys.exit(1)

    if not args.ohne_begleitdatei:
        print(f"Begleitdatei:        {ziel.with_suffix(ziel.suffix + '.anonym.txt')}")
    print("\nDiese Kopie ist zur Fehleranalyse gedacht und darf NICHT abgerechnet werden.")


if __name__ == "__main__":
    main()
