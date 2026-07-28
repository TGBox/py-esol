from typing import Dict, List, Optional, Any


class SchemaRegistry:
    """
    Zentrale Registrierung, die Segment-Tags und Nachrichtentypen ihren Schema-Definitionen zuordnet.
    
    Für Felder, die sich zwischen SLGA- und SLLA-Kontexten unterscheiden (z. B. FKT),
    bietet die Registry kontextspezifische Suchen.
    """

    def __init__(self) -> None:
        # Standardmäßige (kontextfreie) Segment-Schemas, indiziert nach Tag
        self._segments: Dict[str, 'SegmentDefinition'] = {}
        
        # Kontextspezifische Overrides: {message_type: {tag: definition}}
        self._context_overrides: Dict[str, Dict[str, 'SegmentDefinition']] = {}
        
        # Segment-Reihenfolge-Definitionen, indiziert nach Nachrichtentyp
        self._segment_orders: Dict[str, List[Dict[str, Any]]] = {}

    def register(self, definition: 'SegmentDefinition', message_type: Optional[str] = None) -> None:
        """
        Registriert eine SegmentDefinition, optional für einen spezifischen Nachrichtentyp.
        """
        if message_type is not None:
            if message_type not in self._context_overrides:
                self._context_overrides[message_type] = {}
            self._context_overrides[message_type][definition.tag] = definition
        else:
            self._segments[definition.tag] = definition

    def get(self, tag: str, message_type: Optional[str] = None) -> Optional['SegmentDefinition']:
        """
        Sucht eine SegmentDefinition, optional innerhalb eines Nachrichtentyp-Kontexts.
        Kontextspezifische Overrides haben Vorrang.
        """
        if message_type is not None and message_type in self._context_overrides:
            if tag in self._context_overrides[message_type]:
                return self._context_overrides[message_type][tag]
        
        return self._segments.get(tag)

    def register_segment_order(self, message_type: str, order: List[Dict[str, Any]]) -> None:
        """
        Registriert die erwartete Segment-Reihenfolge für einen Nachrichtentyp.
        """
        self._segment_orders[message_type] = order

    def get_segment_order(self, message_type: str) -> Optional[List[Dict[str, Any]]]:
        """
        Gibt die Segment-Reihenfolge für einen Nachrichtentyp zurück.
        """
        return self._segment_orders.get(message_type)

    def is_known_tag(self, tag: str) -> bool:
        """
        Prüft, ob ein Tag bekannt ist (in irgendeinem Kontext).
        """
        if tag in self._segments:
            return True
        for overrides in self._context_overrides.values():
            if tag in overrides:
                return True
        return False

    def get_all_tags(self) -> List[str]:
        """
        Gibt alle bekannten Segment-Tags zurück.
        """
        tags = set(self._segments.keys())
        for overrides in self._context_overrides.values():
            tags.update(overrides.keys())
        return list(tags)

# ========================================================================
# SegmentDefinition (basierend auf Source 2)
# ========================================================================
class SegmentDefinition:
    """
    Beschreibt die Felder eines einzelnen ESOL/EDIFACT-Segmenttyps.
    """
    
    def __init__(self, tag: str, fields: List[Dict[str, Any]]):
        self.tag = tag
        self.fields = fields

    def get_field(self, index: int) -> Optional[Dict[str, Any]]:
        """
        Gibt die Felddefinition an einer bestimmten 0-basierten Position (nach dem Tag) zurück.
        """
        if 0 <= index < len(self.fields):
            return self.fields[index]
        return None

    def field_count(self) -> int:
        """
        Anzahl der definierten Felder (ohne das Tag).
        """
        return len(self.fields)

    def mandatory_field_count(self) -> int:
        """
        Anzahl der Pflichtfelder (Muss-Felder).
        """
        count = 0
        for field in self.fields:
            if field.get('art') == 'M':
                count += 1
        return count

    def last_mandatory_field_index(self) -> int:
        """
        Gibt den Index des letzten Pflichtfelds (0-basiert) zurück.
        Gibt -1 zurück, wenn keine Pflichtfelder existieren.
        """
        last = -1
        for i, field in enumerate(self.fields):
            if field.get('art') == 'M':
                last = i
        return last


