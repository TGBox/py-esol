from collections import defaultdict
from typing import List
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError
from validation_error import ValidationError
from validation_context import ValidationContext


class SingleRechnungsartRule(RuleInterface):
    """
    Rule 1.1.11 — Single Rechnungsart per file.

    All REC.Rechnungsart values within a file must be identical.
    """

    def get_stufe(self) -> int:
        return 1

    def validate(self, context) -> List:
        errors = []
        parsed_segments = context.get_parsed_segments()
        
        rechnungsarten = set()
        for seg in parsed_segments:
            if seg.get("tag") == "UNH":
                fields = seg.get("fields", [])
                if len(fields) > 1 and isinstance(fields[1], list):
                    art = fields[1][0]  # Z.B. 'SLGA' oder 'SLLA'
                    rechnungsarten.add(art)

        if len(rechnungsarten) > 1:
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.11",
                    f"Gemischte Rechnungsarten in einer Datei nicht erlaubt: {rechnungsarten}"
                )
            )

        return errors