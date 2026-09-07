import os
from unittest.mock import patch
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


def test_muster13_krankenkasse_name_resolution(tk_root):
    frame = Muster13PreviewFrame(tk_root)

    # 1. Direct name in beleg
    beleg1 = {"krankenkasse_name": "Meine Betriebskrankenkasse"}
    assert frame._get_krankenkasse_name(beleg1) == "Meine Betriebskrankenkasse"

    # 2. Known IK for TK
    beleg2 = {"kostentraeger_ik": "101777502"}
    assert frame._get_krankenkasse_name(beleg2) == "Techniker Krankenkasse (TK)"

    # 3. Known IK for AOK Baden-Württemberg via 'ik'
    beleg3 = {"ik": "104212505"}
    assert frame._get_krankenkasse_name(beleg3) == "AOK Baden-Württemberg"

    # 4. Unknown IK fallback
    beleg4 = {"ik": "999888777"}
    assert frame._get_krankenkasse_name(beleg4) == "Krankenkasse (IK 999888777)"


def test_muster13_heilmittel_rows_and_diagnose_rendering(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    beleg = {
        "belegnr": "1001",
        "kostentraeger_ik": "101777502",
        "nachname": "Mustermann",
        "vorname": "Max",
        "diagnosegruppe": "WS2a",
        "icd10": "M54.5",
        "leitsymptomatik": "Chronische Lumbalgie",
        "positions": [
            {"code": "20501", "tag": "EHE", "anzahl": 6.0, "einzelbetrag": 30.0},
            {"code": "29901", "tag": "EHE", "anzahl": 6.0, "einzelbetrag": 10.0},
        ],
    }

    # Intercept _draw_text_in_box calls
    boxes_drawn = {}
    orig_draw = frame._draw_text_in_box

    def intercept_draw(draw, box, text, *args, **kwargs):
        boxes_drawn[box] = text
        return orig_draw(draw, box, text, *args, **kwargs)

    frame._draw_text_in_box = intercept_draw

    font_reg, font_bold, font_small = frame._get_fonts()
    coords = frame._load_calibrated_coords()
    frame._render_front_side(beleg, font_reg, font_bold, font_small)

    # 1. Heilmittel Zeile 1 muss gefüllt sein mit Krankengymnastik
    row1_box = coords["hm_pos1_row1_label"]
    assert row1_box in boxes_drawn
    assert "Krankengymnastik" in boxes_drawn[row1_box]

    # Heilmittel Zeile 2 und 3 dürfen NICHT für vorrangiges Heilmittel belegt sein
    row2_box = coords["hm_pos1_row2_label"]
    row3_box = coords["hm_pos1_row3_label"]
    assert row2_box not in boxes_drawn
    assert row3_box not in boxes_drawn

    # 2. Ergänzendes Heilmittel (29901) muss in hm_pos2_label stehen
    erg_box = coords["hm_pos2_label"]
    assert erg_box in boxes_drawn
    assert "Wärmetherapie" in boxes_drawn[erg_box]

    # 3. Diagnose und ICD-10 müssen in Zeile 1 liegen
    diag_box = coords["diag_freitext_row1"]
    assert diag_box in boxes_drawn
    assert "Chronische Lumbalgie" in boxes_drawn[diag_box]

    icd_box = coords["icd10_row1"]
    assert icd_box in boxes_drawn
    assert "M54.5" in boxes_drawn[icd_box]


def test_muster13_mouse_controls_and_zoom(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    beleg = {"belegnr": "2002", "positions": []}
    frame.load_beleg(beleg)

    # Initial zoom factor
    assert frame.zoom_factor == 1.0
    assert frame.zoom_mode == "fit"

    # Zoom by factor
    frame._zoom_by(1.2)
    assert frame.zoom_factor == 1.2
    assert frame.zoom_mode == "custom"

    frame._zoom_by(0.8)
    assert abs(frame.zoom_factor - 0.96) < 1e-4

    # Mouse wheel events
    class DummyEvent:
        def __init__(self, delta, x=100, y=100):
            self.delta = delta
            self.x = x
            self.y = y

    frame._on_mousewheel(DummyEvent(-120))
    frame._on_alt_mousewheel(DummyEvent(-120))
    frame._on_ctrl_mousewheel(DummyEvent(120))
    assert frame.zoom_factor > 0.96

    # Pan drag (canvas scan_mark and scan_dragto)
    frame._on_pan_start(DummyEvent(0, x=50, y=50))
    frame._on_pan_move(DummyEvent(0, x=30, y=20))


def test_muster13_export_prescription(tk_root, tmp_path):
    frame = Muster13PreviewFrame(tk_root)
    beleg = {
        "belegnr": "3003",
        "kostentraeger_ik": "101777502",
        "nachname": "Export",
        "vorname": "Test",
        "positions": [
            {"code": "20501", "anzahl": 6.0, "einzelbetrag": 30.0}
        ],
    }
    frame.load_beleg(beleg)

    with patch("gui_muster13_preview.messagebox.showinfo"):
        # 1. Export as PDF
        pdf_target = str(tmp_path / "test_prescription.pdf")
        res_pdf = frame.export_prescription(target_path=pdf_target)
        assert res_pdf == pdf_target
        assert os.path.exists(pdf_target)
        assert os.path.getsize(pdf_target) > 1000

        # 2. Export as PNG
        png_target = str(tmp_path / "test_prescription.png")
        res_png = frame.export_prescription(target_path=png_target)
        assert res_png is not None
        front_png = str(tmp_path / "test_prescription_vorderseite.png")
        back_png = str(tmp_path / "test_prescription_rueckseite.png")
        assert os.path.exists(front_png)
        assert os.path.exists(back_png)
        assert os.path.getsize(front_png) > 1000
        assert os.path.getsize(back_png) > 1000


def test_muster13_draw_comb_digits():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 100))
    draw = ImageDraw.Draw(img)
    font, _, _ = Muster13PreviewFrame._get_fonts(Muster13PreviewFrame)

    drawn_boxes = []
    orig_draw_box = Muster13PreviewFrame._draw_text_in_box

    def mock_draw(d, box, txt, *args, **kwargs):
        drawn_boxes.append((box, txt))
        return orig_draw_box(d, box, txt, *args, **kwargs)

    with patch.object(Muster13PreviewFrame, "_draw_text_in_box", side_effect=mock_draw):
        dividers = [100, 130, 160, 190, 220]
        Muster13PreviewFrame._draw_comb_digits(draw, dividers, y=20, h=35, text="1042", font=font)

    assert len(drawn_boxes) == 4
    assert drawn_boxes[0] == ((100, 20, 30, 35), "1")
    assert drawn_boxes[1] == ((130, 20, 30, 35), "0")
    assert drawn_boxes[2] == ((160, 20, 30, 35), "4")
    assert drawn_boxes[3] == ((190, 20, 30, 35), "2")


