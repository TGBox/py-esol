"""
Codelisten-Loader — lädt die editierbaren Klartext-Tabellen aus data/codelisten.json.

Die Datei ist bewusst extern gehalten, damit Bezeichnungen (Verordnungsart, Diagnosegruppe,
Positionsnummern, ...) ohne neues Release gepflegt werden können.

Grundregel: ist zu einem Code KEIN Klartext hinterlegt, wird NICHTS geraten. Die
Anzeige zeigt dann nur den Code plus einen Hinweis, dass kein Klartext hinterlegt ist.
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

_cache: Optional[Dict[str, Any]] = None
_loaded_from: Optional[Path] = None
_load_error: Optional[str] = None


def _candidate_paths() -> list[Path]:
    """
    Mögliche Ablageorte der Codelisten — funktioniert im Entwicklungsbaum ebenso wie
    im per PyInstaller gebauten One-File-Exe (sys._MEIPASS).
    """
    paths: list[Path] = []

    # 1. Neben der ausführbaren Datei / im Arbeitsverzeichnis (erlaubt Pflege beim Kunden)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        paths.append(exe_dir / "data" / _CODELIST_FILENAME)
        paths.append(exe_dir / _CODELIST_FILENAME)

    # 2. PyInstaller-Bundle-Verzeichnis
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        paths.append(Path(meipass) / "data" / _CODELIST_FILENAME)
        paths.append(Path(meipass) / _CODELIST_FILENAME)

    # 3. Projektbaum (Entwicklung)
    here = Path(__file__).resolve().parent
    paths.append(here / "data" / _CODELIST_FILENAME)

    # 4. Explizite Überschreibung per Umgebungsvariable
    env_path = os.environ.get("PY_ESOL_CODELISTEN")
    if env_path:
        paths.insert(0, Path(env_path))

    return paths


def load(force: bool = False) -> Dict[str, Any]:
    """
    Lädt die Codelisten (gecacht). force=True erzwingt ein Neuladen von der Platte.
    Fehlt oder ist die Datei defekt, wird ein leeres Dict zurückgegeben — die Anwendung
    bleibt funktionsfähig, es werden dann lediglich keine Klartexte angezeigt.
    """
    global _cache, _loaded_from, _load_error

    if _cache is not None and not force:
        return _cache

    _load_error = None
    for path in _candidate_paths():
        try:
            if not path.is_file():
                continue
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                raise ValueError("Wurzelelement ist kein JSON-Objekt")
            _cache = data
            _loaded_from = path
            return _cache
        except Exception as exc:  # defekte Datei darf die GUI nicht abschießen
            _load_error = f"{path}: {exc}"
            continue

    _cache = {}
    _loaded_from = None
    return _cache


def reload() -> Dict[str, Any]:
    """Erzwingt das Neuladen der Codelisten (Button 'Codelisten neu laden')."""
    return load(force=True)


def source_path() -> Optional[Path]:
    """Pfad, aus dem die Codelisten geladen wurden (None = keine Datei gefunden)."""
    load()
    return _loaded_from


def last_error() -> Optional[str]:
    """Letzter Ladefehler, falls eine gefundene Datei nicht gelesen werden konnte."""
    load()
    return _load_error


def lookup(liste: str, code: Any, default: str = "") -> str:
    """
    Sucht den Klartext zu einem Code. Gibt '' zurück, wenn kein Klartext hinterlegt ist.
    Es wird NIE ein Wert geraten oder abgeleitet.
    """
    if code is None:
        return default
    key = str(code).strip()
    if not key:
        return default
    table = load().get(liste)
    if not isinstance(table, dict):
        return default
    value = table.get(key)
    if value is None:
        # Führende Nullen tolerieren (z. B. '3' vs. '03')
        value = table.get(key.lstrip("0")) or table.get(key.zfill(2))
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def lookup_position(code: Any, abrechnungscode: Any = None, default: str = "") -> str:
    """
    Klartext zu einer Abrechnungspositionsnummer. Zuerst wird die nach Abrechnungscode
    gestaffelte Tabelle geprüft, danach die allgemeine Tabelle unter '*'.
    """
    if code is None:
        return default
    key = str(code).strip()
    if not key:
        return default

    table = load().get("positionsnummern")
    if not isinstance(table, dict):
        return default

    for bucket in (str(abrechnungscode).strip() if abrechnungscode else None, "*"):
        if not bucket:
            continue
        sub = table.get(bucket)
        if isinstance(sub, dict):
            value = sub.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    # Rückfall: flache Tabelle ohne Staffelung nach Abrechnungscode
    value = table.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()

    return default


def describe(liste: str, code: Any, leer_text: str = "—") -> str:
    """
    Anzeigefertige Kombination aus Code und Klartext:
      '05 — Blankoverordnung'   (Klartext hinterlegt)
      '05 (kein Klartext hinterlegt)'  (nichts hinterlegt)
      '—'                       (Feld leer)
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
