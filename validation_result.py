from typing import List
from validation_error import ValidationError


class ValidationResult:
    """Value object holding the complete result of a validation run."""

    def __init__(self) -> None:
        self._findings: List[ValidationError] = []

    def add_error(self, error: ValidationError) -> None:
        self._findings.append(error)

    def add_errors(self, errors: List[ValidationError]) -> None:
        for error in errors:
            self._findings.append(error)

    def is_valid(self) -> bool:
        """File is valid if there are no error-severity findings."""
        return not any(finding.is_error() for finding in self._findings)

    def get_errors(self) -> List[ValidationError]:
        return [e for e in self._findings if e.is_error()]

    def get_warnings(self) -> List[ValidationError]:
        return [e for e in self._findings if e.is_warning()]

    def get_by_stufe(self, stufe: int) -> List[ValidationError]:
        return [e for e in self._findings if e.stufe == stufe]

    def get_all(self) -> List[ValidationError]:
        return self._findings

    def error_count(self) -> int:
        return len(self.get_errors())

    def warning_count(self) -> int:
        return len(self.get_warnings())

    def has_stufe_errors(self, stufe: int) -> bool:
        """Check whether a specific Stufe has errors."""
        return any(
            finding.stufe == stufe and finding.is_error()
            for finding in self._findings
        )

    def without_warnings(self) -> "ValidationResult":
        """Return a new ValidationResult containing only errors (no warnings)."""
        filtered = ValidationResult()
        for finding in self._findings:
            if finding.is_error():
                filtered.add_error(finding)
        return filtered