import pytest
from parser.segment_tokenizer import SegmentTokenizer
from rules.level1 import (
    encoding_rule, structure_rule, msg_count_rule, reference_number_rule, single_invoice_kind_rule, version_rule
)
from tests.helpers import make_context, assert_error_code, assert_no_error_code

class TestSegmentTokenizer:
    def test_tokenize_segments_basic(self):
        tokenizer = SegmentTokenizer()
        segments = tokenizer.tokenize_segments("UNB+UNOC:3+123'UNZ+1+123'")
        assert len(segments) == 2
        assert segments[0] == "UNB+UNOC:3+123"
        assert segments[1] == "UNZ+1+123"

    def test_tokenize_segments_escaped_apostrophe(self):
        tokenizer = SegmentTokenizer()
        segments = tokenizer.tokenize_segments("NAD+D?'Angelo+Luigi'UNT+1+00001'")
        assert len(segments) == 2
        assert segments[0] == "NAD+D?'Angelo+Luigi"

    def test_parse_segment_composite_fields(self):
        tokenizer = SegmentTokenizer()
        parsed = tokenizer.parse_segment('UNB+UNOC:3+123456789+661430035+20260323:1040+00118')
        assert parsed['tag'] == 'UNB'
        assert isinstance(parsed['fields'][0], list)
        assert parsed['fields'][0] == ['UNOC', '3']
        assert parsed['fields'][3] == ['20260323', '1040']

    def test_unescape(self):
        tokenizer = SegmentTokenizer()
        assert tokenizer.unescape('?+') == '+'
        assert tokenizer.unescape("?'") == "'"
        assert tokenizer.unescape('??') == '?'

class TestStructureRules:
    def test_structure_rule_missing_unb(self):
        tokenizer = SegmentTokenizer()
        rule = structure_rule.StructureRule()
        ctx = make_context("UNH+00001+SLGA:21:0:0'UNT+000002+00001'UNZ+000001+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.1.3', 'Missing UNB should fail')

    def test_structure_rule_missing_unz(self):
        tokenizer = SegmentTokenizer()
        rule = structure_rule.StructureRule()
        ctx = make_context("UNB+UNOC:3'UNH+00001+SLGA:21:0:0'UNT+000002+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.1.4', 'Missing UNZ should fail')
    
    def test_encoding_rule_valid_iso_encoding(self, tokenizer):
        rule = encoding_rule.EncodingRule()
        # Ein gültiges EDIFACT-Segment mit UNOC-Syntaxbezeichner
        content = "UNB+UNOC:3+123456789'UNH+00001+SLGA:21:0:0'UNT+2+00001'UNZ+1+123456789'"
        
        ctx = make_context(content, tokenizer)
        errors = rule.validate(ctx)
        
        # Stellt sicher, dass kein Encoding-Fehler (Code 1.1.1) geworfen wird
        assert_no_error_code(errors, '1.1.1', 'Gültiger ISO-8859-1 / UNOC-String darf keinen Fehler werfen')

    def test_encoding_rule_invalid_syntax_identifier(self, tokenizer):
        rule = encoding_rule.EncodingRule()
        # UTF-8 Multi-Byte Sequenzen übergeben
        content = "UNB+UNOC:3'NAD+Testäöü'".encode("utf-8")
        
        ctx = make_context(content, tokenizer)
        errors = rule.validate(ctx)
        
        assert_error_code(errors, '1.1.1', 'UTF-8 Multibyte-Sequenzen müssen fehlschlagen')

    def test_message_count_rule_mismatch(self, tokenizer):
        rule = msg_count_rule.MessageCountRule()
        # UNZ gibt 2 Nachrichten an, aber es ist nur 1 UNH/UNT-Block vorhanden
        ctx = make_context("UNB+UNOC:3'UNH+00001+SLGA:21:0:0'UNT+2+00001'UNZ+2+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.1.6', 'Mismatched message count in UNZ should fail')

    def test_reference_number_rule_mismatch(self, tokenizer):
        rule = reference_number_rule.ReferenceNumberRule()
        # UNB Ref ist 12345, UNZ Ref ist 99999
        ctx = make_context("UNB+UNOC:3+123+456+20260323:1040+12345'UNH+00001+SLGA:21:0:0'UNT+2+00001'UNZ+1+99999'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.1.7', 'Mismatched reference numbers should fail')

    def test_single_rechnungsart_rule_mixed(self, tokenizer):
        rule = single_invoice_kind_rule.SingleRechnungsartRule()
        # Mischen von SLGA und SLLA in einer Datei
        ctx = make_context("UNB+UNOC:3'UNH+00001+SLGA:21:0:0'UNT+2+00001'UNH+00002+SLLA:21:0:0'UNT+2+00002'UNZ+2+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.1.7', 'Mixed message types should fail')

    def test_version_rule_invalid_version(self, tokenizer):
        rule = version_rule.VersionRule()
        ctx = make_context("UNB+UNOC:3'UNH+00001+SLGA:99:0:0'UNT+2+00001'UNZ+1+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.1.13', 'Invalid version should fail')