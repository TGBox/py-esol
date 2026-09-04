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
import verordnung as verordnung_mod


def read_esol_file_text(file_path: Path) -> str:
    """
    Reads an ESOL text file, automatically detecting whether it is encoded in UTF-8
    or ISO-8859-15 / ISO-8859-1 / CP1252 so German umlauts (ä, ö, ü, ß) are always
    displayed and parsed correctly.
    """
    raw_bytes = file_path.read_bytes()
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return raw_bytes.decode("iso-8859-15")
    except UnicodeDecodeError:
        pass
    return raw_bytes.decode("latin-1", errors="replace")


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


def format_date_german(date_str: str) -> str:
    """
    Formats a date string (e.g. YYYYMMDD '19690930') to German format DD.MM.YYYY ('30.09.1969').
    If format is invalid or empty, returns original date_str.
    """
    if not date_str:
        return ""
    s = str(date_str).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}.{s[4:6]}.{s[0:4]}"
    return s


def parse_date_to_iso(date_str: str) -> str:
    """
    Converts a German date string (DD.MM.YYYY or D.M.YYYY) or ISO date (YYYYMMDD) to 8-digit YYYYMMDD format.
    If format is invalid or empty, returns original date_str.
    """
    if not date_str:
        return ""
    s = str(date_str).strip()
    if len(s) == 8 and s.isdigit():
        return s
    if "." in s:
        parts = s.split(".")
        if len(parts) == 3:
            day, month, year = parts[0].zfill(2), parts[1].zfill(2), parts[2].strip()
            if len(year) == 2:
                year = "20" + year
            if len(year) == 4 and day.isdigit() and month.isdigit() and year.isdigit():
                return f"{year}{month}{day}"
    return s


def build_segment_string(tag: str, fields: List[Any]) -> str:
    """Builds a formatted raw EDIFACT segment string from tag and fields."""
    parts = [tag]
    for f in fields:
        if isinstance(f, list):
            parts.append(":".join(str(item) for item in f))
        else:
            parts.append(str(f) if f is not None else "")
    return "+".join(parts) + "'"


