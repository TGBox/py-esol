import pytest
from parser.segment_tokenizer import SegmentTokenizer
from rules.level2 import (
    segment_order_rule, field_presence_rule, field_type_rule, field_length_rule, decimal_format_rule, escape_sequence_rule
)
from schema.schema import SchemaFactory
from tests.helpers import make_context, assert_error_code

class TestSchemaFactory:
    def test_all_segment_tags_registered(self):
        schema = SchemaFactory.create()
        tags = ['UNB', 'UNZ', 'UNH', 'UNT', 'REC', 'GES', 'NAM', 'UST', 'SKO',
                'INV', 'URI', 'NAD', 'IMG', 'EVO', 'EHE', 'TXT', 'MWS', 'ZHE',
                'DIA', 'SKZ', 'BES', 'GZF']
        for tag in tags:
            def_ = schema.get(tag) or schema.get(tag, 'SLGA') or schema.get(tag, 'SLLA')
            assert def_ is not None, f"Schema for {tag} should exist"

class TestSyntaxRules:
    def test_segment_order_slga_wrong_order(self):
        tokenizer = SegmentTokenizer()
        rule = segment_order_rule.SegmentOrderRule()
        ctx = make_context(
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00001+B+SL030179S03+2'"
            "UNH+00001+SLGA:21:0:0'"
            "FKT+03++123456789+101777502+101777502+123456789'"
            "REC+51:0+20260122+1'"
            "NAM+Test'"
            "GES+00+82,89+0,00+82,89'"
            "UNT+000006+00001'"
            "UNZ+000001+00001'", tokenizer
        )
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.2.1.1', 'NAM before GES should fail')

    def test_field_type_alpha_in_numeric_field(self):
        tokenizer = SegmentTokenizer()
        rule = field_type_rule.FieldTypeRule()
        ctx = make_context(
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00001+B+SL030179S03+2'"
            "UNH+00001+SLGA:21:0:0'"
            "FKT+03++123456789+101777502+101777502+123456789'"
            "REC+51:0+20260122+1'"
            "GES+xx+82,89+0,00'"
            "NAM+Test'"
            "UNT+000006+00001'"
            "UNZ+000001+00001'", tokenizer
        )
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.2.2.5', 'Alpha in numeric field should fail')
    
    def test_field_presence_rule_missing_mandatory_field(self, tokenizer):
        rule = field_presence_rule.FieldPresenceRule()
        # FKT-Segment ohne verpflichtendes Feld 01 (Funktionscode)
        ctx = make_context("UNB+UNOC:3'UNH+00001+SLGA:21:0:0'FKT+'UNT+2+00001'UNZ+1+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.2.2.3', 'Missing mandatory field should fail')

    def test_field_length_exceeded(self, tokenizer):
        rule = field_length_rule.FieldLengthRule()
        # Erzeuge einen Wert, der das Längenlimit des Feldes überschreitet
        long_ref = "A" * 50
        ctx = make_context(f"UNB+UNOC:3'UNH+00001+SLGA:21:0:0'INV+{long_ref}'UNT+2+00001'UNZ+1+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.2.2.6', 'Exceeding field length should fail')

    def test_decimal_format_rule_invalid_comma(self, tokenizer):
        rule = decimal_format_rule.DecimalFormatRule()
        # Punkt statt Komma oder mehr als 2 Nachkommastellen verwendet
        ctx = make_context("UNB+UNOC:3'UNH+00001+SLGA:21:0:0'GES+00+82.89'UNT+2+00001'UNZ+1+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.2.2.7', 'Dot used as decimal separator should fail')

    def test_escape_sequence_unescaped_char(self, tokenizer):
        rule = escape_sequence_rule.EscapeSequenceRule()
        # Unescapetes Steuerzeichen innerhalb eines Datenfeldes
        ctx = make_context("UNB+UNOC:3'UNH+00001+SLGA:21:0:0'NAM+Test+Name+mit+'+'UNT+2+00001'UNZ+1+00001'", tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.2.3.1', 'Unescaped special character should fail')