# ========================================================================
# SchemaFactory (basierend auf Source 1)
# ========================================================================
class SchemaFactory:
    """
    Baut und liefert eine SchemaRegistry, die mit allen Segmentdefinitionen 
    für das ESOL-Format nach Technischer Anlage 1 TP5 V21, Leistungsbereich B (Heilmittel) vorbelegt ist.
    """

    @classmethod
    def create(cls) -> SchemaRegistry:
        """
        Erstellt eine vollständig befüllte SchemaRegistry.
        """
        registry = SchemaRegistry()

        # --- Service segments ---
        cls._register_UNB(registry)
        cls._register_UNZ(registry)
        cls._register_UNH(registry)
        cls._register_UNT(registry)

        # --- SLGA segments ---
        cls._register_FKT_SLGA(registry)
        cls._register_REC(registry)
        cls._register_UST(registry)
        cls._register_SKO(registry)
        cls._register_GES(registry)
        cls._register_NAM(registry)

        # --- SLLA base segments ---
        cls._register_FKT_SLLA(registry)
        cls._register_INV(registry)
        cls._register_URI(registry)
        cls._register_NAD(registry)
        cls._register_IMG(registry)
        cls._register_EVO(registry)

        # --- SLLA:B (Heilmittel) segments ---
        cls._register_EHE(registry)
        cls._register_TXT(registry)
        cls._register_MWS(registry)
        cls._register_ZHE(registry)
        cls._register_DIA(registry)
        cls._register_SKZ(registry)
        cls._register_BES(registry)
        cls._register_GZF(registry)

        # --- Segment orders ---
        cls._register_segment_orders(registry)

        return registry

    # ========================================================================
    # Service segments
    # ========================================================================

    @classmethod
    def _register_UNB(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('UNB', [
            # 0: Syntax identifier — composite UNOC:3
            {'name': 'Syntaxkennung', 'type': 'AN', 'art': 'M', 'maxLen': None, 'decimals': None,
             'composite': [
                 {'name': 'Syntax-Kennung', 'type': 'AN', 'maxLen': 4},
                 {'name': 'Syntax-Versionsnummer', 'type': 'N', 'maxLen': 1},
             ]},
            # 1: Absender
            {'name': 'Absender', 'type': 'AN', 'art': 'M', 'maxLen': 35, 'decimals': None, 'composite': None},
            # 2: Empfänger
            {'name': 'Empfänger', 'type': 'AN', 'art': 'M', 'maxLen': 35, 'decimals': None, 'composite': None},
            # 3: Datum/Uhrzeit — composite JJJJMMTT:HHMM
            {'name': 'Datum/Uhrzeit', 'type': 'N', 'art': 'M', 'maxLen': None, 'decimals': None,
             'composite': [
                 {'name': 'Datum', 'type': 'N', 'maxLen': 8},
                 {'name': 'Uhrzeit', 'type': 'N', 'maxLen': 4},
             ]},
            # 4: Datenaustauschreferenz
            {'name': 'Datenaustauschreferenz', 'type': 'AN', 'art': 'M', 'maxLen': 14, 'decimals': None, 'composite': None},
            # 5: Leistungsbereich (Sammelgruppenschlüssel)
            {'name': 'Leistungsbereich', 'type': 'AN', 'art': 'M', 'maxLen': 1, 'decimals': None, 'composite': None},
            # 6: Anwendungsreferenz (logical filename)
            {'name': 'Anwendungsreferenz', 'type': 'AN', 'art': 'M', 'maxLen': 14, 'decimals': None, 'composite': None},
            # 7: Testindikator
            {'name': 'Testindikator', 'type': 'N', 'art': 'M', 'maxLen': 1, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_UNZ(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('UNZ', [
            {'name': 'Anzahl Nachrichten', 'type': 'N', 'art': 'M', 'maxLen': 6, 'decimals': None, 'composite': None},
            {'name': 'Datenaustauschreferenz', 'type': 'AN', 'art': 'M', 'maxLen': 14, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_UNH(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('UNH', [
            {'name': 'Nachrichtenreferenznummer', 'type': 'AN', 'art': 'M', 'maxLen': 14, 'decimals': None, 'composite': None},
            {'name': 'Nachrichtenkennung', 'type': 'AN', 'art': 'M', 'maxLen': None, 'decimals': None,
             'composite': [
                 {'name': 'Nachrichtentyp', 'type': 'AN', 'maxLen': 6},
                 {'name': 'Versionsnummer', 'type': 'AN', 'maxLen': 3},
                 {'name': 'Freigabenummer', 'type': 'AN', 'maxLen': 3},
                 {'name': 'Organisation', 'type': 'AN', 'maxLen': 2},
             ]},
        ]))

    @classmethod
    def _register_UNT(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('UNT', [
            {'name': 'Anzahl Einheiten', 'type': 'N', 'art': 'M', 'maxLen': 6, 'decimals': None, 'composite': None},
            {'name': 'Nachrichtenreferenznummer', 'type': 'AN', 'art': 'M', 'maxLen': 14, 'decimals': None, 'composite': None},
        ]))

    # ========================================================================
    # SLGA segments
    # ========================================================================

    @classmethod
    def _register_FKT_SLGA(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('FKT', [
            {'name': 'Verarbeitungskennzeichen', 'type': 'N', 'art': 'M', 'maxLen': 2, 'decimals': None, 'composite': None},
            {'name': 'Sammelrechnung', 'type': 'AN', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'IK Rechnungssteller', 'type': 'N', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'IK Kostenträger', 'type': 'N', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'IK Krankenkasse', 'type': 'N', 'art': 'K', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'IK Absender', 'type': 'N', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
        ]), 'SLGA')

    @classmethod
    def _register_FKT_SLLA(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('FKT', [
            {'name': 'Verarbeitungskennzeichen', 'type': 'N', 'art': 'M', 'maxLen': 2, 'decimals': None, 'composite': None},
            {'name': 'Freifeld', 'type': 'AN', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'IK Leistungserbringer', 'type': 'N', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'IK Kostenträger', 'type': 'N', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'IK Krankenkasse', 'type': 'N', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'IK Rechnungssteller', 'type': 'N', 'art': 'K', 'maxLen': 9, 'decimals': None, 'composite': None},
        ]), 'SLLA')

    @classmethod
    def _register_REC(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('REC', [
            {'name': 'Rechnungsnummer', 'type': 'AN', 'art': 'M', 'maxLen': None, 'decimals': None,
             'composite': [
                 {'name': 'Sammel-Rechnungsnummer', 'type': 'AN', 'maxLen': 14},
                 {'name': 'Einzel-Rechnungsnummer', 'type': 'AN', 'maxLen': 6},
             ]},
            {'name': 'Rechnungsdatum', 'type': 'N', 'art': 'M', 'maxLen': 8, 'decimals': None, 'composite': None},
            {'name': 'Rechnungsart', 'type': 'N', 'art': 'M', 'maxLen': 1, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_UST(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('UST', [
            {'name': 'Steuernummer/UST-ID', 'type': 'AN', 'art': 'M', 'maxLen': 20, 'decimals': None, 'composite': None},
            {'name': 'Kennung UST-Befreiung', 'type': 'AN', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_SKO(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('SKO', [
            {'name': 'Skonto in Prozent', 'type': 'N', 'art': 'M', 'maxLen': 2, 'decimals': 2, 'composite': None},
            {'name': 'Zahlungsziel', 'type': 'N', 'art': 'M', 'maxLen': 3, 'decimals': 0, 'composite': None},
        ]))

    @classmethod
    def _register_GES(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('GES', [
            {'name': 'Summenstatus', 'type': 'N', 'art': 'M', 'maxLen': 2, 'decimals': 0, 'composite': None},
            {'name': 'Gesamtrechnungsbetrag', 'type': 'N', 'art': 'M', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Gesamtbruttobetrag', 'type': 'N', 'art': 'M', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Gesamtbetrag Zuzahlung', 'type': 'N', 'art': 'K', 'maxLen': 10, 'decimals': 2, 'composite': None},
        ]))

    @classmethod
    def _register_NAM(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('NAM', [
            {'name': 'Name 1', 'type': 'AN', 'art': 'M', 'maxLen': 30, 'decimals': None, 'composite': None},
            {'name': 'Name 2', 'type': 'AN', 'art': 'K', 'maxLen': 30, 'decimals': None, 'composite': None},
            {'name': 'Name 3', 'type': 'AN', 'art': 'K', 'maxLen': 30, 'decimals': None, 'composite': None},
            {'name': 'Name 4 (E-Mail)', 'type': 'AN', 'art': 'K', 'maxLen': 70, 'decimals': None, 'composite': None},
        ]))

    # ========================================================================
    # SLLA base segments
    # ========================================================================

    @classmethod
    def _register_INV(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('INV', [
            {'name': 'Versichertennummer', 'type': 'AN', 'art': 'K', 'maxLen': 12, 'decimals': None, 'composite': None},
            {'name': 'Versichertenstatus', 'type': 'AN', 'art': 'K', 'maxLen': 5, 'decimals': None, 'composite': None},
            {'name': 'Beleginformation', 'type': 'AN', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'Belegnummer', 'type': 'AN', 'art': 'M', 'maxLen': 10, 'decimals': None, 'composite': None},
            {'name': 'Kennzeichen Besondere Versorgungsform', 'type': 'AN', 'art': 'K', 'maxLen': 25, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_URI(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('URI', [
            {'name': 'Ursprüngliches IK', 'type': 'N', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'Ursprüngliche Rechnungsnummer', 'type': 'AN', 'art': 'M', 'maxLen': None, 'decimals': None,
             'composite': [
                 {'name': 'Sammel-Rechnungsnummer', 'type': 'AN', 'maxLen': 14},
                 {'name': 'Einzel-Rechnungsnummer', 'type': 'AN', 'maxLen': 6},
             ]},
            {'name': 'Ursprüngliches Rechnungsdatum', 'type': 'N', 'art': 'M', 'maxLen': 8, 'decimals': None, 'composite': None},
            {'name': 'Ursprüngliche Belegnummer', 'type': 'AN', 'art': 'M', 'maxLen': 10, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_NAD(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('NAD', [
            {'name': 'Nachname', 'type': 'AN', 'art': 'M', 'maxLen': 47, 'decimals': None, 'composite': None},
            {'name': 'Vorname', 'type': 'AN', 'art': 'M', 'maxLen': 30, 'decimals': None, 'composite': None},
            {'name': 'Geburtsdatum', 'type': 'N', 'art': 'M', 'maxLen': 8, 'decimals': None, 'composite': None},
            {'name': 'Straße', 'type': 'AN', 'art': 'K', 'maxLen': 30, 'decimals': None, 'composite': None},
            {'name': 'PLZ', 'type': 'AN', 'art': 'K', 'maxLen': 7, 'decimals': None, 'composite': None},
            {'name': 'Ort', 'type': 'AN', 'art': 'K', 'maxLen': 25, 'decimals': None, 'composite': None},
            {'name': 'Länderkennzeichen', 'type': 'AN', 'art': 'K', 'maxLen': 3, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_IMG(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('IMG', [
            {'name': 'Abrechnungsjahr', 'type': 'N', 'art': 'M', 'maxLen': 4, 'decimals': None, 'composite': None},
            {'name': 'Abrechnungsmonat', 'type': 'AN', 'art': 'M', 'maxLen': 2, 'decimals': None, 'composite': None},
            {'name': 'IK Bildgeber', 'type': 'N', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_EVO(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('EVO', [
            {'name': 'eVO-ID', 'type': 'AN', 'art': 'M', 'maxLen': 256, 'decimals': None, 'composite': None},
        ]))

    # ========================================================================
    # SLLA:B (Heilmittel) segments
    # ========================================================================

    @classmethod
    def _register_EHE(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('EHE', [
            {'name': 'Leistungserbringergruppe', 'type': 'AN', 'art': 'M', 'maxLen': None, 'decimals': None,
             'composite': [
                 {'name': 'Abrechnungscode', 'type': 'AN', 'maxLen': 2},
                 {'name': 'Tarifkennzeichen', 'type': 'AN', 'maxLen': 5},
             ]},
            {'name': 'Abrechnungspositionsnummer', 'type': 'AN', 'art': 'M', 'maxLen': 5, 'decimals': None, 'composite': None},
            {'name': 'Anzahl/Menge', 'type': 'N', 'art': 'M', 'maxLen': 4, 'decimals': 2, 'composite': None},
            {'name': 'Einzelbetrag', 'type': 'N', 'art': 'M', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Datum Leistungserbringung', 'type': 'N', 'art': 'M', 'maxLen': 8, 'decimals': None, 'composite': None},
            {'name': 'Betrag Zuzahlung', 'type': 'N', 'art': 'K', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Gefahrene Kilometer', 'type': 'N', 'art': 'K', 'maxLen': 6, 'decimals': 0, 'composite': None},
        ]))

    @classmethod
    def _register_TXT(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('TXT', [
            {'name': 'Text', 'type': 'AN', 'art': 'M', 'maxLen': 70, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_MWS(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('MWS', [
            {'name': 'Mehrwertsteuersatz', 'type': 'N', 'art': 'M', 'maxLen': 5, 'decimals': 2, 'composite': None},
            {'name': 'Betrag Mehrwertsteuer', 'type': 'N', 'art': 'M', 'maxLen': 10, 'decimals': 2, 'composite': None},
        ]))

    @classmethod
    def _register_ZHE(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('ZHE', [
            {'name': 'Betriebsstättennummer', 'type': 'AN', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'Lebenslange Arztnummer', 'type': 'AN', 'art': 'M', 'maxLen': 9, 'decimals': None, 'composite': None},
            {'name': 'Verordnungsdatum', 'type': 'N', 'art': 'M', 'maxLen': 8, 'decimals': None, 'composite': None},
            {'name': 'Zuzahlungskennzeichen', 'type': 'N', 'art': 'M', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'Diagnosegruppe', 'type': 'AN', 'art': 'M', 'maxLen': 4, 'decimals': None, 'composite': None},
            {'name': 'Verordnungsart', 'type': 'N', 'art': 'M', 'maxLen': 2, 'decimals': None, 'composite': None},
            {'name': 'Verordnungsbesonderheiten', 'type': 'N', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'Unfallkennzeichen', 'type': 'N', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'BVG/Sonstiges/SER', 'type': 'N', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'Behandlungsbeginn', 'type': 'AN', 'art': 'K', 'maxLen': 8, 'decimals': None, 'composite': None}, # deprecated, always empty
            {'name': 'Therapiebericht', 'type': 'N', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'Hausbesuch', 'type': 'N', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'Leitsymptomatik', 'type': 'AN', 'art': 'M', 'maxLen': 4, 'decimals': None, 'composite': None},
            {'name': 'Individuelle Leitsymptomatik', 'type': 'AN', 'art': 'K', 'maxLen': 70, 'decimals': None, 'composite': None},
            {'name': 'Dringlicher Behandlungsbedarf', 'type': 'N', 'art': 'M', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'Heilmittel-Bereich', 'type': 'N', 'art': 'K', 'maxLen': 1, 'decimals': None, 'composite': None},
            {'name': 'Therapiefrequenz', 'type': 'N', 'art': 'M', 'maxLen': 1, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_DIA(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('DIA', [
            {'name': 'Diagnoseschlüssel', 'type': 'AN', 'art': 'K', 'maxLen': 12, 'decimals': None, 'composite': None},
            {'name': 'Diagnosetext', 'type': 'AN', 'art': 'K', 'maxLen': 70, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_SKZ(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('SKZ', [
            {'name': 'Genehmigungskennzeichen', 'type': 'AN', 'art': 'M', 'maxLen': 20, 'decimals': None, 'composite': None},
            {'name': 'Datum der Genehmigung', 'type': 'N', 'art': 'M', 'maxLen': 8, 'decimals': None, 'composite': None},
            {'name': 'Art der Genehmigung', 'type': 'AN', 'art': 'M', 'maxLen': 2, 'decimals': None, 'composite': None},
        ]))

    @classmethod
    def _register_BES(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('BES', [
            {'name': 'Gesamtbetrag Brutto', 'type': 'N', 'art': 'M', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Gesamtbetrag Zuzahlung', 'type': 'N', 'art': 'K', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Betrag prozentuale Zuzahlung', 'type': 'N', 'art': 'K', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Pauschaler Zuzahlungsbetrag', 'type': 'N', 'art': 'K', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Pauschale Korrekturabzug', 'type': 'N', 'art': 'K', 'maxLen': 10, 'decimals': 2, 'composite': None},
        ]))

    @classmethod
    def _register_GZF(cls, r: SchemaRegistry) -> None:
        r.register(SegmentDefinition('GZF', [
            {'name': 'Gesamtbetrag Forderung Zuzahlung', 'type': 'N', 'art': 'M', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Forderung prozentuale Zuzahlung', 'type': 'N', 'art': 'K', 'maxLen': 10, 'decimals': 2, 'composite': None},
            {'name': 'Forderung pauschaler Zuzahlungsbetrag', 'type': 'N', 'art': 'K', 'maxLen': 10, 'decimals': 2, 'composite': None},
        ]))

    # ========================================================================
    # Segment order definitions
    # ========================================================================

    @classmethod
    def _register_segment_orders(cls, r: SchemaRegistry) -> None:
        """
        Registriert die Segment-Reihenfolge-Regeln für SLGA und SLLA:B.
        Format: Dictionary mit 'tag': str, 'min': int, 'max': Optional[int]. 
        None bei max bedeutet unbegrenzte Wiederholungen.
        """
        # SLGA: UNH, FKT, REC, [UST], [SKO]*, GES+, NAM, UNT
        r.register_segment_order('SLGA', [
            {'tag': 'UNH', 'min': 1, 'max': 1},
            {'tag': 'FKT', 'min': 1, 'max': 1},
            {'tag': 'REC', 'min': 1, 'max': 1},
            {'tag': 'UST', 'min': 0, 'max': 1},
            {'tag': 'SKO', 'min': 0, 'max': 9},
            {'tag': 'GES', 'min': 2, 'max': 9},
            {'tag': 'NAM', 'min': 1, 'max': 1},
            {'tag': 'UNT', 'min': 1, 'max': 1},
        ])

        # SLLA:B (Heilmittel): UNH, FKT, REC, then repeating INV blocks, UNT
        r.register_segment_order('SLLA', [
            {'tag': 'UNH', 'min': 1, 'max': 1},
            {'tag': 'FKT', 'min': 1, 'max': 1},
            {'tag': 'REC', 'min': 1, 'max': 1},
            # INV blocks repeat — validated separately
            {'tag': 'INV_BLOCK', 'min': 1, 'max': None},
            {'tag': 'UNT', 'min': 1, 'max': 1},
        ])

        # SLLA:B INV block internal order
        r.register_segment_order('SLLA_B_INV', [
            {'tag': 'INV', 'min': 1, 'max': 1},
            {'tag': 'URI', 'min': 0, 'max': 1},
            {'tag': 'NAD', 'min': 1, 'max': 1},
            {'tag': 'IMG', 'min': 0, 'max': 1},
            {'tag': 'EVO', 'min': 0, 'max': 1},
            # EHE group repeats (EHE [TXT] [MWS])* — at least 1 EHE
            {'tag': 'EHE_GROUP', 'min': 1, 'max': None},
            {'tag': 'ZHE', 'min': 1, 'max': 1},
            {'tag': 'DIA', 'min': 1, 'max': None},
            {'tag': 'SKZ', 'min': 0, 'max': 1},
            {'tag': 'BES_OR_GZF', 'min': 1, 'max': 1}, # BES or GZF depending on VK
        ])