def _finalize_beleg(beleg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ergänzt einen fertig eingelesenen Beleg um die aufbereiteten Verordnungsdaten:
    dekodiertes ZHE, gruppierte Behandlungspositionen, Behandlungsübersicht und
    Plausibilitätshinweise. Bestehende Schlüssel bleiben unverändert.
    """
    if not beleg:
        return beleg

    if not beleg.get("verordnung"):
        beleg["verordnung"] = verordnung_mod.leeres_zhe()

    beleg["positionsgruppen"] = verordnung_mod.gruppiere_positionen(beleg.get("positions", []))
    beleg["behandlung"] = verordnung_mod.behandlungsuebersicht(beleg.get("positions", []))
    beleg["verordnung_hinweise"] = verordnung_mod.pruefe_verordnung(beleg)
    return beleg


def parse_esol_belege_summary(raw_content: str) -> List[Dict[str, Any]]:
    """
    Parses an ESOL file content and returns a list of dictionaries with metadata for each Beleg (INV block).
    Includes positions, prices, dates, tariff indicators, co-payments and — since the
    Verordnungs-Anzeige — the fully decoded prescription data (ZHE), diagnoses (DIA),
    approvals (SKZ) and original-invoice references (URI).
    """
    tokenizer = SegmentTokenizer()
    raw_segments = tokenizer.tokenize_segments(raw_content)

    belege = []
    in_inv = False
    current_beleg: Dict[str, Any] = {}
    # Nachrichtenkontext (FKT/REC der laufenden SLLA-Nachricht) — wird jedem Beleg
    # mitgegeben, damit im Verordnungsblatt Kostenträger und Rechnung sichtbar sind.
    ctx: Dict[str, str] = {}

    global_ik = ""
    for raw_seg in raw_segments:
        tag, fields = parse_segment_fields(raw_seg)
        if tag == "UNH":
            msg_type = ""
            if len(fields) > 1:
                raw_t = fields[1]
                msg_type = str(raw_t[0]) if isinstance(raw_t, list) and raw_t else str(raw_t)
            ctx["nachrichtentyp"] = msg_type

        elif tag == "FKT" and not in_inv:
            def _f(i: int) -> str:
                if len(fields) <= i or fields[i] in (None, ""):
                    return ""
                return ":".join(str(x) for x in fields[i]) if isinstance(fields[i], list) else str(fields[i])
            ctx["verarbeitungskennzeichen"] = _f(0)
            ctx["leistungserbringer_ik"] = _f(2)
            ctx["kostentraeger_ik"] = _f(3)
            ctx["krankenkasse_ik"] = _f(4)

        elif tag == "REC" and not in_inv:
            rec0 = fields[0] if len(fields) > 0 else ""
            if isinstance(rec0, list):
                ctx["rechnungsnummer"] = str(rec0[0]) if rec0 else ""
            else:
                ctx["rechnungsnummer"] = str(rec0)
            ctx["rechnungsdatum"] = str(fields[1]) if len(fields) > 1 and fields[1] else ""

        elif tag in ["UNB", "URI"] and fields:
            if tag == "UNB" and len(fields) > 2 and fields[2]:
                global_ik = str(fields[2])
            elif tag == "URI" and len(fields) > 0 and fields[0]:
                global_ik = str(fields[0])

        if tag == "INV":
            if in_inv and current_beleg:
                belege.append(_finalize_beleg(current_beleg))
            in_inv = True
            belegnr = str(fields[3]) if len(fields) > 3 and fields[3] else ""
            vers_nr = str(fields[0]) if len(fields) > 0 and fields[0] else ""
            vers_status = str(fields[1]) if len(fields) > 1 and fields[1] else "00"
            current_beleg = {
                "belegnr": belegnr,
                "versichertennummer": vers_nr,
                "versichertenstatus": vers_status,
                "beleginformation": str(fields[2]) if len(fields) > 2 and fields[2] else "",
                "versorgungsform": str(fields[4]) if len(fields) > 4 and fields[4] else "",
                "nachname": "",
                "vorname": "",
                "geburtstag": "",
                "ik": global_ik,
                "bsnr": "",
                "lanr": "",
                "verordnungsdatum": "",
                "verordnungsart": "",
                "diagnosegruppe": "",
                "icd10": "",
                "leitsymptomatik": "",
                "tarifkennzeichen": "",
                "abrechnungscode": "",
                "zuzahlungskennzeichen": "2",
                "brutto": 0.0,
                "zuzahlung_proz": 0.0,
                "zuzahlung_pausch": 10.0,
                "total_zuzahlung": 0.0,
                "positions": [],
                "raw_segments": [],
                # --- Verordnungsdaten ---
                "verordnung": None,
                "verordnung_segment_tag": "",
                "verordnung_felder": [],
                "diagnosen": [],
                "genehmigung": [],
                "ursprungsrechnung": [],
                "freitexte": [],
                # --- Nachrichtenkontext ---
                "kostentraeger_ik": ctx.get("kostentraeger_ik", ""),
                "krankenkasse_ik": ctx.get("krankenkasse_ik", ""),
                "leistungserbringer_ik": ctx.get("leistungserbringer_ik", ""),
                "verarbeitungskennzeichen": ctx.get("verarbeitungskennzeichen", ""),
                "rechnungsnummer": ctx.get("rechnungsnummer", ""),
                "rechnungsdatum": ctx.get("rechnungsdatum", ""),
            }
            current_beleg["raw_segments"].append((tag, fields))

        elif in_inv:
            current_beleg["raw_segments"].append((tag, fields))
            if tag == "NAD":
                if len(fields) > 0:
                    current_beleg["nachname"] = str(fields[0])
                if len(fields) > 1:
                    current_beleg["vorname"] = str(fields[1])
                if len(fields) > 2:
                    current_beleg["geburtstag"] = str(fields[2])

            elif tag in ["ZHE", "ZHI", "ZHK", "ZHH", "ZKT", "ZHB", "ZSP", "ZUZ", "ZUV"]:
                # Verordnungssegment: Rohfelder immer schema-benannt mitführen, damit
                # auch Leistungsbereiche ohne ZHE (Hilfsmittel, HKP, ...) anzeigbar sind.
                current_beleg["verordnung_segment_tag"] = tag
                current_beleg["verordnung_felder"] = verordnung_mod.segment_field_rows(tag, fields)

                if len(fields) > 0 and fields[0]:
                    current_beleg["bsnr"] = str(fields[0])
                if len(fields) > 1 and fields[1]:
                    current_beleg["lanr"] = str(fields[1])
                if len(fields) > 2 and fields[2]:
                    current_beleg["verordnungsdatum"] = str(fields[2])
                if len(fields) > 3 and fields[3]:
                    current_beleg["zuzahlungskennzeichen"] = str(fields[3])
                if len(fields) > 4 and fields[4]:
                    current_beleg["diagnosegruppe"] = str(fields[4])
                if len(fields) > 5 and fields[5]:
                    current_beleg["verordnungsart"] = str(fields[5])
                if len(fields) > 12 and fields[12]:
                    current_beleg["leitsymptomatik"] = str(fields[12])

                if tag == "ZHE":
                    current_beleg["verordnung"] = verordnung_mod.decode_zhe(fields)

            elif tag == "DIA":
                if len(fields) > 0 and fields[0]:
                    current_beleg["icd10"] = str(fields[0])
                dia_code = str(fields[0]) if len(fields) > 0 and fields[0] else ""
                dia_text = str(fields[1]) if len(fields) > 1 and fields[1] else ""
                if dia_code or dia_text:
                    current_beleg["diagnosen"].append({"code": dia_code, "text": dia_text})

            elif tag == "SKZ":
                current_beleg["genehmigung"].append({
                    "kennzeichen": str(fields[0]) if len(fields) > 0 and fields[0] else "",
                    "datum": str(fields[1]) if len(fields) > 1 and fields[1] else "",
                    "art": str(fields[2]) if len(fields) > 2 and fields[2] else "",
                })

            elif tag == "URI":
                current_beleg["ursprungsrechnung"].append(
                    "+".join(
                        ":".join(str(x) for x in f) if isinstance(f, list) else str(f)
                        for f in fields
                    )
                )

            elif tag == "TXT":
                txt = " ".join(
                    ":".join(str(x) for x in f) if isinstance(f, list) else str(f)
                    for f in fields
                ).strip()
                if txt:
                    current_beleg["freitexte"].append(txt)

            elif tag in ["EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP"]:
                anzahl = 0.0
                betrag_zuz = 0.0
                code = ""
                tarif_kz = ""
                abr_code = ""
                einzelbetrag = 0.0
                datum = ""

                # Code / composite check
                if tag == "ENF":
                    c_field = fields[1] if len(fields) > 1 else ""
                else:
                    c_field = fields[0] if len(fields) > 0 else ""

                if isinstance(c_field, list):
                    abr_code = str(c_field[0]) if len(c_field) > 0 else ""
                    tarif_kz = str(c_field[1]) if len(c_field) > 1 else ""
                else:
                    raw_c = str(c_field)
                    if ":" in raw_c:
                        parts = raw_c.split(":")
                        abr_code = parts[0]
                        tarif_kz = parts[1]
                    else:
                        abr_code = raw_c

                if tarif_kz and not current_beleg.get("tarifkennzeichen"):
                    current_beleg["tarifkennzeichen"] = tarif_kz
                if abr_code and not current_beleg.get("abrechnungscode"):
                    current_beleg["abrechnungscode"] = abr_code

                if tag == "EHE":
                    code = str(fields[1]) if len(fields) > 1 and fields[1] else ""
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzelbetrag = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    datum = str(fields[4]) if len(fields) > 4 and fields[4] else ""
                    betrag_zuz = float(str(fields[5]).replace(",", ".")) if len(fields) > 5 and fields[5] else 0.0
                elif tag == "ENF":
                    code = str(fields[2]) if len(fields) > 2 and fields[2] else ""
                    anzahl = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    einzelbetrag = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                    datum = str(fields[5]) if len(fields) > 5 and fields[5] else ""
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag == "EHI":
                    code = str(fields[1]) if len(fields) > 1 and fields[1] else ""
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzelbetrag = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                    datum = str(fields[5]) if len(fields) > 5 and fields[5] else ""
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag in ["EHK", "ESP"]:
                    code = str(fields[1]) if len(fields) > 1 and fields[1] else ""
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzelbetrag = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                elif tag == "EKT":
                    code = str(fields[1]) if len(fields) > 1 and fields[1] else ""
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzelbetrag = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    datum = str(fields[4]) if len(fields) > 4 and fields[4] else ""
                elif tag == "EHB":
                    code = str(fields[1]) if len(fields) > 1 and fields[1] else ""
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzelbetrag = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0

                current_beleg["zuzahlung_proz"] += round(anzahl * betrag_zuz, 2)
                current_beleg["positions"].append({
                    "id": len(current_beleg["positions"]),
                    "tag": tag,
                    "code": code,
                    "abr_code": abr_code,
                    "tarif_kz": tarif_kz,
                    "datum": datum,
                    "anzahl": anzahl,
                    "einzelbetrag": einzelbetrag,
                    "gesamtbetrag": round(anzahl * einzelbetrag, 2),
                    "zuzahlung": betrag_zuz,
                    "zuzahlung_gesamt": round(anzahl * betrag_zuz, 2),
                    "raw_fields": fields,
                })

            elif tag == "BES":
                if len(fields) > 0 and fields[0]:
                    current_beleg["brutto"] = float(str(fields[0]).replace(",", "."))
                if len(fields) > 3 and fields[3]:
                    current_beleg["zuzahlung_pausch"] = float(str(fields[3]).replace(",", "."))
                current_beleg["total_zuzahlung"] = round(
                    current_beleg["zuzahlung_proz"] + current_beleg["zuzahlung_pausch"], 2
                )
                belege.append(_finalize_beleg(current_beleg))
                in_inv = False
                current_beleg = {}

    if in_inv and current_beleg:
        belege.append(_finalize_beleg(current_beleg))

    return belege


def _get_beleg_mod(belegnr: str, mods: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Helper to retrieve beleg modifications matching belegnr regardless of leading zeros."""
    if not mods or not belegnr:
        return None
    if belegnr in mods:
        return mods[belegnr]
    clean_nr = belegnr.lstrip("0") or "0"
    if clean_nr in mods:
        return mods[clean_nr]
    for k, v in mods.items():
        if k.lstrip("0") == clean_nr:
            return v
    return None


def generate_correction_esol(
    raw_content: str,
    target_vk: str = "03",  # "02" Nachforderung, "03" Zuzahlungsforderung, "04" Korrekturrechnung
    selected_belegnr_list: Optional[List[str]] = None,
    new_rec_nr: Optional[str] = None,
    new_rec_date: Optional[str] = None,
    zuzahlungskennzeichen: Optional[str] = None,
    beleg_modifications: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generates a new ESOL content string with target VKZ (02, 03, 04) from original raw ESOL content.
    Optionally filters output to include only specified Belegnummern and applies beleg_modifications.
    """
    tokenizer = SegmentTokenizer()
    raw_segments = tokenizer.tokenize_segments(raw_content)

    if not raw_segments:
        raise ValueError("Datei enthält keine gültigen EDIFACT-Segmente.")

    today_str = datetime.datetime.now().strftime("%Y%m%d")
    if not new_rec_date:
        new_rec_date = today_str

    selected_set = set(selected_belegnr_list) if selected_belegnr_list else None
    mods = beleg_modifications or {}

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
    current_inv_brutto_p1 = 0.0
    current_belegnr_p1 = ""

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
            current_belegnr_p1 = str(fields[3]) if len(fields) > 3 and fields[3] else ""
            vers_status = str(fields[1]) if len(fields) > 1 and fields[1] else "00"
            st_prefix2 = vers_status[:2] if len(vers_status) >= 2 else "00"
            st_prefix1 = vers_status[:1] if len(vers_status) >= 1 else "0"

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

            keep_block_p1 = (selected_set is None) or (current_belegnr_p1 in selected_set)
            current_inv_zuz_proz_p1 = 0.0
            current_inv_zuz_pausch_p1 = 0.0
            current_inv_brutto_p1 = 0.0

        elif in_inv_block_p1:
            b_mod = _get_beleg_mod(current_belegnr_p1, mods)
            if keep_block_p1 and b_mod and "positions" in b_mod:
                # Calculate totals from modified positions
                if tag == "BES":
                    mod_positions = b_mod["positions"]
                    mod_brutto = sum(round(p.get("anzahl", 0.0) * p.get("einzelbetrag", 0.0), 2) for p in mod_positions)
                    mod_zuz_proz = sum(round(p.get("anzahl", 0.0) * p.get("zuzahlung", 0.0), 2) for p in mod_positions)
                    zkz = str(b_mod.get("zuzahlungskennzeichen", "2"))
                    if zkz in ["0", "1"]:
                        mod_zuz_pausch = 0.0
                    elif "zuzahlung_pausch" in b_mod:
                        mod_zuz_pausch = float(b_mod["zuzahlung_pausch"])
                    elif len(fields) > 3 and fields[3]:
                        mod_zuz_pausch = float(str(fields[3]).replace(",", "."))
                    else:
                        mod_zuz_pausch = b_mod.get("zuzahlung_pausch", 10.0)

                    brutto_by_status[current_ges_code_p1] = round(
                        brutto_by_status.get(current_ges_code_p1, 0.0) + mod_brutto, 2
                    )
                    inv_zuz = round(mod_zuz_proz + mod_zuz_pausch, 2)
                    zuzahlung_by_status[current_ges_code_p1] = round(
                        zuzahlung_by_status.get(current_ges_code_p1, 0.0) + inv_zuz, 2
                    )
                    in_inv_block_p1 = False
                continue

            if keep_block_p1 and tag in ["EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP"]:
                anzahl = 0.0
                betrag_zuz = 0.0
                einzel = 0.0
                if tag == "EHE":
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzel = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[5]).replace(",", ".")) if len(fields) > 5 and fields[5] else 0.0
                elif tag == "ENF":
                    anzahl = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    einzel = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag == "EHI":
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzel = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                    betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                elif tag in ["EHK", "EKT", "EHB", "ESP"]:
                    anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                    einzel = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                    betrag_zuz = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                current_inv_brutto_p1 += round(anzahl * einzel, 2)
                current_inv_zuz_proz_p1 += round(anzahl * betrag_zuz, 2)

            elif tag == "BES":
                if keep_block_p1:
                    brutto_val = float(str(fields[0]).replace(",", ".")) if (len(fields) > 0 and fields[0]) else current_inv_brutto_p1
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
                        if len(fields) > 3 and fields[3]:
                            current_inv_zuz_pausch_p1 = float(str(fields[3]).replace(",", "."))
                        else:
                            current_inv_zuz_pausch_p1 = 10.0
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
    clean_ref = "".join([c for c in str(new_sammel_nr) if c.isdigit()])
    new_rec_ref = clean_ref.zfill(5) if clean_ref else "00001"

    new_raw_segments = []
    in_inv_block = False
    keep_block = False
    current_inv_belegnr = ""
    current_inv_zuz_proz = 0.0
    current_inv_zuz_pausch = 0.0
    current_inv_brutto = 0.0
    inv_block_segments: List[Tuple[str, List[Any]]] = []
    written_ges_statuses = set()
    positions_inserted = False

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

    def format_pos_segment(pos: Dict[str, Any]) -> Tuple[str, List[Any]]:
        tag = pos.get("tag", "EHE")
        abr_code = str(pos.get("abr_code") or "26")
        code = str(pos.get("code", "59702"))
        tarif_kz = str(pos.get("tarif_kz", "00501"))
        datum = str(pos.get("datum", datetime.datetime.now().strftime("%Y%m%d")))
        anzahl = float(pos.get("anzahl", 1.0))
        einzel = float(pos.get("einzelbetrag", 0.0))
        zuz = float(pos.get("zuzahlung", 0.0))

        code_val: Any = [abr_code, tarif_kz] if tarif_kz else abr_code

        if tag == "EHE":
            fields: List[Any] = [
                code_val,
                code,
                ContentHelper.format_decimal(anzahl),
                ContentHelper.format_decimal(einzel),
                datum,
                ContentHelper.format_decimal(zuz),
            ]
        elif tag == "ENF":
            v_kz = str(pos.get("verordnungskz") or "01")
            fields = [
                v_kz,
                code_val,
                code,
                ContentHelper.format_decimal(anzahl),
                ContentHelper.format_decimal(einzel),
                datum,
                ContentHelper.format_decimal(zuz),
            ]
        elif tag == "EHI":
            fields = [
                code_val,
                code,
                ContentHelper.format_decimal(anzahl),
                "",  # Mengeneinheit (optional)
                ContentHelper.format_decimal(einzel),
                datum,
                ContentHelper.format_decimal(zuz),
            ]
        elif tag == "EKT":
            fields = [
                code_val,
                code,
                ContentHelper.format_decimal(anzahl),
                ContentHelper.format_decimal(einzel),
                datum,
            ]
        else:  # EHK, EHB, ESP
            fields = [
                code_val,
                code,
                ContentHelper.format_decimal(anzahl),
                ContentHelper.format_decimal(einzel),
                ContentHelper.format_decimal(zuz),
            ]
        return tag, fields

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
            if len(fields) > 0:
                fields[0] = target_vk
            new_raw_segments.append(build_segment_string(tag, fields))

        elif tag == "REC":
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
            current_inv_brutto = 0.0
            positions_inserted = False

        elif in_inv_block:
            if not keep_block:
                if tag == "BES":
                    in_inv_block = False
                    inv_block_segments = []
                continue

            b_mod = _get_beleg_mod(current_inv_belegnr, mods)

            # Insert modified position segments at correct EDIFACT segment location (before ZHE / DIA / BES)
            if b_mod and "positions" in b_mod and not positions_inserted:
                if tag in ["ZHE", "ZHI", "ZHK", "ZKT", "ZHB", "ZSP", "DIA", "BES"] or tag in [
                    "EHE",
                    "ENF",
                    "EHI",
                    "EHK",
                    "EKT",
                    "EHB",
                    "ESP",
                ]:
                    current_inv_brutto = 0.0
                    current_inv_zuz_proz = 0.0
                    for pos in b_mod["positions"]:
                        p_tag, p_fields = format_pos_segment(pos)
                        inv_block_segments.append((p_tag, p_fields))
                        p_anz = float(pos.get("anzahl", 0.0))
                        p_einzel = float(pos.get("einzelbetrag", 0.0))
                        p_zuz = float(pos.get("zuzahlung", 0.0))
                        current_inv_brutto += round(p_anz * p_einzel, 2)
                        current_inv_zuz_proz += round(p_anz * p_zuz, 2)
                    positions_inserted = True

            if tag in ["ZHE", "ZHI", "ZHK", "ZKT", "ZHB", "ZSP"]:
                zkz_val = (
                    b_mod.get("zuzahlungskennzeichen")
                    if (b_mod and "zuzahlungskennzeichen" in b_mod)
                    else (zuzahlungskennzeichen if zuzahlungskennzeichen is not None else ("2" if target_vk == "03" else None))
                )
                if zkz_val is not None and len(fields) > 3:
                    fields[3] = zkz_val
                inv_block_segments.append((tag, fields))

            elif tag in ["EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP"]:
                if b_mod and "positions" in b_mod:
                    # Skip original position segments as modified positions have already been inserted above
                    pass
                else:
                    anzahl = 0.0
                    betrag_zuz = 0.0
                    einzel = 0.0
                    if tag == "EHE":
                        anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                        einzel = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                        betrag_zuz = float(str(fields[5]).replace(",", ".")) if len(fields) > 5 and fields[5] else 0.0
                    elif tag == "ENF":
                        anzahl = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                        einzel = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                        betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                    elif tag == "EHI":
                        anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                        einzel = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0
                        betrag_zuz = float(str(fields[6]).replace(",", ".")) if len(fields) > 6 and fields[6] else 0.0
                    elif tag in ["EHK", "EKT", "EHB", "ESP"]:
                        anzahl = float(str(fields[2]).replace(",", ".")) if len(fields) > 2 and fields[2] else 0.0
                        einzel = float(str(fields[3]).replace(",", ".")) if len(fields) > 3 and fields[3] else 0.0
                        betrag_zuz = float(str(fields[4]).replace(",", ".")) if len(fields) > 4 and fields[4] else 0.0

                    current_inv_brutto += round(anzahl * einzel, 2)
                    current_inv_zuz_proz += round(anzahl * betrag_zuz, 2)

                    if b_mod and "tarifkennzeichen" in b_mod:
                        # Override tariff code in composite field
                        c_f = fields[0]
                        if isinstance(c_f, list) and len(c_f) > 1:
                            c_f[1] = str(b_mod["tarifkennzeichen"])
                        elif isinstance(c_f, str) and ":" in c_f:
                            parts = c_f.split(":")
                            fields[0] = [parts[0], str(b_mod["tarifkennzeichen"])]

                    inv_block_segments.append((tag, fields))

            elif tag == "BES":
                # Ursprüngliche Belegnummer (URI-Feld 4) unverändert aus dem Original
                # übernehmen — führende Nullen dürfen NICHT entfernt werden
                # (Rückmeldung der Abrechnungszentren).
                uri_belegnr = current_inv_belegnr

                # Für die Einzel-Rechnungsnummer im Composite (URI-Feld 2, Teil 2)
                # dient die Belegnummer nur als Rückfall, wenn das Original keine
                # Einzel-Rechnungsnummer führt. Dort bleibt die gekürzte Form, weil
                # das Feld eine Rechnungs- und keine Belegnummer ist (max. 6 Zeichen).
                fallback_einzel_nr = current_inv_belegnr.lstrip("0") or "0"
                uri_einzel = orig_einzel_nr if (orig_einzel_nr and orig_einzel_nr != "0") else fallback_einzel_nr

                if orig_sammel_nr:
                    orig_rec_composite: Any = [orig_sammel_nr, uri_einzel]
                elif ":" in orig_rec_nr:
                    parts = orig_rec_nr.split(":")
                    orig_rec_composite = [
                        parts[0],
                        parts[1] if (len(parts) > 1 and parts[1] != "0") else fallback_einzel_nr,
                    ]
                else:
                    orig_rec_composite = [orig_rec_nr, fallback_einzel_nr] if orig_rec_nr else orig_rec_nr

                uri_fields = [
                    orig_ik_le,
                    orig_rec_composite,
                    orig_rec_date,
                    uri_belegnr,
                ]

                zkz = str(b_mod.get("zuzahlungskennzeichen", "2")) if b_mod else "2"
                if zkz in ["0", "1"]:
                    current_inv_zuz_pausch = 0.0
                elif b_mod and "zuzahlung_pausch" in b_mod:
                    current_inv_zuz_pausch = float(b_mod["zuzahlung_pausch"])
                elif len(fields) > 3 and fields[3]:
                    current_inv_zuz_pausch = float(str(fields[3]).replace(",", "."))
                else:
                    current_inv_zuz_pausch = 10.0

                if len(fields) > 0:
                    fields[0] = ContentHelper.format_decimal(current_inv_brutto)

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
                    tot_zuz = round(current_inv_zuz_proz + current_inv_zuz_pausch, 2)
                    if len(fields) > 0:
                        fields[0] = ContentHelper.format_decimal(current_inv_brutto)
                    if len(fields) > 1:
                        fields[1] = ContentHelper.format_decimal(tot_zuz)
                    if len(fields) > 2:
                        fields[2] = ContentHelper.format_decimal(current_inv_zuz_proz)
                    if len(fields) > 3:
                        fields[3] = ContentHelper.format_decimal(current_inv_zuz_pausch)

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
    out_dir: Optional[Path] = None,
    beleg_modifications: Optional[Dict[str, Any]] = None,
    content_override: Optional[str] = None,
) -> Path:
    """
    Reads an ESOL file and generates the corrected/demanded ESOL output file.

    content_override: Wird dieser Text übergeben, so wird er unverändert
    geschrieben statt neu generiert. Das braucht der Korrektur-Editor, wenn der
    Anwender die Vorschau von Hand nachbearbeitet hat — die Namens- und
    Ablagelogik bleibt dadurch an einer Stelle.
    """
    if not input_path.is_file():
        raise FileNotFoundError(f"Datei nicht gefunden: {input_path}")

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        if new_rec_nr:
            sammel_nr = new_rec_nr.split(":")[0]
            formatted_nr = sammel_nr.zfill(4) if (sammel_nr.isdigit() and len(sammel_nr) < 4) else sammel_nr
            output_filename = f"ESOL{formatted_nr}"
        else:
            output_filename = f"{input_path.name}_VK{target_vk}"
        output_path = out_dir / output_filename
    elif not output_path:
        if new_rec_nr:
            sammel_nr = new_rec_nr.split(":")[0]
            formatted_nr = sammel_nr.zfill(4) if (sammel_nr.isdigit() and len(sammel_nr) < 4) else sammel_nr
            output_filename = f"ESOL{formatted_nr}"
        else:
            output_filename = f"{input_path.name}_VK{target_vk}"
        output_path = input_path.with_name(output_filename)

    if content_override is not None:
        new_content = content_override
    else:
        content = read_esol_file_text(input_path)
        new_content = generate_correction_esol(
            raw_content=content,
            target_vk=target_vk,
            selected_belegnr_list=selected_belegnr_list,
            new_rec_nr=new_rec_nr,
            new_rec_date=new_rec_date,
            zuzahlungskennzeichen=zuzahlungskennzeichen,
            beleg_modifications=beleg_modifications,
        )
    output_path.write_text(new_content, encoding="iso-8859-15")
    return output_path


def pruefe_iso_8859_15(text: str) -> List[Tuple[int, int, str]]:
    """
    Findet Zeichen, die sich nicht in ISO-8859-15 schreiben lassen.
    Rückgabe: Liste aus (Zeile, Spalte, Zeichen) — jeweils 1-basiert.

    Wird gebraucht, bevor eine von Hand bearbeitete Fassung gespeichert wird:
    Text aus Word oder Outlook bringt oft typografische Anführungszeichen oder
    Gedankenstriche mit, die ISO-8859-15 nicht kennt.
    """
    treffer: List[Tuple[int, int, str]] = []
    for zeilen_nr, zeile in enumerate(text.splitlines(), start=1):
        for spalte, zeichen in enumerate(zeile, start=1):
            try:
                zeichen.encode("iso-8859-15")
            except UnicodeEncodeError:
                treffer.append((zeilen_nr, spalte, zeichen))
    return treffer


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
        "--out-dir",
        "-o",
        default=None,
        help="Zielverzeichnis für generierte Korrekturdatei",
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
            out_dir=Path(args.out_dir) if args.out_dir else None,
        )
        print(f"Korrekturdatei (VKZ {args.type}) erfolgreich erstellt: {res_path}")
    except Exception as e:
        print(f"Fehler bei Erstellung der Korrekturdatei: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
