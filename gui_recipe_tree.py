"""
ESOL Rezept-Baum Viewer — Hierarchische Klartext-Darstellung der EDIFACT-Struktur
(UNB -> SLGA -> INV -> BES) mit Praxissprache und formatierten Werten.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

from support_helper import parse_esol_tree_nodes


class RecipeTreeFrame(ttk.Frame):
    """
    Klartext-Rezept-Baum zur strukturierten Ansicht aller EDIFACT-Segmente.
    """

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=10)

        self.tree_nodes: List[Dict[str, Any]] = []

        self._setup_ui()

    def _setup_ui(self):
        # Toolbar
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))

        ttk.Button(bar, text="➕ Alle aufklappen", command=self._expand_all).pack(side="left", padx=2)
        ttk.Button(bar, text="➖ Alle zuklappen", command=self._collapse_all).pack(side="left", padx=2)

        ttk.Label(bar, text=" Filter:").pack(side="left", padx=(15, 5))
        self.search_entry = ttk.Entry(bar, width=25)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_tree())

        # Treeview
        cols = ("details", "raw")
        self.tree = ttk.Treeview(self, columns=cols, selectmode="browse")

        self.tree.heading("#0", text="Struktur / Segment (Klartext)")
        self.tree.heading("details", text="Inhalte & Währung/Datum")
        self.tree.heading("raw", text="Rohsegment (EDIFACT)")

        self.tree.column("#0", width=320, anchor="w")
        self.tree.column("details", width=380, anchor="w")
        self.tree.column("raw", width=250, anchor="w")

        sb_y = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb_x = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

    def load_tree(self, raw_content: str):
        """
        Lädt den Rohinhalt und erstellt die Baumstruktur.
        """
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.tree_nodes = parse_esol_tree_nodes(raw_content)

        for node in self.tree_nodes:
            parent_id = self.tree.insert(
                "",
                "end",
                iid=node["id"],
                text=node["label"],
                values=(node["details"], node["raw"]),
                open=True,
            )

            for child in node.get("children", []):
                self.tree.insert(
                    parent_id,
                    "end",
                    iid=child["id"],
                    text=child["label"],
                    values=(child["details"], child["raw"]),
                )

    def focus_beleg(self, belegnr: str):
        """
        Sucht den Beleg-Knoten mit der angegebenen Belegnummer, klappt ihn auf und markiert ihn.
        """
        if not belegnr:
            return

        for node in self.tree_nodes:
            if node.get("tag") == "INV" and belegnr in node.get("details", ""):
                node_id = node["id"]
                if self.tree.exists(node_id):
                    self.tree.item(node_id, open=True)
                    self.tree.selection_set(node_id)
                    self.tree.see(node_id)
                break

    def _expand_all(self):
        for item in self.tree.get_children():
            self.tree.item(item, open=True)
            for child in self.tree.get_children(item):
                self.tree.item(child, open=True)

    def _collapse_all(self):
        for item in self.tree.get_children():
            self.tree.item(item, open=False)

    def _filter_tree(self):
        term = self.search_entry.get().strip().lower()
        if not term:
            self._expand_all()
            return

        for item in self.tree.get_children():
            text = self.tree.item(item, "text").lower()
            vals = [str(v).lower() for v in self.tree.item(item, "values")]
            match = term in text or any(term in v for v in vals)

            if match:
                self.tree.item(item, open=True)
                self.tree.reattach(item, "", "end")
