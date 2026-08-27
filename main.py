import os
import subprocess
import sys
import multiprocessing
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Dict, List, Optional

import theme_manager
from gui_beleg_dashboard import BelegDashboardFrame
from gui_muster13_preview import Muster13PreviewFrame
from gui_recipe_tree import RecipeTreeFrame
from support_helper import generate_html_report, generate_ticket_summary
from tools.generate_correction import parse_esol_belege_summary, read_esol_file_text


class EsolValidatorGUI(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("ESOL Datei-Validator & Support-Dashboard")
        self.geometry("1100x820")
        self.minsize(900, 700)

        # Pfade zu den Skripten bestimmen
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.validate_script = os.path.join(self.base_dir, "validate.py")
        self.batch_script = os.path.join(self.base_dir, "batch_validate.py")
        self.convert_script = os.path.join(self.base_dir, "tools", "convert_utf8_to_iso.py")
        self.generate_auf_script = os.path.join(self.base_dir, "tools", "generate_auf.py")
        self.correction_script = os.path.join(self.base_dir, "tools", "generate_correction.py")

        self.user_selected_out_dir: bool = False
        self.last_belege_summary: List[Dict[str, Any]] = []
        self.last_validation_errors: List[str] = []
        self.last_processed_file: Optional[str] = None

        self._setup_ui()
        self._apply_theme()

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

        # 2. Zeile: Ausgabeordner (Optional)
        ttk.Label(top_frame, text="Ausgabeordner (opt.):").grid(
            row=1, column=0, sticky="w", pady=5
        )

        self.out_dir_entry = ttk.Entry(top_frame, width=50)
        self.out_dir_entry.grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=5, pady=5
        )
        self.out_dir_entry.bind("<KeyRelease>", self._on_out_dir_key_release)

        btn_out_dir = ttk.Button(
            top_frame, text="Ausgabeordner wählen", command=self._select_out_directory
        )
        btn_out_dir.grid(row=1, column=3, columnspan=2, sticky="ew", padx=2, pady=5)

        # 3. Zeile: Optionen & Theme-Toggle
        ttk.Label(top_frame, text="Max. Prüfstufe:").grid(
            row=2, column=0, sticky="w", pady=5
        )

        self.stufe_var = tk.IntVar(value=4)
        stufe_spin = ttk.Spinbox(
            top_frame, from_=1, to=4, textvariable=self.stufe_var, width=5
        )
        stufe_spin.grid(row=2, column=1, sticky="w", padx=5, pady=5)

        self.warnings_var = tk.BooleanVar(value=True)
        chk_warnings = ttk.Checkbutton(
            top_frame, text="Warnungen anzeigen (-w)", variable=self.warnings_var
        )
        chk_warnings.grid(row=2, column=2, sticky="w", padx=5, pady=5)

        self.btn_theme = ttk.Button(
            top_frame, text="🌙 Dark Mode", command=self._toggle_theme
        )
        self.btn_theme.grid(row=2, column=3, columnspan=2, sticky="e", padx=2, pady=5)

        # Grid-Weight für Anpassung bei Fenstergrößenänderung
        top_frame.columnconfigure(1, weight=1)

        # 4. Zeile: Aktions-Buttons
        btn_frame = ttk.Frame(top_frame)
        btn_frame.grid(row=3, column=0, columnspan=5, sticky="ew", pady=10)

        self.btn_run = ttk.Button(
            btn_frame, text="▶ Validieren", command=self._start_validation
        )
        self.btn_run.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_convert = ttk.Button(
            btn_frame, text="🔄 UTF-8 ➔ ISO", command=self._start_conversion
        )
        self.btn_convert.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_auf = ttk.Button(
            btn_frame, text="📄 .auf erstellen", command=self._start_generate_auf
        )
        self.btn_auf.pack(side="left", fill="x", expand=True, padx=2)

        self.btn_correction = ttk.Button(
            btn_frame, text="🛠️ Korrektur / Zuzahlung", command=self._start_correction_dialog
        )
        self.btn_correction.pack(side="left", fill="x", expand=True, padx=2)

        # Progressbar (optional/visuell)
        self.progress = ttk.Progressbar(top_frame, mode="indeterminate")

        # Main Tabbed Notebook Container
        self.main_notebook = ttk.Notebook(self)
        self.main_notebook.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # Tab 1: Validierungs-Log & Ausgabe
        self.tab_log = ttk.Frame(self.main_notebook, padding=5)
        self.main_notebook.add(self.tab_log, text=" 📋 Validierung & Log ")

        self.log_text = ScrolledText(
            self.tab_log, wrap="word", font=("Consolas", 10)
        )
        self.log_text.pack(fill="both", expand=True)

        # Tab 2: Beleg-Dashboard & Rezept-Baum (Master-Detail Split)
        self.tab_dashboard = ttk.Frame(self.main_notebook, padding=5)
        self.main_notebook.add(self.tab_dashboard, text=" 📊 Beleg-Dashboard & Rezept-Baum ")

        dash_paned = ttk.PanedWindow(self.tab_dashboard, orient="vertical")
        dash_paned.pack(fill="both", expand=True)

        self.dashboard_view = BelegDashboardFrame(
            dash_paned,
            on_select_beleg_cb=self._on_dashboard_beleg_selected,
            on_open_editor_cb=self._open_editor_for_beleg,
        )
        dash_paned.add(self.dashboard_view, weight=3)

        self.recipe_tree_view = RecipeTreeFrame(dash_paned)
        dash_paned.add(self.recipe_tree_view, weight=2)

        # Tab 3: Virtuelles Verordnungsblatt (Muster 13/18)
        self.tab_muster13 = ttk.Frame(self.main_notebook, padding=5)
        self.main_notebook.add(self.tab_muster13, text=" 📜 Virtuelles Verordnungsblatt (Muster 13/18) ")

        self.muster13_view = Muster13PreviewFrame(self.tab_muster13)
        self.muster13_view.pack(fill="both", expand=True)

        # Footer Action Toolbar
        footer_frame = ttk.Frame(self, padding=(10, 5))
        footer_frame.pack(fill="x", side="bottom")

        btn_ticket = ttk.Button(
            footer_frame, text="📋 Support-Bericht kopieren", command=self._copy_ticket_summary
        )
        btn_ticket.pack(side="left", padx=3)

        btn_html = ttk.Button(
            footer_frame, text="🌐 HTML-Bericht exportieren", command=self._export_html_report
        )
        btn_html.pack(side="left", padx=3)

        btn_copy_log = ttk.Button(
            footer_frame, text="📋 Log kopieren", command=self._copy_to_clipboard
        )
        btn_copy_log.pack(side="right", padx=3)

        btn_clear = ttk.Button(
            footer_frame, text="Löschen", command=self._clear_log
        )
        btn_clear.pack(side="right", padx=3)

    def _toggle_theme(self):
        current = theme_manager.get_current_theme()
        new_mode = "light" if current == "dark" else "dark"
        theme_manager.set_current_theme(new_mode)
        self._apply_theme()

    def _apply_theme(self):
        mode = theme_manager.apply_theme(self)
        colors = theme_manager.get_theme_colors(mode)

        if mode == "dark":
            self.btn_theme.config(text="☀️ Light Mode")
        else:
            self.btn_theme.config(text="🌙 Dark Mode")

        self.log_text.config(
            bg=colors["log_bg"],
            fg=colors["log_fg"],
            insertbackground=colors["log_fg"],
        )
        self.log_text.tag_config("ERROR", foreground=colors["log_error"])
        self.log_text.tag_config("OK", foreground=colors["log_ok"])
        self.log_text.tag_config("HEADER", foreground=colors["log_header"], font=("Consolas", 10, "bold"))

        if hasattr(self, "dashboard_view"):
            self.dashboard_view.apply_theme(mode)
        if hasattr(self, "muster13_view"):
            self.muster13_view.apply_theme(mode)

    def _on_out_dir_key_release(self, event=None):
        val = self.out_dir_entry.get().strip()
        self.user_selected_out_dir = bool(val)

    def _select_files(self):
        files = filedialog.askopenfilenames(
            title="ESOL-Dateien auswählen",
            filetypes=[("Alle Dateien", "*.*")]
        )
        if files:
            # Pfade durch Semikolon getrennt eintragen
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, "; ".join(files))
            self.path_entry.xview_moveto(1.0)
            self.path_entry.icursor(tk.END)
            # Automatisch das Verzeichnis der ersten Quelldatei als Ausgabeordner eintragen (falls nicht selbst gewählt)
            if not self.user_selected_out_dir or not self.out_dir_entry.get().strip():
                source_dir = os.path.dirname(files[0])
                if source_dir:
                    self.out_dir_entry.delete(0, tk.END)
                    self.out_dir_entry.insert(0, source_dir)
                    self.out_dir_entry.xview_moveto(1.0)
                    self.out_dir_entry.icursor(tk.END)

    def _select_directory(self):
        directory = filedialog.askdirectory(title="Batch-Ordner auswählen")
        if directory:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, directory)
            self.path_entry.xview_moveto(1.0)
            self.path_entry.icursor(tk.END)
            # Automatisch den Quellordner als Ausgabeordner eintragen (falls nicht selbst gewählt)
            if not self.user_selected_out_dir or not self.out_dir_entry.get().strip():
                self.out_dir_entry.delete(0, tk.END)
                self.out_dir_entry.insert(0, directory)
                self.out_dir_entry.xview_moveto(1.0)
                self.out_dir_entry.icursor(tk.END)

    def _select_out_directory(self):
        directory = filedialog.askdirectory(title="Ausgabeordner auswählen")
        if directory:
            self.out_dir_entry.delete(0, tk.END)
            self.out_dir_entry.insert(0, directory)
            self.out_dir_entry.xview_moveto(1.0)
            self.out_dir_entry.icursor(tk.END)
            self.user_selected_out_dir = True

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
        self.btn_correction.config(state=state)

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

    def _start_correction_dialog(self):
        self._open_correction_dialog(default_vk="02")

    def _open_correction_dialog(self, default_vk: str):
        raw_path = self.path_entry.get().strip()
        if not raw_path:
            messagebox.showwarning("Fehler", "Bitte wählen Sie eine Datei aus!")
            return

        # Take first file if multiple selected
        paths = [p.strip() for p in raw_path.split(";") if p.strip()]
        first_file = None
        for p in paths:
            if os.path.isfile(p):
                first_file = p
                break
            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for file in files:
                        if not file.endswith(".txt") and not file.endswith(".auf") and not file.startswith("."):
                            first_file = os.path.join(root, file)
                            break
                    if first_file:
                        break

        if not first_file:
            messagebox.showwarning("Fehler", "Keine gültige ESOL-Datei gefunden.")
            return

        from gui_correction_dialog import CorrectionSelectionDialog

        def on_generated(generated_path: str):
            self._clear_log()
            self._append_log(f"=== Korrekturdatei generiert: {os.path.basename(generated_path)} ===\n", tag="HEADER")
            self._append_log(f"Pfad: {generated_path}\n\n", tag="OK")
            # Automatically validate generated file
            cmd = [
                sys.executable,
                self.validate_script,
                generated_path,
                f"--stufe={self.stufe_var.get()}"
            ]
            if self.warnings_var.get():
                cmd.append("--warnings")
            self._append_log("=== Validierung der generierten Datei ===\n", tag="HEADER")
            self._execute_cmd(cmd)

        out_dir = self.out_dir_entry.get().strip() or None
        CorrectionSelectionDialog(
            self,
            file_path=first_file,
            default_vk=default_vk,
            output_dir=out_dir,
            on_complete_callback=on_generated,
        )

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

            out_dir = self.out_dir_entry.get().strip()

            for file_path in files_to_convert:
                cmd = [
                    sys.executable,
                    self.convert_script,
                    file_path,
                ]
                if out_dir:
                    cmd.extend(["--out-dir", out_dir])

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

            out_dir = self.out_dir_entry.get().strip()

            for file_path in files_to_process:
                cmd = [
                    sys.executable,
                    self.generate_auf_script,
                    file_path
                ]
                if out_dir:
                    cmd.extend(["--out-dir", out_dir])

                self._append_log(f"=== Generiere .auf: {os.path.basename(file_path)} ===\n", tag="HEADER")
                self._execute_cmd(cmd)
                self._append_log("\n" + "-" * 60 + "\n\n")

        finally:
            self.after(0, self._finish_process)

    def _run_correction_process(self, target_vk: str, path_input: str):
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
                self._append_log("Keine ESOL-Dateien zur Korrektur-Generierung gefunden.\n", tag="ERROR")
                return

            label = "Zuzahlungsforderung (VKZ 03)" if target_vk == "03" else "Korrekturrechnung (VKZ 04)"
            self._append_log(f"Erstelle {label} für {len(files_to_process)} Datei(en)...\n\n", tag="HEADER")

            out_dir = self.out_dir_entry.get().strip()

            for file_path in files_to_process:
                cmd = [
                    sys.executable,
                    self.correction_script,
                    file_path,
                    f"--type={target_vk}"
                ]
                if out_dir:
                    cmd.extend(["--out-dir", out_dir])

                self._append_log(f"=== Generiere VKZ {target_vk}: {os.path.basename(file_path)} ===\n", tag="HEADER")
                self._execute_cmd(cmd)
                self._append_log("\n" + "-" * 60 + "\n\n")

        finally:
            self.after(0, self._finish_process)

    def _execute_cmd(self, cmd: list[str]):
        # PYTHONIOENCODING erzwingt UTF-8 für die Standard-Streams (stdout/stderr) der GUI
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

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

    def _on_dashboard_beleg_selected(self, belegnr: str):
        b = next((x for x in self.last_belege_summary if str(x.get("belegnr")) == belegnr), None)
        if b:
            self.muster13_view.load_beleg(b, self.last_validation_errors)
        self.recipe_tree_view.focus_beleg(belegnr)

    def _open_editor_for_beleg(self, belegnr: str):
        if self.last_processed_file and os.path.isfile(self.last_processed_file):
            from vkz_correction_editor import VKZCorrectionEditorDialog

            def on_done(out_path: str):
                self._clear_log()
                self._append_log(f"=== Korrekturdatei generiert: {os.path.basename(out_path)} ===\n", tag="HEADER")
                self._append_log(f"Pfad: {out_path}\n\n", tag="OK")
                self._populate_support_tabs(out_path, [])

            VKZCorrectionEditorDialog(
                parent=self,
                file_path=self.last_processed_file,
                selected_belegnr_list=[belegnr],
                target_vk="02",
                on_complete_callback=on_done,
            )

    def _copy_ticket_summary(self):
        file_name = os.path.basename(self.last_processed_file) if self.last_processed_file else "ESOL-Datei"
        ticket_text = generate_ticket_summary(
            file_name=file_name,
            validation_errors=self.last_validation_errors,
            belege_summary=self.last_belege_summary,
        )
        self.clipboard_clear()
        self.clipboard_append(ticket_text)
        messagebox.showinfo("Support-Bericht", "Der Support-Bericht wurde erfolgreich in die Zwischenablage kopiert!")

    def _export_html_report(self):
        file_name = os.path.basename(self.last_processed_file) if self.last_processed_file else "ESOL-Datei"
        html_content = generate_html_report(
            file_name=file_name,
            validation_errors=self.last_validation_errors,
            belege_summary=self.last_belege_summary,
        )

        out_dir = self.out_dir_entry.get().strip()
        default_name = f"ESOL_Pruefbericht_{file_name}.html"

        if out_dir and os.path.isdir(out_dir):
            out_path = os.path.join(out_dir, default_name)
        else:
            out_path = filedialog.asksaveasfilename(
                title="HTML-Prüfbericht speichern",
                initialfile=default_name,
                defaultextension=".html",
                filetypes=[("HTML-Dateien", "*.html"), ("Alle Dateien", "*.*")],
            )

        if out_path:
            Path(out_path).write_text(html_content, encoding="utf-8")
            messagebox.showinfo("Export Erfolgreich", f"Der HTML-Prüfbericht wurde erfolgreich gespeichert:\n\n{out_path}")

    def _populate_support_tabs(self, file_path: str, errors: List[str]):
        if not os.path.isfile(file_path):
            return

        try:
            raw_content = read_esol_file_text(Path(file_path))
            belege = parse_esol_belege_summary(raw_content)

            self.last_processed_file = file_path
            self.last_belege_summary = belege
            self.last_validation_errors = errors

            # Populate Dashboard
            self.dashboard_view.load_data(belege, errors)

            # Populate Recipe Tree
            self.recipe_tree_view.load_tree(raw_content)

            # Populate Muster 13 preview with first Beleg
            if belege:
                self.muster13_view.load_beleg(belege[0], errors)
        except Exception as e:
            self._append_log(f"Konnte Support-Tabs für {file_path} nicht befüllen: {e}\n", tag="ERROR")

    def _finish_process(self):
        self.progress.stop()
        self.progress.grid_forget()
        self._set_buttons_state("normal")

        # Automatically parse and populate support tabs for the first valid input file
        raw_path = self.path_entry.get().strip()
        if raw_path:
            paths = [p.strip() for p in raw_path.split(";") if p.strip()]
            for p in paths:
                if os.path.isfile(p):
                    # Gather errors logged in output text
                    log_content = self.log_text.get("1.0", tk.END)
                    errors = [
                        line.strip()
                        for line in log_content.splitlines()
                        if ("FEHLER" in line or "UNGÜLTIG" in line or "Stufe" in line) and not line.startswith("===")
                    ]
                    self._populate_support_tabs(p, errors)
                    break


if __name__ == "__main__":
    multiprocessing.freeze_support()

    if len(sys.argv) > 1:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

        target_script = sys.argv[1]
        sys.argv.pop(1)

        if "validate" in target_script:
            import validate
            validate.main()
        elif "convert" in target_script:
            from tools import convert_utf8_to_iso
            convert_utf8_to_iso.main()
        elif "generate_auf" in target_script:
            from tools import generate_auf
            generate_auf.main()
        elif "generate_correction" in target_script:
            from tools import generate_correction
            generate_correction.main()
        else:
            print(f"Unbekanntes CLI-Skript: {target_script}", file=sys.stderr)
            sys.exit(1)
    else:
        app = EsolValidatorGUI()
        app.mainloop()