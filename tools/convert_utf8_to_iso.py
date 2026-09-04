#!/usr/bin/env python3
"""
ESOL File Encoding Converter — Konvertiert ESOL-Dateien von UTF-8 zu ISO-8859-15 (oder ISO-8859-1).

Der Dateiname bleibt dabei immer unverändert — ESOL-Dateien tragen bewusst keine
Endung und der Name ist Teil der Einreichung. Ohne --out-dir (oder wenn das
Zielverzeichnis dem Quellverzeichnis entspricht) wird die Datei an ihrem Platz
ersetzt; das Schreiben erfolgt atomar, damit ein Abbruch das Original nicht
beschädigt.

Nutzung:
  python convert_utf8_to_iso.py [Pfade ...] [Optionen]

Beispiele:
  python convert_utf8_to_iso.py ordner/                                  # ersetzt die Dateien im Ordner
  python convert_utf8_to_iso.py testdata/in/ESOL0253                      # ersetzt genau diese Datei
  python convert_utf8_to_iso.py datei1 datei2 --out-dir konvertiert/       # Kopien mit gleichem Namen
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Tuple

# Namensmuster der temporären Schreibdatei, in die convert_file zuerst schreibt
_TMP_MARKER = ".convert-tmp-"


def convert_file(
    src_path: Path,
    dst_path: Path,
    source_encoding: str = "utf-8",
    target_encoding: str = "iso-8859-15",
    errors_strategy: str = "replace",
) -> Tuple[bool, str]:
    """
    Konvertiert eine einzelne Datei von Quell-Kodierung (UTF-8) zu Ziel-Kodierung (ISO-8859-15).
    Verwendet eine intelligente Dekodierungs-Logik, um bereits im Ziel-Encoding vorliegende
    oder UTF-8-kodierte Dateien ohne Zeichenverlust oder Formatierungsänderungen zu verarbeiten.

    Gibt (Erfolg: bool, Nachricht: str) zurück.
    """
    try:
        if not src_path.is_file():
            return False, f"Datei nicht gefunden: {src_path}"

        if dst_path.is_dir():
            dst_path = dst_path / src_path.name

        raw_bytes = src_path.read_bytes()

        # Intelligente Dekodierung mit Fehlererkennung
        content = None

        # 1. Versuche Quell-Encoding (standardmäßig UTF-8) strikt zu dekodieren
        try:
            content = raw_bytes.decode(source_encoding)
        except UnicodeDecodeError:
            pass

        # 2. Falls Fehlschlag, versuche Ziel-Encoding (z. B. ISO-8859-15) strikt zu dekodieren
        if content is None and target_encoding.lower() != source_encoding.lower():
            try:
                content = raw_bytes.decode(target_encoding)
            except UnicodeDecodeError:
                pass

        # 3. Falls weiterhin Fehlschlag, versuche kompatible Encodings (ISO-8859-1, CP1252)
        if content is None:
            for fallback in ("iso-8859-1", "cp1252"):
                try:
                    content = raw_bytes.decode(fallback)
                    break
                except UnicodeDecodeError:
                    pass

        # 4. Letzter Ausweg: Quell-Encoding mit Replace-Strategie
        if content is None:
            content = raw_bytes.decode(source_encoding, errors="replace")

        # Zielverzeichnis bei Bedarf erstellen
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        ersetzt_original = dst_path.resolve() == src_path.resolve()

        # Erst in eine temporäre Datei im Zielverzeichnis schreiben und danach
        # atomar umbenennen. Das ist wichtig, weil die Datei üblicherweise an
        # ihrer Originalstelle ersetzt wird: bricht das Schreiben ab (voller
        # Datenträger, Virenscanner, Netzlaufwerk weg), bleibt die
        # Ursprungsdatei unversehrt statt halb überschrieben liegen zu bleiben.
        tmp_path = dst_path.with_name(f"{dst_path.name}{_TMP_MARKER}{os.getpid()}")
        try:
            # newline="" bewahrt die ursprünglichen Zeilenumbrüche (\r\n bzw. \n)
            with open(tmp_path, "w", encoding=target_encoding, errors=errors_strategy, newline="") as f:
                f.write(content)
            os.replace(tmp_path, dst_path)
        except Exception:
            try:
                tmp_path.unlink()
            except OSError:
                pass
            raise

        if ersetzt_original:
            return True, f"Erfolgreich konvertiert (Original ersetzt): {dst_path}"
        return True, f"Erfolgreich konvertiert -> {dst_path}"
    except Exception as e:
        return False, f"Fehler bei Konvertierung von {src_path}: {e}"


def collect_files(path: Path, recurse: bool = True) -> List[Path]:
    """
    Sammelt alle Dateien aus einem Pfad oder Verzeichnis.
    Liegengebliebene temporäre Schreibdateien eines abgebrochenen Laufs
    werden übersprungen.
    """
    def brauchbar(p: Path) -> bool:
        return p.is_file() and _TMP_MARKER not in p.name

    if path.is_file():
        return [path] if brauchbar(path) else []
    elif path.is_dir():
        pattern = path.rglob("*") if recurse else path.glob("*")
        return sorted([p for p in pattern if brauchbar(p)])
    return []


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="ESOL Encoding Converter — Konvertiert ESOL-Dateien von UTF-8 zu ISO-8859-15 / ISO-8859-1"
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Dateien oder Ordner, die konvertiert werden sollen",
    )
    parser.add_argument(
        "--dir",
        "-d",
        default=None,
        help="Eingabeverzeichnis für Konvertierung",
    )
    parser.add_argument(
        "--out-dir",
        "-o",
        default=None,
        help="Zielverzeichnis für konvertierte Dateien",
    )
    parser.add_argument(
        "--inplace",
        "-i",
        action="store_true",
        help="Ohne Wirkung — das Ersetzen am Originalort ist das Standardverhalten. "
             "Nur aus Kompatibilitätsgründen erhalten.",
    )
    parser.add_argument(
        "--encoding",
        "-e",
        default="iso-8859-15",
        choices=["iso-8859-15", "iso-8859-1", "cp1252"],
        help="Ziel-Kodierung (Standard: iso-8859-15)",
    )
    parser.add_argument(
        "--source-encoding",
        default="utf-8",
        help="Quell-Kodierung (Standard: utf-8)",
    )

    args = parser.parse_args()

    input_paths: List[Path] = []

    if args.dir:
        input_paths.append(Path(args.dir))

    for p in args.paths:
        input_paths.append(Path(p))

    if not input_paths:
        print("Hinweis: Keine Pfade angegeben.")
        parser.print_help()
        sys.exit(0)

    all_files: List[Path] = []
    for ip in input_paths:
        all_files.extend(collect_files(ip))

    if not all_files:
        print("Keine Dateien zur Konvertierung gefunden.")
        sys.exit(0)

    print(f"Starte Konvertierung von {len(all_files)} Datei(en) nach {args.encoding.upper()}...")
    print("=" * 65)

    converted_count = 0
    error_count = 0

    out_dir_path = Path(args.out_dir) if args.out_dir else None

    for index, src_file in enumerate(all_files, start=1):
        # Der Dateiname bleibt in JEDEM Fall unverändert. ESOL-Dateien tragen
        # bewusst keine Endung (ESOL0253) und der Name gehört zur Einreichung —
        # eine angehängte Endung würde die Datei beim Abrechnungszentrum
        # unbrauchbar machen. Zeigt das Ziel auf die Quelle, wird die Datei an
        # ihrem Platz ersetzt (convert_file schreibt dafür atomar).
        if out_dir_path:
            if input_paths and input_paths[0].is_file():
                rel = Path(src_file.name)
            else:
                try:
                    rel = src_file.relative_to(input_paths[0])
                except (ValueError, IndexError):
                    rel = Path(src_file.name)
            dst_file = out_dir_path / rel
            if dst_file.is_dir() or str(rel) == ".":
                dst_file = out_dir_path / src_file.name
        else:
            dst_file = src_file

        success, msg = convert_file(
            src_path=src_file,
            dst_path=dst_file,
            source_encoding=args.source_encoding,
            target_encoding=args.encoding,
        )

        if success:
            converted_count += 1
            print(f"[{index}/{len(all_files)}] OK: {src_file} -> {dst_file}")
        else:
            error_count += 1
            print(f"[{index}/{len(all_files)}] FEHLER: {msg}", file=sys.stderr)

    print("=" * 65)
    print(f"Abgeschlossen: {converted_count} erfolgreich konvertiert, {error_count} Fehler.")


if __name__ == "__main__":
    main()
