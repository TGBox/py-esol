import datetime
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, List, Optional

import theme_manager

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from tools.generate_correction import parse_esol_belege_summary, generate_correction_file, read_esol_file_text, format_date_german


class CorrectionSelectionDialog(tk.Toplevel):
    """
    Interactive Dialog window for selecting Belege, VKZ (02, 03, 04), and options
    when generating a correction invoice or co-payment demand.
    """

    def __init__(self, parent: tk.Tk, file_path: str, default_vk: str = "02", output_dir: Optional[str] = None, on_complete_callback: Optional[Callable[[str], None]] = None):
        super().__init__(parent)

        self.file_path = Path(file_path)
        self.default_vk = default_vk
        self.output_dir = output_dir
        self.on_complete_callback = on_complete_callback

        self.title("Korrektur- & Zuzahlungs-Konfigurator")
        self.geometry("850x720")
        self.minsize(800, 650)
        self.resizable(True, True)

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        theme_manager.apply_theme(self)

        self._load_belege_data()
        self._setup_ui()

    def _load_belege_data(self):
        try:
            content = read_esol_file_text(self.file_path)
            self.belege_list = parse_esol_belege_summary(content)
        except Exception as e:
            messagebox.showerror("Fehler beim Lesen", f"Konnte ESOL-Datei nicht lesen:\n{e}")
            self.belege_list = []

    def _setup_ui(self):
        # Header Info
        header_frame = ttk.LabelFrame(self, text=" Datei-Information ", padding=10)
        header_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(header_frame, text=f"Quelldatei: {self.file_path.name}", font=("Consolas", 10, "bold")).pack(anchor="w")
        ttk.Label(header_frame, text=f"Pfad: {self.file_path}", font=("Consolas", 9)).pack(anchor="w")

        # Step 1: Beleg-Auswahl
        beleg_frame = ttk.LabelFrame(self, text=" 1. Belege auswählen ", padding=10)
        beleg_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Buttons for Select All / Deselect All
        btn_bar = ttk.Frame(beleg_frame)
        btn_bar.pack(fill="x", pady=(0, 5))

        ttk.Button(btn_bar, text="Alle auswählen", command=self._select_all).pack(side="left", padx=2)
        ttk.Button(btn_bar, text="Alle abwählen", command=self._deselect_all).pack(side="left", padx=2)

        # Treeview Table
        columns = ("select", "belegnr", "name", "geburtstag", "brutto", "zuzahlung")
        self.tree = ttk.Treeview(beleg_frame, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("select", text="Auswahl")
        self.tree.heading("belegnr", text="Belegnummer")
        self.tree.heading("name", text="Versicherter Name")
        self.tree.heading("geburtstag", text="Geburtsdatum")
        self.tree.heading("brutto", text="Brutto (€)")
        self.tree.heading("zuzahlung", text="Zuzahlung (€)")

        self.tree.column("select", width=70, anchor="center")
        self.tree.column("belegnr", width=120, anchor="w")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("geburtstag", width=100, anchor="center")
        self.tree.column("brutto", width=100, anchor="e")
        self.tree.column("zuzahlung", width=100, anchor="e")

        scrollbar = ttk.Scrollbar(beleg_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate tree items
        self.item_select_map = {}
        for b in self.belege_list:
            b_nr = b.get("belegnr", "")
            name = f"{b.get('nachname', '')}, {b.get('vorname', '')}".strip(", ")
            geb = format_date_german(b.get("geburtstag", ""))
            brutto_str = f"{b.get('brutto', 0.0):.2f}".replace(".", ",")
            zuz_str = f"{b.get('total_zuzahlung', 0.0):.2f}".replace(".", ",")

            item_id = self.tree.insert("", "end", values=("[X]", b_nr, name, geb, brutto_str, zuz_str))
            self.item_select_map[item_id] = {"selected": True, "belegnr": b_nr}

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        # Step 2: Options Frame
        opt_frame = ttk.LabelFrame(self, text=" 2. Korrektur-Optionen ", padding=10)
        opt_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(opt_frame, text="Verarbeitungskennzeichen (VKZ):").grid(row=0, column=0, sticky="w", pady=5)

        self.vk_var = tk.StringVar(value=self.default_vk)
        r1 = ttk.Radiobutton(opt_frame, text="VK 02 — Nachforderung (Teilnachforderung)", value="02", variable=self.vk_var)
        r2 = ttk.Radiobutton(opt_frame, text="VK 03 — Zuzahlungsforderung (§ 43c SGB V)", value="03", variable=self.vk_var)
        r3 = ttk.Radiobutton(opt_frame, text="VK 04 — Korrekturrechnung (Neuberechnung)", value="04", variable=self.vk_var)
        r4 = ttk.Radiobutton(opt_frame, text="VK 10 — Wiederaufnahme Blankoverordnung (§ 125a SGB V)", value="10", variable=self.vk_var)

        r1.grid(row=0, column=1, columnspan=2, sticky="w", padx=5)
        r2.grid(row=1, column=1, columnspan=2, sticky="w", padx=5)
        r3.grid(row=2, column=1, columnspan=2, sticky="w", padx=5)
        r4.grid(row=3, column=1, columnspan=2, sticky="w", padx=5)

        ttk.Label(opt_frame, text="Zuzahlungskennzeichen (ZHE):").grid(row=4, column=0, sticky="w", pady=5)
        self.zkz_options = [
            "0 — keine gesetzliche Zuzahlung",
            "1 — Zuzahlungsbefreit",
            "2 — keine Zuzahlung trotz schriftlicher Zahlungsaufforderung",
            "3 — Zuzahlungspflichtig",
            "4 — Übergang zuzahlungspflichtig zu zuzahlungsfrei",
            "5 — Übergang zuzahlungsfrei zu zuzahlungspflichtig",
        ]
        self.zkz_combo = ttk.Combobox(opt_frame, values=self.zkz_options, state="readonly", width=55)
        self.zkz_combo.grid(row=4, column=1, columnspan=3, sticky="w", padx=5, pady=5)
        self.zkz_combo.current(2)  # Default option 2

        ttk.Label(opt_frame, text="Neue Rechnungsnummer:").grid(row=5, column=0, sticky="w", pady=5)
        self.rec_nr_entry = ttk.Entry(opt_frame, width=25)
        self.rec_nr_entry.grid(row=5, column=1, sticky="w", padx=5, pady=5)
        self.rec_nr_entry.insert(0, f"RE{datetime.datetime.now().strftime('%d%m')}Z")
        self.rec_nr_entry.bind("<Return>", lambda event: self._generate())

        ttk.Label(opt_frame, text="Neues Rechnungsdatum:").grid(row=5, column=2, sticky="w", pady=5)
        self.rec_date_entry = ttk.Entry(opt_frame, width=15)
        self.rec_date_entry.grid(row=5, column=3, sticky="w", padx=5, pady=5)
        self.rec_date_entry.insert(0, datetime.datetime.now().strftime("%Y%m%d"))
        self.rec_date_entry.bind("<Return>", lambda event: self._generate())

        # Footer Buttons
        footer_frame = ttk.Frame(self)
        footer_frame.pack(side="bottom", fill="both", padx=10, pady=10, expand=True)

        btn_cancel = ttk.Button(footer_frame, text="Abbrechen", command=self.destroy)
        btn_cancel.pack(side="right", padx=5)

        self.btn_generate = ttk.Button(footer_frame, text="▶ Datei generieren", command=self._generate)
        self.btn_generate.pack(side="right", padx=5)

        # Update button text on VK selection change
        r1.configure(command=self._on_vk_changed)
        r2.configure(command=self._on_vk_changed)
        r3.configure(command=self._on_vk_changed)
        r4.configure(command=self._on_vk_changed)
        self._on_vk_changed()

    def _on_vk_changed(self):
        if self.vk_var.get() == "02":
            self.btn_generate.config(text="Weiter zur Detail-Korrektur ▶")
        else:
            self.btn_generate.config(text="▶ Datei generieren")

    def _on_tree_click(self, event):
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if item_id and col == "#1":  # Column 1 is checkbox
            current = self.item_select_map[item_id]["selected"]
            new_state = not current
            self.item_select_map[item_id]["selected"] = new_state

            vals = list(self.tree.item(item_id, "values"))
            vals[0] = "[X]" if new_state else "[ ]"
            self.tree.item(item_id, values=vals)

    def _select_all(self):
        for item_id, data in self.item_select_map.items():
            data["selected"] = True
            vals = list(self.tree.item(item_id, "values"))
            vals[0] = "[X]"
            self.tree.item(item_id, values=vals)

    def _deselect_all(self):
        for item_id, data in self.item_select_map.items():
            data["selected"] = False
            vals = list(self.tree.item(item_id, "values"))
            vals[0] = "[ ]"
            self.tree.item(item_id, values=vals)

    def _generate(self):
        selected_belege = [
            data["belegnr"] for data in self.item_select_map.values() if data["selected"]
        ]

        if not selected_belege:
            messagebox.showwarning("Keine Belege", "Bitte wählen Sie mindestens einen Beleg aus.")
            return

        target_vk = self.vk_var.get()
        new_rec_nr = self.rec_nr_entry.get().strip() or None
        new_rec_date = self.rec_date_entry.get().strip() or None

        zkz_text = self.zkz_combo.get()
        selected_zkz = zkz_text.split(" ")[0] if zkz_text else "2"

        if target_vk == "02":
            from vk02_correction_editor import VK02CorrectionEditorDialog

            parent_tk = self.master
            cb = self.on_complete_callback
            f_path = str(self.file_path)
            o_dir = self.output_dir
            self.destroy()

            VK02CorrectionEditorDialog(
                parent=parent_tk,
                file_path=f_path,
                selected_belegnr_list=selected_belege,
                output_dir=o_dir,
                new_rec_nr=new_rec_nr,
                new_rec_date=new_rec_date,
                zuzahlungskennzeichen=selected_zkz,
                on_complete_callback=cb,
            )
            return

        try:
            res_path = generate_correction_file(
                input_path=self.file_path,
                output_path=None,
                target_vk=target_vk,
                selected_belegnr_list=selected_belege,
                new_rec_nr=new_rec_nr,
                new_rec_date=new_rec_date,
                zuzahlungskennzeichen=selected_zkz,
                out_dir=Path(self.output_dir) if self.output_dir else None,
            )

            msg = f"Korrekturdatei (VKZ {target_vk}) wurde erfolgreich erstellt:\n\n{res_path}"
            messagebox.showinfo("Erfolg", msg)

            if self.on_complete_callback:
                self.on_complete_callback(str(res_path))

            self.destroy()
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler bei Erstellung der Korrekturdatei:\n{e}")
