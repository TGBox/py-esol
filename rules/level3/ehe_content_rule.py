import re
from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class EheContentRule(RuleInterface):
    """Rule 1.3.8 — EHE segment content validation."""

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()

        rechnungs_datum = None
        for seg in context.get_parsed_segments():
            if seg.get("tag") == "REC":
                rechnungs_datum = ContentHelper.get_field(seg, 1)
                break

        for msg in messages:
            if msg.get("type") != "SLLA":
                continue

            inv_blocks = ContentHelper.extract_inv_blocks(msg)

            for block_idx, block in enumerate(inv_blocks):
                pos_date_combos = {}

                for seg in block:
                    if seg.get("tag") != "EHE":
                        continue

                    seg_index = self._find_global_index(msg, seg)

                    abr_code = ContentHelper.get_field(seg, 0, 0)
                    tarif_kz = ContentHelper.get_field(seg, 0, 1)

                    if abr_code and len(abr_code) != 2:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.8.1",
                                f'EHE (Block {block_idx}): Abrechnungscode "{abr_code}" muss 2-stellig sein.',
                                "EHE",
                                seg_index,
                            )
                        )

                    if tarif_kz:
                        if len(tarif_kz) != 5:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.8.1",
                                    f'EHE (Block {block_idx}): Tarifkennzeichen "{tarif_kz}" muss 5-stellig sein.',
                                    "EHE",
                                    seg_index,
                                )
                            )

                        sondertarif = tarif_kz[2:5]
                        if re.search(r"[a-z]", sondertarif):
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.8.1",
                                    f'EHE (Block {block_idx}): Tarifkennzeichen "{tarif_kz}" — Sondertarifbuchstaben müssen Großbuchstaben sein.',
                                    "EHE",
                                    seg_index,
                                )
                            )

                    pos_nr = ContentHelper.get_field(seg, 1)
                    if pos_nr and len(pos_nr) > 5:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.8.2",
                                f'EHE (Block {block_idx}): Abrechnungspositionsnummer "{pos_nr}" überschreitet 5 Zeichen.',
                                "EHE",
                                seg_index,
                            )
                        )

                    anzahl = ContentHelper.parse_decimal(
                        ContentHelper.get_field(seg, 2)
                    )
                    if anzahl is not None and anzahl <= 0:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.8.3",
                                f"EHE (Block {block_idx}): Anzahl/Menge muss > 0 sein, gefunden: {ContentHelper.get_field(seg, 2)}.",
                                "EHE",
                                seg_index,
                            )
                        )

                    einzelbetrag = ContentHelper.parse_decimal(
                        ContentHelper.get_field(seg, 3)
                    )
                    if einzelbetrag is not None and einzelbetrag < 0:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.8.4",
                                f"EHE (Block {block_idx}): Einzelbetrag muss >= 0 sein, gefunden: {ContentHelper.get_field(seg, 3)}.",
                                "EHE",
                                seg_index,
                            )
                        )

                    datum_le = ContentHelper.get_field(seg, 4)
                    if datum_le:
                        if not ContentHelper.is_valid_date(datum_le):
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.8.5",
                                    f'EHE (Block {block_idx}): Datum Leistungserbringung "{datum_le}" ist kein gültiges Datum.',
                                    "EHE",
                                    seg_index,
                                )
                            )
                        elif rechnungs_datum and datum_le > rechnungs_datum:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.8.5",
                                    f'EHE (Block {block_idx}): Datum Leistungserbringung "{datum_le}" liegt nach dem Rechnungsdatum "{rechnungs_datum}".',
                                    "EHE",
                                    seg_index,
                                )
                            )

                    if pos_nr and datum_le:
                        key = f"{pos_nr}:{datum_le}"
                        pos_date_combos[key] = (
                            pos_date_combos.get(key, 0) + 1
                        )

                for key, count in pos_date_combos.items():
                    if count > 1:
                        pos_nr, datum = key.split(":", 1)
                        errors.append(
                            ValidationError.warning(
                                3,
                                "1.3.8.7",
                                f'INV-Block {block_idx}: Abrechnungspositionsnummer "{pos_nr}" erscheint {count}x am Datum "{datum}". '
                                f"Gleiche Positionen am gleichen Tag sollten in einem EHE zusammengefasst werden (via Anzahl).",
                                "EHE",
                                None,
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