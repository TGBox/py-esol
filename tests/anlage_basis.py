"""
Gemeinsame Hilfen für die Abgleichstests gegen die Technischen Anlagen.

Grundlage ist tests/fixtures/valid_esol_smoke — der kleinste vollständige,
gültige ESOL-Vorgang. Jeder Test verändert daran genau eine Stelle und prüft,
was die Validierung dazu sagt. Dadurch steht in jedem Test nur der
Unterschied, nicht eine ganze nachgebaute Datei.

Die Tests liefen zuerst gegen testdata/in/ESOL0001. Das ging lokal, im CI aber
nicht: testdata/ enthält echte Abrechnungsdateien und liegt deshalb nicht im
Repository. Die Fixture ist ohnehin die dafür vorgesehene Referenzdatei — sie
wird auch vom Rauchtest der fertigen EXE benutzt.
"""

from pathlib import Path
from typing import List

from esol_validator import EsolValidator
from tools.generate_correction import read_esol_file_text

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "valid_esol_smoke"

# Verzeichnis mit echten Abrechnungsdateien. Liegt nicht im Repository; wo es
# vorhanden ist, prüfen die Tests zusätzlich, dass keine Regel auf echten
# Daten anschlägt.
ECHTE_DATEIEN = Path(__file__).resolve().parent.parent / "testdata" / "in"


def basis() -> str:
    return read_esol_file_text(FIXTURE)


def basis_zeilen() -> List[str]:
    return [z for z in basis().replace("\r\n", "\n").split("\n") if z]


def zusammensetzen(zeilen) -> str:
    """
    Fügt die Zeilen zu einer Datei zusammen und zieht dabei die Zähler nach:
    UNT.Anzahl Einheiten und UNZ.Anzahl Nachrichten. Ohne das meldet jede
    Änderung zusätzlich einen Zählerfehler und verdeckt, was der Test
    eigentlich prüfen soll.
    """
    aus, puffer, anzahl_unh = [], [], 0
    for z in zeilen:
        if not z:
            continue
        if z.startswith("UNH"):
            anzahl_unh += 1
            puffer = [z]
        elif z.startswith("UNT"):
            puffer.append(z)
            ref = puffer[0].split("+")[1]
            puffer[-1] = f"UNT+{len(puffer):06d}+{ref}'"
            aus.extend(puffer)
            puffer = []
        elif puffer:
            puffer.append(z)
        elif z.startswith("UNZ"):
            ref = z.split("+")[2].rstrip("'")
            aus.append(f"UNZ+{anzahl_unh:06d}+{ref}'")
        else:
            aus.append(z)
    return "\r\n".join(aus) + "\r\n"


def _ergebnis(text: str):
    validator = EsolValidator()
    validator.register_default_rules()
    return validator.validate_string(text)


def codes(text: str) -> set:
    """Die Fehlercodes zu einem ESOL-Text."""
    return {e.code for e in _ergebnis(text).get_errors()}


def warnungen(text: str) -> set:
    return {w.code for w in _ergebnis(text).get_warnings()}


def ersetzt(alt: str, neu: str) -> str:
    """Die Fixture mit genau einer ersetzten Stelle."""
    text = basis()
    assert alt in text, f"Muster {alt!r} steht nicht in der Fixture"
    return zusammensetzen(text.replace(alt, neu, 1).replace("\r\n", "\n").split("\n"))


def ohne(tag: str) -> str:
    """Die Fixture ohne alle Segmente mit diesem Kennzeichen."""
    return zusammensetzen([z for z in basis_zeilen() if not z.startswith(tag)])


def mit_segment(nach_tag: str, segment: str) -> str:
    """Die Fixture mit einem zusätzlichen Segment hinter jedem <nach_tag>."""
    zeilen = []
    for z in basis_zeilen():
        zeilen.append(z)
        if z.startswith(nach_tag):
            zeilen.append(segment)
    return zusammensetzen(zeilen)


def echte_dateien() -> List[Path]:
    """Die vorhandenen Echtdateien, oder eine leere Liste."""
    if not ECHTE_DATEIEN.is_dir():
        return []
    return sorted(p for p in ECHTE_DATEIEN.iterdir() if p.is_file())
