from typing import Any, Dict, List, Optional, Union

from validation_error import ValidationError


class ValidationContext:
    """Holds the parsed representation of an ESOL file for validation.

    Built progressively during validation:
      - Raw content (for encoding checks)
      - Tokenized segments (raw strings)
      - Parsed segments (tag + fields)
      - Messages grouped by UNH..UNT blocks
    """

    def __init__(self) -> None:
        self.raw_content: str | bytes = ""
        self.file_path: str = ""
        self.raw_segments: List[str] = []
        self.parsed_segments: List[Dict[str, Any]] = []
        self.messages: List[Dict[str, Any]] = []

    # Accessor aliases for compatibility
    def set_raw_content(self, c: str | bytes) -> None: self.raw_content = c
    def get_raw_content(self) -> str | bytes: return self.raw_content
    def set_file_path(self, p: str) -> None: self.file_path = p
    def get_file_path(self) -> str: return self.file_path
    def set_raw_segments(self, s: List[str]) -> None: self.raw_segments = s
    def get_raw_segments(self) -> List[str]: return self.raw_segments
    def set_parsed_segments(self, s: List[Dict[str, Any]]) -> None: self.parsed_segments = s
    def get_parsed_segments(self) -> List[Dict[str, Any]]: return self.parsed_segments
    def set_messages(self, m: List[Dict[str, Any]]) -> None: self.messages = m
    def get_messages(self) -> List[Dict[str, Any]]: return self.messages

    def get_segment(self, index: int) -> Optional[Dict[str, Any]]:
        """Get a parsed segment by index."""
        return self.parsed_segments[index] if 0 <= index < len(self.parsed_segments) else None

    def get_segment_count(self) -> int:
        """Count of parsed segments."""
        return len(self.parsed_segments)

    def find_first_segment(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get the first parsed segment with a given tag."""
        return next((s for s in self.parsed_segments if s.get("tag") == tag), None)

    def find_last_segment(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get the last parsed segment with a given tag."""
        return next((s for s in reversed(self.parsed_segments) if s.get("tag") == tag), None)

    def find_all_segments(self, tag: str) -> Dict[int, Dict[str, Any]]:
        """Get all parsed segments with a given tag mapped by index."""
        return {idx: s for idx, s in enumerate(self.parsed_segments) if s.get("tag") == tag}

    def find_first_segment_index(self, tag: str) -> Optional[int]:
        """Get the index of the first segment with a given tag."""
        return next((i for i, s in enumerate(self.parsed_segments) if s.get("tag") == tag), None)

    def find_last_segment_index(self, tag: str) -> Optional[int]:
        """Get the index of the last segment with a given tag."""
        return next((i for i in range(len(self.parsed_segments) - 1, -1, -1) if self.parsed_segments[i].get("tag") == tag), None)

    @staticmethod
    def get_field_value(
        segment: Dict[str, Any], field_index: int, sub_index: Optional[int] = None
    ) -> Optional[str]:
        """Get a field value from a parsed segment. Handles both simple and composite fields."""
        fields = segment.get("fields", [])
        if field_index >= len(fields):
            return None

        field = fields[field_index]

        if sub_index is not None:
            if isinstance(field, list):
                return field[sub_index] if sub_index < len(field) else None
            return field if sub_index == 0 else None

        if isinstance(field, list):
            return ":".join(str(val) for val in field)

        return str(field) if field is not None else None
    
    def create_validation_error(
        self,
        stufe: int,
        code: str,
        message: str,
        segment: Optional[str] = None,
        segment_index: Optional[int] = None,
        severity: str = "error",
    ) -> ValidationError:
        """
        Baut eine ValidationError.

        ACHTUNG bei der Parameterreihenfolge: 'severity' steht bewusst hinten.
        Vorher stand es an vierter Stelle, alle 43 Aufrufstellen in rules/
        uebergeben dort aber das Segmentkuerzel positional. Damit landete "UNB",
        "FKT", "REC" ... in 'severity'; get_errors() filtert auf
        severity == "error", und has_stufe_errors() sah keine Fehler. Folge:
        saemtliche Meldungen der Pruefstufen 1 und 2 (1.1.3 bis 1.1.13 und
        1.2.1.1 bis 1.2.2.9) verschwanden lautlos, und die Pruefung lief in
        Stufe 3 weiter, obwohl sie laut Anlage 1 Kapitel 6 dort haette abbrechen
        muessen. Wer die Reihenfolge zurueckdreht, schaltet die beiden Stufen
        wieder ab. Eine abweichende Severity wird per Schluesselwort uebergeben.
        """
        return ValidationError(
            stufe=stufe,
            code=code,
            message=message,
            severity=severity,
            segment=segment,
            segment_index=segment_index,
        )