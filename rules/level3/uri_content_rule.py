from typing import Any, Dict, List, Optional

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class UriContentRule(RuleInterface):
    """Rule 1.3.6 — URI segment content validation (Korrekturverfahren)."""

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()
        vk = ContentHelper.get_file_vk(context.get_parsed_segments())

        for msg in messages:
            if msg.get("type") != "SLLA":
                continue

            inv_blocks = ContentHelper.extract_inv_blocks(msg)

            for block_idx, block in enumerate(inv_blocks):
                has_uri = False
                uri_seg = None
                uri_seg_index = None

                for seg in block:
                    if seg.get("tag") == "URI":
                        has_uri = True
                        uri_seg = seg
                        uri_seg_index = self._find_global_index(msg, seg)
                        break

                # 1.3.6.1: URI presence based on VK
                if vk == "01" and has_uri:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.6.1",
                            f"URI (INV-Block {block_idx}): URI-Segment darf bei VK 01 (Erstrechnung) nicht vorhanden sein.",
                            "URI",
                            uri_seg_index
                            if uri_seg_index is not None
                            else (msg["start"] + block_idx),
                        )
                    )

                if vk in ["02", "03", "04", "10"] and not has_uri:
                    inv_seg_index = self._find_global_index(msg, block[0])
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.6.1",
                            f"INV-Block {block_idx}: URI-Segment fehlt. Bei VK {vk} muss ein URI-Segment vorhanden sein.",
                            "INV",
                            inv_seg_index,
                        )
                    )

                if has_uri and uri_seg is not None:
                    errors.extend(
                        self._validate_uri_content(
                            uri_seg, uri_seg_index, block_idx
                        )
                    )

        return errors

    def _validate_uri_content(
        self, seg: Dict[str, Any], seg_index: Optional[int], block_idx: int
    ) -> List[Any]:
        errors = []

        # 1.3.6.2: URI IK
        ik = ContentHelper.get_field(seg, 0)
        if ik and not ContentHelper.is_valid_ik(ik):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.6.2",
                    f'URI (Block {block_idx}): IK "{ik}" ist kein gültiges 9-stelliges IK.',
                    "URI",
                    seg_index,
                )
            )

        # 1.3.6.3: URI Rechnungsnummer format
        sammel_nr = ContentHelper.get_field(seg, 1, 0)
        einzel_nr = ContentHelper.get_field(seg, 1, 1)

        if sammel_nr:
            if len(sammel_nr) > 14:
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.6.3",
                        f'URI (Block {block_idx}): Sammel-Rechnungsnummer "{sammel_nr}" überschreitet 14 Zeichen.',
                        "URI",
                        seg_index,
                    )
                )
            if not ContentHelper.is_valid_rechnungsnummer_part(sammel_nr):
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.6.3",
                        f'URI (Block {block_idx}): Sammel-Rechnungsnummer "{sammel_nr}" hat ungültiges Format.',
                        "URI",
                        seg_index,
                    )
                )

        if einzel_nr and len(einzel_nr) > 6:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.6.3",
                    f'URI (Block {block_idx}): Einzel-Rechnungsnummer "{einzel_nr}" überschreitet 6 Zeichen.',
                    "URI",
                    seg_index,
                )
            )

        # 1.3.6.4: URI Rechnungsdatum
        datum = ContentHelper.get_field(seg, 2)
        if datum and not ContentHelper.is_valid_date(datum):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.6.4",
                    f'URI (Block {block_idx}): Rechnungsdatum "{datum}" ist kein gültiges Datum (JJJJMMTT).',
                    "URI",
                    seg_index,
                )
            )

        # 1.3.6.5: URI Belegnummer
        beleg_nr = ContentHelper.get_field(seg, 3)
        if beleg_nr and len(beleg_nr) > 10:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.6.5",
                    f'URI (Block {block_idx}): Belegnummer "{beleg_nr}" überschreitet 10 Zeichen.',
                    "URI",
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