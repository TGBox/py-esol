"""
ESOL Support Helper — Übersetzung von Validierungsfehlern, Hotline-Handlungsempfehlungen,
Ticket-Zusammenfassungen und EDIFACT-Klartext-Baumdarstellung.
"""

import datetime
import html
from typing import Any, Dict, List, Optional, Tuple

from tools.generate_correction import format_date_german, parse_esol_belege_summary, parse_segment_fields, read_esol_file_text
from parser.segment_tokenizer import SegmentTokenizer


# Mapping von Regel-IDs/Schlüsselbegriffen zu lesbaren Erklärungen und Hotline-Handlungen
ERROR_TRANSLATION_MAP: Dict[str, Dict[str, str]] = {
    "R_FKT_01": {
        "title": "Verarbeitungskennzeichen ungültig",
        "explanation": "Das Verarbeitungskennzeichen (FKT) entspricht nicht den Vorgaben für Erstabrechnung oder Korrektur.",
        "action": "Kunden bitten, den Abrechnungstyp (Erstabrechnung VK 01, Nachforderung VK 02/03, Korrektur VK 04) in den Stammdaten zu überprüfen.",
    },
    "R_IK_01": {
        "title": "Institutionskennzeichen (IK) Prüfziffer fehlerhaft",
        "explanation": "Das Institutionskennzeichen (IK) der Krankenkasse oder des Leistungserbringers hat einen Tippfehler oder ungültige Prüfziffer.",
        "action": "IK des Kostenträgers oder Leistungserbringers in den Kundenstammdaten auf Tippfehler prüfen und korrigieren.",
    },
    "R_GES_01": {
        "title": "Gesamtsummen-Abweichung (GES)",
        "explanation": "Die im GES-Segment angegebene Rechnungs- oder Zuzahlungssumme stimmt nicht mit der Summe der Einzelbelege (BES) überein.",
        "action": "Datei im Korrektur-Editor öffnen oder Rechnungsbeträge/Zuzahlungen neu berechnen lassen.",
    },
    "R_ZHE_01": {
        "title": "Zuzahlungskennzeichen widersprüchlich",
        "explanation": "Der Patient ist als zuzahlungsbefreit gekennzeichnet, es wurden jedoch Zuzahlungsbeträge berechnet (oder umgekehrt).",
        "action": "Zuzahlungsstatus (befreit / pflichtig) auf dem Rezept prüfen und im Beleg-Editor anpassen.",
    },
    "R_DATE_LOGIC": {
        "title": "Unplausibles Datum",
        "explanation": "Das Behandlungsdatum liegt nach dem Rechnungsdatum oder das Verordnungsdatum liegt in der Zukunft.",
        "action": "Behandlungs- und Verordnungsdaten im Rezept-Formular auf Tippfehler prüfen.",
    },
    "R_SEG_SYNTAX": {
        "title": "Syntaxfehler in EDIFACT-Segment",
        "explanation": "Ein Segment enthält eine ungültige Anzahl an Feldern oder fehlerhafte Trennzeichen.",
        "action": "Segmentaufbau prüfen oder Datei über 'UTF-8 -> ISO' erneut konvertieren.",
    },
}

# Standard-Fallback für unbekannte Fehler
DEFAULT_ERROR_TRANSLATION: Dict[str, str] = {
    "title": "Technische Validierungsauffälligkeit",
    "explanation": "Eine Segment- oder Inhaltsregel wurde verletzt.",
    "action": "Die betroffene Belegnummer und Fehlermeldung prüfen und gegebenenfalls im Korrektur-Editor anpassen.",
}


