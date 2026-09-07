import os
import tempfile
import pytest
import kostentraeger


def test_kostentraeger_load():
    data = kostentraeger.load(force=True)
    assert isinstance(data, dict)
    assert len(data) > 0
    # Comments starting with _ are filtered
    for k in data.keys():
        assert not k.startswith("_")


def test_kostentraeger_lookup():
    # TK
    assert kostentraeger.lookup("101777502") == "Techniker Krankenkasse (TK)"
    # AOK Baden-Württemberg
    assert kostentraeger.lookup("104212505") == "AOK Baden-Württemberg"
    # Fallback/default for unknown or empty
    assert kostentraeger.lookup("999999999") == ""
    assert kostentraeger.lookup("999999999", default="Unbekannt") == "Unbekannt"
    assert kostentraeger.lookup(None) == ""
    assert kostentraeger.lookup("") == ""


def test_kostentraeger_get_name_or_fallback():
    assert kostentraeger.get_name_or_fallback("101777502") == "Techniker Krankenkasse (TK)"
    assert kostentraeger.get_name_or_fallback("104212505") == "AOK Baden-Württemberg"
    assert kostentraeger.get_name_or_fallback("987654321") == "Krankenkasse (IK 987654321)"
    assert kostentraeger.get_name_or_fallback("") == "Krankenkasse"
    assert kostentraeger.get_name_or_fallback(None) == "Krankenkasse"


def test_kostentraeger_env_override(monkeypatch):
    custom_json = '{"111222333": "Testkasse XYZ"}'
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
        f.write(custom_json)
        tmp_path = f.name

    try:
        monkeypatch.setenv("PY_ESOL_KOSTENTRAEGER", tmp_path)
        data = kostentraeger.load(force=True)
        assert data.get("111222333") == "Testkasse XYZ"
        assert kostentraeger.lookup("111222333") == "Testkasse XYZ"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        # Reset cache back to normal
        monkeypatch.delenv("PY_ESOL_KOSTENTRAEGER", raising=False)
        kostentraeger.load(force=True)
