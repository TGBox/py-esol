import tkinter as tk
import pytest
from gui_muster13_preview import Muster13PreviewFrame

@pytest.fixture
def tk_root():
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()

def test_muster13_preview_frame_initialization(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    assert frame is not None
    assert frame.active_side == "front"
    assert frame.zoom_mode == "fit"
    assert frame.current_beleg is None

def test_muster13_preview_load_beleg(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    sample_beleg = {
        "belegnr": "12345",
        "ik": "104212505",
        "nachname": "Mustermann",
        "vorname": "Erika",
        "geburtstag": "19800101",
        "versichertennummer": "X123456789",
        "versichertenstatus": "10000",
        "bsnr": "123456789",
        "lanr": "987654321",
        "verordnungsdatum": "20251010",
        "zuzahlungskennzeichen": "1",
        "verordnungsart": "1",
        "diagnosegruppe": "WS2",
        "icd10": "M54.5",
        "leitsymptomatik": "Lumbago",
        "brutto": 150.00,
        "zuzahlung_proz": 0.0,
        "zuzahlung_pausch": 0.0,
        "total_zuzahlung": 0.0,
        "positions": [
            {"code": "20501", "tag": "EHE", "anzahl": 6, "einzelbetrag": 25.00, "gesamtbetrag": 150.00, "zuzahlung": 0.0, "datum": "20251011"}
        ]
    }

    frame.load_beleg(sample_beleg, validation_errors=["Fehler Beleg-Nr. 12345"])
    assert frame.current_beleg == sample_beleg
    assert frame.current_rendered_image is not None
    assert frame.lbl_beleg_nr.cget("text") == "Beleg-Nr. 12345"
    assert "Brutto: 150,00 €" in frame.lbl_brutto.cget("text")

def test_muster13_preview_side_switch(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    sample_beleg = {
        "belegnr": "999",
        "nachname": "Tester",
        "vorname": "Hans",
        "brutto": 100.0,
        "total_zuzahlung": 10.0,
        "positions": []
    }
    frame.load_beleg(sample_beleg)

    frame._set_active_side("back")
    assert frame.active_side == "back"
    assert frame.current_rendered_image is not None

    frame._set_active_side("front")
    assert frame.active_side == "front"

def test_muster13_preview_zoom_toggle(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    sample_beleg = {"belegnr": "100", "positions": []}
    frame.load_beleg(sample_beleg)

    frame._toggle_zoom()
    assert frame.zoom_mode == "100"

    frame._toggle_zoom()
    assert frame.zoom_mode == "fit"

def test_muster13_preview_apply_theme(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    sample_beleg = {"belegnr": "200", "positions": []}
    frame.load_beleg(sample_beleg)

    frame.apply_theme("dark")
    frame.apply_theme("light")


def test_muster13_coords_load_dimensions(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    coords = frame._load_calibrated_coords()
    assert "krankenkasse" in coords
    assert "zuz_frei" in coords
    # Check that each entry has (x, y, w, h)
    for key, val in coords.items():
        assert len(val) == 4, f"Field {key} does not have (x, y, w, h): {val}"
        x, y, w, h = val
        assert w > 0 and h > 0, f"Field {key} has invalid dimension: w={w}, h={h}"


def test_muster13_draw_checkbox_centered():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    box = (10, 10, 40, 40)
    font, _, _ = Muster13PreviewFrame._get_fonts(Muster13PreviewFrame)

    # Record draw.text calls
    drawn_points = []
    orig_text = draw.text
    def mock_text(xy, text, **kwargs):
        drawn_points.append((xy, text))
        return orig_text(xy, text, **kwargs)

    draw.text = mock_text
    Muster13PreviewFrame._draw_checkbox(draw, box, "X", font=font)

    assert len(drawn_points) == 1
    xy, char = drawn_points[0]
    assert char == "X"
    # Check that the glyph center is at box center (30, 30)
    bb = draw.textbbox((0, 0), "X", font=font)
    glyph_cx = xy[0] + (bb[0] + bb[2]) / 2.0
    glyph_cy = xy[1] + (bb[1] + bb[3]) / 2.0
    assert abs(glyph_cx - 30.0) < 0.5
    assert abs(glyph_cy - 30.0) < 0.5


def test_muster13_wrap_text_lines():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (500, 500))
    draw = ImageDraw.Draw(img)
    font, _, _ = Muster13PreviewFrame._get_fonts(Muster13PreviewFrame)

    # Word wrapping when text exceeds width
    lines = Muster13PreviewFrame._wrap_text_lines(draw, "Sehr langer Text der umbrochen werden muss", font, max_width=100)
    assert len(lines) > 1

    # Respect explicit newline
    lines_nl = Muster13PreviewFrame._wrap_text_lines(draw, "Zeile 1\nZeile 2", font, max_width=300)
    assert len(lines_nl) == 2
    assert lines_nl[0] == "Zeile 1"
    assert lines_nl[1] == "Zeile 2"


def test_muster13_draw_text_in_box_centering():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (200, 200))
    draw = ImageDraw.Draw(img)
    font, _, _ = Muster13PreviewFrame._get_fonts(Muster13PreviewFrame)

    # Single line in box (y=20, h=60) -> box center y = 50
    box_single = (10, 20, 180, 60)
    drawn = []
    def mock_text(xy, text, **kwargs):
        drawn.append((xy, text))

    draw.text = mock_text
    Muster13PreviewFrame._draw_text_in_box(draw, box_single, "Einzeiler", font=font)
    assert len(drawn) == 1
    (x_pos, y_pos), txt = drawn[0]
    sample_bb = draw.textbbox((0, 0), "Ag123q", font=font)
    line_center_y = y_pos + (sample_bb[1] + sample_bb[3]) / 2.0
    assert abs(line_center_y - 50.0) < 1.0  # Center is around 50

    # Multiline in box (y=10, h=100) -> box center y = 60
    drawn.clear()
    box_multi = (10, 10, 180, 100)
    Muster13PreviewFrame._draw_text_in_box(draw, box_multi, "Zeile Eins\nZeile Zwei", font=font)
    assert len(drawn) == 2
    y0 = drawn[0][0][1]
    y1 = drawn[1][0][1]
    # Block center should be around 60
    block_center_y = (y0 + y1) / 2.0 + (sample_bb[1] + sample_bb[3]) / 2.0
    assert abs(block_center_y - 60.0) < 1.0

