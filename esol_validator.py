import os
from typing import Any, Dict, List, Optional

from rules.level1.encoding_rule import EncodingRule
from rules.level1.msg_count_rule import MessageCountRule
from rules.level1.reference_number_rule import ReferenceNumberRule
from rules.level1.single_invoice_kind_rule import SingleRechnungsartRule
from rules.level1.structure_rule import StructureRule
from rules.level1.version_rule import VersionRule
from rules.level2.decimal_format_rule import DecimalFormatRule
from rules.level2.escape_sequence_rule import EscapeSequenceRule
from rules.level2.field_length_rule import FieldLengthRule
from rules.level2.field_presence_rule import FieldPresenceRule
from rules.level2.field_type_rule import FieldTypeRule
from rules.level2.segment_order_rule import SegmentOrderRule
from rules.level3.bes_content_rule import BesContentRule
from rules.level3.cross_message_rule import CrossMessageRule
from rules.level3.dia_content_rule import DiaContentRule
from rules.level3.ehe_content_rule import EheContentRule
from rules.level3.fkt_content_rule import FktContentRule
from rules.level3.ges_content_rule import GesContentRule
from rules.level3.gzf_content_rule import GzfContentRule
from rules.level3.inv_content_rule import InvContentRule
from rules.level3.nad_content_rule import NadContentRule
from rules.level3.nam_content_rule import NamContentRule
from rules.level3.rec_content_rule import RecContentRule
from rules.level3.unb_content_rule import UnbContentRule
from rules.level3.uri_content_rule import UriContentRule
from rules.level3.zhe_content_rule import ZheContentRule
from rules.level3.unt_content_rule import UntContentRule
from rules.level4.unique_ehe_date_service_rule import UniqueEheDateServiceRule

from parser.segment_tokenizer import SegmentTokenizer
from rules.rule_interface import RuleInterface
from validation_context import ValidationContext
from validation_error import ValidationError
from validation_result import ValidationResult


