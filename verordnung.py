"""
Verordnungs-Auswertung — bereitet die in einer ESOL-Datei enthaltenen Verordnungen
(INV-Blöcke mit ZHE / DIA / SKZ / URI / EHE) für die Anzeige auf.

Kernpunkte:
  * ZHE wird vollständig ausgewertet (17 Felder statt bisher nur dem Zuzahlungskennzeichen).
  * Klartexte kommen ausschließlich aus data/codelisten.json — es wird nichts geraten.
  * Feldnamen für beliebige Segmente kommen aus der vorhandenen SchemaRegistry,
    damit der Rezept-Baum jedes Segment benennen kann, ohne dass hier eine
    zweite Feldliste gepflegt werden muss.
  * Behandlungspositionen werden zu Leistungsgruppen zusammengefasst
    (Anzahl Termine, Zeitraum von–bis, Summen) und behalten die Einzeltermine
    als Unterliste.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple

import codelisten
from schema.schema import SchemaFactory

# ---------------------------------------------------------------------------
# Feldpositionen des ZHE-Segments (0-basiert, nach dem Tag) gemäß
# Technische Anlage 1, Segment ZHE — deckungsgleich mit schema/schema.py.
# ---------------------------------------------------------------------------
ZHE_BSNR = 0
ZHE_LANR = 1
ZHE_VERORDNUNGSDATUM = 2
ZHE_ZUZAHLUNGSKZ = 3
ZHE_DIAGNOSEGRUPPE = 4
ZHE_VERORDNUNGSART = 5
ZHE_VERORDNUNGSBESONDERHEITEN = 6
ZHE_UNFALLKENNZEICHEN = 7
ZHE_BVG = 8
ZHE_BEHANDLUNGSBEGINN = 9  # laut TA1 entfallen, immer leer
ZHE_THERAPIEBERICHT = 10
ZHE_HAUSBESUCH = 11
ZHE_LEITSYMPTOMATIK = 12
ZHE_IND_LEITSYMPTOMATIK = 13
ZHE_DRINGLICH = 14
ZHE_HEILMITTELBEREICH = 15
ZHE_THERAPIEFREQUENZ = 16

# Positionen der Leitsymptomatik-Stellen. Stelle 4 = patientenindividuelle
# Leitsymptomatik; das bestätigt auch rules/level3/zhe_content_rule.py (1.3.9.8).
LEITSYMPTOMATIK_STELLEN = ("a", "b", "c", "X (patientenindividuell)")
LEITSYMPTOMATIK_INDIVIDUELL = "9999"

# Segmente, die eine Verordnung beschreiben (Zusatzinfo je Leistungsbereich).
VERORDNUNGS_SEGMENTE = ("ZHE", "ZHI", "ZHK", "ZHH", "ZKT", "ZHB", "ZSP", "ZUZ", "ZUV")

# Leistungs-/Positionssegmente je Leistungsbereich.
POSITIONS_SEGMENTE = ("EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP", "EHH", "EHP")

_registry = None


def _schema_registry():
    global _registry
    if _registry is None:
        _registry = SchemaFactory.create()
    return _registry


# ---------------------------------------------------------------------------
# Formatierungshilfen
# ---------------------------------------------------------------------------

def fmt_datum(value: Any) -> str:
    """JJJJMMTT -> TT.MM.JJJJ; leere/abweichende Werte bleiben unverändert."""
    s = "" if value is None else str(value).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[6:8]}.{s[4:6]}.{s[0:4]}"
    return s


def fmt_betrag(value: Any) -> str:
    """Zahl -> '1.234,56 €' mit deutschem Tausender- und Dezimaltrennzeichen."""
    try:
        num = float(str(value).replace(",", ".")) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return str(value)
    return f"{num:,.2f} €".replace(",", "~").replace(".", ",").replace("~", ".")


def fmt_menge(value: Any) -> str:
    try:
        num = float(str(value).replace(",", ".")) if value not in (None, "") else 0.0
    except (TypeError, ValueError):
        return str(value)
    return f"{num:g}".replace(".", ",")


def _as_text(value: Any) -> str:
    """Ein Feld aus parse_segment_fields kann str oder Liste (Composite) sein."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ":".join(str(v) for v in value)
    return str(value).strip()


