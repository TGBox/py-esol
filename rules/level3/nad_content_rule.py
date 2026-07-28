import re
from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class NadContentRule(RuleInterface):
    """Rule 1.3.7 — NAD segment content validation."""

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
                inv_seg = block[0]
                vers_nr = ContentHelper.get_field(inv_seg, 0)
                vers_status = ContentHelper.get_field(inv_seg, 1)
                has_versicherten_info = bool(vers_nr or vers_status)

                for seg in block:
                    if seg.get("tag") != "NAD":
                        continue

                    seg_index = self._find_global_index(msg, seg)

                    # 1.3.7.1: Nachname
                    nachname = ContentHelper.get_field(seg, 0)
                    if nachname and len(nachname) > 47:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.7.1",
                                f"NAD (Block {block_idx}): Nachname überschreitet 47 Zeichen.",
                                "NAD",
                                seg_index,
                            )
                        )

                    # 1.3.7.2: Vorname
                    vorname = ContentHelper.get_field(seg, 1)
                    if vorname and len(vorname) > 30:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.7.2",
                                f"NAD (Block {block_idx}): Vorname überschreitet 30 Zeichen.",
                                "NAD",
                                seg_index,
                            )
                        )

                    # 1.3.7.3: Geburtsdatum
                    geb_datum = ContentHelper.get_field(seg, 2)
                    if geb_datum:
                        if not ContentHelper.is_valid_date(
                            geb_datum, allow_partial_zero=True
                        ):
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.7.3",
                                    f'NAD (Block {block_idx}): Geburtsdatum "{geb_datum}" ist kein gültiges Datum.',
                                    "NAD",
                                    seg_index,
                                )
                            )
                        elif ContentHelper.is_date_in_future(geb_datum):
                            errors.append(
                                ValidationError.warning(
                                    3,
                                    "1.3.7.3",
                                    f'NAD (Block {block_idx}): Geburtsdatum "{geb_datum}" liegt in der Zukunft.',
                                    "NAD",
                                    seg_index,
                                )
                            )

                    # 1.3.7.4: Address mandatory if Versichertennummer/Status unknown
                    if not has_versicherten_info:
                        strasse = ContentHelper.get_field(seg, 3)
                        plz = ContentHelper.get_field(seg, 4)
                        ort = ContentHelper.get_field(seg, 5)

                        if not strasse:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.7.4",
                                    f"NAD (Block {block_idx}): Straße ist Pflicht wenn Versichertennummer/Status unbekannt.",
                                    "NAD",
                                    seg_index,
                                )
                            )
                        if not plz:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.7.4",
                                    f"NAD (Block {block_idx}): PLZ ist Pflicht wenn Versichertennummer/Status unbekannt.",
                                    "NAD",
                                    seg_index,
                                )
                            )
                        if not ort:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.7.4",
                                    f"NAD (Block {block_idx}): Ort ist Pflicht wenn Versichertennummer/Status unbekannt.",
                                    "NAD",
                                    seg_index,
                                )
                            )

                        land = ContentHelper.get_field(seg, 6)
                        if not land and plz:
                            if not re.match(r"^\d{5}$", plz):
                                errors.append(
                                    ValidationError.error(
                                        3,
                                        "1.3.7.4",
                                        f'NAD (Block {block_idx}): PLZ "{plz}" muss 5-stellig numerisch sein (Inland).',
                                        "NAD",
                                        seg_index,
                                    )
                                )

                    break  # One NAD per INV block

        return errors

    def _find_global_index(
        self, msg: Dict[str, Any], target_seg: Dict[str, Any]
    ) -> int:
        for idx, seg in enumerate(msg.get("segments", [])):
            if seg == target_seg:
                return msg["start"] + idx
        return msg["start"]