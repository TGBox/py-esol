"""
ESOL Visuelle Rezept-Vorschau — Fotorealistisches virtuelles Verordnungsblatt (Muster 13/18)
mit Templating auf Basis der Vorlagenbilder in assets/Muster13_1280x1280.jpg (Vorderseite) und
assets/Muster13_2_1280x1280.jpg (Rückseite).
"""

import os
import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageTk

import theme_manager
from support_helper import translate_error
from tools.generate_correction import format_date_german


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

    def _toggle_zoom(self):
        if self.zoom_mode == "fit":
            self.zoom_mode = "100"
            self.btn_zoom.config(text="🔍 100% Zoom")
        else:
            self.zoom_mode = "fit"
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

    def _load_calibrated_coords(self) -> Dict[str, tuple]:
        """Lädt benutzerdefinierte Kalibrierungskoordinaten aus assets/muster13_coords.json."""
        json_path = os.path.join(self.base_dir, "assets", "muster13_coords.json")
        if os.path.exists(json_path):
            try:
                import json
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    fields = data.get("fields", {})
                    return {k: (v["abs_x"], v["abs_y"]) for k, v in fields.items()}
            except Exception:
                pass
        return {}

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
        ik_str = str(beleg.get("ik", ""))
        # 1. Krankenkasse / Kostenträger
        ik_str = str(beleg.get("ik", ""))
        pos_kasse = c.get("krankenkasse", (249, 56))
        draw.text(pos_kasse, f"IK: {ik_str}".strip() if ik_str else "Krankenkasse", fill=ink_color, font=font_reg)

        # 2. Name des Versicherten
        nachname = beleg.get("nachname", "")
        vorname = beleg.get("vorname", "")
        full_name = f"{nachname}, {vorname}".strip(", ")
        pos_name = c.get("versicherter_name", (252, 116))
        draw.text(pos_name, full_name or "-", fill=ink_color, font=font_bold)

        # 3. Geburtsdatum (geb. am)
        geb_raw = str(beleg.get("geburtstag", ""))
        geb_fmt = format_date_german(geb_raw)
        pos_geb = c.get("geb_datum", (588, 151))
        draw.text(pos_geb, geb_fmt or "-", fill=ink_color, font=font_reg)

        # 4. Kostenträgerkennung / Versicherten-Nr. / Status
        pos_ik = c.get("ik", (248, 231))
        draw.text(pos_ik, ik_str or "-", fill=ink_color, font=font_reg)
        vers_nr = str(beleg.get("versichertennummer", ""))
        pos_vnr = c.get("vers_nr", (419, 234))
        draw.text(pos_vnr, vers_nr or "-", fill=ink_color, font=font_reg)
        status = str(beleg.get("versichertenstatus", ""))
        pos_status = c.get("status", (616, 234))
        draw.text(pos_status, status or "-", fill=ink_color, font=font_reg)

        # 5. BSNR / LANR / Verordnungsdatum
        bsnr = str(beleg.get("bsnr", ""))
        pos_bsnr = c.get("bsnr", (250, 285))
        draw.text(pos_bsnr, bsnr or "-", fill=ink_color, font=font_reg)
        lanr = str(beleg.get("lanr", ""))
        pos_lanr = c.get("lanr", (420, 285))
        draw.text(pos_lanr, lanr or "-", fill=ink_color, font=font_reg)
        v_datum_raw = str(beleg.get("verordnungsdatum", ""))
        v_datum_fmt = format_date_german(v_datum_raw)
        pos_vdatum = c.get("verordnungsdatum", (588, 286))
        draw.text(pos_vdatum, v_datum_fmt or "-", fill=ink_color, font=font_reg)

        # 6. Checkboxen Zuzahlung / Unfallfolgen / BVG
        zkz = str(beleg.get("zuzahlungskennzeichen", "2"))
        if zkz in ["0", "1"]:
            draw.text(c.get("zuz_frei", (205, 39)), "X", fill=check_color, font=font_bold)
        else:
            draw.text(c.get("zuz_pflicht", (206, 99)), "X", fill=check_color, font=font_bold)

        if beleg.get("unfallfolgen"):
            draw.text(c.get("unfallfolgen", (207, 158)), "X", fill=check_color, font=font_bold)
        if beleg.get("bvg"):
            draw.text(c.get("bvg", (207, 219)), "X", fill=check_color, font=font_bold)

        # 7. Checkboxen Verordnungsart
        v_art = str(beleg.get("verordnungsart", "1"))
        if v_art == "1":
            draw.text(c.get("v_art_erst", (752, 35)), "X", fill=check_color, font=font_bold)
        elif v_art == "2":
            draw.text(c.get("v_art_folge", (752, 65)), "X", fill=check_color, font=font_bold)

        # 8. Checkboxen Heilmittelbereich
        hm_bereich = str(beleg.get("heilmittelbereich", ""))
        if "54001" in str(beleg.get("positions", [])) or hm_bereich == "2":
            draw.text(c.get("hm_ergo", (753, 212)), "X", fill=check_color, font=font_bold)
        elif "40101" in str(beleg.get("positions", [])) or hm_bereich == "3":
            draw.text(c.get("hm_logo", (752, 175)), "X", fill=check_color, font=font_bold)
        else:
            draw.text(c.get("hm_physio", (752, 100)), "X", fill=check_color, font=font_bold)

        # 9. Diagnosen & Leitsymptomatik
        diag = str(beleg.get("diagnosegruppe", ""))
        icd = str(beleg.get("icd10", ""))
        leitsymp = str(beleg.get("leitsymptomatik", ""))

        pos_diag_frei = c.get("diag_freitext", (416, 363))
        draw.text(pos_diag_frei, f"{icd} {leitsymp}".strip(), fill=ink_color, font=font_reg)

        pos_dgruppe = c.get("diag_gruppe", (339, 441))
        pos_icd = c.get("icd10", (248, 357))

        draw.text(pos_dgruppe, diag or "-", fill=ink_color, font=font_bold)
        draw.text(pos_icd, icd or "-", fill=ink_color, font=font_reg)

        # Leitsymptomatik Checkboxen a, b, c
        ls_kombi = str(beleg.get("leitsymptomatik_kombi", "a")).lower()
        if "a" in ls_kombi:
            draw.text(c.get("leitsymp_a", (629, 443)), "X", fill=check_color, font=font_bold)
        if "b" in ls_kombi:
            draw.text(c.get("leitsymp_b", (691, 443)), "X", fill=check_color, font=font_bold)
        if "c" in ls_kombi:
            draw.text(c.get("leitsymp_c", (754, 442)), "X", fill=check_color, font=font_bold)

        if leitsymp:
            pos_lsymp_frei = c.get("leitsymp_freitext", (246, 499))
            draw.text(pos_lsymp_frei, leitsymp[:48], fill=ink_color, font=font_reg)

        # 10. Therapieoptionen (Therapiebericht, Hausbesuch, Therapiefrequenz, Therapieziele)
        tb_req = beleg.get("therapiebericht", True)
        if tb_req:
            draw.text(c.get("therapiebericht", (247, 824)), "X", fill=check_color, font=font_bold)

        hb_req = beleg.get("hausbesuch", False)
        if hb_req:
            draw.text(c.get("hausbesuch_ja", (569, 826)), "X", fill=check_color, font=font_bold)
        else:
            draw.text(c.get("hausbesuch_nein", (644, 824)), "X", fill=check_color, font=font_bold)

        frequenz = str(beleg.get("therapiefrequenz", "1-2x wöchentlich"))
        draw.text(c.get("therapiefrequenz", (836, 822)), frequenz, fill=ink_color, font=font_reg)

        ziele = str(beleg.get("therapieziele", ""))
        if ziele:
            draw.text(c.get("therapieziele", (247, 947)), ziele[:45], fill=ink_color, font=font_reg)

        # 11. Heilmittel Tabelle
        positions = beleg.get("positions", [])
        pos_hm1_lbl = c.get("hm_pos1_label", (246, 627))
        pos_hm1_anz = c.get("hm_pos1_anzahl", (909, 627))

        pos_hm2_lbl = c.get("hm_pos2_label", (247, 766))
        pos_hm2_anz = c.get("hm_pos2_anzahl", (908, 767))

        y_positions = [pos_hm1_lbl, pos_hm2_lbl]
        anz_positions = [pos_hm1_anz, pos_hm2_anz]

        for idx, pos in enumerate(positions[:2]):
            code = str(pos.get("code", ""))
            anzahl = pos.get("anzahl", 0.0)

            code_labels = {
                "20501": "Krankengymnastik (Einzelbehandlung)",
                "29901": "Wärmetherapie / Fango",
                "54001": "Motorisch-funktionelle Behandlung",
                "40101": "Sprachtherapie (Einzelbehandlung 45 Min)",
                "59702": "Ergotherapeutische Schienenbehandlung",
            }
            label = code_labels.get(code, f"Heilmittel Pos. {code}" if code else f"Behandlung ({pos.get('tag', 'EHE')})")

            draw.text(y_positions[idx], label, fill=ink_color, font=font_bold)
            draw.text(anz_positions[idx], f"{anzahl:g}", fill=ink_color, font=font_bold)

        # 12. Fusszeile (IK des Leistungserbringers, Arztstempel & Unterschrift)
        ik_le = str(beleg.get("ik_leistungserbringer", beleg.get("ik", "")))
        draw.text(c.get("ik_leistungserbringer", (461, 1174)), ik_le, fill=ink_color, font=font_reg)

        if "arztstempel" in c:
            draw.text(c["arztstempel"], "Praxis Dr. med. Musterarzt\nFacharzt für Allgemeinmedizin", fill=(20, 20, 100), font=font_small)

        if "arztunterschrift" in c:
            draw.text(c["arztunterschrift"], "Dr. Musterarzt", fill=(10, 10, 80), font=font_reg)

        return base_img

    def _render_back_side(
        self, beleg: Dict[str, Any], font_reg, font_bold, font_small
    ) -> Image.Image:
        """Rendert die Rückseite des Muster 13 Verordnungsblatts (Abrechnung & Bestätigung)."""
        if os.path.exists(self.path_back_asset):
            base_img = Image.open(self.path_back_asset).convert("RGB")
        else:
            base_img = Image.new("RGB", (1280, 1280), color=(245, 245, 220))

        draw = ImageDraw.Draw(base_img)
        ink_color = (5, 20, 90)

        # Behandlungsbestätigungs-Tabelle (y = 203, 236, 269, 302, 334, 368...)
        positions = beleg.get("positions", [])
        nachname = beleg.get("nachname", "Versicherter")
        vorname = beleg.get("vorname", "")
        patient_label = f"{nachname}, {vorname}".strip(", ")

        row_y_list = [203, 236, 269, 302, 334, 368, 400, 433, 466, 499, 532, 565, 598, 630, 664, 696]
        row_idx = 0

        for pos in positions:
            datum_raw = str(pos.get("datum", ""))
            datum_fmt = format_date_german(datum_raw)
            code = str(pos.get("code", ""))
            anzahl = int(pos.get("anzahl", 1))

            for _ in range(min(anzahl, 6)):
                if row_idx >= len(row_y_list):
                    break
                y_r = row_y_list[row_idx]
                draw.text((270, y_r + 6), datum_fmt or "-", fill=ink_color, font=font_reg)
                draw.text((390, y_r + 6), code or "-", fill=ink_color, font=font_reg)
                draw.text((520, y_r + 6), patient_label[:22], fill=ink_color, font=font_small)
                row_idx += 1

        # Abrechnungstabelle unten (y=935, 968, 1001...)
        y_abr = 935
        for pos in positions[:5]:
            code = str(pos.get("code", ""))
            anz = f"{pos.get('anzahl', 0.0):g}"
            einzel = f"{pos.get('einzelbetrag', 0.0):.2f}".replace(".", ",")
            gesamt = f"{pos.get('gesamtbetrag', 0.0):.2f}".replace(".", ",")
            zuz = f"{pos.get('zuzahlung', 0.0):.2f}".replace(".", ",")

            draw.text((270, y_abr), code or "-", fill=ink_color, font=font_reg)
            draw.text((480, y_abr), anz, fill=ink_color, font=font_reg)
            draw.text((600, y_abr), einzel + " €", fill=ink_color, font=font_reg)
            draw.text((750, y_abr), gesamt + " €", fill=ink_color, font=font_reg)
            draw.text((900, y_abr), zuz + " €", fill=ink_color, font=font_reg)
            y_abr += 33

        # Summenblock unten (y=1185)
        brutto = float(beleg.get("brutto", 0.0))
        tot_zuz = float(beleg.get("total_zuzahlung", 0.0))
        netto = round(brutto - tot_zuz, 2)

        draw.text((300, 1185), f"{brutto:.2f} €".replace(".", ","), fill=ink_color, font=font_bold)
        draw.text((600, 1185), f"{tot_zuz:.2f} €".replace(".", ","), fill=ink_color, font=font_bold)
        draw.text((880, 1185), f"{netto:.2f} €".replace(".", ","), fill=ink_color, font=font_bold)

        return base_img

    def _update_canvas_display(self):
        """Aktualisiert die Canvas-Anzeige unter Berücksichtigung des gewählten Zoom-Modus."""
        if not self.current_rendered_image:
            self.canvas.delete("all")
            return

        img = self.current_rendered_image

        if self.zoom_mode == "fit":
            # An Canvas-Fenstergröße anpassen
            canvas_w = max(self.canvas.winfo_width(), 300)
            canvas_h = max(self.canvas.winfo_height(), 300)

            # Proportionale Skalierung
            scale_w = canvas_w / img.width
            scale_h = canvas_h / img.height
            scale = min(scale_w, scale_h)

            new_w = max(int(img.width * scale), 10)
            new_h = max(int(img.height * scale), 10)

            display_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            # 100% Zoom Originalgröße
            display_img = img

        self.photo_image = ImageTk.PhotoImage(display_img)

        self.canvas.delete("all")
        self.canvas.create_image(
            display_img.width // 2 if self.zoom_mode == "fit" else 0,
            display_img.height // 2 if self.zoom_mode == "fit" else 0,
            image=self.photo_image,
            anchor="center" if self.zoom_mode == "fit" else "nw",
        )

        self.canvas.config(scrollregion=(0, 0, display_img.width, display_img.height))

        # Button Styling aktualisieren
        if self.active_side == "front":
            self.btn_side_front.state(["disabled"])
            self.btn_side_back.state(["!disabled"])
        else:
            self.btn_side_front.state(["!disabled"])
            self.btn_side_back.state(["disabled"])
