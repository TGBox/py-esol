from pathlib import Path
from tools.generate_auf import create_auftragsdatei, parse_esol_file, generate_auf


def test_create_auftragsdatei_format(tmp_path: Path):
    esol_file = tmp_path / "SL030179S03"
    esol_file.write_text("dummy content")

    auf_str = create_auftragsdatei(
        file_path=esol_file,
        owner_ik="101777502",
        absender_ik="123456789",
        empfaenger_ik="661430035",
        logischer_name="SL030179S03",
        timestamp="202603231040",
        size=13,
    )

    # Check identifying prefix and fields
    assert auf_str.startswith("5000000100000348000SL030179S03")
    assert "123456789      " in auf_str
    assert "661430035      " in auf_str
    assert "20260323104000" in auf_str
    assert "000000000013" in auf_str
    assert "I5" in auf_str


def test_generate_auf_from_file(tmp_path: Path):
    sample_esol = tmp_path / "SL030179S03"
    sample_esol.write_text(
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S03+2'\n"
        "UNH+00001+SLGA:21:0:0'\n"
        "FKT+01++123456789+101777502+101777502+123456789'\n"
        "REC+51:0+20260122+1'\n"
        "GES+00+100,00+100,00+0,00'\n"
        "GES+31+100,00+100,00+0,00'\n"
        "NAM+Test+++\n"
        "UNT+000007+00001'\n"
        "UNZ+000001+00118'\n",
        encoding="iso-8859-1"
    )

    auf_file = generate_auf(sample_esol)
    assert auf_file.exists()
    assert auf_file.name == "SL030179S03.auf"

    content = auf_file.read_text(encoding="iso-8859-15")
    assert "5000000100000348" in content
    assert "123456789      " in content
    assert "661430035      " in content
    assert "SL030179S03" in content
