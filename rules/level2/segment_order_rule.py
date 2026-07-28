from typing import List, Optional, Dict, Any

from schema.schema import SchemaFactory
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class SegmentOrderRule(RuleInterface):
    """
    Rules 1.2.1.1–1.2.1.5 — Segment order validation.

    1.2.1.1: SLGA segment order: FKT, REC, [UST], [SKO]*, GES+, NAM
    1.2.1.2: SLLA base segment order: FKT, REC, (INV block)*
    1.2.1.3: SLLA:B INV block order: INV, [URI], NAD, [IMG], [EVO], EHE+, ZHE, DIA+, [SKZ], BES|GZF
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

        valid_sequence = {
            "INV": {"next": ("URI", "NAD"), "required": True},
            "URI": {"next": ("NAD",), "required": False},
            "NAD": {"next": ("IMG", "EVO", "EHE"), "required": True},
            "IMG": {"next": ("EVO", "EHE"), "required": False},
            "EVO": {"next": ("EHE",), "required": False},
            "EHE": {"next": ("TXT", "MWS", "EHE", "ZHE"), "required": True},
            "TXT": {"next": ("MWS", "EHE", "ZHE"), "required": False},
            "MWS": {"next": ("EHE", "ZHE"), "required": False},
            "ZHE": {"next": ("DIA",), "required": True},
            "DIA": {"next": ("DIA", "SKZ", "BES", "GZF"), "required": True},
            "SKZ": {"next": ("BES", "GZF"), "required": False},
            "BES": {"next": (), "required": False},
            "GZF": {"next": (), "required": False},
        }

        if not tags:
            return errors

        current_state = None
        saw_ehe = False
        saw_dia = False
        saw_terminator = False

        for i, tag in enumerate(tags):
            global_idx = global_start + i

            if current_state is None:
                if tag != "INV":
                    errors.append(
                        context.create_validation_error(
                            2,
                            "1.2.1.3",
                            f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: "
                            f"Erster Segment muss INV sein, gefunden: {tag}.",
                            tag,
                            global_idx,
                        )
                    )
                    return errors
                current_state = "INV"
                continue

            state_info = valid_sequence.get(current_state)
            if state_info is None:
                errors.append(
                    context.create_validation_error(
                        2,
                        "1.2.1.3",
                        f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: "
                        f"Unerwartetes Segment {tag} nach {current_state} (Position {global_idx}).",
                        tag,
                        global_idx,
                    )
                )
                continue

            allowed_next = state_info["next"]

            if tag in allowed_next:
                current_state = tag
                if tag == "EHE":
                    saw_ehe = True
                if tag == "DIA":
                    saw_dia = True
                if tag in ("BES", "GZF"):
                    saw_terminator = True
            else:
                found = False
                search_state = current_state
                visited = {search_state}

                while not found:
                    info = valid_sequence.get(search_state)
                    if info is None:
                        break

                    advanced = False
                    for next_state in info["next"]:
                        if next_state == tag:
                            current_state = tag
                            found = True
                            if tag == "EHE":
                                saw_ehe = True
                            if tag == "DIA":
                                saw_dia = True
                            if tag in ("BES", "GZF"):
                                saw_terminator = True
                            break

                        next_info = valid_sequence.get(next_state)
                        if next_info and not next_info["required"] and next_state not in visited:
                            visited.add(next_state)
                            search_state = next_state
                            advanced = True
                            break

                    if found or not advanced or len(visited) > len(valid_sequence):
                        break

                if not found:
                    errors.append(
                        context.create_validation_error(
                            2,
                            "1.2.1.3",
                            f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: "
                            f"Segment {tag} nicht erlaubt nach {current_state} (Position {global_idx}).",
                            tag,
                            global_idx,
                        )
                    )

        if not saw_ehe:
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.3",
                    f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: "
                    "Mindestens ein EHE-Segment ist erforderlich.",
                    "EHE",
                    global_start,
                )
            )

        if not saw_dia:
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.3",
                    f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: "
                    "Mindestens ein DIA-Segment ist erforderlich.",
                    "DIA",
                    global_start,
                )
            )

        if not saw_terminator:
            errors.append(
                context.create_validation_error(
                    2,
                    "1.2.1.3",
                    f"SLLA-Nachricht {msg_ref_nr}, INV-Block #{block_num}: "
                    "Abschließendes BES- oder GZF-Segment fehlt.",
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