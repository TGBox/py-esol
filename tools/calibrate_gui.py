#!/usr/bin/env python3
"""
Interaktiver grafischer Feld-Kalibrator für Muster 13 Verordnungsblätter.
Erlaubt das Aufziehen von Rechtecken mit der Maus in Originalgröße (scrollbar)
und speichert die relativen/absoluten Koordinaten in assets/muster13_coords.json.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List
from PIL import Image, ImageTk

# Project root setup
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Exakt korrigierte Feld-Definitionen für Muster 13
FIELDS_TO_CALIBRATE = [
    # 1. Personalien- & Statusfeld (oben links)
    {"id": 1, "key": "zuz_frei", "label": "1 — Zuzahlung gebührenfrei [X]"},
    {"id": 2, "key": "zuz_pflicht", "label": "2 — Zuzahlung gebührenpflichtig [X]"},
    {"id": 3, "key": "unfallfolgen", "label": "3 — Unfallfolgen [X]"},
    {"id": 4, "key": "bvg", "label": "4 — BVG [X]"},
    {"id": 5, "key": "krankenkasse", "label": "5 — Krankenkasse / Kostenträger Name"},
    {"id": 6, "key": "versicherter_name", "label": "6 — Name, Vorname des Versicherten"},
    {"id": 7, "key": "geb_datum", "label": "7 — Geburtsdatum (geb. am)"},
    {"id": 8, "key": "ik", "label": "8 — Kostenträgerkennung (IK)"},
    {"id": 9, "key": "vers_nr", "label": "9 — Versicherten-Nr."},
    {"id": 10, "key": "status", "label": "10 — Status"},
    {"id": 11, "key": "bsnr", "label": "11 — Betriebsstätten-Nr. (BSNR)"},
    {"id": 12, "key": "lanr", "label": "12 — Arzt-Nr. (LANR)"},
    {"id": 13, "key": "verordnungsdatum", "label": "13 — Datum (Verordnungsdatum)"},

    # 2. Verordnungsart & Heilmittelbereich (oben rechts)
    {"id": 14, "key": "v_art_erst", "label": "14 — Verordnungsart Erstverordnung [X]"},
    {"id": 15, "key": "v_art_folge", "label": "15 — Verordnungsart Folgeverordnung [X]"},
    {"id": 16, "key": "hm_physio", "label": "16 — Heilmittelbereich Physiotherapie [X]"},
    {"id": 17, "key": "hm_podo", "label": "17 — Heilmittelbereich Podologie [X]"},
    {"id": 18, "key": "hm_logo", "label": "18 — Heilmittelbereich Logopädie [X]"},
    {"id": 19, "key": "hm_ergo", "label": "19 — Heilmittelbereich Ergotherapie [X]"},
    {"id": 20, "key": "hm_ernaehrung", "label": "20 — Heilmittelbereich Ernährungstherapie [X]"},

    # 3. Diagnosen & Leitsymptomatik
    {"id": 21, "key": "diag_freitext", "label": "21 — Behandlungsrelevante Diagnose(n)"},
    {"id": 22, "key": "diag_gruppe", "label": "22 — Diagnosegruppe (z.B. EN1)"},
    {"id": 23, "key": "icd10", "label": "23 — ICD-10 Code (z.B. G35)"},
    {"id": 24, "key": "leitsymp_a", "label": "24 — Leitsymptomatik a [X]"},
    {"id": 25, "key": "leitsymp_b", "label": "25 — Leitsymptomatik b [X]"},
    {"id": 26, "key": "leitsymp_c", "label": "26 — Leitsymptomatik c [X]"},
    {"id": 27, "key": "leitsymp_patientenindividuell", "label": "27 — Patientenindividuelle Leitsymptomatik [X]"},
    {"id": 28, "key": "leitsymp_freitext", "label": "28 — Leitsymptomatik Freitext-Zeile"},

    # 4. Therapieoptionen, Frequenz & Ziele
    {"id": 29, "key": "therapiebericht", "label": "29 — Therapiebericht [X]"},
    {"id": 30, "key": "hausbesuch_ja", "label": "30 — Hausbesuch ja [X]"},
    {"id": 31, "key": "hausbesuch_nein", "label": "31 — Hausbesuch nein [X]"},
    {"id": 32, "key": "therapiefrequenz", "label": "32 — Therapiefrequenz (z.B. 1-2x wöchentlich)"},
    {"id": 33, "key": "therapieziele", "label": "33 — ggf. Therapieziele Freitext"},

    # 5. Heilmittel Tabelle
    {"id": 34, "key": "hm_pos1_label", "label": "34 — Heilmittel Pos 1 Bezeichnung"},
    {"id": 35, "key": "hm_pos1_anzahl", "label": "35 — Heilmittel Pos 1 Behandlungseinheiten"},
    {"id": 36, "key": "hm_pos2_label", "label": "36 — Heilmittel Pos 2 Bezeichnung"},
    {"id": 37, "key": "hm_pos2_anzahl", "label": "37 — Heilmittel Pos 2 Behandlungseinheiten"},

    # 6. Fusszeile / Leistungserbringer & Arztstempel
    {"id": 38, "key": "ik_leistungserbringer", "label": "38 — IK des Leistungserbringers (unten links)"},
    {"id": 39, "key": "arztstempel", "label": "39 — Vertragsarztstempel"},
    {"id": 40, "key": "arztunterschrift", "label": "40 — Unterschrift des Arztes"},
]

class Muster13CalibratorDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget = None):
        if parent:
            super().__init__(parent)
        else:
            self.root = tk.Tk()
            self.root.title("Muster 13 Interaktiver Feld-Kalibrator")
            self.root.geometry("1150x880")
            super().__init__(self.root)

        self.title("🎯 Interaktiver Muster 13 Feld-Kalibrator")
        self.geometry("1150x880")

        self.asset_path = os.path.join(project_root, "assets", "Muster13_1280x1280.jpg")
        self.json_out_path = os.path.join(project_root, "assets", "muster13_coords.json")

        self.current_step_idx = 0
        self.recorded_coords: Dict[str, Dict[str, Any]] = {}
        
        # Rubberband Status
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.temp_rect_id = None
        self.drawn_rectangles: Dict[int, List[int]] = {}  # step_idx -> canvas items

        self._setup_ui()
        self._load_image()
        self._load_existing_coords()
        self._update_prompt_banner()

    def _setup_ui(self):
        # Top Prompt Banner
        self.banner_frame = ttk.Frame(self, padding=10)
        self.banner_frame.pack(fill="x", side="top")

        self.lbl_step_counter = ttk.Label(
            self.banner_frame,
            text=f"Schritt 1 / {len(FIELDS_TO_CALIBRATE)}",
            font=("Segoe UI", 10, "bold"),
            foreground="#0275d8",
        )
        self.lbl_step_counter.pack(side="top", anchor="w")

        self.lbl_prompt = ttk.Label(
            self.banner_frame,
            text="",
            font=("Segoe UI", 12, "bold"),
            foreground="#d9534f",
        )
        self.lbl_prompt.pack(side="top", anchor="w", pady=(2, 6))

        # Instructions Subtitle
        ttk.Label(
            self.banner_frame,
            text="👉 Ziehe mit gedrückter linker Maustaste ein Rechteck über das oben beschriebene Feld im Vordruck.",
            font=("Segoe UI", 9, "italic"),
        ).pack(side="top", anchor="w")

        # Toolbar Control Buttons
        btn_bar = ttk.Frame(self.banner_frame)
        btn_bar.pack(fill="x", side="top", pady=(8, 0))

        ttk.Button(btn_bar, text="◀ Vorheriges Feld", command=self._prev_step).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="▶ Überspringen", command=self._next_step).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="🔄 Rückgängig", command=self._undo_current).pack(side="left", padx=4)
        ttk.Button(btn_bar, text="💾 Speichern & Schließen", command=self._save_and_close).pack(side="right", padx=4)

        # Scrollable Canvas
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.canvas = tk.Canvas(canvas_frame, bg="#2b2b2b", highlightthickness=0)
        self.h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        self.v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.v_scroll.pack(side="right", fill="y")
        self.h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Mouse Bindings on Canvas
        self.canvas.bind("<ButtonPress-1>", self._on_button_press)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_button_release)

    def _load_image(self):
        if os.path.exists(self.asset_path):
            self.pil_img = Image.open(self.asset_path).convert("RGB")
        else:
            self.pil_img = Image.new("RGB", (1280, 1280), color=(240, 240, 220))

        self.img_w, self.img_h = self.pil_img.size
        self.photo_img = ImageTk.PhotoImage(self.pil_img)
        self.canvas.create_image(0, 0, image=self.photo_img, anchor="nw")
        self.canvas.config(scrollregion=(0, 0, self.img_w, self.img_h))

    def _load_existing_coords(self):
        """Bereits gespeicherte Koordinaten aus muster13_coords.json vorab auf dem Canvas einzeichnen."""
        if not os.path.exists(self.json_out_path):
            return
        try:
            with open(self.json_out_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                fields = data.get("fields", {})
                self.recorded_coords = fields
                
                for idx, field in enumerate(FIELDS_TO_CALIBRATE):
                    key = field["key"]
                    if key in fields:
                        c = fields[key]
                        x1, y1, w, h = c["abs_x"], c["abs_y"], c["abs_w"], c["abs_h"]
                        x2, y2 = x1 + w, y1 + h

                        rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00e676", width=3)
                        bg_id = self.canvas.create_rectangle(x1, y1 - 22, x1 + 35, y1, fill="#00e676", outline="#00e676")
                        text_id = self.canvas.create_text(x1 + 17, y1 - 11, text=str(field["id"]), fill="#000000", font=("Segoe UI", 10, "bold"))
                        self.drawn_rectangles[idx] = [rect_id, bg_id, text_id]
        except Exception as e:
            print(f"Fehler beim Laden existierender Koordinaten: {e}")

    def _update_prompt_banner(self):
        if 0 <= self.current_step_idx < len(FIELDS_TO_CALIBRATE):
            field = FIELDS_TO_CALIBRATE[self.current_step_idx]
            self.lbl_step_counter.config(text=f"Feld {self.current_step_idx + 1} von {len(FIELDS_TO_CALIBRATE)}")
            self.lbl_prompt.config(text=f"Bitte markiere Feld: {field['label']}")
        else:
            self.lbl_step_counter.config(text="Alle Felder kalibriert!")
            self.lbl_prompt.config(text="🎉 Hervorragend! Klicke auf 'Speichern & Schließen' zum Übernehmen.")

    def _on_button_press(self, event):
        self.drag_start_x = int(self.canvas.canvasx(event.x))
        self.drag_start_y = int(self.canvas.canvasy(event.y))

        if self.temp_rect_id:
            self.canvas.delete(self.temp_rect_id)
        self.temp_rect_id = self.canvas.create_rectangle(
            self.drag_start_x, self.drag_start_y, self.drag_start_x, self.drag_start_y, outline="#ff0000", width=2
        )

    def _on_mouse_drag(self, event):
        cur_x = int(self.canvas.canvasx(event.x))
        cur_y = int(self.canvas.canvasy(event.y))
        if self.temp_rect_id:
            self.canvas.coords(self.temp_rect_id, self.drag_start_x, self.drag_start_y, cur_x, cur_y)

    def _on_button_release(self, event):
        end_x = int(self.canvas.canvasx(event.x))
        end_y = int(self.canvas.canvasy(event.y))

        if self.temp_rect_id:
            self.canvas.delete(self.temp_rect_id)
            self.temp_rect_id = None

        x1, x2 = min(self.drag_start_x, end_x), max(self.drag_start_x, end_x)
        y1, y2 = min(self.drag_start_y, end_y), max(self.drag_start_y, end_y)

        w = x2 - x1
        h = y2 - y1

        if w < 5 or h < 5:
            return

        if self.current_step_idx < len(FIELDS_TO_CALIBRATE):
            field = FIELDS_TO_CALIBRATE[self.current_step_idx]

            if self.current_step_idx in self.drawn_rectangles:
                for item_id in self.drawn_rectangles[self.current_step_idx]:
                    self.canvas.delete(item_id)

            rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00e676", width=3)
            bg_id = self.canvas.create_rectangle(x1, y1 - 22, x1 + 35, y1, fill="#00e676", outline="#00e676")
            text_id = self.canvas.create_text(x1 + 17, y1 - 11, text=str(field["id"]), fill="#000000", font=("Segoe UI", 10, "bold"))

            self.drawn_rectangles[self.current_step_idx] = [rect_id, bg_id, text_id]

            self.recorded_coords[field["key"]] = {
                "id": field["id"],
                "label": field["label"],
                "abs_x": x1,
                "abs_y": y1,
                "abs_w": w,
                "abs_h": h,
                "rel_x": round(x1 / self.img_w, 4),
                "rel_y": round(y1 / self.img_h, 4),
                "rel_w": round(w / self.img_w, 4),
                "rel_h": round(h / self.img_h, 4),
            }

            self.current_step_idx += 1
            self._update_prompt_banner()

    def _undo_current(self):
        if self.current_step_idx in self.drawn_rectangles:
            for item_id in self.drawn_rectangles[self.current_step_idx]:
                self.canvas.delete(item_id)
            del self.drawn_rectangles[self.current_step_idx]

        field = FIELDS_TO_CALIBRATE[self.current_step_idx] if self.current_step_idx < len(FIELDS_TO_CALIBRATE) else None
        if field and field["key"] in self.recorded_coords:
            del self.recorded_coords[field["key"]]

    def _prev_step(self):
        if self.current_step_idx > 0:
            self.current_step_idx -= 1
            self._update_prompt_banner()

    def _next_step(self):
        if self.current_step_idx < len(FIELDS_TO_CALIBRATE):
            self.current_step_idx += 1
            self._update_prompt_banner()

    def _save_and_close(self):
        if not self.recorded_coords:
            if not messagebox.askyesno("Keine Felder markiert", "Es wurden keine Felder markiert. Trotzdem beenden?"):
                return

        out_data = {
            "image_size": {"width": self.img_w, "height": self.img_h},
            "fields": self.recorded_coords,
        }

        with open(self.json_out_path, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=2, ensure_ascii=False)

        messagebox.showinfo(
            "Kalibrierung Gespeichert",
            f"Erfolgreich {len(self.recorded_coords)} Feld-Positionen in '{self.json_out_path}' gespeichert!\n"
            "Die Muster 13 Vorschau übernimmt diese Koordinaten jetzt automatisch."
        )

        self.destroy()
        if hasattr(self, "root"):
            self.root.destroy()

if __name__ == "__main__":
    dialog = Muster13CalibratorDialog()
    dialog.root.mainloop()