def _to_date(value: Any) -> Optional[datetime.date]:
    s = "" if value is None else str(value).strip()
    if len(s) == 8 and s.isdigit():
        try:
            return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    return None


def _split_leistungserbringergruppe(value: Any) -> Tuple[str, str]:
    """Composite 'Abrechnungscode:Tarifkennzeichen' -> ('26', '00501')."""
    if isinstance(value, list):
        parts = [str(v).strip() for v in value]
    else:
        parts = [p.strip() for p in _as_text(value).split(":")]
    abr = parts[0] if parts else ""
    tarif = parts[1] if len(parts) > 1 else ""
    return abr, tarif


# ---------------------------------------------------------------------------
# Generische, schema-gestützte Feldbenennung (für den Rezept-Baum)
# ---------------------------------------------------------------------------

def _segment_definition(tag: str, message_type: Optional[str] = None):
    """
    Felddefinition eines Segments. Manche Segmente (FKT) sind nur kontextspezifisch
    registriert — dann werden die bekannten Kontexte nachgeschlagen.
    """
    try:
        reg = _schema_registry()
    except Exception:
        return None
    for ctx in (message_type, None, "SLLA", "SLGA"):
        try:
            definition = reg.get(tag, ctx) if ctx else reg.get(tag)
        except Exception:
            definition = None
        if definition is not None:
            return definition
    return None


