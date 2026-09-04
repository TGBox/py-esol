"""
ESOL Visuelle Rezept-Vorschau — Fotorealistisches virtuelles Verordnungsblatt (Muster 13/18)
mit Templating auf Basis der Vorlagenbilder in assets/Muster13_1280x1280.jpg (Vorderseite) und
assets/Muster13_2_1280x1280.jpg (Rückseite).
"""

import os
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageTk

import codelisten
import kostentraeger
import theme_manager
from support_helper import translate_error
from tools.generate_correction import format_date_german

_MONO = ("Consolas", 10)
_MONO_B = ("Consolas", 10, "bold")
_UI = ("Segoe UI", 9)
_UI_B = ("Segoe UI", 9, "bold")

_STUFE_ICON = {"fehler": "⛔", "warnung": "⚠️", "info": "ℹ️"}
_STUFE_RANG = {"fehler": 0, "warnung": 1, "info": 2}

# Standard-Fallback-Bounding-Boxen (abs_x, abs_y, abs_w, abs_h) für Muster 13 Verordnung
DEFAULT_MUSTER13_BOXES: Dict[str, tuple] = {
    "krankenkasse": (249, 56, 478, 43),
    "versicherter_name": (252, 116, 334, 102),
    "geb_datum": (588, 151, 137, 69),
    "ik": (248, 231, 168, 39),
    "vers_nr": (419, 234, 187, 35),
    "status": (616, 234, 110, 36),
    "bsnr": (250, 285, 163, 38),
    "lanr": (420, 285, 163, 34),
    "verordnungsdatum": (588, 286, 138, 35),
    "zuz_frei": (205, 39, 42, 43),
    "zuz_pflicht": (206, 99, 42, 40),
    "unfallfolgen": (207, 158, 38, 46),
    "bvg": (207, 219, 39, 43),
    "v_art_erst": (752, 35, 30, 30),
    "v_art_folge": (752, 65, 30, 30),
    "hm_physio": (752, 100, 27, 31),
    "hm_podo": (754, 138, 28, 31),
    "hm_logo": (752, 175, 29, 31),
    "hm_ergo": (753, 212, 29, 31),
    "hm_ernaehrung": (752, 251, 30, 32),
    # Diagnosen: Zeile 1 und Zeile 2
    "diag_freitext": (416, 363, 626, 38),
    "diag_freitext_row1": (416, 363, 626, 38),
    "diag_freitext_row2": (416, 401, 626, 38),
    "diag_gruppe": (339, 441, 62, 33),
    "icd10": (248, 357, 154, 39),
    "icd10_row1": (248, 357, 154, 39),
    "icd10_row2": (248, 396, 154, 39),
    "leitsymp_code": (1011, 440, 32, 37),
    "leitsymp_a": (629, 443, 28, 31),
    "leitsymp_b": (691, 443, 31, 32),
    "leitsymp_c": (754, 442, 27, 33),
    "leitsymp_patientenindividuell": (1013, 444, 30, 31),
    "leitsymp_freitext": (246, 499, 797, 76),
    "therapiebericht": (247, 824, 32, 31),
    "hausbesuch_ja": (569, 826, 29, 28),
    "hausbesuch_nein": (644, 824, 33, 32),
    "therapiefrequenz": (836, 822, 209, 34),
    "therapieziele": (247, 947, 489, 213),
    # Vorrangiges Heilmittel: 3 Zeilen
    "hm_pos1_label": (246, 627, 657, 38),
    "hm_pos1_anzahl": (909, 627, 130, 38),
    "hm_pos1_row1_label": (246, 627, 657, 38),
    "hm_pos1_row1_anzahl": (909, 627, 130, 38),
    "hm_pos1_row2_label": (246, 665, 657, 38),
    "hm_pos1_row2_anzahl": (909, 665, 130, 38),
    "hm_pos1_row3_label": (246, 703, 657, 38),
    "hm_pos1_row3_anzahl": (909, 703, 130, 38),
    # Ergänzendes Heilmittel
    "hm_pos2_label": (247, 766, 657, 39),
    "hm_pos2_anzahl": (908, 767, 134, 39),
    "ik_leistungserbringer": (461, 1174, 275, 38),
    "arztstempel": (756, 1000, 284, 193),
    "arztunterschrift": (789, 1063, 210, 74),
}


