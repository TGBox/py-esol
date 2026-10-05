"""
ESOL Beleg-Dashboard — Interaktive Beleg-Übersichtstabelle mit KPI-Kacheln,
Schnellfilter/Volltextsuche, Status-Indikatoren und Hotline-Handlungsempfehlungen.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional

import codelisten
import theme_manager
from support_helper import translate_error


class BelegDashboardFrame(ttk.Frame):
    """
    Interaktives Dashboard für Support-Mitarbeiter zur schnellen Übersicht
    aller Rechnungsbelege, Filterung und Fehler-Fokussierung.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_select_beleg_cb: Optional[Callable[[str], None]] = None,
        on_open_editor_cb: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(parent, padding=10)

        self.on_select_beleg_cb = on_select_beleg_cb
        self.on_open_editor_cb = on_open_editor_cb

        self.belege_list: List[Dict[str, Any]] = []
        self.validation_errors: List[str] = []
        self.active_belegnr: Optional[str] = None

        self._setup_ui()

    def _setup_ui(self):
        # -------------------------------------------------------------
        # 1. KPI-Kacheln (Header)
        # -------------------------------------------------------------
        kpi_frame = ttk.Frame(self)
        kpi_frame.pack(fill="x", pady=(0, 10))

        # Card 1: Anzahl Belege
        c1 = ttk.LabelFrame(kpi_frame, text=" Anzahl Belege ", padding=8)
        c1.pack(side="left", fill="both", expand=True, padx=3)
        self.lbl_kpi_count = ttk.Label(c1, text="0", font=("Consolas", 14, "bold"))
        self.lbl_kpi_count.pack(anchor="center")

        # Card 2: Gesamtsumme Brutto
        c2 = ttk.LabelFrame(kpi_frame, text=" Gesamtsumme Brutto ", padding=8)
        c2.pack(side="left", fill="both", expand=True, padx=3)
        self.lbl_kpi_brutto = ttk.Label(c2, text="0,00 €", font=("Consolas", 14, "bold"))
        self.lbl_kpi_brutto.pack(anchor="center")

        # Card 3: Gesamte Zuzahlung
        c3 = ttk.LabelFrame(kpi_frame, text=" Gesamte Zuzahlung ", padding=8)
        c3.pack(side="left", fill="both", expand=True, padx=3)
        self.lbl_kpi_zuz = ttk.Label(c3, text="0,00 €", font=("Consolas", 14, "bold"))
        self.lbl_kpi_zuz.pack(anchor="center")

        # Card 4: Validierungs-Status
        c4 = ttk.LabelFrame(kpi_frame, text=" Status ", padding=8)
        c4.pack(side="left", fill="both", expand=True, padx=3)
        self.lbl_kpi_status = ttk.Label(c4, text="Ungeprüft", font=("Consolas", 12, "bold"))
        self.lbl_kpi_status.pack(anchor="center")

        # -------------------------------------------------------------
        # 2. Such- & Filterleiste
        # -------------------------------------------------------------
        filter_bar = ttk.LabelFrame(self, text=" Suche & Filter ", padding=8)
        filter_bar.pack(fill="x", pady=(0, 10))

        ttk.Label(filter_bar, text="🔍 Volltextsuche:").pack(side="left", padx=5)
        self.search_entry = ttk.Entry(filter_bar, width=30)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filters())

        ttk.Label(filter_bar, text="Status-Filter:").pack(side="left", padx=(15, 5))
        self.combo_filter = ttk.Combobox(
            filter_bar,
            values=["Alle Belege", "Nur Fehlerfreie (Grün)", "Nur Fehlerhafte (Rot)"],
            state="readonly",
            width=22,
        )
        self.combo_filter.current(0)
        self.combo_filter.pack(side="left", padx=5)
        self.combo_filter.bind("<<ComboboxSelected>>", lambda e: self._apply_filters())

        ttk.Button(filter_bar, text="Filter zurücksetzen", command=self._reset_filters).pack(side="right", padx=5)

        # -------------------------------------------------------------
        # 3. Master-Detail Paned Window
        # -------------------------------------------------------------
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        # Left Pane: Beleg-Tabelle
        left_frame = ttk.LabelFrame(paned, text=" Beleg-Übersicht ", padding=5)
        paned.add(left_frame, weight=3)

        cols = ("belegnr", "name", "versnr", "brutto", "zuzahlung", "status")
        self.beleg_tree = ttk.Treeview(left_frame, columns=cols, show="headings", selectmode="browse")

        self.beleg_tree.heading("belegnr", text="Beleg-Nr.")
        self.beleg_tree.heading("name", text="Versicherter Name")
        self.beleg_tree.heading("versnr", text="Versicherter-ID")
        self.beleg_tree.heading("brutto", text="Brutto (€)")
        self.beleg_tree.heading("zuzahlung", text="Zuzahlung (€)")
        self.beleg_tree.heading("status", text="Status")

        self.beleg_tree.column("belegnr", width=100, anchor="w")
        self.beleg_tree.column("name", width=180, anchor="w")
        self.beleg_tree.column("versnr", width=110, anchor="center")
        self.beleg_tree.column("brutto", width=90, anchor="e")
        self.beleg_tree.column("zuzahlung", width=90, anchor="e")
        self.beleg_tree.column("status", width=90, anchor="center")

        sb_y = ttk.Scrollbar(left_frame, orient="vertical", command=self.beleg_tree.yview)
        self.beleg_tree.configure(yscrollcommand=sb_y.set)

        self.beleg_tree.pack(side="left", fill="both", expand=True)
        sb_y.pack(side="right", fill="y")

        self.beleg_tree.bind("<<TreeviewSelect>>", self._on_beleg_selected)

        # Right Pane: Hotline-Handlungsanweisung & Detail-Fokus
        right_frame = ttk.LabelFrame(paned, text=" Support-Handlungsanweisung & Details ", padding=8)
        paned.add(right_frame, weight=2)

        self.lbl_selected_title = ttk.Label(
            right_frame, text="Kein Beleg ausgewählt", font=("Consolas", 11, "bold")
        )
        self.lbl_selected_title.pack(anchor="w", pady=(0, 5))

        # Detail-Notebook mit zwei Tabs: Support/Fehler und Leistungen
        self.detail_notebook = ttk.Notebook(right_frame)
        self.detail_notebook.pack(fill="both", expand=True, pady=3)

        # Tab 1: Hotline-Anweisung & Fehler
        self.tab_info = ttk.Frame(self.detail_notebook, padding=2)
        self.detail_notebook.add(self.tab_info, text=" ⚠️ Hotline-Anweisung & Analyse ")

        self.info_box = tk.Text(self.tab_info, wrap="word", font=("Segoe UI", 9), height=11, state="disabled")
        self.info_box.pack(fill="both", expand=True)

        # Tab 2: Verordnete Leistungen & Positionen
        self.tab_positions = ttk.Frame(self.detail_notebook, padding=2)
        self.detail_notebook.add(self.tab_positions, text=" 💶 Verordnete Leistungen ")

        pos_cols = ("tag", "code", "bezeichnung", "menge", "einzel", "gesamt")
        self.beleg_pos_tree = ttk.Treeview(self.tab_positions, columns=pos_cols, show="headings", selectmode="browse")
        self.beleg_pos_tree.heading("tag", text="Tag")
        self.beleg_pos_tree.heading("code", text="Code")
        self.beleg_pos_tree.heading("bezeichnung", text="Bezeichnung (Klartext)")
        self.beleg_pos_tree.heading("menge", text="Menge")
        self.beleg_pos_tree.heading("einzel", text="Einzel €")
        self.beleg_pos_tree.heading("gesamt", text="Gesamt €")

        self.beleg_pos_tree.column("tag", width=45, minwidth=35, anchor="center")
        self.beleg_pos_tree.column("code", width=70, minwidth=55, anchor="w")
        self.beleg_pos_tree.column("bezeichnung", width=180, minwidth=110, anchor="w")
        self.beleg_pos_tree.column("menge", width=55, minwidth=40, anchor="e")
        self.beleg_pos_tree.column("einzel", width=65, minwidth=50, anchor="e")
        self.beleg_pos_tree.column("gesamt", width=70, minwidth=55, anchor="e")

        sb_pos_y = ttk.Scrollbar(self.tab_positions, orient="vertical", command=self.beleg_pos_tree.yview)
        self.beleg_pos_tree.configure(yscrollcommand=sb_pos_y.set)
        self.beleg_pos_tree.pack(side="left", fill="both", expand=True)
        sb_pos_y.pack(side="right", fill="y")

        # Action Buttons below detail box
        btn_bar = ttk.Frame(right_frame)
        btn_bar.pack(fill="x", pady=(8, 0))

        self.btn_preview = ttk.Button(
            btn_bar, text="📜 Im Verordnungsblatt anzeigen", command=self._trigger_preview
        )
        self.btn_preview.pack(fill="x", pady=2)

        self.btn_editor = ttk.Button(
            btn_bar, text="🛠️ In Korrektur-Editor bearbeiten", command=self._trigger_editor
        )
        self.btn_editor.pack(fill="x", pady=2)

    def apply_theme(self, mode: Optional[str] = None):
        colors = theme_manager.get_theme_colors(mode)
        self.info_box.config(
            bg=colors["entry_bg"],
            fg=colors["entry_fg"],
            insertbackground=colors["entry_fg"],
        )
        self.info_box.tag_config("ERROR", foreground=colors["log_error"])
        self.info_box.tag_config("OK", foreground=colors["log_ok"])
        self.info_box.tag_config("HEADER", foreground=colors.get("log_header", "#0066cc"))

    def load_data(self, belege_summary: List[Dict[str, Any]], validation_errors: List[str]):
        """
        Lädt die Belegdaten und Fehlerergebnisse in das Dashboard.
        """
        self.belege_list = belege_summary
        self.validation_errors = validation_errors

        # KPI-Kacheln aktualisieren
        total_count = len(belege_summary)
        total_brutto = sum(b.get("brutto", 0.0) for b in belege_summary)
        total_zuz = sum(b.get("total_zuzahlung", 0.0) for b in belege_summary)

        self.lbl_kpi_count.config(text=str(total_count))
        self.lbl_kpi_brutto.config(text=f"{total_brutto:.2f} €".replace(".", ","))
        self.lbl_kpi_zuz.config(text=f"{total_zuz:.2f} €".replace(".", ","))

        colors = theme_manager.get_theme_colors()
        if validation_errors:
            self.lbl_kpi_status.config(text=f"⚠️ {len(validation_errors)} Fehler", foreground=colors["log_error"])
        else:
            self.lbl_kpi_status.config(text="✅ Fehlerfrei", foreground=colors["log_ok"])

        self._apply_filters()

    def _reset_filters(self):
        self.search_entry.delete(0, tk.END)
        self.combo_filter.current(0)
        self._apply_filters()

    def _apply_filters(self):
        for item in self.beleg_tree.get_children():
            self.beleg_tree.delete(item)

        search_term = self.search_entry.get().strip().lower()
        filter_mode = self.combo_filter.get()

        for b in self.belege_list:
            b_nr = str(b.get("belegnr", ""))
            nachname = str(b.get("nachname", ""))
            vorname = str(b.get("vorname", ""))
            versnr = str(b.get("versichertennummer", ""))
            name = f"{nachname}, {vorname}".strip(", ")
            brutto = f"{b.get('brutto', 0.0):.2f}".replace(".", ",")
            zuz = f"{b.get('total_zuzahlung', 0.0):.2f}".replace(".", ",")

            has_error = any(b_nr in err for err in self.validation_errors) if self.validation_errors else False
            status_text = "❌ Fehler" if has_error else "✅ OK"

            # Filter-Check 1: Status
            if filter_mode == "Nur Fehlerfreie (Grün)" and has_error:
                continue
            if filter_mode == "Nur Fehlerhafte (Rot)" and not has_error:
                continue

            # Filter-Check 2: Suchbegriff
            if search_term:
                match = (
                    search_term in b_nr.lower()
                    or search_term in name.lower()
                    or search_term in versnr.lower()
                )
                if not match:
                    continue

            self.beleg_tree.insert(
                "",
                "end",
                iid=b_nr,
                values=(b_nr, name, versnr, brutto, zuz, status_text),
            )

        # Select first item if available
        children = self.beleg_tree.get_children()
        if children:
            self.beleg_tree.selection_set(children[0])
            self._on_beleg_selected(None)

    def _on_beleg_selected(self, event):
        sel = self.beleg_tree.selection()
        if not sel:
            return

        b_nr = sel[0]
        self.active_belegnr = b_nr

        b = next((x for x in self.belege_list if str(x.get("belegnr")) == b_nr), None)
        if not b:
            return

        name = f"{b.get('nachname', '')}, {b.get('vorname', '')}".strip(", ")
        self.lbl_selected_title.config(text=f"Beleg-Nr. {b_nr} — {name}")

        # Update positions tree and info text
        for item in self.beleg_pos_tree.get_children():
            self.beleg_pos_tree.delete(item)

        positions = b.get("positions", [])
        # Die eigene Pflege in codelisten.json ist nach Abrechnungscode gestaffelt,
        # nicht nach Tarifkennzeichen.
        beleg_abr = str(b.get("abrechnungscode", "") or "")

        for idx, pos in enumerate(positions):
            p_tag = str(pos.get("tag", "EHE"))
            p_code = str(pos.get("code", ""))
            p_bez = (
                pos.get("code_klartext")
                or pos.get("bezeichnung")
                or codelisten.lookup_position(p_code, pos.get("abr_code") or beleg_abr)
                or "—"
            )
            p_menge = f"{pos.get('anzahl', 0.0):g}"
            p_einzel = f"{pos.get('einzelbetrag', 0.0):.2f}".replace(".", ",")
            p_ges = f"{pos.get('gesamtbetrag', 0.0):.2f}".replace(".", ",")
            self.beleg_pos_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(p_tag, p_code, p_bez, p_menge, p_einzel, p_ges),
            )

        self.detail_notebook.tab(self.tab_positions, text=f" 💶 Verordnete Leistungen ({len(positions)}) ")

        # Erstelle Hotline-Anweisungstext
        self.info_box.config(state="normal")
        self.info_box.delete("1.0", tk.END)

        self.info_box.insert(tk.END, f"PATIENT: {name}\n")
        self.info_box.insert(tk.END, f"Versichertennummer: {b.get('versichertennummer', '-')}\n")
        self.info_box.insert(tk.END, f"Tarif-KZ: {b.get('tarifkennzeichen', '-')}\n\n")

        if positions:
            self.info_box.insert(tk.END, "VERORDNETE LEISTUNGEN & POSITIONEN:\n", "HEADER")
            for pos in positions:
                p_code = str(pos.get("code", ""))
                p_bez = (
                    pos.get("code_klartext")
                    or pos.get("bezeichnung")
                    or codelisten.lookup_position(p_code, pos.get("abr_code") or beleg_abr)
                    or "Kein Klartext hinterlegt"
                )
                p_menge = f"{pos.get('anzahl', 0.0):g}"
                p_einzel = f"{pos.get('einzelbetrag', 0.0):.2f}".replace(".", ",")
                p_ges = f"{pos.get('gesamtbetrag', 0.0):.2f}".replace(".", ",")
                self.info_box.insert(tk.END, f"• {p_code}: {p_bez}\n   Menge: {p_menge} × {p_einzel} € = {p_ges} €\n")
            self.info_box.insert(tk.END, "\n")

        matching_errors = [err for err in self.validation_errors if b_nr in err]
        if matching_errors:
            self.info_box.insert(tk.END, "⚠️ BELEG-SPEZIFISCHE FEHLER:\n", "ERROR")
            for err in matching_errors:
                trans = translate_error(err)
                self.info_box.insert(tk.END, f"• {trans['title']}\n")
                self.info_box.insert(tk.END, f"  Log: {err}\n")
                self.info_box.insert(tk.END, f"  Ursache: {trans['explanation']}\n")
                self.info_box.insert(tk.END, f"  👉 HANDLUNG: {trans['action']}\n\n")
            # If errors exist, make the error tab active
            self.detail_notebook.select(self.tab_info)
        elif self.validation_errors:
            self.info_box.insert(tk.END, "✅ Dieser Beleg ist fehlerfrei.\n")
            self.info_box.insert(tk.END, "Es liegen jedoch allgemeine Datei-/Header-Fehler vor:\n")
            for err in self.validation_errors[:3]:
                trans = translate_error(err)
                self.info_box.insert(tk.END, f"• {trans['title']}: {trans['action']}\n")
        else:
            self.info_box.insert(tk.END, "✅ Beleg ist vollständig valide und fehlerfrei.\n")
            self.info_box.insert(tk.END, "Keine Aktion erforderlich.\n")

        self.info_box.config(state="disabled")

        if self.on_select_beleg_cb:
            self.on_select_beleg_cb(b_nr)

    def _trigger_preview(self):
        if self.active_belegnr and self.on_select_beleg_cb:
            self.on_select_beleg_cb(self.active_belegnr)

    def _trigger_editor(self):
        if self.active_belegnr and self.on_open_editor_cb:
            self.on_open_editor_cb(self.active_belegnr)
