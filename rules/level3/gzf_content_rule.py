from typing import Any, Dict, List

from validation_error import ValidationError
from rules.level3.content_helper import ContentHelper
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


# Verordnungssegmente je Leistungsbereich. Das Zuzahlungskennzeichen steht in
# allen an derselben Stelle (4. Feld, Index 3).
_VERORDNUNGS_SEGMENTE = ("ZHE", "ZHI", "ZHK", "ZHH", "ZKT", "ZHB", "ZSP")
_ZKZ_FELD = 3

# Zuzahlungskennzeichen, bei denen es keine Zuzahlung gibt, die man
# nachfordern könnte (Anlage 3 zu TP 5, Abschnitt 8.1.3).
#
# Hier steht nur die "0". Die "1" (Zuzahlungsbefreit) gehörte zunächst auch
# dazu — falsch: Anlage 1 Abschnitt 7.4.2.2 beschreibt genau diesen Fall als
# zulässige Zuzahlungsforderung. Die ursprüngliche Rechnung war um die
# Zuzahlung gemindert, der Versicherte zahlt wegen erreichter Belastungsgrenze
# nicht, der Leistungserbringer fordert sie beim Kostenträger — mit
# Zuzahlungskennzeichen "1". Eine Forderung neben der "1" ist also der
# Regelfall und kein Fehler.
#
# Bei "0" (keine gesetzliche Zuzahlung) wurde nie eine Zuzahlung abgesetzt.
# Dann gibt es auch keinen Betrag, den § 43c SGB V zurückholen könnte.
_ZKZ_OHNE_ZUZAHLUNG = {
    "0": "Keine gesetzliche Zuzahlung",
}


class GzfContentRule(RuleInterface):
    """Rule 1.3.12 — GZF segment content validation (VK 03 only)."""

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
                gzf_seg = None
                gzf_seg_index = None
                ehe_segments = []
                zhe_seg = None

                for seg in block:
                    if seg.get("tag") == "GZF":
                        gzf_seg = seg
                        gzf_seg_index = self._find_global_index(msg, seg)
                    if seg.get("tag") == "EHE":
                        ehe_segments.append(seg)
                    if seg.get("tag") in _VERORDNUNGS_SEGMENTE and zhe_seg is None:
                        zhe_seg = seg

                if vk != "03" and gzf_seg is not None:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.12.1",
                            f"GZF (Block {block_idx}): GZF-Segment darf nur bei VK 03 (Zuzahlungsforderung) vorhanden sein.",
                            "GZF",
                            gzf_seg_index,
                        )
                    )

                if vk == "03" and gzf_seg is None:
                    inv_seg_index = self._find_global_index(msg, block[0])
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.12.1",
                            f"INV-Block {block_idx}: GZF-Segment fehlt. Bei VK 03 muss ein GZF-Segment vorhanden sein.",
                            "INV",
                            inv_seg_index,
                        )
                    )
                    continue

                if gzf_seg is None:
                    continue

                gzf_ges = ContentHelper.parse_decimal(
                    ContentHelper.get_field(gzf_seg, 0)
                )
                gzf_proz = ContentHelper.parse_decimal(
                    ContentHelper.get_field(gzf_seg, 1)
                )
                gzf_pausch = ContentHelper.parse_decimal(
                    ContentHelper.get_field(gzf_seg, 2)
                )

                # 1.3.12.3 — Forderung trotz Befreiung.
                # Das Verordnungssegment weist den Versicherten als befreit aus,
                # das GZF fordert trotzdem Geld. Solche Dateien entstanden früher
                # beim Generieren und fielen keiner Regel auf; über die
                # bearbeitbare Vorschau lassen sie sich weiterhin von Hand bauen.
                if zhe_seg is not None and gzf_ges is not None:
                    zkz = (ContentHelper.get_field(zhe_seg, _ZKZ_FELD) or "").strip()
                    if zkz in _ZKZ_OHNE_ZUZAHLUNG and abs(gzf_ges) > 0.005:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.12.3",
                                f"GZF (Block {block_idx}): Forderung über "
                                f"{ContentHelper.format_decimal(gzf_ges)}, obwohl "
                                f"{zhe_seg.get('tag')} das Zuzahlungskennzeichen {zkz} "
                                f"({_ZKZ_OHNE_ZUZAHLUNG[zkz]}) trägt. Es besteht keine "
                                f"Zuzahlung, die nachgefordert werden könnte.",
                                "GZF",
                                gzf_seg_index,
                            )
                        )

                # 1.3.12.4 — Forderung über null Euro.
                # Formal rechnet die Datei auf, fachlich fordert sie nichts.
                if gzf_ges is not None and abs(gzf_ges) <= 0.005:
                    errors.append(
                        ValidationError.error(
                            3,
                            "1.3.12.4",
                            f"GZF (Block {block_idx}): Gesamtbetrag der Forderung ist "
                            f"0,00. Eine Zuzahlungsforderung ohne Betrag hat keinen "
                            f"Zweck — der Beleg gehört nicht in eine VK-03-Datei.",
                            "GZF",
                            gzf_seg_index,
                        )
                    )

                if gzf_ges is not None:
                    calc_proz = gzf_proz or 0.0
                    calc_pausch = gzf_pausch or 0.0
                    calculated = ContentHelper.round_commercial(
                        calc_proz + calc_pausch
                    )
                    gzf_ges = ContentHelper.round_commercial(gzf_ges)

                    if abs(gzf_ges - calculated) > 0.005:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.12.2",
                                f"GZF (Block {block_idx}): Gesamtbetrag Forderung {ContentHelper.format_decimal(gzf_ges)} "
                                f"≠ prozentuale Zuzahlung {ContentHelper.format_decimal(calc_proz)} "
                                f"+ pauschale Zuzahlung {ContentHelper.format_decimal(calc_pausch)} "
                                f"= {ContentHelper.format_decimal(calculated)}.",
                                "GZF",
                                gzf_seg_index,
                            )
                        )

                if gzf_proz is not None:
                    calculated_proz_zuz = 0.0
                    for ehe in ehe_segments:
                        anzahl = (
                            ContentHelper.parse_decimal(
                                ContentHelper.get_field(ehe, 2)
                            )
                            or 0.0
                        )
                        betrag_zuz = ContentHelper.parse_decimal(
                            ContentHelper.get_field(ehe, 5)
                        )
                        if betrag_zuz is not None:
                            calculated_proz_zuz += betrag_zuz * anzahl

                    calculated_proz_zuz = ContentHelper.round_commercial(
                        calculated_proz_zuz
                    )
                    gzf_proz_rounded = ContentHelper.round_commercial(gzf_proz)

                    if abs(gzf_proz_rounded - calculated_proz_zuz) > 0.005:
                        errors.append(
                            ValidationError.error(
                                3,
                                "1.3.12.2",
                                f"GZF (Block {block_idx}): Forderung prozentuale Zuzahlung {ContentHelper.format_decimal(gzf_proz_rounded)} "
                                f"stimmt nicht mit SUM(EHE.Zuzahlung × Anzahl) = {ContentHelper.format_decimal(calculated_proz_zuz)} überein.",
                                "GZF",
                                gzf_seg_index,
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