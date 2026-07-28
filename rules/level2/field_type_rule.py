import re
from typing import List, Optional, Dict, Any

from schema.schema import SchemaFactory
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class FieldTypeRule(RuleInterface):
    """
    Rules 1.2.2.4, 1.2.2.5 — Field type validation.

    1.2.2.4: AN fields — any character allowed (per field-specific constraints).
    1.2.2.5: N fields — only digits 0-9, decimal comma, optional leading minus. No alpha.
    """

    NUMERIC_PATTERN = re.compile(r"^-?[0-9]*(?:,[0-9]+)?$")

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

            errors.extend(self._check_field_types(seg, definition, index, context))

        return errors

    def _check_field_types(
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

            # Composite field: check sub-elements
            if isinstance(value, list) and "composite" in field_def:
                for sub_idx, sub_def in enumerate(field_def["composite"]):
                    sub_value = value[sub_idx] if sub_idx < len(value) else ""
                    if sub_value == "":
                        continue

                    sub_type = sub_def.get("type", "AN")
                    if sub_type == "N" and not self._is_valid_numeric(sub_value):
                        errors.append(
                            context.create_validation_error(
                                2,
                                "1.2.2.5",
                                f'{tag}-Segment an Position {seg_index}: '
                                f'Unterfeld "{sub_def.get("name")}" (Feld {i}.{sub_idx}) muss numerisch sein, '
                                f'enthält aber ungültige Zeichen: "{sub_value}".',
                                tag,
                                seg_index,
                            )
                        )
                continue

            # Simple field
            if isinstance(value, str) and value == "":
                continue
            if isinstance(value, list):
                continue  # Composite without schema definition — skip

            field_type = field_def.get("type", "AN")
            if field_type == "N" and isinstance(value, str) and not self._is_valid_numeric(value):
                errors.append(
                    context.create_validation_error(
                        2,
                        "1.2.2.5",
                        f'{tag}-Segment an Position {seg_index}: '
                        f'Feld "{field_def.get("name")}" (Feld {i}) muss numerisch sein, '
                        f'enthält aber ungültige Zeichen: "{value}".',
                        tag,
                        seg_index,
                    )
                )

        return errors

    def _is_valid_numeric(self, value: str) -> bool:
        """
        Check if a value conforms to the N (numeric) type.
        Valid: digits 0-9, optional leading minus, optional decimal comma.
        Examples: "123", "-10,00", ",15", "0", "82,89"
        """
        if value in ("", "-", ","):
            return False
        return bool(self.NUMERIC_PATTERN.match(value))

    def _get_message_type_for_segment(
        self, seg_index: int, messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        for msg in messages:
            if msg["start"] <= seg_index <= msg["end"]:
                return msg.get("type")
        return None