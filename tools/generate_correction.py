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
            belegnr = str(fields[3]) if len(fields) > 3 and fields[3] else ""
            vers_nr = str(fields[0]) if len(fields) > 0 and fields[0] else ""
            current_beleg = {
                "belegnr": belegnr,
                "versichertennummer": vers_nr,
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

            elif tag in ["EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP"]:
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
                elif tag == "EHI":
                    code = str(fields[0]) if len(fields) > 0 else ""
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzelbetrag = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag in ["EHK", "EKT", "EHB", "ESP"]:
                    code = str(fields[0]) if len(fields) > 0 else ""
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzelbetrag = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0

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
    zuzahlungskennzeichen: Optional[str] = None,
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

    # Discover all non-00 GES status codes present in raw file
    ges_status_codes = []
    for raw_seg in raw_segments:
        t, f = parse_segment_fields(raw_seg)
        if t == "GES" and len(f) > 0:
            st = str(f[0])
            if st != "00" and st not in ges_status_codes:
                ges_status_codes.append(st)

    # First pass: extract original header metadata and calculate per-status totals for selected Belege
    orig_rec_nr = ""
    orig_rec_date = ""
    orig_ik_le = ""

    brutto_by_status: Dict[str, float] = {}
    zuzahlung_by_status: Dict[str, float] = {}

    in_inv_block_p1 = False
    keep_block_p1 = False
    current_ges_code_p1 = "00"
    current_inv_zuz_proz_p1 = 0.0
    current_inv_zuz_pausch_p1 = 0.0

    orig_sammel_nr = ""
    orig_einzel_nr = ""

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
                if isinstance(fields[0], list):
                    orig_sammel_nr = str(fields[0][0])
                    orig_einzel_nr = str(fields[0][1]) if len(fields[0]) > 1 and str(fields[0][1]) != "" else "0"
                    orig_rec_nr = ":".join([str(x) for x in fields[0]])
                else:
                    raw_str = str(fields[0])
                    if ":" in raw_str:
                        parts = raw_str.split(":")
                        orig_sammel_nr = parts[0]
                        orig_einzel_nr = parts[1] if len(parts) > 1 and parts[1] != "" else "0"
                    else:
                        orig_sammel_nr = raw_str
                        orig_einzel_nr = "0"
                    orig_rec_nr = raw_str
            if len(fields) > 1:
                orig_rec_date = str(fields[1])

        elif tag == "INV":
            in_inv_block_p1 = True
            belegnr = str(fields[3]) if len(fields) > 3 and fields[3] else ""
            vers_status = str(fields[1]) if len(fields) > 1 and fields[1] else "00"
            st_prefix2 = vers_status[:2] if len(vers_status) >= 2 else "00"
            st_prefix1 = vers_status[:1] if len(vers_status) >= 1 else "0"

            # Match Versichertenstatus to available GES status codes in the file
            if st_prefix2 in ges_status_codes:
                current_ges_code_p1 = st_prefix2
            else:
                matching = [c for c in ges_status_codes if c.startswith(st_prefix1)]
                if matching:
                    current_ges_code_p1 = matching[0]
                elif ges_status_codes:
                    current_ges_code_p1 = ges_status_codes[0]
                else:
                    current_ges_code_p1 = "00"

            keep_block_p1 = (selected_set is None) or (belegnr in selected_set)
            current_inv_zuz_proz_p1 = 0.0
            current_inv_zuz_pausch_p1 = 0.0

        elif in_inv_block_p1:
            if keep_block_p1 and tag in ["EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP"]:
                anzahl = 0.0
                betrag_zuz = 0.0
                if tag == "EHE":
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    betrag_zuz = float(str(fields[5]).replace(",", ".")) if len(fields) > 5 and fields[5] else 0.0
                elif tag == "ENF":
                    anzahl = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag == "EHI":
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag in ["EHK", "EKT", "EHB", "ESP"]:
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    betrag_zuz = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                current_inv_zuz_proz_p1 += round(anzahl * betrag_zuz, 2)
            elif tag == "BES":
                if keep_block_p1:
                    brutto_val = float(str(fields[0]).replace(",", ".")) if len(fields) > 0 and fields[0] else 0.0
                    brutto_by_status[current_ges_code_p1] = round(
                        brutto_by_status.get(current_ges_code_p1, 0.0) + brutto_val, 2
                    )

                    if target_vk == "03":
                        if len(fields) > 3 and fields[3]:
                            current_inv_zuz_pausch_p1 = float(str(fields[3]).replace(",", "."))
                        else:
                            current_inv_zuz_pausch_p1 = 10.0
                        inv_zuz = round(current_inv_zuz_proz_p1 + current_inv_zuz_pausch_p1, 2)
                    else:
                        if len(fields) > 1 and fields[1]:
                            inv_zuz = float(str(fields[1]).replace(",", "."))
                        else:
                            inv_zuz = round(current_inv_zuz_proz_p1 + current_inv_zuz_pausch_p1, 2)

                    zuzahlung_by_status[current_ges_code_p1] = round(
                        zuzahlung_by_status.get(current_ges_code_p1, 0.0) + inv_zuz, 2
                    )

                in_inv_block_p1 = False

    total_brutto_file = round(sum(brutto_by_status.values()), 2)
    total_zuzahlung_file = round(sum(zuzahlung_by_status.values()), 2)
    total_rechnungsbetrag_file = round(total_brutto_file - total_zuzahlung_file, 2)

    if not new_rec_nr:
        suffix = "Z" if target_vk == "03" else ("K" if target_vk == "04" else ("W" if target_vk == "10" else "N"))
        if orig_sammel_nr:
            new_sammel_nr = f"{orig_sammel_nr}{suffix}"
        else:
            new_sammel_nr = f"RE{today_str}{suffix}"
        new_einzel_nr = orig_einzel_nr if orig_einzel_nr != "" else ("0" if orig_sammel_nr else "")
    else:
        if ":" in new_rec_nr:
            parts = new_rec_nr.split(":")
            new_sammel_nr = parts[0]
            new_einzel_nr = parts[1]
        else:
            new_sammel_nr = new_rec_nr
            new_einzel_nr = orig_einzel_nr if orig_einzel_nr != "" else ("0" if orig_sammel_nr else "")

    if new_einzel_nr != "":
        rec_nr_fields: Any = [new_sammel_nr, new_einzel_nr]
    else:
        rec_nr_fields = new_sammel_nr
    new_rec_ref = new_sammel_nr.zfill(5) if (new_sammel_nr and len(new_sammel_nr) < 5) else new_sammel_nr

    new_raw_segments = []
    in_inv_block = False
    keep_block = False
    current_inv_belegnr = ""
    current_inv_zuz_proz = 0.0
    current_inv_zuz_pausch = 0.0
    inv_block_segments: List[Tuple[str, List[Any]]] = []
    written_ges_statuses = set()

    def make_ges_segment(st_code: str, st_b: float, st_z: float) -> str:
        st_rechn = round(st_b - st_z, 2)
        if target_vk == "03":
            f1 = ContentHelper.format_decimal(st_z)
            f2 = "0,00"
            f3 = ContentHelper.format_decimal(st_z)
        else:
            f1 = ContentHelper.format_decimal(st_rechn)
            f2 = ContentHelper.format_decimal(st_b)
            f3 = ContentHelper.format_decimal(st_z)
        return build_segment_string("GES", [st_code, f1, f2, f3])

    for raw_seg in raw_segments:
        tag, fields = parse_segment_fields(raw_seg)

        if tag != "GES" and "00" in written_ges_statuses:
            active_statuses = set(
                [code for code, val in brutto_by_status.items() if val > 0]
                + [code for code, val in zuzahlung_by_status.items() if val > 0]
            )
            for st_code in sorted(active_statuses):
                if st_code not in written_ges_statuses:
                    st_b = round(brutto_by_status.get(st_code, 0.0), 2)
                    st_z = round(zuzahlung_by_status.get(st_code, 0.0), 2)
                    new_raw_segments.append(make_ges_segment(st_code, st_b, st_z))
                    written_ges_statuses.add(st_code)

        if tag == "UNB":
            # Update Erstelldatum/Erstelluhrzeit (field 3), Datenaustauschreferenz (field 4), and Anwendungsreferenz/logischer Dateiname (field 6)
            curr_time_str = datetime.datetime.now().strftime("%H%M")
            if len(fields) > 3 and fields[3]:
                if isinstance(fields[3], list):
                    fields[3][0] = new_rec_date
                    if len(fields[3]) > 1:
                        fields[3][1] = curr_time_str
                elif isinstance(fields[3], str):
                    parts = fields[3].split(":")
                    if len(parts) > 1:
                        fields[3] = f"{new_rec_date}:{curr_time_str}"
                    else:
                        fields[3] = new_rec_date

            if len(fields) > 4:
                fields[4] = new_rec_ref

            month_str = new_rec_date[4:6] if len(new_rec_date) >= 6 else datetime.datetime.now().strftime("%m")
            if len(fields) > 6 and fields[6]:
                if isinstance(fields[6], str) and len(fields[6]) >= 2:
                    fields[6] = fields[6][:-2] + month_str
                elif isinstance(fields[6], list) and len(fields[6]) > 0:
                    val = str(fields[6][0])
                    if len(val) >= 2:
                        fields[6][0] = val[:-2] + month_str

            new_raw_segments.append(build_segment_string(tag, fields))

        elif tag == "FKT":
            # Change VK in FKT (field 0)
            if len(fields) > 0:
                fields[0] = target_vk
            new_raw_segments.append(build_segment_string(tag, fields))

        elif tag == "REC":
            # Change Rechnungsnummer and Rechnungsdatum
            if len(fields) > 0:
                fields[0] = rec_nr_fields
            if len(fields) > 1:
                fields[1] = new_rec_date
            new_raw_segments.append(build_segment_string(tag, fields))

        elif tag == "GES":
            status_code = fields[0] if len(fields) > 0 else "00"
            if status_code == "00":
                new_raw_segments.append(make_ges_segment("00", total_brutto_file, total_zuzahlung_file))
                written_ges_statuses.add("00")
            else:
                st_brutto = round(brutto_by_status.get(status_code, 0.0), 2)
                st_zuz = round(zuzahlung_by_status.get(status_code, 0.0), 2)
                if st_brutto > 0 or st_zuz > 0:
                    new_raw_segments.append(make_ges_segment(status_code, st_brutto, st_zuz))
                    written_ges_statuses.add(status_code)

        elif tag == "INV":
            in_inv_block = True
            current_inv_belegnr = str(fields[3]) if len(fields) > 3 and fields[3] else ""
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

            if tag in ["EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP"]:
                anzahl = 0.0
                betrag_zuz = 0.0
                if tag == "EHE":
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    betrag_zuz = float(str(fields[5]).replace(",", ".")) if len(fields) > 5 and fields[5] else 0.0
                elif tag == "ENF":
                    anzahl = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag == "EHI":
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag in ["EHK", "EKT", "EHB", "ESP"]:
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    betrag_zuz = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0

                current_inv_zuz_proz += round(anzahl * betrag_zuz, 2)
                inv_block_segments.append((tag, fields))

            elif tag in ["ZHE", "ZHI", "ZHK", "ZKT", "ZHB", "ZSP"]:
                zkz_val = zuzahlungskennzeichen if zuzahlungskennzeichen is not None else ("2" if target_vk == "03" else None)
                if zkz_val is not None and len(fields) > 3:
                    fields[3] = zkz_val
                inv_block_segments.append((tag, fields))

            elif tag == "BES":
                if len(fields) > 3 and fields[3]:
                    current_inv_zuz_pausch = float(str(fields[3]).replace(",", "."))
                else:
                    current_inv_zuz_pausch = 10.0

                clean_belegnr = current_inv_belegnr.lstrip("0") or "0"
                uri_einzel = orig_einzel_nr if (orig_einzel_nr and orig_einzel_nr != "0") else clean_belegnr

                if orig_sammel_nr:
                    orig_rec_composite: Any = [orig_sammel_nr, uri_einzel]
                elif ":" in orig_rec_nr:
                    parts = orig_rec_nr.split(":")
                    orig_rec_composite = [parts[0], parts[1] if (len(parts) > 1 and parts[1] != "0") else clean_belegnr]
                else:
                    orig_rec_composite = [orig_rec_nr, clean_belegnr] if orig_rec_nr else orig_rec_nr

                uri_fields = [
                    orig_ik_le,
                    orig_rec_composite,
                    orig_rec_date,
                    clean_belegnr,
                ]

                if target_vk == "03":
                    tot_zuz = round(current_inv_zuz_proz + current_inv_zuz_pausch, 2)

                    gzf_fields = [
                        ContentHelper.format_decimal(tot_zuz),
                        ContentHelper.format_decimal(current_inv_zuz_proz),
                        ContentHelper.format_decimal(current_inv_zuz_pausch),
                    ]
                    for inv_tag, inv_f in inv_block_segments:
                        if inv_tag == "URI":
                            continue
                        new_raw_segments.append(build_segment_string(inv_tag, inv_f))
                        if inv_tag == "INV":
                            new_raw_segments.append(build_segment_string("URI", uri_fields))

                    new_raw_segments.append(build_segment_string("GZF", gzf_fields))
                    in_inv_block = False
                    inv_block_segments = []
                else:
                    for inv_tag, inv_f in inv_block_segments:
                        if inv_tag == "URI":
                            continue
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

        elif tag == "UNZ":
            if len(fields) > 1:
                fields[1] = new_rec_ref
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
    zuzahlungskennzeichen: Optional[str] = None,
) -> Path:
    """Reads an ESOL file and generates the corrected/demanded ESOL output file."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {input_path}")

    if not output_path:
        if new_rec_nr:
            sammel_nr = new_rec_nr.split(":")[0]
            formatted_nr = sammel_nr.zfill(4) if (sammel_nr.isdigit() and len(sammel_nr) < 4) else sammel_nr
            output_filename = f"ESOL{formatted_nr}"
        else:
            output_filename = f"{input_path.name}_VK{target_vk}"
        output_path = input_path.with_name(output_filename)

    content = input_path.read_text(encoding="iso-8859-15", errors="replace")
    new_content = generate_correction_esol(
        raw_content=content,
        target_vk=target_vk,
        selected_belegnr_list=selected_belegnr_list,
        new_rec_nr=new_rec_nr,
        new_rec_date=new_rec_date,
        zuzahlungskennzeichen=zuzahlungskennzeichen,
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
        choices=["02", "03", "04", "10"],
        help="Verarbeitungskennzeichen: 02 (Nachforderung), 03 (Zuzahlungsforderung), 04 (Korrekturrechnung), 10 (Wiederaufnahme Blankoverordnung)",
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
        "--zuzahlungskennzeichen",
        "-z",
        default=None,
        choices=["0", "1", "2", "3", "4", "5"],
        help="Zuzahlungskennzeichen (0=keine gesetzl. Zuzahlung, 1=befreit, 2=trotz Aufforderung nicht gezahlt, 3=pflichtig, 4=pflichtig zu befreit, 5=befreit zu pflichtig)",
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
            zuzahlungskennzeichen=args.zuzahlungskennzeichen,
        )
        print(f"Korrekturdatei (VKZ {args.type}) erfolgreich erstellt: {res_path}")
    except Exception as e:
        print(f"Fehler bei Erstellung der Korrekturdatei: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
