#!/usr/bin/env python3
"""
ESOL Correction & Co-payment Generator — Generiert Korrekturabrechnungen (VKZ 04),
Zuzahlungsnachforderungen (VKZ 03) oder Nachforderungen (VKZ 02) aus einer bestehenden ESOL-Datei.

Nutzung:
  python tools/generate_correction.py <input-file> --type=03 [options]
  python tools/generate_correction.py <input-file> --type=04 [options]
"""

import argparse
import datetime
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Ensure project root is in sys.path when script is executed directly from tools directory
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from parser.segment_tokenizer import SegmentTokenizer
from rules.level3.content_helper import ContentHelper


def parse_segment_fields(raw_segment: str) -> Tuple[str, List[Any]]:
    """Splits a raw EDIFACT segment into tag and field elements."""
    raw = raw_segment.strip().rstrip("'")
    if not raw:
        return "", []
    parts = raw.split("+")
    tag = parts[0]
    fields = []
    for p in parts[1:]:
        if ":" in p:
            fields.append(p.split(":"))
        else:
            fields.append(p)
    return tag, fields


def build_segment_string(tag: str, fields: List[Any]) -> str:
    """Builds a formatted raw EDIFACT segment string from tag and fields."""
    parts = [tag]
    for f in fields:
        if isinstance(f, list):
            parts.append(":".join(str(item) for item in f))
        else:
            parts.append(str(f) if f is not None else "")
    return "+".join(parts) + "'"


def parse_esol_belege_summary(raw_content: str) -> List[Dict[str, Any]]:
    """
    Parses an ESOL file content and returns a list of dictionaries with metadata for each Beleg (INV block).
    """
    tokenizer = SegmentTokenizer()
    raw_segments = tokenizer.tokenize_segments(raw_content)

    belege = []
    in_inv = False
    current_beleg: Dict[str, Any] = {}

    for raw_seg in raw_segments:
        tag, fields = parse_segment_fields(raw_seg)

        if tag == "INV":
            if in_inv and current_beleg:
                belege.append(current_beleg)
            in_inv = True
            belegnr = str(fields[0]) if len(fields) > 0 else ""
            current_beleg = {
                "belegnr": belegnr,
                "nachname": "",
                "vorname": "",
                "geburtstag": "",
                "brutto": 0.0,
                "zuzahlung_proz": 0.0,
                "zuzahlung_pausch": 10.0,
                "total_zuzahlung": 0.0,
                "positions": [],
            }

        elif in_inv:
            if tag == "NAD":
                if len(fields) > 0:
                    current_beleg["nachname"] = str(fields[0])
                if len(fields) > 1:
                    current_beleg["vorname"] = str(fields[1])
                if len(fields) > 2:
                    current_beleg["geburtstag"] = str(fields[2])

            elif tag in ["EHE", "ENF", "EHI", "EHK"]:
                anzahl = 0.0
                betrag_zuz = 0.0
                code = ""
                einzelbetrag = 0.0

                if tag == "EHE":
                    code = str(fields[0]) if len(fields) > 0 else ""
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzelbetrag = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[5]).replace(",", ".")) if len(fields) > 5 and fields[5] else 0.0
                elif tag == "ENF":
                    code = str(fields[1]) if len(fields) > 1 else ""
                    anzahl = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    einzelbetrag = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0

                current_beleg["zuzahlung_proz"] += round(anzahl * betrag_zuz, 2)
                current_beleg["positions"].append({
                    "tag": tag,
                    "code": code,
                    "anzahl": anzahl,
                    "einzelbetrag": einzelbetrag,
                    "zuzahlung": betrag_zuz,
                })

            elif tag == "BES":
                if len(fields) > 0 and fields[0]:
                    current_beleg["brutto"] = float(str(fields[0]).replace(",", "."))
                if len(fields) > 3 and fields[3]:
                    current_beleg["zuzahlung_pausch"] = float(str(fields[3]).replace(",", "."))
                current_beleg["total_zuzahlung"] = round(
                    current_beleg["zuzahlung_proz"] + current_beleg["zuzahlung_pausch"], 2
                )
                belege.append(current_beleg)
                in_inv = False
                current_beleg = {}

    if in_inv and current_beleg:
        belege.append(current_beleg)

    return belege


