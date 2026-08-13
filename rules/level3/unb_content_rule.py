import re
from typing import Any, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class UnbContentRule(RuleInterface):
    """Rule 1.3.1 — UNB segment content validation."""

    VALID_LEISTUNGSBEREICHE = [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "J",
        "K",
        "L",
        "M",
        "N",
        "O",
        "P",
        "Q",
        "R",
        "S",
    ]

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        unb = context.find_first_segment("UNB")

        if unb is None:
            return errors

        seg_index = context.find_first_segment_index("UNB") or 0

        # 1.3.1.1: Syntax identifier must be UNOC:3
        syntax_id = ContentHelper.get_field(unb, 0, 0)
        syntax_ver = ContentHelper.get_field(unb, 0, 1)
        if syntax_id != "UNOC" or syntax_ver != "3":
            actual = ContentHelper.get_field(unb, 0)
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.1.1",
                    f'UNB: Syntaxkennung muss "UNOC:3" sein, gefunden: "{actual}".',
                    "UNB",
                    seg_index,
                )
            )

        # 1.3.1.2: Absender-IK
        absender_ik = ContentHelper.get_field(unb, 1)
        if absender_ik:
            if not ContentHelper.is_valid_ik(absender_ik):
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.1.2",
                        f'UNB: Absender-IK "{absender_ik}" ist kein gültiges 9-stelliges IK.',
                        "UNB",
                        seg_index,
                    )
                )
            elif not ContentHelper.is_valid_ik_check_digit(absender_ik):
                errors.append(
                    ValidationError.warning(
                        3,
                        "1.3.1.2",
                        f'UNB: Absender-IK "{absender_ik}" hat eine ungültige Prüfziffer.',
                        "UNB",
                        seg_index,
                    )
                )

            self._check_absender_match(
                context, absender_ik, seg_index, errors
            )

        # 1.3.1.3: Empfänger-IK
        empfaenger_ik = ContentHelper.get_field(unb, 2)
        if empfaenger_ik:
            if not ContentHelper.is_valid_ik(empfaenger_ik):
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.1.3",
                        f'UNB: Empfänger-IK "{empfaenger_ik}" ist kein gültiges 9-stelliges IK.',
                        "UNB",
                        seg_index,
                    )
                )
            elif not ContentHelper.is_valid_ik_check_digit(empfaenger_ik):
                errors.append(
                    ValidationError.warning(
                        3,
                        "1.3.1.3",
                        f'UNB: Empfänger-IK "{empfaenger_ik}" hat eine ungültige Prüfziffer.',
                        "UNB",
                        seg_index,
                    )
                )

        # 1.3.1.4: Datum/Uhrzeit
        datum = ContentHelper.get_field(unb, 3, 0)
        uhrzeit = ContentHelper.get_field(unb, 3, 1)

        if datum and not ContentHelper.is_valid_date(datum):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.1.4",
                    f'UNB: Erstelldatum "{datum}" ist kein gültiges Datum (JJJJMMTT).',
                    "UNB",
                    seg_index,
                )
            )

        if uhrzeit and not ContentHelper.is_valid_time(uhrzeit):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.1.4",
                    f'UNB: Erstelluhrzeit "{uhrzeit}" ist keine gültige Uhrzeit (HHMM).',
                    "UNB",
                    seg_index,
                )
            )

        # 1.3.1.5: Datenaustauschreferenz — max 14 alphanumeric characters
        ref = ContentHelper.get_field(unb, 4)
        if ref:
            if len(ref) > 14 or not re.match(r"^[A-Za-z0-9\-_]{1,14}$", ref):
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.1.5",
                        f'UNB: Datenaustauschreferenz "{ref}" ist ungültig (max. 14 Zeichen alphanumerisch).',
                        "UNB",
                        seg_index,
                    )
                )
            elif ref == "00000":
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.1.5",
                        'UNB: Datenaustauschreferenz darf nicht "00000" sein (Bereich: 00001-99999).',
                        "UNB",
                        seg_index,
                    )
                )

        # 1.3.1.6: Leistungsbereich
        lb = ContentHelper.get_field(unb, 5)
        if lb and lb not in self.VALID_LEISTUNGSBEREICHE:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.1.6",
                    f'UNB: Leistungsbereich "{lb}" ist kein gültiger Sammelgruppenschlüssel (A-S).',
                    "UNB",
                    seg_index,
                )
            )

        # 1.3.1.7: Anwendungsreferenz
        anw_ref = ContentHelper.get_field(unb, 6)
        if anw_ref and len(anw_ref) < 11:
            errors.append(
                ValidationError.warning(
                    3,
                    "1.3.1.7",
                    f'UNB: Anwendungsreferenz "{anw_ref}" sollte 11 Zeichen lang sein (logischer Dateiname).',
                    "UNB",
                    seg_index,
                )
            )

        # 1.3.1.8: Testindikator — 0, 1, or 2
        test_ind = ContentHelper.get_field(unb, 7)
        if test_ind and test_ind not in ["0", "1", "2"]:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.1.8",
                    f'UNB: Testindikator "{test_ind}" ist ungültig. Erlaubt: 0 (Test), 1 (Erprobung), 2 (Echtdaten).',
                    "UNB",
                    seg_index,
                )
            )

        return errors

    def _check_absender_match(
        self,
        context: Any,
        unb_absender: str,
        seg_index: int,
        errors: List[Any],
    ) -> None:
        messages = context.get_messages()
        for msg in messages:
            if msg.get("type") != "SLGA":
                continue
            for seg in msg.get("segments", []):
                if seg.get("tag") == "FKT":
                    fkt_absender = ContentHelper.get_field(seg, 5)
                    if fkt_absender and fkt_absender != unb_absender:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.1.2",
                                f'UNB: Absender-IK "{unb_absender}" stimmt nicht mit SLGA.FKT.IK Absender "{fkt_absender}" überein.',
                                "UNB",
                                seg_index,
                            )
                        )
                    break
            break