def test_muster13_draw_fitted_text():
    from PIL import Image
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    font, _, _ = Muster13PreviewFrame._get_fonts(Muster13PreviewFrame)

    # 1. Short text fitting directly
    box_normal = (50, 20, 300, 30)
    Muster13PreviewFrame._draw_fitted_text(img, box_normal, "Kurzer Text", font=font)

    # 2. Overlong text fitting with scaling
    box_narrow = (50, 50, 150, 30)
    overlong_text = "Sprachtherapie (Einzelbehandlung 45 Min)"
    Muster13PreviewFrame._draw_fitted_text(img, box_narrow, overlong_text, font=font)
    # Ensure no crash and valid pixel buffer
    assert img.size == (400, 100)


def test_muster13_doctor_stamp_and_signature_layout(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    beleg = {
        "belegnr": "5005",
        "bsnr": "123456789",
        "lanr": "987654321",
        "positions": [],
    }

    boxes_called = []
    orig_draw = frame._draw_text_in_box

    def intercept(draw, box, text, *args, **kwargs):
        boxes_called.append((box, text))
        return orig_draw(draw, box, text, *args, **kwargs)

    frame._draw_text_in_box = intercept
    font_reg, font_bold, font_small = frame._get_fonts()
    frame._render_front_side(beleg, font_reg, font_bold, font_small)

    # Find stamp and signature in called boxes
    stamp_entries = [b for b in boxes_called if "Dr. med. Musterarzt" in b[1]]
    sig_entries = [b for b in boxes_called if b[1] == "Dr. Musterarzt"]

    assert len(stamp_entries) >= 1
    assert len(sig_entries) >= 1

    stamp_box = stamp_entries[0][0]
    sig_box = sig_entries[0][0]

    # Check that stamp is on top and signature is below it
    assert stamp_box[1] < sig_box[1]
    # Check 60% / 40% height ratio roughly
    total_h = stamp_box[3] + sig_box[3]
    assert abs(stamp_box[3] / total_h - 0.60) < 0.05
    assert abs(sig_box[3] / total_h - 0.40) < 0.05


def test_muster13_back_side_fitted_table_rendering(tk_root):
    frame = Muster13PreviewFrame(tk_root)
    beleg = {
        "belegnr": "6006",
        "rechnungsnummer": "RE12345",
        "leistungserbringer_ik": "104212505",
        "positions": [
            {"code": "20501", "anzahl": 2, "datum": "20251002"}
        ],
    }

    fitted_calls = []
    orig_fitted = frame._draw_fitted_text

    def intercept_fitted(target_img, box, text, *args, **kwargs):
        fitted_calls.append((box, text))
        return orig_fitted(target_img, box, text, *args, **kwargs)

    drawn_text_boxes = []
    orig_draw_box = frame._draw_text_in_box

    def intercept_text(draw, box, text, *args, **kwargs):
        drawn_text_boxes.append((box, text))
        return orig_draw_box(draw, box, text, *args, **kwargs)

    frame._draw_text_in_box = intercept_text
    frame._draw_fitted_text = intercept_fitted
    font_reg, font_bold, font_small = frame._get_fonts()
    img_back = frame._render_back_side(beleg, font_reg, font_bold, font_small)

    assert img_back is not None
    assert len(fitted_calls) == 2  # 2 treatment sessions
    # Treatment title rendered into column 2
    for box, text in fitted_calls:
        assert box[0] == 379  # Col 2 x-coord
        assert box[2] == 327  # Col 2 width
        assert "Krankengymnastik" in text

    # Check Datum boxes in column 1: must be within x=264..378
    date_entries = [b for b in drawn_text_boxes if "2025" in str(b[1])]
    assert len(date_entries) >= 2
    for box, text in date_entries:
        assert box[0] >= 264, f"Datum box starts to the left of the column divider line (264): {box}"
        assert box[0] + box[2] <= 378, f"Datum box exceeds column right divider line (378): {box}"




