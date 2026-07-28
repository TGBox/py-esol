import re
from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class ZheContentRule(RuleInterface):
    """Rule 1.3.9 — ZHE segment content validation (Zusatzinfo Verordnung Heilmittel)."""

    VALID_ZUZAHLUNGSKZ = [
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

    VALID_VERORDNUNGSART = [
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "99",
    ]

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
                for seg in block:
                    if seg.get("tag") != "ZHE":
                        continue

                    seg_index = self._find_global_index(msg, seg)
                    self._validate_zhe(seg, seg_index, block_idx, errors)

                    break  # One ZHE per INV block

        return errors

    def _validate_zhe(
        self,
        seg: Dict[str, Any],
        seg_index: int,
        block_idx: int,
        errors: List[Any],
    ) -> None:
        # 1.3.9.1: BSNR
        bsnr = ContentHelper.get_field(seg, 0)
        if bsnr and not re.match(r"^\d{1,9}$", bsnr):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.9.1",
                    f'ZHE (Block {block_idx}): BSNR "{bsnr}" muss numerisch sein (max 9 Stellen).',
                    "ZHE",
                    seg_index,
                )
            )

        # 1.3.9.2: LANR
        lanr = ContentHelper.get_field(seg, 1)
        if lanr and not re.match(r"^\d{1,9}$", lanr):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.9.2",
                    f'ZHE (Block {block_idx}): LANR "{lanr}" muss numerisch sein (max 9 Stellen).',
                    "ZHE",
                    seg_index,
                )
            )

        # 1.3.9.3: Verordnungsdatum
        verordnungs_datum = ContentHelper.get_field(seg, 2)
        if verordnungs_datum and not ContentHelper.is_valid_date(
            verordnungs_datum
        ):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.9.3",
                    f'ZHE (Block {block_idx}): Verordnungsdatum "{verordnungs_datum}" ist kein gültiges Datum.',
                    "ZHE",
                    seg_index,
                )
            )

        # 1.3.9.4: Zuzahlungskennzeichen
        zuz_kz = ContentHelper.get_field(seg, 3)
        if zuz_kz and zuz_kz not in self.VALID_ZUZAHLUNGSKZ:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.9.4",
                    f'ZHE (Block {block_idx}): Zuzahlungskennzeichen "{zuz_kz}" ist ungültig per Schlüssel 8.1.3.',
                    "ZHE",
                    seg_index,
                )
            )

        # 1.3.9.5: Diagnosegruppe
        diag_gruppe = ContentHelper.get_field(seg, 4)
        if diag_gruppe:
            if len(diag_gruppe) > 4:
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.9.5",
                        f'ZHE (Block {block_idx}): Diagnosegruppe "{diag_gruppe}" überschreitet 4 Zeichen.',
                        "ZHE",
                        seg_index,
                    )
                )
            if not re.match(r"^[0-9A-Za-z]+$", diag_gruppe):
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.9.5",
                        f'ZHE (Block {block_idx}): Diagnosegruppe "{diag_gruppe}" darf nur Ziffern und Buchstaben enthalten (keine Umlaute, keine Leerzeichen).',
                        "ZHE",
                        seg_index,
                    )
                )

        # 1.3.9.6: Verordnungsart
        verordnungsart = ContentHelper.get_field(seg, 5)
        if verordnungsart and not re.match(r"^\d{2}$", verordnungsart):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.9.6",
                    f'ZHE (Block {block_idx}): Verordnungsart "{verordnungsart}" muss 2-stellig numerisch sein.',
                    "ZHE",
                    seg_index,
                )
            )

        # 1.3.9.7: Leitsymptomatik
        leitsym = ContentHelper.get_field(seg, 12)
        if leitsym:
            if len(leitsym) != 4:
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.9.7",
                        f'ZHE (Block {block_idx}): Leitsymptomatik "{leitsym}" muss 4-stellig sein.',
                        "ZHE",
                        seg_index,
                    )
                )
            elif leitsym != "9999" and not re.match(r"^[01]{4}$", leitsym):
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.9.7",
                        f'ZHE (Block {block_idx}): Leitsymptomatik "{leitsym}" muss aus 0 und 1 bestehen (oder 9999).',
                        "ZHE",
                        seg_index,
                    )
                )

            # 1.3.9.8: Individuelle Leitsymptomatik
            ind_leitsym = ContentHelper.get_field(seg, 13)
            if leitsym != "9999":
                needs_individual = False
                if leitsym == "0000":
                    needs_individual = True
                elif len(leitsym) == 4 and leitsym[3] == "1":
                    needs_individual = True

                if needs_individual and not ind_leitsym:
                    errors.append(
                        ValidationError.warning(
                            3,
                            "1.3.9.8",
                            f'ZHE (Block {block_idx}): Individuelle Leitsymptomatik fehlt (Pflicht wenn Leitsymptomatik="{leitsym}").',
                            "ZHE",
                            seg_index,
                        )
                    )

        # 1.3.9.9: Dringlicher Behandlungsbedarf
        dringend = ContentHelper.get_field(seg, 14)
        if dringend and dringend not in ["0", "1"]:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.9.9",
                    f'ZHE (Block {block_idx}): Dringlicher Behandlungsbedarf "{dringend}" muss 0 oder 1 sein.',
                    "ZHE",
                    seg_index,
                )
            )

        # 1.3.9.10: Heilmittel-Bereich
        hm_bereich = ContentHelper.get_field(seg, 15)
        if hm_bereich and hm_bereich not in ["1", "2", "3", "4", "5"]:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.9.10",
                    f'ZHE (Block {block_idx}): Heilmittel-Bereich "{hm_bereich}" muss 1-5 sein.',
                    "ZHE",
                    seg_index,
                )
            )

        # 1.3.9.11: Therapiefrequenz
        therapie_freq = ContentHelper.get_field(seg, 16)
        if therapie_freq and not re.match(r"^\d$", therapie_freq):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.9.11",
                    f'ZHE (Block {block_idx}): Therapiefrequenz "{therapie_freq}" muss einstellig numerisch sein.',
                    "ZHE",
                    seg_index,
                )
            )

    def _find_global_index(
        self, msg: Dict[str, Any], target_seg: Dict[str, Any]
    ) -> int:
        for idx, seg in enumerate(msg.get("segments", [])):
            if seg == target_seg:
                return msg["start"] + idx
        return msg["start"]