def translate_error(error_msg: str) -> Dict[str, str]:
    """
    Übersetzt eine technische Fehlermeldung in verständlichen Klartext mit Hotline-Handlungsempfehlung.
    """
    if not error_msg:
        return DEFAULT_ERROR_TRANSLATION

    msg_upper = error_msg.upper()

    for key, data in ERROR_TRANSLATION_MAP.items():
        if key in msg_upper:
            return data

    if " IK" in f" {msg_upper}" or "INSTITUTION" in msg_upper:
        return ERROR_TRANSLATION_MAP["R_IK_01"]
    if "GES" in msg_upper or "SUMME" in msg_upper or "BETRAG" in msg_upper:
        return ERROR_TRANSLATION_MAP["R_GES_01"]
    if "ZUZ" in msg_upper or "BEFREI" in msg_upper or "ZHE" in msg_upper:
        return ERROR_TRANSLATION_MAP["R_ZHE_01"]
    if "DATUM" in msg_upper or "DATE" in msg_upper:
        return ERROR_TRANSLATION_MAP["R_DATE_LOGIC"]

    # Generischer Rückfallwert mit der Originalmeldung
    return {
        "title": "Validierungsfehler",
        "explanation": f"Technischer Detailfehler: {error_msg}",
        "action": "Prüfen Sie die Belegdaten oder wenden Sie sich an die Second-Level-Entwicklung.",
    }


def generate_ticket_summary(file_name: str, validation_errors: List[str], belege_summary: List[Dict[str, Any]]) -> str:
    """
    Generiert eine strukturierte Text-Zusammenfassung für Ticketsysteme (z. B. Jira, ServiceNow, Hotline-Notes).
    """
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    total_belege = len(belege_summary)
    total_brutto = sum(b.get("brutto", 0.0) for b in belege_summary)
    total_zuzahlung = sum(b.get("total_zuzahlung", 0.0) for b in belege_summary)

    lines = [
        "==================================================",
        "          ESOL SUPPORT-TICKET BERICHT             ",
        "==================================================",
        f"Erstellt am:        {now_str}",
        f"Quelldatei:         {file_name}",
        f"Anzahl Belege:      {total_belege}",
        f"Gesamtsumme Brutto: {total_brutto:.2f} €".replace(".", ","),
        f"Gesamte Zuzahlung:  {total_zuzahlung:.2f} €".replace(".", ","),
        f"Status:             {'⚠️ FEHLERHAFT' if validation_errors else '✅ GÜLTIG'}",
        "--------------------------------------------------",
    ]

    if validation_errors:
        lines.append("\n[AUFGETRETENE FEHLER & HANDLUNGSEMPFEHLUNGEN]")
        for idx, err in enumerate(validation_errors, start=1):
            trans = translate_error(err)
            lines.append(f"\nFehler #{idx}: {trans['title']}")
            lines.append(f"  Technical Log: {err}")
            lines.append(f"  Was ist passiert? {trans['explanation']}")
            lines.append(f"  👉 Was ist zu tun? {trans['action']}")
    else:
        lines.append("\nKeine Validierungsfehler festgestellt. Die Datei entspricht allen geprüften Richtlinien.")

    if belege_summary:
        lines.append("\n--------------------------------------------------")
        lines.append("[BELEG-ÜBERSICHT]")
        for b in belege_summary:
            b_nr = b.get("belegnr", "-")
            name = f"{b.get('nachname', '')}, {b.get('vorname', '')}".strip(", ")
            brutto = f"{b.get('brutto', 0.0):.2f} €".replace(".", ",")
            zuz = f"{b.get('total_zuzahlung', 0.0):.2f} €".replace(".", ",")
            lines.append(f"- Beleg-Nr. {b_nr} | Patient: {name} | Brutto: {brutto} | Zuzahlung: {zuz}")

    lines.append("\n==================================================")
    return "\n".join(lines)


