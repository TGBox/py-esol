"""
Kostenträger-Loader — Lädt die Zuordnung von Institutionskennzeichen (IK)
zu den Namen der Krankenkassen und Kostenträger aus data/kostentraeger.json.

Getrennt von medizinischen Leistungscodes (codelisten.json), da IKs Institutionsdaten
und keine Leistungskatalog-Schlüssel darstellen.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_FILENAME = "kostentraeger.json"
_cache: Optional[Dict[str, str]] = None
_loaded_from: Optional[Path] = None


def _candidate_paths() -> list[Path]:
    paths: list[Path] = []

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        paths.append(exe_dir / "data" / _FILENAME)
        paths.append(exe_dir / _FILENAME)

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        paths.append(Path(meipass) / "data" / _FILENAME)
        paths.append(Path(meipass) / _FILENAME)

    here = Path(__file__).resolve().parent
    paths.append(here / "data" / _FILENAME)

    env_path = os.environ.get("PY_ESOL_KOSTENTRAEGER")
    if env_path:
        paths.insert(0, Path(env_path))

    return paths


def load(force: bool = False) -> Dict[str, str]:
    """Lädt das IK-zu-Name Dictionary (gecacht)."""
    global _cache, _loaded_from

    if _cache is not None and not force:
        return _cache

    for path in _candidate_paths():
        try:
            if not path.is_file():
                continue
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if not isinstance(data, dict):
                continue
            # Hinweis-Schlüssel filtern
            _cache = {str(k).strip(): str(v).strip() for k, v in data.items() if not str(k).startswith("_")}
            _loaded_from = path
            return _cache
        except Exception:
            continue

    _cache = {}
    _loaded_from = None
    return _cache


def lookup(ik: Any, default: str = "") -> str:
    """Sucht den Namen des Kostenträgers / der Krankenkasse anhand der IK."""
    if ik is None:
        return default
    key = str(ik).strip()
    if not key:
        return default
    table = load()
    val = table.get(key)
    if val:
        return val
    # Toleranz für führende Nullen bzw. 9-stellige IKs
    val = table.get(key.zfill(9))
    if val:
        return val
    return default


def get_name_or_fallback(ik: Any) -> str:
    """Gibt den Namen zurück oder 'Krankenkasse (IK <Nummer>)' bzw. 'Krankenkasse'."""
    key = "" if ik is None else str(ik).strip()
    if not key:
        return "Krankenkasse"
    name = lookup(key)
    if name:
        return name
    return f"Krankenkasse (IK {key})"
