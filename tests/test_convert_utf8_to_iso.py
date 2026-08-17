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


def test_convert_file_already_iso8859_15(tmp_path: Path):
    iso_file = tmp_path / "sample_already_iso.txt"
    original_text = "UNB+UNOC:3'\r\nNAD+Müster+Märta+Groß'\r\n"
    # Write directly as ISO-8859-15
    iso_file.write_bytes(original_text.encode("iso-8859-15"))

    out_file = tmp_path / "output_iso.txt"
    success, msg = convert_file(iso_file, out_file, target_encoding="iso-8859-15")
    assert success is True

    # Raw bytes must match original exactly (no corruption into '?' or altered line endings)
    assert out_file.read_bytes() == iso_file.read_bytes()
    with open(out_file, "r", encoding="iso-8859-15", newline="") as f:
        assert f.read() == original_text


def test_convert_file_line_endings_preserved(tmp_path: Path):
    # CRLF test
    crlf_file = tmp_path / "crlf.txt"
    crlf_bytes = b"UNB+UNOC:3'\r\nNAD+M\xc3\xbcster'\r\n"
    crlf_file.write_bytes(crlf_bytes)

    out_crlf = tmp_path / "out_crlf.txt"
    convert_file(crlf_file, out_crlf, target_encoding="iso-8859-15")
    assert out_crlf.read_bytes() == b"UNB+UNOC:3'\r\nNAD+M\xfcster'\r\n"

    # LF test
    lf_file = tmp_path / "lf.txt"
    lf_bytes = b"UNB+UNOC:3'\nNAD+M\xc3\xbcster'\n"
    lf_file.write_bytes(lf_bytes)

    out_lf = tmp_path / "out_lf.txt"
    convert_file(lf_file, out_lf, target_encoding="iso-8859-15")
    assert out_lf.read_bytes() == b"UNB+UNOC:3'\nNAD+M\xfcster'\n"

