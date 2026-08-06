import pytest
from esol_validator import EsolValidator
from parser.segment_tokenizer import SegmentTokenizer
from tests.helpers import make_context, assert_no_error_code, assert_error_code


class TestAllSammelgruppen:

    @pytest.fixture
    def validator(self):
        v = EsolValidator()
        v.register_default_rules()
        return v

    def test_sammelgruppe_a_hilfsmittel_valid(self, validator):
        file_content = "\n".join([
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+A+SL030179S03+2'",
            "UNH+00001+SLGA:21:0:0'",
            "FKT+01++123456789+101777502+101777502+123456789'",
            "REC+51:0+20260122+1'",
            "GES+00+100,00+100,00+0,00'",
            "GES+31+100,00+100,00+0,00'",
            "NAM+Hilfsmittel Sanitätshaus+++info@sanitaetshaus.de'",
            "UNT+000007+00001'",
            "UNH+00002+SLLA:21:0:0'",
            "FKT+01++123456789+101777502+101777502'",
            "REC+51:0+20260122+1'",
            "INV+A123456789+30000+1+00001'",
            "NAD+Muster+Hans+19800101'",
            "HIL+1'",
            "EHI+04:12345+1234567890+1,00+ST+100,00+20260115+01'",
            "MEH+0,00'",
            "ZHI+123456789+987654321+20260110+0'",
            "BES+100,00'",
            "UNT+000011+00002'",
            "UNZ+000002+00118'",
        ])
        result = validator.validate_string(file_content)
        assert result.is_valid(), f"Expected valid result, got errors: {result.get_errors()}"

    def test_sammelgruppe_c_hkp_valid(self, validator):
        file_content = "\n".join([
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+C+SL030179S03+2'",
            "UNH+00001+SLGA:21:0:0'",
            "FKT+01++123456789+101777502+101777502+123456789'",
            "REC+51:0+20260122+1'",
            "GES+00+50,00+50,00+0,00'",
            "GES+31+50,00+50,00+0,00'",
            "NAM+Pflegedienst Muster+++info@pflegedienst.de'",
            "UNT+000007+00001'",
            "UNH+00002+SLLA:21:0:0'",
            "FKT+01++123456789+101777502+101777502'",
            "REC+51:0+20260122+1'",
            "INV+A123456789+30000+1+00001'",
            "NAD+Muster+Anna+19750512'",
            "ESK+20260115+0800+0830+30'",
            "EHK+05:12345+1234567890+1,00+50,00+0+123456789'",
            "ZHK+123456789+987654321+20260110'",
            "BES+50,00'",
            "UNT+000010+00002'",
            "UNZ+000002+00118'",
        ])
        result = validator.validate_string(file_content)
        assert result.is_valid(), f"Expected valid result, got errors: {result.get_errors()}"

    def test_sammelgruppe_e_krankentransport_valid(self, validator):
        file_content = "\n".join([
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+E+SL030179S03+2'",
            "UNH+00001+SLGA:21:0:0'",
            "FKT+01++123456789+101777502+101777502+123456789'",
            "REC+51:0+20260122+1'",
            "GES+00+75,00+75,00+0,00'",
            "GES+31+75,00+75,00+0,00'",
            "NAM+Taxi & Krankentransport+++info@transport.de'",
            "UNT+000007+00001'",
            "UNH+00002+SLLA:21:0:0'",
            "FKT+01++123456789+101777502+101777502'",
            "REC+51:0+20260122+1'",
            "INV+A123456789+30000+1+00001'",
            "NAD+Muster+Klaus+19600320'",
            "KTL+1+Musterstr. 1+12345+DE+Startstadt+Zielstr. 2+12345+DE+Zielstadt'",
            "EKT+06:12345+1234567890+1,00+75,00+20260115'",
            "ZKT+123456789+987654321+0'",
            "BES+75,00'",
            "UNT+000010+00002'",
            "UNZ+000002+00118'",
        ])
        result = validator.validate_string(file_content)
        assert result.is_valid(), f"Expected valid result, got errors: {result.get_errors()}"

    def test_sammelgruppe_f_hebammen_valid(self, validator):
        file_content = "\n".join([
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+F+SL030179S03+2'",
            "UNH+00001+SLGA:21:0:0'",
            "FKT+01++123456789+101777502+101777502+123456789'",
            "REC+51:0+20260122+1'",
            "GES+00+120,00+120,00+0,00'",
            "GES+31+120,00+120,00+0,00'",
            "NAM+Hebamme Maria+++info@hebamme.de'",
            "UNT+000007+00001'",
            "UNH+00002+SLLA:21:0:0'",
            "FKT+01++123456789+101777502+101777502'",
            "REC+51:0+20260122+1'",
            "INV+A123456789+30000+1+00001'",
            "NAD+Muster+Lisa+19920815'",
            "HEB+123456789'",
            "HEL+20260115'",
            "EHB+07:12345+12345+1,00+120,00'",
            "ZHB++1+20260115+1000'",
            "BES+120,00'",
            "UNT+000011+00002'",
            "UNZ+000002+00118'",
        ])
        result = validator.validate_string(file_content)
        assert result.is_valid(), f"Expected valid result, got errors: {result.get_errors()}"

    def test_sammelgruppe_o_sapv_v21_zzl(self, validator):
        """Tests SAPV with V21 3x LANR and 3x Beschäftigtennummer in ZZL."""
        file_content = "\n".join([
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+O+SL030179S03+2'",
            "UNH+00001+SLGA:21:0:0'",
            "FKT+01++123456789+101777502+101777502+123456789'",
            "REC+51:0+20260122+1'",
            "GES+00+250,00+250,00+0,00'",
            "GES+31+250,00+250,00+0,00'",
            "NAM+SAPV Team Muster+++info@sapv.de'",
            "UNT+000007+00001'",
            "UNH+00002+SLLA:21:0:0'",
            "FKT+01++123456789+101777502+101777502'",
            "REC+51:0+20260122+1'",
            "INV+A123456789+30000+1+00001'",
            "NAD+Muster+Otto+19500410'",
            "ERS+20260101'",
            "ESP+15:12345+1234567890+1,00+250,00'",
            "ZZL+20260115+1000+20260115+1100+60+ID123+111111111+222222222+333333333+444444444+555555555+666666666'",
            "ZSP+123456789+987654321+20260101+0+20260101+20260331'",
            "BES+250,00'",
            "UNT+000011+00002'",
            "UNZ+000002+00118'",
        ])
        result = validator.validate_string(file_content)
        assert result.is_valid(), f"Expected valid result, got errors: {result.get_errors()}"

    def test_vk10_wiederaufnahme_valid(self, validator):
        """Tests VKZ 10 (Wiederaufnahme bei Blankoverordnung)."""
        file_content = "\n".join([
            "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
            "UNH+00001+SLGA:21:0:0'",
            "FKT+10++123456789+101777502+101777502+123456789'",
            "REC+51:0+20260122+1'",
            "GES+00+100,00+100,00+0,00'",
            "GES+31+100,00+100,00+0,00'",
            "NAM+Physio Praxis+++info@physio.de'",
            "UNT+000007+00001'",
            "UNH+00002+SLLA:21:0:0'",
            "FKT+10++123456789+101777502+101777502'",
            "REC+51:0+20260122+1'",
            "INV+A123456789+30000+1+00001'",
            "URI+123456789+13:19+20251017+19'",
            "NAD+Muster+Max+19900101'",
            "EHE+26:00501+59702+1,00+100,00+20260115+0,00'",
            "ZHE+110178400+906716934+20250528+2+EN1+04+++++1++1110++0+1+2'",
            "DIA+F98.9'",
            "BES+100,00'",
            "UNT+000011+00002'",
            "UNZ+000002+00118'",
        ])
        result = validator.validate_string(file_content)
        assert result.is_valid(), f"Expected valid result, got errors: {result.get_errors()}"
