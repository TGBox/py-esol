#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List


def collect_files(directory: Path) -> List[Path]:
    """Rekursives Sammeln aller Dateien ohne Dateiendung."""
    files = [
        p for p in directory.rglob("*") if p.is_file() and p.suffix == ""
    ]
    return sorted(files)


def main() -> None:
    base_script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Batch Validator — Rekursive Validierung aller Dateien ohne Erweiterung",
        add_help=False,
    )
    parser.add_argument(
        "--dir",
        default="data_batch",
        help="Verzeichnis zum Scannen (Standard: data_batch)",
    )
    parser.add_argument(
        "--stufe",
        type=int,
        default=4,
        help="--stufe=N an validate.py übergeben (Standard: 4)",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Ausgabedatei für Report (Standard: data_batch/validation_report.txt)",
    )
    parser.add_argument(
        "-h", "--help", action="store_true", help="Diese Hilfe anzeigen"
    )

    args = parser.parse_args()

    if args.help:
        parser.print_help()
        sys.exit(0)

    dir_path = Path(args.dir)
    if not dir_path.is_absolute():
        dir_path = base_script_dir / dir_path

    if not dir_path.is_dir():
        print(f"Fehler: Verzeichnis nicht gefunden: {dir_path}", file=sys.stderr)
        sys.exit(2)

    report_path = (
        Path(args.report)
        if args.report
        else dir_path / "validation_report.txt"
    )

    validate_script = base_script_dir / "validate.py"
    if not validate_script.is_file():
        print(
            f"Fehler: validate.py nicht gefunden: {validate_script}",
            file=sys.stderr,
        )
        sys.exit(2)

    files = collect_files(dir_path)

    if not files:
        print(f"Keine Dateien ohne Erweiterung in {dir_path} gefunden.")
        sys.exit(0)

    total_files = len(files)
    print(f"Gefunden: {total_files} Datei(en) ohne Erweiterung in {dir_path}")
    print("=" * 60 + "\n")

    report: List[str] = [
        "ESOL Batch-Validierungsreport",
        f"Erstellt: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Verzeichnis: {dir_path}",
        f"Prüfstufe: {args.stufe}",
        "=" * 70,
        "",
    ]

    valid_count = 0
    invalid_count = 0
    error_total = 0
    warning_total = 0

    for index, file_path in enumerate(files, start=1):
        try:
            relative_path = file_path.relative_to(dir_path)
        except ValueError:
            relative_path = file_path

        print(
            f"[{index}/{total_files}] Validiere: {relative_path} ... ",
            end="",
            flush=True,
        )

        cmd = [
            sys.executable,
            str(validate_script),
            str(file_path),
            f"--stufe={args.stufe}",
            "--format=json",
        ]

        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )

        try:
            data = json.loads(proc.stdout)
        except (json.JSONDecodeError, TypeError):
            print("PARSE-FEHLER")
            report.extend(
                [
                    f"Datei: {relative_path}",
                    "  Status: PARSE-FEHLER — Ausgabe konnte nicht gelesen werden",
                    f"  Rohausgabe: {proc.stdout.strip() or '(leer)'}",
                    "",
                ]
            )
            invalid_count += 1
            continue

        file_errors = data.get("errorCount", 0)
        file_warnings = data.get("warningCount", 0)
        is_valid = data.get("valid", False)

        if is_valid:
            print("OK")
            valid_count += 1
        else:
            print(f"UNGÜLTIG ({file_errors} Fehler)")
            invalid_count += 1

        error_total += file_errors
        warning_total += file_warnings

        if not is_valid and data.get("errors"):
            report.append(f"Datei: {relative_path}")
            report.append(f"  Status: UNGÜLTIG | Fehler: {file_errors}")

            for err in data["errors"]:
                code = err.get("code", "?")
                segment = err.get("segment", "")
                seg_idx = err.get("segmentIndex")
                message = err.get("message", "")

                location = segment
                if seg_idx is not None:
                    location += f" (Position {seg_idx})"

                report.append(f"    FEHLER [{code}] {location}: {message}")

            report.append("")

    report.extend(
        [
            "=" * 70,
            "ZUSAMMENFASSUNG",
            "-" * 70,
            f"Dateien geprüft:   {total_files}",
            f"Gültig:            {valid_count}",
            f"Ungültig:          {invalid_count}",
            f"Fehler gesamt:     {error_total}",
            "=" * 70,
        ]
    )

    report_path.write_text("\n".join(report) + "\n", encoding="ISO-8859-1")

    print("\n" + "=" * 60)
    print(
        f"Zusammenfassung: {valid_count} gültig, {invalid_count} ungültig ({error_total} Fehler)"
    )
    print(f"Report geschrieben: {report_path}")

    sys.exit(1 if invalid_count > 0 else 0)


if __name__ == "__main__":
    main()