class ScrollableFrame(ttk.Frame):
    """Vertikal scrollbarer Container — das Verordnungsblatt ist höher als der Tab."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=15)

        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mausrad: einmalig anwenden-weit registrieren (add="+" lässt andere
        # Bindings unberührt) und im Handler prüfen, ob das Ereignis wirklich
        # zu diesem Container gehört. So bleibt das Scrollen in inneren
        # Treeviews/Textfeldern denen selbst überlassen.
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind_all(seq, self._on_wheel, add="+")

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event):
        widget = getattr(event, "widget", None)
        if not self._handles(widget):
            return

        if getattr(event, "num", None) in (4, 5):
            schritte = -1 if event.num == 4 else 1
        else:
            schritte = int(-1 * (getattr(event, "delta", 0) / 120)) or 0
        if schritte:
            self.canvas.yview_scroll(schritte, "units")

    def _handles(self, widget) -> bool:
        """
        True, wenn das Mausrad-Ereignis diesen Container scrollen soll:
        das Widget muss innerhalb liegen und darf nicht selbst scrollbar sein.
        """
        if widget is None:
            return False
        try:
            if not str(widget).startswith(str(self)):
                return False
        except Exception:
            return False
        # Eigene Scrollbereiche (Treeview, Text, Listbox, Canvas) selbst scrollen lassen
        node = widget
        while node is not None and str(node) != str(self):
            if isinstance(node, (ttk.Treeview, tk.Text, tk.Listbox)):
                return False
            node = getattr(node, "master", None)
        return True

    def scroll_to_top(self):
        self.canvas.yview_moveto(0.0)

    def apply_theme(self, colors: Dict[str, str]):
        self.canvas.configure(background=colors["bg"])


class Muster13PreviewFrame(ttk.Frame):
    """
    Grafische Verordnungsblatt-Vorschau im Layout der Heilmittelverordnung (Muster 13/18)
    mit exakt kalibriertem Bild-Overlay (Vorder- und Rückseite) und Zoom-Modus.
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=10)

        self.current_beleg: Optional[Dict[str, Any]] = None
        self.validation_errors: List[str] = []

        # Interner Zustand
        self.active_side: str = "front"  # "front" oder "back"
        self.zoom_mode: str = "fit"      # "fit" (An Fenster anpassen) oder "100" (Original 1280x1280)
        self.zoom_factor: float = 1.0
        self.current_rendered_image: Optional[Image.Image] = None
        self.photo_image: Optional[ImageTk.PhotoImage] = None

        # Pfade zu den Grafikvorlagen
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.path_front_asset = os.path.join(self.base_dir, "assets", "Muster13_1280x1280.jpg")
        self.path_back_asset = os.path.join(self.base_dir, "assets", "Muster13_2_1280x1280.jpg")

        self._setup_ui()

    def _setup_ui(self):
        # -------------------------------------------------------------
        # Header / Control Toolbar
        # -------------------------------------------------------------
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(0, 8))

        # Title & Beleg Info
        ttk.Label(
            toolbar,
            text="📋 Virtuelles Verordnungsblatt Muster 13 / 18",
            font=("Segoe UI", 11, "bold"),
        ).pack(side="left", padx=(0, 15))

        self.lbl_beleg_nr = ttk.Label(
            toolbar, text="Kein Beleg gewählt", font=("Consolas", 10, "bold"), foreground="#0275d8"
        )
        self.lbl_beleg_nr.pack(side="left", padx=(0, 15))

        # Side Switch Buttons (Vorderseite / Rückseite)
        side_frame = ttk.Frame(toolbar)
        side_frame.pack(side="left", padx=5)

        self.btn_side_front = ttk.Button(
            side_frame, text="📜 Vorderseite (Muster 13)", command=lambda: self._set_active_side("front")
        )
        self.btn_side_front.pack(side="left", padx=2)

        self.btn_side_back = ttk.Button(
            side_frame, text="📄 Rückseite (Abrechnung)", command=lambda: self._set_active_side("back")
        )
        self.btn_side_back.pack(side="left", padx=2)

        # Export Button
        self.btn_export = ttk.Button(
            toolbar, text="💾 Exportieren...", command=self.export_prescription
        )
        self.btn_export.pack(side="right", padx=5)

        # Zoom Toggle Button
        self.btn_zoom = ttk.Button(
            toolbar, text="🔍 Fit Window", command=self._toggle_zoom
        )
        self.btn_zoom.pack(side="right", padx=5)

        # Interactive Calibrator Button
        self.btn_calibrate = ttk.Button(
            toolbar, text="🎯 Feld-Kalibrator", command=self._open_calibrator
        )
        self.btn_calibrate.pack(side="right", padx=5)

        # -------------------------------------------------------------
        # Canvas Container mit Scrollbars
        # -------------------------------------------------------------
        canvas_container = ttk.Frame(self)
        canvas_container.pack(fill="both", expand=True, pady=(0, 8))

        self.canvas = tk.Canvas(canvas_container, bg="#1e1e1e", highlightthickness=0)
        self.h_scroll = ttk.Scrollbar(canvas_container, orient="horizontal", command=self.canvas.xview)
        self.v_scroll = ttk.Scrollbar(canvas_container, orient="vertical", command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Maus-Interaktionen für Scrollen, Zoomen & Panning
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.canvas.bind("<Alt-MouseWheel>", self._on_alt_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_alt_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel)
        self.canvas.bind("<Button-5>", self._on_mousewheel)

        self.canvas.bind("<Alt-ButtonPress-1>", self._on_pan_start)
        self.canvas.bind("<Alt-B1-Motion>", self._on_pan_move)
        self.canvas.bind("<ButtonPress-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_move)

        # -------------------------------------------------------------
        # Summen- & Info-Panel unten
        # -------------------------------------------------------------
        sum_frame = ttk.LabelFrame(self, text=" Stammdaten & Abrechnung ", padding=6)
        sum_frame.pack(fill="x", pady=(0, 4))

        pad = {"padx": 6, "pady": 2}

        # Zeile 0: Patient & Krankenkasse (API Contracts / Test Kompatibilität)
        ttk.Label(sum_frame, text="Name:").grid(row=0, column=0, sticky="w", **pad)
        self.lbl_name = ttk.Label(sum_frame, text="-", font=("Segoe UI", 9, "bold"))
        self.lbl_name.grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(sum_frame, text="Vers-Nr:").grid(row=0, column=2, sticky="w", **pad)
        self.lbl_versnr = ttk.Label(sum_frame, text="-")
        self.lbl_versnr.grid(row=0, column=3, sticky="w", **pad)

        ttk.Label(sum_frame, text="Geburtstag:").grid(row=0, column=4, sticky="w", **pad)
        self.lbl_geb = ttk.Label(sum_frame, text="-")
        self.lbl_geb.grid(row=0, column=5, sticky="w", **pad)

        ttk.Label(sum_frame, text="IK:").grid(row=0, column=6, sticky="w", **pad)
        self.lbl_ik = ttk.Label(sum_frame, text="-")
        self.lbl_ik.grid(row=0, column=7, sticky="w", **pad)

        # Zeile 1: Zuzahlungsstatus & Beträge
        self.lbl_zuz_status = ttk.Label(sum_frame, text="-", font=("Segoe UI", 9))
        self.lbl_zuz_status.grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        self.lbl_brutto = ttk.Label(sum_frame, text="Brutto: 0,00 €", font=("Consolas", 9, "bold"))
        self.lbl_brutto.grid(row=1, column=2, columnspan=2, sticky="w", **pad)

        self.lbl_proz_zuz = ttk.Label(sum_frame, text="10%: 0,00 €", font=("Segoe UI", 9))
        self.lbl_proz_zuz.grid(row=1, column=4, sticky="w", **pad)

        self.lbl_pausch_zuz = ttk.Label(sum_frame, text="10€ Pausch: 10,00 €", font=("Segoe UI", 9))
        self.lbl_pausch_zuz.grid(row=1, column=5, sticky="w", **pad)

        self.lbl_total_zuz = ttk.Label(
            sum_frame, text="Zuzahlung: 0,00 €", font=("Consolas", 9, "bold"), foreground="#d9534f"
        )
        self.lbl_total_zuz.grid(row=1, column=6, sticky="w", **pad)

        self.lbl_netto = ttk.Label(
            sum_frame, text="Kassenanteil: 0,00 €", font=("Consolas", 9, "bold"), foreground="#5cb85c"
        )
        self.lbl_netto.grid(row=1, column=7, sticky="w", **pad)

        # Error notification banner inside Muster 13 form
        self.err_banner = ttk.Label(
            self, text="", font=("Segoe UI", 9, "bold"), background="#f8d7da", foreground="#721c24", padding=6
        )

    def _open_calibrator(self):
        try:
            from tools.calibrate_gui import Muster13CalibratorDialog
            dlg = Muster13CalibratorDialog(self)
            dlg.grab_set()
        except Exception as err:
            theme_manager.messagebox.showerror("Fehler beim Öffnen", f"Kalibrator konnte nicht geöffnet werden: {err}")

    def apply_theme(self, mode: Optional[str] = None):
        colors = theme_manager.get_theme_colors(mode)
        active_mode = mode or theme_manager.get_current_theme()
        if active_mode == "dark":
            self.lbl_beleg_nr.config(foreground=colors["log_header"])
            self.lbl_total_zuz.config(foreground=colors["log_error"])
            self.lbl_netto.config(foreground=colors["log_ok"])
            self.err_banner.config(background="#5c1d24", foreground="#f8d7da")
            self.canvas.config(bg="#1e1e1e")
        else:
            self.lbl_beleg_nr.config(foreground="#0275d8")
            self.lbl_total_zuz.config(foreground="#d9534f")
            self.lbl_netto.config(foreground="#5cb85c")
            self.err_banner.config(background="#f8d7da", foreground="#721c24")
            self.canvas.config(bg="#d0d0d0")

        # Neu rendern
        if self.current_beleg:
            self._render_active_beleg()

    def _set_active_side(self, side: str):
        if self.active_side != side:
            self.active_side = side
            self._render_active_beleg()

    def _on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _on_pan_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_mousewheel(self, event):
        state = getattr(event, "state", 0)
        # Control-Taste gehalten -> Zoom
        if state & 0x0004:
            return self._on_ctrl_mousewheel(event)
        # Alt- oder Shift-Taste gehalten -> Horizontaler Bildlauf
        if (state & 0x20000) or (state & 0x0008) or (state & 0x0001):
            return self._on_alt_mousewheel(event)

        # Vertikaler Bildlauf
        delta = getattr(event, "delta", 0)
        if getattr(event, "num", None) == 4:
            schritte = -1
        elif getattr(event, "num", None) == 5:
            schritte = 1
        else:
            schritte = -1 if delta > 0 else 1
        self.canvas.yview_scroll(schritte, "units")

    def _on_alt_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        schritte = -1 if delta > 0 else 1
        self.canvas.xview_scroll(schritte, "units")

    def _on_ctrl_mousewheel(self, event):
        delta = getattr(event, "delta", 0)
        if delta > 0 or getattr(event, "num", None) == 4:
            self._zoom_by(1.15)
        else:
            self._zoom_by(1.0 / 1.15)

    def _zoom_by(self, factor: float):
        self.zoom_mode = "custom"
        self.zoom_factor = max(0.2, min(self.zoom_factor * factor, 4.0))
        pct = int(self.zoom_factor * 100)
        self.btn_zoom.config(text=f"🔍 {pct}%")
        self._update_canvas_display()

    def _toggle_zoom(self):
        if self.zoom_mode == "fit":
            self.zoom_mode = "100"
            self.zoom_factor = 1.0
            self.btn_zoom.config(text="🔍 100% Zoom")
        else:
            self.zoom_mode = "fit"
            self.zoom_factor = 1.0
            self.btn_zoom.config(text="🔍 Fit Window")
        self._update_canvas_display()

    def _on_canvas_configure(self, event):
        if self.zoom_mode == "fit" and self.current_rendered_image:
            new_size = (event.width, event.height)
            if getattr(self, "_last_canvas_size", None) != new_size:
                self._last_canvas_size = new_size
                self._update_canvas_display()

    def load_beleg(self, beleg: Dict[str, Any], validation_errors: List[str] = None):
        """
        Befüllt das virtuelle Verordnungsblatt mit den Daten des ausgewählten Belegs.
        """
        self.current_beleg = beleg
        self.validation_errors = validation_errors or []

        b_nr = str(beleg.get("belegnr", "-"))
        self.lbl_beleg_nr.config(text=f"Beleg-Nr. {b_nr}")

        # Stammdaten-Labels aktualisieren
        nachname = beleg.get("nachname", "")
        vorname = beleg.get("vorname", "")
        full_name = f"{nachname}, {vorname}".strip(", ")
        self.lbl_name.config(text=full_name or "-")
        self.lbl_versnr.config(text=str(beleg.get("versichertennummer", "-")))
        geb_raw = str(beleg.get("geburtstag", ""))
        self.lbl_geb.config(text=format_date_german(geb_raw) if geb_raw else "-")
        self.lbl_ik.config(text=str(beleg.get("ik", "-")))

        # Zuzahlungsstatus
        zkz = str(beleg.get("zuzahlungskennzeichen", "2"))
        zkz_labels = {
            "0": "0 — Keine Zuzahlung",
            "1": "1 — Zuzahlungsbefreit",
            "2": "2 — Zuzahlungspflichtig",
            "3": "3 — Zuzahlungspflichtig",
            "4": "4 — Übergang zu befreit",
            "5": "5 — Übergang zu pflichtig",
        }
        self.lbl_zuz_status.config(text=zkz_labels.get(zkz, f"Kennzeichen {zkz}"))

        # Summen aktualisieren
        brutto = float(beleg.get("brutto", 0.0))
        proz_zuz = float(beleg.get("zuzahlung_proz", 0.0))
        pausch_zuz = float(beleg.get("zuzahlung_pausch", 10.0))
        tot_zuz = float(beleg.get("total_zuzahlung", 0.0))
        netto = round(brutto - tot_zuz, 2)

        self.lbl_brutto.config(text=f"Brutto: {brutto:.2f} €".replace(".", ","))
        self.lbl_proz_zuz.config(text=f"10%: {proz_zuz:.2f} €".replace(".", ","))
        self.lbl_pausch_zuz.config(text=f"10€ Pausch: {pausch_zuz:.2f} €".replace(".", ","))
        self.lbl_total_zuz.config(text=f"Zuzahlung: {tot_zuz:.2f} €".replace(".", ","))
        self.lbl_netto.config(text=f"Kassenanteil: {netto:.2f} €".replace(".", ","))

        # Fehler-Banner falls Fehler auf diesen Beleg zutreffen
        matching = [e for e in self.validation_errors if b_nr in e]
        if matching:
            trans = translate_error(matching[0])
            self.err_banner.config(text=f"⚠️ {trans['title']} — {trans['action']}")
            self.err_banner.pack(fill="x", pady=(4, 0))
        else:
            self.err_banner.pack_forget()

        # Bild-Overlay neu aufbauen & rendern
        self._render_active_beleg()

    def _get_fonts(self):
        """Monospace-Schriften für den Rezeptdruck."""
        try:
            font_regular = ImageFont.truetype("consola.ttf", 20)
            font_bold = ImageFont.truetype("consolab.ttf", 21)
            font_small = ImageFont.truetype("consola.ttf", 16)
        except IOError:
            try:
                font_regular = ImageFont.truetype("arial.ttf", 18)
                font_bold = ImageFont.truetype("arialbd.ttf", 19)
                font_small = ImageFont.truetype("arial.ttf", 15)
            except IOError:
                font_regular = font_bold = font_small = ImageFont.load_default()

        return font_regular, font_bold, font_small

    @classmethod
    def _get_handwriting_font(cls, size: int = 22) -> Any:
        """Handschrift-Font für Unterschriften (z.B. Segoe Script, Ink Free oder kursiver Fallback)."""
        candidates = ("segoesc.ttf", "Inkfree.ttf", "segoescb.ttf", "BRUSHSCI.TTF", "LHANDW.TTF", "ariali.ttf")
        for fname in candidates:
            try:
                return ImageFont.truetype(fname, size)
            except IOError:
                continue
        try:
            return ImageFont.truetype("arial.ttf", size)
        except IOError:
            return ImageFont.load_default()

    @classmethod
    def _get_stamp_font(cls, size: int = 13) -> Any:
        """Kompakte serifenlose Schrift für Praxisstempel."""
        try:
            return ImageFont.truetype("arial.ttf", size)
        except IOError:
            try:
                return ImageFont.truetype("consola.ttf", size)
            except IOError:
                return ImageFont.load_default()

    def _render_active_beleg(self):
        if not self.current_beleg:
            return

        beleg = self.current_beleg
        font_regular, font_bold, font_small = self._get_fonts()

        if self.active_side == "front":
            img = self._render_front_side(beleg, font_regular, font_bold, font_small)
        else:
            img = self._render_back_side(beleg, font_regular, font_bold, font_small)

        self.current_rendered_image = img
        self._update_canvas_display()

    def _get_krankenkasse_name(self, beleg: Dict[str, Any]) -> str:
        """Ermittelt den Klarnamen der Krankenkasse / des Kostenträgers anhand der IK."""
        for key in ("krankenkasse_name", "name_krankenkasse", "kassenname"):
            val = str(beleg.get(key, "")).strip()
            if val:
                return val

        ik = str(beleg.get("krankenkasse_ik") or beleg.get("kostentraeger_ik") or beleg.get("ik") or "").strip()
        return kostentraeger.get_name_or_fallback(ik)

    def _load_calibrated_coords(self) -> Dict[str, tuple]:
        """Lädt benutzerdefinierte Kalibrierungskoordinaten (abs_x, abs_y, abs_w, abs_h) aus assets/muster13_coords.json."""
        coords = dict(DEFAULT_MUSTER13_BOXES)
        json_path = os.path.join(self.base_dir, "assets", "muster13_coords.json")
        if os.path.exists(json_path):
            try:
                import json
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    fields = data.get("fields", {})
                    for k, v in fields.items():
                        x = int(v["abs_x"])
                        y = int(v["abs_y"])
                        w = int(v.get("abs_w", DEFAULT_MUSTER13_BOXES.get(k, (0, 0, 30, 30))[2]))
                        h = int(v.get("abs_h", DEFAULT_MUSTER13_BOXES.get(k, (0, 0, 30, 30))[3]))

                        if k == "hm_pos1_label":
                            row_h = (h // 3) if h > 50 else h
                            coords["hm_pos1_label"] = (x, y, w, row_h)
                            coords["hm_pos1_row1_label"] = (x, y, w, row_h)
                            coords["hm_pos1_row2_label"] = (x, y + row_h, w, row_h)
                            coords["hm_pos1_row3_label"] = (x, y + 2 * row_h, w, row_h)
                        elif k == "hm_pos1_anzahl":
                            row_h = (h // 3) if h > 50 else h
                            coords["hm_pos1_anzahl"] = (x, y, w, row_h)
                            coords["hm_pos1_row1_anzahl"] = (x, y, w, row_h)
                            coords["hm_pos1_row2_anzahl"] = (x, y + row_h, w, row_h)
                            coords["hm_pos1_row3_anzahl"] = (x, y + 2 * row_h, w, row_h)
                        elif k == "icd10":
                            row_h = (h // 2) if h > 50 else h
                            coords["icd10"] = (x, y, w, row_h)
                            coords["icd10_row1"] = (x, y, w, row_h)
                            coords["icd10_row2"] = (x, y + row_h, w, row_h)
                        elif k == "diag_freitext":
                            row_h = (h // 2) if h > 50 else h
                            coords["diag_freitext"] = (x, y, w, row_h)
                            coords["diag_freitext_row1"] = (x, y, w, row_h)
                            coords["diag_freitext_row2"] = (x, y + row_h, w, row_h)
                        else:
                            coords[k] = (x, y, w, h)
            except Exception:
                pass
        return coords

    @staticmethod
    def _draw_checkbox(
        draw: ImageDraw.ImageDraw,
        box: tuple,
        char: str = "X",
        fill: tuple = (180, 20, 20),
        font: Any = None,
    ):
        """
        Platziert ein Kreuz [X] exakt horizontal und vertikal zentriert in der Checkbox-Box (x, y, w, h).
        """
        if len(box) >= 4:
            x, y, w, h = box[0], box[1], box[2], box[3]
        else:
            x, y = box[0], box[1]
            w, h = 30, 30

        bb = draw.textbbox((0, 0), char, font=font)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]

        center_x = x + (w - tw) / 2.0 - bb[0]
        center_y = y + (h - th) / 2.0 - bb[1]

        draw.text((center_x, center_y), char, fill=fill, font=font)

    @staticmethod
    def _wrap_text_lines(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int) -> List[str]:
        """
        Bricht Text anhand von bestehenden Newlines und der maximalen Pixelbreite (Word-Wrap) um.
        """
        lines = []
        for raw_line in str(text).split("\n"):
            raw_line = raw_line.strip()
            if not raw_line:
                lines.append("")
                continue

            words = raw_line.split(" ")
            current_line = ""
            for word in words:
                candidate = f"{current_line} {word}".strip() if current_line else word
                bbox = draw.textbbox((0, 0), candidate, font=font)
                cand_w = bbox[2] - bbox[0]
                if cand_w <= max_width:
                    current_line = candidate
                else:
                    if current_line:
                        lines.append(current_line)
                        current_line = word
                    else:
                        lines.append(word)
                        current_line = ""
            if current_line:
                lines.append(current_line)
        return lines or [""]

    @classmethod
    def _draw_text_in_box(
        cls,
        draw: ImageDraw.ImageDraw,
        box: tuple,
        text: str,
        font: Any,
        fill: tuple = (5, 20, 90),
        pad_x: int = 4,
        align_h: str = "left",
    ):
        """
        Rendert einzeiligen oder mehrzeiligen Text in einer Bounding-Box (x, y, w, h).
        - Mehrzeilige Texte werden automatisch an max_width (w - 2 * pad_x) umbrochen.
        - Der gesamte resultierende Textblock wird vertikal exakt in der Mitte der Box zentriert:
          Die Mitte des Textblocks liegt auf der vertikalen Mitte des Feldes.
        - Horizontal: leicht linksbündig mit pad_x (oder 'center' falls align_h == 'center').
        """
        if not text:
            return

        if len(box) >= 4:
            x, y, w, h = box[0], box[1], box[2], box[3]
        else:
            x, y = box[0], box[1]
            w, h = 200, 30

        max_w = max(w - 2 * pad_x, 10)
        lines = cls._wrap_text_lines(draw, text, font, max_w)

        sample_bb = draw.textbbox((0, 0), "Ag123q", font=font)
        line_h = max(sample_bb[3] - sample_bb[1], 12)
        line_spacing = max(int(line_h * 1.25), line_h + 4)

        n_lines = len(lines)
        # Vertikaler Startpunkt: Mitte des Textblocks liegt genau auf der Mitte des Feldes
        y_start = (y + h / 2.0) - ((n_lines - 1) * line_spacing / 2.0 + (sample_bb[1] + sample_bb[3]) / 2.0)

        for i, line in enumerate(lines):
            cur_y = y_start + i * line_spacing
            if align_h == "center":
                l_bb = draw.textbbox((0, 0), line, font=font)
                lw = l_bb[2] - l_bb[0]
                cur_x = x + (w - lw) / 2.0 - l_bb[0]
            else:
                cur_x = x + pad_x

            draw.text((cur_x, cur_y), line, fill=fill, font=font)

    @classmethod
    def _draw_comb_digits(
        cls,
        draw: ImageDraw.ImageDraw,
        dividers: List[int],
        y: int,
        h: int,
        text: str,
        font: Any,
        fill: tuple = (5, 20, 90),
    ):
        """
        Platziert einzelne Ziffern zentriert in den durch 'dividers' definierten Kästchen.
        dividers: Liste von X-Koordinaten der vertikalen Trennlinien (N+1 Trennlinien für N Kästchen).
        """
        digits = [c for c in str(text or "") if c.isdigit()]
        n_boxes = max(len(dividers) - 1, 0)
        for i, digit in enumerate(digits[:n_boxes]):
            x0 = dividers[i]
            x1 = dividers[i + 1]
            w = x1 - x0
            cls._draw_text_in_box(
                draw,
                (x0, y, w, h),
                digit,
                font=font,
                fill=fill,
                pad_x=1,
                align_h="center",
            )

    @classmethod
    def _draw_fitted_text(
        cls,
        img_target: Image.Image,
        box: tuple,
        text: str,
        font: Any,
        fill: tuple = (5, 20, 90),
        pad_x: int = 4,
        align_h: str = "center",
    ):
        """
        Rendert einzeiligen Text in einer Bounding-Box (x, y, w, h).
        Falls die Textbreite die Boxbreite (w - 2 * pad_x) überschreitet,
        wird die Buchstabenbreite und der Zeichenabstand stufenlos gestaucht (horizontal scaling),
        sodass der vollständige Text ohne Überschreitung der Grenzen abgebildet wird.
        """
        if not text:
            return

        x, y, w, h = box[0], box[1], box[2], box[3]
        max_w = max(w - 2 * pad_x, 10)

        dummy_draw = ImageDraw.Draw(img_target)
        bb = dummy_draw.textbbox((0, 0), text, font=font)
        tw = max(bb[2] - bb[0], 1)
        th = max(bb[3] - bb[1], 1)

        if tw <= max_w:
            cls._draw_text_in_box(
                dummy_draw,
                box,
                text,
                font=font,
                fill=fill,
                pad_x=pad_x,
                align_h=align_h,
            )
        else:
            scale_x = max_w / tw
            target_w = max(int(tw * scale_x), 1)

            txt_surface = Image.new("RGBA", (tw + 10, th + 10), (0, 0, 0, 0))
            d_txt = ImageDraw.Draw(txt_surface)
            rgba_fill = fill + (255,) if len(fill) == 3 else fill
            d_txt.text((-bb[0], -bb[1]), text, font=font, fill=rgba_fill)

            txt_crop = txt_surface.crop((0, 0, tw, th))
            txt_scaled = txt_crop.resize((target_w, th), Image.Resampling.LANCZOS)

            if align_h == "center":
                pos_x = int(x + (w - target_w) / 2.0)
            elif align_h == "right":
                pos_x = int(x + w - pad_x - target_w)
            else:
                pos_x = int(x + pad_x)

            sample_bb = dummy_draw.textbbox((0, 0), "Ag123q", font=font)
            line_glyph_h = sample_bb[3] - sample_bb[1]
            pos_y = int(y + (h - line_glyph_h) / 2.0)
            img_target.paste(txt_scaled, (pos_x, pos_y), txt_scaled)

    def _render_front_side(
        self, beleg: Dict[str, Any], font_reg, font_bold, font_small
    ) -> Image.Image:
        """Rendert die Vorderseite des Muster 13 Verordnungsblatts mit dunkler Tinte."""
        if os.path.exists(self.path_front_asset):
            base_img = Image.open(self.path_front_asset).convert("RGB")
        else:
            base_img = Image.new("RGB", (1280, 1280), color=(245, 245, 220))

        draw = ImageDraw.Draw(base_img)

        # IMMER dunkle Kassenrezept-Tinte (Dunkelblau/Schwarz) — KEIN GELB!
        ink_color = (5, 20, 90)       # Dunkelblaue Nadel- / Laserdrucker-Tinte
        check_color = (180, 20, 20)   # Rote Abhakung

        # Dynamisch geladene Mauskalibrierungs-Koordinaten (falls vorhanden)
        c = self._load_calibrated_coords()

        # 1. Krankenkasse / Kostenträger
        kassen_name = self._get_krankenkasse_name(beleg)
        self._draw_text_in_box(
            draw,
            c.get("krankenkasse", DEFAULT_MUSTER13_BOXES["krankenkasse"]),
            kassen_name,
            font=font_reg,
            fill=ink_color,
        )

        # 2. Name des Versicherten
        nachname = beleg.get("nachname", "")
        vorname = beleg.get("vorname", "")
        full_name = f"{nachname}, {vorname}".strip(", ")
        self._draw_text_in_box(
            draw,
            c.get("versicherter_name", DEFAULT_MUSTER13_BOXES["versicherter_name"]),
            full_name or "-",
            font=font_bold,
            fill=ink_color,
        )

        # 3. Geburtsdatum (geb. am)
        geb_raw = str(beleg.get("geburtstag", ""))
        geb_fmt = format_date_german(geb_raw)
        self._draw_text_in_box(
            draw,
            c.get("geb_datum", DEFAULT_MUSTER13_BOXES["geb_datum"]),
            geb_fmt or "-",
            font=font_reg,
            fill=ink_color,
        )

        # 4. Kostenträgerkennung / Versicherten-Nr. / Status
        ik_str = str(beleg.get("kostentraeger_ik") or beleg.get("krankenkasse_ik") or beleg.get("ik", ""))
        self._draw_text_in_box(
            draw, c.get("ik", DEFAULT_MUSTER13_BOXES["ik"]), ik_str or "-", font=font_reg, fill=ink_color
        )
        vers_nr = str(beleg.get("versichertennummer", ""))
        self._draw_text_in_box(
            draw, c.get("vers_nr", DEFAULT_MUSTER13_BOXES["vers_nr"]), vers_nr or "-", font=font_reg, fill=ink_color
        )
        status = str(beleg.get("versichertenstatus", ""))
        self._draw_text_in_box(
            draw, c.get("status", DEFAULT_MUSTER13_BOXES["status"]), status or "-", font=font_reg, fill=ink_color
        )

        # 5. BSNR / LANR / Verordnungsdatum
        bsnr = str(beleg.get("bsnr", ""))
        self._draw_text_in_box(
            draw, c.get("bsnr", DEFAULT_MUSTER13_BOXES["bsnr"]), bsnr or "-", font=font_reg, fill=ink_color
        )
        lanr = str(beleg.get("lanr", ""))
        self._draw_text_in_box(
            draw, c.get("lanr", DEFAULT_MUSTER13_BOXES["lanr"]), lanr or "-", font=font_reg, fill=ink_color
        )
        v_datum_raw = str(beleg.get("verordnungsdatum", ""))
        v_datum_fmt = format_date_german(v_datum_raw)
        self._draw_text_in_box(
            draw,
            c.get("verordnungsdatum", DEFAULT_MUSTER13_BOXES["verordnungsdatum"]),
            v_datum_fmt or "-",
            font=font_reg,
            fill=ink_color,
        )

        # 6. Checkboxen Zuzahlung / Unfallfolgen / BVG
        zkz = str(beleg.get("zuzahlungskennzeichen", "2"))
        if zkz in ["0", "1"]:
            self._draw_checkbox(
                draw, c.get("zuz_frei", DEFAULT_MUSTER13_BOXES["zuz_frei"]), "X", fill=check_color, font=font_bold
            )
        else:
            self._draw_checkbox(
                draw, c.get("zuz_pflicht", DEFAULT_MUSTER13_BOXES["zuz_pflicht"]), "X", fill=check_color, font=font_bold
            )

        if beleg.get("unfallfolgen"):
            self._draw_checkbox(
                draw, c.get("unfallfolgen", DEFAULT_MUSTER13_BOXES["unfallfolgen"]), "X", fill=check_color, font=font_bold
            )
        if beleg.get("bvg"):
            self._draw_checkbox(
                draw, c.get("bvg", DEFAULT_MUSTER13_BOXES["bvg"]), "X", fill=check_color, font=font_bold
            )

        # 7. Checkboxen Verordnungsart
        v_art = str(beleg.get("verordnungsart", "1"))
        if v_art == "1":
            self._draw_checkbox(
                draw, c.get("v_art_erst", DEFAULT_MUSTER13_BOXES["v_art_erst"]), "X", fill=check_color, font=font_bold
            )
        elif v_art == "2":
            self._draw_checkbox(
                draw, c.get("v_art_folge", DEFAULT_MUSTER13_BOXES["v_art_folge"]), "X", fill=check_color, font=font_bold
            )

        # 8. Checkboxen Heilmittelbereich
        hm_bereich = str(beleg.get("heilmittelbereich", ""))
        if "54001" in str(beleg.get("positions", [])) or hm_bereich == "2":
            self._draw_checkbox(
                draw, c.get("hm_ergo", DEFAULT_MUSTER13_BOXES["hm_ergo"]), "X", fill=check_color, font=font_bold
            )
        elif "40101" in str(beleg.get("positions", [])) or hm_bereich == "3":
            self._draw_checkbox(
                draw, c.get("hm_logo", DEFAULT_MUSTER13_BOXES["hm_logo"]), "X", fill=check_color, font=font_bold
            )
        else:
            self._draw_checkbox(
                draw, c.get("hm_physio", DEFAULT_MUSTER13_BOXES["hm_physio"]), "X", fill=check_color, font=font_bold
            )

        # 9. Diagnosen & Leitsymptomatik
        diag = str(beleg.get("diagnosegruppe", ""))
        icd = str(beleg.get("icd10", ""))
        leitsymp = str(beleg.get("leitsymptomatik", ""))

        # Diagnose im ersten Feld der Tabelle zentriert
        diag_text = f"{icd} {leitsymp}".strip() if icd or leitsymp else ""
        box_diag = c.get("diag_freitext_row1", c.get("diag_freitext", DEFAULT_MUSTER13_BOXES["diag_freitext_row1"]))
        self._draw_text_in_box(
            draw,
            box_diag,
            diag_text,
            font=font_reg,
            fill=ink_color,
        )
        self._draw_text_in_box(
            draw,
            c.get("diag_gruppe", DEFAULT_MUSTER13_BOXES["diag_gruppe"]),
            diag or "-",
            font=font_bold,
            fill=ink_color,
            align_h="center",
        )
        box_icd = c.get("icd10_row1", c.get("icd10", DEFAULT_MUSTER13_BOXES["icd10_row1"]))
        self._draw_text_in_box(
            draw,
            box_icd,
            icd or "-",
            font=font_reg,
            fill=ink_color,
        )

        # Leitsymptomatik Checkboxen a, b, c
        ls_kombi = str(beleg.get("leitsymptomatik_kombi", "a")).lower()
        if "a" in ls_kombi:
            self._draw_checkbox(
                draw, c.get("leitsymp_a", DEFAULT_MUSTER13_BOXES["leitsymp_a"]), "X", fill=check_color, font=font_bold
            )
        if "b" in ls_kombi:
            self._draw_checkbox(
                draw, c.get("leitsymp_b", DEFAULT_MUSTER13_BOXES["leitsymp_b"]), "X", fill=check_color, font=font_bold
            )
        if "c" in ls_kombi:
            self._draw_checkbox(
                draw, c.get("leitsymp_c", DEFAULT_MUSTER13_BOXES["leitsymp_c"]), "X", fill=check_color, font=font_bold
            )

        if leitsymp:
            self._draw_text_in_box(
                draw,
                c.get("leitsymp_freitext", DEFAULT_MUSTER13_BOXES["leitsymp_freitext"]),
                leitsymp,
                font=font_reg,
                fill=ink_color,
            )

        # 10. Therapieoptionen (Therapiebericht, Hausbesuch, Therapiefrequenz, Therapieziele)
        tb_req = beleg.get("therapiebericht", True)
        if tb_req:
            self._draw_checkbox(
                draw,
                c.get("therapiebericht", DEFAULT_MUSTER13_BOXES["therapiebericht"]),
                "X",
                fill=check_color,
                font=font_bold,
            )

        hb_req = beleg.get("hausbesuch", False)
        if hb_req:
            self._draw_checkbox(
                draw,
                c.get("hausbesuch_ja", DEFAULT_MUSTER13_BOXES["hausbesuch_ja"]),
                "X",
                fill=check_color,
                font=font_bold,
            )
        else:
            self._draw_checkbox(
                draw,
                c.get("hausbesuch_nein", DEFAULT_MUSTER13_BOXES["hausbesuch_nein"]),
                "X",
                fill=check_color,
                font=font_bold,
            )

        frequenz = str(beleg.get("therapiefrequenz", "1-2x wöchentlich"))
        self._draw_text_in_box(
            draw,
            c.get("therapiefrequenz", DEFAULT_MUSTER13_BOXES["therapiefrequenz"]),
            frequenz,
            font=font_reg,
            fill=ink_color,
        )

        ziele = str(beleg.get("therapieziele", ""))
        if ziele:
            self._draw_text_in_box(
                draw,
                c.get("therapieziele", DEFAULT_MUSTER13_BOXES["therapieziele"]),
                ziele,
                font=font_reg,
                fill=ink_color,
            )

        # 11. Heilmittel Tabelle
        # Aufteilung in Vorrangige Heilmittel (Zeilen 1 bis 3) und Ergänzende Heilmittel
        positions = beleg.get("positions", [])
        ergaenzend_codes = {"29901", "29701", "29801", "29802", "29803"}

        vorrangig_pos = []
        ergaenzend_pos = []
        for p in positions:
            p_code = str(p.get("code", "")).strip()
            if p_code in ergaenzend_codes:
                ergaenzend_pos.append(p)
            else:
                vorrangig_pos.append(p)

        if not vorrangig_pos and ergaenzend_pos:
            vorrangig_pos.append(ergaenzend_pos.pop(0))

        code_labels = {
            "20501": "Krankengymnastik (Einzelbehandlung)",
            "29901": "Wärmetherapie / Fango",
            "54001": "Motorisch-funktionelle Behandlung",
            "40101": "Sprachtherapie (Einzelbehandlung 45 Min)",
            "59702": "Ergotherapeutische Schienenbehandlung",
        }

        # 1. Vorrangige Heilmittel in Zeile 1, Zeile 2, Zeile 3
        vorrangig_rows = [
            (c.get("hm_pos1_row1_label", DEFAULT_MUSTER13_BOXES["hm_pos1_row1_label"]),
             c.get("hm_pos1_row1_anzahl", DEFAULT_MUSTER13_BOXES["hm_pos1_row1_anzahl"])),
            (c.get("hm_pos1_row2_label", DEFAULT_MUSTER13_BOXES["hm_pos1_row2_label"]),
             c.get("hm_pos1_row2_anzahl", DEFAULT_MUSTER13_BOXES["hm_pos1_row2_anzahl"])),
            (c.get("hm_pos1_row3_label", DEFAULT_MUSTER13_BOXES["hm_pos1_row3_label"]),
             c.get("hm_pos1_row3_anzahl", DEFAULT_MUSTER13_BOXES["hm_pos1_row3_anzahl"])),
        ]

        for idx, pos in enumerate(vorrangig_pos[:3]):
            code = str(pos.get("code", ""))
            anzahl = pos.get("anzahl", 0.0)
            label = code_labels.get(code, f"Heilmittel Pos. {code}" if code else f"Behandlung ({pos.get('tag', 'EHE')})")
            lbl_box, anz_box = vorrangig_rows[idx]
            self._draw_text_in_box(draw, lbl_box, label, font=font_bold, fill=ink_color)
            self._draw_text_in_box(draw, anz_box, f"{anzahl:g}", font=font_bold, fill=ink_color, align_h="center")

        # 2. Ergänzendes Heilmittel (falls vorhanden)
        if ergaenzend_pos:
            pos_erg = ergaenzend_pos[0]
            code_erg = str(pos_erg.get("code", ""))
            anz_erg = pos_erg.get("anzahl", 0.0)
            label_erg = code_labels.get(code_erg, f"Heilmittel Pos. {code_erg}" if code_erg else "Ergänzendes Heilmittel")
            lbl_erg_box = c.get("hm_pos2_label", DEFAULT_MUSTER13_BOXES["hm_pos2_label"])
            anz_erg_box = c.get("hm_pos2_anzahl", DEFAULT_MUSTER13_BOXES["hm_pos2_anzahl"])
            self._draw_text_in_box(draw, lbl_erg_box, label_erg, font=font_bold, fill=ink_color)
            self._draw_text_in_box(draw, anz_erg_box, f"{anz_erg:g}", font=font_bold, fill=ink_color, align_h="center")

        # 12. Fusszeile (IK des Leistungserbringers, Arztstempel & Unterschrift)
        ik_le = str(beleg.get("leistungserbringer_ik") or beleg.get("ik_leistungserbringer", beleg.get("ik", "")))
        dividers_le = [462, 492, 522, 553, 584, 614, 645, 675, 706, 736]
        self._draw_comb_digits(
            draw,
            dividers_le,
            y=1174,
            h=38,
            text=ik_le,
            font=font_bold,
            fill=ink_color,
        )

        # Arztstempel zentriert in den oberen 60% des Feldes
        # Arztunterschrift zentriert in den unteren 40% des Feldes (in Handschrift-Schriftart)
        box_arzt = c.get("arztstempel", DEFAULT_MUSTER13_BOXES["arztstempel"])
        bx, by, bw, bh = box_arzt
        h_stamp = int(bh * 0.60)
        h_sig = bh - h_stamp
        box_stamp = (bx, by, bw, h_stamp)
        box_sig = (bx, by + h_stamp, bw, h_sig)

        bsnr = str(beleg.get("bsnr", "")).strip()
        lanr = str(beleg.get("lanr", "")).strip()
        meta_stamp = f"BSNR: {bsnr} • LANR: {lanr}" if (bsnr or lanr) else "Musterstadt"
        stamp_text = f"Praxis Dr. med. Musterarzt\nFacharzt für Allgemeinmedizin\n{meta_stamp}"
        font_stamp = self._get_stamp_font(13)
        self._draw_text_in_box(
            draw,
            box_stamp,
            stamp_text,
            font=font_stamp,
            fill=(20, 30, 110),
            align_h="center",
        )

        font_hand = self._get_handwriting_font(22)
        self._draw_text_in_box(
            draw,
            box_sig,
            "Dr. Musterarzt",
            font=font_hand,
            fill=(10, 20, 90),
            align_h="center",
        )

        return base_img

    def _render_back_side(
        self, beleg: Dict[str, Any], font_reg, font_bold, font_small
    ) -> Image.Image:
        """Rendert die Rückseite des Muster 13 Verordnungsblatts (Behandlungsbestätigung & Abrechnungsdaten)."""
        if os.path.exists(self.path_back_asset):
            base_img = Image.open(self.path_back_asset).convert("RGB")
        else:
            base_img = Image.new("RGB", (1280, 1280), color=(245, 245, 220))

        draw = ImageDraw.Draw(base_img)
        ink_color = (5, 20, 90)

        # 1. Behandlungsbestätigungs-Tabelle (20 Zeilen, y=203, 236, 269... bis y=830)
        # Spalten laut Vordruck:
        # Col 1 (Datum): x=235, w=143
        # Col 2 (Maßnahmen / erhaltene Heilmittel): x=379, w=327
        # Col 3 (Leistungserbringer): x=708, w=136
        # Col 4 (Unterschrift des Versicherten): x=846, w=196
        positions = beleg.get("positions", [])
        nachname = str(beleg.get("nachname", "Versicherter")).strip()
        vorname = str(beleg.get("vorname", "")).strip()
        patient_sig = f"{vorname[0]}. {nachname}" if vorname else nachname
        if not patient_sig:
            patient_sig = "M. Mustermann"

        code_labels = {
            "20501": "Krankengymnastik (Einzelbehandlung)",
            "29901": "Wärmetherapie / Fango",
            "54001": "Motorisch-funktionelle Behandlung",
            "40101": "Sprachtherapie (Einzelbehandlung 45 Min)",
            "59702": "Ergotherapeutische Schienenbehandlung",
        }

        font_hand_patient = self._get_handwriting_font(18)

        row_y_start = 170
        row_height = 33
        max_rows = 20
        row_idx = 0

        for pos in positions:
            code = str(pos.get("code", "")).strip()
            label = code_labels.get(code, f"Heilmittel Pos. {code}" if code else f"Behandlung ({pos.get('tag', 'EHE')})")
            anzahl = int(pos.get("anzahl", 1))
            raw_datum = str(pos.get("datum", "")).strip()
            datum_base = format_date_german(raw_datum) if raw_datum else ""

            parsed_dt = None
            if len(raw_datum) == 8 and raw_datum.isdigit():
                try:
                    parsed_dt = datetime.strptime(raw_datum, "%Y%m%d")
                except Exception:
                    parsed_dt = None

            for i_sess in range(anzahl):
                if row_idx >= max_rows:
                    break
                y_r = row_y_start + row_idx * row_height

                if parsed_dt:
                    # 2-3 Tage Abstand zwischen Behandlungsterminen
                    sess_dt = parsed_dt + timedelta(days=i_sess * 3 + (1 if i_sess % 2 == 1 else 0))
                    cur_date = sess_dt.strftime("%d.%m.%Y")
                else:
                    cur_date = datum_base or format_date_german(str(beleg.get("verordnungsdatum", "")))

                # 1. Datum zentriert
                self._draw_text_in_box(
                    draw,
                    (235, y_r, 143, row_height),
                    cur_date or "-",
                    font=font_reg,
                    fill=ink_color,
                    align_h="center",
                )

                # 2. Maßnahmen: Titel der Behandlung, angepasst & zentriert
                self._draw_fitted_text(
                    base_img,
                    (379, y_r, 327, row_height),
                    label,
                    font=font_reg,
                    fill=ink_color,
                    align_h="center",
                )

                # 3. Leistungserbringer zentriert (Kürzel des Therapeuten)
                self._draw_text_in_box(
                    draw,
                    (708, y_r, 136, row_height),
                    "TH",
                    font=font_reg,
                    fill=ink_color,
                    align_h="center",
                )

                # 4. Unterschrift des Versicherten in Handschrift-Font zentriert
                self._draw_text_in_box(
                    draw,
                    (846, y_r, 196, row_height),
                    patient_sig,
                    font=font_hand_patient,
                    fill=(10, 20, 80),
                    align_h="center",
                )

                row_idx += 1

        # 2. Abrechnungsdaten des Heilmittelerbringers (unterer Block)
        # Rechnungsnummer (18 Kästchen bei y=907, h=38)
        rechnungsnr = str(beleg.get("rechnungsnummer", "")).strip()
        if rechnungsnr:
            dividers_rech = [234, 264, 295, 325, 356, 386, 417, 448, 478, 509, 539, 570, 601, 631, 661, 692, 723, 753, 784]
            self._draw_comb_digits(
                draw,
                dividers_rech,
                y=907,
                h=38,
                text=rechnungsnr,
                font=font_bold,
                fill=ink_color,
            )

        # IK des Leistungserbringers (9 Kästchen bei y=958, h=38)
        ik_le = str(beleg.get("leistungserbringer_ik") or beleg.get("ik_leistungserbringer", beleg.get("ik", ""))).strip()
        if ik_le:
            dividers_ik_back = [234, 264, 295, 325, 356, 386, 417, 448, 478, 509]
            self._draw_comb_digits(
                draw,
                dividers_ik_back,
                y=958,
                h=38,
                text=ik_le,
                font=font_bold,
                fill=ink_color,
            )

        # Belegnummer (10 Kästchen bei y=958, h=38)
        belegnr = str(beleg.get("belegnr", "")).strip()
        if belegnr:
            dividers_beleg = [539, 570, 601, 631, 661, 692, 723, 753, 784, 814, 845]
            self._draw_comb_digits(
                draw,
                dividers_beleg,
                y=958,
                h=38,
                text=belegnr,
                font=font_bold,
                fill=ink_color,
            )

        # Stempel/Unterschrift des Leistungserbringers (Rechte Box bei x=746, y=1021, w=297, h=191)
        stamp_le_box = (746, 1021, 297, 114)
        sig_le_box = (746, 1135, 297, 75)

        therapie_praxis = (
            f"Physiotherapie & Heilmittelpraxis\nZugelassene Praxis für Heilmittel\nIK: {ik_le}"
            if ik_le
            else "Physiotherapie & Heilmittelpraxis\nZugelassene Praxis für Heilmittel"
        )
        font_stamp_le = self._get_stamp_font(13)
        self._draw_text_in_box(
            draw,
            stamp_le_box,
            therapie_praxis,
            font=font_stamp_le,
            fill=(20, 30, 110),
            align_h="center",
        )

        font_sig_le = self._get_handwriting_font(20)
        self._draw_text_in_box(
            draw,
            sig_le_box,
            "Therapeut / Praxisleitung",
            font=font_sig_le,
            fill=(10, 20, 90),
            align_h="center",
        )

        return base_img

    def _update_canvas_display(self):
        """Aktualisiert die Canvas-Anzeige unter Berücksichtigung des gewählten Zoom-Modus."""
        if not self.current_rendered_image:
            self.canvas.delete("all")
            return

        img = self.current_rendered_image

        canvas_w = max(self.canvas.winfo_width(), 300)
        canvas_h = max(self.canvas.winfo_height(), 300)

        if self.zoom_mode == "fit":
            scale_w = canvas_w / img.width
            scale_h = canvas_h / img.height
            scale = min(scale_w, scale_h)
        elif self.zoom_mode == "100":
            scale = 1.0
        else:
            # Custom Zoom (Strg + Mausrad)
            scale_w = canvas_w / img.width
            scale_h = canvas_h / img.height
            base_scale = min(scale_w, scale_h)
            scale = base_scale * self.zoom_factor

        new_w = max(int(img.width * scale), 20)
        new_h = max(int(img.height * scale), 20)

        display_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.photo_image = ImageTk.PhotoImage(display_img)

        self.canvas.delete("all")

        pos_x = max(0, (canvas_w - new_w) // 2) if new_w < canvas_w else 0
        pos_y = max(0, (canvas_h - new_h) // 2) if new_h < canvas_h else 0

        self.canvas.create_image(pos_x, pos_y, image=self.photo_image, anchor="nw")
        self.canvas.config(scrollregion=(0, 0, max(new_w, canvas_w), max(new_h, canvas_h)))

        # Button Styling aktualisieren
        if self.active_side == "front":
            self.btn_side_front.state(["disabled"])
            self.btn_side_back.state(["!disabled"])
        else:
            self.btn_side_front.state(["!disabled"])
            self.btn_side_back.state(["disabled"])

    def export_prescription(self, target_path: Optional[str] = None) -> Optional[str]:
        """
        Exportiert das Verordnungsblatt als mehrseitiges PDF oder Bild (PNG/JPEG).
        """
        if not self.current_beleg:
            messagebox.showwarning(
                "Kein Beleg gewählt",
                "Bitte wähle zuerst einen Beleg aus, um die Verordnung zu exportieren.",
            )
            return None

        belegnr = str(self.current_beleg.get("belegnr", "Unbekannt"))

        if not target_path:
            from tkinter import filedialog
            init_file = f"Muster13_Beleg_{belegnr}.pdf"
            filetypes = [
                ("PDF-Dokument (*.pdf)", "*.pdf"),
                ("PNG-Bild (*.png)", "*.png"),
                ("JPEG-Bild (*.jpg)", "*.jpg"),
                ("Alle Dateien (*.*)", "*.*"),
            ]
            target_path = filedialog.asksaveasfilename(
                title="Verordnung exportieren",
                initialfile=init_file,
                defaultextension=".pdf",
                filetypes=filetypes,
            )
            if not target_path:
                return None

        try:
            font_regular, font_bold, font_small = self._get_fonts()
            img_front = self._render_front_side(self.current_beleg, font_regular, font_bold, font_small).convert("RGB")
            img_back = self._render_back_side(self.current_beleg, font_regular, font_bold, font_small).convert("RGB")

            lower_path = target_path.lower()
            if lower_path.endswith(".pdf"):
                img_front.save(
                    target_path, "PDF", resolution=150.0, save_all=True, append_images=[img_back]
                )
            elif lower_path.endswith(".png") or lower_path.endswith(".jpg") or lower_path.endswith(".jpeg"):
                base, ext = os.path.splitext(target_path)
                front_path = f"{base}_vorderseite{ext}"
                back_path = f"{base}_rueckseite{ext}"
                img_front.save(front_path)
                img_back.save(back_path)
                target_path = f"{front_path}, {back_path}"
            else:
                target_path = f"{target_path}.pdf"
                img_front.save(
                    target_path, "PDF", resolution=150.0, save_all=True, append_images=[img_back]
                )

            messagebox.showinfo(
                "Export erfolgreich",
                f"Die Verordnung zu Beleg-Nr. {belegnr} wurde erfolgreich exportiert:\n{target_path}",
            )
            return target_path
        except Exception as err:
            messagebox.showerror("Export-Fehler", f"Fehler beim Exportieren der Verordnung:\n{err}")
            return None

