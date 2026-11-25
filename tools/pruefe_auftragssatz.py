#!/usr/bin/env python3
"""
Auftragssatz (.auf) prüfen und Versandweg anzeigen.

Nutzung:
  python tools/pruefe_auftragssatz.py <datei> [<datei> ...]
  py-esol.exe pruefe_auftragssatz <datei>

<datei> darf die Nutzdatendatei (ESOL0145) oder der Auftragssatz
(ESOL0145.auf) sein; die jeweils andere Datei wird daneben gesucht.
Exit-Code 1, wenn mindestens ein FEHLER gefunden wurde.
"""

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import auftragssatz


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Auftragssatz (.auf) prüfen und Versandweg anzeigen"
    )
    parser.add_argument("dateien", nargs="+",
                        help="Nutzdatendatei oder .auf-Datei")
    args = parser.parse_args()

    fehler = False
    for name in args.dateien:
        pfad = Path(name)
        if not pfad.is_file():
            print(f"FEHLER  Datei nicht gefunden: {pfad}", file=sys.stderr)
            fehler = True
            continue
        try:
            bericht = auftragssatz.pruefe(pfad)
        except Exception as exc:  # eine defekte Datei darf den Lauf nicht abbrechen
            print(f"FEHLER  {pfad.name}: Auftragssatz nicht prüfbar: {exc}")
            fehler = True
            continue
        print(auftragssatz.bericht_text(bericht))
        fehler = fehler or bericht.hat_fehler

    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
