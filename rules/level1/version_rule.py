from typing import List
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError


class VersionRule(RuleInterface):
    """
    Rules 1.1.12, 1.1.13 — TA version and message type validation.

    1.1.12: All UNH.Nachrichtenkennung must reference the same version (21).
    1.1.13: UNH.Nachrichtenkennung must be SLGA:21:0:0 or SLLA:21:0:0.

    Grace period: Version 20 (SLGA:20:0:0, SLLA:20:0:0) is accepted for
    files created before 2026-10-01 (based on UNB interchange date).
    """

    VALID_MESSAGE_TYPES: tuple[str, ...] = ("SLGA:21:0:0", "SLLA:21:0:0")
    LEGACY_MESSAGE_TYPES: tuple[str, ...] = ("SLGA:20:0:0", "SLLA:20:0:0")

    EXPECTED_VERSION = "21"
    LEGACY_VERSION = "20"

    LEGACY_CUTOFF_DATE = "20261001"

    def get_stufe(self) -> int:
        return 1

    def validate(self, context) -> List:
        errors = []
        unh_segments = context.find_all_segments("UNH")

        if not unh_segments:
            return errors  # StructureRule handles missing UNH

        legacy_allowed = self._is_legacy_version_allowed(context)

        all_valid_types = list(self.VALID_MESSAGE_TYPES)
        accepted_versions = [self.EXPECTED_VERSION]

        if legacy_allowed:
            all_valid_types.extend(self.LEGACY_MESSAGE_TYPES)
            accepted_versions.append(self.LEGACY_VERSION)

        versions = set()

        for index, seg in unh_segments.items():
            fields = seg.get("fields", [])
            msg_id = fields[1] if len(fields) > 1 else None

            # Reconstruct the message identifier string
            msg_id_str = ""
            if isinstance(msg_id, list):
                msg_id_str = ":".join(str(x) for x in msg_id)
            elif isinstance(msg_id, str):
                msg_id_str = msg_id

            # 1.1.13: Check valid message type
            if msg_id_str not in all_valid_types:
                errors.append(
                    context.create_validation_error(
                        1,
                        "1.1.13",
                        f'UNH-Segment an Position {index}: Ungültige Nachrichtenkennung "{msg_id_str}". '
                        f'Erlaubt sind: {", ".join(all_valid_types)}.',
                        "UNH",
                        f"{index}",
                    )
                )

            # Extract version for 1.1.12 check
            version = None
            if isinstance(msg_id, list) and len(msg_id) > 1:
                version = str(msg_id[1])
            elif isinstance(msg_id, str):
                parts = msg_id.split(":")
                if len(parts) > 1:
                    version = parts[1]

            if version is not None:
                versions.add(version)

        unique_versions = list(versions)

        # 1.1.12: All versions must be identical and equal '21'
        if len(unique_versions) > 1:
            found = ", ".join(unique_versions)
            errors.append(
                context.create_validation_error(
                    1,
                    "1.1.12",
                    f"Verschiedene TA-Versionen in einer Datei gefunden: {found}. "
                    "Eine Datei darf nur Rechnungen einer TA-Version enthalten.",
                    "UNH",
                )
            )

        for version in unique_versions:
            if str(version) not in accepted_versions:
                expected = " oder ".join(accepted_versions)
                errors.append(
                    context.create_validation_error(
                        1,
                        "1.1.12",
                        f'UNH-Nachrichtenkennung referenziert Version "{version}", erwartet: {expected}.',
                        "UNH",
                    )
                )

        return errors

    def _is_legacy_version_allowed(self, context) -> bool:
        unb_segment = context.find_first_segment("UNB")
        if unb_segment is None:
            return False

        fields = unb_segment.get("fields", [])
        date_field = fields[3] if len(fields) > 3 else None
        date_str = None

        if isinstance(date_field, list) and len(date_field) > 0:
            date_str = str(date_field[0])
        elif isinstance(date_field, str):
            parts = date_field.split(":")
            date_str = parts[0]

        if not date_str or len(date_str) != 8:
            return False

        return date_str < self.LEGACY_CUTOFF_DATE