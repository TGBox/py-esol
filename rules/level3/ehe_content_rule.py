import re
from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class EheContentRule(RuleInterface):
    """Rule 1.3.8 — EHE segment content validation."""

    # Schlüssel Kennzeichen Leistungserbringer-Sammelgruppenschlüssel, Anlage 3
    # Abschnitt 8.1.14: welche Abrechnungscodes in welchem Leistungsbereich
    # zulässig sind. Der Leistungsbereich steht im UNB-Segment.
    ABRECHNUNGSCODES_JE_LEISTUNGSBEREICH = {
        "A": {"11", "12", "13", "14", "15", "16", "17", "18", "19"},
        "B": {"21", "22", "23", "24", "25", "26", "27", "28", "29",
              "71", "72", "73", "74"},
        "C": {"31", "32", "33", "34"},
        "D": {"31", "32", "33", "34"},
        "E": {"41", "42", "43", "44", "45", "46", "47", "48", "49"},
        "F": {"50"},
        "G": {"55", "56", "57"},
        "H": {"61"},
        "I": {"62"},
        "J": {"65"},
        "K": {"66"},
        "L": {"63", "67"},
        "M": {"68"},
        "N": {"69"},
        "O": {"75"},
        "P": {"76"},
        "Q": {"91", "92", "93", "94"},
        "R": {"A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"},
        "S": {"B1"},
    }

    @staticmethod
    def _tarifbereich_belegt(bereich: str) -> bool:
        """Anlage 3, 8.1.5.2: belegt sind 00-25, 50-75 und 90-99."""
        zahl = int(bereich)
        return 0 <= zahl <= 25 or 50 <= zahl <= 75 or 90 <= zahl <= 99

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

        leistungsbereich = (
            ContentHelper.get_file_leistungsbereich(context.get_parsed_segments()) or ""
        ).upper()
        erlaubte_codes = self.ABRECHNUNGSCODES_JE_LEISTUNGSBEREICH.get(leistungsbereich)

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
                    elif (
                        abr_code
                        and erlaubte_codes is not None
                        and abr_code not in erlaubte_codes
                    ):
                        # 1.3.8.7 — Abrechnungscode und Leistungsbereich passen
                        # nicht zusammen. Anlage 3, Abschnitt 8.1.14 ordnet die
                        # Abrechnungscodes den Sammelgruppenschlüsseln zu; im
                        # Leistungsbereich B (Heilmittel) sind es 21-29 und
                        # 71-74. Eine Datei mit "B" im UNB und einem
                        # Hilfsmittelcode im EHE ist in sich widersprüchlich.
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.8.7",
                                f'EHE (Block {block_idx}): Abrechnungscode "{abr_code}" '
                                f"gehört nicht zum Leistungsbereich "
                                f"'{leistungsbereich}' des UNB-Segmentes. Zulässig "
                                f"nach Anlage 3 Abschnitt 8.1.14: "
                                + ", ".join(sorted(erlaubte_codes))
                                + ".",
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

                        # 1.3.8.8 — Tarifbereich (1. und 2. Stelle).
                        # Anlage 3, Abschnitt 8.1.5.2 belegt 00 bis 25, 50 bis
                        # 75, 90 und 91 bis 99. Die Bereiche 26 bis 49 und 76
                        # bis 89 führt die Anlage als "noch zu vergeben" — ein
                        # Kennzeichen daraus benennt keinen Tarifbereich.
                        bereich = tarif_kz[:2]
                        if bereich.isdigit() and not self._tarifbereich_belegt(bereich):
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.8.8",
                                    f'EHE (Block {block_idx}): Tarifbereich "{bereich}" '
                                    f"aus dem Tarifkennzeichen \"{tarif_kz}\" ist nach "
                                    f"Anlage 3 Abschnitt 8.1.5.2 noch nicht vergeben "
                                    f"(belegt sind 00-25, 50-75 und 90-99).",
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
                    if pos_nr and len(pos_nr) != 5:
                        # Anlage 1 zum EHE-Feld "Art der abgegebenen Leistung":
                        # "Es muss die vertraglich vereinbarte 5-stellige
                        # bundeseinheitliche Positionsnummer übermittelt
                        # werden." Anlage 3, Abschnitt 8.2.1 gibt die
                        # Schlüsselgröße ebenfalls mit 5 Stellen an. Geprüft
                        # wurde vorher nur die Obergrenze, eine dreistellige
                        # Nummer lief also durch.
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.8.2",
                                f'EHE (Block {block_idx}): Abrechnungspositionsnummer '
                                f'"{pos_nr}" muss genau 5-stellig sein '
                                f"(Anlage 3 Abschnitt 8.2.1), gefunden: "
                                f"{len(pos_nr)} Zeichen.",
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