class EsolValidator:
    """Main entry point / orchestrator for ESOL file validation.

    Execution flow:
      1. Read file, check encoding                     -> Stufe 1
      2. Tokenize into segments                        -> Stufe 1
      3. Validate file structure (UNB/UNZ/UNH/UNT)    -> Stufe 1
         └─ If Stufe 1 fails -> stop (file-level rejection)
      4. Parse segments, validate syntax               -> Stufe 2
         └─ If Stufe 2 fails -> stop
      5. Run content/semantic rules                    -> Stufe 3/4
      6. Return ValidationResult
    """

    def __init__(self) -> None:
        self._rules: List[RuleInterface] = []
        self._tokenizer = SegmentTokenizer()
        self._max_stufe: int = 4

    def register_rule(self, rule: RuleInterface) -> None:
        """Register a validation rule."""
        self._rules.append(rule)

    def set_max_stufe(self, stufe: int) -> None:
        """Set the maximum Prüfstufe to run (1, 2, 3, or 4)."""
        self._max_stufe = max(1, min(4, stufe))

    def validate(self, file_path: str) -> ValidationResult:
        """Validate an ESOL file by path."""
        result = ValidationResult()

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            result.add_error(
                ValidationError.error(
                    stufe=1,
                    code="1.0.1",
                    message=f"Datei kann nicht gelesen werden: {file_path}",
                )
            )
            return result

        try:
            # ISO-8859-1 (oder cp1252) liest jedes Byte 1:1 ohne Absturz ein
            with open(file_path, "r", encoding="iso-8859-1", errors="replace") as f:
                content = f.read()
        except Exception as e:
            result.add_error(
                ValidationError.error(
                    stufe=1,
                    code="1.0.1",
                    message=f"Datei kann nicht gelesen werden: {file_path}",
                )
            )
            return result

        context = ValidationContext()
        context.set_file_path(file_path)
        context.set_raw_content(content)

        return self._run_validation(context, result)

    def validate_string(self, content: str) -> ValidationResult:
        """Validate ESOL content provided as a string."""
        result = ValidationResult()
        context = ValidationContext()
        context.set_raw_content(content)

        return self._run_validation(context, result)

    def _run_validation(
        self, context: ValidationContext, result: ValidationResult
    ) -> ValidationResult:
        """Core validation pipeline."""
        # Tokenize segments
        raw_segments = self._tokenizer.tokenize_segments(
            context.get_raw_content()
        )
        context.set_raw_segments(raw_segments)

        # Parse all segments
        parsed = [
            self._tokenizer.parse_segment(raw) for raw in raw_segments
        ]
        context.set_parsed_segments(parsed)

        # Build message list (UNH..UNT blocks)
        self._build_messages(context)

        # Run rules by Stufe, stopping if a Stufe has errors
        for stufe in range(1, self._max_stufe + 1):
            stufe_rules = [r for r in self._rules if r.get_stufe() == stufe]

            for rule in stufe_rules:
                errors = rule.validate(context)
                result.add_errors(errors)

            # Per spec: Stufe 1 and 2 failures cause file-level rejection -> stop
            if result.has_stufe_errors(stufe) and stufe <= 2:
                break

        return result

    def _build_messages(self, context: ValidationContext) -> None:
        """Build UNH..UNT message blocks from parsed segments."""
        segments = context.get_parsed_segments()
        messages: List[Dict[str, Any]] = []

        current_start: Optional[int] = None
        current_ref_nr: str = ""
        current_type: str = ""

        for index, seg in enumerate(segments):
            tag = seg.get("tag")
            fields = seg.get("fields", [])

            if tag == "UNH":
                current_start = index

                # Referenznummer aus Feld 0 (falls vorhanden)
                if len(fields) > 0 and isinstance(fields[0], str):
                    current_ref_nr = fields[0]
                else:
                    current_ref_nr = ""

                # Nachrichtentyp aus Feld 1 (z.B. SLGA oder SLLA)
                msg_id = fields[1] if len(fields) > 1 else ""
                if isinstance(msg_id, list):
                    current_type = str(msg_id[0]) if len(msg_id) > 0 else ""
                elif isinstance(msg_id, str):
                    parts = msg_id.split(":")
                    current_type = parts[0] if parts else ""
                else:
                    current_type = ""

            elif tag == "UNT" and current_start is not None:
                msg_segments = segments[current_start : index + 1]
                messages.append(
                    {
                        "start": current_start,
                        "end": index,
                        "type": current_type,
                        "refNr": current_ref_nr,
                        "segments": msg_segments,
                    }
                )
                current_start = None
                current_ref_nr = ""
                current_type = ""

        context.set_messages(messages)

    # --- Registrierungsmethoden für Standard-Regeln ---

    def register_default_stufe1_rules(self) -> None:
        """Register all default Stufe 1 rules."""
        self.register_rule(EncodingRule())
        self.register_rule(StructureRule())
        self.register_rule(MessageCountRule())
        self.register_rule(ReferenceNumberRule())
        self.register_rule(SingleRechnungsartRule())
        self.register_rule(VersionRule())

    def register_default_stufe2_rules(self) -> None:
        """Register all default Stufe 2 rules."""
        self.register_rule(SegmentOrderRule())
        self.register_rule(FieldPresenceRule())
        self.register_rule(FieldTypeRule())
        self.register_rule(FieldLengthRule())
        self.register_rule(DecimalFormatRule())
        self.register_rule(EscapeSequenceRule())

    def register_default_stufe3_rules(self) -> None:
        """Register all default Stufe 3 rules."""
        self.register_rule(UnbContentRule())
        self.register_rule(FktContentRule())
        self.register_rule(RecContentRule())
        self.register_rule(InvContentRule())
        self.register_rule(UriContentRule())
        self.register_rule(NadContentRule())
        self.register_rule(EheContentRule())
        self.register_rule(ZheContentRule())
        self.register_rule(DiaContentRule())
        self.register_rule(BesContentRule())
        self.register_rule(GzfContentRule())
        self.register_rule(GesContentRule())
        self.register_rule(NamContentRule())
        self.register_rule(UntContentRule())
        self.register_rule(CrossMessageRule())

    def register_default_stufe4_rules(self) -> None:
        """Register all default Stufe 4 rules (custom / project-specific checks)."""
        self.register_rule(UniqueEheDateServiceRule())

    def register_default_rules(self) -> None:
        """Register all default rules (all available Stufen)."""
        self.register_default_stufe1_rules()
        self.register_default_stufe2_rules()
        self.register_default_stufe3_rules()
        self.register_default_stufe4_rules()