def generate_html_report(file_name: str, validation_errors: List[str], belege_summary: List[Dict[str, Any]]) -> str:
    """
    Erstellt einen eigenständigen, formatierten HTML-Prüfbericht.
    """
    now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    total_belege = len(belege_summary)
    total_brutto = sum(b.get("brutto", 0.0) for b in belege_summary)
    total_zuzahlung = sum(b.get("total_zuzahlung", 0.0) for b in belege_summary)
    status_class = "error" if validation_errors else "success"
    status_text = "FEHLERHAFT" if validation_errors else "GÜLTIG"

    errors_html = ""
    if validation_errors:
        errors_html += "<h2>Aufgetretene Fehler &amp; Handlungsempfehlungen</h2>"
        for err in validation_errors:
            trans = translate_error(err)
            errors_html += f"""
            <div class="error-card">
                <h3>⚠️ {html.escape(trans['title'])}</h3>
                <p><strong>Log:</strong> <code>{html.escape(err)}</code></p>
                <p><strong>Ursache:</strong> {html.escape(trans['explanation'])}</p>
                <p class="action-box"><strong>👉 Was ist zu tun?</strong> {html.escape(trans['action'])}</p>
            </div>
            """

    table_rows = ""
    for b in belege_summary:
        b_nr = html.escape(str(b.get("belegnr", "-")))
        name = html.escape(f"{b.get('nachname', '')}, {b.get('vorname', '')}".strip(", "))
        brutto = f"{b.get('brutto', 0.0):.2f} €".replace(".", ",")
        zuz = f"{b.get('total_zuzahlung', 0.0):.2f} €".replace(".", ",")
        table_rows += f"<tr><td>{b_nr}</td><td>{name}</td><td>{brutto}</td><td>{zuz}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<title>ESOL Prüfbericht - {html.escape(file_name)}</title>
