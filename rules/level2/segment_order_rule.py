from typing import List, Optional, Dict, Any

from schema.schema import SchemaFactory
from rules.rule_interface import RuleInterface
from rules.level3.content_helper import ContentHelper
from validation_context import ValidationContext
from validation_error import ValidationError


class SegmentOrderRule(RuleInterface):
    """
    Rules 1.2.1.1–1.2.1.5 — Segment order validation.

    1.2.1.1: SLGA segment order: FKT, REC, [UST], [SKO]*, GES+, NAM
    1.2.1.2: SLLA base segment order: FKT, REC, (INV block)*
    1.2.1.3: SLLA INV block order across all Sammelgruppenschlüssel A-S
    1.2.1.4: SLGA before SLLA for each group
    1.2.1.5: No mixed VK in file
    """

    def __init__(self, schema: Optional[Any] = None):
        if schema is None:
            self.schema = SchemaFactory.create()
        else:
            self.schema = schema

    def get_stufe(self) -> int:
        return 2

    def validate(self, context) -> List:
        errors = []
        messages = context.get_messages()

        errors.extend(self._check_slga_before_slla(messages, context))
        errors.extend(self._check_no_mixed_vk(context))

        for msg_index, msg in enumerate(messages):
            if msg.get("type") == "SLGA":
                errors.extend(self._validate_slga_order(msg, msg_index, context))
            elif msg.get("type") == "SLLA":
                errors.extend(self._validate_slla_order(msg, msg_index, context))

        return errors

    def _validate_slga_order(self, msg: Dict[str, Any], msg_index: int, context: Any) -> List:
        errors = []
        segments = msg.get("segments", [])
        tags = [s["tag"] for s in segments]

        inner_tags = tags[1:-1]  # Strip UNH and UNT

        pattern = [
            {"tag": "FKT", "optional": False, "repeatable": False},
            {"tag": "REC", "optional": False, "repeatable": False},
            {"tag": "UST", "optional": True, "repeatable": False},
            {"tag": "SKO", "optional": True, "repeatable": True},
            {"tag": "GES", "optional": False, "repeatable": True},
            {"tag": "NAM", "optional": False, "repeatable": False},
        ]

        pos = 0
        seen_count: Dict[int, int] = {}

        for inner_idx, tag in enumerate(inner_tags):
            global_idx = msg["start"] + 1 + inner_idx
            matched = False
            search_pos = pos

            while search_pos < len(pattern):
                rule = pattern[search_pos]

                if tag == rule["tag"]:
                    matched = True
                    seen_count[search_pos] = seen_count.get(search_pos, 0) + 1
                    pos = search_pos
                    if not rule["repeatable"]:
                        pos += 1
                    break

                seen = seen_count.get(search_pos, 0)
                can_skip = rule["optional"] or (rule["repeatable"] and seen > 0)

                if can_skip:
                    search_pos += 1
                    continue

                break

            if not matched:
                if tag in ("FKT", "REC", "UST", "SKO", "GES", "NAM"):
                    errors.append(
                        context.create_validation_error(
                            2,
                            "1.2.1.1",
                            f"SLGA-Nachricht {msg.get('refNr')}: Segment {tag} an falscher Position "
                            f"(Position {global_idx}). Erwartete Reihenfolge: FKT, REC, [UST], [SKO]*, GES+, NAM.",
                            tag,
                            global_idx,
                        )
                    )
                else:
                    errors.append(
                        context.create_validation_error(
                            2,
                            "1.2.1.1",
                            f"SLGA-Nachricht {msg.get('refNr')}: Unerwartetes Segment {tag} "
                            f"(Position {global_idx}). Erlaubt in SLGA: FKT, REC, UST, SKO, GES, NAM.",
                            tag,
                            global_idx,
                        )
                    )

        return errors

    def _validate_slla_order(self, msg: Dict[str, Any], msg_index: int, context: Any) -> List:
        errors = []
        segments = msg.get("segments", [])
        tags = [s["tag"] for s in segments]
        inner_tags = tags[1:-1]

        if len(inner_tags) < 2:
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.2",
                    f"SLLA-Nachricht {msg.get('refNr')}: Zu wenige Segmente.",
                    "SLLA",
                    msg["start"],
                )
            )
            return errors

        if not inner_tags or inner_tags[0] != "FKT":
            found_tag = inner_tags[0] if inner_tags else "(fehlt)"
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.2",
                    f"SLLA-Nachricht {msg.get('refNr')}: Erstes Nutzsegment muss FKT sein, gefunden: {found_tag}.",
                    found_tag,
                    msg["start"] + 1,
                )
            )

        if len(inner_tags) < 2 or inner_tags[1] != "REC":
            found_tag = inner_tags[1] if len(inner_tags) > 1 else "(fehlt)"
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.2",
                    f"SLLA-Nachricht {msg.get('refNr')}: Zweites Nutzsegment muss REC sein, gefunden: {found_tag}.",
                    found_tag,
                    msg["start"] + 2,
                )
            )

        remaining = inner_tags[2:]
        remaining_start = msg["start"] + 3

        inv_blocks = []
        current_block = []
        current_block_start = remaining_start

        for i, tag in enumerate(remaining):
            if tag == "INV" and current_block:
                inv_blocks.append({"tags": current_block, "start": current_block_start})
                current_block = [tag]
                current_block_start = remaining_start + i
            else:
                current_block.append(tag)

        if current_block:
            inv_blocks.append({"tags": current_block, "start": current_block_start})

        if not inv_blocks:
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.2",
                    f"SLLA-Nachricht {msg.get('refNr')}: Keine INV-Blöcke gefunden.",
                    "SLLA",
                    msg["start"],
                )
            )
            return errors

        if inv_blocks[0]["tags"][0] != "INV":
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.2",
                    f"SLLA-Nachricht {msg.get('refNr')}: Nach FKT+REC wird INV erwartet, gefunden: {inv_blocks[0]['tags'][0]}.",
                    inv_blocks[0]["tags"][0],
                    inv_blocks[0]["start"],
                )
            )

        for block_idx, block in enumerate(inv_blocks):
            errors.extend(
                self._validate_inv_block(
                    block["tags"],
                    block["start"],
                    msg.get("refNr", ""),
                    block_idx + 1,
                    context,
                )
            )

        return errors

    def _validate_inv_block(
        self,
        tags: List[str],
        global_start: int,
        msg_ref_nr: str,
        block_num: int,
        context: Any,
    ) -> List:
        errors = []

        if not tags:
            return errors

        lb = ContentHelper.get_file_leistungsbereich(context.get_parsed_segments()) or "B"
        lb = lb.upper()
        if lb in ("G", "H", "I", "J", "K", "L", "M", "N"):
            lb_group = "G-N"
        else:
            lb_group = lb

        # Configuration of allowed tags and primary service tags per Sammelgruppenschlüssel
        sammelgruppen_config = {
            "A": {
                "primary": ("EHI", "HIL"),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "HIL", "EHI", "TXT", "MWS", "ZUH", "MEH", "ZHI", "DIA", "SKZ", "BES"},
            },
            "B": {
                "primary": ("EHE",),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "EHE", "TXT", "MWS", "ZHE", "DIA", "SKZ", "BES", "GZF"},
            },
            "C": {
                "primary": ("EHK", "ESK"),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "ESK", "EHK", "TXT", "ELP", "ZHK", "DIA", "SKZ", "BES"},
            },
            "D": {
                "primary": ("EHH", "ESH"),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "ESH", "EHH", "TXT", "ELP", "ZHH", "DIA", "SKZ", "BES"},
            },
            "E": {
                "primary": ("EKT", "KTL"),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "KTL", "EKT", "TXT", "MWS", "ZUK", "ZKT", "SKZ", "BES"},
            },
            "F": {
                "primary": ("EHB", "HEB", "HEL"),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "HEB", "HEL", "EHB", "TXT", "MWS", "ZHB", "DIA", "SKZ", "BES"},
            },
            "G-N": {
                "primary": ("ENF",),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "ENF", "SUT", "TXT", "MWS", "ZUZ", "ZUV", "DIA", "SKZ", "BES"},
            },
            "O": {
                "primary": ("ESP", "ERS"),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "ERS", "ESP", "TXT", "ZZL", "ZSP", "DIA", "SKZ", "BES"},
            },
            "P": {
                "primary": ("EGV",),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "EGV", "IBP", "TXT", "BES"},
            },
            "Q": {
                "primary": ("EHP",),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "EHP", "TXT", "DIA", "SKZ", "BES"},
            },
            "R": {
                "primary": ("AHK",),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "AHK", "ASK", "TXT", "ZHK", "DIA", "SKZ", "BES"},
            },
            "S": {
                "primary": ("EMP",),
                "allowed": {"INV", "URI", "NAD", "IMG", "EVO", "EMP", "TXT", "BES"},
            },
        }

        config = sammelgruppen_config.get(lb_group, sammelgruppen_config["B"])
        primary_tags = config["primary"]
        allowed_tags = config["allowed"]

        if tags[0] != "INV":
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.3",
                    f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: Erster Segment muss INV sein, gefunden: {tags[0]}.",
                    tags[0],
                    global_start,
                )
            )
            return errors

        # Check allowed tags in block
        for i, tag in enumerate(tags):
            global_idx = global_start + i
            if tag not in allowed_tags:
                errors.append(
                    context.create_validation_error(
                        2,
                        "1.2.1.3",
                        f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: Segment {tag} ist im Leistungsbereich '{lb}' nicht zulässig (Position {global_idx}).",
                        tag,
                        global_idx,
                    )
                )

        # Check primary service segment presence
        if not any(pt in tags for pt in primary_tags):
            p_name = " oder ".join(primary_tags)
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.3",
                    f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: Mindestens ein {p_name}-Segment ist im Leistungsbereich '{lb}' erforderlich.",
                    primary_tags[0],
                    global_start,
                )
            )

        # Check DIA requirement for B
        if lb_group == "B" and "DIA" not in tags:
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.3",
                    f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: Mindestens ein DIA-Segment ist erforderlich.",
                    "DIA",
                    global_start,
                )
            )

        # Check terminator segment presence
        if tags[-1] not in ("BES", "GZF"):
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.3",
                    f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: Abschließendes BES- oder GZF-Segment fehlt (gefunden: {tags[-1]}).",
                    "BES",
                    global_start,
                )
            )

        return errors

    def _check_slga_before_slla(self, messages: List[Dict[str, Any]], context: Any) -> List:
        errors = []
        seen_slga = False

        for msg in messages:
            if msg.get("type") == "SLGA":
                seen_slga = True
            elif msg.get("type") == "SLLA" and not seen_slga:
                errors.append(
                    context.create_validation_error(
                        2,
                        "1.2.1.4",
                        f"SLLA-Nachricht {msg.get('refNr')} erscheint vor einer SLGA-Nachricht. "
                        "Die SLGA-Nachricht muss vor den zugehörigen SLLA-Nachrichten stehen.",
                        "SLLA",
                        msg["start"],
                    )
                )

        return errors

    def _check_no_mixed_vk(self, context: Any) -> List:
        errors = []
        fkt_segments = context.find_all_segments("FKT")
        vks: Dict[str, List[int]] = {}

        for index, seg in fkt_segments.items():
            vk = context.get_field_value(seg, 0)
            if vk:
                if vk not in vks:
                    vks[vk] = []
                vks[vk].append(index)

        if len(vks) > 1:
            found = ", ".join(vks.keys())
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.5",
                    f"Verschiedene Verarbeitungskennzeichen in einer Datei gefunden: {found}. "
                    "Alle FKT.Verarbeitungskennzeichen müssen innerhalb einer Datei identisch sein.",
                    "FKT",
                )
            )

        return errors