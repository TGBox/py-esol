"""
Codelisten-Loader — lädt die Klartext-Tabellen für die Verordnungs-Anzeige.

Sechs Quellen. data/codelisten.json ist von Hand gepflegt und hat immer
Vorrang; alle anderen werden von den Skripten in tools/ erzeugt und beim
nächsten Import überschrieben.

  data/codelisten.json        eigene Pflege, Vorrang vor allem anderen
  data/heilmittelpreise.json  GKV-Heilmittelpreisstammdatei (tools/import_hmp.py)
  data/heilmittelkatalog.json X-Codes, BG/UV, Heilpraktiker
                              (tools/import_heilmittelkatalog.py)
  data/kostentraeger.json     IK-Verzeichnis (tools/import_kostentraeger.py)
  data/diagnosegruppen.json   KBV-Heilmittelstammdatei
                              (tools/import_kbv_stammdaten.py)
  data/verordnungsbedarf.json KBV-Stammdatei Heilmittelanlagen, dito

Grundregel: ist zu einem Code in keiner Quelle ein Klartext hinterlegt, wird
NICHTS geraten. Die Anzeige zeigt dann nur den Code plus einen Hinweis.

Positionsnummern werden in drei Stufen aufgelöst: eigene Pflege, dann die
GKV-Stammdatei, dann der Heilmittelkatalog. Zur maskierten ersten Stelle: die
Stammdatei führt Positionen nach § 125 (Regelversorgung) mit 'X' als erster
Stelle — X4103 statt 54103. In der Abrechnung steht dort die Stelle des
Heilmittelbereichs. Beim Nachschlagen wird deshalb zusätzlich 'X' + Rest
probiert. Belegt an den Testdaten: alle acht Positionen mit Tarifkennzeichen
00501, die als 5xxxx abgerechnet werden, finden sich in der Stammdatei als
X-Code wieder.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Marker, der in der GUI erscheint, wenn zu einem Code kein Klartext hinterlegt ist.
KEIN_KLARTEXT = "kein Klartext hinterlegt"

# Marker für ein Institutionskennzeichen, das in keinem Verzeichnis steht.
# Das ist der Normalfall bei Leistungserbringer-IKs: die Verzeichnisse führen
# Kostenträger, nicht Praxen.
KEIN_IK_EINTRAG = "kein Eintrag im IK-Verzeichnis"

_CODELIST_FILENAME = "codelisten.json"
_HMP_FILENAME = "heilmittelpreise.json"
_KATALOG_FILENAME = "heilmittelkatalog.json"
_KOSTENTRAEGER_FILENAME = "kostentraeger.json"
_DIAGNOSEGRUPPEN_FILENAME = "diagnosegruppen.json"
_VERORDNUNGSBEDARF_FILENAME = "verordnungsbedarf.json"

# Umgebungsvariablen zum Erzwingen eines Pfades (praktisch für Tests)
_ENV_CODELISTEN = "PY_ESOL_CODELISTEN"
_ENV_HMP = "PY_ESOL_HEILMITTELPREISE"
_ENV_KATALOG = "PY_ESOL_HEILMITTELKATALOG"
_ENV_KOSTENTRAEGER = "PY_ESOL_KOSTENTRAEGER"
_ENV_DIAGNOSEGRUPPEN = "PY_ESOL_DIAGNOSEGRUPPEN"
_ENV_VERORDNUNGSBEDARF = "PY_ESOL_VERORDNUNGSBEDARF"

# Kurzform der Kapitelbezeichnung des Heilmittelkatalogs für die Anzeige.
# Ein schlichtes Abschneiden von "Maßnahmen der " liefert beim zweiten Kapitel
# den Genitiv ("Podologischen Therapie"), deshalb die ausgeschriebene Zuordnung.
_BEREICH_KURZ = {
    "Maßnahmen der Physiotherapie": "Physiotherapie",
    "Maßnahmen der Podologischen Therapie": "Podologie",
    "Maßnahmen der Stimm-, Sprech-, Sprach- und Schlucktherapie":
        "Stimm-/Sprech-/Sprach-/Schlucktherapie",
    "Maßnahmen der Ergotherapie": "Ergotherapie",
    "Maßnahmen der Ernährungstherapie": "Ernährungstherapie",
}

# Art des Kostenträgers -> Beschriftung in der Anzeige
_ART_TEXT = {
    "gkv": "Krankenkasse / Kostenträger",
    "uv": "Unfallversicherungsträger",
    "heilfuersorge": "Heilfürsorge",
}

# ICD-10-Code mit optionalem Zusatzkennzeichen der Diagnosesicherheit.
# In den Belegen steht das teils angehängt ("F89G") und teils mit Leerzeichen
# ("F90.0 G"). Endstellen-Platzhalter ('-', '+', '*') gehören zum Code.
_ICD_MUSTER = re.compile(
    r"^\s*([A-Z]\d{2}(?:\.\d{1,2})?[-+*]?)\s*([GVAZ])?\s*$", re.IGNORECASE
)


class _Quelle:
    """Eine JSON-Datei mit Klartexten, gecacht und mit Ladefehler-Protokoll."""

    def __init__(self, dateiname: str, env_var: str):
        self.dateiname = dateiname
        self.env_var = env_var
        self._daten: Optional[Dict[str, Any]] = None
        self._pfad: Optional[Path] = None
        self._fehler: Optional[str] = None

    def _kandidaten(self) -> List[Path]:
        """
        Mögliche Ablageorte — funktioniert im Entwicklungsbaum ebenso wie im
        per PyInstaller gebauten One-File-Exe (sys._MEIPASS).
        """
        pfade: List[Path] = []

        # 1. Neben der ausführbaren Datei (erlaubt Pflege beim Kunden)
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            pfade.append(exe_dir / "data" / self.dateiname)
            pfade.append(exe_dir / self.dateiname)

        # 2. PyInstaller-Bundle-Verzeichnis
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            pfade.append(Path(meipass) / "data" / self.dateiname)
            pfade.append(Path(meipass) / self.dateiname)

        # 3. Projektbaum (Entwicklung)
        pfade.append(Path(__file__).resolve().parent / "data" / self.dateiname)

        # 4. Explizite Überschreibung per Umgebungsvariable
        env_pfad = os.environ.get(self.env_var)
        if env_pfad:
            pfade.insert(0, Path(env_pfad))

        return pfade

    def load(self, force: bool = False) -> Dict[str, Any]:
        if self._daten is not None and not force:
            return self._daten

        self._fehler = None
        for pfad in self._kandidaten():
            try:
                if not pfad.is_file():
                    continue
                with pfad.open("r", encoding="utf-8") as fh:
                    daten = json.load(fh)
                if not isinstance(daten, dict):
                    raise ValueError("Wurzelelement ist kein JSON-Objekt")
                self._daten = daten
                self._pfad = pfad
                return self._daten
            except Exception as exc:  # defekte Datei darf die GUI nicht abschießen
                self._fehler = f"{pfad}: {exc}"
                continue

        self._daten = {}
        self._pfad = None
        return self._daten

    @property
    def pfad(self) -> Optional[Path]:
        self.load()
        return self._pfad

    @property
    def fehler(self) -> Optional[str]:
        self.load()
        return self._fehler


_codelisten = _Quelle(_CODELIST_FILENAME, _ENV_CODELISTEN)
_hmp = _Quelle(_HMP_FILENAME, _ENV_HMP)
_katalog = _Quelle(_KATALOG_FILENAME, _ENV_KATALOG)
_kostentraeger = _Quelle(_KOSTENTRAEGER_FILENAME, _ENV_KOSTENTRAEGER)
_diagnosegruppen = _Quelle(_DIAGNOSEGRUPPEN_FILENAME, _ENV_DIAGNOSEGRUPPEN)
_verordnungsbedarf = _Quelle(_VERORDNUNGSBEDARF_FILENAME, _ENV_VERORDNUNGSBEDARF)

_ALLE_QUELLEN = (
    _codelisten, _hmp, _katalog, _kostentraeger, _diagnosegruppen, _verordnungsbedarf,
)


# ---------------------------------------------------------------------------
# Laden / Zustand
# ---------------------------------------------------------------------------

def load(force: bool = False) -> Dict[str, Any]:
    """Die handgepflegten Codelisten (gecacht)."""
    return _codelisten.load(force=force)


def load_hmp(force: bool = False) -> Dict[str, Any]:
    """Die aus der GKV-Stammdatei importierten Positionsbezeichnungen."""
    return _hmp.load(force=force)


def load_katalog(force: bool = False) -> Dict[str, Any]:
    """Positionsbezeichnungen aus dem Heilmittelkatalog, BG/UV und HP-Verzeichnis."""
    return _katalog.load(force=force)


def load_kostentraeger(force: bool = False) -> Dict[str, Any]:
    """Das IK-Verzeichnis (Kostenträger, UV-Träger, Heilfürsorge)."""
    return _kostentraeger.load(force=force)


def load_diagnosegruppen(force: bool = False) -> Dict[str, Any]:
    """Die Diagnosegruppen aus der KBV-Heilmittelstammdatei."""
    return _diagnosegruppen.load(force=force)


def load_verordnungsbedarf(force: bool = False) -> Dict[str, Any]:
    """ICD-Codes mit Langfristigem Heilmittelbedarf / Besonderem Verordnungsbedarf."""
    return _verordnungsbedarf.load(force=force)


def reload() -> Dict[str, Any]:
    """Erzwingt das Neuladen aller Quellen (Button 'Codelisten neu laden')."""
    for quelle in _ALLE_QUELLEN:
        if quelle is not _codelisten:
            quelle.load(force=True)
    return _codelisten.load(force=True)


def source_path() -> Optional[Path]:
    """Pfad der handgepflegten Codelisten (None = keine Datei gefunden)."""
    return _codelisten.pfad


def hmp_source_path() -> Optional[Path]:
    """Pfad der importierten Heilmittelpreis-Bezeichnungen."""
    return _hmp.pfad


def katalog_source_path() -> Optional[Path]:
    return _katalog.pfad


def kostentraeger_source_path() -> Optional[Path]:
    return _kostentraeger.pfad


def diagnosegruppen_source_path() -> Optional[Path]:
    return _diagnosegruppen.pfad


def verordnungsbedarf_source_path() -> Optional[Path]:
    return _verordnungsbedarf.pfad


def last_error() -> Optional[str]:
    """Letzter Ladefehler einer der Quellen."""
    for quelle in _ALLE_QUELLEN:
        if quelle.fehler:
            return quelle.fehler
    return None


def _quelle_info(quelle: _Quelle) -> Dict[str, Any]:
    info = quelle.load().get("_quelle")
    return info if isinstance(info, dict) else {}


def hmp_info() -> Dict[str, Any]:
    """
    Metadaten des letzten HMP-Imports: Quelldatei, Version, Anzahl Positionen,
    Heilmittelbereiche, Gültigkeitsstände. Leeres Dict, wenn nichts geladen ist.
    """
    return _quelle_info(_hmp)


def hmp_beschreibung() -> str:
    """Einzeiler über den geladenen HMP-Stand, für die Statuszeile der GUI."""
    info = hmp_info()
    if not info:
        return "Keine Heilmittelpreis-Bezeichnungen geladen"
    staende = ", ".join(info.get("gueltigkeitsstaende", {})) or "ohne Datum"
    return (
        f"{info.get('anzahl_positionen', 0)} Positionsbezeichnungen "
        f"aus {info.get('datei', 'HMP-Stammdatei')} (Stand {staende})"
    )


def quellen_beschreibung() -> List[str]:
    """
    Je geladene Zusatzquelle eine kurze Zeile für die Statuszeile des
    Verordnungsblatts. Nicht geladene Quellen werden weggelassen.
    """
    zeilen: List[str] = []

    # Bedingung ist jeweils: Datei gefunden UND Inhalt vorhanden. Eine leere
    # oder inhaltlich unbrauchbare Datei soll nicht als geladene Quelle
    # erscheinen — das wäre die irreführendere Auskunft.
    if _hmp.pfad and hmp_info():
        zeilen.append(hmp_beschreibung())

    katalog = _quelle_info(_katalog)
    if _katalog.pfad and katalog:
        zeilen.append(f"{katalog.get('anzahl_positionen', 0)} Positionen aus dem "
                      f"Heilmittelkatalog / BG / HP")

    ktr = _quelle_info(_kostentraeger)
    if _kostentraeger.pfad and ktr:
        zeilen.append(f"{ktr.get('anzahl_ik', 0)} Institutionskennzeichen")

    dg = _quelle_info(_diagnosegruppen)
    if _diagnosegruppen.pfad and dg:
        zeilen.append(f"{dg.get('anzahl_diagnosegruppen', 0)} Diagnosegruppen "
                      f"({dg.get('datei', 'KBV-Stammdatei')})")

    vb = _quelle_info(_verordnungsbedarf)
    if _verordnungsbedarf.pfad and vb:
        zeilen.append(f"{vb.get('anzahl_icd', 0)} ICD-Codes mit Verordnungsbedarf "
                      f"(gültig {vb.get('gueltig', '?')})")

    return zeilen


# ---------------------------------------------------------------------------
# Einfaches Nachschlagen
# ---------------------------------------------------------------------------

def lookup(liste: str, code: Any, default: str = "") -> str:
    """
    Sucht den Klartext zu einem Code. Gibt '' zurück, wenn kein Klartext
    hinterlegt ist. Es wird NIE ein Wert geraten oder abgeleitet.

    Für 'diagnosegruppe' wird nach der eigenen Pflege zusätzlich die
    KBV-Heilmittelstammdatei befragt.
    """
    if code is None:
        return default
    key = str(code).strip()
    if not key:
        return default

    tabelle = load().get(liste)
    if isinstance(tabelle, dict):
        wert = tabelle.get(key)
        if wert is None:
            # Führende Nullen tolerieren (z. B. '3' vs. '03')
            wert = tabelle.get(key.lstrip("0")) or tabelle.get(key.zfill(2))
        if isinstance(wert, str) and wert.strip():
            return wert.strip()

    if liste == "diagnosegruppe":
        bezeichnung = diagnosegruppe_info(key).get("bezeichnung", "")
        if bezeichnung:
            return bezeichnung

    return default


# ---------------------------------------------------------------------------
# Diagnosegruppen
# ---------------------------------------------------------------------------

def diagnosegruppe_info(code: Any) -> Dict[str, str]:
    """
    Auskunft zu einer Diagnosegruppe:
      bezeichnung    — Klartext oder ''
      bereich        — Heilmittelbereich ('Maßnahmen der Ergotherapie')
      kapitel        — römische Kapitelnummer des Heilmittelkatalogs
      kapitel_nummer — dieselbe Nummer arabisch; siehe Warnung unten
      quelle         — 'codelisten' | 'kbv' | ''

    'kapitel_nummer' ist NICHT der Schlüssel des 16. ZHE-Feldes. In echten
    Abrechnungsdateien steht dort bei einer Ergotherapie-Verordnung (Kapitel
    IV) eine 1. Der Zusammenhang ist ungeklärt, deshalb wird das Feld nur
    informativ mitgeführt und nirgends zur Prüfung verwendet.
    """
    leer = {"bezeichnung": "", "bereich": "", "kapitel": "",
            "kapitel_nummer": "", "quelle": ""}
    if code is None:
        return dict(leer)
    key = str(code).strip().upper()
    if not key:
        return dict(leer)

    eigene = load().get("diagnosegruppe")
    if isinstance(eigene, dict):
        wert = eigene.get(key)
        if isinstance(wert, str) and wert.strip():
            return {**leer, "bezeichnung": wert.strip(), "quelle": "codelisten"}

    tabelle = load_diagnosegruppen().get("diagnosegruppen")
    if isinstance(tabelle, dict):
        eintrag = tabelle.get(key)
        if isinstance(eintrag, dict) and str(eintrag.get("bezeichnung", "")).strip():
            return {
                "bezeichnung": str(eintrag.get("bezeichnung", "")).strip(),
                "bereich": str(eintrag.get("bereich", "")),
                "kapitel": str(eintrag.get("kapitel", "")),
                "kapitel_nummer": str(eintrag.get("kapitel_nummer", "")),
                "quelle": "kbv",
            }

    return dict(leer)


# ---------------------------------------------------------------------------
# Positionsnummern
# ---------------------------------------------------------------------------

def _aus_codelisten(key: str, abrechnungscode: Any) -> str:
    """Handgepflegte Positionsbezeichnung, gestaffelt nach Abrechnungscode."""
    tabelle = load().get("positionsnummern")
    if not isinstance(tabelle, dict):
        return ""

    for bucket in (str(abrechnungscode).strip() if abrechnungscode else None, "*"):
        if not bucket:
            continue
        sub = tabelle.get(bucket)
        if isinstance(sub, dict):
            wert = sub.get(key)
            if isinstance(wert, str) and wert.strip():
                return wert.strip()

    # Rückfall: flache Tabelle ohne Staffelung nach Abrechnungscode
    wert = tabelle.get(key)
    if isinstance(wert, str) and wert.strip():
        return wert.strip()
    return ""


def hmp_position(code: Any) -> Dict[str, str]:
    """
    Eintrag der GKV-Stammdatei zu einer Abrechnungspositionsnummer.

    Zuerst wird der Code direkt gesucht (Positionen nach § 125a stehen dort
    unverändert), danach mit 'X' an erster Stelle (Positionen nach § 125 sind
    so maskiert). Rückgabe enthält zusätzlich 'hmp_code' — den Code, unter dem
    der Eintrag tatsächlich gefunden wurde.
    """
    return _aus_positionstabelle(load_hmp().get("positionen"), code)


def katalog_position(code: Any) -> Dict[str, str]:
    """
    Eintrag des Heilmittelkatalogs (oder der BG/HP-Verzeichnisse). Gleiche
    X-Masken-Auflösung wie bei der GKV-Stammdatei.

    Ist zum Code eine Leistungsgruppe hinterlegt und nennt die Bezeichnung nur
    den Zusatz ("bei motorischen Störungen"), wird die Gruppe davorgesetzt.
    """
    eintrag = _aus_positionstabelle(load_katalog().get("positionen"), code)
    if not eintrag:
        return {}

    gruppe = str(eintrag.get("gruppe", "")).strip()
    if gruppe:
        gruppen = load_katalog().get("leistungsgruppen")
        if isinstance(gruppen, dict):
            gruppentext = str(gruppen.get(gruppe, "")).strip()
            if gruppentext:
                eintrag["gruppe_text"] = gruppentext
                if eintrag["bezeichnung"].lower().startswith(("bei ", "je ", "auf ")):
                    eintrag["bezeichnung"] = f"{gruppentext}: {eintrag['bezeichnung']}"
    return eintrag


def _aus_positionstabelle(positionen: Any, code: Any) -> Dict[str, str]:
    """Gemeinsame Suche für HMP und Heilmittelkatalog, inkl. X-Maske."""
    if code is None or not isinstance(positionen, dict):
        return {}
    key = str(code).strip()
    if not key:
        return {}

    for kandidat in (key, "X" + key[1:] if len(key) > 1 else None):
        if not kandidat:
            continue
        eintrag = positionen.get(kandidat)
        if isinstance(eintrag, dict) and str(eintrag.get("bezeichnung", "")).strip():
            ergebnis = {k: str(v) for k, v in eintrag.items()}
            ergebnis["hmp_code"] = kandidat
            return ergebnis
    return {}


def position_info(code: Any, abrechnungscode: Any = None) -> Dict[str, str]:
    """
    Vollständige Auskunft zu einer Positionsnummer:
      bezeichnung — Klartext oder ''
      quelle      — 'codelisten' | 'hmp' | 'katalog' | ''
      bereich     — Heilmittelbereich (nicht bei Quelle 'codelisten')
      grundlage   — '125' | '125a' | '' (nur bei Quelle 'hmp')
      gueltig_ab  — Gültigkeitsdatum (nur bei Quelle 'hmp')
      hmp_code    — Code in der Quelltabelle, falls über die X-Maske gefunden
      gruppe_text — Leistungsgruppe (nur bei Quelle 'katalog')
    """
    leer = {"bezeichnung": "", "quelle": "", "bereich": "", "grundlage": "",
            "gueltig_ab": "", "hmp_code": "", "gruppe_text": ""}
    if code is None:
        return dict(leer)
    key = str(code).strip()
    if not key:
        return dict(leer)

    eigene = _aus_codelisten(key, abrechnungscode)
    if eigene:
        return {**leer, "bezeichnung": eigene, "quelle": "codelisten"}

    for quelle, sucher in (("hmp", hmp_position), ("katalog", katalog_position)):
        eintrag = sucher(key)
        if eintrag:
            return {
                **leer,
                "bezeichnung": eintrag.get("bezeichnung", ""),
                "quelle": quelle,
                "bereich": eintrag.get("bereich", ""),
                "grundlage": eintrag.get("grundlage", ""),
                "gueltig_ab": eintrag.get("gueltig_ab", ""),
                "hmp_code": eintrag.get("hmp_code", ""),
                "gruppe_text": eintrag.get("gruppe_text", ""),
            }

    return dict(leer)


def lookup_position(code: Any, abrechnungscode: Any = None, default: str = "") -> str:
    """
    Klartext zu einer Abrechnungspositionsnummer. Reihenfolge: eigene Pflege in
    codelisten.json, dann die GKV-Stammdatei, dann der Heilmittelkatalog
    (jeweils direkt, dann über die X-Maske).
    """
    bezeichnung = position_info(code, abrechnungscode).get("bezeichnung", "")
    return bezeichnung or default


# ---------------------------------------------------------------------------
# Institutionskennzeichen
# ---------------------------------------------------------------------------

def kostentraeger(ik: Any) -> Dict[str, Any]:
    """
    Auskunft zu einem Institutionskennzeichen. Leeres Dict, wenn der IK in
    keinem Verzeichnis steht — das ist bei Leistungserbringer-IKs der
    Normalfall, denn die Verzeichnisse führen Kostenträger, nicht Praxen.

    Eine eigene Korrektur ist über codelisten.json möglich:
        "kostentraeger": { "101777502": "Techniker Krankenkasse" }
    """
    if ik is None:
        return {}
    key = str(ik).strip()
    if not key:
        return {}

    eigene = load().get("kostentraeger")
    eigener_name = ""
    if isinstance(eigene, dict):
        wert = eigene.get(key)
        if isinstance(wert, str) and wert.strip():
            eigener_name = wert.strip()

    traeger = load_kostentraeger().get("traeger")
    eintrag = traeger.get(key) if isinstance(traeger, dict) else None

    if not isinstance(eintrag, dict):
        if eigener_name:
            return {"ik": key, "name": eigener_name, "art": "", "art_text": "",
                    "quelle": "codelisten"}
        return {}

    ergebnis = dict(eintrag)
    ergebnis["ik"] = key
    if eigener_name:
        ergebnis["name"] = eigener_name
        ergebnis["quelle"] = "codelisten"
    ergebnis["art_text"] = _ART_TEXT.get(str(ergebnis.get("art", "")), "")
    return ergebnis


def ik_name(ik: Any, default: str = "") -> str:
    """Nur der Name zu einem IK, oder default."""
    return kostentraeger(ik).get("name", "") or default


def describe_ik(ik: Any, leer_text: str = "—") -> str:
    """
    Anzeigefertige Kombination aus IK und Name:
      '101777502 — TECHNIKER KRANKENKASSE'
      '480512931 (kein Eintrag im IK-Verzeichnis)'
      '—'
    """
    key = "" if ik is None else str(ik).strip()
    if not key:
        return leer_text
    eintrag = kostentraeger(key)
    name = eintrag.get("name", "")
    if not name:
        return f"{key} ({KEIN_IK_EINTRAG})"
    zusatz = str(eintrag.get("zusatz", "")).strip()
    # 'Land NW' ist eine Herkunftsangabe der Quelldatei, keine Organisations-
    # einheit — die gehört nicht hinter den Namen.
    if zusatz and not zusatz.startswith("Land "):
        return f"{key} — {name}, {zusatz}"
    return f"{key} — {name}"


def ik_zeilen(ik: Any) -> List[str]:
    """
    Mehrzeilige Auskunft zu einem IK für Bericht und Ticket-Zusammenfassung.
    Leere Liste, wenn nichts bekannt ist.
    """
    eintrag = kostentraeger(ik)
    if not eintrag:
        return []

    zeilen = [describe_ik(ik)]
    if eintrag.get("art_text"):
        zeilen.append(f"Art: {eintrag['art_text']}")

    anschrift = " ".join(p for p in [
        str(eintrag.get("strasse", "")).strip(),
        f"{str(eintrag.get('plz', '')).strip()} {str(eintrag.get('ort', '')).strip()}".strip(),
    ] if p)
    if anschrift:
        zeilen.append(anschrift)
    if eintrag.get("email"):
        zeilen.append(str(eintrag["email"]))

    if eintrag.get("nachfolge_ik"):
        zeilen.append(f"Nachfolge-IK: {describe_ik(eintrag['nachfolge_ik'])}")
    gueltig = " bis ".join(p for p in [
        str(eintrag.get("gueltig_ab", "")).strip(),
        str(eintrag.get("gueltig_bis", "")).strip(),
    ] if p)
    if gueltig:
        zeilen.append(f"Gültig ab {gueltig}")

    for name, beschriftung in (("dfu", "Datenannahmestelle (DFÜ)"),
                               ("papier", "Papierannahmestelle"),
                               ("zahlung", "Zahlung an")):
        stelle = (eintrag.get("annahmestelle") or {}).get(name)
        if not isinstance(stelle, dict) or not stelle.get("ik"):
            continue
        text = describe_ik(stelle["ik"])
        if stelle.get("art_text"):
            text += f" [{stelle['art_text']}]"
        zeilen.append(f"{beschriftung}: {text}")

    return zeilen


def annahmestelle(ik: Any, art: str = "dfu") -> Dict[str, str]:
    """
    Die Datenannahmestelle zu einem Kostenträger-IK. 'art' ist 'dfu'
    (Datenfernübertragung), 'papier' oder 'zahlung'.
    """
    stelle = (kostentraeger(ik).get("annahmestelle") or {}).get(art)
    return dict(stelle) if isinstance(stelle, dict) else {}


# ---------------------------------------------------------------------------
# Verordnungsbedarf zum ICD-Code
# ---------------------------------------------------------------------------

def normalisiere_icd(code: Any) -> Tuple[str, str]:
    """
    Trennt einen ICD-Code aus dem DIA-Segment in Code und Diagnosesicherheit.

        'F90.0 G' -> ('F90.0', 'G')
        'F89G'    -> ('F89',   'G')
        'G35.30'  -> ('G35.30', '')

    Passt der Wert nicht auf das ICD-Muster, wird er unverändert als Code
    zurückgegeben — geraten wird nicht.
    """
    if code is None:
        return "", ""
    text = " ".join(str(code).split())
    if not text:
        return "", ""
    treffer = _ICD_MUSTER.match(text)
    if not treffer:
        return text, ""
    return treffer.group(1).upper(), (treffer.group(2) or "").upper()


def _icd_kandidaten(icd: str) -> List[str]:
    """
    Suchreihenfolge für einen ICD-Code, von der genauesten zur allgemeinsten
    Form. Zu jeder Stufe wird auch die Schreibweise mit Endstellen-Platzhalter
    probiert, weil die Stammdatei beides führt (G35.1 und G35.1-).

        'G35.30' -> G35.30, G35.30-, G35.3, G35.3-, G35, G35.-
        'G35'    -> G35, G35.-

    Ein Schlüssel wie 'G35' in der Stammdatei gilt für die ganze Gruppe —
    deshalb ist das Aufsteigen zur Oberform kein Raten, sondern die
    beabsichtigte Lesart.
    """
    basis = icd.rstrip("-+*")
    stufen = [basis]
    if "." in basis:
        vor, _, nach = basis.partition(".")
        for laenge in range(len(nach) - 1, 0, -1):
            stufen.append(f"{vor}.{nach[:laenge]}")
        stufen.append(vor)

    kandidaten = [icd]
    for stufe in stufen:
        kandidaten.append(stufe)
        kandidaten.append(stufe + "-" if "." in stufe else stufe + ".-")
    return list(dict.fromkeys(k for k in kandidaten if k))


def _bedarf_eintraege(icd: str) -> List[Dict[str, Any]]:
    tabelle = load_verordnungsbedarf().get("icd")
    if not isinstance(tabelle, dict):
        return []
    eintraege = tabelle.get(icd)
    return eintraege if isinstance(eintraege, list) else []


def verordnungsbedarf(code: Any) -> Dict[str, Any]:
    """
    Sucht einen ICD-Code in der KBV-Stammdatei Heilmittelanlagen.

    Die Stammdatei führt die Codes endstellengenau (G35.0, G35.1-, G35.30).
    Im DIA-Segment steht teils nur die Gruppe (G35). Deshalb drei Stufen:

      1. exakter Treffer
      2. Endstellen abschneiden (G35.30 -> G35.3- -> G35.3 -> G35)
      3. Unterformen einsammeln (G35 -> G35.0, G35.1-, ...) und melden, ob
         alle Unterformen dieselbe Anlage tragen

    Rückgabe:
      icd           — normalisierter Code
      sicherheit    — Zusatzkennzeichen der Diagnosesicherheit ('G','V','A','Z')
      treffer       — Einträge zum gefundenen Code (Liste, kann leer sein)
      quelle_code   — Code, unter dem die Treffer gefunden wurden
      genau         — True bei exaktem Treffer, False bei Ober-/Unterform
      unterformen   — {Code: Einträge} bei Stufe 3
      anlagen       — vorkommende Anlagen-Schlüssel, z. B. ['LHM']
      text          — anzeigefertiger Einzeiler, '' wenn nichts gefunden wurde
    """
    icd, sicherheit = normalisiere_icd(code)
    ergebnis: Dict[str, Any] = {
        "icd": icd, "sicherheit": sicherheit, "treffer": [], "quelle_code": "",
        "genau": False, "unterformen": {}, "anlagen": [], "text": "",
    }
    if not icd:
        return ergebnis

    # Stufe 1 und 2: exakt, dann Endstellen abschneiden
    for kandidat in _icd_kandidaten(icd):
        eintraege = _bedarf_eintraege(kandidat)
        if eintraege:
            ergebnis["treffer"] = eintraege
            ergebnis["quelle_code"] = kandidat
            ergebnis["genau"] = kandidat == ergebnis["icd"]
            break

    # Stufe 3: Unterformen einsammeln
    if not ergebnis["treffer"]:
        tabelle = load_verordnungsbedarf().get("icd")
        if isinstance(tabelle, dict):
            praefix = ergebnis["icd"].rstrip("-+*") + "."
            unterformen = {
                k: v for k, v in tabelle.items()
                if k.startswith(praefix) and isinstance(v, list) and v
            }
            if unterformen:
                ergebnis["unterformen"] = unterformen

    anlagen: List[str] = []
    for eintraege in [ergebnis["treffer"]] + list(ergebnis["unterformen"].values()):
        for eintrag in eintraege:
            anlage = str(eintrag.get("anlage", "")).strip()
            if anlage and anlage not in anlagen:
                anlagen.append(anlage)
    ergebnis["anlagen"] = anlagen

    ergebnis["text"] = _bedarf_text(ergebnis)
    return ergebnis


def _bedarf_text(ergebnis: Dict[str, Any]) -> str:
    """Anzeigefertiger Einzeiler zum Ergebnis von verordnungsbedarf()."""
    if not ergebnis["anlagen"]:
        return ""

    anlagentexte: List[str] = []
    for eintraege in [ergebnis["treffer"]] + list(ergebnis["unterformen"].values()):
        for eintrag in eintraege:
            text = str(eintrag.get("anlage_text") or eintrag.get("anlage") or "").strip()
            if text and text not in anlagentexte:
                anlagentexte.append(text)

    text = " / ".join(anlagentexte)

    if ergebnis["treffer"] and not ergebnis["genau"]:
        text += f" — Eintrag zur Oberform {ergebnis['quelle_code']}"
    elif ergebnis["unterformen"]:
        anzahl = len(ergebnis["unterformen"])
        beispiele = ", ".join(sorted(ergebnis["unterformen"])[:4])
        text += (f" — nicht für {ergebnis['icd']} selbst, aber für "
                 f"{anzahl} Unterform{'en' if anzahl != 1 else ''} ({beispiele}"
                 f"{', ...' if anzahl > 4 else ''})")
    return text


def verordnungsbedarf_zeilen(code: Any) -> List[str]:
    """
    Mehrzeilige Auskunft zum Verordnungsbedarf eines ICD-Codes, für Bericht,
    Ticket-Zusammenfassung und den Rezept-Baum. Leere Liste, wenn der Code
    nicht in der Stammdatei steht.
    """
    ergebnis = verordnungsbedarf(code)
    if not ergebnis["text"]:
        return []

    zeilen = [ergebnis["text"]]
    for eintrag in ergebnis["treffer"]:
        if eintrag.get("hinweis"):
            zeilen.append(str(eintrag["hinweis"]))
        for kapitel in eintrag.get("kapitel", []):
            gruppen = ", ".join(kapitel.get("diagnosegruppen", []))
            bereich = str(kapitel.get("bereich", "")).strip()
            if bereich and gruppen:
                zeilen.append(f"{bereich}: {gruppen}")
            elif gruppen:
                zeilen.append(f"Diagnosegruppen: {gruppen}")
        if eintrag.get("alter_ab") or eintrag.get("alter_bis"):
            grenzen = " ".join(p for p in [
                f"ab {eintrag['alter_ab']}" if eintrag.get("alter_ab") else "",
                f"bis {eintrag['alter_bis']}" if eintrag.get("alter_bis") else "",
            ] if p)
            zeilen.append(f"Altersgrenze: {grenzen}")
        if eintrag.get("zeitraum_akutereignis"):
            zeilen.append(f"Zeitraum nach Akutereignis: {eintrag['zeitraum_akutereignis']}")
        if eintrag.get("sekundaercode"):
            zeilen.append("Sekundärcode: " + ", ".join(eintrag["sekundaercode"]))
        if eintrag.get("geltungsbereich_kv"):
            zeilen.append("Nur in KV-Bereich "
                          + ", ".join(eintrag["geltungsbereich_kv"]))

    stand = _quelle_info(_verordnungsbedarf).get("gueltig", "")
    if stand:
        zeilen.append(f"Stand der Stammdatei: {stand}")
    return zeilen


# ---------------------------------------------------------------------------
# Anzeigefertige Kombinationen
# ---------------------------------------------------------------------------

def describe(liste: str, code: Any, leer_text: str = "—") -> str:
    """
    Anzeigefertige Kombination aus Code und Klartext:
      '05 — Blankoverordnung'          (Klartext hinterlegt)
      '05 (kein Klartext hinterlegt)'  (nichts hinterlegt)
      '—'                              (Feld leer)
    """
    key = "" if code is None else str(code).strip()
    if not key:
        return leer_text
    text = lookup(liste, key)
    return f"{key} — {text}" if text else f"{key} ({KEIN_KLARTEXT})"


def describe_position(code: Any, abrechnungscode: Any = None, leer_text: str = "—") -> str:
    """Anzeigefertige Kombination aus Positionsnummer und Klartext."""
    key = "" if code is None else str(code).strip()
    if not key:
        return leer_text
    text = lookup_position(key, abrechnungscode)
    return f"{key} — {text}" if text else f"{key} ({KEIN_KLARTEXT})"


def describe_diagnosegruppe(code: Any, leer_text: str = "—") -> str:
    """
    Wie describe('diagnosegruppe', ...), ergänzt aber den Heilmittelbereich:
      'EN3 — Periphere Nervenläsionen / Muskelerkrankungen [Ergotherapie]'
    """
    key = "" if code is None else str(code).strip()
    if not key:
        return leer_text
    info = diagnosegruppe_info(key)
    if not info["bezeichnung"]:
        return f"{key} ({KEIN_KLARTEXT})"
    text = f"{key} — {info['bezeichnung']}"
    kurz = bereich_kurz(info.get("bereich", ""))
    if kurz:
        text += f"  [{kurz}]"
    return text


def bereich_kurz(bereich: Any) -> str:
    """
    'Maßnahmen der Podologischen Therapie' -> 'Podologie'. Unbekannte
    Bezeichnungen werden unverändert zurückgegeben.
    """
    text = "" if bereich is None else str(bereich).strip()
    if not text:
        return ""
    return _BEREICH_KURZ.get(text, text)
