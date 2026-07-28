import re
from typing import List
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class ReferenceNumberRule(RuleInterface):
    """
    Rules 1.1.7, 1.1.8, 1.1.10 — Reference number validation.

    1.1.7:  UNZ.Datenaustauschreferenz must equal UNB.Datenaustauschreferenz.
    1.1.8:  UNT.Nachrichtenreferenznummer must equal corresponding UNH.Nachrichtenreferenznummer.
    1.1.10: UNH.Nachrichtenreferenznummer must be sequential (00001, 00002, ...) with 5-digit leading zeros.
    """

    def get_stufe(self) -> int:
        return 1

    def validate(self, context) -> List:
        errors = []

        errors.extend(self._check_datenaustauschreferenz(context))
        errors.extend(self._check_nachrichtenreferenznummern(context))
        errors.extend(self._check_sequential_numbering(context))

        return errors

    def _check_datenaustauschreferenz(self, context) -> List:
        errors = []

        unb_segment = context.find_first_segment("UNB")
        unz_segment = context.find_last_segment("UNZ")

        if unb_segment is None or unz_segment is None:
            return errors  # StructureRule handles missing UNB/UNZ

        unb_ref = context.get_field_value(unb_segment, 4)
        unz_ref = context.get_field_value(unz_segment, 1)

        if unb_ref is not None and unz_ref is not None and unb_ref != unz_ref:
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.7",
                    f"UNZ.Datenaustauschreferenz ({unz_ref}) stimmt nicht mit "
                    f"UNB.Datenaustauschreferenz ({unb_ref}) überein.",
                    "UNZ",
                    context.find_last_segment_index("UNZ"),
                )
            )

        return errors

    def _check_nachrichtenreferenznummern(self, context) -> List:
        errors = []
        messages = context.get_messages()

        for msg in messages:
            msg_segments = msg.get("segments", [])
            if len(msg_segments) < 2:
                continue

            unh_seg = msg_segments[0]
            unt_seg = msg_segments[-1]

            if unh_seg.get("tag") != "UNH" or unt_seg.get("tag") != "UNT":
                continue

            unh_ref_nr = context.get_field_value(unh_seg, 0)
            unt_ref_nr = context.get_field_value(unt_seg, 1)

            if unh_ref_nr is not None and unt_ref_nr is not None and unh_ref_nr != unt_ref_nr:
                errors.append(
                    context.create_validation_error(
                        1,
                        "1.1.8",
                        f"UNT.Nachrichtenreferenznummer ({unt_ref_nr}) stimmt nicht mit "
                        f"UNH.Nachrichtenreferenznummer ({unh_ref_nr}) überein (Nachricht an Position {msg['start']}).",
                        "UNT",
                        msg["end"],
                    )
                )

        return errors

    def _check_sequential_numbering(self, context) -> List:
        errors = []
        unh_segments = context.find_all_segments("UNH")
        expected_number = 1

        for index, seg in unh_segments.items():
            ref_nr = context.get_field_value(seg, 0)

            if not ref_nr:
                errors.append(
                    context.create_validation_error(
                        1,
                        "1.1.10",
                        f"UNH-Segment an Position {index}: Nachrichtenreferenznummer fehlt.",
                        "UNH",
                        index,
                    )
                )
                expected_number += 1
                continue

            expected_str = str(expected_number).zfill(5)

            if ref_nr != expected_str:
                if not re.match(r"^\d{5}$", ref_nr):
                    errors.append(
                        context.create_validation_error(
                            1,
                            "1.1.10",
                            f'UNH-Segment an Position {index}: Nachrichtenreferenznummer "{ref_nr}" '
                            f"hat nicht das erwartete Format (5 Ziffern mit führenden Nullen). Erwartet: {expected_str}.",
                            "UNH",
                            index,
                        )
                    )
                else:
                    errors.append(
                        context.create_validation_error(
                            1,
                            "1.1.10",
                            f'UNH-Segment an Position {index}: Nachrichtenreferenznummer "{ref_nr}" '
                            f"ist nicht sequentiell. Erwartet: {expected_str}.",
                            "UNH",
                            index,
                        )
                    )

            expected_number += 1

        return errors