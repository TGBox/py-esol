from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError

class BesContentRule(RuleInterface):
    """Rule 1.3.11 — BES segment content validation (Betrags-Summen)."""

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
                bes_seg = None
                bes_seg_index = None
                detail_segments = []
                mws_segments = []

                detail_tags = {"EHE", "EHI", "EHK", "EHH", "EKT", "EHB", "ENF", "ESP", "EGV", "EHP", "AHK", "EMP"}

                for seg in block:
                    tag = seg.get("tag")
                    if tag == "BES":
                        bes_seg = seg
                        bes_seg_index = self._find_global_index(msg, seg)
                    elif tag in detail_tags:
                        detail_segments.append(seg)
                    elif tag == "MWS":
                        mws_segments.append(seg)

                if vk == "03":
                    if bes_seg is not None:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.11.1",
                                f"BES (Block {block_idx}): BES-Segment darf bei VK 03 (Zuzahlungsforderung) nicht vorhanden sein.",
                                "BES",
                                bes_seg_index,
                            )
                        )
                    continue

                if vk in ["01", "02", "04", "10"] and bes_seg is None:
                    inv_seg_index = self._find_global_index(msg, block[0])
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.11.1",
                            f"INV-Block {block_idx}: BES-Segment fehlt. Bei VK {vk} muss ein BES-Segment vorhanden sein.",
                            "INV",
                            inv_seg_index,
                        )
                    )
                    continue

                if bes_seg is None:
                    continue

                # 1.3.11.2 Brutto Calculation
                calculated_brutto = 0.0
                calculated_proz_zuz = 0.0

                for seg in detail_segments:
                    tag = seg.get("tag")
                    if tag == "EHI":
                        anz_idx, betrag_idx, zuz_idx = 2, 4, None
                    elif tag == "ENF":
                        anz_idx, betrag_idx, zuz_idx = 3, 4, 6
                    elif tag == "EHE":
                        anz_idx, betrag_idx, zuz_idx = 2, 3, 5
                    else:
                        anz_idx, betrag_idx, zuz_idx = 2, 3, None

                    anzahl = (
                        ContentHelper.parse_decimal(
                            ContentHelper.get_field(seg, anz_idx)
                        )
                        or 0.0
                    )
                    einzelbetrag = (
                        ContentHelper.parse_decimal(
                            ContentHelper.get_field(seg, betrag_idx)
                        )
                        or 0.0
                    )
                    calculated_brutto += einzelbetrag * anzahl

                    if zuz_idx is not None:
                        betrag_zuz = ContentHelper.parse_decimal(
                            ContentHelper.get_field(seg, zuz_idx)
                        )
                        if betrag_zuz is not None:
                            calculated_proz_zuz += betrag_zuz * anzahl

                total_mws = 0.0
                for mws in mws_segments:
                    mws_betrag = (
                        ContentHelper.parse_decimal(
                            ContentHelper.get_field(mws, 1)
                        )
                        or 0.0
                    )
                    total_mws += mws_betrag

                calculated_brutto += total_mws
                calculated_brutto = ContentHelper.round_commercial(
                    calculated_brutto
                )

                bes_brutto = (
                    ContentHelper.parse_decimal(
                        ContentHelper.get_field(bes_seg, 0)
                    )
                    or 0.0
                )
                bes_brutto = ContentHelper.round_commercial(bes_brutto)

                if abs(bes_brutto - calculated_brutto) > 0.005:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.11.2",
                            f"BES (Block {block_idx}): Gesamtbetrag Brutto {ContentHelper.format_decimal(bes_brutto)} "
                            f"stimmt nicht mit berechnetem Wert {ContentHelper.format_decimal(calculated_brutto)} überein "
                            f"(Differenz: {ContentHelper.format_decimal(abs(bes_brutto - calculated_brutto))}).",
                            "BES",
                            bes_seg_index,
                        )
                    )

                # 1.3.11.4 Proz Zuzahlung
                calculated_proz_zuz = ContentHelper.round_commercial(
                    calculated_proz_zuz
                )

                bes_proz_zuz = ContentHelper.parse_decimal(
                    ContentHelper.get_field(bes_seg, 2)
                )
                if bes_proz_zuz is not None:
                    bes_proz_zuz = ContentHelper.round_commercial(bes_proz_zuz)
                    if abs(bes_proz_zuz - calculated_proz_zuz) > 0.005:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.11.4",
                                f"BES (Block {block_idx}): Gesamtbetrag prozentuale Zuzahlung {ContentHelper.format_decimal(bes_proz_zuz)} "
                                f"stimmt nicht mit berechnetem Wert {ContentHelper.format_decimal(calculated_proz_zuz)} überein.",
                                "BES",
                                bes_seg_index,
                            )
                        )

                # 1.3.11.3 Gesamtbetrag Zuzahlung
                bes_ges_zuz = ContentHelper.parse_decimal(
                    ContentHelper.get_field(bes_seg, 1)
                )
                bes_pausch_zuz = ContentHelper.parse_decimal(
                    ContentHelper.get_field(bes_seg, 3)
                )

                if bes_ges_zuz is not None:
                    calc_proz_zuz = bes_proz_zuz or 0.0
                    calc_pausch_zuz = bes_pausch_zuz or 0.0
                    calculated_ges_zuz = ContentHelper.round_commercial(
                        calc_proz_zuz + calc_pausch_zuz
                    )
                    bes_ges_zuz = ContentHelper.round_commercial(bes_ges_zuz)

                    if abs(bes_ges_zuz - calculated_ges_zuz) > 0.005:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.11.3",
                                f"BES (Block {block_idx}): Gesamtbetrag Zuzahlung {ContentHelper.format_decimal(bes_ges_zuz)} "
                                f"≠ prozentuale Zuzahlung {ContentHelper.format_decimal(calc_proz_zuz)} "
                                f"+ pauschale Zuzahlung {ContentHelper.format_decimal(calc_pausch_zuz)} "
                                f"= {ContentHelper.format_decimal(calculated_ges_zuz)}.",
                                "BES",
                                bes_seg_index,
                            )
                        )

                # 1.3.11.5 Pauschale Zuzahlung Max Limit
                if bes_pausch_zuz is not None and bes_pausch_zuz > 0:
                    max_pausch = bes_brutto - (bes_proz_zuz or 0.0)
                    expected_pausch = min(10.00, max_pausch)
                    expected_pausch = ContentHelper.round_commercial(
                        max(0.0, expected_pausch)
                    )

                    if abs(bes_pausch_zuz - expected_pausch) > 0.005:
                        errors.append(
                            ValidationError.warning(
                                3,
                                "1.3.11.5",
                                f"BES (Block {block_idx}): Pauschaler Zuzahlungsbetrag {ContentHelper.format_decimal(bes_pausch_zuz)} "
                                f"— erwartet: {ContentHelper.format_decimal(expected_pausch)} "
                                f"(10,00 EUR, max Brutto - proz. Zuzahlung).",
                                "BES",
                                bes_seg_index,
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