"""
ESOL Support Helper — Übersetzung von Validierungsfehlern, Hotline-Handlungsempfehlungen,
Ticket-Zusammenfassungen und EDIFACT-Klartext-Baumdarstellung.
"""

import datetime
import html
from typing import Any, Dict, List, Optional, Tuple

import codelisten
import verordnung as vo
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
        lines.append("[VERORDNUNGS-ÜBERSICHT]")
        for b in belege_summary:
            b_nr = b.get("belegnr", "-")
            name = f"{b.get('nachname', '')}, {b.get('vorname', '')}".strip(", ")
            brutto = f"{b.get('brutto', 0.0):.2f} €".replace(".", ",")
            zuz = f"{b.get('total_zuzahlung', 0.0):.2f} €".replace(".", ",")
            lines.append(f"\n- Beleg-Nr. {b_nr} | Patient: {name} | Brutto: {brutto} | Zuzahlung: {zuz}")
            for zeile in vo.verordnung_textzeilen(b):
                lines.append(f"    {zeile}")
            for h in b.get("verordnung_hinweise") or []:
                lines.append(f"    ! [{h.get('stufe', 'info').upper()}] {h.get('text', '')}")

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

        z = b.get("verordnung") or {}
        vo_datum = html.escape(z.get("verordnungsdatum_text", "—") if not z.get("fehlt") else "—")
        vo_art = html.escape(str(z.get("verordnungsart", "") or "—"))
        vo_grp = html.escape(str(z.get("diagnosegruppe", "") or "—"))
        arzt = html.escape(z.get("arzt_text", "—") if not z.get("fehlt") else "—")
        dia = html.escape("; ".join(d.get("code", "") for d in (b.get("diagnosen") or [])) or "—")
        ub = b.get("behandlung") or {}
        zeitraum = html.escape(str(ub.get("zeitraum_text", "—")))
        tage = ub.get("anzahl_behandlungstage", 0)

        hinweise = b.get("verordnung_hinweise") or []
        hint_html = ""
        if hinweise:
            items = "".join(
                f"<li class=\"h-{html.escape(h.get('stufe', 'info'))}\">{html.escape(h.get('text', ''))}</li>"
                for h in hinweise
            )
            hint_html = f'<tr class="hinweis-row"><td colspan="9"><ul class="hinweise">{items}</ul></td></tr>'

        table_rows += (
            f"<tr><td>{b_nr}</td><td>{name}</td><td>{vo_datum}</td><td>{vo_art}</td>"
            f"<td>{vo_grp}</td><td>{dia}</td><td class=\"nowrap\">{arzt}</td>"
            f"<td class=\"num\">{brutto}</td><td class=\"num\">{zuz}</td></tr>"
            f"<tr class=\"sub\"><td></td><td colspan=\"8\">Behandlung: {zeitraum} "
            f"({tage} Behandlungstage)</td></tr>"
            f"{hint_html}"
        )

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
    table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 13px; }}
    th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
    th {{ background-color: #ebf8ff; color: #2c5282; }}
    td.num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
    td.nowrap {{ white-space: nowrap; }}
    tr.sub td {{ border-bottom: none; padding-top: 0; color: #718096; font-size: 12px; }}
    tr.hinweis-row td {{ padding-top: 0; }}
    ul.hinweise {{ margin: 0 0 6px 0; padding-left: 18px; font-size: 12px; }}
    ul.hinweise li.h-fehler {{ color: #c53030; font-weight: 600; }}
    ul.hinweise li.h-warnung {{ color: #b7791f; }}
    ul.hinweise li.h-info {{ color: #4a5568; }}
    .tablewrap {{ overflow-x: auto; }}
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

    <h2>Verordnungs- &amp; Belegübersicht</h2>
    <div class="tablewrap">
    <table>
        <thead>
            <tr>
                <th>Belegnr.</th><th>Versicherter</th><th>Verordnet am</th><th>VO-Art</th>
                <th>Diagnosegr.</th><th>ICD-10</th><th>Arzt</th>
                <th>Brutto (€)</th><th>Zuzahlung (€)</th>
            </tr>
        </thead>
        <tbody>
            {table_rows}
        </tbody>
    </table>
    </div>
</div>
</body>
</html>
"""


# Fachübersetzung von EDIFACT Segmenten für den Rezept-Baum
_SEGMENT_LABEL_MAP: Dict[str, str] = {
    "UNB": "Nutzdaten-Kopfsegment (UNB)",
    "UNH": "Nachricht (UNH)",
    "FKT": "Funktionsschlüssel / Abrechnungsverfahren (FKT)",
    "REC": "Rechnungsdaten (REC)",
    "UST": "Umsatzsteuer (UST)",
    "SKO": "Skonto (SKO)",
    "GES": "Gesamtsumme nach Status (GES)",
    "NAM": "Praxis- / Dienstleister-Name (NAM)",
    "INV": "Verordnung / Abrechnungsbeleg (INV)",
    "URI": "Ursprungsrechnung-Referenz (URI)",
    "NAD": "Versichertendaten (NAD)",
    "IMG": "Bild-/Anlagenreferenz (IMG)",
    "EVO": "Elektronische Verordnung (EVO)",
    "TXT": "Freitext (TXT)",
    "MWS": "Mehrwertsteuer (MWS)",
    "ZHE": "Verordnungsdaten Heilmittel (ZHE)",
    "ZHI": "Verordnungsdaten Hilfsmittel (ZHI)",
    "ZHK": "Verordnungsdaten häusliche Krankenpflege (ZHK)",
    "ZHH": "Verordnungsdaten Haushaltshilfe (ZHH)",
    "ZKT": "Verordnungsdaten Krankentransport (ZKT)",
    "ZHB": "Verordnungsdaten Hebammenhilfe (ZHB)",
    "ZSP": "Verordnungsdaten SAPV (ZSP)",
    "EHE": "Heilmittel-Position (EHE)",
    "ENF": "Nebenkosten / Wegegeld (ENF)",
    "EHI": "Hilfsmittel-Position (EHI)",
    "EHK": "Position häusliche Krankenpflege (EHK)",
    "EKT": "Position Krankentransport (EKT)",
    "EHB": "Position Hebammenhilfe (EHB)",
    "ESP": "Position SAPV (ESP)",
    "DIA": "Diagnose ICD-10 (DIA)",
    "SKZ": "Genehmigung (SKZ)",
    "BES": "Belegsumme & Zuzahlung (BES)",
    "GZF": "Forderung Zuzahlung (GZF)",
    "UNT": "Nachrichten-Trailer (UNT)",
    "UNZ": "Nutzdaten-Trailer (UNZ)",
}

# Segmente, die innerhalb eines INV-Blocks in Sammelknoten zusammengefasst werden
_DIAGNOSE_SEGMENTE = ("DIA",)
_GENEHMIGUNG_SEGMENTE = ("SKZ",)
_ABSCHLUSS_SEGMENTE = ("BES", "GZF")


class _IdGen:
    """Vergibt eindeutige, stabile Knoten-IDs für den Treeview."""

    def __init__(self) -> None:
        self._n = 0

    def next(self, prefix: str = "n") -> str:
        self._n += 1
        return f"{prefix}{self._n}"


def _node(ids: _IdGen, tag: str, label: str, details: str = "", raw: str = "",
          prefix: str = "n") -> Dict[str, Any]:
    return {
        "id": ids.next(prefix),
        "tag": tag,
        "label": label,
        "details": details,
        "raw": raw,
        "children": [],
    }


def _field_children(ids: _IdGen, tag: str, fields: List[Any], raw: str,
                    msg_type: str = "") -> List[Dict[str, Any]]:
    """Ein Unterknoten je belegtem Segmentfeld, benannt nach der SchemaRegistry."""
    children = []
    for row in vo.segment_field_rows(tag, fields, message_type=msg_type or None):
        children.append(
            _node(ids, tag, f"{row['index']}. {row['name']}", row["value"], "", prefix="f")
        )
    return children


def _segment_summary(tag: str, fields: List[Any], msg_type: str = "") -> str:
    """Kurzfassung eines Segments für die Detailspalte."""
    def g(i: int) -> str:
        if len(fields) <= i or fields[i] in (None, ""):
            return ""
        return ":".join(str(x) for x in fields[i]) if isinstance(fields[i], list) else str(fields[i])

    if tag == "UNB":
        return " | ".join(p for p in [
            f"Absender: {g(1)}" if g(1) else "",
            f"Empfänger: {g(2)}" if g(2) else "",
            f"Erstellt: {g(3)}" if g(3) else "",
            f"Datenaustauschreferenz: {g(4)}" if g(4) else "",
        ] if p)
    if tag == "FKT":
        return " | ".join(p for p in [
            f"VK {g(0)}" if g(0) else "",
            f"IK Leistungserbringer: {g(2)}" if g(2) else "",
            f"IK Kostenträger: {g(3)}" if g(3) else "",
            f"IK Krankenkasse: {g(4)}" if g(4) else "",
        ] if p)
    if tag == "REC":
        return " | ".join(p for p in [
            f"Rechnungsnr.: {g(0)}" if g(0) else "",
            f"Rechnungsdatum: {format_date_german(g(1))}" if g(1) else "",
        ] if p)
    if tag == "GES":
        return " | ".join(p for p in [
            f"Status: {g(0)}" if g(0) else "",
            f"Brutto: {vo.fmt_betrag(g(1))}" if g(1) else "",
            f"Rechnungsbetrag: {vo.fmt_betrag(g(2))}" if g(2) else "",
            f"Zuzahlung: {vo.fmt_betrag(g(3))}" if g(3) else "",
        ] if p)
    if tag == "NAM":
        return g(0)
    if tag == "NAD":
        name = ", ".join(p for p in [g(0), g(1)] if p)
        geb = format_date_german(g(2))
        return " | ".join(p for p in [name, f"geb. {geb}" if geb else ""] if p)
    if tag == "DIA":
        code, text = g(0), g(1)
        return f"{code}  —  {text}" if text else code
    if tag == "SKZ":
        return " | ".join(p for p in [
            f"Kennzeichen: {g(0)}" if g(0) else "",
            f"vom {format_date_german(g(1))}" if g(1) else "",
            f"Art: {g(2)}" if g(2) else "",
        ] if p)
    if tag == "BES":
        return " | ".join(p for p in [
            f"Brutto: {vo.fmt_betrag(g(0))}" if g(0) else "",
            f"Zuzahlung ges.: {vo.fmt_betrag(g(1))}" if g(1) else "",
            f"prozentual: {vo.fmt_betrag(g(2))}" if g(2) else "",
            f"pauschal: {vo.fmt_betrag(g(3))}" if g(3) else "",
        ] if p)
    if tag == "GZF":
        return " | ".join(p for p in [
            f"Forderung ges.: {vo.fmt_betrag(g(0))}" if g(0) else "",
            f"prozentual: {vo.fmt_betrag(g(1))}" if g(1) else "",
            f"pauschal: {vo.fmt_betrag(g(2))}" if g(2) else "",
        ] if p)
    if tag in ("UNH", "UNT", "UNZ"):
        return " | ".join(x for x in (g(0), g(1)) if x)

    # Rückfall: alle belegten Felder benannt aneinanderreihen
    rows = vo.segment_field_rows(tag, fields, message_type=msg_type or None)
    return " | ".join(f"{r['name']}: {r['value']}" for r in rows[:4])


def _zhe_node(ids: _IdGen, tag: str, fields: List[Any], raw: str) -> Dict[str, Any]:
    """Verordnungsdaten als aufklappbarer Klartext-Knoten."""
    label = _SEGMENT_LABEL_MAP.get(tag, f"Verordnungsdaten ({tag})")

    if tag != "ZHE":
        node = _node(ids, tag, label, _segment_summary(tag, fields), raw)
        node["children"] = _field_children(ids, tag, fields, raw)
        return node

    z = vo.decode_zhe(fields)
    summary = " | ".join(p for p in [
        f"Verordnung vom {z['verordnungsdatum_text']}" if z["verordnungsdatum"] else "",
        z["arzt_text"] if z["arzt_text"] != "—" else "",
        f"Verordnungsart {z['verordnungsart']}" if z["verordnungsart"] else "",
        f"Diagnosegruppe {z['diagnosegruppe']}" if z["diagnosegruppe"] else "",
    ] if p)

    node = _node(ids, tag, label, summary, raw)

    zeilen: List[Tuple[str, str]] = [
        ("Verordnungsdatum", z["verordnungsdatum_text"]),
        ("Betriebsstättennummer (BSNR)", z["bsnr"] or "—"),
        ("Lebenslange Arztnummer (LANR)", z["lanr"] or "—"),
        ("Verordnungsart", z["verordnungsart_text"]),
        ("Diagnosegruppe", z["diagnosegruppe_text"]),
        ("Leitsymptomatik", z["leitsymptomatik_text"]),
    ]
    if z["ind_leitsymptomatik"]:
        zeilen.append(("Individuelle Leitsymptomatik", z["ind_leitsymptomatik"]))
    zeilen += [
        ("Therapiefrequenz", z["therapiefrequenz_text"]),
        ("Therapiebericht", z["therapiebericht_text"]),
        ("Hausbesuch", z["hausbesuch_text"]),
        ("Dringlicher Behandlungsbedarf", z["dringlich_text"]),
        ("Heilmittel-Bereich", z["heilmittelbereich_text"]),
        ("Verordnungsbesonderheiten", z["verordnungsbesonderheiten_text"]),
        ("Unfallkennzeichen", z["unfallkennzeichen_text"]),
        ("BVG / Sonstiges / SER", z["bvg_text"]),
        ("Zuzahlungskennzeichen", z["zuzahlungskennzeichen_text"]),
    ]

    for name, value in zeilen:
        node["children"].append(_node(ids, tag, name, value, "", prefix="f"))

    return node


def _leistungen_node(ids: _IdGen, positions: List[Dict[str, Any]],
                     abrechnungscode: str) -> Optional[Dict[str, Any]]:
    """Behandlungspositionen gruppiert, Einzeltermine als Unterknoten."""
    if not positions:
        return None

    gruppen = vo.gruppiere_positionen(positions)
    uebersicht = vo.behandlungsuebersicht(positions)

    root = _node(
        ids, "LEISTUNGEN",
        f"Leistungen / Behandlungsverlauf ({len(gruppen)} Leistungsarten)",
        f"{uebersicht['zeitraum_text']} | {uebersicht['anzahl_behandlungstage']} Behandlungstage "
        f"| {uebersicht['anzahl_positionen']} Einzelpositionen",
        prefix="l",
    )

    for g in gruppen:
        klartext = g.get("code_klartext") or codelisten.KEIN_KLARTEXT
        g_node = _node(
            ids, g["tag"],
            f"{g['tag']} {g['code']} — {klartext}",
            f"{g['anzahl_termine']}× | {g['zeitraum_text']} | Einzel {vo.fmt_betrag(g['einzelbetrag'])} "
            f"| Gesamt {vo.fmt_betrag(g['betrag_gesamt'])} | Zuzahlung {vo.fmt_betrag(g['zuzahlung_gesamt'])}",
            prefix="lg",
        )
        for t in g.get("termine", []):
            g_node["children"].append(
                _node(
                    ids, g["tag"],
                    f"{vo.fmt_datum(t.get('datum')) or 'ohne Datum'}",
                    f"Menge {vo.fmt_menge(t.get('anzahl'))} × {vo.fmt_betrag(t.get('einzelbetrag'))} "
                    f"= {vo.fmt_betrag(t.get('gesamtbetrag'))} | Zuzahlung "
                    f"{vo.fmt_betrag(t.get('zuzahlung_gesamt', t.get('zuzahlung')))}",
                    prefix="lt",
                )
            )
        root["children"].append(g_node)

    return root


def parse_esol_tree_nodes(raw_content: str) -> List[Dict[str, Any]]:
    """
    Parst den ESOL-Inhalt in eine hierarchische Datenstruktur für den Rezept-Baum.

    Aufbau:
        UNB
        Nachricht 1 (SLGA)  ->  FKT, REC, GES..., NAM, UNT
        Nachricht 2 (SLLA)  ->  FKT, REC
                                Verordnung / Beleg <Nr>
                                    Versicherter (NAD)
                                    Verordnungsdaten (ZHE)  -> Feld je Zeile
                                    Diagnosen (DIA)
                                    Genehmigung (SKZ)
                                    Leistungen              -> Leistungsart -> Termine
                                    Belegsumme (BES/GZF)
                                UNT
        UNZ

    Jeder Knoten: {id, tag, label, details, raw, children}. Kinder können selbst
    Kinder haben — der Viewer fügt sie rekursiv ein.
    """
    tokenizer = SegmentTokenizer()
    raw_segments = tokenizer.tokenize_segments(raw_content)

    ids = _IdGen()
    tree: List[Dict[str, Any]] = []

    msg_node: Optional[Dict[str, Any]] = None
    msg_type = ""
    msg_index = 0
    inv_node: Optional[Dict[str, Any]] = None
    inv_state: Dict[str, Any] = {}

    def flush_inv():
        """Sammelknoten des laufenden INV-Blocks in fester Reihenfolge anhängen."""
        nonlocal inv_node, inv_state
        if inv_node is None:
            return

        if inv_state.get("versicherter"):
            inv_node["children"].append(inv_state["versicherter"])
        if inv_state.get("verordnung"):
            inv_node["children"].append(inv_state["verordnung"])
        if inv_state.get("diagnosen"):
            dia_root = _node(
                ids, "DIA", f"Diagnosen ({len(inv_state['diagnosen'])})",
                " ; ".join(d["details"] for d in inv_state["diagnosen"]), prefix="d",
            )
            dia_root["children"] = inv_state["diagnosen"]
            inv_node["children"].append(dia_root)
        if inv_state.get("genehmigung"):
            inv_node["children"].extend(inv_state["genehmigung"])
        if inv_state.get("weitere"):
            inv_node["children"].extend(inv_state["weitere"])

        leist = _leistungen_node(ids, inv_state.get("positions", []),
                                 inv_state.get("abrechnungscode", ""))
        if leist:
            inv_node["children"].append(leist)

        if inv_state.get("abschluss"):
            inv_node["children"].extend(inv_state["abschluss"])

        # Detailzeile des INV-Knotens um die Verordnungsdaten ergänzen
        z = inv_state.get("zhe_decoded")
        extra = []
        if z:
            if z.get("verordnungsdatum"):
                extra.append(f"Verordnung vom {z['verordnungsdatum_text']}")
            if z.get("diagnosegruppe"):
                extra.append(f"Diagnosegruppe {z['diagnosegruppe']}")
            if z.get("verordnungsart"):
                extra.append(f"Verordnungsart {z['verordnungsart']}")
        if inv_state.get("positions"):
            ub = vo.behandlungsuebersicht(inv_state["positions"])
            extra.append(f"{ub['anzahl_behandlungstage']} Behandlungstage")
        if extra:
            inv_node["details"] = inv_node["details"] + " | " + " | ".join(extra)

        inv_node = None
        inv_state = {}

    for raw_seg in raw_segments:
        parsed = tokenizer.parse_segment(raw_seg)
        tag = parsed.get("tag", "")
        fields = parsed.get("fields", [])
        raw = raw_seg.strip()
        if not tag:
            continue

        # ---------------- Umschlag ----------------
        if tag == "UNB":
            flush_inv()
            msg_node = None
            n = _node(ids, tag, _SEGMENT_LABEL_MAP[tag], _segment_summary(tag, fields), raw)
            n["children"] = _field_children(ids, tag, fields, raw)
            tree.append(n)
            continue

        if tag == "UNZ":
            flush_inv()
            msg_node = None
            n = _node(ids, tag, _SEGMENT_LABEL_MAP[tag], _segment_summary(tag, fields), raw)
            n["children"] = _field_children(ids, tag, fields, raw)
            tree.append(n)
            continue

        if tag == "UNH":
            flush_inv()
            msg_index += 1
            typ = ""
            if len(fields) > 1:
                raw_t = fields[1]
                typ = str(raw_t[0]) if isinstance(raw_t, list) and raw_t else str(raw_t)
            msg_type = typ
            ref = str(fields[0]) if fields else ""
            msg_node = _node(
                ids, tag, f"Nachricht {msg_index}" + (f" — {typ}" if typ else ""),
                f"Referenz: {ref}", raw, prefix="m",
            )
            tree.append(msg_node)
            continue

        if tag == "UNT":
            flush_inv()
            n = _node(ids, tag, _SEGMENT_LABEL_MAP[tag], _segment_summary(tag, fields, msg_type), raw)
            (msg_node["children"] if msg_node else tree).append(n)
            msg_type = ""
            continue

        # ---------------- INV-Block beginnt ----------------
        if tag == "INV":
            flush_inv()
            belegnr = str(fields[3]) if len(fields) > 3 else ""
            versnr = str(fields[0]) if len(fields) > 0 else ""
            status = str(fields[1]) if len(fields) > 1 else ""
            inv_node = _node(
                ids, tag,
                f"Verordnung / Beleg {belegnr or '(ohne Nr.)'}",
                " | ".join(p for p in [
                    f"Beleg-Nr: {belegnr}" if belegnr else "",
                    f"Versicherten-Nr: {versnr}" if versnr else "",
                    f"Status: {status}" if status else "",
                ] if p),
                raw, prefix="inv",
            )
            inv_state = {
                "positions": [],
                "diagnosen": [],
                "genehmigung": [],
                "weitere": [],
                "abschluss": [],
                "abrechnungscode": "",
            }
            (msg_node["children"] if msg_node else tree).append(inv_node)
            continue

        # ---------------- Segmente innerhalb eines INV-Blocks ----------------
        if inv_node is not None:
            if tag == "NAD":
                inv_state["versicherter"] = _build_simple_node(ids, tag, fields, raw, msg_type)
                continue

            if tag in vo.VERORDNUNGS_SEGMENTE:
                inv_state["verordnung"] = _zhe_node(ids, tag, fields, raw)
                if tag == "ZHE":
                    inv_state["zhe_decoded"] = vo.decode_zhe(fields)
                continue

            if tag in _DIAGNOSE_SEGMENTE:
                inv_state["diagnosen"].append(_build_simple_node(ids, tag, fields, raw, msg_type))
                continue

            if tag in _GENEHMIGUNG_SEGMENTE:
                inv_state["genehmigung"].append(_build_simple_node(ids, tag, fields, raw, msg_type))
                continue

            if tag in vo.POSITIONS_SEGMENTE:
                pos = _position_from_fields(tag, fields)
                if not inv_state["abrechnungscode"] and pos.get("abr_code"):
                    inv_state["abrechnungscode"] = pos["abr_code"]
                inv_state["positions"].append(pos)
                continue

            if tag in _ABSCHLUSS_SEGMENTE:
                inv_state["abschluss"].append(_build_simple_node(ids, tag, fields, raw, msg_type))
                continue

            inv_state["weitere"].append(_build_simple_node(ids, tag, fields, raw, msg_type))
            continue

        # ---------------- Segmente auf Nachrichtenebene ----------------
        n = _build_simple_node(ids, tag, fields, raw, msg_type)
        (msg_node["children"] if msg_node else tree).append(n)

    flush_inv()
    return tree


def _build_simple_node(ids: _IdGen, tag: str, fields: List[Any], raw: str,
                       msg_type: str = "") -> Dict[str, Any]:
    """Standardknoten: Klartext-Label, Kurzfassung und Feldliste als Kinder."""
    node = _node(
        ids, tag,
        _SEGMENT_LABEL_MAP.get(tag, f"Segment ({tag})"),
        _segment_summary(tag, fields, msg_type),
        raw,
    )
    node["children"] = _field_children(ids, tag, fields, raw, msg_type)
    return node


def _position_from_fields(tag: str, fields: List[Any]) -> Dict[str, Any]:
    """
    Baut aus einem Positionssegment das gleiche Dict-Format, das
    parse_esol_belege_summary liefert, damit vo.gruppiere_positionen greift.
    """
    def g(i: int) -> str:
        if len(fields) <= i or fields[i] in (None, ""):
            return ""
        return ":".join(str(x) for x in fields[i]) if isinstance(fields[i], list) else str(fields[i])

    def num(i: int) -> float:
        try:
            return float(g(i).replace(",", ".")) if g(i) else 0.0
        except ValueError:
            return 0.0

    leg_index = 1 if tag == "ENF" else 0
    leg_raw = fields[leg_index] if len(fields) > leg_index else ""
    if isinstance(leg_raw, list):
        abr = str(leg_raw[0]) if leg_raw else ""
        tarif = str(leg_raw[1]) if len(leg_raw) > 1 else ""
    else:
        parts = str(leg_raw).split(":")
        abr = parts[0]
        tarif = parts[1] if len(parts) > 1 else ""

    # Feldpositionen je Segmenttyp (identisch zu parse_esol_belege_summary)
    layout = {
        "EHE": {"code": 1, "anzahl": 2, "einzel": 3, "datum": 4, "zuz": 5},
        "ENF": {"code": 2, "anzahl": 3, "einzel": 4, "datum": 5, "zuz": 6},
        "EHI": {"code": 1, "anzahl": 2, "einzel": 4, "datum": 5, "zuz": 6},
        "EHK": {"code": 1, "anzahl": 2, "einzel": 3, "datum": None, "zuz": 4},
        "ESP": {"code": 1, "anzahl": 2, "einzel": 3, "datum": None, "zuz": 4},
        "EKT": {"code": 1, "anzahl": 2, "einzel": 3, "datum": 4, "zuz": None},
        "EHB": {"code": 1, "anzahl": 2, "einzel": 3, "datum": None, "zuz": None},
    }.get(tag, {"code": 1, "anzahl": 2, "einzel": 3, "datum": 4, "zuz": 5})

    anzahl = num(layout["anzahl"]) if layout["anzahl"] is not None else 0.0
    einzel = num(layout["einzel"]) if layout["einzel"] is not None else 0.0
    zuz = num(layout["zuz"]) if layout["zuz"] is not None else 0.0

    return {
        "tag": tag,
        "code": g(layout["code"]) if layout["code"] is not None else "",
        "abr_code": abr,
        "tarif_kz": tarif,
        "datum": g(layout["datum"]) if layout["datum"] is not None else "",
        "anzahl": anzahl,
        "einzelbetrag": einzel,
        "gesamtbetrag": round(anzahl * einzel, 2),
        "zuzahlung": zuz,
        "zuzahlung_gesamt": round(anzahl * zuz, 2),
        "raw_fields": fields,
    }
