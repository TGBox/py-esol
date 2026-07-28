from typing import List
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class MessageCountRule(RuleInterface):
    """
    Rules 1.1.6, 1.1.9 — Message and segment count validation.

    1.1.6: UNZ.Anzahl Nachrichten must equal actual number of UNH segments.
    1.1.9: UNT.Anzahl Einheiten must equal actual segment count between UNH and UNT (inclusive).
    """

    def get_stufe(self) -> int:
        return 1

    def validate(self, context) -> List:
        errors = []

        # 1.1.6: UNZ message count
        errors.extend(self._check_unz_message_count(context))

        # 1.1.9: UNT segment count per message
        errors.extend(self._check_unt_segment_counts(context))

        return errors

    def _check_unz_message_count(self, context) -> List:
        errors = []
        unz_segment = context.find_last_segment("UNZ")

        if unz_segment is None:
            return errors  # StructureRule handles missing UNZ

        declared_count = context.get_field_value(unz_segment, 0)
        if declared_count is None or declared_count == "":
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.6",
                    'UNZ-Segment: Feld "Anzahl Nachrichten" fehlt.',
                    "UNZ",
                    context.find_last_segment_index("UNZ"),
                )
            )
            return errors

        # Count actual UNH segments
        actual_count = len(context.find_all_segments("UNH"))

        declared_int = 0
        if declared_count.isdigit():
            declared_int = int(declared_count)

        if declared_int != actual_count:
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.6",
                    f"UNZ-Segment: Anzahl Nachrichten ist {declared_count} (= {declared_int}), "
                    f"tatsächliche Anzahl UNH-Segmente ist {actual_count}.",
                    "UNZ",
                    context.find_last_segment_index("UNZ"),
                )
            )

        return errors

    def _check_unt_segment_counts(self, context) -> List:
        errors = []
        messages = context.get_messages()

        for msg in messages:
            segment_count = msg["end"] - msg["start"] + 1
            msg_segments = msg.get("segments", [])

            if not msg_segments:
                continue

            unt_seg = msg_segments[-1]  # Equivalent to PHP's end()
            if unt_seg.get("tag") != "UNT":
                continue  # StructureRule handles missing UNT

            declared_count = context.get_field_value(unt_seg, 0)
            if declared_count is None or declared_count == "":
                errors.append(
                    context.create_validation_error(
                        1,
                        "1.1.9",
                        f"UNT-Segment an Position {msg['end']}: Feld \"Anzahl Einheiten\" fehlt.",
                        "UNT",
                        msg["end"],
                    )
                )
                continue

            declared_int = int(declared_count) if declared_count.isdigit() else 0

            if declared_int != segment_count:
                errors.append(
                    context.create_validation_error(
                        1,
                        "1.1.9",
                        f"UNT-Segment an Position {msg['end']}: Anzahl Einheiten ist {declared_count} (= {declared_int}), "
                        f"tatsächliche Anzahl Segmente ist {segment_count} (Nachricht {msg.get('refNr')}).",
                        "UNT",
                        msg["end"],
                    )
                )

        return errors