import re
from typing import Any, List, Optional

from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_error import ValidationError

class UntContentRule(RuleInterface):
    """Nachrichtentyp-Endesegment (UNT) Content Validation.

    - 0074: Anzahl Einheiten — 6-stellig numerisch, exakte Anzahl der Segmente (inkl. UNH und UNT)
    - 0062: Nachrichtenreferenznummer — max 14 Zeichen, muss mit der aus UNH übereinstimmen
    """

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()

        for msg in messages:
            unh_ref_number: Optional[str] = None

            # Extrahiere Nachrichtenreferenznummer aus UNH
            for seg in msg.get("segments", []):
                if seg.get("tag") == "UNH":
                    unh_ref_number = ContentHelper.get_field(seg, 0)
                    break

            # Validierung des UNT Segments
            for seg_offset, seg in enumerate(msg.get("segments", [])):
                if seg.get("tag") != "UNT":
                    continue

                seg_index = msg.get("start", 0) + seg_offset

                # Feld 0074: Anzahl Einheiten
                anzahl_einheiten = ContentHelper.get_field(seg, 0)
                if anzahl_einheiten is None or anzahl_einheiten == "":
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.UNT.1",
                            "UNT: Feld 'Anzahl Einheiten' (0074) ist ein Pflichtfeld.",
                            "UNT",
                            seg_index,
                        )
                    )
                else:
                    # Prüfe auf 6 Stellen numerisch mit führenden Nullen
                    if not re.match(r"^\d{6}$", str(anzahl_einheiten)):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.UNT.1",
                                f'UNT: \'Anzahl Einheiten\' ("{anzahl_einheiten}") muss genau 6-stellig numerisch sein (mit führenden Nullen).',
                                "UNT",
                                seg_index,
                            )
                        )

                    # Abgleich mit der tatsächlichen Segmentanzahl in der Nachricht
                    actual_segment_count = len(msg.get("segments", []))
                    try:
                        parsed_count = int(anzahl_einheiten)
                        if parsed_count != actual_segment_count:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.UNT.1",
                                    f"UNT: Angegebene Anzahl Einheiten ({anzahl_einheiten}) stimmt nicht mit der tatsächlichen Segmentanzahl ({actual_segment_count}) überein.",
                                    "UNT",
                                    seg_index,
                                )
                            )
                    except ValueError:
                        # Fallback, falls die Konvertierung in int fehlschlägt (bereits durch Regex abgefangen)
                        pass

                # Feld 0062: Nachrichtenreferenznummer
                unt_ref_number = ContentHelper.get_field(seg, 1)
                if unt_ref_number is None or unt_ref_number == "":
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.UNT.2",
                            "UNT: Feld 'Nachrichtenreferenznummer' (0062) ist ein Pflichtfeld.",
                            "UNT",
                            seg_index,
                        )
                    )
                else:
                    if len(unt_ref_number) > 14:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.UNT.2",
                                f'UNT: Nachrichtenreferenznummer "{unt_ref_number}" überschreitet 14 Zeichen.',
                                "UNT",
                                seg_index,
                            )
                        )

                    # Abgleich mit UNH
                    if (
                        unh_ref_number is not None
                        and unt_ref_number != unh_ref_number
                    ):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.UNT.2",
                                f'UNT: Nachrichtenreferenznummer ("{unt_ref_number}") stimmt nicht mit der aus dem UNH-Segment ("{unh_ref_number}") überein.',
                                "UNT",
                                seg_index,
                            )
                        )

                break  # Max 1 UNT pro Nachricht

        return errors