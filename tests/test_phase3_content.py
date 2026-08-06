import pytest
from parser.segment_tokenizer import SegmentTokenizer
from rules.level3 import (
    content_helper, unb_content_rule, fkt_content_rule, rec_content_rule, inv_content_rule, uri_content_rule, nad_content_rule, gzf_content_rule
)
from tests.helpers import assert_no_error_code, make_context, assert_error_code

class TestContentHelper:
    def test_is_valid_date(self):
        assert content_helper.ContentHelper.is_valid_date('20260101') is True
        assert content_helper.ContentHelper.is_valid_date('20260230') is False
        assert content_helper.ContentHelper.is_valid_date('20260000', allow_partial_zero=True) is True

    def test_parse_decimal(self):
        assert content_helper.ContentHelper.parse_decimal('82,89') == 82.89
        assert content_helper.ContentHelper.parse_decimal('-10,5') == -10.5

class TestContentRules:
    @pytest.fixture
    def valid_vk03_file(self):
        return "\n".join([
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
            "UNH+00001+SLGA:21:0:0'",
            "FKT+03++123456789+101777502+101777502+123456789'",
            "REC+51:0+20260122+1'",
            "GES+00+82,89+0,00+82,89'",
            "GES+31+82,89+0,00+82,89'",
            "NAM+Blabla Praxis +++info@blablapraxis.de'",
            "UNT+000007+00001'",
            "UNH+00002+SLLA:21:0:0'",
            "FKT+03++123456789+101777502+101777502'",
            "REC+51:0+20260122+1'",
            "INV+A123456789+30000+1+00001'",
            "URI+123456789+13:19+20251017+19'",
            "NAD+Muster+Elvis-Leonhard+20210521'",
            "EHE+26:00501+59702+1,00+1,20+20250528+0,00'",
            "ZHE+110178400+906716934+20250528+2+EN1+04+++++1++1110++0+1+2'",
            "DIA+F98.9'",
            "GZF+82,89+72,89+10,00'",
            "UNT+000019+00002'",
            "UNZ+000002+00118'",
        ])

    def test_unb_content_rule_wrong_syntax(self, valid_vk03_file):
        tokenizer = SegmentTokenizer()
        bad_syntax = valid_vk03_file.replace('UNOC:3', 'UNOA:2')
        ctx = make_context(bad_syntax, tokenizer)
        rule = unb_content_rule.UnbContentRule()
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.3.1.1', 'Should detect wrong syntax identifier')
        
    def test_fkt_content_rule_invalid_ik(self, tokenizer, valid_vk03_file):
        rule = fkt_content_rule.FktContentRule()
        # 'ABC' hat die falsche Länge/Format für ein IK -> Code 1.3.2.1
        bad_file = valid_vk03_file.replace('FKT+03++123456789', 'FKT+03++ABC')
        ctx = make_context(bad_file, tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.3.2.3', 'Invalid IK format should fail with 1.3.2.3')

    def test_rec_content_rule_future_date(self, tokenizer, valid_vk03_file):
        rule = rec_content_rule.RecContentRule()
        # Erstelle ein Rechnungsdatum in der Zukunft (z. B. 2099)
        bad_file = valid_vk03_file.replace('20260122', '20990101')
        ctx = make_context(bad_file, tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.3.4.4', 'Future invoice date should fail')

    def test_gzf_content_rule_sum_mismatch(self, tokenizer, valid_vk03_file):
        rule = gzf_content_rule.GzfContentRule()
        # Verfälsche den Bruttobetrag im GZF-Segment (82,89 -> 99,99)
        bad_file = valid_vk03_file.replace('82,89+72,89', '99,99+72,89')
        ctx = make_context(bad_file, tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.3.12.2', 'GZF amount mismatch should fail')

    def test_nad_content_rule_invalid_dob(self, tokenizer, valid_vk03_file):
        rule = nad_content_rule.NadContentRule()
        # Geburtsdatum ungültig (z. B. 31. Februar)
        bad_file = valid_vk03_file.replace('20210521', '20210231')
        ctx = make_context(bad_file, tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.3.7.3', 'Invalid date of birth should fail')
        
    def test_uri_content_rule_valid(self, tokenizer, valid_vk03_file):
        """Prüft, dass ein korrektes URI-Segment ohne Fehler durchläuft."""
        rule = uri_content_rule.UriContentRule()
        ctx = make_context(valid_vk03_file, tokenizer)
        errors = rule.validate(ctx)
        
        # Es sollte kein Fehler für das URI-Segment geworfen werden
        assert_no_error_code(errors, '1.3.6.1', 'Gültige URI-Daten sollten keinen Fehler erzeugen')

    def test_uri_content_rule_invalid_ik(self, tokenizer, valid_vk03_file):
        """Prüft ungültiges IK im URI-Segment (z.B. ABC)."""
        rule = uri_content_rule.UriContentRule()
        bad_file = valid_vk03_file.replace('URI+123456789', 'URI+ABC')
        ctx = make_context(bad_file, tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.3.6.2', 'Ungültiges IK im URI-Segment muss erkannt werden')

    def test_uri_content_rule_invalid_date(self, tokenizer, valid_vk03_file):
        """Prüft ungültige Datumsangaben im URI-Segment (z.B. 31. April)."""
        rule = uri_content_rule.UriContentRule()
        # Ersetze ein gültiges Datum durch ein existierendes, aber falsches Kalenderdatum
        bad_file = valid_vk03_file.replace('20251017', '20250431')
        
        ctx = make_context(bad_file, tokenizer)
        errors = rule.validate(ctx)
        
        assert_error_code(errors, '1.3.6.4', 'Ungültiges Datum im URI-Segment muss erkannt werden')

    def test_uri_content_rule_belegnummer_too_long(self, tokenizer, valid_vk03_file):
        """Prüft zu lange Belegnummer im URI-Segment (> 10 Zeichen)."""
        rule = uri_content_rule.UriContentRule()
        bad_file = valid_vk03_file.replace("URI+123456789+13:19+20251017+19'", "URI+123456789+13:19+20251017+123456789012345'")
        
        ctx = make_context(bad_file, tokenizer)
        errors = rule.validate(ctx)
        assert_error_code(errors, '1.3.6.5', 'Zu lange Belegnummer im URI-Segment muss erkannt werden')