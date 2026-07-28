from typing import List, Any, Union, Optional
from schema.schema import SchemaFactory, SchemaRegistry, SegmentDefinition

class EsolSegment:
    """Repräsentiert ein einzelnes EDIFACT/ESOL-Segment mit Werten."""
    
    def __init__(self, tag: str, elements: List[Union[str, int, float, list, None]]):
        self.tag = tag
        self.elements = elements

    def serialize(self) -> str:
        """
        Wandelt das Segment in den EDIFACT-String um.
        Beispiel: UNB+UNOC:3+Absender+Empfänger+20260721:1600+Ref123+B+Filename+0'
        """
        formatted_elements = []
        for elem in self.elements:
            if isinstance(elem, list):
                # Composite-Feld (z.B. Syntaxkennung UNOC:3) -> mit ':' verbinden
                formatted_elements.append(":".join("" if x is None else str(x) for x in elem))
            else:
                formatted_elements.append("" if elem is None else str(elem))

        # Nach EDIFACT-Standard können leere Felder am Ende eines Segments abgeschnitten werden
        while formatted_elements and formatted_elements[-1] == "":
            formatted_elements.pop()

        body = "+".join(formatted_elements)
        if body:
            return f"{self.tag}+{body}'"
        return f"{self.tag}'"


class EsolDocumentBuilder:
    """Erstellt ein vollständiges ESOL-Dokument und validiert es gegen die SchemaRegistry."""

    def __init__(self, registry: Optional[SchemaRegistry] = None):
        self.registry = registry or SchemaFactory.create()
        self.segments: List[EsolSegment] = []

    def add_segment(self, tag: str, elements: List[Union[str, int, float, list, None]]) -> 'EsolDocumentBuilder':
        """Fügt ein Segment hinzu (z. B. UNB, UNH, FKT, EHE)."""
        # Check if tag and definition exist.
        if self.registry.is_known_tag(tag):
            segment_def = self.registry.get(tag)
            if segment_def is not None:
                self.validate_segment_data(definition=segment_def, elements=elements)
            else:
                raise ValueError(f"Fehler! Es konnte keine Definition für ein Segment mit dem Bezeichner \"{tag}\" gefunden werden!")
        else:
            raise ValueError(f"Fehler! Der Bezeichner \"{tag}\" konnte nicht gefunden werden!")
        
        segment = EsolSegment(tag, elements)
        self.segments.append(segment)
        return self
    
    def validate_segment_data(self, definition: SegmentDefinition, elements: list):
        for i, field in enumerate(definition.fields):
            val = elements[i] if i < len(elements) else None
            
            # 1. Pflichtfeld-Prüfung
            if field.get('art') == 'M' and val is None:
                raise ValueError(f"Pflichtfeld '{field['name']}' in Segment {definition.tag} fehlt!")
            
            # 2. Längen-Prüfung bei Strings
            max_len = field.get('maxLen')
            if max_len and isinstance(val, str) and len(val) > max_len:
                raise ValueError(f"Feld '{field['name']}' überschreitet Max-Länge {max_len}: '{val}'")

    def render(self) -> str:
        """Erzeugt den gesamten Datei-Inhalt als String."""
        return "\n".join(seg.serialize() for seg in self.segments)

    def save_to_file(self, filepath: str, encoding: str = "iso-8859-15") -> None:
        """Speichert den String in einer Datei (typischerweise ISO-8859-15 / Latin-9 für Abrechnungsdaten)."""
        content = self.render()
        with open(filepath, "w", encoding=encoding, newline="\r\n") as f:
            f.write(content)