from typing import Any, Dict, List

from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class UniqueEheDateServiceRule(RuleInterface):
    """Rule 1.4.1 — Unique service code per date within an INV..BES block.

    Within the same INV..BES section, if multiple EHE items share the same
    Datum Leistungserbringung (field 4), their Abrechnungspositionsnummer
    (field 1 / "third column") must be different.
    """

    def get_stufe(self) -> int:
        return 4

    def validate(self, context: ValidationContext) -> List[ValidationError]:
        errors: List[ValidationError] = []
        messages = context.get_messages()

        for msg in messages:
            if msg.get("type") != "SLLA":
                continue

            # ContentHelper.extract_inv_blocks(msg)
            inv_blocks = ContentHelper.extract_inv_blocks(msg)

            for block_idx, block in enumerate(inv_blocks):
                # Collect (date -> serviceCode[]) mapping for this INV block
                date_service_map: Dict[str, List[Dict[str, Any]]] = {}

                for seg in block:
                    if seg.get("tag") != "EHE":
                        continue

                    service_code = ContentHelper.get_field(seg, 1)
                    datum = ContentHelper.get_field(seg, 4)
                    seg_index = self._find_global_index(msg, seg)

                    if not datum or not service_code:
                        continue

                    if datum not in date_service_map:
                        date_service_map[datum] = []

                    date_service_map[datum].append({
                        "code": service_code,
                        "seg_index": seg_index,
                    })

                # Check for duplicate service codes on the same date
                for datum, entries in date_service_map.items():
                    seen: Dict[str, int] = {}
                    for entry in entries:
                        code = entry["code"]
                        if code in seen:
                            errors.append(
                                ValidationError.error(
                                    stufe=4,
                                    code="1.4.1",
                                    message=(
                                        f'INV-Block {block_idx}: Abrechnungspositionsnummer "{code}" '
                                        f'erscheint mehrfach am Datum "{datum}". Gleiche Leistung am gleichen '
                                        f"Tag muss unterschiedliche Positionsnummern haben oder über "
                                        f"die Anzahl zusammengefasst werden."
                                    ),
                                    segment="EHE",
                                    segment_index=entry["seg_index"],
                                )
                            )
                        else:
                            seen[code] = entry["seg_index"]

        return errors

    def _find_global_index(
        self, msg: Dict[str, Any], target_seg: Dict[str, Any]
    ) -> int:
        segments = msg.get("segments", [])
        start = msg.get("start", 0)

        for idx, seg in enumerate(segments):
            if seg == target_seg:
                return start + idx
        return start