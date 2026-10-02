from pathlib import Path
from tools.generate_auf import create_auftragsdatei, parse_esol_file, generate_auf


def test_create_auftragsdatei_format(tmp_path: Path):
    esol_file = tmp_path / "ESOL0179"
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
    assert auf_str.startswith("5000000100000348000ESOL0179     ")
    assert "123456789      " in auf_str
    assert "661430035      " in auf_str
    assert "20260323104000" in auf_str
    assert "000000000013" in auf_str
    assert "I1" in auf_str


def test_auftragssatz_zeichensatz_an_stelle_203(tmp_path: Path):
    """Zeichensatz steht in Stellen 203-204; I1 = ISO-8859-1 (ESOL-Vorgabe)."""
    auf_str = create_auftragsdatei(
        file_path=tmp_path / "ESOL0156",   # Verfahren ESOL0 + Transfer-Nr. 156
        owner_ik="101777502",
        absender_ik="123456789",
        empfaenger_ik="661430035",
        logischer_name="SL030179S03",
        timestamp="202603231040",
        size=13,
    )
    assert len(auf_str) == 348
    assert auf_str[202:204] == "I1"


def test_generate_auf_from_file(tmp_path: Path):
    sample_esol = tmp_path / "ESOL0179"
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
    assert auf_file.name == "ESOL0179.auf"

    content = auf_file.read_text(encoding="iso-8859-1")
    assert "5000000100000348" in content
    assert "123456789      " in content
    assert "661430035      " in content
    assert "SL030179S03" in content


def test_generate_auf_with_out_dir(tmp_path: Path):
    sample_esol = tmp_path / "ESOL0180"
    sample_esol.write_text(
        "UNB+UNOC:3+123456789+661430035+20260323:1040+00118+B+SL030179S04+2'\n"
        "UNH+00001+SLGA:21:0:0'\n"
        "FKT+01++123456789+101777502+101777502+123456789'\n"
        "REC+51:0+20260122+1'\n"
        "GES+00+100,00+100,00+0,00'\n"
        "UNT+000005+00001'\n"
        "UNZ+000001+00118'\n",
        encoding="iso-8859-1"
    )
    custom_out_dir = tmp_path / "custom_output"
    auf_file = generate_auf(sample_esol, out_dir=custom_out_dir)

    assert auf_file.exists()
    assert auf_file.parent == custom_out_dir
    assert auf_file.name == "ESOL0180.auf"


def test_auftragssatz_lehnt_falschen_dateinamen_ab(tmp_path: Path):
    """Ein Dateiname mit mehr als 8 Zeichen würde alle Felder ab Stelle 28 verschieben."""
    import pytest

    with pytest.raises(ValueError, match="ESOL0156"):
        create_auftragsdatei(
            file_path=tmp_path / "ESOL0253_VK02",
            owner_ik="101777502",
            absender_ik="123456789",
            empfaenger_ik="661430035",
            logischer_name="SL030179S03",
            timestamp="202603231040",
            size=13,
        )


def test_auftragssatz_fuellt_kurzen_logischen_namen_auf(tmp_path: Path):
    auf_str = create_auftragsdatei(
        file_path=tmp_path / "ESOL0156",
        owner_ik="101777502",
        absender_ik="123456789",
        empfaenger_ik="661430035",
        logischer_name="SL0301",
        timestamp="202603231040",
        size=13,
    )
    assert len(auf_str) == 348
    assert auf_str[104:115] == "SL0301     "
    assert auf_str[202:204] == "I1"
