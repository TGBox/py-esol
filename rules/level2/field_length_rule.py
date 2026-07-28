from typing import List, Optional, Dict, Any

from schema.schema import SchemaFactory
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class FieldLengthRule(RuleInterface):
    """
    Rule 1.2.2.6 — Maximum field length validation.

    Each field must not exceed its defined maximum length.
    For numeric fields, the minus sign and decimal comma are NOT counted.
    """

    def __init__(self, schema: Optional[Any] = None):
        if schema is None:
            self.schema = SchemaFactory.create()
        else:
            self.schema = schema

    def get_stufe(self) -> int:
        return 2

    def validate(self, context) -> List:
        errors = []
        messages = context.get_messages()

        for index, seg in enumerate(context.get_parsed_segments()):
            tag = seg.get("tag")

            msg_type = None
            if tag not in ("UNB", "UNZ", "UNH", "UNT"):
                msg_type = self._get_message_type_for_segment(index, messages)

            definition = self.schema.get(tag or "", msg_type) or self.schema.get(tag or "")
            if definition is None:
                continue

            errors.extend(self._check_field_lengths(seg, definition, index, context))

        return errors

    def _check_field_lengths(
        self, seg: Dict[str, Any], definition: Any, seg_index: int, context: Any
    ) -> List:
        errors = []
        tag = seg.get("tag", "")
        fields = seg.get("fields", [])

        count = min(len(fields), definition.field_count())
        for i in range(count):
            field_def = definition.get_field(i)
            if field_def is None:
                continue

            value = fields[i]

            # Composite field: check sub-element lengths
            if isinstance(value, list) and "composite" in field_def:
                for sub_idx, sub_def in enumerate(field_def["composite"]):
                    sub_value = value[sub_idx] if sub_idx < len(value) else ""
                    if sub_value == "":
                        continue

                    max_len = sub_def.get("maxLen")
                    if max_len is None:
                        continue

                    eff_len = self._effective_length(sub_value, sub_def.get("type", "AN"))

                    if eff_len > max_len:
                        errors.append(
                            context.create_validation_error(
                                2,
                                "1.2.2.6",
                                f'{tag}-Segment an Position {seg_index}: '
                                f'Unterfeld "{sub_def.get("name")}" (Feld {i}.{sub_idx}) überschreitet '
                                f'Maximallänge {max_len} (tatsächlich: {eff_len}, Wert: "{sub_value}").',
                                tag,
                                seg_index,
                            )
                        )
                continue

            # Simple field
            if not isinstance(value, str) or value == "":
                continue

            max_len = field_def.get("maxLen")
            if max_len is None:
                continue

            eff_len = self._effective_length(value, field_def.get("type", "AN"))

            if eff_len > max_len:
                errors.append(
                    context.create_validation_error(
                        2,
                        "1.2.2.6",
                        f'{tag}-Segment an Position {seg_index}: '
                        f'Feld "{field_def.get("name")}" (Feld {i}) überschreitet '
                        f'Maximallänge {max_len} (tatsächlich: {eff_len}, Wert: "{value}").',
                        tag,
                        seg_index,
                    )
                )

        return errors

    def _effective_length(self, value: str, field_type: str) -> int:
        """
        Calculate the effective length of a field value.
        For numeric fields, minus sign and decimal comma are excluded from count.
        """
        if field_type == "N":
            stripped = value.replace("-", "").replace(",", "")
            return len(stripped)
        return len(value)

    def _get_message_type_for_segment(
        self, seg_index: int, messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        for msg in messages:
            if msg["start"] <= seg_index <= msg["end"]:
                return msg.get("type")
        return None