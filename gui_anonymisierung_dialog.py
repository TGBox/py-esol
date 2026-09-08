"""
Export-Dialog für die Anonymisierung.

Wird vor jedem Bericht und vor jedem Export gezeigt: der Anwender entscheidet
jedes Mal neu, ob anonymisiert wird und welche Feldgruppen. Die Vorbelegung
kommt aus anonymisierung.FELDGRUPPEN — Versicherter und Arzt sind an, alles
andere aus.

Bewusst ein Dialog und keine dauerhafte Einstellung: welche Daten hinaus
dürfen, hängt vom Empfänger ab. Ein Ticket im eigenen Haus ist etwas anderes
als eine Datei an den Hersteller, und eine Einstellung, die vor Monaten
gesetzt wurde, weiß davon nichts.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional, Set

import anonymisierung
import theme_manager


class AnonymisierungsDialog(tk.Toplevel):
    """
    Fragt Umfang der Anonymisierung ab.

    Ergebnis nach dem Schließen in .ergebnis:
      None       — abgebrochen, es soll nichts exportiert werden
      set()      — ohne Anonymisierung exportieren (Klartext)
      {"..."}    — die gewählten Feldgruppen
    """

    def __init__(self, parent: tk.Widget, titel: str, zweck: str,
                 vorbelegung: Optional[Set[str]] = None):
        super().__init__(parent)
        self.title(titel)
        self.resizable(False, False)
        self.transient(parent)

        theme_manager.apply_theme(self)

        self.ergebnis: Optional[Set[str]] = None
        self._vars: Dict[str, tk.BooleanVar] = {}

        vorbelegung = (
            anonymisierung.standard_gruppen() if vorbelegung is None else set(vorbelegung)
        )

        rahmen = ttk.Frame(self, padding=15)
        rahmen.pack(fill="both", expand=True)

        ttk.Label(rahmen, text=zweck, font=("Segoe UI", 10, "bold"),
                  wraplength=560, justify="left").pack(anchor="w", pady=(0, 10))

        self.var_aktiv = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            rahmen,
            text="Daten anonymisieren",
            variable=self.var_aktiv,
            command=self._umschalten,
        ).pack(anchor="w", pady=(0, 8))

        self.gruppen_rahmen = ttk.LabelFrame(rahmen, text=" Was ersetzt wird ", padding=10)
        self.gruppen_rahmen.pack(fill="x")

        for name, gruppe in anonymisierung.FELDGRUPPEN.items():
            var = tk.BooleanVar(value=name in vorbelegung)
            self._vars[name] = var

            zeile = ttk.Frame(self.gruppen_rahmen)
            zeile.pack(fill="x", pady=(0, 6))

            ttk.Checkbutton(
                zeile, text=gruppe["label"], variable=var, width=34,
            ).pack(anchor="w")
            ttk.Label(
                zeile, text=gruppe["felder"], font=("Consolas", 8),
                wraplength=520, justify="left",
            ).pack(anchor="w", padx=(24, 0))
            if gruppe.get("hinweis"):
                ttk.Label(
                    zeile, text=gruppe["hinweis"], font=("Segoe UI", 8),
                    wraplength=520, justify="left",
                ).pack(anchor="w", padx=(24, 0))

        ttk.Label(
            rahmen,
            text="Pseudonyme sind innerhalb dieses Exports stabil — mehrere Belege "
                 "derselben Person bleiben zuordenbar. Über Exporte hinweg gelten "
                 "sie nicht.",
            font=("Segoe UI", 8), wraplength=560, justify="left",
        ).pack(anchor="w", pady=(10, 0))

        knopfleiste = ttk.Frame(rahmen)
        knopfleiste.pack(fill="x", pady=(12, 0))
        ttk.Button(knopfleiste, text="Abbrechen", command=self._abbrechen).pack(side="right")
        ttk.Button(knopfleiste, text="Exportieren", command=self._uebernehmen).pack(
            side="right", padx=(0, 6)
        )

        self._umschalten()

        # Modal erst nach dem Aufbau — grab_set auf ein noch nicht sichtbares
        # Fenster schlägt auf manchen Systemen fehl.
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _umschalten(self):
        """Die Feldgruppen sind nur wählbar, wenn überhaupt anonymisiert wird."""
        zustand = "normal" if self.var_aktiv.get() else "disabled"
        for kind in self.gruppen_rahmen.winfo_children():
            for enkel in kind.winfo_children():
                try:
                    enkel.configure(state=zustand)
                except tk.TclError:
                    pass

    def _uebernehmen(self):
        if not self.var_aktiv.get():
            self.ergebnis = set()
        else:
            self.ergebnis = {name for name, var in self._vars.items() if var.get()}
        self.destroy()

    def _abbrechen(self):
        self.ergebnis = None
        self.destroy()


def frage_anonymisierung(parent: tk.Widget, titel: str, zweck: str,
                         vorbelegung: Optional[Set[str]] = None) -> Optional[Set[str]]:
    """
    Zeigt den Dialog und wartet auf die Entscheidung.

    Rückgabe wie AnonymisierungsDialog.ergebnis: None bei Abbruch, sonst die
    gewählten Feldgruppen (leere Menge = Klartext).
    """
    dialog = AnonymisierungsDialog(parent, titel, zweck, vorbelegung)
    parent.wait_window(dialog)
    return dialog.ergebnis
