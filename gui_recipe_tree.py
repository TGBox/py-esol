"""
ESOL Rezept-Baum Viewer — Hierarchische Klartext-Darstellung der EDIFACT-Struktur
(UNB -> Nachricht -> Verordnung/Beleg -> Verordnungsdaten / Diagnosen / Leistungen)
mit Praxissprache, formatierten Werten und Feldnamen aus dem Schema.
"""

import tkinter as tk
from tkinter import ttk
from typing import Any, Dict, List, Optional

from support_helper import parse_esol_tree_nodes

# Bis zu dieser Tiefe wird beim Laden automatisch aufgeklappt
_AUTO_OPEN_TIEFE = 1


class RecipeTreeFrame(ttk.Frame):
    """Klartext-Rezept-Baum zur strukturierten Ansicht aller EDIFACT-Segmente."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent, padding=10)

        self.tree_nodes: List[Dict[str, Any]] = []
        # Flacher Index: iid -> {node, parent_iid, tiefe, suchtext}
        self._index: Dict[str, Dict[str, Any]] = {}

        self._setup_ui()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 10))

        ttk.Button(bar, text="➕ Alle aufklappen", command=self._expand_all).pack(side="left", padx=2)
        ttk.Button(bar, text="➖ Alle zuklappen", command=self._collapse_all).pack(side="left", padx=2)
        ttk.Button(bar, text="📋 Verordnungen", command=self._show_verordnungen).pack(side="left", padx=(10, 2))

        ttk.Label(bar, text=" Filter:").pack(side="left", padx=(15, 5))
        self.search_entry = ttk.Entry(bar, width=28)
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_tree())

        ttk.Button(bar, text="✖", width=3, command=self._clear_filter).pack(side="left")

        self.lbl_status = ttk.Label(bar, text="", font=("Segoe UI", 8))
        self.lbl_status.pack(side="right", padx=5)

        cols = ("details", "raw")
        self.tree = ttk.Treeview(self, columns=cols, selectmode="browse")

        self.tree.heading("#0", text="Struktur / Segment (Klartext)")
        self.tree.heading("details", text="Inhalte in Klartext")
        self.tree.heading("raw", text="Rohsegment (EDIFACT)")

        self.tree.column("#0", width=340, anchor="w", stretch=False)
        self.tree.column("details", width=520, anchor="w", stretch=True)
        self.tree.column("raw", width=280, anchor="w", stretch=False)

        sb_y = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sb_x = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        sb_y.pack(side="right", fill="y")
        sb_x.pack(side="bottom", fill="x")
        self.tree.pack(side="left", fill="both", expand=True)

    # ---------------------------------------------------------------- Laden

    def load_tree(self, raw_content: str):
        """Lädt den Rohinhalt und erstellt die Baumstruktur."""
        self._clear_filter_entry()
        self.tree_nodes = parse_esol_tree_nodes(raw_content)
        self._rebuild()

    def _rebuild(self, nur_treffer: Optional[set] = None):
        """Baut den Treeview neu auf. nur_treffer=None -> vollständiger Baum."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._index.clear()

        for node in self.tree_nodes:
            self._insert_node("", node, 0, nur_treffer)

        anzahl = len(self._index)
        if nur_treffer is None:
            self.lbl_status.config(text=f"{anzahl} Knoten")
        else:
            self.lbl_status.config(text=f"{anzahl} Treffer")

    def _insert_node(self, parent_iid: str, node: Dict[str, Any], tiefe: int,
                     nur_treffer: Optional[set]) -> Optional[str]:
        """
        Fügt einen Knoten samt Kindern rekursiv ein. Ist nur_treffer gesetzt, werden
        nur Knoten eingefügt, die selbst Treffer sind oder Treffer unterhalb haben.
        """
        iid = node["id"]
        if nur_treffer is not None and iid not in nur_treffer:
            return None

        self.tree.insert(
            parent_iid, "end", iid=iid,
            text=node.get("label", ""),
            values=(node.get("details", ""), node.get("raw", "")),
            open=(nur_treffer is not None) or tiefe < _AUTO_OPEN_TIEFE,
        )
        self._index[iid] = {"node": node, "parent": parent_iid, "tiefe": tiefe}

        for child in node.get("children", []) or []:
            self._insert_node(iid, child, tiefe + 1, nur_treffer)

        return iid

    # ---------------------------------------------------------------- Fokus

    def focus_beleg(self, belegnr: str):
        """Sucht den Beleg-Knoten mit der angegebenen Belegnummer, klappt ihn auf und markiert ihn."""
        if not belegnr:
            return

        treffer = self._finde_beleg_iid(self.tree_nodes, str(belegnr))
        if not treffer:
            return

        # Falls gefiltert ist, erst den vollständigen Baum wiederherstellen
        if not self.tree.exists(treffer):
            self._clear_filter_entry()
            self._rebuild()
            if not self.tree.exists(treffer):
                return

        parent = self.tree.parent(treffer)
        while parent:
            self.tree.item(parent, open=True)
            parent = self.tree.parent(parent)

        self.tree.item(treffer, open=True)
        self.tree.selection_set(treffer)
        self.tree.see(treffer)

    def _finde_beleg_iid(self, nodes: List[Dict[str, Any]], belegnr: str) -> Optional[str]:
        for node in nodes:
            if node.get("tag") == "INV":
                details = str(node.get("details", ""))
                label = str(node.get("label", ""))
                if belegnr in details or belegnr in label:
                    return node["id"]
            gefunden = self._finde_beleg_iid(node.get("children", []) or [], belegnr)
            if gefunden:
                return gefunden
        return None

    # -------------------------------------------------------------- Aktionen

    def _expand_all(self):
        for iid in self._index:
            if self.tree.exists(iid):
                self.tree.item(iid, open=True)

    def _collapse_all(self):
        for iid in self._index:
            if self.tree.exists(iid):
                self.tree.item(iid, open=False)

    def _show_verordnungen(self):
        """Klappt alle Belege bis einschließlich der Verordnungsdaten auf."""
        for iid, meta in self._index.items():
            if not self.tree.exists(iid):
                continue
            node = meta["node"]
            tag = node.get("tag", "")
            offen = meta["tiefe"] < 1 or tag in ("INV", "ZHE", "ZHI", "ZHK", "ZHH", "ZKT", "ZHB", "ZSP")
            self.tree.item(iid, open=offen)

    def _clear_filter_entry(self):
        self.search_entry.delete(0, tk.END)

    def _clear_filter(self):
        self._clear_filter_entry()
        self._rebuild()

    # ---------------------------------------------------------------- Filter

    def _filter_tree(self):
        term = self.search_entry.get().strip().lower()
        if not term:
            self._rebuild()
            return

        treffer: set = set()
        for node in self.tree_nodes:
            self._collect_matches(node, term, treffer)

        self._rebuild(nur_treffer=treffer)

    def _collect_matches(self, node: Dict[str, Any], term: str, treffer: set) -> bool:
        """
        Markiert Knoten, die den Suchbegriff enthalten. Trifft ein Kind zu, werden
        alle Elternknoten mit aufgenommen, damit der Pfad sichtbar bleibt.
        Trifft ein Elternknoten zu, bleibt sein gesamter Teilbaum sichtbar.
        """
        selbst = term in " ".join([
            str(node.get("label", "")),
            str(node.get("details", "")),
            str(node.get("raw", "")),
        ]).lower()

        kind_trefft = False
        for child in node.get("children", []) or []:
            if self._collect_matches(child, term, treffer):
                kind_trefft = True

        if selbst:
            self._mark_subtree(node, treffer)
        if selbst or kind_trefft:
            treffer.add(node["id"])
            return True
        return False

    def _mark_subtree(self, node: Dict[str, Any], treffer: set):
        treffer.add(node["id"])
        for child in node.get("children", []) or []:
            self._mark_subtree(child, treffer)
