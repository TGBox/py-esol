"""
ESOL Visuelle Rezept-Vorschau — Virtuelles Verordnungsblatt im Stil des Musters 13/18
(Heilmittelverordnung).

Zeigt die Verordnung so, wie sie auf dem Papierformular steht:
  * Kopf: Krankenkasse & Versicherter
  * Verordnung: verordnender Arzt (BSNR/LANR), Verordnungsdatum, Verordnungsart,
    Diagnosegruppe, Leitsymptomatik, ICD-10-Diagnosen, Therapiefrequenz,
    Therapiebericht, Hausbesuch, Dringlichkeit, Genehmigung, Ursprungsrechnung
  * Behandlungsverlauf: Leistungen gruppiert (Anzahl Termine, Zeitraum, Summen),
    Einzeltermine aufklappbar
  * Abrechnung: Kassenanteil / Zuzahlungs-Aufschlüsselung
  * Hinweisleiste: Plausibilitätsprobleme der Verordnung + Validierungsfehler
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List, Optional

import codelisten
import theme_manager
import verordnung as vo
from support_helper import translate_error

_MONO = ("Consolas", 10)
_MONO_B = ("Consolas", 10, "bold")
_UI = ("Segoe UI", 9)
_UI_B = ("Segoe UI", 9, "bold")

_STUFE_ICON = {"fehler": "⛔", "warnung": "⚠️", "info": "ℹ️"}
_STUFE_RANG = {"fehler": 0, "warnung": 1, "info": 2}


class ScrollableFrame(ttk.Frame):
    """Vertikal scrollbarer Container — das Verordnungsblatt ist höher als der Tab."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, padding=15)

        self._window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Mausrad: einmalig anwenden-weit registrieren (add="+" lässt andere
        # Bindings unberührt) und im Handler prüfen, ob das Ereignis wirklich
        # zu diesem Container gehört. So bleibt das Scrollen in inneren
        # Treeviews/Textfeldern denen selbst überlassen.
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.bind_all(seq, self._on_wheel, add="+")

    def _on_inner_configure(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)

    def _on_wheel(self, event):
        widget = getattr(event, "widget", None)
        if not self._handles(widget):
            return

        if getattr(event, "num", None) in (4, 5):
            schritte = -1 if event.num == 4 else 1
        else:
            schritte = int(-1 * (getattr(event, "delta", 0) / 120)) or 0
        if schritte:
            self.canvas.yview_scroll(schritte, "units")

    def _handles(self, widget) -> bool:
        """
        True, wenn das Mausrad-Ereignis diesen Container scrollen soll:
        das Widget muss innerhalb liegen und darf nicht selbst scrollbar sein.
        """
        if widget is None:
            return False
        try:
            if not str(widget).startswith(str(self)):
                return False
        except Exception:
            return False
        # Eigene Scrollbereiche (Treeview, Text, Listbox, Canvas) selbst scrollen lassen
        node = widget
        while node is not None and str(node) != str(self):
            if isinstance(node, (ttk.Treeview, tk.Text, tk.Listbox)):
                return False
            node = getattr(node, "master", None)
        return True

    def scroll_to_top(self):
        self.canvas.yview_moveto(0.0)

    def apply_theme(self, colors: Dict[str, str]):
        self.canvas.configure(background=colors["bg"])


class Muster13PreviewFrame(ttk.Frame):
    """Formularbasierter Rezept-Viewer im Layout der Heilmittelverordnung (Muster 13/18)."""

    def __init__(self, parent: tk.Widget):
        super().__init__(parent)

        self.current_beleg: Optional[Dict[str, Any]] = None
        self.validation_errors: List[str] = []
        self._detail_labels: Dict[str, ttk.Label] = {}

        self._setup_ui()

    # ------------------------------------------------------------------ UI

    def _setup_ui(self):
        self.scroller = ScrollableFrame(self)
        self.scroller.pack(fill="both", expand=True)
        root = self.scroller.inner

        self._build_title(root)
        self._build_hinweise(root)
        self._build_versicherter(root)
        self._build_verordnung(root)
        self._build_positionen(root)
        self._build_summen(root)
        self._build_footer(root)

    def _build_title(self, root: ttk.Frame):
        title_bar = ttk.Frame(root)
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

    def _build_hinweise(self, root: ttk.Frame):
        """Hinweisleiste: Verordnungs-Plausibilität + zugeordnete Validierungsfehler."""
        self.hinweis_frame = ttk.LabelFrame(root, text=" Hinweise zu dieser Verordnung ", padding=8)
        # wird in load_beleg() bei Bedarf eingeblendet

        self.hinweis_box = tk.Text(
            self.hinweis_frame, wrap="word", font=_UI, height=4, state="disabled",
            borderwidth=0, highlightthickness=0,
        )
        self.hinweis_box.pack(fill="both", expand=True)

    def _build_versicherter(self, root: ttk.Frame):
        head = ttk.LabelFrame(root, text=" Krankenkasse & Versicherter ", padding=10)
        head.pack(fill="x", pady=(0, 10))
        for col in (1, 3):
            head.columnconfigure(col, weight=1)
        self._versicherter_box = head

        self._grid_row(head, 0, 0, "Kostenträger-IK:", "ik", mono=True, bold=True)
        self._grid_row(head, 0, 2, "Versicherter Name:", "name", mono=True, bold=True)
        self._grid_row(head, 1, 0, "Krankenkassen-IK:", "ik_kasse", mono=True)
        self._grid_row(head, 1, 2, "Geburtsdatum:", "geb", mono=True)
        self._grid_row(head, 2, 0, "Versichertennummer:", "versnr", mono=True)
        self._grid_row(head, 2, 2, "Versichertenstatus:", "versstatus", mono=True)
        self._grid_row(head, 3, 0, "Rechnung:", "rechnung", mono=True)
        self._grid_row(head, 3, 2, "Zuzahlungsstatus:", "zuz_status", bold=True)

    def _build_verordnung(self, root: ttk.Frame):
        box = ttk.LabelFrame(root, text=" Verordnung / verordnender Arzt ", padding=10)
        box.pack(fill="x", pady=(0, 10))
        for col in (1, 3):
            box.columnconfigure(col, weight=1)

        self._grid_row(box, 0, 0, "Verordnungsdatum:", "vo_datum", mono=True, bold=True)
        self._grid_row(box, 0, 2, "Verordnender Arzt:", "vo_arzt", mono=True)
        self._grid_row(box, 1, 0, "Verordnungsart:", "vo_art")
        self._grid_row(box, 1, 2, "Diagnosegruppe:", "vo_diagnosegruppe")
        self._grid_row(box, 2, 0, "Leitsymptomatik:", "vo_leitsym")
        self._grid_row(box, 2, 2, "Therapiefrequenz:", "vo_frequenz")
        self._grid_row(box, 3, 0, "Therapiebericht:", "vo_bericht")
        self._grid_row(box, 3, 2, "Hausbesuch:", "vo_hausbesuch")
        self._grid_row(box, 4, 0, "Dringlichkeit:", "vo_dringlich")
        self._grid_row(box, 4, 2, "Heilmittel-Bereich:", "vo_hmbereich")
        self._grid_row(box, 5, 0, "Verordnungsbesonderh.:", "vo_besonderheiten")
        self._grid_row(box, 5, 2, "Unfall / BVG:", "vo_unfall")

        # Volle Breite: Freitexte, Diagnosen, Genehmigung, Ursprungsrechnung
        self._grid_wide(box, 6, "Individuelle Leitsympt.:", "vo_ind_leitsym")
        self._grid_wide(box, 7, "ICD-10 Diagnose(n):", "vo_diagnosen", mono=True)
        self._grid_wide(box, 8, "Genehmigung (SKZ):", "vo_genehmigung", mono=True)
        self._grid_wide(box, 9, "Ursprungsrechnung (URI):", "vo_uri", mono=True)
        self._grid_wide(box, 10, "Freitext (TXT):", "vo_freitext")

        # Rohfelder für Leistungsbereiche ohne ZHE (Hilfsmittel, HKP, ...)
        self.lbl_vo_fremdsegment = ttk.Label(box, text="", font=_UI, wraplength=900, justify="left")
        self._fremdsegment_sichtbar = False

    def _build_positionen(self, root: ttk.Frame):
        self.pos_frame = ttk.LabelFrame(root, text=" Verordnete Heilmittel / Behandlungsverlauf ", padding=10)
        self.pos_frame.pack(fill="both", expand=True, pady=(0, 10))

        bar = ttk.Frame(self.pos_frame)
        bar.pack(fill="x", pady=(0, 6))

        self.lbl_behandlung = ttk.Label(bar, text="Behandlungszeitraum: —", font=_UI_B)
        self.lbl_behandlung.pack(side="left")

        ttk.Button(bar, text="➖ Termine zuklappen", command=self._collapse_positions).pack(side="right", padx=2)
        ttk.Button(bar, text="➕ Einzeltermine anzeigen", command=self._expand_positions).pack(side="right", padx=2)

        cols = ("code", "zeitraum", "termine", "menge", "einzel", "gesamt", "zuzahlung")
        self.pos_tree = ttk.Treeview(self.pos_frame, columns=cols, height=10, selectmode="browse")

        self.pos_tree.heading("#0", text="Leistung")
        self.pos_tree.heading("code", text="Positionsnr.")
        self.pos_tree.heading("zeitraum", text="Zeitraum / Datum")
        self.pos_tree.heading("termine", text="Termine")
        self.pos_tree.heading("menge", text="Menge")
        self.pos_tree.heading("einzel", text="Einzel €")
        self.pos_tree.heading("gesamt", text="Gesamt €")
        self.pos_tree.heading("zuzahlung", text="Zuzahlung €")

        self.pos_tree.column("#0", width=300, anchor="w", stretch=True)
        self.pos_tree.column("code", width=90, anchor="w", stretch=False)
        self.pos_tree.column("zeitraum", width=180, anchor="center", stretch=False)
        self.pos_tree.column("termine", width=70, anchor="e", stretch=False)
        self.pos_tree.column("menge", width=70, anchor="e", stretch=False)
        self.pos_tree.column("einzel", width=90, anchor="e", stretch=False)
        self.pos_tree.column("gesamt", width=100, anchor="e", stretch=False)
        self.pos_tree.column("zuzahlung", width=95, anchor="e", stretch=False)

        sb = ttk.Scrollbar(self.pos_frame, orient="vertical", command=self.pos_tree.yview)
        self.pos_tree.configure(yscrollcommand=sb.set)

        self.pos_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_summen(self, root: ttk.Frame):
        sums = ttk.LabelFrame(root, text=" Abrechnung & Zuzahlungs-Aufschlüsselung ", padding=10)
        sums.pack(fill="x", pady=(0, 10))
        for col in range(3):
            sums.columnconfigure(col, weight=1)

        pad = {"padx": 8, "pady": 4}
        self.lbl_brutto = ttk.Label(sums, text="Bruttobetrag: —", font=_MONO_B)
        self.lbl_brutto.grid(row=0, column=0, sticky="w", **pad)

        self.lbl_proz_zuz = ttk.Label(sums, text="Prozentuale Zuzahlung: —", font=_MONO)
        self.lbl_proz_zuz.grid(row=0, column=1, sticky="w", **pad)

        self.lbl_pausch_zuz = ttk.Label(sums, text="Pauschale Zuzahlung: —", font=_MONO)
        self.lbl_pausch_zuz.grid(row=0, column=2, sticky="w", **pad)

        self.lbl_total_zuz = ttk.Label(sums, text="Gesamte Zuzahlung: —", font=_MONO_B, foreground="#d9534f")
        self.lbl_total_zuz.grid(row=1, column=0, sticky="w", **pad)

        self.lbl_netto = ttk.Label(sums, text="Kassenanteil (Netto): —", font=_MONO_B, foreground="#5cb85c")
        self.lbl_netto.grid(row=1, column=1, columnspan=2, sticky="w", **pad)

    def _build_footer(self, root: ttk.Frame):
        footer = ttk.Frame(root)
        footer.pack(fill="x")

        ttk.Button(footer, text="🔄 Codelisten neu laden", command=self._reload_codelisten).pack(side="left")

        self.lbl_codelisten = ttk.Label(footer, text="", font=("Segoe UI", 8), foreground="#888888")
        self.lbl_codelisten.pack(side="left", padx=10)
        self._update_codelisten_hint()

    # ------------------------------------------------------- Layout-Helfer

    def _grid_row(self, parent, row: int, col: int, caption: str, key: str,
                  mono: bool = False, bold: bool = False):
        pad = {"padx": 8, "pady": 3}
        ttk.Label(parent, text=caption, font=_UI).grid(row=row, column=col, sticky="w", **pad)
        font = (_MONO_B if bold else _MONO) if mono else (_UI_B if bold else _UI)
        lbl = ttk.Label(parent, text="—", font=font)
        lbl.grid(row=row, column=col + 1, sticky="w", **pad)
        self._register(key, lbl)

    def _grid_wide(self, parent, row: int, caption: str, key: str, mono: bool = False):
        pad = {"padx": 8, "pady": 3}
        cap = ttk.Label(parent, text=caption, font=_UI)
        cap.grid(row=row, column=0, sticky="nw", **pad)
        lbl = ttk.Label(parent, text="—", font=_MONO if mono else _UI, wraplength=760, justify="left")
        lbl.grid(row=row, column=1, columnspan=3, sticky="w", **pad)
        self._register(key, lbl)
        # Merken, um ganze Zeilen ausblenden zu können
        self._detail_labels[f"{key}__caption"] = cap

    def _register(self, key: str, lbl: ttk.Label):
        """
        Label unter seinem Schlüssel ablegen und zusätzlich als Attribut lbl_<key>
        veröffentlichen (z. B. self.lbl_name) — so bleiben bestehende Zugriffe gültig.
        """
        self._detail_labels[key] = lbl
        setattr(self, f"lbl_{key}", lbl)

    def _set(self, key: str, value: str):
        lbl = self._detail_labels.get(key)
        if lbl is not None:
            lbl.config(text=value if value else "—")

    def _set_wide_visible(self, key: str, visible: bool):
        """Blendet eine volle Zeile (Caption + Wert) ein oder aus."""
        cap = self._detail_labels.get(f"{key}__caption")
        lbl = self._detail_labels.get(key)
        if cap is None or lbl is None:
            return
        if visible:
            cap.grid()
            lbl.grid()
        else:
            cap.grid_remove()
            lbl.grid_remove()

    # ------------------------------------------------------------- Theming

    def apply_theme(self, mode: Optional[str] = None):
        colors = theme_manager.get_theme_colors(mode)
        active_mode = mode or theme_manager.get_current_theme()

        self.scroller.apply_theme(colors)

        self.hinweis_box.config(
            bg=colors["card_bg"], fg=colors["fg"], insertbackground=colors["fg"]
        )
        self.hinweis_box.tag_config("fehler", foreground=colors["log_error"], font=_UI_B)
        self.hinweis_box.tag_config("warnung", foreground=colors["log_header"], font=_UI_B)
        self.hinweis_box.tag_config("info", foreground=colors["fg_subdued"])

        self.pos_tree.tag_configure("gruppe", font=_MONO_B)
        self.pos_tree.tag_configure("termin", foreground=colors["fg_subdued"], font=("Consolas", 9))
        self.pos_tree.tag_configure("summe", font=_MONO_B, background=colors["tree_heading_bg"])

        self.lbl_codelisten.config(foreground=colors["fg_subdued"])

        if active_mode == "dark":
            self.lbl_beleg_nr.config(foreground=colors["log_header"])
            self.lbl_total_zuz.config(foreground=colors["log_error"])
            self.lbl_netto.config(foreground=colors["log_ok"])
        else:
            self.lbl_beleg_nr.config(foreground="#0275d8")
            self.lbl_total_zuz.config(foreground="#d9534f")
            self.lbl_netto.config(foreground="#5cb85c")

    # ---------------------------------------------------------- Codelisten

    def _update_codelisten_hint(self):
        path = codelisten.source_path()
        err = codelisten.last_error()
        if err:
            self.lbl_codelisten.config(text=f"Codelisten fehlerhaft: {err}")
        elif path:
            self.lbl_codelisten.config(text=f"Klartexte aus: {path}")
        else:
            self.lbl_codelisten.config(
                text="Keine data/codelisten.json gefunden — Codes werden ohne Klartext angezeigt."
            )

    def _reload_codelisten(self):
        codelisten.reload()
        self._update_codelisten_hint()
        err = codelisten.last_error()
        if err:
            messagebox.showwarning("Codelisten", f"Codelisten konnten nicht gelesen werden:\n{err}")
            return
        if self.current_beleg:
            # Klartexte im Beleg neu auflösen und Ansicht aktualisieren
            zhe = self.current_beleg.get("verordnung") or {}
            if not zhe.get("fehlt") and zhe.get("rohfelder"):
                self.current_beleg["verordnung"] = vo.decode_zhe(zhe["rohfelder"])
            self.current_beleg["positionsgruppen"] = vo.gruppiere_positionen(
                self.current_beleg.get("positions", [])
            )
            self.load_beleg(self.current_beleg, self.validation_errors)

    # -------------------------------------------------------------- Laden

    def load_beleg(self, beleg: Dict[str, Any], validation_errors: Optional[List[str]] = None):
        """Befüllt das virtuelle Verordnungsblatt mit den Daten des ausgewählten Belegs."""
        self.current_beleg = beleg
        self.validation_errors = validation_errors or []

        b_nr = str(beleg.get("belegnr", "-"))
        self.lbl_beleg_nr.config(text=f"Beleg-Nr. {b_nr}")

        self._fill_versicherter(beleg)
        self._fill_verordnung(beleg)
        self._fill_positionen(beleg)
        self._fill_summen(beleg)
        self._fill_hinweise(beleg, b_nr)

        self.scroller.scroll_to_top()

    def _fill_versicherter(self, beleg: Dict[str, Any]):
        name = f"{beleg.get('nachname', '')}, {beleg.get('vorname', '')}".strip(", ")
        self._set("name", name)
        self._set("versnr", str(beleg.get("versichertennummer", "")))
        self._set("geb", vo.fmt_datum(beleg.get("geburtstag", "")))
        self._set("versstatus", str(beleg.get("versichertenstatus", "")))

        # IKs und Rechnungsdaten stammen aus FKT/REC der Nachricht, nicht aus dem INV-Block.
        self._set("ik", str(beleg.get("kostentraeger_ik", "")))
        self._set("ik_kasse", str(beleg.get("krankenkasse_ik", "")))

        rg_nr = str(beleg.get("rechnungsnummer", ""))
        rg_dat = vo.fmt_datum(beleg.get("rechnungsdatum", ""))
        vk = str(beleg.get("verarbeitungskennzeichen", ""))
        rechnung = " ".join(p for p in [
            f"Nr. {rg_nr}" if rg_nr else "",
            f"vom {rg_dat}" if rg_dat else "",
            f"(VK {vk})" if vk else "",
        ] if p)
        self._set("rechnung", rechnung)

        zhe = beleg.get("verordnung") or {}
        self._set("zuz_status", zhe.get("zuzahlungskennzeichen_text")
                  or codelisten.describe("zuzahlungskennzeichen", beleg.get("zuzahlungskennzeichen")))

    def _fill_verordnung(self, beleg: Dict[str, Any]):
        zhe: Dict[str, Any] = beleg.get("verordnung") or vo.leeres_zhe()

        self._set("vo_datum", zhe.get("verordnungsdatum_text"))
        self._set("vo_arzt", zhe.get("arzt_text"))
        self._set("vo_art", zhe.get("verordnungsart_text"))
        self._set("vo_diagnosegruppe", zhe.get("diagnosegruppe_text"))
        self._set("vo_leitsym", zhe.get("leitsymptomatik_text"))
        self._set("vo_frequenz", zhe.get("therapiefrequenz_text"))
        self._set("vo_bericht", zhe.get("therapiebericht_text"))
        self._set("vo_hausbesuch", zhe.get("hausbesuch_text"))
        self._set("vo_dringlich", zhe.get("dringlich_text"))
        self._set("vo_hmbereich", zhe.get("heilmittelbereich_text"))
        self._set("vo_besonderheiten", zhe.get("verordnungsbesonderheiten_text"))

        unfall = zhe.get("unfallkennzeichen_text") or "—"
        bvg = zhe.get("bvg_text") or "—"
        self._set("vo_unfall", f"{unfall}  |  BVG: {bvg}")

        # Optionale Zeilen nur zeigen, wenn Inhalt vorhanden ist
        ind = zhe.get("ind_leitsymptomatik", "")
        self._set("vo_ind_leitsym", ind)
        self._set_wide_visible("vo_ind_leitsym", bool(ind))

        diagnosen = beleg.get("diagnosen") or []
        dia_text = "\n".join(
            f"{d.get('code', '')}" + (f"  —  {d['text']}" if d.get("text") else "")
            for d in diagnosen
        )
        self._set("vo_diagnosen", dia_text or "keine Diagnose im Beleg (DIA fehlt)")
        self._set_wide_visible("vo_diagnosen", True)

        skz = beleg.get("genehmigung") or []
        skz_text = "\n".join(
            f"{s.get('kennzeichen', '') or '—'}  vom {vo.fmt_datum(s.get('datum')) or '—'}"
            f"  (Art: {codelisten.describe('genehmigungsart', s.get('art'))})"
            for s in skz
        )
        self._set("vo_genehmigung", skz_text)
        self._set_wide_visible("vo_genehmigung", bool(skz))

        uri = beleg.get("ursprungsrechnung") or []
        self._set("vo_uri", "\n".join(uri))
        self._set_wide_visible("vo_uri", bool(uri))

        txt = beleg.get("freitexte") or []
        self._set("vo_freitext", "\n".join(txt))
        self._set_wide_visible("vo_freitext", bool(txt))

        # Leistungsbereiche ohne ZHE: Rohfelder des vorhandenen Z-Segments zeigen
        seg_tag = beleg.get("verordnung_segment_tag", "")
        felder = beleg.get("verordnung_felder") or []
        if zhe.get("fehlt") and seg_tag and seg_tag != "ZHE" and felder:
            text = f"Verordnungsdaten aus Segment {seg_tag}:\n" + "\n".join(
                f"  • {row['name']}: {row['value']}" for row in felder
            )
            self.lbl_vo_fremdsegment.config(text=text)
            self.lbl_vo_fremdsegment.grid(row=11, column=0, columnspan=4, sticky="w", padx=8, pady=(6, 3))
            self._fremdsegment_sichtbar = True
        elif self._fremdsegment_sichtbar:
            self.lbl_vo_fremdsegment.grid_remove()
            self._fremdsegment_sichtbar = False

    def _fill_positionen(self, beleg: Dict[str, Any]):
        for item in self.pos_tree.get_children():
            self.pos_tree.delete(item)

        uebersicht = beleg.get("behandlung") or vo.behandlungsuebersicht(beleg.get("positions", []))
        self.lbl_behandlung.config(
            text=f"Behandlungszeitraum: {uebersicht.get('zeitraum_text', '—')}   ·   "
                 f"{uebersicht.get('anzahl_behandlungstage', 0)} Behandlungstage   ·   "
                 f"{uebersicht.get('anzahl_positionen', 0)} Einzelpositionen"
        )

        gruppen = beleg.get("positionsgruppen")
        if gruppen is None:
            gruppen = vo.gruppiere_positionen(beleg.get("positions", []))

        abr = str(beleg.get("abrechnungscode", ""))
        summe_betrag = 0.0
        summe_zuz = 0.0

        for g_idx, g in enumerate(gruppen):
            klartext = g.get("code_klartext") or f"ohne Klartext ({codelisten.KEIN_KLARTEXT})"
            label = f"{g['tag']}  {klartext}"
            if g.get("tarif_kz"):
                label += f"   [{g.get('abr_code', '')}:{g['tarif_kz']}]"

            parent = self.pos_tree.insert(
                "", "end", iid=f"g{g_idx}", text=label, open=False, tags=("gruppe",),
                values=(
                    g["code"],
                    g["zeitraum_text"],
                    f"{g['anzahl_termine']}×",
                    vo.fmt_menge(g["menge_gesamt"]),
                    vo.fmt_betrag(g["einzelbetrag"]),
                    vo.fmt_betrag(g["betrag_gesamt"]),
                    vo.fmt_betrag(g["zuzahlung_gesamt"]),
                ),
            )
            summe_betrag += g["betrag_gesamt"]
            summe_zuz += g["zuzahlung_gesamt"]

            for t_idx, t in enumerate(g.get("termine", [])):
                self.pos_tree.insert(
                    parent, "end", iid=f"g{g_idx}t{t_idx}",
                    text=f"    Termin {t_idx + 1}", tags=("termin",),
                    values=(
                        t.get("code", ""),
                        vo.fmt_datum(t.get("datum")) or "—",
                        "",
                        vo.fmt_menge(t.get("anzahl")),
                        vo.fmt_betrag(t.get("einzelbetrag")),
                        vo.fmt_betrag(t.get("gesamtbetrag")),
                        vo.fmt_betrag(t.get("zuzahlung_gesamt", t.get("zuzahlung"))),
                    ),
                )

        if gruppen:
            self.pos_tree.insert(
                "", "end", iid="summe", text="Summe der Positionen", tags=("summe",),
                values=("", "", "", "", "", vo.fmt_betrag(summe_betrag), vo.fmt_betrag(summe_zuz)),
            )

    def _fill_summen(self, beleg: Dict[str, Any]):
        brutto = float(beleg.get("brutto", 0.0) or 0.0)
        proz = float(beleg.get("zuzahlung_proz", 0.0) or 0.0)
        pausch = float(beleg.get("zuzahlung_pausch", 0.0) or 0.0)
        total = float(beleg.get("total_zuzahlung", 0.0) or 0.0)
        netto = round(brutto - total, 2)

        self.lbl_brutto.config(text=f"Bruttobetrag: {vo.fmt_betrag(brutto)}")
        self.lbl_proz_zuz.config(text=f"Prozentuale Zuzahlung: {vo.fmt_betrag(proz)}")
        self.lbl_pausch_zuz.config(text=f"Pauschale Zuzahlung: {vo.fmt_betrag(pausch)}")
        self.lbl_total_zuz.config(text=f"Gesamte Zuzahlung: {vo.fmt_betrag(total)}")
        self.lbl_netto.config(text=f"Kassenanteil (Netto): {vo.fmt_betrag(netto)}")

    def _fill_hinweise(self, beleg: Dict[str, Any], b_nr: str):
        hinweise: List[Dict[str, str]] = list(beleg.get("verordnung_hinweise") or [])

        # Validierungsfehler, die diese Belegnummer nennen, mit aufnehmen
        for err in self.validation_errors:
            if b_nr and b_nr in err:
                trans = translate_error(err)
                hinweise.append({
                    "stufe": "fehler",
                    "text": f"{trans['title']} — {trans['action']}",
                })

        if not hinweise:
            self.hinweis_frame.pack_forget()
            return

        hinweise.sort(key=lambda h: _STUFE_RANG.get(h.get("stufe", "info"), 3))

        self.hinweis_box.config(state="normal")
        self.hinweis_box.delete("1.0", tk.END)
        for h in hinweise:
            stufe = h.get("stufe", "info")
            icon = _STUFE_ICON.get(stufe, "•")
            self.hinweis_box.insert(tk.END, f"{icon} {h.get('text', '')}\n", stufe)
        self.hinweis_box.config(state="disabled", height=min(max(len(hinweise), 2), 8))

        # direkt unter der Titelzeile, oberhalb der Versichertendaten einblenden
        self.hinweis_frame.pack(fill="x", pady=(0, 10), before=self._versicherter_box)

    # ----------------------------------------------------------- Aktionen

    def _expand_positions(self):
        for item in self.pos_tree.get_children():
            self.pos_tree.item(item, open=True)

    def _collapse_positions(self):
        for item in self.pos_tree.get_children():
            self.pos_tree.item(item, open=False)
