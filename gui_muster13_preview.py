"""
ESOL Visuelle Rezept-Vorschau — Virtuelles Verordnungsblatt im Stil des Musters 13/18
(Heilmittelverordnung) mit Aufschlüsselung von Kassenanteil, Zuzahlung und Fehlermeldungen.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

import theme_manager
from tools.generate_correction import format_date_german
from support_helper import translate_error


class Muster13PreviewFrame(ttk.Frame):
    """
    Formularbasierter Rezept-Viewer im Layout der Heilmittelverordnung (Muster 13/18).
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=15)

        self.current_beleg: Optional[Dict[str, Any]] = None
        self.validation_errors: List[str] = []

        self._setup_ui()

    def apply_theme(self, mode: Optional[str] = None):
        colors = theme_manager.get_theme_colors(mode)
        active_mode = mode or theme_manager.get_current_theme()
        if active_mode == "dark":
            self.lbl_beleg_nr.config(foreground=colors["log_header"])
            self.lbl_total_zuz.config(foreground=colors["log_error"])
            self.lbl_netto.config(foreground=colors["log_ok"])
            self.err_banner.config(background="#5c1d24", foreground="#f8d7da")
        else:
            self.lbl_beleg_nr.config(foreground="#0275d8")
            self.lbl_total_zuz.config(foreground="#d9534f")
            self.lbl_netto.config(foreground="#5cb85c")
            self.err_banner.config(background="#f8d7da", foreground="#721c24")

    def _setup_ui(self):
        # Header Title
        title_bar = ttk.Frame(self)
        title_bar.pack(fill="x", pady=(0, 10))

        ttk.Label(
            title_bar,
            text="📋 Heilmittelverordnung — Virtuelles Muster 13 / 18",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")

        self.lbl_beleg_nr = ttk.Label(
            title_bar, text="Kein Beleg gewählt", font=("Consolas", 11, "bold"), foreground="#0275d8"
        )
        self.lbl_beleg_nr.pack(side="right")

        # -------------------------------------------------------------
        # Box 1: Krankenkasse & Versichertendaten (Kopfzeile Verordnung)
        # -------------------------------------------------------------
        head_frame = ttk.LabelFrame(self, text=" Krankenkasse & Versicherter ", padding=10)
        head_frame.pack(fill="x", pady=(0, 10))

        pad = {"padx": 8, "pady": 4}

        ttk.Label(head_frame, text="Kostenträger-IK:").grid(row=0, column=0, sticky="w", **pad)
        self.lbl_ik = ttk.Label(head_frame, text="-", font=("Consolas", 10, "bold"))
        self.lbl_ik.grid(row=0, column=1, sticky="w", **pad)

        ttk.Label(head_frame, text="Versicherter Name:").grid(row=0, column=2, sticky="w", **pad)
        self.lbl_name = ttk.Label(head_frame, text="-", font=("Consolas", 10, "bold"))
        self.lbl_name.grid(row=0, column=3, sticky="w", **pad)

        ttk.Label(head_frame, text="Versichertennr.:").grid(row=1, column=0, sticky="w", **pad)
        self.lbl_versnr = ttk.Label(head_frame, text="-")
        self.lbl_versnr.grid(row=1, column=1, sticky="w", **pad)

        ttk.Label(head_frame, text="Geburtsdatum:").grid(row=1, column=2, sticky="w", **pad)
        self.lbl_geb = ttk.Label(head_frame, text="-")
        self.lbl_geb.grid(row=1, column=3, sticky="w", **pad)

        ttk.Label(head_frame, text="Zuzahlungsstatus:").grid(row=2, column=0, sticky="w", **pad)
        self.lbl_zuz_status = ttk.Label(head_frame, text="-", font=("Segoe UI", 9, "bold"))
        self.lbl_zuz_status.grid(row=2, column=1, columnspan=3, sticky="w", **pad)

        # -------------------------------------------------------------
        # Box 2: Heilmittel-Positionen & Behandlungen
        # -------------------------------------------------------------
        pos_frame = ttk.LabelFrame(self, text=" Verordnete Heilmittel / Behandlungen ", padding=10)
        pos_frame.pack(fill="both", expand=True, pady=(0, 10))

        cols = ("tag", "code", "datum", "anzahl", "einzel", "gesamt", "zuzahlung")
        self.pos_tree = ttk.Treeview(pos_frame, columns=cols, show="headings", height=6)

        self.pos_tree.heading("tag", text="Art")
        self.pos_tree.heading("code", text="Leistungsschlüssel")
        self.pos_tree.heading("datum", text="Behandlungsdatum")
        self.pos_tree.heading("anzahl", text="Anzahl")
        self.pos_tree.heading("einzel", text="Einzel €")
        self.pos_tree.heading("gesamt", text="Gesamt €")
        self.pos_tree.heading("zuzahlung", text="Zuzahlung €")

        self.pos_tree.column("tag", width=60, anchor="center")
        self.pos_tree.column("code", width=140, anchor="w")
        self.pos_tree.column("datum", width=120, anchor="center")
        self.pos_tree.column("anzahl", width=70, anchor="e")
        self.pos_tree.column("einzel", width=90, anchor="e")
        self.pos_tree.column("gesamt", width=100, anchor="e")
        self.pos_tree.column("zuzahlung", width=90, anchor="e")

        sb = ttk.Scrollbar(pos_frame, orient="vertical", command=self.pos_tree.yview)
        self.pos_tree.configure(yscrollcommand=sb.set)

        self.pos_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # -------------------------------------------------------------
        # Box 3: Abrechnungs- & Betragsaufschlüsselung
        # -------------------------------------------------------------
        sum_frame = ttk.LabelFrame(self, text=" Abrechnung & Zuzahlungs-Aufschlüsselung ", padding=10)
        sum_frame.pack(fill="x", pady=(0, 10))

        self.lbl_brutto = ttk.Label(sum_frame, text="Bruttobetrag: 0,00 €", font=("Consolas", 10, "bold"))
        self.lbl_brutto.grid(row=0, column=0, sticky="w", **pad)

        self.lbl_proz_zuz = ttk.Label(sum_frame, text="Prozentuale Zuzahlung (10%): 0,00 €")
        self.lbl_proz_zuz.grid(row=0, column=1, sticky="w", **pad)

        self.lbl_pausch_zuz = ttk.Label(sum_frame, text="10 € Pauschale: 10,00 €")
        self.lbl_pausch_zuz.grid(row=0, column=2, sticky="w", **pad)

        self.lbl_total_zuz = ttk.Label(sum_frame, text="Gesamte Zuzahlung: 0,00 €", font=("Consolas", 10, "bold"), foreground="#d9534f")
        self.lbl_total_zuz.grid(row=1, column=0, sticky="w", **pad)

        self.lbl_netto = ttk.Label(sum_frame, text="Kassenanteil (Netto): 0,00 €", font=("Consolas", 10, "bold"), foreground="#5cb85c")
        self.lbl_netto.grid(row=1, column=1, columnspan=2, sticky="w", **pad)

        # Error notification banner inside Muster 13 form
        self.err_banner = ttk.Label(self, text="", font=("Segoe UI", 9, "bold"), background="#f8d7da", foreground="#721c24", padding=6)

    def load_beleg(self, beleg: Dict[str, Any], validation_errors: List[str] = None):
        """
        Befüllt das virtuelle Verordnungsblatt mit den Daten des ausgewählten Belegs.
        """
        self.current_beleg = beleg
        self.validation_errors = validation_errors or []

        b_nr = str(beleg.get("belegnr", "-"))
        self.lbl_beleg_nr.config(text=f"Beleg-Nr. {b_nr}")

        # Stammdaten
        name = f"{beleg.get('nachname', '')}, {beleg.get('vorname', '')}".strip(", ")
        self.lbl_name.config(text=name or "-")
        self.lbl_versnr.config(text=str(beleg.get("versichertennummer", "-")))
        geb_raw = str(beleg.get("geburtstag", ""))
        self.lbl_geb.config(text=format_date_german(geb_raw) if geb_raw else "-")

        # Zuzahlungsstatus
        zkz = str(beleg.get("zuzahlungskennzeichen", "2"))
        zkz_labels = {
            "0": "0 — keine gesetzliche Zuzahlung",
            "1": "1 — Zuzahlungsbefreit",
            "2": "2 — Zuzahlungspflichtig (nicht entrichtet)",
            "3": "3 — Zuzahlungspflichtig",
            "4": "4 — Übergang zuzahlungspflichtig zu befreit",
            "5": "5 — Übergang befreit zu zuzahlungspflichtig",
        }
        self.lbl_zuz_status.config(text=zkz_labels.get(zkz, f"Kennzeichen {zkz}"))

        # Positionen
        for item in self.pos_tree.get_children():
            self.pos_tree.delete(item)

        positions = beleg.get("positions", [])
        for pos in positions:
            tag = pos.get("tag", "EHE")
            code = str(pos.get("code", ""))
            datum = format_date_german(str(pos.get("datum", "")))
            anzahl = f"{pos.get('anzahl', 0.0):g}"
            einzel = f"{pos.get('einzelbetrag', 0.0):.2f}".replace(".", ",")
            gesamt = f"{pos.get('gesamtbetrag', 0.0):.2f}".replace(".", ",")
            zuz = f"{pos.get('zuzahlung', 0.0):.2f}".replace(".", ",")

            self.pos_tree.insert("", "end", values=(tag, code, datum, anzahl, einzel, gesamt, zuz))

        # Summen
        brutto = float(beleg.get("brutto", 0.0))
        proz_zuz = float(beleg.get("zuzahlung_proz", 0.0))
        pausch_zuz = float(beleg.get("zuzahlung_pausch", 10.0))
        tot_zuz = float(beleg.get("total_zuzahlung", 0.0))
        netto = round(brutto - tot_zuz, 2)

        self.lbl_brutto.config(text=f"Bruttobetrag: {brutto:.2f} €".replace(".", ","))
        self.lbl_proz_zuz.config(text=f"Prozentuale Zuzahlung (10%): {proz_zuz:.2f} €".replace(".", ","))
        self.lbl_pausch_zuz.config(text=f"10 € Pauschale: {pausch_zuz:.2f} €".replace(".", ","))
        self.lbl_total_zuz.config(text=f"Gesamte Zuzahlung: {tot_zuz:.2f} €".replace(".", ","))
        self.lbl_netto.config(text=f"Kassenanteil (Netto): {netto:.2f} €".replace(".", ","))

        # Fehler-Banner falls Fehler auf diesen Beleg zutreffen
        matching = [e for e in self.validation_errors if b_nr in e]
        if matching:
            trans = translate_error(matching[0])
            self.err_banner.config(text=f"⚠️ {trans['title']} — {trans['action']}")
            self.err_banner.pack(fill="x", pady=(5, 0))
        else:
            self.err_banner.pack_forget()
