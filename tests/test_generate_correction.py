from pathlib import Path
from tools.generate_correction import generate_correction_esol, generate_correction_file, parse_esol_belege_summary
from esol_validator import EsolValidator


def test_generate_vk03_zuzahlungsforderung(tmp_path: Path):
    orig_esol = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+100,00+100,00+0,00'",
        "GES+31+100,00+100,00+0,00'",
        "NAM+Physio Praxis+++info@physio.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+30000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
        "ZHE+110178400+906716934+20250528+0+EN1+04+++++1++1110++0+1+2'",
        "DIA+F98.9'",
        "BES+100,00+10,00+0,00+10,00'",
        "UNT+000010+00002'",
        "UNZ+000002+00118'",
    ])

    orig_file = tmp_path / "orig_esol.txt"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    res_file = generate_correction_file(orig_file, target_vk="03", new_rec_nr="5100Z", new_rec_date="20260325")

    assert res_file.exists()
    content = res_file.read_text(encoding="iso-8859-15")

    # Check FKT changed to VK 03
    assert "FKT+03+" in content
    # Check new REC number
    assert "REC+5100Z+20260325" in content
    # Check URI segment inserted
    assert "URI+123456789+51:0+20260122+00001'" in content
    # Check ZHE Zuzahlungskennzeichen changed to '2'
    assert "+2+EN1+04+" in content
    # Check GZF segment replaced BES segment
    assert "GZF+20,00+10,00+10,00'" in content

    # Validate generated file with EsolValidator
    validator = EsolValidator()
    validator.register_default_rules()
    res = validator.validate_string(content)
    assert res.is_valid(), f"Expected valid VK03 file, got errors: {res.get_errors()}"


def test_generate_vk04_korrekturrechnung(tmp_path: Path):
    orig_esol = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+100,00+100,00+0,00'",
        "GES+31+100,00+100,00+0,00'",
        "NAM+Physio Praxis+++info@physio.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+30000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+59702+1,00+100,00+20260115+0,00'",
        "ZHE+110178400+906716934+20250528+0+EN1+04+++++1++1110++0+1+2'",
        "DIA+F98.9'",
        "BES+100,00'",
        "UNT+000010+00002'",
        "UNZ+000002+00118'",
    ])

    orig_file = tmp_path / "orig_esol_vk04.txt"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    res_file = generate_correction_file(orig_file, target_vk="04", new_rec_nr="5100K", new_rec_date="20260325")

    assert res_file.exists()
    content = res_file.read_text(encoding="iso-8859-15")

    # Check FKT changed to VK 04
    assert "FKT+04+" in content
    # Check URI segment inserted
    assert "URI+123456789+51:0+20260122+00001'" in content
    # Check BES segment preserved
    assert "BES+100,00'" in content

    # Validate generated file with EsolValidator
    validator = EsolValidator()
    validator.register_default_rules()
    res = validator.validate_string(content)
    assert res.is_valid(), f"Expected valid VK04 file, got errors: {res.get_errors()}"


def test_generate_vk10_wiederaufnahme_blankoverordnung(tmp_path: Path):
    orig_esol = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+100,00+100,00+0,00'",
        "GES+31+100,00+100,00+0,00'",
        "NAM+Physio Praxis+++info@physio.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+30000+1+00001'",
        "NAD+Muster+Max+19900101'",
        "EHE+26:00501+59702+1,00+100,00+20260115+0,00'",
        "ZHE+110178400+906716934+20250528+0+EN1+04+++++1++1110++0+1+2'",
        "DIA+F98.9'",
        "BES+100,00'",
        "UNT+000010+00002'",
        "UNZ+000002+00118'",
    ])

    orig_file = tmp_path / "orig_esol_vk10.txt"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    res_file = generate_correction_file(orig_file, target_vk="10", new_rec_nr="5100W", new_rec_date="20260325")

    assert res_file.exists()
    content = res_file.read_text(encoding="iso-8859-15")

    # Check FKT changed to VK 10
    assert "FKT+10+" in content
    # Check URI segment inserted
    assert "URI+123456789+51:0+20260122+00001'" in content

    # Validate generated file with EsolValidator
    validator = EsolValidator()
    validator.register_default_rules()
    res = validator.validate_string(content)
    assert res.is_valid(), f"Expected valid VK10 file, got errors: {res.get_errors()}"


def test_parse_belege_summary_and_selective_filtering(tmp_path: Path):
    orig_esol = "\n".join([
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++123456789+101777502+101777502+123456789'",
        "REC+51:0+20260122+1'",
        "GES+00+200,00+200,00+0,00'",
        "GES+31+200,00+200,00+0,00'",
        "NAM+Physio Praxis+++info@physio.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++123456789+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+A123456789+30000+1+00001'",
        "NAD+Muster+Anna+19850101'",
        "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
        "ZHE+110178400+906716934+20250528+0+EN1+04+++++1++1110++0+1+2'",
        "DIA+F98.9'",
        "BES+100,00+10,00+10,00+0,00'",
        "INV+A987654321+30000+1+00002'",
        "NAD+Schmidt+Peter+19700505'",
        "EHE+26:00501+59702+1,00+100,00+20260115+10,00'",
        "ZHE+110178400+906716934+20250528+0+EN1+04+++++1++1110++0+1+2'",
        "DIA+F98.9'",
        "BES+100,00+10,00+10,00+0,00'",
        "UNT+000016+00002'",
        "UNZ+000002+00118'",
    ])

    belege = parse_esol_belege_summary(orig_esol)
    assert len(belege) == 2
    assert belege[0]["belegnr"] == "00001"
    assert belege[0]["versichertennummer"] == "A123456789"
    assert belege[0]["nachname"] == "Muster"
    assert belege[1]["belegnr"] == "00002"
    assert belege[1]["versichertennummer"] == "A987654321"
    assert belege[1]["nachname"] == "Schmidt"

    # Test filtering: generate VK 03 only for Beleg 00002
    orig_file = tmp_path / "multi_beleg.txt"
    orig_file.write_text(orig_esol, encoding="iso-8859-15")

    res_file = generate_correction_file(
        orig_file,
        target_vk="03",
        selected_belegnr_list=["00002"],
        new_rec_nr="5100Z2",
    )

    content = res_file.read_text(encoding="iso-8859-15")
    assert "00002" in content
    assert "NAD+Muster" not in content
    assert "URI+123456789+51:0+20260122+00002'" in content

    validator = EsolValidator()
    validator.register_default_rules()
    res_vk03 = validator.validate_string(content)
    assert res_vk03.is_valid(), f"Expected valid VK03 filtered file, got errors: {res_vk03.get_errors()}"

    # Test filtering for VK 02 (Nachforderung) with only 1 Beleg selected
    res_file_vk02 = generate_correction_file(
        orig_file,
        target_vk="02",
        selected_belegnr_list=["00002"],
        new_rec_nr="5100N2",
    )
    content_vk02 = res_file_vk02.read_text(encoding="iso-8859-15")
    res_vk02 = validator.validate_string(content_vk02)
    assert res_vk02.is_valid(), f"Expected valid VK02 filtered file, got errors: {res_vk02.get_errors()}"
