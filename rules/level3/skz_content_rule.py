from typing import Any, Dict, List

from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_error import ValidationError


class SkzContentRule(RuleInterface):
    """
    Regel 1.3.14 — Inhalt des SKZ-Segmentes (Kostenzusage/Genehmigung).

    Das Segment hatte bisher keine Inhaltsprüfung. Geprüft wird gegen:

    * Anlage 1, Abschnitt 5.5.3.3, Segment SKZ: Genehmigungskennzeichen (..20
      AN M), Datum der Genehmigung (8 N M), Art der Genehmigung (2 AN M).
    * Anlage 3, Abschnitt 8.1.17 Art der Genehmigung: zweistellig, die erste
      Stelle ist der Leistungserbringer-Sammelgruppenschlüssel, die zweite die
      Art. Für Heilmittel ist allein B2 besetzt; B1 führt die Anlage als
      "nicht belegt".

    In den vorliegenden Echtdateien kommt kein SKZ vor — die Regel greift also
    erst, wenn eine Kostenzusage übermittelt wird. Genau dann ist sie nützlich:
    ein "A2" in einer Heilmittelrechnung fällt sonst niemandem auf.
    """

    # Anlage 3, Abschnitt 8.1.17 — vollständig
    ART_DER_GENEHMIGUNG = {
        "A1", "A2",
        "B1", "B2",
        "C1", "C2",
        "D1",
        "E1", "E2",
        "F1",
        "G1", "H1", "I1", "J1", "K1", "L1", "M1", "N1",
        "O1",
        "Q1",
        "R1", "R2",
    }

    # Werte, die die Anlage ausdrücklich als "nicht belegt" führt
    NICHT_BELEGT = {"B1"}

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors: List[Any] = []
        leistungsbereich = (
            ContentHelper.get_file_leistungsbereich(context.get_parsed_segments()) or ""
        ).upper()

        for msg in context.get_messages():
            if msg.get("type") != "SLLA":
                continue

            for block_idx, block in enumerate(ContentHelper.extract_inv_blocks(msg)):
                for seg in block:
                    if seg.get("tag") != "SKZ":
                        continue
                    self._pruefe(
                        seg,
                        self._index(msg, seg),
                        block_idx,
                        leistungsbereich,
                        errors,
                    )

        return errors

    def _pruefe(
        self,
        seg: Dict[str, Any],
        seg_index: int,
        block_idx: int,
        leistungsbereich: str,
        errors: List[Any],
    ) -> None:
        kennzeichen = ContentHelper.get_field(seg, 0)
        if kennzeichen and len(kennzeichen) > 20:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.14.1",
                    f"SKZ (Block {block_idx}): Genehmigungskennzeichen "
                    f'"{kennzeichen}" überschreitet 20 Zeichen.',
                    "SKZ",
                    seg_index,
                )
            )

        datum = ContentHelper.get_field(seg, 1)
        if datum and not ContentHelper.is_valid_date(datum):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.14.2",
                    f'SKZ (Block {block_idx}): Datum der Genehmigung "{datum}" ist '
                    f"kein gültiges Datum (JJJJMMTT erwartet).",
                    "SKZ",
                    seg_index,
                )
            )
        elif datum and ContentHelper.is_date_in_future(datum):
            errors.append(
                ValidationError.warning(
                    3,
                    "1.3.14.2",
                    f'SKZ (Block {block_idx}): Datum der Genehmigung "{datum}" liegt '
                    f"in der Zukunft.",
                    "SKZ",
                    seg_index,
                )
            )

        art = (ContentHelper.get_field(seg, 2) or "").strip()
        if not art:
            return

        if art not in self.ART_DER_GENEHMIGUNG:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.14.3",
                    f'SKZ (Block {block_idx}): Art der Genehmigung "{art}" ist kein '
                    f"Schlüsselwert nach Anlage 3 Abschnitt 8.1.17.",
                    "SKZ",
                    seg_index,
                )
            )
            return

        if art in self.NICHT_BELEGT:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.14.3",
                    f'SKZ (Block {block_idx}): Art der Genehmigung "{art}" führt die '
                    f"Anlage 3 (Abschnitt 8.1.17) als nicht belegt.",
                    "SKZ",
                    seg_index,
                )
            )
            return

        # Die erste Stelle ist der Leistungserbringer-Sammelgruppenschlüssel und
        # muss zum Leistungsbereich der Datei passen.
        if leistungsbereich and art[0] != leistungsbereich:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.14.4",
                    f'SKZ (Block {block_idx}): Art der Genehmigung "{art}" gehört zum '
                    f"Leistungsbereich '{art[0]}', die Datei weist im UNB-Segment aber "
                    f"'{leistungsbereich}' aus.",
                    "SKZ",
                    seg_index,
                )
            )

    @staticmethod
    def _index(msg: Dict[str, Any], target: Dict[str, Any]) -> int:
        for idx, seg in enumerate(msg.get("segments", [])):
            if seg is target:
                return msg["start"] + idx
        return msg["start"]
