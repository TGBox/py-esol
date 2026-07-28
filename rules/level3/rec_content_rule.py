from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class RecContentRule(RuleInterface):
    """Rule 1.3.4 — REC segment content validation."""

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()
        slga_rec_data = None

        for msg in messages:
            for seg_offset, seg in enumerate(msg.get("segments", [])):
                if seg.get("tag") != "REC":
                    continue

                seg_index = msg["start"] + seg_offset

                sammel_nr = ContentHelper.get_field(seg, 0, 0)
                einzel_nr = ContentHelper.get_field(seg, 0, 1)

                # 1.3.4.2: Sammel-Rechnungsnummer
                if sammel_nr:
                    if len(sammel_nr) > 14:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.4.2",
                                f'REC: Sammel-Rechnungsnummer "{sammel_nr}" überschreitet 14 Zeichen.',
                                "REC",
                                seg_index,
                            )
                        )
                    if not ContentHelper.is_valid_rechnungsnummer_part(
                        sammel_nr
                    ):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.4.1",
                                f'REC: Sammel-Rechnungsnummer "{sammel_nr}" enthält ungültige Zeichen oder Formatierung.',
                                "REC",
                                seg_index,
                            )
                        )

                # 1.3.4.3: Einzel-Rechnungsnummer
                if einzel_nr:
                    if len(einzel_nr) > 6:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.4.3",
                                f'REC: Einzel-Rechnungsnummer "{einzel_nr}" überschreitet 6 Zeichen.',
                                "REC",
                                seg_index,
                            )
                        )
                    if (
                        einzel_nr != "0"
                        and not ContentHelper.is_valid_rechnungsnummer_part(
                            einzel_nr
                        )
                    ):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.4.1",
                                f'REC: Einzel-Rechnungsnummer "{einzel_nr}" enthält ungültige Zeichen oder Formatierung.',
                                "REC",
                                seg_index,
                            )
                        )

                # 1.3.4.4: Rechnungsdatum
                datum = ContentHelper.get_field(seg, 1)
                if datum:
                    if not ContentHelper.is_valid_date(datum):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.4.4",
                                f'REC: Rechnungsdatum "{datum}" ist kein gültiges Datum (JJJJMMTT).',
                                "REC",
                                seg_index,
                            )
                        )
                    elif ContentHelper.is_date_in_future(datum):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.4.4",
                                f'REC: Rechnungsdatum "{datum}" liegt in der Zukunft.',
                                "REC",
                                seg_index,
                            )
                        )

                # 1.3.4.5: Rechnungsart — 1, 2, or 3
                art = ContentHelper.get_field(seg, 2)
                if art and art not in ["1", "2", "3"]:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.4.5",
                            f'REC: Rechnungsart "{art}" ist ungültig. Erlaubt: 1, 2, 3.',
                            "REC",
                            seg_index,
                        )
                    )

                if msg.get("type") == "SLGA":
                    slga_rec_data = {
                        "sammelNr": sammel_nr,
                        "einzelNr": einzel_nr,
                        "datum": datum,
                        "art": art,
                    }

                # 1.3.4.6: SLLA.REC must match SLGA.REC
                if msg.get("type") == "SLLA" and slga_rec_data is not None:
                    if (
                        sammel_nr != slga_rec_data["sammelNr"]
                        or einzel_nr != slga_rec_data["einzelNr"]
                        or datum != slga_rec_data["datum"]
                        or art != slga_rec_data["art"]
                    ):
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.4.6",
                                f'SLLA.REC: Rechnungsdaten stimmen nicht mit SLGA.REC überein '
                                f'(Sammel-Nr: "{sammel_nr}" vs "{slga_rec_data["sammelNr"]}", '
                                f'Einzel-Nr: "{einzel_nr}" vs "{slga_rec_data["einzelNr"]}", '
                                f'Datum: "{datum}" vs "{slga_rec_data["datum"]}", '
                                f'Art: "{art}" vs "{slga_rec_data["art"]}").',
                                "REC",
                                seg_index,
                            )
                        )

                break  # Only one REC per message

        return errors