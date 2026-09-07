"""
Codelisten-Loader — lädt die Klartext-Tabellen für die Verordnungs-Anzeige.

Zwei Quellen, in dieser Rangfolge:

  1. data/codelisten.json      — von Hand gepflegt, hat immer Vorrang.
  2. data/heilmittelpreise.json — aus der Heilmittelpreisstammdatei des
     GKV-Spitzenverbands erzeugt (siehe tools/import_hmp.py). Wird bei jedem
     Import überschrieben und ist deshalb nicht zum Bearbeiten gedacht.

Grundregel: ist zu einem Code in keiner Quelle ein Klartext hinterlegt, wird
NICHTS geraten. Die Anzeige zeigt dann nur den Code plus einen Hinweis.

Zur maskierten ersten Stelle: Die Stammdatei führt Positionen nach § 125
(Regelversorgung) mit 'X' als erster Stelle — X4103 statt 54103. In der
Abrechnung steht dort die Stelle des Heilmittelbereichs. Beim Nachschlagen wird
deshalb zusätzlich 'X' + Rest probiert. Belegt an den Testdaten: alle acht
Positionen mit Tarifkennzeichen 00501, die als 5xxxx abgerechnet werden, finden
sich in der Stammdatei als X-Code wieder.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Marker, der in der GUI erscheint, wenn zu einem Code kein Klartext hinterlegt ist.
KEIN_KLARTEXT = "kein Klartext hinterlegt"

_CODELIST_FILENAME = "codelisten.json"
_HMP_FILENAME = "heilmittelpreise.json"

# Umgebungsvariablen zum Erzwingen eines Pfades (praktisch für Tests)
_ENV_CODELISTEN = "PY_ESOL_CODELISTEN"
_ENV_HMP = "PY_ESOL_HEILMITTELPREISE"


class _Quelle:
    """Eine JSON-Datei mit Klartexten, gecacht und mit Ladefehler-Protokoll."""

    def __init__(self, dateiname: str, env_var: str):
        self.dateiname = dateiname
        self.env_var = env_var
        self._daten: Optional[Dict[str, Any]] = None
        self._pfad: Optional[Path] = None
        self._fehler: Optional[str] = None

    def _kandidaten(self) -> list[Path]:
        """
        Mögliche Ablageorte — funktioniert im Entwicklungsbaum ebenso wie im
        per PyInstaller gebauten One-File-Exe (sys._MEIPASS).
        """
        pfade: list[Path] = []

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


# ---------------------------------------------------------------------------
# Laden / Zustand
# ---------------------------------------------------------------------------

def load(force: bool = False) -> Dict[str, Any]:
    """Die handgepflegten Codelisten (gecacht)."""
    return _codelisten.load(force=force)


def load_hmp(force: bool = False) -> Dict[str, Any]:
    """Die aus der GKV-Stammdatei importierten Positionsbezeichnungen."""
    return _hmp.load(force=force)


def reload() -> Dict[str, Any]:
    """Erzwingt das Neuladen beider Quellen (Button 'Codelisten neu laden')."""
    _hmp.load(force=True)
    return _codelisten.load(force=True)


def source_path() -> Optional[Path]:
    """Pfad der handgepflegten Codelisten (None = keine Datei gefunden)."""
    return _codelisten.pfad


def hmp_source_path() -> Optional[Path]:
    """Pfad der importierten Heilmittelpreis-Bezeichnungen."""
    return _hmp.pfad


def last_error() -> Optional[str]:
    """Letzter Ladefehler einer der beiden Quellen."""
    return _codelisten.fehler or _hmp.fehler


def hmp_info() -> Dict[str, Any]:
    """
    Metadaten des letzten HMP-Imports: Quelldatei, Version, Anzahl Positionen,
    Heilmittelbereiche, Gültigkeitsstände. Leeres Dict, wenn nichts geladen ist.
    """
    quelle = load_hmp().get("_quelle")
    return quelle if isinstance(quelle, dict) else {}


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


# ---------------------------------------------------------------------------
# Nachschlagen
# ---------------------------------------------------------------------------

def lookup(liste: str, code: Any, default: str = "") -> str:
    """
    Sucht den Klartext zu einem Code. Gibt '' zurück, wenn kein Klartext
    hinterlegt ist. Es wird NIE ein Wert geraten oder abgeleitet.
    """
    if code is None:
        return default
    key = str(code).strip()
    if not key:
        return default
    tabelle = load().get(liste)
    if not isinstance(tabelle, dict):
        return default
    wert = tabelle.get(key)
    if wert is None:
        # Führende Nullen tolerieren (z. B. '3' vs. '03')
        wert = tabelle.get(key.lstrip("0")) or tabelle.get(key.zfill(2))
    if isinstance(wert, str) and wert.strip():
        return wert.strip()
    return default


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
    if code is None:
        return {}
    key = str(code).strip()
    if not key:
        return {}

    positionen = load_hmp().get("positionen")
    if not isinstance(positionen, dict):
        return {}

    for kandidat in (key, "X" + key[1:] if len(key) > 1 else None):
        if not kandidat:
            continue
        eintrag = positionen.get(kandidat)
        if isinstance(eintrag, dict) and str(eintrag.get("bezeichnung", "")).strip():
            ergebnis = dict(eintrag)
            ergebnis["hmp_code"] = kandidat
            return ergebnis
    return {}


def position_info(code: Any, abrechnungscode: Any = None) -> Dict[str, str]:
    """
    Vollständige Auskunft zu einer Positionsnummer:
      bezeichnung — Klartext oder ''
      quelle      — 'codelisten' | 'hmp' | ''
      bereich     — Heilmittelbereich (nur bei Quelle 'hmp')
      grundlage   — '125' | '125a' | '' (nur bei Quelle 'hmp')
      gueltig_ab  — Gültigkeitsdatum (nur bei Quelle 'hmp')
      hmp_code    — Code in der Stammdatei, falls über die X-Maske gefunden
    """
    leer = {"bezeichnung": "", "quelle": "", "bereich": "", "grundlage": "",
            "gueltig_ab": "", "hmp_code": ""}
    if code is None:
        return leer
    key = str(code).strip()
    if not key:
        return leer

    eigene = _aus_codelisten(key, abrechnungscode)
    if eigene:
        return {**leer, "bezeichnung": eigene, "quelle": "codelisten"}

    eintrag = hmp_position(key)
    if eintrag:
        return {
            "bezeichnung": eintrag.get("bezeichnung", ""),
            "quelle": "hmp",
            "bereich": eintrag.get("bereich", ""),
            "grundlage": eintrag.get("grundlage", ""),
            "gueltig_ab": eintrag.get("gueltig_ab", ""),
            "hmp_code": eintrag.get("hmp_code", ""),
        }

    return leer


def lookup_position(code: Any, abrechnungscode: Any = None, default: str = "") -> str:
    """
    Klartext zu einer Abrechnungspositionsnummer. Reihenfolge: eigene Pflege in
    codelisten.json, dann die GKV-Stammdatei (direkt, dann über die X-Maske).
    """
    bezeichnung = position_info(code, abrechnungscode).get("bezeichnung", "")
    return bezeichnung or default


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
