#!/usr/bin/env python3
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Optional


class EsolValidatorGUI(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("ESOL Datei-Validator")
        self.geometry("850x650")
        self.minsize(700, 500)

        # Pfade zu den Skripten bestimmen
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.validate_script = os.path.join(self.base_dir, "validate.py")
        self.batch_script = os.path.join(self.base_dir, "batch_validate.py")
        self.convert_script = os.path.join(self.base_dir, "tools\\convert_utf8_to_iso.py")
        self.generate_auf_script = os.path.join(self.base_dir, "tools\\generate_auf.py")

        self._setup_ui()

    def _setup_ui(self):
        # Frame oben: Dateiauswahl & Einstellungen
        top_frame = ttk.LabelFrame(self, text=" Eingabe & Optionen ", padding=10)
        top_frame.pack(fill="x", padx=10, pady=10)

        # 1. Zeile: Dateiauswahl
        ttk.Label(top_frame, text="Pfad / Datei(en):").grid(
            row=0, column=0, sticky="w", pady=5
        )

        self.path_entry = ttk.Entry(top_frame, width=50)
        self.path_entry.grid(
            row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5
        )

        btn_files = ttk.Button(
            top_frame, text="Datei(en) wählen", command=self._select_files
        )
        btn_files.grid(row=0, column=3, padx=2, pady=5)

        btn_dir = ttk.Button(
            top_frame, text="Ordner wählen", command=self._select_directory
        )
        btn_dir.grid(row=0, column=4, padx=2, pady=5)

        # 2. Zeile: Optionen
        ttk.Label(top_frame, text="Max. Prüfstufe:").grid(
            row=1, column=0, sticky="w", pady=5
        )

        self.stufe_var = tk.IntVar(value=4)
        stufe_spin = ttk.Spinbox(
            top_frame, from_=1, to=4, textvariable=self.stufe_var, width=5
        )
        stufe_spin.grid(row=1, column=1, sticky="w", padx=5, pady=5)

        self.warnings_var = tk.BooleanVar(value=True)
        chk_warnings = ttk.Checkbutton(
            top_frame, text="Warnungen anzeigen (-w)", variable=self.warnings_var
        )
        chk_warnings.grid(row=1, column=2, sticky="w", padx=5, pady=5)

        # Grid-Weight für Anpassung bei Fenstergrößenänderung
        top_frame.columnconfigure(1, weight=1)

        # 3. Zeile: Aktions-Buttons
        btn_frame = ttk.Frame(top_frame)
        btn_frame.grid(row=2, column=0, columnspan=5, sticky="ew", pady=10)

        self.btn_run = ttk.Button(
            btn_frame, text="▶ Validierung starten", command=self._start_validation
        )
        self.btn_run.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_convert = ttk.Button(
            btn_frame, text="🔄 UTF-8 ➔ ISO-8859-15", command=self._start_conversion
        )
        self.btn_convert.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_auf = ttk.Button(
            btn_frame, text="📄 Auftragsdatei (.auf) erstellen", command=self._start_generate_auf
        )
        self.btn_auf.pack(side="left", fill="x", expand=True, padx=2)

        # Progressbar (optional/visuell)
        self.progress = ttk.Progressbar(top_frame, mode="indeterminate")

        # Frame unten: Ausgabepanel
        output_frame = ttk.LabelFrame(self, text=" Ergebnis ", padding=10)
        output_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Text-Panel für Log
        self.log_text = ScrolledText(
            output_frame, wrap="word", font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4"
        )
        self.log_text.pack(fill="both", expand=True, side="top")

        # Text-Farbtags konfigurieren
        self.log_text.tag_config("ERROR", foreground="#f44336")
        self.log_text.tag_config("OK", foreground="#4caf50")
        self.log_text.tag_config("HEADER", foreground="#64b5f6", font=("Consolas", 10, "bold"))

        # Footer mit Kopieren-Button
        footer_frame = ttk.Frame(output_frame)
        footer_frame.pack(fill="x", pady=(5, 0))

        btn_copy = ttk.Button(
            footer_frame, text="📋 Ergebnisse kopieren", command=self._copy_to_clipboard
        )
        btn_copy.pack(side="right")

        btn_clear = ttk.Button(
            footer_frame, text="Löschen", command=self._clear_log
        )
        btn_clear.pack(side="right", padx=5)

    def _select_files(self):
        files = filedialog.askopenfilenames(
            title="ESOL-Dateien auswählen",
            filetypes=[("Alle Dateien", "*.*")]
        )
        if files:
            # Pfade durch Semikolon getrennt eintragen
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, "; ".join(files))

    def _select_directory(self):
        directory = filedialog.askdirectory(title="Batch-Ordner auswählen")
        if directory:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, directory)

    def _clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def _copy_to_clipboard(self):
        content = self.log_text.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(content)
        messagebox.showinfo("Erfolg", "Ergebnisse wurden in die Zwischenablage kopiert!")

    def _set_buttons_state(self, state: str):
        self.btn_run.config(state=state)
        self.btn_convert.config(state=state)
        self.btn_auf.config(state=state)

    def _start_validation(self):
        raw_path = self.path_entry.get().strip()

        if not raw_path:
            messagebox.showwarning("Fehler", "Bitte wählen Sie eine Datei oder einen Ordner aus!")
            return

        self._set_buttons_state("disabled")
        self.progress.grid(row=3, column=0, columnspan=5, sticky="ew", pady=2)
        self.progress.start(10)
        self._clear_log()

        # In separatem Thread ausführen, damit GUI reagiert
        threading.Thread(target=self._run_process, args=(raw_path,), daemon=True).start()

    def _start_conversion(self):
        raw_path = self.path_entry.get().strip()

        if not raw_path:
            messagebox.showwarning("Fehler", "Bitte wählen Sie eine Datei oder einen Ordner aus!")
            return

        self._set_buttons_state("disabled")
        self.progress.grid(row=3, column=0, columnspan=5, sticky="ew", pady=2)
        self.progress.start(10)
        self._clear_log()

        threading.Thread(target=self._run_conversion_process, args=(raw_path,), daemon=True).start()

    def _start_generate_auf(self):
        raw_path = self.path_entry.get().strip()

        if not raw_path:
            messagebox.showwarning("Fehler", "Bitte wählen Sie eine Datei oder einen Ordner aus!")
            return

        self._set_buttons_state("disabled")
        self.progress.grid(row=3, column=0, columnspan=5, sticky="ew", pady=2)
        self.progress.start(10)
        self._clear_log()

        threading.Thread(target=self._run_generate_auf_process, args=(raw_path,), daemon=True).start()

    def _run_process(self, path_input: str):
        try:
            paths = [p.strip() for p in path_input.split(";") if p.strip()]

            files_to_validate: list[str] = []

            for path in paths:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            if not file.endswith(".txt") and not file.endswith(".auf") and not file.startswith("."):
                                files_to_validate.append(os.path.join(root, file))
                elif os.path.isfile(path):
                    if not path.endswith(".txt") and not path.endswith(".auf"):
                        files_to_validate.append(path)

            if not files_to_validate:
                self._append_log("Keine gültigen ESOL-Dateien zur Validierung gefunden.\n", tag="ERROR")
                return

            self._append_log(f"Starte Validierung von {len(files_to_validate)} Datei(en)...\n\n", tag="HEADER")

            for file_path in files_to_validate:
                cmd = [
                    sys.executable,
                    self.validate_script,
                    file_path,
                    f"--stufe={self.stufe_var.get()}"
                ]
                if self.warnings_var.get():
                    cmd.append("--warnings")

                self._append_log(f"=== Datei: {os.path.basename(file_path)} ===\n", tag="HEADER")
                self._execute_cmd(cmd)
                self._append_log("\n" + "-" * 60 + "\n\n")

        finally:
            self.after(0, self._finish_process)

    def _run_conversion_process(self, path_input: str):
        try:
            paths = [p.strip() for p in path_input.split(";") if p.strip()]
            files_to_convert: list[str] = []

            for path in paths:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            if not file.endswith(".txt") and not file.endswith(".auf") and not file.startswith("."):
                                files_to_convert.append(os.path.join(root, file))
                elif os.path.isfile(path):
                    if not path.endswith(".txt") and not path.endswith(".auf"):
                        files_to_convert.append(path)

            if not files_to_convert:
                self._append_log("Keine Dateien zur Konvertierung gefunden.\n", tag="ERROR")
                return

            self._append_log(f"Starte Konvertierung von {len(files_to_convert)} Datei(en) nach ISO-8859-15...\n\n", tag="HEADER")

            for file_path in files_to_convert:
                cmd = [
                    sys.executable,
                    self.convert_script,
                    file_path,
                    "--inplace"
                ]
                self._append_log(f"=== Konvertiere: {os.path.basename(file_path)} ===\n", tag="HEADER")
                self._execute_cmd(cmd)
                self._append_log("\n" + "-" * 60 + "\n\n")

        finally:
            self.after(0, self._finish_process)

    def _run_generate_auf_process(self, path_input: str):
        try:
            paths = [p.strip() for p in path_input.split(";") if p.strip()]
            files_to_process: list[str] = []

            for path in paths:
                if os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            if not file.endswith(".txt") and not file.endswith(".auf") and not file.startswith("."):
                                files_to_process.append(os.path.join(root, file))
                elif os.path.isfile(path):
                    if not path.endswith(".txt") and not path.endswith(".auf"):
                        files_to_process.append(path)

            if not files_to_process:
                self._append_log("Keine ESOL-Dateien zur Erstellung von Auftragsdateien gefunden.\n", tag="ERROR")
                return

            self._append_log(f"Erstelle Auftragsdateien (.auf) für {len(files_to_process)} Datei(en)...\n\n", tag="HEADER")

            for file_path in files_to_process:
                cmd = [
                    sys.executable,
                    self.generate_auf_script,
                    file_path
                ]
                self._append_log(f"=== Generiere .auf: {os.path.basename(file_path)} ===\n", tag="HEADER")
                self._execute_cmd(cmd)
                self._append_log("\n" + "-" * 60 + "\n\n")

        finally:
            self.after(0, self._finish_process)

    def _execute_cmd(self, cmd: list[str]):
        # Neu: Erzwinge UTF-8 sowohl für Ausgaben als auch für Python-Interna
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        if proc.stdout:
            for line in proc.stdout:
                tag: Optional[str] = None
                if "FEHLER" in line or "UNGÜLTIG" in line or "PARSE-FEHLER" in line:
                    tag = "ERROR"
                elif "GÜLTIG" in line or "OK" in line:
                    tag = "OK"

                self._append_log(line, tag)

        proc.wait()

    def _append_log(self, text: str, tag: Optional[str] = None):
        def write():
            if tag:
                self.log_text.insert(tk.END, text, tag)
            else:
                self.log_text.insert(tk.END, text)
            self.log_text.see(tk.END)

        self.after(0, write)

    def _finish_process(self):
        self.progress.stop()
        self.progress.grid_forget()
        self._set_buttons_state("normal")


if __name__ == "__main__":
    app = EsolValidatorGUI()
    app.mainloop()