from typing import List
from rules.rule_interface import RuleInterface


class EscapeSequenceRule(RuleInterface):
    """
    Rule 1.2.2.2 — Escape sequence validation.

    The EDIFACT escape character '?' must only appear before the special
    characters +, ', :, ,, and ? itself. Any other use of '?' is invalid.

    This rule checks the raw (un-parsed) segment strings before unescaping.
    """

    VALID_ESCAPED: tuple[str, ...] = ("+", "'", ":", ",", "?")

    def get_stufe(self) -> int:
        return 2

    def validate(self, context) -> List:
        errors = []
        raw = context.get_raw_content()
        if isinstance(raw, bytes):
            raw = raw.decode("latin-1", errors="replace")

        # Wenn ein ' Mitten im Text steht ohne ? davor
        # Oder verwaiste Escapes vorkommen
        for idx, char in enumerate(raw):
            if char == "?":
                if idx + 1 >= len(raw) or raw[idx + 1] not in ["+", ":", "'", "?"]:
                    errors.append(
                        context.create_validation_error(
                            2, "1.2.3.1", f"Ungültiges Escaping bei Position {idx}."
                        )
                    )
        
        # Falls durch kaputtes Escaping leere/ungültige Segmente beim Parsing entstanden sind:
        for seg in context.get_parsed_segments():
            if seg.get("tag") == "" or seg.get("raw") == "+":
                errors.append(
                    context.create_validation_error(
                        2, "1.2.3.1", "Unescapetes Steuerzeichen zerstört Segmentstruktur."
                    )
                )

        return errors

    def _extract_tag(self, raw: str) -> str:
        """Extract the segment tag from a raw segment string."""
        plus_pos = raw.find("+")
        if plus_pos != -1:
            return raw[:plus_pos]
        return raw[:3]