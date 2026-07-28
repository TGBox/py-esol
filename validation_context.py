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
        self._raw_content: str | bytes = ""
        self._file_path: str = ""
        self._raw_segments: List[str] = []
        self._parsed_segments: List[Dict[str, Any]] = []
        self._messages: List[Dict[str, Any]] = []

    def set_raw_content(self, content: str | bytes) -> None:
        self._raw_content = content

    def get_raw_content(self) -> str | bytes:
        return self._raw_content

    def set_file_path(self, path: str) -> None:
        self._file_path = path

    def get_file_path(self) -> str:
        return self._file_path

    def set_raw_segments(self, segments: List[str]) -> None:
        self._raw_segments = segments

    def get_raw_segments(self) -> List[str]:
        return self._raw_segments

    def set_parsed_segments(self, segments: List[Dict[str, Any]]) -> None:
        self._parsed_segments = segments

    def get_parsed_segments(self) -> List[Dict[str, Any]]:
        return self._parsed_segments

    def get_segment(self, index: int) -> Optional[Dict[str, Any]]:
        """Get a parsed segment by index."""
        if 0 <= index < len(self._parsed_segments):
            return self._parsed_segments[index]
        return None

    def get_segment_count(self) -> int:
        """Count of parsed segments."""
        return len(self._parsed_segments)

    def set_messages(self, messages: List[Dict[str, Any]]) -> None:
        """Set identified messages (UNH..UNT blocks)."""
        self._messages = messages

    def get_messages(self) -> List[Dict[str, Any]]:
        return self._messages

    def find_first_segment(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get the first parsed segment with a given tag."""
        for seg in self._parsed_segments:
            if seg.get("tag") == tag:
                return seg
        return None

    def find_last_segment(self, tag: str) -> Optional[Dict[str, Any]]:
        """Get the last parsed segment with a given tag."""
        result = None
        for seg in self._parsed_segments:
            if seg.get("tag") == tag:
                result = seg
        return result

    def find_all_segments(self, tag: str) -> Dict[int, Dict[str, Any]]:
        """Get all parsed segments with a given tag mapped by index."""
        result = {}
        for index, seg in enumerate(self._parsed_segments):
            if seg.get("tag") == tag:
                result[index] = seg
        return result

    def find_first_segment_index(self, tag: str) -> Optional[int]:
        """Get the index of the first segment with a given tag."""
        for index, seg in enumerate(self._parsed_segments):
            if seg.get("tag") == tag:
                return index
        return None

    def find_last_segment_index(self, tag: str) -> Optional[int]:
        """Get the index of the last segment with a given tag."""
        result = None
        for index, seg in enumerate(self._parsed_segments):
            if seg.get("tag") == tag:
                result = index
        return result

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
        severity: str = "error",
        segment: Optional[str] = None,
        segment_index: Optional[int] = None,
    ) -> ValidationError:
        """Helper method to create a ValidationError instance."""
        return ValidationError(
            stufe=stufe,
            code=code,
            message=message,
            severity=severity,
            segment=segment,
            segment_index=segment_index,
        )