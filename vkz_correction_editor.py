import copy
import datetime
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk, simpledialog
from typing import Any, Callable, Dict, List, Optional

import theme_manager

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tools.generate_correction import (
    parse_esol_belege_summary,
    generate_correction_esol,
    generate_correction_file,
    read_esol_file_text,
    format_date_german,
    parse_date_to_iso,
)

# Human-readable labels for each supported VKZ
_VKZ_LABELS: Dict[str, str] = {
    "02": "Nachforderung (VKZ 02)",
    "03": "Zuzahlungsforderung (VKZ 03)",
    "04": "Korrekturrechnung (VKZ 04)",
    "10": "Wiederaufnahme Blankoverordnung (VKZ 10)",
}


class PositionEditDialog(tk.Toplevel):
    """
    Sub-dialog to add or edit an individual billing position (EHE, ENF, EHI, EHK, etc.).
    """

    def __init__(self, parent: tk.Widget, position_data: Optional[Dict[str, Any]] = None, default_tarif_kz: str = ""):
        super().__init__(parent)
        self.title("Leistungsposition bearbeiten" if position_data else "Neue Leistungsposition hinzufügen")
        self.geometry("500x520")
        self.minsize(450, 420)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        theme_manager.apply_theme(self)

        self.result: Optional[Dict[str, Any]] = None
        self.position_data = position_data or {}
        self.default_tarif_kz = default_tarif_kz

        self._setup_ui()

    def _setup_ui(self):
        pad = {"padx": 10, "pady": 6}

        frame = ttk.Frame(self, padding=15)
        frame.pack(fill="both", expand=True)

        # Segment-Typ
        ttk.Label(frame, text="Segment-Typ:").grid(row=0, column=0, sticky="w", **pad)
        self.tag_combo = ttk.Combobox(
            frame, values=["EHE", "ENF", "EHI", "EHK", "EKT", "EHB", "ESP"], state="readonly", width=15
        )
        self.tag_combo.set(self.position_data.get("tag", "EHE"))
        self.tag_combo.grid(row=0, column=1, sticky="w", **pad)

        # Leistungsschlüssel / Code
        ttk.Label(frame, text="Leistungsschlüssel (Code):").grid(row=1, column=0, sticky="w", **pad)
        self.code_entry = ttk.Entry(frame, width=25)
        self.code_entry.insert(0, str(self.position_data.get("code", "")))
        self.code_entry.grid(row=1, column=1, sticky="w", **pad)

        # Tarifkennzeichen
        ttk.Label(frame, text="Tarifkennzeichen (10-stellig):").grid(row=2, column=0, sticky="w", **pad)
        self.tarif_entry = ttk.Entry(frame, width=25)
        tkz = self.position_data.get("tarif_kz") or self.default_tarif_kz
        self.tarif_entry.insert(0, str(tkz))
        self.tarif_entry.grid(row=2, column=1, sticky="w", **pad)

        # Behandlungsdatum (TT.MM.JJJJ)
        ttk.Label(frame, text="Behandlungsdatum (TT.MM.JJJJ):").grid(row=3, column=0, sticky="w", **pad)
        self.datum_entry = ttk.Entry(frame, width=20)
        raw_datum = str(self.position_data.get("datum", datetime.datetime.now().strftime("%Y%m%d")))
        fmt_datum = format_date_german(raw_datum) if raw_datum else ""
        self.datum_entry.insert(0, fmt_datum)
        self.datum_entry.grid(row=3, column=1, sticky="w", **pad)

        # Anzahl
        ttk.Label(frame, text="Anzahl (Menge):").grid(row=4, column=0, sticky="w", **pad)
        self.anzahl_entry = ttk.Entry(frame, width=15)
        self.anzahl_entry.insert(0, f"{self.position_data.get('anzahl', 1.0):g}")
        self.anzahl_entry.grid(row=4, column=1, sticky="w", **pad)

        # Einzelpreis (€)
        ttk.Label(frame, text="Einzelpreis (€):").grid(row=5, column=0, sticky="w", **pad)
        self.einzel_entry = ttk.Entry(frame, width=15)
        einzel_val = self.position_data.get("einzelbetrag", 0.0)
        self.einzel_entry.insert(0, f"{einzel_val:.2f}".replace(".", ","))
        self.einzel_entry.grid(row=5, column=1, sticky="w", **pad)

        # Zuzahlung pro Einheit (€)
        ttk.Label(frame, text="Zuzahlung pro Einheit (€):").grid(row=6, column=0, sticky="w", **pad)
        self.zuz_entry = ttk.Entry(frame, width=15)
        zuz_val = self.position_data.get("zuzahlung", 0.0)
        self.zuz_entry.insert(0, f"{zuz_val:.2f}".replace(".", ","))
        self.zuz_entry.grid(row=6, column=1, sticky="w", **pad)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20, sticky="e")

        ttk.Button(btn_frame, text="Abbrechen", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Speichern", command=self._save).pack(side="right", padx=5)

    def _save(self):
        try:
            tag = self.tag_combo.get().strip()
            code = self.code_entry.get().strip()
            tarif_kz = self.tarif_entry.get().strip()
            datum_raw = self.datum_entry.get().strip()
            datum_iso = parse_date_to_iso(datum_raw)

            anzahl_str = self.anzahl_entry.get().strip().replace(",", ".")
            anzahl = float(anzahl_str) if anzahl_str else 0.0

            einzel_str = self.einzel_entry.get().strip().replace(",", ".")
            einzel = float(einzel_str) if einzel_str else 0.0

            zuz_str = self.zuz_entry.get().strip().replace(",", ".")
            zuz = float(zuz_str) if zuz_str else 0.0

            if not code:
                messagebox.showwarning("Eingabefehler", "Bitte geben Sie einen Leistungsschlüssel (Code) ein.")
                return

            if datum_raw and not (len(datum_iso) == 8 and datum_iso.isdigit()):
                messagebox.showwarning(
                    "Eingabefehler", "Bitte geben Sie ein gültiges Behandlungsdatum im Format TT.MM.JJJJ (z.B. 04.12.2025) ein."
                )
                return

            self.result = {
                "tag": tag,
                "code": code,
                "tarif_kz": tarif_kz,
                "datum": datum_iso,
                "anzahl": anzahl,
                "einzelbetrag": round(einzel, 2),
                "gesamtbetrag": round(anzahl * einzel, 2),
                "zuzahlung": round(zuz, 2),
                "zuzahlung_gesamt": round(anzahl * zuz, 2),
            }
            self.destroy()
        except ValueError:
            messagebox.showerror("Eingabefehler", "Bitte gültige Zahlen für Anzahl, Einzelpreis und Zuzahlung eingeben.")


class VKZCorrectionEditorDialog(tk.Toplevel):
    """
    Generischer Master-Detail-Editor-Dialog für alle VKZ (02, 03, 04, 10).
    Erlaubt die gezielte Auswahl und Anpassung von Preisen, Positionen, Terminen
    und Tarifen für Korrekturabrechnungen aller Art.
    """

    def __init__(
        self,
        parent: tk.Tk,
        file_path: str,
        selected_belegnr_list: List[str],
        target_vk: str = "02",
        output_dir: Optional[str] = None,
        new_rec_nr: Optional[str] = None,
        new_rec_date: Optional[str] = None,
        zuzahlungskennzeichen: Optional[str] = None,
        on_complete_callback: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent)

        self.file_path = Path(file_path)
        self.selected_belegnr_list = selected_belegnr_list
        self.target_vk = target_vk
        self.output_dir = output_dir
        self.new_rec_nr = new_rec_nr
        self.new_rec_date = new_rec_date
        self.zuzahlungskennzeichen = zuzahlungskennzeichen
        self.on_complete_callback = on_complete_callback

        vkz_label = _VKZ_LABELS.get(target_vk, f"VKZ {target_vk}")
        self.title(f"VKZ {target_vk} — Detail-Korrektureditor ({vkz_label})")
        self.geometry("1280x820")
        self.minsize(950, 650)
        self.resizable(True, True)

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        theme_manager.apply_theme(self)

        # Load raw content and parse Belege
        self.raw_content = read_esol_file_text(self.file_path)
        self.all_belege = parse_esol_belege_summary(self.raw_content)

        # Filter to selected Belege
        selected_set = set(self.selected_belegnr_list)
        self.belege = [b for b in self.all_belege if b["belegnr"] in selected_set]

        # Apply global pre-selection if provided by the user
        if self.zuzahlungskennzeichen is not None:
            for b in self.belege:
                b["zuzahlungskennzeichen"] = self.zuzahlungskennzeichen

        self.belege_map: Dict[str, Dict[str, Any]] = {b["belegnr"]: b for b in self.belege}

        # Keep track of original copies for restore
        self.original_belege_map: Dict[str, Dict[str, Any]] = copy.deepcopy(self.belege_map)

        # Storage for user modifications per Beleg
        # belegnr -> {"tarifkennzeichen": str, "zuzahlungskennzeichen": str, "positions": list}
        self.modifications: Dict[str, Dict[str, Any]] = {}

        self.active_belegnr: Optional[str] = self.belege[0]["belegnr"] if self.belege else None

        self._setup_ui()
        if self.active_belegnr:
            self._select_beleg(self.active_belegnr)

    def _setup_ui(self):
        vkz_label = _VKZ_LABELS.get(self.target_vk, f"VKZ {self.target_vk}")

        # Top Header Info
        header = ttk.Frame(self, padding=(10, 8))
        header.pack(fill="x")

        ttk.Label(
            header,
            text=f"VKZ {self.target_vk} Korrektur-Spezifikation für {len(self.belege)} Belege",
            font=("Consolas", 12, "bold"),
        ).pack(anchor="w")
        ttk.Label(header, text=f"Quelldatei: {self.file_path.name}  |  Typ: {vkz_label}", font=("Consolas", 9)).pack(anchor="w")

        # Main PanedWindow (Master-Detail Split)
        main_paned = ttk.PanedWindow(self, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=10, pady=5)

        # -------------------------------------------------------------
        # Left Pane: Beleg List (Master)
        # -------------------------------------------------------------
        left_frame = ttk.LabelFrame(main_paned, text=" Belege (Auswahl) ", padding=5)
        main_paned.add(left_frame, weight=1)

        tree_cols = ("belegnr", "name", "status")
        self.beleg_tree = ttk.Treeview(left_frame, columns=tree_cols, show="headings", selectmode="browse")
        self.beleg_tree.heading("belegnr", text="Beleg-Nr.")
        self.beleg_tree.heading("name", text="Versicherter")
        self.beleg_tree.heading("status", text="Status")

        self.beleg_tree.column("belegnr", width=90, anchor="w")
        self.beleg_tree.column("name", width=140, anchor="w")
        self.beleg_tree.column("status", width=80, anchor="center")

        b_scroll = ttk.Scrollbar(left_frame, orient="vertical", command=self.beleg_tree.yview)
        self.beleg_tree.configure(yscrollcommand=b_scroll.set)

        self.beleg_tree.pack(side="left", fill="both", expand=True)
        b_scroll.pack(side="right", fill="y")

        self.beleg_tree.bind("<<TreeviewSelect>>", self._on_beleg_selected)

        # Populate left tree
        for b in self.belege:
            b_nr = b["belegnr"]
            name = f"{b.get('nachname', '')}, {b.get('vorname', '')}".strip(", ")
            self.beleg_tree.insert("", "end", iid=b_nr, values=(b_nr, name, "Unverändert"))

        # -------------------------------------------------------------
        # Right Pane: Tabs / Detail Editor (Detail)
        # -------------------------------------------------------------
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill="both", expand=True)

        # Tab 1: Stammdaten & Tarif
        self.tab_meta = ttk.Frame(self.notebook, padding=15)
        self.notebook.add(self.tab_meta, text=" 📋 Stammdaten & Tarif ")
        self._setup_meta_tab()

        # Tab 2: Leistungspositionen & Termine
        self.tab_pos = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_pos, text=" 💶 Leistungspositionen & Termine ")
        self._setup_positions_tab()

        # Tab 3: Vorschau & EDIFACT-Diff
        self.tab_diff = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.tab_diff, text=" 🔍 Vorschau & EDIFACT-Diff ")
        self._setup_diff_tab()

        # Automatically update preview when switching to preview tab
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # -------------------------------------------------------------
        # Footer Action Bar
        # -------------------------------------------------------------
        footer = ttk.Frame(self, padding=10)
        footer.pack(fill="x", side="bottom")

        btn_cancel = ttk.Button(footer, text="Abbrechen", command=self.destroy)
        btn_cancel.pack(side="right", padx=5)

        btn_generate = ttk.Button(
            footer,
            text=f"▶ Korrekturdatei (VKZ {self.target_vk}) generieren",
            command=self._generate_correction,
        )
        btn_generate.pack(side="right", padx=5)

    def _on_tab_changed(self, event):
        selected_tab = self.notebook.select()
        if selected_tab == str(self.tab_diff):
            self._update_diff_preview()

    def _setup_meta_tab(self):
        pad = {"padx": 10, "pady": 8}

        # Info Box (Readonly)
        info_frame = ttk.LabelFrame(self.tab_meta, text=" Versichertendaten (Original) ", padding=10)
        info_frame.pack(fill="x", pady=(0, 10))

        self.lbl_vers_name = ttk.Label(info_frame, text="Versicherter: -", font=("Consolas", 10, "bold"))
        self.lbl_vers_name.grid(row=0, column=0, sticky="w", **pad)

        self.lbl_vers_nr = ttk.Label(info_frame, text="Versichertennr: -")
        self.lbl_vers_nr.grid(row=0, column=1, sticky="w", **pad)

        self.lbl_geburtstag = ttk.Label(info_frame, text="Geburtsdatum: -")
        self.lbl_geburtstag.grid(row=0, column=2, sticky="w", **pad)

        # Edit Box
        edit_frame = ttk.LabelFrame(self.tab_meta, text=" Tarif- & Abrechnungsparameter ", padding=10)
        edit_frame.pack(fill="x", pady=10)

        ttk.Label(edit_frame, text="Tarifkennzeichen (10-stellig):").grid(row=0, column=0, sticky="w", **pad)
        self.entry_tarif_kz = ttk.Entry(edit_frame, width=25)
        self.entry_tarif_kz.grid(row=0, column=1, sticky="w", **pad)
        self.entry_tarif_kz.bind("<FocusOut>", lambda e: self._on_meta_changed())

        ttk.Label(edit_frame, text="Zuzahlungskennzeichen (ZHE):").grid(row=1, column=0, sticky="w", **pad)
        self.zkz_options = [
            "0 — keine gesetzliche Zuzahlung",
            "1 — Zuzahlungsbefreit",
            "2 — keine Zuzahlung trotz schriftlicher Zahlungsaufforderung",
            "3 — Zuzahlungspflichtig",
            "4 — Übergang zuzahlungspflichtig zu zuzahlungsfrei",
            "5 — Übergang zuzahlungsfrei zu zuzahlungspflichtig",
        ]
        self.combo_zkz = ttk.Combobox(edit_frame, values=self.zkz_options, state="readonly", width=55)
        self.combo_zkz.grid(row=1, column=1, columnspan=2, sticky="w", **pad)
        self.combo_zkz.bind("<<ComboboxSelected>>", lambda e: self._on_meta_changed())

        ttk.Label(edit_frame, text="10 € Verordnungs-Zuzahlung:").grid(row=2, column=0, sticky="w", **pad)
        self.var_pausch = tk.BooleanVar(value=True)
        self.chk_pausch = ttk.Checkbutton(
            edit_frame,
            text="10,00 € Pauschale einrechnen (Patient hat 10 € Gebühr noch nicht bezahlt)",
            variable=self.var_pausch,
            command=self._on_meta_changed,
        )
        self.chk_pausch.grid(row=2, column=1, columnspan=2, sticky="w", **pad)

        # Recalculated Sums Display Box
        sum_frame = ttk.LabelFrame(self.tab_meta, text=" Berechnete Belegsummen ", padding=10)
        sum_frame.pack(fill="x", pady=10)

        self.lbl_sum_brutto = ttk.Label(sum_frame, text="Brutto: 0,00 €", font=("Consolas", 10, "bold"))
        self.lbl_sum_brutto.grid(row=0, column=0, sticky="w", **pad)

        self.lbl_sum_zuz = ttk.Label(sum_frame, text="Zuzahlung: 0,00 €", font=("Consolas", 10))
        self.lbl_sum_zuz.grid(row=0, column=1, sticky="w", **pad)

        self.lbl_sum_rechn = ttk.Label(sum_frame, text="Rechnungsbetrag (Netto): 0,00 €", font=("Consolas", 10, "bold"))
        self.lbl_sum_rechn.grid(row=0, column=2, sticky="w", **pad)

    def _setup_positions_tab(self):
        # Action Toolbar
        bar = ttk.Frame(self.tab_pos)
        bar.pack(fill="x", pady=(0, 5))

        ttk.Button(bar, text="➕ Position hinzufügen", command=self._add_position).pack(side="left", padx=2)
        ttk.Button(bar, text="✏ Position bearbeiten", command=self._edit_position).pack(side="left", padx=2)
        ttk.Button(bar, text="❌ Position entfernen", command=self._delete_position).pack(side="left", padx=2)
        btn_prices_label = (
            "Preise nullen — Zuzahlung bleibt (VKZ 03 Nachforderung)"
            if self.target_vk == "03"
            else "Alle Preise nullen (nur Zuzahlung)"
        )
        ttk.Button(bar, text=btn_prices_label, command=self._zero_prices).pack(side="left", padx=2)
        ttk.Button(bar, text="Zuzahlungen nullen (Preise behalten)", command=self._zero_zuzahlungen).pack(side="left", padx=2)
        ttk.Button(bar, text="🔄 Original wiederherstellen", command=self._restore_original_beleg).pack(
            side="right", padx=2
        )

        # Positions Treeview Table
        cols = ("tag", "code", "tarif_kz", "datum", "anzahl", "einzel", "gesamt", "zuz", "zuz_gesamt")
        self.pos_tree = ttk.Treeview(self.tab_pos, columns=cols, show="headings", selectmode="extended")

        self.pos_tree.heading("tag", text="Tag")
        self.pos_tree.heading("code", text="Code")
        self.pos_tree.heading("tarif_kz", text="Tarif-KZ")
        self.pos_tree.heading("datum", text="Datum")
        self.pos_tree.heading("anzahl", text="Anzahl")
        self.pos_tree.heading("einzel", text="Einzel €")
        self.pos_tree.heading("gesamt", text="Gesamt €")
        self.pos_tree.heading("zuz", text="Zuz. €")
        self.pos_tree.heading("zuz_gesamt", text="Zuz. Ges €")

        self.pos_tree.column("tag", width=60, minwidth=50, anchor="center")
        self.pos_tree.column("code", width=110, minwidth=80, anchor="w")
        self.pos_tree.column("tarif_kz", width=100, minwidth=80, anchor="center")
        self.pos_tree.column("datum", width=100, minwidth=80, anchor="center")
        self.pos_tree.column("anzahl", width=70, minwidth=50, anchor="e")
        self.pos_tree.column("einzel", width=90, minwidth=70, anchor="e")
        self.pos_tree.column("gesamt", width=100, minwidth=80, anchor="e")
        self.pos_tree.column("zuz", width=80, minwidth=60, anchor="e")
        self.pos_tree.column("zuz_gesamt", width=95, minwidth=75, anchor="e")

        p_scroll_y = ttk.Scrollbar(self.tab_pos, orient="vertical", command=self.pos_tree.yview)
        p_scroll_x = ttk.Scrollbar(self.tab_pos, orient="horizontal", command=self.pos_tree.xview)
        self.pos_tree.configure(yscrollcommand=p_scroll_y.set, xscrollcommand=p_scroll_x.set)

        p_scroll_y.pack(side="right", fill="y")
        p_scroll_x.pack(side="bottom", fill="x")
        self.pos_tree.pack(side="left", fill="both", expand=True)

        self.pos_tree.bind("<Double-1>", lambda e: self._edit_position())

    def _setup_diff_tab(self):
        bar = ttk.Frame(self.tab_diff)
        bar.pack(fill="x", pady=(0, 5))

        ttk.Button(bar, text="🔄 Vorschau & EDIFACT-Diff aktualisieren", command=self._update_diff_preview).pack(
            side="left"
        )

        paned = ttk.PanedWindow(self.tab_diff, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Original Segments Pane
        orig_frame = ttk.LabelFrame(paned, text=" Original EDIFACT-Segmente ", padding=5)
        paned.add(orig_frame, weight=1)

        self.txt_orig = tk.Text(orig_frame, wrap="none", font=("Consolas", 9), width=50)
        sb_orig = ttk.Scrollbar(orig_frame, orient="vertical", command=self.txt_orig.yview)
        self.txt_orig.configure(yscrollcommand=sb_orig.set)
        self.txt_orig.pack(side="left", fill="both", expand=True)
        sb_orig.pack(side="right", fill="y")

        # Modified Segments Pane
        mod_frame = ttk.LabelFrame(paned, text=" Korrigierte EDIFACT-Segmente (Vorschau) ", padding=5)
        paned.add(mod_frame, weight=1)

        self.txt_mod = tk.Text(mod_frame, wrap="none", font=("Consolas", 9), width=50)
        sb_mod = ttk.Scrollbar(mod_frame, orient="vertical", command=self.txt_mod.yview)
        self.txt_mod.configure(yscrollcommand=sb_mod.set)
        self.txt_mod.pack(side="left", fill="both", expand=True)
        sb_mod.pack(side="right", fill="y")

    def _on_beleg_selected(self, event):
        sel = self.beleg_tree.selection()
        if sel:
            b_nr = sel[0]
            self.active_belegnr = b_nr
            self._select_beleg(b_nr)

    def _select_beleg(self, belegnr: str):
        b = self.belege_map.get(belegnr)
        if not b:
            return

        # Update metadata tab info
        name = f"{b.get('nachname', '')}, {b.get('vorname', '')}".strip(", ")
        self.lbl_vers_name.config(text=f"Versicherter: {name}")
        self.lbl_vers_nr.config(text=f"Versichertennr: {b.get('versichertennummer', '-')}")
        geb_raw = b.get("geburtstag", "")
        geb_fmt = format_date_german(geb_raw) if geb_raw else "-"
        self.lbl_geburtstag.config(text=f"Geburtsdatum: {geb_fmt}")

        # Fill edit fields
        self.entry_tarif_kz.delete(0, "end")
        self.entry_tarif_kz.insert(0, b.get("tarifkennzeichen", ""))

        zkz = b.get("zuzahlungskennzeichen", "2")
        idx = 2
        for i, opt in enumerate(self.zkz_options):
            if opt.startswith(zkz):
                idx = i
                break
        self.combo_zkz.current(idx)

        # Set pauschale checkbox state based on Beleg data
        p_val = b.get("zuzahlung_pausch", 10.0)
        self.var_pausch.set(p_val > 0.0)

        # Refresh position table
        self._refresh_positions_table()
        self._update_sums_display()
        self._update_diff_preview()

    def _refresh_positions_table(self):
        for item in self.pos_tree.get_children():
            self.pos_tree.delete(item)

        if not self.active_belegnr:
            return

        b = self.belege_map[self.active_belegnr]
        for idx, pos in enumerate(b.get("positions", [])):
            p_id = str(idx)
            tag = pos.get("tag", "EHE")
            code = pos.get("code", "")
            tarif_kz = pos.get("tarif_kz", "")
            datum = format_date_german(pos.get("datum", ""))
            anzahl = f"{pos.get('anzahl', 0.0):g}"
            einzel = f"{pos.get('einzelbetrag', 0.0):.2f}".replace(".", ",")
            gesamt = f"{pos.get('gesamtbetrag', 0.0):.2f}".replace(".", ",")
            zuz = f"{pos.get('zuzahlung', 0.0):.2f}".replace(".", ",")
            zuz_ges = f"{pos.get('zuzahlung_gesamt', 0.0):.2f}".replace(".", ",")

            self.pos_tree.insert(
                "",
                "end",
                iid=p_id,
                values=(tag, code, tarif_kz, datum, anzahl, einzel, gesamt, zuz, zuz_ges),
            )

    def _update_sums_display(self):
        if not self.active_belegnr:
            return
        b = self.belege_map[self.active_belegnr]
        positions = b.get("positions", [])

        zkz = str(b.get("zuzahlungskennzeichen", "2"))
        brutto = sum(round(p.get("anzahl", 0.0) * p.get("einzelbetrag", 0.0), 2) for p in positions)
        zuz_proz = sum(round(p.get("anzahl", 0.0) * p.get("zuzahlung", 0.0), 2) for p in positions)

        if zkz in ["0", "1"]:
            zuz_pausch = 0.0
        elif "zuzahlung_pausch" in b:
            zuz_pausch = float(b["zuzahlung_pausch"])
        else:
            zuz_pausch = 10.0 if self.var_pausch.get() else 0.0

        tot_zuz = round(zuz_proz + zuz_pausch, 2)
        netto = round(brutto - tot_zuz, 2)

        b["brutto"] = brutto
        b["zuzahlung_proz"] = zuz_proz
        b["zuzahlung_pausch"] = zuz_pausch
        b["total_zuzahlung"] = tot_zuz

        self.lbl_sum_brutto.config(text=f"Brutto: {brutto:.2f} €".replace(".", ","))
        self.lbl_sum_zuz.config(text=f"Zuzahlung: {tot_zuz:.2f} €".replace(".", ","))
        if self.target_vk == "03":
            # For VKZ 03, the Rechnungsbetrag IS the Zuzahlung demand, not Brutto minus Zuzahlung.
            self.lbl_sum_rechn.config(text=f"Nachgeforderte Zuzahlung: {tot_zuz:.2f} €".replace(".", ","))
        else:
            self.lbl_sum_rechn.config(text=f"Rechnungsbetrag (Netto): {netto:.2f} €".replace(".", ","))

    def _mark_active_beleg_modified(self):
        if not self.active_belegnr:
            return
        b_nr = self.active_belegnr
        b = self.belege_map[b_nr]

        # Record modifications dict for generator
        zkz_text = self.combo_zkz.get()
        selected_zkz = zkz_text.split(" ")[0] if zkz_text else "2"
        tarif_kz = self.entry_tarif_kz.get().strip()
        pausch_val = 10.0 if self.var_pausch.get() else 0.0

        self.modifications[b_nr] = {
            "tarifkennzeichen": tarif_kz,
            "zuzahlungskennzeichen": selected_zkz,
            "zuzahlung_pausch": pausch_val,
            "positions": b.get("positions", []),
        }

        # Update left tree status
        if self.beleg_tree.exists(b_nr):
            name = f"{b.get('nachname', '')}, {b.get('vorname', '')}".strip(", ")
            self.beleg_tree.item(b_nr, values=(b_nr, name, "Geändert"))

    def _on_meta_changed(self):
        if not self.active_belegnr:
            return
        b = self.belege_map[self.active_belegnr]
        b["tarifkennzeichen"] = self.entry_tarif_kz.get().strip()
        zkz_text = self.combo_zkz.get()
        b["zuzahlungskennzeichen"] = zkz_text.split(" ")[0] if zkz_text else "2"
        b["zuzahlung_pausch"] = 10.0 if self.var_pausch.get() else 0.0

        self._update_sums_display()
        self._mark_active_beleg_modified()
        self._update_diff_preview()

    def _add_position(self):
        if not self.active_belegnr:
            return
        b = self.belege_map[self.active_belegnr]
        def_tk = b.get("tarifkennzeichen", "")

        dlg = PositionEditDialog(self, position_data=None, default_tarif_kz=def_tk)
        self.wait_window(dlg)

        if dlg.result:
            new_pos = dlg.result
            new_pos["id"] = len(b.get("positions", []))
            b["positions"].append(new_pos)
            self._refresh_positions_table()
            self._update_sums_display()
            self._mark_active_beleg_modified()
            self._update_diff_preview()

    def _edit_position(self):
        if not self.active_belegnr:
            return
        sel = self.pos_tree.selection()
        if not sel:
            messagebox.showwarning("Keine Position", "Bitte wählen Sie eine Leistungsposition zum Bearbeiten aus.")
            return
        if len(sel) > 1:
            messagebox.showwarning("Mehrfachauswahl", "Bitte wählen Sie genau eine Leistungsposition zum Bearbeiten aus.")
            return

        p_idx = int(sel[0])
        b = self.belege_map[self.active_belegnr]
        positions = b.get("positions", [])

        if not (0 <= p_idx < len(positions)):
            return

        target_pos = positions[p_idx]
        def_tk = b.get("tarifkennzeichen", "")
        dlg = PositionEditDialog(self, position_data=target_pos, default_tarif_kz=def_tk)
        self.wait_window(dlg)

        if dlg.result:
            updated = dlg.result
            updated["id"] = target_pos.get("id", p_idx)
            positions[p_idx] = updated
            self._refresh_positions_table()
            self._update_sums_display()
            self._mark_active_beleg_modified()
            self._update_diff_preview()

    def _delete_position(self):
        if not self.active_belegnr:
            return
        sel = self.pos_tree.selection()
        if not sel:
            messagebox.showwarning("Keine Position", "Bitte wählen Sie mindestens eine Leistungsposition zum Entfernen aus.")
            return

        b = self.belege_map[self.active_belegnr]
        positions = b.get("positions", [])

        indices_to_remove = sorted([int(x) for x in sel], reverse=True)
        for p_idx in indices_to_remove:
            if 0 <= p_idx < len(positions):
                positions.pop(p_idx)

        b["positions"] = positions

        self._refresh_positions_table()
        self._update_sums_display()
        self._mark_active_beleg_modified()
        self._update_diff_preview()

    def _zero_prices(self):
        if not self.active_belegnr:
            return

        b = self.belege_map[self.active_belegnr]
        positions = b.get("positions", [])

        if not positions:
            return

        if not messagebox.askyesno("Preise nullen", "Möchten Sie wirklich die Preise (Einzelbetrag) aller Positionen in diesem Beleg auf 0,00 € setzen? Die Zuzahlungen bleiben dabei erhalten."):
            return

        for pos in positions:
            pos["einzelbetrag"] = 0.0
            pos["gesamtbetrag"] = 0.0

        b["positions"] = positions

        self._refresh_positions_table()
        self._update_sums_display()
        self._mark_active_beleg_modified()
        self._update_diff_preview()

    def _zero_zuzahlungen(self):
        if not self.active_belegnr:
            return

        b = self.belege_map[self.active_belegnr]
        positions = b.get("positions", [])

        if not positions:
            return

        if self.target_vk == "03":
            # For VKZ 03, the Rechnungsbetrag IS the Zuzahlung. Zeroing it results
            # in a 0-demand file. Warn the user explicitly before proceeding.
            if not messagebox.askyesno(
                "⚠️ Zuzahlungen nullen — VKZ 03",
                "Achtung: Bei VKZ 03 ist die Zuzahlung der Nachforderungsbetrag!\n\n"
                "Wenn Sie die Zuzahlungen nullen, ist der Rechnungsbetrag der erzeugten Datei 0,00 €.\n\n"
                "Möchten Sie stattdessen die Einzelbeträge nullen und die Zuzahlungen behalten,\n"
                "verwenden Sie den Button \u201ePreise nullen — Zuzahlung bleibt (VKZ 03 Nachforderung)\u201c.\n\n"
                "Trotzdem fortfahren und Zuzahlungen auf 0,00 € setzen?",
            ):
                return
        else:
            if not messagebox.askyesno(
                "Zuzahlungen nullen",
                "Möchten Sie wirklich die Zuzahlungen aller Positionen in diesem Beleg auf 0,00 € setzen? "
                "Die regulären Preise bleiben dabei erhalten.",
            ):
                return

        for pos in positions:
            pos["zuzahlung"] = 0.0
            pos["zuzahlung_gesamt"] = 0.0

        b["positions"] = positions

        self._refresh_positions_table()
        self._update_sums_display()
        self._mark_active_beleg_modified()
        self._update_diff_preview()

    def _restore_original_beleg(self):
        if not self.active_belegnr:
            return
        b_nr = self.active_belegnr
        if b_nr in self.original_belege_map:
            self.belege_map[b_nr] = copy.deepcopy(self.original_belege_map[b_nr])
            if b_nr in self.modifications:
                del self.modifications[b_nr]

            name = f"{self.belege_map[b_nr].get('nachname', '')}, {self.belege_map[b_nr].get('vorname', '')}".strip(
                ", "
            )
            self.beleg_tree.item(b_nr, values=(b_nr, name, "Unverändert"))
            self._select_beleg(b_nr)

    def _update_diff_preview(self):
        if not self.active_belegnr:
            return
        b_nr = self.active_belegnr

        self.txt_orig.delete("1.0", "end")
        self.txt_mod.delete("1.0", "end")

        # Show raw original segments for this Beleg
        orig_b = self.original_belege_map.get(b_nr, {})
        orig_segs = orig_b.get("raw_segments", [])

        orig_lines = []
        for tag, fields in orig_segs:
            parts = [tag]
            for f in fields:
                if isinstance(f, list):
                    parts.append(":".join(str(x) for x in f))
                else:
                    parts.append(str(f))
            orig_lines.append("+".join(parts) + "'")

        self.txt_orig.insert("1.0", "\n".join(orig_lines))

        # Generate modified preview content for this single Beleg
        try:
            mod_content = generate_correction_esol(
                raw_content=self.raw_content,
                target_vk=self.target_vk,
                selected_belegnr_list=[b_nr],
                new_rec_nr=self.new_rec_nr,
                new_rec_date=self.new_rec_date,
                zuzahlungskennzeichen=self.zuzahlungskennzeichen,
                beleg_modifications=self.modifications,
            )
            self.txt_mod.insert("1.0", mod_content)
        except Exception as e:
            self.txt_mod.insert("1.0", f"Vorschau konnte nicht generiert werden:\n{e}")

    def _generate_correction(self):
        if not self.selected_belegnr_list:
            messagebox.showwarning("Keine Belege", "Keine Belege für die Korrektur ausgewählt.")
            return

        try:
            res_path = generate_correction_file(
                input_path=self.file_path,
                output_path=None,
                target_vk=self.target_vk,
                selected_belegnr_list=self.selected_belegnr_list,
                new_rec_nr=self.new_rec_nr,
                new_rec_date=self.new_rec_date,
                zuzahlungskennzeichen=self.zuzahlungskennzeichen,
                out_dir=Path(self.output_dir) if self.output_dir else None,
                beleg_modifications=self.modifications,
            )

            msg = f"Korrekturdatei (VKZ {self.target_vk}) wurde erfolgreich erstellt:\n\n{res_path}"
            messagebox.showinfo("Erfolg", msg)

            if self.on_complete_callback:
                self.on_complete_callback(str(res_path))

            self.destroy()
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler bei Erstellung der VKZ {self.target_vk} Korrekturdatei:\n{e}")
