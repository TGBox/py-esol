import re
from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class DiaContentRule(RuleInterface):
    """Rule 1.3.10 — DIA segment content validation."""

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()

        for msg in messages:
            if msg.get("type") != "SLLA":
                continue

            inv_blocks = ContentHelper.extract_inv_blocks(msg)

            for block_idx, block in enumerate(inv_blocks):
                dia_segments = []
                has_zhe = False

                for seg in block:
                    if seg.get("tag") == "ZHE":
                        has_zhe = True
                    if seg.get("tag") == "DIA":
                        dia_segments.append(seg)

                if has_zhe and not dia_segments:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.10.3",
                            f"INV-Block {block_idx}: Mindestens ein DIA-Segment pro ZHE erforderlich.",
                            "DIA",
                            msg["start"],
                        )
                    )

                for dia_seg in dia_segments:
                    seg_index = self._find_global_index(msg, dia_seg)
                    diag_code = ContentHelper.get_field(dia_seg, 0)
                    diag_text = ContentHelper.get_field(dia_seg, 1)

                    if diag_code:
                        if len(diag_code) > 12:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.10.1",
                                    f'DIA (Block {block_idx}): Diagnoseschlüssel "{diag_code}" überschreitet 12 Zeichen.',
                                    "DIA",
                                    seg_index,
                                )
                            )

                        if not re.match(
                            r"^[A-Z]\d{2}(\.\d{1,4})?(\s*[A-Z]+)*$",
                            diag_code,
                            re.IGNORECASE,
                        ):
                            errors.append(
                                ValidationError.warning(
                                    3,
                                    "1.3.10.1",
                                    f'DIA (Block {block_idx}): Diagnoseschlüssel "{diag_code}" entspricht nicht dem üblichen ICD-10-Format.',
                                    "DIA",
                                    seg_index,
                                )
                            )

                    if not diag_code and not diag_text:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.10.2",
                                f"DIA (Block {block_idx}): Weder Diagnoseschlüssel noch Diagnosetext angegeben. Mindestens eines muss gefüllt sein.",
                                "DIA",
                                seg_index,
                            )
                        )

                    if diag_text and len(diag_text) > 70:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.10.2",
                                f"DIA (Block {block_idx}): Diagnosetext überschreitet 70 Zeichen.",
                                "DIA",
                                seg_index,
                            )
                        )

        return errors

    def _find_global_index(
        self, msg: Dict[str, Any], target_seg: Dict[str, Any]
    ) -> int:
        for idx, seg in enumerate(msg.get("segments", [])):
            if seg == target_seg:
                return msg["start"] + idx
        return msg["start"]