from pathlib import Path
from tools.convert_utf8_to_iso import convert_file, collect_files


def test_convert_file_utf8_to_iso8859_15(tmp_path: Path):
    utf8_file = tmp_path / "sample_utf8.txt"
    # Write German umlauts encoded in UTF-8
    original_text = "UNB+UNOC:3'NAD+Müster+Märta'\n"
    utf8_file.write_text(original_text, encoding="utf-8")

    iso_file = tmp_path / "sample_iso.txt"

    success, msg = convert_file(utf8_file, iso_file, target_encoding="iso-8859-15")
    assert success is True

    # Verify content read in ISO-8859-15
    read_text = iso_file.read_text(encoding="iso-8859-15")
    assert read_text == original_text

    # Verify raw bytes: UTF-8 'ü' is 0xc3 0xbc (2 bytes), ISO-8859-15 'ü' is 0xfc (1 byte)
    raw_bytes = iso_file.read_bytes()
    assert b"\xfc" in raw_bytes


def test_collect_files(tmp_path: Path):
    f1 = tmp_path / "f1"
    f2 = tmp_path / "sub" / "f2"
    f1.write_text("test1")
    f2.parent.mkdir()
    f2.write_text("test2")

    files = collect_files(tmp_path)
    assert len(files) == 2
    assert f1 in files
    assert f2 in files
