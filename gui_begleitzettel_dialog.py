"""
GUI Dialog for creating Begleitzettel PDF documents in py-esol.
Provides an interactive input mask for user entries with auto-prefill support from ESOL files.
"""

import datetime
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Any, Optional

import theme_manager

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from parser.segment_tokenizer import SegmentTokenizer
from tools.generate_begleitzettel import generate_begleitzettel_pdf
from tools.generate_correction import parse_segment_fields, read_esol_file_text, format_date_german


def extract_begleitzettel_defaults(file_path: Path) -> Dict[str, str]:
    """
    Extracts default billing/invoice values from an ESOL file to populate the Begleitzettel form.
    """
    defaults = {
        "ik_kostentraeger": "",
        "name_krankenkasse": "",
        "ik_rechnungssteller": "",
        "name_rechnungssteller": "",
        "rechnungsnummer": "",
        "rechnungsdatum": datetime.date.today().strftime("%d.%m.%Y"),
        "erste_belegnummer": "",
        "letzte_belegnummer": "",
        "anzahl_urbelege": "0",
    }

    if not file_path.exists() or not file_path.is_file():
        return defaults

    try:
        content = read_esol_file_text(file_path)
        tokenizer = SegmentTokenizer()
        segments = tokenizer.tokenize_segments(content)

        beleg_numbers = []

        for seg_str in segments:
            tag, fields = parse_segment_fields(seg_str)

            if tag == "UNB":
                # UNB+UNOA:2+SenderIK:Qual+ReceiverIK:Qual+Date:Time+Ref'
                if len(fields) > 1:
                    sender_field = fields[1]
                    if isinstance(sender_field, list) and len(sender_field) > 0:
                        defaults["ik_rechnungssteller"] = sender_field[0]
                    elif isinstance(sender_field, str):
                        defaults["ik_rechnungssteller"] = sender_field.split(":")[0]

                if len(fields) > 2:
                    rec_field = fields[2]
                    if isinstance(rec_field, list) and len(rec_field) > 0:
                        defaults["ik_kostentraeger"] = rec_field[0]
                    elif isinstance(rec_field, str):
                        defaults["ik_kostentraeger"] = rec_field.split(":")[0]

            elif tag in ["FKT", "SLD"]:
                if len(fields) > 1 and fields[1]:
                    defaults["rechnungsnummer"] = str(fields[1])

                # Search for date in FKT/SLD if present
                for f in fields:
                    if isinstance(f, str) and len(f) == 8 and f.isdigit():
                        defaults["rechnungsdatum"] = format_date_german(f)

            elif tag == "INV":
                if len(fields) > 3 and fields[3]:
                    beleg_numbers.append(str(fields[3]))
                elif len(fields) > 0 and fields[0]:
                    beleg_numbers.append(str(fields[0]))

        if beleg_numbers:
            defaults["erste_belegnummer"] = beleg_numbers[0]
            defaults["letzte_belegnummer"] = beleg_numbers[-1]
            defaults["anzahl_urbelege"] = str(len(beleg_numbers))

    except Exception as e:
        print(f"Warning: Could not extract ESOL defaults: {e}")

    return defaults


