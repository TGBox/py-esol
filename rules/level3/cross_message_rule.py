from typing import Any, Dict, List, Optional

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class CrossMessageRule(RuleInterface):
    """Rule 1.3.15 — Cross-message consistency validation."""

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()

        groups = self._group_messages_by_slga(messages)

        for group in groups:
            slga = group.get("slga")
            slla_list = group.get("slla", [])

            if not slga or not slla_list:
                continue

            slga_fkt = self._find_segment_in_message(slga, "FKT")
            slga_rec = self._find_segment_in_message(slga, "REC")

            if not slga_fkt:
                continue

            slga_ik_kt = ContentHelper.get_field(slga_fkt, 3)
            slga_ik_kk = ContentHelper.get_field(slga_fkt, 4)
            slga_ik_rs = ContentHelper.get_field(slga_fkt, 2)

            slga_sammel_nr = (
                ContentHelper.get_field(slga_rec, 0, 0) if slga_rec else None
            )
            slga_einzel_nr = (
                ContentHelper.get_field(slga_rec, 0, 1) if slga_rec else None
            )
            slga_datum = (
                ContentHelper.get_field(slga_rec, 1) if slga_rec else None
            )
            slga_art = (
                ContentHelper.get_field(slga_rec, 2) if slga_rec else None
            )

            all_belegnummern = {}

            for slla in slla_list:
                slla_fkt = self._find_segment_in_message(slla, "FKT")
                slla_rec = self._find_segment_in_message(slla, "REC")

                if slla_fkt:
                    fkt_index = self._find_segment_global_index(slla, "FKT")

                    slla_ik_kt = ContentHelper.get_field(slla_fkt, 3)
                    if slla_ik_kt and slga_ik_kt and slla_ik_kt != slga_ik_kt:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.15.1",
                                f'SLLA.FKT: IK Kostenträger "{slla_ik_kt}" stimmt nicht mit SLGA.FKT "{slga_ik_kt}" überein.',
                                "FKT",
                                fkt_index,
                            )
                        )

                    slla_ik_kk = ContentHelper.get_field(slla_fkt, 4)
                    if slla_ik_kk and slga_ik_kk and slla_ik_kk != slga_ik_kk:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.15.1",
                                f'SLLA.FKT: IK Krankenkasse "{slla_ik_kk}" stimmt nicht mit SLGA.FKT "{slga_ik_kk}" überein.',
                                "FKT",
                                fkt_index,
                            )
                        )

                if slla_rec and slga_rec:
                    rec_index = self._find_segment_global_index(slla, "REC")
                    slla_sammel_nr = ContentHelper.get_field(slla_rec, 0, 0)
                    slla_einzel_nr = ContentHelper.get_field(slla_rec, 0, 1)
                    slla_datum = ContentHelper.get_field(slla_rec, 1)
                    slla_art = ContentHelper.get_field(slla_rec, 2)

                    if (
                        slla_sammel_nr != slga_sammel_nr
                        or slla_einzel_nr != slga_einzel_nr
                        or slla_datum != slga_datum
                        or slla_art != slga_art
                    ):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.15.2",
                                "SLLA.REC stimmt nicht mit SLGA.REC überein.",
                                "REC",
                                rec_index,
                            )
                        )

                inv_blocks = ContentHelper.extract_inv_blocks(slla)
                for block_idx, block in enumerate(inv_blocks):
                    beleg_nr = ContentHelper.get_field(block[0], 3)
                    if beleg_nr:
                        inv_seg_index = self._find_global_index(slla, block[0])
                        if beleg_nr in all_belegnummern:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.15.4",
                                    f'INV: Belegnummer "{beleg_nr}" ist nicht eindeutig innerhalb der Gesamtrechnung '
                                    f"(erstmals an Position {all_belegnummern[beleg_nr]}).",
                                    "INV",
                                    inv_seg_index,
                                )
                            )
                        else:
                            all_belegnummern[beleg_nr] = inv_seg_index

        return errors

    def _group_messages_by_slga(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        groups = []
        current_group = None

        for msg in messages:
            if msg.get("type") == "SLGA":
                if current_group is not None:
                    groups.append(current_group)
                current_group = {"slga": msg, "slla": []}
            elif msg.get("type") == "SLLA" and current_group is not None:
                current_group["slla"].append(msg)

        if current_group is not None:
            groups.append(current_group)

        return groups

    def _find_segment_in_message(
        self, msg: Dict[str, Any], tag: str
    ) -> Optional[Dict[str, Any]]:
        for seg in msg.get("segments", []):
            if seg.get("tag") == tag:
                return seg
        return None

    def _find_segment_global_index(self, msg: Dict[str, Any], tag: str) -> int:
        for idx, seg in enumerate(msg.get("segments", [])):
            if seg.get("tag") == tag:
                return msg["start"] + idx
        return msg["start"]

    def _find_global_index(
        self, msg: Dict[str, Any], target_seg: Dict[str, Any]
    ) -> int:
        for idx, seg in enumerate(msg.get("segments", [])):
            if seg == target_seg:
                return msg["start"] + idx
        return msg["start"]