def generate_correction_esol(
    raw_content: str,
    target_vk: str = "03",  # "02" Nachforderung, "03" Zuzahlungsforderung, "04" Korrekturrechnung
    selected_belegnr_list: Optional[List[str]] = None,
    new_rec_nr: Optional[str] = None,
    new_rec_date: Optional[str] = None,
) -> str:
    """
    Generates a new ESOL content string with target VKZ (02, 03, 04) from original raw ESOL content.
    Optionally filters output to include only specified Belegnummern.
    """
    tokenizer = SegmentTokenizer()
    raw_segments = tokenizer.tokenize_segments(raw_content)

    if not raw_segments:
        raise ValueError("Datei enthält keine gültigen EDIFACT-Segmente.")

    today_str = datetime.datetime.now().strftime("%Y%m%d")
    if not new_rec_date:
        new_rec_date = today_str

    selected_set = set(selected_belegnr_list) if selected_belegnr_list else None

    # First pass: extract original header metadata and calculate total Zuzahlung for selected Belege
    orig_rec_nr = ""
    orig_rec_date = ""
    orig_ik_le = ""
    total_zuzahlung_file = 0.0

    in_inv_block_p1 = False
    keep_block_p1 = False
    current_inv_zuz_proz_p1 = 0.0
    current_inv_zuz_pausch_p1 = 0.0

    for raw_seg in raw_segments:
        tag, fields = parse_segment_fields(raw_seg)
        if tag == "UNB" and not orig_ik_le:
            if len(fields) > 1 and fields[1]:
                orig_ik_le = fields[1][0] if isinstance(fields[1], list) else str(fields[1])
        elif tag == "FKT" and not orig_ik_le:
            if len(fields) > 2 and fields[2]:
                orig_ik_le = fields[2][0] if isinstance(fields[2], list) else str(fields[2])
            elif len(fields) > 1 and fields[1]:
                orig_ik_le = fields[1][0] if isinstance(fields[1], list) else str(fields[1])
        elif tag == "REC" and not orig_rec_nr:
            if len(fields) > 0:
                orig_rec_nr = ":".join(fields[0]) if isinstance(fields[0], list) else str(fields[0])
            if len(fields) > 1:
                orig_rec_date = str(fields[1])

        elif tag == "INV":
            in_inv_block_p1 = True
            belegnr = str(fields[0]) if len(fields) > 0 else ""
            keep_block_p1 = (selected_set is None) or (belegnr in selected_set)
            current_inv_zuz_proz_p1 = 0.0
            current_inv_zuz_pausch_p1 = 0.0

        elif in_inv_block_p1:
            if keep_block_p1 and tag in ["EHE", "ENF", "EHI", "EHK"]:
                anzahl = 0.0
                betrag_zuz = 0.0
                if tag == "EHE":
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    betrag_zuz = float(str(fields[5]).replace(",", ".")) if len(fields) > 5 and fields[5] else 0.0
                elif tag == "ENF":
                    anzahl = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                current_inv_zuz_proz_p1 += round(anzahl * betrag_zuz, 2)
            elif tag == "BES":
                if keep_block_p1:
                    if len(fields) > 3 and fields[3]:
                        current_inv_zuz_pausch_p1 = float(str(fields[3]).replace(",", "."))
                    else:
                        current_inv_zuz_pausch_p1 = 10.0
                    total_zuzahlung_file += round(current_inv_zuz_proz_p1 + current_inv_zuz_pausch_p1, 2)
                in_inv_block_p1 = False

    if not new_rec_nr:
        suffix = "Z" if target_vk == "03" else ("K" if target_vk == "04" else "N")
        orig_clean_nr = orig_rec_nr.replace(":", "")
        new_rec_nr = f"{orig_clean_nr}{suffix}" if orig_clean_nr else f"RE{today_str}{suffix}"

    new_raw_segments = []

    in_inv_block = False
    keep_block = False
    current_inv_belegnr = ""
    current_inv_zuz_proz = 0.0
    current_inv_zuz_pausch = 0.0
    inv_block_segments: List[Tuple[str, List[Any]]] = []

    for raw_seg in raw_segments:
        tag, fields = parse_segment_fields(raw_seg)

        if tag == "FKT":
            # Change VK in FKT (field 0)
            if len(fields) > 0:
                fields[0] = target_vk
            new_raw_segments.append(build_segment_string(tag, fields))

        elif tag == "REC":
            # Change Rechnungsnummer and Rechnungsdatum
            if len(fields) > 0:
                fields[0] = new_rec_nr.split(":") if ":" in new_rec_nr else new_rec_nr
            if len(fields) > 1:
                fields[1] = new_rec_date
            new_raw_segments.append(build_segment_string(tag, fields))

        elif tag == "GES":
            # In SLGA for VK 03, GES field 1 is Rechnungsbetrag (total_zuzahlung), field 2 is Brutto (0.00), field 3 is Zuzahlung (total_zuzahlung)
            if target_vk == "03":
                zuz_str = ContentHelper.format_decimal(total_zuzahlung_file)
                if len(fields) > 1:
                    fields[1] = zuz_str
                if len(fields) > 2:
                    fields[2] = "0,00"
                if len(fields) > 3:
                    fields[3] = zuz_str
            new_raw_segments.append(build_segment_string(tag, fields))

        elif tag == "INV":
            in_inv_block = True
            current_inv_belegnr = str(fields[0]) if len(fields) > 0 else ""
            keep_block = (selected_set is None) or (current_inv_belegnr in selected_set)
            inv_block_segments = [(tag, fields)]
            current_inv_zuz_proz = 0.0
            current_inv_zuz_pausch = 0.0

        elif in_inv_block:
            if not keep_block:
                if tag == "BES":
                    in_inv_block = False
                    inv_block_segments = []
                continue

            if tag in ["EHE", "ENF", "EHI", "EHK"]:
                anzahl = 0.0
                betrag_zuz = 0.0
                if tag == "EHE":
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    betrag_zuz = float(str(fields[5]).replace(",", ".")) if len(fields) > 5 and fields[5] else 0.0
                elif tag == "ENF":
                    anzahl = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0

                current_inv_zuz_proz += round(anzahl * betrag_zuz, 2)
                inv_block_segments.append((tag, fields))

            elif tag == "ZHE":
                # In VK 03, Zuzahlungskennzeichen in ZHE (field 3) is set to '2' (Zuzahlung verweigert)
                if target_vk == "03" and len(fields) > 3:
                    fields[3] = "2"
                inv_block_segments.append((tag, fields))

            elif tag == "BES":
                if len(fields) > 3 and fields[3]:
                    current_inv_zuz_pausch = float(str(fields[3]).replace(",", "."))
                else:
                    current_inv_zuz_pausch = 10.0

                uri_fields = [
                    orig_ik_le,
                    orig_rec_nr.split(":") if ":" in orig_rec_nr else orig_rec_nr,
                    orig_rec_date,
                    current_inv_belegnr,
                ]

                if target_vk == "03":
                    tot_zuz = round(current_inv_zuz_proz + current_inv_zuz_pausch, 2)

                    gzf_fields = [
                        ContentHelper.format_decimal(tot_zuz),
                        ContentHelper.format_decimal(current_inv_zuz_proz),
                        ContentHelper.format_decimal(current_inv_zuz_pausch),
                    ]
                    for inv_tag, inv_f in inv_block_segments:
                        new_raw_segments.append(build_segment_string(inv_tag, inv_f))
                        if inv_tag == "INV":
                            new_raw_segments.append(build_segment_string("URI", uri_fields))

                    new_raw_segments.append(build_segment_string("GZF", gzf_fields))
                    in_inv_block = False
                    inv_block_segments = []
                else:
                    for inv_tag, inv_f in inv_block_segments:
                        new_raw_segments.append(build_segment_string(inv_tag, inv_f))
                        if inv_tag == "INV":
                            new_raw_segments.append(build_segment_string("URI", uri_fields))
                    new_raw_segments.append(build_segment_string(tag, fields))
                    in_inv_block = False
                    inv_block_segments = []

            elif tag == "UNT":
                if in_inv_block and keep_block:
                    for inv_tag, inv_f in inv_block_segments:
                        new_raw_segments.append(build_segment_string(inv_tag, inv_f))
                    in_inv_block = False
                    inv_block_segments = []
                new_raw_segments.append(build_segment_string(tag, fields))

            else:
                inv_block_segments.append((tag, fields))

        elif tag == "UNT":
            new_raw_segments.append(build_segment_string(tag, fields))

        else:
            new_raw_segments.append(build_segment_string(tag, fields))

    # Recalculate UNT segment counts (number of segments between UNH and UNT inclusive)
    final_segments = []
    unh_seg_index = -1
    seg_counter = 0

    for seg_str in new_raw_segments:
        tag, fields = parse_segment_fields(seg_str)
        if tag == "UNH":
            unh_seg_index = len(final_segments)
            seg_counter = 1
            final_segments.append(seg_str)
        elif tag == "UNT":
            seg_counter += 1
            if len(fields) > 0:
                fields[0] = str(seg_counter).zfill(6)
            final_segments.append(build_segment_string(tag, fields))
            seg_counter = 0
        else:
            if unh_seg_index >= 0:
                seg_counter += 1
            final_segments.append(seg_str)

    return "\n".join(final_segments) + "\n"


