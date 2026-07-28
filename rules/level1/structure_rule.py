from typing import List, Dict, Any, Optional
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class StructureRule(RuleInterface):
    """
    Rules 1.1.2-1.1.5 — File structure validation.

    1.1.2: Segment terminator — every segment ends with '
    1.1.3: UNB present & first
    1.1.4: UNZ present & last
    1.1.5: UNH/UNT pairing — every UNH has a matching UNT, no nesting
    """

    def get_stufe(self) -> int:
        return 1

    def validate(self, context) -> List:
        errors = []
        segments = context.get_parsed_segments()

        if not segments:
            errors.append(
                context.create_validation_error(
                    1, "1.1.2", "Datei enthält keine gültigen Segmente."
                )
            )
            return errors

        # 1.1.2: Check that raw content ends with segment terminator
        raw_content = context.get_raw_content()
        if isinstance(raw_content, bytes):
            raw_content = raw_content.decode("latin-1", errors="replace")

        raw_content = raw_content.rstrip()
        if not raw_content.endswith("'"):
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.2",
                    "Datei endet nicht mit dem Segmentendezeichen (').",
                )
            )

        # 1.1.3: UNB present and first
        first_tag = segments[0].get("tag") if segments else None
        if first_tag != "UNB":
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.3",
                    f"Datei beginnt nicht mit UNB-Segment. Erstes Segment: {first_tag or '(leer)'}",
                    "UNB",
                    "0",
                )
            )

        # 1.1.4: UNZ present and last
        last_index = len(segments) - 1
        last_tag = segments[last_index].get("tag") if segments else None
        if last_tag != "UNZ":
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.4",
                    f"Datei endet nicht mit UNZ-Segment. Letztes Segment: {last_tag or '(leer)'}",
                    "UNZ",
                    f"{last_index}",
                )
            )

        # 1.1.5: UNH/UNT pairing — no nesting
        errors.extend(self._check_unh_unt_pairing(context, segments))

        return errors

    def _check_unh_unt_pairing(
        self, context, segments: List[Dict[str, Any]]
    ) -> List:
        errors = []
        inside_message = False
        unh_index: Optional[int] = None
        unh_count = 0
        unt_count = 0

        for index, seg in enumerate(segments):
            tag = seg.get("tag")

            if tag == "UNH":
                unh_count += 1
                if inside_message:
                    errors.append(
                        context.create_validation_error(
                            1,
                            "1.1.5",
                            f"UNH-Segment an Position {index} ohne vorheriges UNT-Segment "
                            f"(verschachtelte Nachrichten sind nicht erlaubt).",
                            "UNH",
                            index,
                        )
                    )
                inside_message = True
                unh_index = index

            if tag == "UNT":
                unt_count += 1
                if not inside_message:
                    errors.append(
                        context.create_validation_error(
                            1,
                            "1.1.5",
                            f"UNT-Segment an Position {index} ohne vorheriges UNH-Segment.",
                            "UNT",
                            index,
                        )
                    )
                inside_message = False
                unh_index = None

        if inside_message and unh_index is not None:
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.5",
                    f"UNH-Segment an Position {unh_index} hat kein zugehöriges UNT-Segment.",
                    "UNH",
                    unh_index,
                )
            )

        if unh_count != unt_count and not errors:
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.5",
                    f"Anzahl UNH-Segmente ({unh_count}) stimmt nicht mit "
                    f"Anzahl UNT-Segmente ({unt_count}) überein.",
                )
            )

        return errors