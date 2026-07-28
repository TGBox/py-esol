import re
from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class InvContentRule(RuleInterface):
    """Rule 1.3.5 — INV segment content validation."""

    VALID_BELEGINFORMATION = [
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
    ]

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()

        belegnummern_per_slga = {}
        current_slga_idx = 0

        for msg_idx, msg in enumerate(messages):
            if msg.get("type") == "SLGA":
                current_slga_idx = msg_idx
                belegnummern_per_slga[current_slga_idx] = []

            if msg.get("type") != "SLLA":
                continue

            inv_blocks = ContentHelper.extract_inv_blocks(msg)

            for block_idx, block in enumerate(inv_blocks):
                inv_seg = block[0]
                seg_index = msg["start"] + self._find_segment_global_offset(
                    msg, inv_seg
                )

                # 1.3.5.1: Versichertennummer
                vers_nr = ContentHelper.get_field(inv_seg, 0)
                if vers_nr:
                    if len(vers_nr) > 12:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.5.1",
                                f'INV (Block {block_idx}): Versichertennummer "{vers_nr}" überschreitet 12 Zeichen.',
                                "INV",
                                seg_index,
                            )
                        )

                    if not re.match(r"^[A-Za-z]\d+$", vers_nr):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.5.1",
                                f'INV (Block {block_idx}): Versichertennummer "{vers_nr}" hat ungültiges Format (Buchstabe + Ziffern erwartet).',
                                "INV",
                                seg_index,
                            )
                        )

                # 1.3.5.2: Versichertenstatus
                status = ContentHelper.get_field(inv_seg, 1)
                if status:
                    if len(status) != 5:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.5.2",
                                f'INV (Block {block_idx}): Versichertenstatus "{status}" muss 5-stellig sein.',
                                "INV",
                                seg_index,
                            )
                        )
                    elif not re.match(r"^\d{5}$", status):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.5.2",
                                f'INV (Block {block_idx}): Versichertenstatus "{status}" muss numerisch sein.',
                                "INV",
                                seg_index,
                            )
                        )

                # 1.3.5.3: Beleginformation
                beleg_info = ContentHelper.get_field(inv_seg, 2)
                if beleg_info:
                    if beleg_info not in self.VALID_BELEGINFORMATION:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.5.3",
                                f'INV (Block {block_idx}): Beleginformation "{beleg_info}" ist ungültig per Schlüssel 8.1.18.',
                                "INV",
                                seg_index,
                            )
                        )

                # 1.3.5.4: Belegnummer — unique within Gesamtrechnung
                beleg_nr = ContentHelper.get_field(inv_seg, 3)
                if beleg_nr:
                    if len(beleg_nr) > 10:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.5.4",
                                f'INV (Block {block_idx}): Belegnummer "{beleg_nr}" überschreitet 10 Zeichen.',
                                "INV",
                                seg_index,
                            )
                        )

                    if current_slga_idx in belegnummern_per_slga:
                        if (
                            beleg_nr
                            in belegnummern_per_slga[current_slga_idx]
                        ):
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.5.4",
                                    f'INV (Block {block_idx}): Belegnummer "{beleg_nr}" ist nicht eindeutig innerhalb der Gesamtrechnung.',
                                    "INV",
                                    seg_index,
                                )
                            )
                        belegnummern_per_slga[current_slga_idx].append(beleg_nr)

        return errors

    def _find_segment_global_offset(
        self, msg: Dict[str, Any], target_seg: Dict[str, Any]
    ) -> int:
        for idx, seg in enumerate(msg.get("segments", [])):
            if seg == target_seg:
                return idx
        return 0