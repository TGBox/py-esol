from typing import Any, Dict, List, Optional

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class GesContentRule(RuleInterface):
    """Rule 1.3.13 — GES segment content validation (SLGA Rechnungssummen)."""

    # Schlüssel Summenstatus, Anlage 3 Abschnitt 8.1.6
    VALID_SUMMENSTATUS = {"00", "11", "31", "51", "99"}

    def get_stufe(self) -> int:
        return 3

    def validate(self, context: Any) -> List[Any]:
        errors = []
        messages = context.get_messages()
        vk = ContentHelper.get_file_vk(context.get_parsed_segments())

        for msg_idx, msg in enumerate(messages):
            if msg.get("type") != "SLGA":
                continue

            ges_segments = []
            for seg_offset, seg in enumerate(msg.get("segments", [])):
                if seg.get("tag") == "GES":
                    ges_segments.append(
                        {"seg": seg, "index": msg["start"] + seg_offset}
                    )

            if not ges_segments:
                continue

            if len(ges_segments) < 2:
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.13.2",
                        f"SLGA: Mindestens 2 GES-Segmente erforderlich (Status 00 + mindestens ein Versichertenstatus), gefunden: {len(ges_segments)}.",
                        "GES",
                        ges_segments[0]["index"],
                    )
                )

            if len(ges_segments) > 9:
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.13.2",
                        f"SLGA: Maximal 9 GES-Segmente erlaubt, gefunden: {len(ges_segments)}.",
                        "GES",
                        ges_segments[0]["index"],
                    )
                )

            for ges_item in ges_segments:
                status = (ContentHelper.get_field(ges_item["seg"], 0) or "").strip()
                if status and status not in self.VALID_SUMMENSTATUS:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.13.8",
                            f'GES: Summenstatus "{status}" ist kein Schlüsselwert nach '
                            f"Anlage 3 Abschnitt 8.1.6. Zulässig: "
                            + ", ".join(sorted(self.VALID_SUMMENSTATUS))
                            + ".",
                            "GES",
                            ges_item["index"],
                        )
                    )

            first_status = ContentHelper.get_field(ges_segments[0]["seg"], 0)
            if first_status != "00":
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.13.1",
                        f'SLGA: Erstes GES-Segment muss Summenstatus "00" haben, gefunden: "{first_status}".',
                        "GES",
                        ges_segments[0]["index"],
                    )
                )

            ges_data = []
            for ges_item in ges_segments:
                ges_seg = ges_item["seg"]
                ges_data.append(
                    {
                        "status": ContentHelper.get_field(ges_seg, 0),
                        "rechnungsbetrag": ContentHelper.parse_decimal(
                            ContentHelper.get_field(ges_seg, 1)
                        )
                        or 0.0,
                        "brutto": ContentHelper.parse_decimal(
                            ContentHelper.get_field(ges_seg, 2)
                        )
                        or 0.0,
                        "zuzahlung": ContentHelper.parse_decimal(
                            ContentHelper.get_field(ges_seg, 3)
                        ),
                        "index": ges_item["index"],
                    }
                )

            for ges in ges_data:
                seg_index = ges["index"]

                if vk == "03":
                    if abs(ges["brutto"]) > 0.005:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.13.5",
                                f"GES (Status {ges['status']}): Bei VK 03 muss Gesamtbruttobetrag 0,00 sein, gefunden: {ContentHelper.format_decimal(ges['brutto'])}.",
                                "GES",
                                seg_index,
                            )
                        )

                    if ges["zuzahlung"] is not None:
                        expected_rechnung = ContentHelper.round_commercial(
                            ges["zuzahlung"]
                        )
                        actual_rechnung = ContentHelper.round_commercial(
                            ges["rechnungsbetrag"]
                        )
                        if abs(actual_rechnung - expected_rechnung) > 0.005:
                            errors.append(
                                ValidationError.error(
                                    3,
                                    "1.3.13.4",
                                    f"GES (Status {ges['status']}): Bei VK 03 muss Gesamtrechnungsbetrag = Gesamtbetrag Zuzahlung sein. "
                                    f"Rechnungsbetrag: {ContentHelper.format_decimal(actual_rechnung)}, "
                                    f"Zuzahlung: {ContentHelper.format_decimal(expected_rechnung)}.",
                                    "GES",
                                    seg_index,
                                )
                            )
                else:
                    zuzahlung = ges["zuzahlung"] or 0.0
                    expected_rechnung = ContentHelper.round_commercial(
                        ges["brutto"] - zuzahlung
                    )
                    actual_rechnung = ContentHelper.round_commercial(
                        ges["rechnungsbetrag"]
                    )

                    if abs(actual_rechnung - expected_rechnung) > 0.005:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.13.3",
                                f"GES (Status {ges['status']}): Gesamtrechnungsbetrag {ContentHelper.format_decimal(actual_rechnung)} "
                                f"≠ Brutto {ContentHelper.format_decimal(ges['brutto'])} "
                                f"- Zuzahlung {ContentHelper.format_decimal(zuzahlung)} "
                                f"= {ContentHelper.format_decimal(expected_rechnung)}.",
                                "GES",
                                seg_index,
                            )
                        )

            if len(ges_data) >= 2 and ges_data[0]["status"] == "00":
                sum_rechnung = sum(
                    g["rechnungsbetrag"] for g in ges_data[1:]
                )
                sum_brutto = sum(g["brutto"] for g in ges_data[1:])
                sum_zuzahlung = sum(
                    g["zuzahlung"] or 0.0 for g in ges_data[1:]
                )

                sum_rechnung = ContentHelper.round_commercial(sum_rechnung)
                sum_brutto = ContentHelper.round_commercial(sum_brutto)
                sum_zuzahlung = ContentHelper.round_commercial(sum_zuzahlung)

                ges00 = ges_data[0]

                if abs(ges00["rechnungsbetrag"] - sum_rechnung) > 0.005:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.13.1",
                            f"GES(00): Gesamtrechnungsbetrag {ContentHelper.format_decimal(ges00['rechnungsbetrag'])} "
                            f"≠ Summe der Statuszeilen {ContentHelper.format_decimal(sum_rechnung)}.",
                            "GES",
                            ges00["index"],
                        )
                    )

                if abs(ges00["brutto"] - sum_brutto) > 0.005:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.13.1",
                            f"GES(00): Gesamtbruttobetrag {ContentHelper.format_decimal(ges00['brutto'])} "
                            f"≠ Summe der Statuszeilen {ContentHelper.format_decimal(sum_brutto)}.",
                            "GES",
                            ges00["index"],
                        )
                    )

                if ges00["zuzahlung"] is not None:
                    if abs(ges00["zuzahlung"] - sum_zuzahlung) > 0.005:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.13.1",
                                f"GES(00): Gesamtbetrag Zuzahlung {ContentHelper.format_decimal(ges00['zuzahlung'])} "
                                f"≠ Summe der Statuszeilen {ContentHelper.format_decimal(sum_zuzahlung)}.",
                                "GES",
                                ges00["index"],
                            )
                        )

            self._cross_check_with_slla(
                msg, msg_idx, ges_data, messages, vk, errors
            )

        return errors

    def _cross_check_with_slla(
        self,
        slga_msg: Dict[str, Any],
        slga_msg_idx: int,
        ges_data: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        vk: Optional[str],
        errors: List[Any],
    ) -> None:
        slla_messages = []
        found_slga = False

        for idx, msg in enumerate(messages):
            if idx == slga_msg_idx:
                found_slga = True
                continue
            if found_slga:
                if msg.get("type") == "SLGA":
                    break
                if msg.get("type") == "SLLA":
                    slla_messages.append(msg)

        if not slla_messages:
            return

        brutto_by_status = {}
        zuzahlung_by_status = {}
        total_brutto = 0.0
        total_zuzahlung = 0.0

        for slla_msg in slla_messages:
            inv_blocks = ContentHelper.extract_inv_blocks(slla_msg)

            for block in inv_blocks:
                # Summenstatus nach Anlage 3, 8.1.6: es zählt allein die erste
                # Ziffer des Versichertenstatus. Vorher standen hier die ersten
                # zwei Stellen — daraus wurde "10", "30", "50", also Werte, die
                # der Schlüssel nicht kennt. Kein GES-Status stimmte damit je
                # überein, und der Abgleich je Status lief ins Leere.
                vers_status = ContentHelper.get_field(block[0], 1)
                status_key = ContentHelper.summenstatus(vers_status)

                for seg in block:
                    if seg.get("tag") == "BES":
                        brutto = (
                            ContentHelper.parse_decimal(
                                ContentHelper.get_field(seg, 0)
                            )
                            or 0.0
                        )
                        zuzahlung = (
                            ContentHelper.parse_decimal(
                                ContentHelper.get_field(seg, 1)
                            )
                            or 0.0
                        )

                        brutto_by_status[status_key] = (
                            brutto_by_status.get(status_key, 0.0) + brutto
                        )
                        zuzahlung_by_status[status_key] = (
                            zuzahlung_by_status.get(status_key, 0.0) + zuzahlung
                        )
                        total_brutto += brutto
                        total_zuzahlung += zuzahlung

                    if seg.get("tag") == "GZF" and vk == "03":
                        gzf_ges = (
                            ContentHelper.parse_decimal(
                                ContentHelper.get_field(seg, 0)
                            )
                            or 0.0
                        )
                        zuzahlung_by_status[status_key] = (
                            zuzahlung_by_status.get(status_key, 0.0) + gzf_ges
                        )
                        total_zuzahlung += gzf_ges

        if ges_data and ges_data[0]["status"] == "00":
            ges00 = ges_data[0]

            if vk != "03":
                rounded_total_brutto = ContentHelper.round_commercial(
                    total_brutto
                )
                if abs(ges00["brutto"] - rounded_total_brutto) > 0.01:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.13.6",
                            f"GES(00): Gesamtbruttobetrag {ContentHelper.format_decimal(ges00['brutto'])} "
                            f"stimmt nicht mit Summe aller SLLA.BES.Brutto {ContentHelper.format_decimal(rounded_total_brutto)} überein.",
                            "GES",
                            ges00["index"],
                        )
                    )

            if ges00["zuzahlung"] is not None and total_zuzahlung > 0:
                rounded_total_zuz = ContentHelper.round_commercial(
                    total_zuzahlung
                )
                if abs(ges00["zuzahlung"] - rounded_total_zuz) > 0.01:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.13.6",
                            f"GES(00): Gesamtbetrag Zuzahlung {ContentHelper.format_decimal(ges00['zuzahlung'])} "
                            f"stimmt nicht mit Summe aller SLLA Zuzahlungen {ContentHelper.format_decimal(rounded_total_zuz)} überein.",
                            "GES",
                            ges00["index"],
                        )
                    )

        self._pruefe_je_status(ges_data, brutto_by_status, vk, errors)

    def _pruefe_je_status(
        self,
        ges_data: List[Dict[str, Any]],
        brutto_by_status: Dict[str, float],
        vk: Optional[str],
        errors: List[Any],
    ) -> None:
        """
        Regel 1.3.13.7 — jede GES-Statuszeile gegen die Belege dieses Status.

        Anlage 1, Abschnitt 5.5.2 zum GES-Segment: "Die Betragssumme des
        Versichertenstatus (SLGA) entspricht den Summen der Abrechnungsfälle
        (SLLA), die diesen Status beinhalten." Welcher Summenstatus zu einem
        Versichertenstatus gehört, sagt Anlage 3, 8.1.6.

        Bisher wurde nur die Zeile mit Summenstatus 00 gegen die Gesamtsumme
        gestellt. Damit fiel eine Datei nicht auf, in der die Beträge in der
        Summe stimmen, aber in der falschen Statuszeile stehen — genau der
        Fehler, den das Erzeugen einer Korrekturrechnung produziert hat.

        Bei Verarbeitungskennzeichen 03 wird nicht geprüft: dort ist der
        Bruttobetrag laut Anlage mit 0,00 zu übermitteln, ein Abgleich gegen
        die Belegsummen wäre sinnlos.
        """
        if vk == "03":
            return

        for ges in ges_data:
            status = ges["status"]
            if status == "00":
                continue
            erwartet = ContentHelper.round_commercial(
                brutto_by_status.get(status, 0.0)
            )
            ist = ContentHelper.round_commercial(ges["brutto"])
            if abs(ist - erwartet) > 0.01:
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.13.7",
                        f"GES (Status {status}): Gesamtbruttobetrag "
                        f"{ContentHelper.format_decimal(ist)} stimmt nicht mit der "
                        f"Summe der Abrechnungsfälle dieses Versichertenstatus "
                        f"{ContentHelper.format_decimal(erwartet)} überein.",
                        "GES",
                        ges["index"],
                    )
                )

        # Ein Status, für den es Belege gibt, aber keine GES-Zeile
        vorhanden = {g["status"] for g in ges_data}
        for status, betrag in sorted(brutto_by_status.items()):
            if status not in vorhanden and ContentHelper.round_commercial(betrag) != 0.0:
                errors.append(
                    ValidationError.error(
                        3,
                        "1.3.13.7",
                        f"GES: Für den Summenstatus {status} fehlt eine Statuszeile, "
                        f"obwohl Abrechnungsfälle dieses Versichertenstatus über "
                        f"{ContentHelper.format_decimal(betrag)} vorliegen.",
                        "GES",
                        ges_data[0]["index"] if ges_data else None,
                    )
                )