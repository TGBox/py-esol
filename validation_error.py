from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationError:
    """Value object representing a single validation error or warning."""

    stufe: int
    code: str
    message: str
    severity: str = "error"
    segment: Optional[str] = None
    segment_index: Optional[int] = None

    @classmethod
    def error(
        cls,
        stufe: int,
        code: str,
        message: str,
        segment: Optional[str] = None,
        segment_index: Optional[int] = None,
    ) -> "ValidationError":
        """Create an error-level validation finding."""
        return cls(stufe, code, message, "error", segment, segment_index)

    @classmethod
    def warning(
        cls,
        stufe: int,
        code: str,
        message: str,
        segment: Optional[str] = None,
        segment_index: Optional[int] = None,
    ) -> "ValidationError":
        """Create a warning-level validation finding."""
        return cls(stufe, code, message, "warning", segment, segment_index)

    def is_error(self) -> bool:
        return self.severity == "error"

    def is_warning(self) -> bool:
        return self.severity == "warning"

    def __str__(self) -> str:
        prefix = self.severity.upper()
        location = ""
        if self.segment:
            pos = (
                f" at position {self.segment_index}"
                if self.segment_index is not None
                else ""
            )
            location = f" ({self.segment}{pos})"

        return f"{prefix} [{self.code}]{location}: {self.message}"