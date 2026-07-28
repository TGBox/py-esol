from typing import Any, Dict, List, Union


class SegmentTokenizer:
    """Low-level EDIFACT tokenizer that respects escape sequences.

    Splits an ESOL file (raw string) into segments, and each segment
    into data elements and composite sub-elements.

    EDIFACT special characters:
      +  field (data element) separator
      :  composite sub-element separator
      '  segment terminator
      ?  escape (release) character
      ,  decimal separator (not a structural delimiter)
    """

    SEGMENT_TERMINATOR = "'"
    FIELD_SEPARATOR = "+"
    COMPOSITE_SEPARATOR = ":"
    ESCAPE_CHAR = "?"

    def tokenize_segments(self, content: str | bytes) -> List[str]:
        """Tokenize raw ESOL content into a list of raw segment strings.

        Each segment string does NOT include the trailing segment terminator.
        Escape sequences are respected: ?' is NOT treated as a segment end.
        """
        # Wenn Bytes übergeben werden, in ISO-8859-1 / Latin-1 String umwandeln
        if isinstance(content, bytes):
            content = content.decode("latin-1", errors="replace")

        segments: List[str] = []
        current: str = ""
        length = len(content)
        i = 0

        while i < length:
            char = content[i]

            if char == self.ESCAPE_CHAR and i + 1 < length:
                # Escape character: take next char literally
                current += char + content[i + 1]
                i += 2
                continue

            if char == self.SEGMENT_TERMINATOR:
                trimmed = current.strip()
                if trimmed != "":
                    segments.append(trimmed)
                current = ""
                i += 1
                continue

            current += char
            i += 1

        # Handle content after last terminator (should not happen in valid files)
        trimmed = current.strip()
        if trimmed != "":
            segments.append(trimmed)

        return segments

    def parse_segment(self, raw_segment: str) -> Dict[str, Any]:
        """Parse a single raw segment string into its constituent fields.

        Returns a dictionary where:
          - 'tag' is the segment tag (e.g. "UNB", "EHE")
          - 'fields' is a list of field values (string) or lists of composite
            sub-elements if the field contains ':'.

        Escape sequences are resolved in returned values.
        """
        fields = self._split_by_delimiter(raw_segment, self.FIELD_SEPARATOR)

        tag = fields[0] if fields else ""
        parsed_fields: List[Union[str, List[str]]] = []

        for i in range(1, len(fields)):
            field = fields[i]

            # Check if field has composite sub-elements
            sub_elements = self._split_by_delimiter(field, self.COMPOSITE_SEPARATOR)

            if len(sub_elements) > 1:
                # Composite field: unescape each sub-element
                parsed_fields.append([self.unescape(sub) for sub in sub_elements])
            else:
                # Simple field: unescape
                parsed_fields.append(self.unescape(field))

        return {
            "tag": self.unescape(tag),
            "fields": parsed_fields,
        }

    def _split_by_delimiter(self, input_str: str, delimiter: str) -> List[str]:
        """Split a string by a delimiter, respecting the EDIFACT escape character."""
        parts: List[str] = []
        current: str = ""
        length = len(input_str)
        i = 0

        while i < length:
            char = input_str[i]

            if char == self.ESCAPE_CHAR and i + 1 < length:
                # Escaped character: take literally (keep escape for later unescape)
                current += char + input_str[i + 1]
                i += 2
                continue

            if char == delimiter:
                parts.append(current)
                current = ""
                i += 1
                continue

            current += char
            i += 1

        parts.append(current)
        return parts

    def unescape(self, value: str) -> str:
        """Remove EDIFACT escape sequences from a string.

        ?+ -> +, ?' -> ', ?: -> :, ?, -> ,, ?? -> ?
        """
        result: List[str] = []
        length = len(value)
        i = 0

        while i < length:
            if value[i] == self.ESCAPE_CHAR and i + 1 < length:
                result.append(value[i + 1])
                i += 2
            else:
                result.append(value[i])
                i += 1

        return "".join(result)