class BegleitzettelDialog(tk.Toplevel):
    """
    Modal Dialog window for configuring and generating Begleitzettel PDF documents.
    """

    def __init__(self, parent: tk.Tk, esol_file_path: Optional[str] = None):
        super().__init__(parent)

        self.esol_file_path = Path(esol_file_path) if esol_file_path else None
        self.title("Begleitzettel PDF erstellen")
        self.geometry("750x700")
        self.minsize(700, 620)

        # Make window modal
        self.transient(parent)
        self.grab_set()

        theme_manager.apply_theme(self)

        self._setup_ui()
        self._load_defaults()

    def _setup_ui(self):
        # Outer container with padding & canvas scrollbar if screen is small
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill="both", expand=True)

        # --- Section 1: Absender (Praxis-Informationen) ---
        sec_absender = ttk.LabelFrame(main_frame, text=" 1. Absender (Praxis-Informationen) ", padding=8)
        sec_absender.pack(fill="x", padx=5, pady=4)

        sec_absender.columnconfigure(1, weight=1)
        sec_absender.columnconfigure(3, weight=1)

        ttk.Label(sec_absender, text="Name / Praxis:").grid(row=0, column=0, sticky="w", pady=2)
        self.ent_abs_name = ttk.Entry(sec_absender)
        self.ent_abs_name.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(sec_absender, text="Straße & Hausnr.:").grid(row=0, column=2, sticky="w", pady=2)
        self.ent_abs_strasse = ttk.Entry(sec_absender)
        self.ent_abs_strasse.grid(row=0, column=3, sticky="ew", padx=4, pady=2)

        ttk.Label(sec_absender, text="PLZ & Ort:").grid(row=1, column=0, sticky="w", pady=2)
        self.ent_abs_plz_ort = ttk.Entry(sec_absender)
        self.ent_abs_plz_ort.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(sec_absender, text="Telefon:").grid(row=1, column=2, sticky="w", pady=2)
        self.ent_abs_telefon = ttk.Entry(sec_absender)
        self.ent_abs_telefon.grid(row=1, column=3, sticky="ew", padx=4, pady=2)

        ttk.Label(sec_absender, text="E-Mail:").grid(row=2, column=0, sticky="w", pady=2)
        self.ent_abs_email = ttk.Entry(sec_absender)
        self.ent_abs_email.grid(row=2, column=1, columnspan=3, sticky="ew", padx=4, pady=2)

        # --- Section 2: Fenster-Absenderzeile (Kurzadresse) ---
        sec_fenster = ttk.LabelFrame(main_frame, text=" 2. Absenderzeile (im Brieffenster oben) ", padding=8)
        sec_fenster.pack(fill="x", padx=5, pady=4)
        sec_fenster.columnconfigure(1, weight=1)

        ttk.Label(sec_fenster, text="Kurzadresse:").grid(row=0, column=0, sticky="w", pady=2)
        self.ent_fensterzeile = ttk.Entry(sec_fenster)
        self.ent_fensterzeile.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        # Sync button to generate window line from absender details
        btn_sync = ttk.Button(sec_fenster, text="Aus Absender erzeugen", command=self._generate_fensterzeile)
        btn_sync.grid(row=0, column=2, padx=4, pady=2)

        # --- Section 3: Empfänger (DLZ / Annahmestelle) ---
        sec_empf = ttk.LabelFrame(main_frame, text=" 3. Empfänger (Anschriftfeld) ", padding=8)
        sec_empf.pack(fill="x", padx=5, pady=4)
        sec_empf.columnconfigure(1, weight=1)

        ttk.Label(sec_empf, text="Name / Zeile 1:").grid(row=0, column=0, sticky="w", pady=2)
        self.ent_empf_1 = ttk.Entry(sec_empf)
        self.ent_empf_1.grid(row=0, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(sec_empf, text="Straße / Zeile 2:").grid(row=1, column=0, sticky="w", pady=2)
        self.ent_empf_2 = ttk.Entry(sec_empf)
        self.ent_empf_2.grid(row=1, column=1, sticky="ew", padx=4, pady=2)

        ttk.Label(sec_empf, text="PLZ Ort / Zeile 3:").grid(row=2, column=0, sticky="w", pady=2)
        self.ent_empf_3 = ttk.Entry(sec_empf)
        self.ent_empf_3.grid(row=2, column=1, sticky="ew", padx=4, pady=2)

        # --- Section 4: Abrechnungsdaten ---
        sec_daten = ttk.LabelFrame(main_frame, text=" 4. Abrechnungs- & Belegdaten ", padding=8)
        sec_daten.pack(fill="x", padx=5, pady=4)

        sec_daten.columnconfigure(1, weight=1)
        sec_daten.columnconfigure(3, weight=1)

        fields_meta = [
            ("IK Kostenträger:", "ik_kostentraeger", 0, 0),
            ("Name der Krankenkasse:", "name_krankenkasse", 0, 2),
            ("IK Rechnungssteller:", "ik_rechnungssteller", 1, 0),
            ("Name d. Rechnungsstellers:", "name_rechnungssteller", 1, 2),
            ("Rechnungsnummer:", "rechnungsnummer", 2, 0),
            ("Rechnungsdatum:", "rechnungsdatum", 2, 2),
            ("erste Belegnummer:", "erste_belegnummer", 3, 0),
            ("letzte Belegnummer:", "letzte_belegnummer", 3, 2),
            ("Anzahl Urbelege:", "anzahl_urbelege", 4, 0),
        ]

        self.entries_daten = {}
        for label_text, key, r, c in fields_meta:
            ttk.Label(sec_daten, text=label_text).grid(row=r, column=c, sticky="w", pady=2)
            entry = ttk.Entry(sec_daten)
            entry.grid(row=r, column=c + 1, sticky="ew", padx=4, pady=2)
            self.entries_daten[key] = entry

        # --- Footer Actions ---
        btn_bar = ttk.Frame(main_frame, padding=(0, 10))
        btn_bar.pack(fill="x", side="bottom")

        btn_cancel = ttk.Button(btn_bar, text="Abbrechen", command=self.destroy)
        btn_cancel.pack(side="right", padx=4)

        btn_generate = ttk.Button(btn_bar, text="📄 PDF erstellen & speichern", command=self._on_generate_pdf)
        btn_generate.pack(side="right", padx=4)

    def _load_defaults(self):
        """Loads default values into form entries."""
        defaults = {}
        if self.esol_file_path:
            defaults = extract_begleitzettel_defaults(self.esol_file_path)

        for key, entry in self.entries_daten.items():
            val = defaults.get(key, "")
            entry.delete(0, tk.END)
            entry.insert(0, val)

    def _generate_fensterzeile(self):
        """Builds a formatted window sender line from the main sender fields."""
        name = self.ent_abs_name.get().strip()
        strasse = self.ent_abs_strasse.get().strip()
        plz_ort = self.ent_abs_plz_ort.get().strip()
        parts = [p for p in [name, strasse, plz_ort] if p]
        self.ent_fensterzeile.delete(0, tk.END)
        self.ent_fensterzeile.insert(0, " . ".join(parts))

    def _on_generate_pdf(self):
        """Collects form inputs, prompts for output file location, and creates PDF."""
        # Compile dictionary of values
        data = {
            "absender_name": self.ent_abs_name.get().strip(),
            "absender_strasse": self.ent_abs_strasse.get().strip(),
            "absender_plz_ort": self.ent_abs_plz_ort.get().strip(),
            "absender_telefon": self.ent_abs_telefon.get().strip(),
            "absender_email": self.ent_abs_email.get().strip(),
            "absender_fensterzeile": self.ent_fensterzeile.get().strip(),
            "empfaenger_zeile1": self.ent_empf_1.get().strip(),
            "empfaenger_zeile2": self.ent_empf_2.get().strip(),
            "empfaenger_zeile3": self.ent_empf_3.get().strip(),
        }

        for key, entry in self.entries_daten.items():
            data[key] = entry.get().strip()

        # Suggest default file name based on invoice number & date
        rechnr = data.get("rechnungsnummer", "1") or "1"
        datum_str = data.get("rechnungsdatum", "").replace(".", "_") or datetime.date.today().strftime("%d_%m_%Y")
        default_filename = f"Begleitzettel_{rechnr}_{datum_str}.pdf"

        # Show Save As file dialog
        output_file = filedialog.asksaveasfilename(
            parent=self,
            title="Begleitzettel PDF speichern unter",
            initialfile=default_filename,
            defaultextension=".pdf",
            filetypes=[("PDF Datei", "*.pdf"), ("Alle Dateien", "*.*")],
        )

        if not output_file:
            return

        try:
            generated_path = generate_begleitzettel_pdf(data, output_file)
            messagebox.showinfo(
                "PDF erfolgreich erstellt",
                f"Der Begleitzettel wurde erfolgreich gespeichert unter:\n{generated_path}",
                parent=self,
            )

            # Open PDF in default viewer
            if sys.platform == "win32":
                os.startfile(generated_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", generated_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", generated_path])

            self.destroy()

        except Exception as e:
            messagebox.showerror("Fehler bei PDF-Erstellung", f"Konnte PDF nicht erstellen:\n{e}", parent=self)
