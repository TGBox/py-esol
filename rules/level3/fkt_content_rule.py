from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class FktContentRule(RuleInterface):
    """Rules 1.3.2 + 1.3.3 — FKT segment content validation (SLGA + SLLA)."""

    VALID_VK = ["01", "02", "03", "04", "10"]

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()
        slga_data = []

        for msg in messages:
            for seg in msg.get("segments", []):
                if seg.get("tag") != "FKT":
                    continue

                if msg.get("type") == "SLGA":
                    slga_errors = self._validate_slga_fkt(seg, msg, context)
                    errors.extend(slga_errors)

                    slga_data.append(
                        {
                            "vk": ContentHelper.get_field(seg, 0),
                            "ikRechnungssteller": ContentHelper.get_field(
                                seg, 2
                            ),
                            "ikKostentraeger": ContentHelper.get_field(seg, 3),
                            "ikKrankenkasse": ContentHelper.get_field(seg, 4),
                            "ikAbsender": ContentHelper.get_field(seg, 5),
                        }
                    )
                elif msg.get("type") == "SLLA":
                    slla_errors = self._validate_slla_fkt(seg, msg, slga_data)
                    errors.extend(slla_errors)

                break  # Only one FKT per message

        return errors

    def _validate_slga_fkt(
        self, seg: Dict[str, Any], msg: Dict[str, Any], context: Any
    ) -> List[Any]:
        errors = []
        seg_index = msg["start"] + self._find_segment_offset(msg, "FKT")

        vk = ContentHelper.get_field(seg, 0)
        if vk and vk not in self.VALID_VK:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.2.1",
                    f'SLGA.FKT: Verarbeitungskennzeichen "{vk}" ist ungültig. Erlaubt: 01, 02, 03, 04, 10.',
                    "FKT",
                    seg_index,
                )
            )

        sammelr = ContentHelper.get_field(seg, 1)
        if sammelr and sammelr != "J":
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.2.2",
                    f'SLGA.FKT: Sammelrechnung wenn angegeben muss "J" sein, gefunden: "{sammelr}".',
                    "FKT",
                    seg_index,
                )
            )

        ik_fields = [
            (2, "IK Rechnungssteller"),
            (3, "IK Kostenträger"),
            (5, "IK Absender"),
        ]
        ik_kk = ContentHelper.get_field(seg, 4)
        if ik_kk:
            ik_fields.append((4, "IK Krankenkasse"))

        for field_idx, field_name in ik_fields:
            ik_value = ContentHelper.get_field(seg, field_idx)
            if ik_value:
                if not ContentHelper.is_valid_ik(ik_value):
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.2.3",
                            f'SLGA.FKT: {field_name} "{ik_value}" ist kein gültiges 9-stelliges IK.',
                            "FKT",
                            seg_index,
                        )
                    )
                elif not ContentHelper.is_valid_ik_check_digit(ik_value):
                    errors.append(
                        ValidationError.warning(
                            3,
                            "1.3.2.3",
                            f'SLGA.FKT: {field_name} "{ik_value}" hat eine ungültige Prüfziffer.',
                            "FKT",
                            seg_index,
                        )
                    )

        ik_absender = ContentHelper.get_field(seg, 5)
        unb = context.find_first_segment("UNB")
        if unb and ik_absender:
            unb_absender = ContentHelper.get_field(unb, 1)
            if unb_absender and unb_absender != ik_absender:
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.2.4",
                        f'SLGA.FKT: IK Absender "{ik_absender}" stimmt nicht mit UNB.Absender "{unb_absender}" überein.',
                        "FKT",
                        seg_index,
                    )
                )

        return errors

    def _validate_slla_fkt(
        self, seg: Dict[str, Any], msg: Dict[str, Any], slga_data: List[Dict[str, Any]]
    ) -> List[Any]:
        errors = []
        seg_index = msg["start"] + self._find_segment_offset(msg, "FKT")

        vk = ContentHelper.get_field(seg, 0)
        if vk and vk not in self.VALID_VK:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.3.1",
                    f'SLLA.FKT: Verarbeitungskennzeichen "{vk}" ist ungültig.',
                    "FKT",
                    seg_index,
                )
            )

        ik_fields = [
            (2, "IK Leistungserbringer"),
            (3, "IK Kostenträger"),
            (4, "IK Krankenkasse"),
        ]
        for field_idx, field_name in ik_fields:
            ik_value = ContentHelper.get_field(seg, field_idx)
            if ik_value and not ContentHelper.is_valid_ik(ik_value):
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.3.1",
                        f'SLLA.FKT: {field_name} "{ik_value}" ist kein gültiges 9-stelliges IK.',
                        "FKT",
                        seg_index,
                    )
                )

        if not slga_data:
            return errors

        slga = slga_data[0]

        if vk and slga["vk"] and vk != slga["vk"]:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.3.1",
                    f'SLLA.FKT: Verarbeitungskennzeichen "{vk}" stimmt nicht mit SLGA.FKT.VK "{slga["vk"]}" überein.',
                    "FKT",
                    seg_index,
                )
            )

        ik_le = ContentHelper.get_field(seg, 2)
        if (
            ik_le
            and slga["ikRechnungssteller"]
            and ik_le != slga["ikRechnungssteller"]
        ):
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.3.2",
                    f'SLLA.FKT: IK Leistungserbringer "{ik_le}" stimmt nicht mit SLGA.FKT.IK Rechnungssteller "{slga["ikRechnungssteller"]}" überein.',
                    "FKT",
                    seg_index,
                )
            )

        ik_kt = ContentHelper.get_field(seg, 3)
        if ik_kt and slga["ikKostentraeger"] and ik_kt != slga["ikKostentraeger"]:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.3.3",
                    f'SLLA.FKT: IK Kostenträger "{ik_kt}" stimmt nicht mit SLGA.FKT.IK Kostenträger "{slga["ikKostentraeger"]}" überein.',
                    "FKT",
                    seg_index,
                )
            )

        ik_kk = ContentHelper.get_field(seg, 4)
        if ik_kk and slga["ikKrankenkasse"] and ik_kk != slga["ikKrankenkasse"]:
            errors.append(
                ValidationError.error(
                    3,
                    "1.3.3.4",
                    f'SLLA.FKT: IK Krankenkasse "{ik_kk}" stimmt nicht mit SLGA.FKT.IK Krankenkasse "{slga["ikKrankenkasse"]}" überein.',
                    "FKT",
                    seg_index,
                )
            )

        return errors

    def _find_segment_offset(self, msg: Dict[str, Any], tag: str) -> int:
        for idx, seg in enumerate(msg.get("segments", [])):
            if seg.get("tag") == tag:
                return idx
        return 0