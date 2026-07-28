from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class NamContentRule(RuleInterface):
    """Rule 1.3.14 — NAM segment content validation (SLGA)."""

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()

        for msg in messages:
            if msg.get("type") != "SLGA":
                continue

            for seg_offset, seg in enumerate(msg.get("segments", [])):
                if seg.get("tag") != "NAM":
                    continue

                seg_index = msg["start"] + seg_offset

                # 1.3.14.1: Name 1 — max 30 chars
                name1 = ContentHelper.get_field(seg, 0)
                if name1 and len(name1) > 30:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.14.1",
                            f"NAM: Name 1 überschreitet 30 Zeichen (Länge: {len(name1)}).",
                            "NAM",
                            seg_index,
                        )
                    )

                # 1.3.14.2: Name 4 (E-Mail) — if present, valid email, no umlauts
                name4 = ContentHelper.get_field(seg, 3)
                if name4 and not ContentHelper.is_valid_email(name4):
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.14.2",
                            f'NAM: E-Mail-Adresse "{name4}" hat ungültiges Format.',
                            "NAM",
                            seg_index,
                        )
                    )

                break  # One NAM per SLGA

        return errors