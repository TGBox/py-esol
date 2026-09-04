import sys
from pathlib import Path

from tools.convert_utf8_to_iso import collect_files, convert_file, main


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



# ---------------------------------------------------------------------------
# Zieldateinamen: ESOL-Dateien tragen keine Endung, und die darf beim
# Konvertieren auch nicht entstehen (Rückmeldung aus der Praxis: aus ESOL0253
# wurde ESOL0253.iso).
# ---------------------------------------------------------------------------

def _run_cli(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["convert_utf8_to_iso.py"] + [str(a) for a in argv])
    main()


def _esol_utf8(pfad: Path) -> bytes:
    """Legt eine UTF-8-kodierte ESOL-Datei ohne Dateiendung an."""
    roh = "UNB+UNOC:3+123456789+661430035+20260408:1200+00151+B+SL051293S04+2'\r\nNAD+Müster+Märta+19900101'\r\n"
    pfad.write_bytes(roh.encode("utf-8"))
    return roh.encode("iso-8859-15")


def test_cli_ohne_out_dir_ersetzt_original_ohne_endung(tmp_path: Path, monkeypatch):
    src = tmp_path / "ESOL0253"
    erwartet = _esol_utf8(src)

    _run_cli(monkeypatch, [src])

    assert src.read_bytes() == erwartet, "Datei muss an ihrem Platz ersetzt werden"
    assert not (tmp_path / "ESOL0253.iso").exists(), "Es darf keine .iso-Datei entstehen"
    assert [p.name for p in tmp_path.iterdir()] == ["ESOL0253"]


def test_cli_out_dir_gleich_quellordner_ersetzt_original(tmp_path: Path, monkeypatch):
    src = tmp_path / "ESOL0253"
    erwartet = _esol_utf8(src)

    # Genau der Fall aus der GUI: der Ausgabeordner ist der Quellordner
    _run_cli(monkeypatch, [src, "--out-dir", tmp_path])

    assert src.read_bytes() == erwartet
    assert not (tmp_path / "ESOL0253.iso").exists()
    assert [p.name for p in tmp_path.iterdir()] == ["ESOL0253"]


def test_cli_out_dir_behaelt_dateinamen(tmp_path: Path, monkeypatch):
    src = tmp_path / "ESOL0253"
    erwartet = _esol_utf8(src)
    out_dir = tmp_path / "konvertiert"

    _run_cli(monkeypatch, [src, "--out-dir", out_dir])

    ziel = out_dir / "ESOL0253"
    assert ziel.read_bytes() == erwartet
    # Original unangetastet (noch UTF-8)
    assert src.read_bytes() != erwartet
    assert not (out_dir / "ESOL0253.iso").exists()


def test_cli_ordner_ersetzt_alle_dateien_ohne_endung(tmp_path: Path, monkeypatch):
    quelle = tmp_path / "in"
    quelle.mkdir()
    erwartet = {}
    for name in ("ESOL0001", "ESOL0002"):
        erwartet[name] = _esol_utf8(quelle / name)

    _run_cli(monkeypatch, [quelle])

    assert sorted(p.name for p in quelle.iterdir()) == ["ESOL0001", "ESOL0002"]
    for name, inhalt in erwartet.items():
        assert (quelle / name).read_bytes() == inhalt


def test_inplace_flag_bleibt_akzeptiert(tmp_path: Path, monkeypatch):
    """--inplace ist wirkungslos, darf aber weiter übergeben werden."""
    src = tmp_path / "ESOL0253"
    erwartet = _esol_utf8(src)

    _run_cli(monkeypatch, [src, "--inplace"])

    assert src.read_bytes() == erwartet
    assert [p.name for p in tmp_path.iterdir()] == ["ESOL0253"]


def test_keine_temporaere_datei_bleibt_liegen(tmp_path: Path, monkeypatch):
    src = tmp_path / "ESOL0253"
    _esol_utf8(src)

    _run_cli(monkeypatch, [src])

    uebrig = [p.name for p in tmp_path.iterdir()]
    assert uebrig == ["ESOL0253"], f"Aufräumen fehlgeschlagen: {uebrig}"


def test_original_bleibt_bei_schreibfehler_unversehrt(tmp_path: Path, monkeypatch):
    """
    Beim Ersetzen am Originalort darf ein abgebrochener Schreibvorgang die
    Ursprungsdatei nicht beschädigen — deshalb wird atomar geschrieben.
    """
    src = tmp_path / "ESOL0253"
    _esol_utf8(src)
    original = src.read_bytes()

    import tools.convert_utf8_to_iso as konverter

    echtes_open = konverter.open if hasattr(konverter, "open") else open

    def kaputtes_open(pfad, *args, **kwargs):
        if konverter._TMP_MARKER in str(pfad):
            raise OSError("Datenträger voll (simuliert)")
        return echtes_open(pfad, *args, **kwargs)

    monkeypatch.setattr(konverter, "open", kaputtes_open, raising=False)

    ok, msg = convert_file(src, src)

    assert ok is False
    assert "Fehler" in msg
    assert src.read_bytes() == original, "Original wurde beschädigt"
    assert [p.name for p in tmp_path.iterdir()] == ["ESOL0253"]


def test_collect_files_ignoriert_temporaere_dateien(tmp_path: Path):
    (tmp_path / "ESOL0253").write_text("a", encoding="iso-8859-15")
    (tmp_path / "ESOL0253.convert-tmp-4711").write_text("b", encoding="iso-8859-15")

    gefunden = [p.name for p in collect_files(tmp_path)]
    assert gefunden == ["ESOL0253"]