<style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; color: #333; margin: 20px; }}
    .container {{ max-width: 950px; margin: 0 auto; background: #fff; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
    h1 {{ color: #1a365d; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; }}
    .kpi-grid {{ display: flex; gap: 15px; margin: 20px 0; }}
    .kpi-card {{ flex: 1; background: #edf2f7; padding: 15px; border-radius: 6px; text-align: center; }}
    .kpi-card .num {{ font-size: 20px; font-weight: bold; color: #2b6cb0; margin-top: 5px; }}
    .status-badge {{ display: inline-block; padding: 6px 12px; border-radius: 4px; font-weight: bold; color: #fff; }}
    .status-badge.error {{ background-color: #e53e3e; }}
    .status-badge.success {{ background-color: #38a169; }}
    .error-card {{ background: #fff5f5; border-left: 4px solid #e53e3e; padding: 12px; margin-bottom: 15px; border-radius: 4px; }}
    .action-box {{ background: #feebc8; padding: 8px; border-radius: 4px; color: #744210; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
    th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
    th {{ background-color: #ebf8ff; color: #2c5282; }}
</style>
</head>
<body>
<div class="container">
    <h1>📄 ESOL Support &amp; Prüfbericht</h1>
    <p><strong>Quelldatei:</strong> {html.escape(file_name)} | <strong>Erstellt am:</strong> {now_str}</p>
    <p>Status: <span class="status-badge {status_class}">{status_text}</span></p>

    <div class="kpi-grid">
        <div class="kpi-card"><div>Belege</div><div class="num">{total_belege}</div></div>
        <div class="kpi-card"><div>Gesamtsumme</div><div class="num">{total_brutto:.2f} €</div></div>
        <div class="kpi-card"><div>Gesamte Zuzahlung</div><div class="num">{total_zuzahlung:.2f} €</div></div>
    </div>

    {errors_html}

    <h2>Belegübersicht</h2>
    <table>
        <thead>
            <tr><th>Belegnummer</th><th>Versicherter</th><th>Brutto (€)</th><th>Zuzahlung (€)</th></tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
</div>
</body>
</html>
"""


# Fachübersetzung von EDIFACT Segmenten für den Rezept-Baum
_SEGMENT_LABEL_MAP: Dict[str, str] = {
    "UNB": "Nachrichten-Kopfsegment (UNB)",
    "UNH": "Nachrichten-Header (UNH)",
    "FKT": "Funktionsschlüssel / Abrechnungsverfahren (FKT)",
    "REC": "Rechnungsdaten (REC)",
    "GES": "Gesamtsumme nach Status (GES)",
    "NAM": "Praxis- / Dienstleister-Name (NAM)",
    "INV": "Rezept / Abrechnungsbeleg (INV)",
    "URI": "Ursprungsrechnung-Referenz (URI)",
    "NAD": "Versichertendaten (NAD)",
    "ZHE": "Zuzahlungs- & Verordnungskennzeichen (ZHE)",
    "EHE": "Einzelheilleistung / Heilmittel (EHE)",
    "ENF": "Hausbesuch / Nebenkosten (ENF)",
    "EHI": "Zusatzleistung (EHI)",
    "EHK": "Kurzzeitpflege-Leistung (EHK)",
    "EKT": "Fahrkosten (EKT)",
    "EHB": "Hausbesuchspauschale (EHB)",
    "ESP": "Sonderleistung (ESP)",
    "DIA": "Diagnose ICD-10 (DIA)",
    "BES": "Belegsumme & Zuzahlung (BES)",
    "UNT": "Nachrichten-Trailer (UNT)",
    "UNZ": "Nutzdaten-Trailer (UNZ)",
}


def parse_esol_tree_nodes(raw_content: str) -> List[Dict[str, Any]]:
    """
    Parst den ESOL-Inhalt in eine hierarchische Datenstruktur für den Rezept-Baum.
    """
    tokenizer = SegmentTokenizer()
    raw_segments = tokenizer.tokenize_segments(raw_content)

    tree: List[Dict[str, Any]] = []
    current_inv_node: Optional[Dict[str, Any]] = None

    for idx, raw_seg in enumerate(raw_segments):
        tag, fields = parse_segment_fields(raw_seg)
        if not tag:
            continue

        label = _SEGMENT_LABEL_MAP.get(tag, f"Segment ({tag})")
        details = []

        if tag == "UNB":
            if len(fields) > 1:
                details.append(f"Absender/Empfänger: {fields[1]}")
            if len(fields) > 3:
                details.append(f"Datum/Zeit: {fields[3]}")
        elif tag == "FKT":
            if len(fields) > 0:
                details.append(f"Verarbeitungskennzeichen: VK {fields[0]}")
            if len(fields) > 2:
                details.append(f"IK Kostenträger: {fields[2]}")
        elif tag == "REC":
            if len(fields) > 0:
                details.append(f"Rechnungsnummer: {fields[0]}")
            if len(fields) > 1:
                details.append(f"Rechnungsdatum: {format_date_german(str(fields[1]))}")
        elif tag == "INV":
            belegnr = str(fields[3]) if len(fields) > 3 else ""
            versnr = str(fields[0]) if len(fields) > 0 else ""
            details.append(f"Beleg-Nr: {belegnr}")
            details.append(f"Versicherten-Nr: {versnr}")
        elif tag == "NAD":
            nachname = str(fields[0]) if len(fields) > 0 else ""
            vorname = str(fields[1]) if len(fields) > 1 else ""
            geb = format_date_german(str(fields[2])) if len(fields) > 2 else ""
            details.append(f"Name: {nachname}, {vorname}")
            if geb:
                details.append(f"Geburtsdatum: {geb}")
        elif tag in ["EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP"]:
            code = ""
            anzahl = ""
            preis = ""
            if tag == "EHE":
                code = str(fields[1]) if len(fields) > 1 else ""
                anzahl = str(fields[2]) if len(fields) > 2 else ""
                preis = str(fields[3]) if len(fields) > 3 else ""
            details.append(f"Code: {code} | Menge: {anzahl} | Preis: {preis} €")
        elif tag == "BES":
            if len(fields) > 0:
                details.append(f"Brutto: {fields[0]} €")
            if len(fields) > 1:
                details.append(f"Gesamt-Zuzahlung: {fields[1]} €")

        node = {
            "id": str(idx),
            "tag": tag,
            "label": label,
            "raw": raw_seg.strip(),
            "details": " | ".join(details),
            "children": [],
        }

        if tag == "INV":
            current_inv_node = node
            tree.append(node)
        elif current_inv_node and tag in ["NAD", "ZHE", "EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP", "DIA", "BES", "URI"]:
            current_inv_node["children"].append(node)
        else:
            tree.append(node)

    return tree
