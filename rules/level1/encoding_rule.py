from typing import List, Union
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class EncodingRule(RuleInterface):
    """
    Rule 1.1.1 — Encoding validation.

    File MUST be ISO-8859-1. Detect and reject UTF-8 BOM or other encodings.
    """

    def get_stufe(self) -> int:
        return 1

    def validate(self, context) -> List:
        errors = []
        content: Union[str, bytes] = context.get_raw_content()

        # In Bytes umwandeln, falls als ISO-8859-1 / Latin-1 String geliefert
        if isinstance(content, str):
            content_bytes = content.encode("latin-1", errors="replace")
        else:
            content_bytes = content

        # Check for UTF-8 BOM (EF BB BF)
        if content_bytes.startswith(b"\xef\xbb\xbf"):
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.1",
                    "Datei enthält UTF-8 BOM. Die Datei muss ISO-8859-1 kodiert sein.",
                )
            )
            return errors

        # Check for UTF-16 LE BOM (FF FE)
        if content_bytes.startswith(b"\xff\xfe"):
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.1",
                    "Datei enthält UTF-16 LE BOM. Die Datei muss ISO-8859-1 kodiert sein.",
                )
            )
            return errors

        # Check for UTF-16 BE BOM (FE FF)
        if content_bytes.startswith(b"\xfe\xff"):
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.1",
                    "Datei enthält UTF-16 BE BOM. Die Datei muss ISO-8859-1 kodiert sein.",
                )
            )
            return errors

        # Heuristic: check for multi-byte UTF-8 sequences
        if self._looks_like_utf8(content_bytes):
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.1",
                    "Datei scheint UTF-8 kodiert zu sein (Multibyte-Sequenzen erkannt). "
                    "Die Datei muss ISO-8859-1 kodiert sein.",
                )
            )

        return errors

    def _looks_like_utf8(self, content: bytes) -> bool:
        try:
            decoded = content.decode("utf-8")
            return sum(1 for ch in decoded if ord(ch) > 0x7F) >= 2
        except UnicodeDecodeError:
            return False