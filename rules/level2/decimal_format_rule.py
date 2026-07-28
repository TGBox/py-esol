from typing import List, Optional, Dict, Any

from schema.schema import SchemaFactory
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class DecimalFormatRule(RuleInterface):
    """
    Rule 1.2.2.7 — Decimal format validation.

    Numeric decimal fields must use ',' as decimal separator and
    contain the specified number of decimal places.
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

            errors.extend(self._check_decimal_formats(seg, definition, index, context))

        return errors

    def _check_decimal_formats(
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

            if field_def.get("type") != "N":
                continue
            decimals = field_def.get("decimals")
            if decimals is None:
                continue

            value = fields[i] if i < len(fields) else ""
            if isinstance(value, list) or value == "":
                continue

            error = self._validate_decimal_format(
                value, decimals, field_def.get("name", ""), tag, seg_index, i, context
            )
            if error is not None:
                errors.append(error)

        return errors

    def _validate_decimal_format(
        self,
        value: str,
        expected_decimals: int,
        field_name: str,
        tag: str,
        seg_index: int,
        field_index: int,
        context: Any,
    ) -> Optional[Any]:
        stripped = value.lstrip("-")

        if expected_decimals == 0:
            if "," in stripped:
                return context.create_validation_error(
                    2,
                    "1.2.2.7",
                    f'{tag}-Segment an Position {seg_index}: '
                    f'Feld "{field_name}" (Feld {field_index}) soll keine Dezimalstellen haben, '
                    f'enthält aber ein Komma: "{value}".',
                    tag,
                    seg_index,
                )
            return None

        if "," not in stripped:
            return context.create_validation_error(
                2,
                "1.2.2.7",
                f'{tag}-Segment an Position {seg_index}: '
                f'Feld "{field_name}" (Feld {field_index}) muss {expected_decimals} Nachkommastellen haben, '
                f'enthält aber kein Komma: "{value}".',
                tag,
                seg_index,
            )

        parts = stripped.split(",", 1)
        actual_decimals = len(parts[1]) if len(parts) > 1 else 0

        if actual_decimals != expected_decimals:
            return context.create_validation_error(
                2,
                "1.2.2.7",
                f'{tag}-Segment an Position {seg_index}: '
                f'Feld "{field_name}" (Feld {field_index}) muss {expected_decimals} Nachkommastellen haben, '
                f'hat aber {actual_decimals}: "{value}".',
                tag,
                seg_index,
            )

        return None

    def _get_message_type_for_segment(
        self, seg_index: int, messages: List[Dict[str, Any]]
    ) -> Optional[str]:
        for msg in messages:
            if msg["start"] <= seg_index <= msg["end"]:
                return msg.get("type")
        return None