from typing import List, Optional, Dict, Any

from schema.schema import SchemaFactory
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class FieldPresenceRule(RuleInterface):
    """
    Rule 1.2.2.3 — Muss-Feld (mandatory field) presence validation.

    All fields marked M (Muss) must be present and non-empty.
    Trailing optional (Kann) fields at the segment end may be omitted.
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

            # Service segments — use default (no message context)
            if tag in ("UNB", "UNZ", "UNH", "UNT"):
                definition = self.schema.get(tag)
            else:
                # Determine message context for context-specific segments (FKT)
                msg_type = self._get_message_type_for_segment(index, messages)
                definition = self.schema.get(tag or "", msg_type) or self.schema.get(tag or "")

            if definition is None:
                # 1.2.2.9: Segment tag check
                errors.append(
                    context.create_validation_error(
                        2,
                        "1.2.2.9",
                        f'Unbekanntes Segment "{tag}" an Position {index}.',
                        tag or "",
                        f"{index}",
                    )
                )
                continue

            errors.extend(self._check_presence(seg, definition, index, context))

        return errors

    def _check_presence(
        self, seg: Dict[str, Any], definition: Any, seg_index: int, context: Any
    ) -> List:
        errors = []
        tag = seg.get("tag", "")
        fields = seg.get("fields", [])

        for i in range(definition.field_count()):
            field_def = definition.get_field(i)
            if field_def is None:
                continue

            art = field_def.get("art", "K")
            if art != "M":
                continue

            # Field is mandatory
            value = fields[i] if i < len(fields) else None

            if value is None:
                errors.append(
                    context.create_validation_error(
                        2,
                        "1.2.2.3",
                        f'{tag}-Segment an Position {seg_index}: '
                        f'Pflichtfeld "{field_def.get("name")}" (Feld {i}) fehlt.',
                        tag,
                        seg_index,
                    )
                )
                continue

            # Check if the field is empty
            is_empty = False
            if isinstance(value, str) and value == "":
                is_empty = True
            elif isinstance(value, list):
                # Composite field: check if all sub-elements are empty
                is_empty = all(sub == "" for sub in value)

            if is_empty:
                errors.append(
                    context.create_validation_error(
                        2,
                        "1.2.2.3",
                        f'{tag}-Segment an Position {seg_index}: '
                        f'Pflichtfeld "{field_def.get("name")}" (Feld {i}) ist leer.',
                        tag,
                        seg_index,
                    )
                )

            # For composite mandatory fields, check mandatory sub-elements
            if isinstance(value, list) and "composite" in field_def:
                for sub_idx, sub_def in enumerate(field_def["composite"]):
                    sub_value = value[sub_idx] if sub_idx < len(value) else ""
                    if sub_value == "" and sub_def.get("art", "M") == "M":
                        errors.append(
                            context.create_validation_error(
                                2,
                                "1.2.2.3",
                                f'{tag}-Segment an Position {seg_index}: '
                                f'Pflicht-Unterfeld "{sub_def.get("name")}" in '
                                f'"{field_def.get("name")}" (Feld {i}.{sub_idx}) ist leer.',
                                tag,
                                seg_index,
                            )
                        )

        return errors

    def _get_message_type_for_segment(
        self, seg_index: int, messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        for msg in messages:
            if msg["start"] <= seg_index <= msg["end"]:
                return msg.get("type")
        return None