def generate_correction_file(
    input_path: Path,
    output_path: Optional[Path] = None,
    target_vk: str = "03",
    selected_belegnr_list: Optional[List[str]] = None,
    new_rec_nr: Optional[str] = None,
    new_rec_date: Optional[str] = None,
) -> Path:
    """Reads an ESOL file and generates the corrected/demanded ESOL output file."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {input_path}")

    if not output_path:
        suffix = f"_VK{target_vk}"
        output_path = input_path.with_name(f"{input_path.name}{suffix}")

    content = input_path.read_text(encoding="iso-8859-15", errors="replace")
    new_content = generate_correction_esol(
        raw_content=content,
        target_vk=target_vk,
        selected_belegnr_list=selected_belegnr_list,
        new_rec_nr=new_rec_nr,
        new_rec_date=new_rec_date,
    )
    output_path.write_text(new_content, encoding="iso-8859-15")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ESOL Korrektur & Zuzahlungsnachforderung Generator (VKZ 02 / 03 / 04)"
    )
    parser.add_argument("input_file", help="Pfad zur ursprünglichen ESOL-Datei")
    parser.add_argument(
        "output_file",
        nargs="?",
        default=None,
        help="Optionaler Zielpfad für die generierte Datei",
    )
    parser.add_argument(
        "--type",
        "-t",
        default="03",
        choices=["02", "03", "04"],
        help="Verarbeitungskennzeichen: 03 (Zuzahlungsforderung), 04 (Korrekturrechnung), 02 (Nachforderung)",
    )
    parser.add_argument(
        "--new-rec-nr",
        default=None,
        help="Neue Rechnungsnummer (standardmäßig automatisch)",
    )
    parser.add_argument(
        "--new-rec-date",
        default=None,
        help="Neues Rechnungsdatum JJJJMMTT (standardmäßig heute)",
    )
    parser.add_argument(
        "--belege",
        nargs="*",
        default=None,
        help="Ausgewählte Belegnummern, die übernommen werden sollen",
    )

    args = parser.parse_args()
    input_path = Path(args.input_file)

    try:
        res_path = generate_correction_file(
            input_path=input_path,
            output_path=Path(args.output_file) if args.output_file else None,
            target_vk=args.type,
            selected_belegnr_list=args.belege,
            new_rec_nr=args.new_rec_nr,
            new_rec_date=args.new_rec_date,
        )
        print(f"Korrekturdatei (VKZ {args.type}) erfolgreich erstellt: {res_path}")
    except Exception as e:
        print(f"Fehler bei Erstellung der Korrekturdatei: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