def segment_field_rows(tag: str, fields: List[Any], skip_empty: bool = True,
                       message_type: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Liefert je Segmentfeld eine Zeile {'name', 'value', 'index'} mit dem
    Feldnamen aus der SchemaRegistry. Unbekannte Felder erhalten 'Feld <n>'.
    """
    definition = _segment_definition(tag, message_type)

    rows: List[Dict[str, str]] = []
    for idx, raw in enumerate(fields):
        value = _as_text(raw)
        if skip_empty and not value:
            continue

        name = f"Feld {idx + 1}"
        fdef = definition.get_field(idx) if definition else None
        if fdef and fdef.get("name"):
            name = str(fdef["name"])

        # Composite-Felder in ihre Bestandteile aufschlüsseln
        if fdef and fdef.get("composite") and isinstance(fdef["composite"], list):
            parts = raw if isinstance(raw, list) else value.split(":")
            labels = []
            for c_idx, c_def in enumerate(fdef["composite"]):
                c_val = str(parts[c_idx]).strip() if c_idx < len(parts) else ""
                if c_val or not skip_empty:
                    labels.append(f"{c_def.get('name', f'Teil {c_idx + 1}')}: {c_val}")
            if labels:
                rows.append({"index": str(idx + 1), "name": name, "value": " | ".join(labels)})
                continue

        rows.append({"index": str(idx + 1), "name": name, "value": value})

    return rows


# ---------------------------------------------------------------------------
# ZHE-Auswertung
# ---------------------------------------------------------------------------

def decode_leitsymptomatik(value: Any) -> Dict[str, Any]:
    """
    Zerlegt das 4-stellige Leitsymptomatik-Feld in seine gesetzten Stellen.
    '9999' bedeutet: ausschließlich patientenindividuelle Leitsymptomatik.
    """
    raw = _as_text(value)
    result: Dict[str, Any] = {
        "raw": raw,
        "individuell": False,
        "stellen": [],
        "text": "—",
        "valide": True,
    }
    if not raw:
        result["valide"] = False
        return result

    if raw == LEITSYMPTOMATIK_INDIVIDUELL:
        result["individuell"] = True
        result["text"] = "9999 — patientenindividuelle Leitsymptomatik"
        return result

    if len(raw) != 4 or any(ch not in "01" for ch in raw):
        result["valide"] = False
        result["text"] = f"{raw} (ungültig — erwartet 4 Stellen aus 0/1 oder 9999)"
        return result

    gesetzt = [LEITSYMPTOMATIK_STELLEN[i] for i, ch in enumerate(raw) if ch == "1"]
    result["stellen"] = gesetzt
    result["individuell"] = raw[3] == "1"
    result["text"] = f"{raw} — " + (", ".join(gesetzt) if gesetzt else "keine Stelle gesetzt")
    return result


def decode_zhe(fields: List[Any]) -> Dict[str, Any]:
    """
    Wertet ein ZHE-Segment vollständig aus. Rohwerte bleiben erhalten ('*_raw'),
    dazu kommen anzeigefertige Klartexte ('*_text') aus den Codelisten.
    """
    def g(idx: int) -> str:
        return _as_text(fields[idx]) if len(fields) > idx else ""

    zhe: Dict[str, Any] = {
        # Rohfelder mitführen, damit die Klartexte nach dem Neuladen der
        # Codelisten ohne erneutes Parsen der Datei aufgelöst werden können.
        "rohfelder": [_as_text(f) for f in fields],
        "bsnr": g(ZHE_BSNR),
        "lanr": g(ZHE_LANR),
        "verordnungsdatum": g(ZHE_VERORDNUNGSDATUM),
        "zuzahlungskennzeichen": g(ZHE_ZUZAHLUNGSKZ),
        "diagnosegruppe": g(ZHE_DIAGNOSEGRUPPE),
        "verordnungsart": g(ZHE_VERORDNUNGSART),
        "verordnungsbesonderheiten": g(ZHE_VERORDNUNGSBESONDERHEITEN),
        "unfallkennzeichen": g(ZHE_UNFALLKENNZEICHEN),
        "bvg": g(ZHE_BVG),
        "behandlungsbeginn": g(ZHE_BEHANDLUNGSBEGINN),
        "therapiebericht": g(ZHE_THERAPIEBERICHT),
        "hausbesuch": g(ZHE_HAUSBESUCH),
        "leitsymptomatik": g(ZHE_LEITSYMPTOMATIK),
        "ind_leitsymptomatik": g(ZHE_IND_LEITSYMPTOMATIK),
        "dringlich": g(ZHE_DRINGLICH),
        "heilmittelbereich": g(ZHE_HEILMITTELBEREICH),
        "therapiefrequenz": g(ZHE_THERAPIEFREQUENZ),
    }

    zhe["verordnungsdatum_text"] = fmt_datum(zhe["verordnungsdatum"]) or "—"
    zhe["arzt_text"] = _arzt_text(zhe["bsnr"], zhe["lanr"])

    zhe["zuzahlungskennzeichen_text"] = codelisten.describe(
        "zuzahlungskennzeichen", zhe["zuzahlungskennzeichen"]
    )
    zhe["diagnosegruppe_text"] = codelisten.describe("diagnosegruppe", zhe["diagnosegruppe"])
    zhe["verordnungsart_text"] = codelisten.describe("verordnungsart", zhe["verordnungsart"])
    zhe["verordnungsbesonderheiten_text"] = codelisten.describe(
        "verordnungsbesonderheiten", zhe["verordnungsbesonderheiten"], leer_text="keine"
    )
    zhe["unfallkennzeichen_text"] = codelisten.describe(
        "unfallkennzeichen", zhe["unfallkennzeichen"], leer_text="kein Unfall"
    )
    zhe["bvg_text"] = codelisten.describe("bvg_sonstiges_ser", zhe["bvg"], leer_text="—")
    zhe["therapiebericht_text"] = codelisten.describe(
        "therapiebericht", zhe["therapiebericht"], leer_text="nicht angegeben"
    )
    zhe["hausbesuch_text"] = codelisten.describe(
        "hausbesuch", zhe["hausbesuch"], leer_text="nicht angegeben"
    )
    zhe["dringlich_text"] = codelisten.describe(
        "dringlicher_behandlungsbedarf", zhe["dringlich"], leer_text="nicht angegeben"
    )
    zhe["heilmittelbereich_text"] = codelisten.describe(
        "heilmittelbereich", zhe["heilmittelbereich"]
    )
    zhe["therapiefrequenz_text"] = codelisten.describe(
        "therapiefrequenz", zhe["therapiefrequenz"]
    )

    zhe["leitsymptomatik_decoded"] = decode_leitsymptomatik(zhe["leitsymptomatik"])
    zhe["leitsymptomatik_text"] = zhe["leitsymptomatik_decoded"]["text"]

    return zhe


def _arzt_text(bsnr: str, lanr: str) -> str:
    parts = []
    if bsnr:
        parts.append(f"BSNR {bsnr}")
    if lanr:
        parts.append(f"LANR {lanr}")
    return " · ".join(parts) if parts else "—"


def leeres_zhe() -> Dict[str, Any]:
    """Platzhalter-Verordnungsdaten, wenn ein Beleg kein ZHE-Segment enthält."""
    zhe = decode_zhe([])
    zhe["fehlt"] = True
    return zhe


# ---------------------------------------------------------------------------
# Positionen gruppieren
# ---------------------------------------------------------------------------

def gruppiere_positionen(positions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Fasst Behandlungspositionen zu Leistungsgruppen zusammen (Segmenttyp +
    Abrechnungscode/Tarifkennzeichen + Positionsnummer + Einzelbetrag).

    Je Gruppe: Anzahl Termine, Summe Menge, Summe Betrag, Summe Zuzahlung,
    Behandlungszeitraum von–bis sowie die Einzeltermine unter 'termine'.
    """
    gruppen: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    reihenfolge: List[Tuple[str, ...]] = []

    for pos in positions:
        tag = str(pos.get("tag", ""))
        code = str(pos.get("code", ""))
        abr = str(pos.get("abr_code", ""))
        tarif = str(pos.get("tarif_kz", ""))
        try:
            einzel = round(float(pos.get("einzelbetrag", 0.0) or 0.0), 2)
        except (TypeError, ValueError):
            einzel = 0.0

        key = (tag, abr, tarif, code, f"{einzel:.2f}")
        if key not in gruppen:
            reihenfolge.append(key)
            gruppen[key] = {
                "tag": tag,
                "abr_code": abr,
                "tarif_kz": tarif,
                "code": code,
                "code_text": codelisten.describe_position(code, abr),
                "code_klartext": codelisten.lookup_position(code, abr),
                "einzelbetrag": einzel,
                "termine": [],
                "anzahl_termine": 0,
                "menge_gesamt": 0.0,
                "betrag_gesamt": 0.0,
                "zuzahlung_gesamt": 0.0,
                "datum_von": "",
                "datum_bis": "",
            }

        g = gruppen[key]
        try:
            menge = float(pos.get("anzahl", 0.0) or 0.0)
        except (TypeError, ValueError):
            menge = 0.0

        g["termine"].append(pos)
        g["anzahl_termine"] += 1
        g["menge_gesamt"] = round(g["menge_gesamt"] + menge, 2)
        g["betrag_gesamt"] = round(g["betrag_gesamt"] + float(pos.get("gesamtbetrag", 0.0) or 0.0), 2)
        g["zuzahlung_gesamt"] = round(
            g["zuzahlung_gesamt"] + float(pos.get("zuzahlung_gesamt", pos.get("zuzahlung", 0.0)) or 0.0), 2
        )

        datum = str(pos.get("datum", "") or "")
        if datum:
            if not g["datum_von"] or datum < g["datum_von"]:
                g["datum_von"] = datum
            if not g["datum_bis"] or datum > g["datum_bis"]:
                g["datum_bis"] = datum

    ergebnis = []
    for key in reihenfolge:
        g = gruppen[key]
        g["termine"].sort(key=lambda p: str(p.get("datum", "")))
        g["zeitraum_text"] = zeitraum_text(g["datum_von"], g["datum_bis"])
        ergebnis.append(g)

    # Sortierung: nach erstem Behandlungsdatum, dann nach Positionsnummer
    ergebnis.sort(key=lambda g: (g["datum_von"] or "99999999", g["code"]))
    return ergebnis


def zeitraum_text(von: str, bis: str) -> str:
    v, b = fmt_datum(von), fmt_datum(bis)
    if not v and not b:
        return "—"
    if v == b or not b:
        return v or b
    return f"{v} – {b}"


def behandlungsuebersicht(positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Kennzahlen über alle Behandlungspositionen eines Belegs:
    Anzahl Behandlungstage, Zeitraum, erste/letzte Behandlung.
    """
    daten = sorted({str(p.get("datum", "")) for p in positions if p.get("datum")})
    return {
        "anzahl_positionen": len(positions),
        "anzahl_behandlungstage": len(daten),
        "erste_behandlung": daten[0] if daten else "",
        "letzte_behandlung": daten[-1] if daten else "",
        "zeitraum_text": zeitraum_text(daten[0], daten[-1]) if daten else "—",
    }


# ---------------------------------------------------------------------------
# Plausibilitätshinweise zur Verordnung (ergänzen die Validierung, ersetzen sie nicht)
# ---------------------------------------------------------------------------

def pruefe_verordnung(beleg: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Liefert Hinweise, die für die Hotline direkt am Verordnungsblatt sichtbar sein
    sollen: fehlendes ZHE/DIA, Datumslogik, Zuzahlungs-Widersprüche, fehlende
    individuelle Leitsymptomatik. Jeweils {'stufe': 'fehler'|'warnung'|'info', 'text': ...}.
    """
    hinweise: List[Dict[str, str]] = []
    zhe: Dict[str, Any] = beleg.get("verordnung") or {}
    positions: List[Dict[str, Any]] = beleg.get("positions") or []

    if zhe.get("fehlt"):
        hinweise.append({
            "stufe": "fehler",
            "text": "Kein ZHE-Segment im Beleg — es liegen keine Verordnungsdaten (Arzt, "
                    "Verordnungsdatum, Diagnosegruppe) vor.",
        })
        return hinweise

    # Verordnungsdatum vs. Behandlungsdaten
    vo_datum = _to_date(zhe.get("verordnungsdatum"))
    behandlungsdaten = sorted(
        d for d in (_to_date(p.get("datum")) for p in positions) if d is not None
    )
    if vo_datum and behandlungsdaten:
        if behandlungsdaten[0] < vo_datum:
            hinweise.append({
                "stufe": "fehler",
                "text": f"Erste Behandlung ({behandlungsdaten[0]:%d.%m.%Y}) liegt VOR dem "
                        f"Verordnungsdatum ({vo_datum:%d.%m.%Y}).",
            })
        spanne = (behandlungsdaten[-1] - vo_datum).days
        if spanne > 365:
            hinweise.append({
                "stufe": "warnung",
                "text": f"Letzte Behandlung liegt {spanne} Tage nach dem Verordnungsdatum — "
                        f"Gültigkeit der Verordnung prüfen.",
            })
    if vo_datum and vo_datum > datetime.date.today():
        hinweise.append({
            "stufe": "fehler",
            "text": f"Verordnungsdatum ({vo_datum:%d.%m.%Y}) liegt in der Zukunft.",
        })

    # Pflichtfelder der Verordnung
    for feld, bez in (
        ("bsnr", "Betriebsstättennummer (BSNR)"),
        ("lanr", "Lebenslange Arztnummer (LANR)"),
        ("verordnungsdatum", "Verordnungsdatum"),
        ("diagnosegruppe", "Diagnosegruppe"),
        ("verordnungsart", "Verordnungsart"),
    ):
        if not zhe.get(feld):
            hinweise.append({"stufe": "fehler", "text": f"{bez} fehlt im ZHE-Segment."})

    # Leitsymptomatik
    ls = zhe.get("leitsymptomatik_decoded") or {}
    if not ls.get("raw"):
        hinweise.append({"stufe": "warnung", "text": "Leitsymptomatik ist nicht angegeben."})
    elif not ls.get("valide"):
        hinweise.append({"stufe": "fehler", "text": f"Leitsymptomatik {ls.get('raw')} ist ungültig."})
    elif (ls.get("individuell") or ls.get("raw") == "0000") and not zhe.get("ind_leitsymptomatik"):
        hinweise.append({
            "stufe": "warnung",
            "text": "Patientenindividuelle Leitsymptomatik ist gesetzt, der Freitext dazu fehlt.",
        })

    # Diagnosen
    if not beleg.get("diagnosen"):
        hinweise.append({
            "stufe": "fehler",
            "text": "Kein DIA-Segment — bei Heilmitteln ist mindestens eine Diagnose erforderlich.",
        })

    # Zuzahlung vs. Zuzahlungskennzeichen
    zkz = str(zhe.get("zuzahlungskennzeichen", ""))
    try:
        zuz_summe = float(beleg.get("total_zuzahlung", 0.0) or 0.0)
    except (TypeError, ValueError):
        zuz_summe = 0.0
    if zkz == "1" and zuz_summe > 0:
        hinweise.append({
            "stufe": "fehler",
            "text": f"Zuzahlungskennzeichen 1 (befreit), es sind aber {fmt_betrag(zuz_summe)} "
                    f"Zuzahlung berechnet.",
        })
    if zkz == "3" and zuz_summe <= 0:
        hinweise.append({
            "stufe": "warnung",
            "text": "Zuzahlungskennzeichen 3 (zuzahlungspflichtig), es ist aber keine "
                    "Zuzahlung ausgewiesen.",
        })

    # Hausbesuch verordnet, aber keine Hausbesuchsposition erkennbar
    if str(zhe.get("hausbesuch", "")) == "1" and not any(
        p.get("tag") in ("ENF", "EHB") for p in positions
    ):
        hinweise.append({
            "stufe": "info",
            "text": "Hausbesuch ist verordnet. Ob eine passende Hausbesuchsposition "
                    "abgerechnet wurde, ist über die Positionsnummer zu prüfen.",
        })

    return hinweise


# ---------------------------------------------------------------------------
# Kompakte Textausgabe (Ticket / Bericht)
# ---------------------------------------------------------------------------

def verordnung_textzeilen(beleg: Dict[str, Any]) -> List[str]:
    """Mehrzeilige Klartext-Zusammenfassung der Verordnung für Tickets und Berichte."""
    zhe = beleg.get("verordnung") or {}
    if zhe.get("fehlt"):
        return ["Verordnung: keine Verordnungsdaten (ZHE-Segment fehlt)"]

    diagnosen = beleg.get("diagnosen") or []
    dia_text = "; ".join(
        d["code"] + (f" ({d['text']})" if d.get("text") else "") for d in diagnosen
    ) or "—"

    uebersicht = beleg.get("behandlung") or {}

    lines = [
        f"Verordnung vom:      {zhe.get('verordnungsdatum_text', '—')}",
        f"Verordnender Arzt:   {zhe.get('arzt_text', '—')}",
        f"Verordnungsart:      {zhe.get('verordnungsart_text', '—')}",
        f"Diagnosegruppe:      {zhe.get('diagnosegruppe_text', '—')}",
        f"Leitsymptomatik:     {zhe.get('leitsymptomatik_text', '—')}",
    ]
    if zhe.get("ind_leitsymptomatik"):
        lines.append(f"  individuell:       {zhe['ind_leitsymptomatik']}")
    lines += [
        f"ICD-10 Diagnose(n):  {dia_text}",
        f"Therapiefrequenz:    {zhe.get('therapiefrequenz_text', '—')}",
        f"Therapiebericht:     {zhe.get('therapiebericht_text', '—')}",
        f"Hausbesuch:          {zhe.get('hausbesuch_text', '—')}",
        f"Dringlichkeit:       {zhe.get('dringlich_text', '—')}",
        f"Zuzahlungsstatus:    {zhe.get('zuzahlungskennzeichen_text', '—')}",
        f"Behandlungszeitraum: {uebersicht.get('zeitraum_text', '—')} "
        f"({uebersicht.get('anzahl_behandlungstage', 0)} Behandlungstage)",
    ]

    if beleg.get("genehmigung"):
        for skz in beleg["genehmigung"]:
            lines.append(
                f"Genehmigung:         {skz.get('kennzeichen', '—')} "
                f"vom {fmt_datum(skz.get('datum'))} (Art {skz.get('art') or '—'})"
            )
    if beleg.get("ursprungsrechnung"):
        for uri in beleg["ursprungsrechnung"]:
            lines.append(f"Ursprungsrechnung:   {uri}")

    return lines
