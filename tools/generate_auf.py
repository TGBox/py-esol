#!/usr/bin/env python3
"""
ESOL Auftragsdatei Generator — Generiert eine GKV-Auftragsdatei (.auf, Version 01, 348 Bytes)
aus einer ESOL Nutzdatendatei.

Nutzung:
  python generate_auf.py <input-file> [output-file]

Beispiel:
  python generate_auf.py SL030179S03
  # Erzeugt: SL030179S03.auf
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

# Ensure project root is in sys.path when script is executed directly from tools directory
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from parser.segment_tokenizer import SegmentTokenizer
from rules.level3.content_helper import ContentHelper


def create_auftragsdatei(
    file_path: Path,
    owner_ik: str,
    absender_ik: str,
    empfaenger_ik: str,
    logischer_name: str,
    timestamp: str,
    size: int,
    encoding_code: str = "I5",
) -> str:
    """
    Erstellt den 348-Byte String einer GKV-Auftragsdatei (Version 01).
    """
    kurzel = file_path.name
    clean_timestamp = str(timestamp).replace(":", "").strip()
    if len(clean_timestamp) == 12:
        clean_timestamp += "00"

    absender_padded = str(absender_ik).strip().ljust(15)
    empfaenger_padded = str(empfaenger_ik).strip().ljust(15)
    logischer_name_str = str(logischer_name).strip()

    buf = []
    buf.append("500000")                             # Identifikator (6)
    buf.append("01")                                 # Version (2)
    buf.append("00000348")                           # Länge der Auftragsdatei (8)
    buf.append("000")                                # Sequenznummer (3)
    buf.append(kurzel)                               # Verfahrenskennung / Dateiname
    buf.append("     ")                              # Spezifikation (5 Leerzeichen)
    buf.append(absender_padded)                      # Absender IK Eigner (15)
    buf.append(absender_padded)                      # Absender IK Physikalisch (15)
    buf.append(empfaenger_padded)                    # Empfänger IK (15)
    buf.append(empfaenger_padded)                    # Empfänger IK (15)
    buf.append("000000")                             # Fehler-Nummer (6)
    buf.append("000000")                             # Fehler-Maßnahme (6)
    buf.append(logischer_name_str)                   # Logischer Dateiname
    buf.append(clean_timestamp)                      # Datum/Zeit Erstellung JHJJMMTThhmmss (14)
    buf.append(clean_timestamp)                      # Datum/Zeit Gesendet JHJJMMTThhmmss (14)
    buf.append("00000000000000")                     # Datum/Zeit Empfangen 1 (14)
    buf.append("00000000000000")                     # Datum/Zeit Empfangen 2 (14)
    buf.append("000000")                             # Version (6)
    buf.append("0")                                  # Korrektur (1)
    buf.append(f"{size:012d}")                       # Dateigröße Nutzdaten (12)
    buf.append(f"{size:012d}")                       # Dateigröße komprimiert (12)
    buf.append(encoding_code.ljust(2)[:2])          # Zeichensatz I5=ISO-8859-15, U8=UTF-8 (2)
    buf.append("00")                                 # Komprimierung (2)
    buf.append("00")                                 # Verschlüsselung (2)
    buf.append("00")                                 # Elektronische Unterschrift (2)
    buf.append("   ")                                # Satzformat (3)
    buf.append("00000")                              # Satzlänge (5)
    buf.append("00000000")                           # Blocklänge (8)
    buf.append("0")                                  # Flag (1)
    buf.append("00")                                 # Wiederholung (2)
    buf.append("5")                                  # Übertragungsweg (1)
    buf.append("0000000000")                         # Verzögerter Versand (10)
    buf.append("000000")                             # Status (6)
    buf.append(" " * 28)                             # Infofeld 1 (28)
    buf.append(" " * 44)                             # Infofeld 2 (44)
    buf.append(" " * 30)                             # Infofeld 3 (30)

    return "".join(buf)


def parse_esol_file(file_path: Path) -> Tuple[str, str, str, str, str, int]:
    """
    Liest eine ESOL-Datei und extrahiert UNB- und FKT-Felder.
    Rückgabe: (my_ik, sender_ik, recver_ik, logischer_name, timestamp, size)
    """
    size = file_path.stat().st_size
    raw_content = file_path.read_text(encoding="iso-8859-1", errors="replace")

    tokenizer = SegmentTokenizer()
    raw_segments = tokenizer.tokenize_segments(raw_content)
    parsed_segments = [tokenizer.parse_segment(raw) for raw in raw_segments]

    unb_seg = next((s for s in parsed_segments if s.get("tag") == "UNB"), None)
    fkt_seg = next((s for s in parsed_segments if s.get("tag") == "FKT"), None)

    if not unb_seg:
        raise ValueError(f"Kein UNB-Segment in {file_path} gefunden.")

    sender_ik = ContentHelper.get_field(unb_seg, 1) or ""
    recver_ik = ContentHelper.get_field(unb_seg, 2) or ""

    datum = ContentHelper.get_field(unb_seg, 3, 0) or ""
    uhrzeit = ContentHelper.get_field(unb_seg, 3, 1) or ""
    timestamp = f"{datum}{uhrzeit}"

    logischer_name = ContentHelper.get_field(unb_seg, 6) or ""

    my_ik = ""
    if fkt_seg:
        my_ik = ContentHelper.get_field(fkt_seg, 2) or ""

    return my_ik, sender_ik, recver_ik, logischer_name, timestamp, size


def generate_auf(input_path: Path, output_path: Optional[Path] = None) -> Path:
    """
    Generiert die .auf Auftragsdatei für eine gegebene ESOL-Datei.
    """
    if not output_path:
        output_path = Path(f"{input_path}.auf")

    my_ik, sender_ik, recver_ik, logischer_name, timestamp, size = parse_esol_file(input_path)

    auf_content = create_auftragsdatei(
        file_path=input_path,
        owner_ik=my_ik,
        absender_ik=sender_ik,
        empfaenger_ik=recver_ik,
        logischer_name=logischer_name,
        timestamp=timestamp,
        size=size,
    )

    output_path.write_text(auf_content, encoding="iso-8859-15")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ESOL Auftragsdatei Generator — Generiert .auf Auftragsdateien"
    )
    parser.add_argument(
        "input_file",
        help="Pfad zur ESOL Nutzdatendatei",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        default=None,
        help="Optionaler Pfad für die Ausgabedatei (Standard: <input_file>.auf)",
    )

    args = parser.parse_args()
    input_path = Path(args.input_file)

    if not input_path.is_file():
        print(f"Fehler: Datei nicht gefunden: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output_file) if args.output_file else None

    try:
        res_path = generate_auf(input_path, output_path)
        print(f"Auftragsdatei erfolgreich erstellt: {res_path}")
    except Exception as e:
        print(f"Fehler beim Erstellen der Auftragsdatei: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
