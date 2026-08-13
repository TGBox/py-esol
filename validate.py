#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from esol_validator import EsolValidator
from validation_error import ValidationError
from validation_result import ValidationResult


def output_text(
    file_path: str, result: ValidationResult, max_stufe: int
) -> None:
    print(f"Validierung: {file_path}")
    print("-" * 60)

    for stufe in range(1, max_stufe + 1):
        stufe_findings = result.get_by_stufe(stufe)
        stufe_errors = [e for e in stufe_findings if e.is_error()]
        stufe_warnings = [e for e in stufe_findings if e.is_warning()]

        if not stufe_findings:
            print(f"Prüfstufe {stufe}: OK")
        else:
            parts = []
            if stufe_errors:
                parts.append(f"{len(stufe_errors)} Fehler")
            if stufe_warnings:
                parts.append(f"{len(stufe_warnings)} Warnungen")
            print(f"Prüfstufe {stufe}: {', '.join(parts)}")

        # Stop reporting if Stufe failed and is <= 2
        if result.has_stufe_errors(stufe) and stufe <= 2:
            break

    print()

    all_findings = result.get_all()
    for finding in all_findings:
        prefix = "  FEHLER" if finding.is_error() else "  WARNUNG"
        location = ""
        if finding.segment:
            pos = (
                f" (Position {finding.segment_index})"
                if finding.segment_index is not None
                else ""
            )
            location = f" {finding.segment}{pos}"

        print(f"{prefix} [{finding.code}]{location}: {finding.message}")

    if all_findings:
        print()

    error_count = result.error_count()
    warning_count = result.warning_count()
    status = "GÜLTIG" if result.is_valid() else "UNGÜLTIG"
    print(f"Ergebnis: {status} ({error_count} Fehler, {warning_count} Warnungen)")


def output_json(
    file_path: str, result: ValidationResult, max_stufe: int
) -> None:
    errors = [
        {
            "stufe": finding.stufe,
            "code": finding.code,
            "severity": finding.severity,
            "segment": finding.segment,
            "segmentIndex": finding.segment_index,
            "message": finding.message,
        }
        for finding in result.get_all()
    ]

    summary = {
        f"stufe{stufe}": "fail" if result.has_stufe_errors(stufe) else "pass"
        for stufe in range(1, max_stufe + 1)
    }

    output_data = {
        "file": file_path,
        "valid": result.is_valid(),
        "errorCount": result.error_count(),
        "warningCount": result.warning_count(),
        "errors": errors,
        "summary": summary,
    }

    print(json.dumps(output_data, indent=2, ensure_ascii=False))


def main() -> None:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="ESOL Validator — Prüfung von ESOL-Dateien gemäß Technische Anlage 1 TP5 V21",
        add_help=False,
    )
    parser.add_argument("file", nargs="?", help="Pfad zur ESOL-Datei")
    parser.add_argument(
        "--stufe",
        type=int,
        default=4,
        help="Nur bis Prüfstufe N prüfen (1–4). Standard: 4.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Ausgabeformat: text (Standard), json.",
    )
    parser.add_argument(
        "-w",
        "--warnings",
        action="store_true",
        help="Warnungen anzeigen (standardmäßig deaktiviert).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Warnungen als Fehler behandeln (aktiviert --warnings).",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Nur Fehleranzahl und Exit-Code ausgeben.",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Diese Hilfe anzeigen.",
    )

    args = parser.parse_args()

    if args.help or not args.file:
        parser.print_help()
        sys.exit(0 if args.help else 2)

    file_path = Path(args.file)
    if not file_path.is_file():
        if not args.quiet:
            print(f"Fehler: Datei nicht gefunden: {file_path}", file=sys.stderr)
        sys.exit(2)

    validator = EsolValidator()
    validator.register_default_rules()
    validator.set_max_stufe(args.stufe)

    result = validator.validate(str(file_path))

    show_warnings = args.warnings or args.strict

    if not show_warnings:
        result = result.without_warnings()

    is_valid = (
        (result.error_count() == 0 and result.warning_count() == 0)
        if args.strict
        else result.is_valid()
    )

    if args.format == "json":
        output_json(str(file_path), result, args.stufe)
    else:
        if not args.quiet:
            output_text(str(file_path), result, args.stufe)

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()