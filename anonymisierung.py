"""
Anonymisierung für Berichte, Exporte und Kundendateien.

Wozu: der Ticket-Bericht und der HTML-Prüfbericht enthalten Namen,
Geburtsdaten und Versichertennummern. Wer sie in ein Ticketsystem einfügt oder
per Mail weitergibt, legt Patientendaten in Systemen ab, die dafür nicht
gedacht sind. Dieses Modul ersetzt sie durch stabile Pseudonyme.

Stabil heißt: derselbe Versicherte bekommt innerhalb eines Vorgangs immer
dasselbe Pseudonym. Mehrere Belege einer Person bleiben damit als
zusammengehörig erkennbar — genau das braucht man in der Fehleranalyse. Über
Vorgänge hinweg ist das Pseudonym NICHT stabil: eine Wiedererkennung derselben
Person in einer anderen Datei wäre keine Anonymisierung mehr.

Zwei Darstellungen:

  STIL_LESBAR      für Berichte: "Versicherter A", "Jahrgang 2019".
  STIL_FORMATTREU  für ESOL-Dateien: gleiche Länge und Zeichenart wie das
                   Original, damit die Datei die Prüfung weiter besteht.
                   Das Geburtsdatum wird dabei auf den 1. Januar des
                   Geburtsjahres gesetzt — ein Platzhalter, der wie ein Datum
                   aussieht. Wer die Datei liest, muss wissen, dass der Tag
                   erfunden ist; deshalb steht es hier und im Kopf der
                   erzeugten Datei.

Was NICHT anonymisiert wird, solange man es nicht ausdrücklich anwählt:
Belegnummern und Institutionskennzeichen. Ohne sie lässt sich ein Fall
gegenüber dem Abrechnungszentrum nicht mehr nachvollziehen — dann ist der
Bericht wertlos.
"""

from __future__ import annotations

import copy
import datetime
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

STIL_LESBAR = "lesbar"
STIL_FORMATTREU = "formattreu"

# Auswählbare Feldgruppen. 'standard' ist die Vorbelegung im Export-Dialog.
FELDGRUPPEN: Dict[str, Dict[str, Any]] = {
    "versicherter": {
        "label": "Versicherter",
        "felder": "Nachname, Vorname, Geburtsdatum, Versichertennummer",
        "standard": True,
        "hinweis": "Der Versichertenstatus bleibt stehen — ein Schlüsselwert, kein Identifikator, und für die Fehlersuche gebraucht.",
    },
    "arzt": {
        "label": "Verordnender Arzt",
        "felder": "LANR (lebenslange Arztnummer)",
        "standard": True,
        "hinweis": "Die BSNR bleibt stehen — sie bezeichnet die Betriebsstätte, "
                   "nicht eine Person, und ohne sie ist der Fall kaum zuzuordnen.",
    },
    "diagnosen": {
        "label": "Diagnosen",
        "felder": "ICD-10-Schlüssel und Diagnose-Freitext",
        "standard": False,
        "hinweis": "Gesundheitsdaten. Für die Fehlersuche sind sie aber oft genau "
                   "das, worum es geht — deshalb standardmäßig aus.",
    },
    "praxis": {
        "label": "Praxis / Leistungserbringer",
        "felder": "Name und E-Mail aus dem NAM-Segment",
        "standard": False,
        "hinweis": "Ein Betrieb, keine Privatperson — die E-Mail ist allerdings "
                   "häufig eine persönliche.",
    },
    "belegnummer": {
        "label": "Belegnummern und Institutionskennzeichen",
        "felder": "Belegnummer, IK von Kostenträger, Krankenkasse und Leistungserbringer",
        "standard": False,
        "hinweis": "Nur wählen, wenn der Bericht das Haus verlässt: ohne diese "
                   "Angaben ist der Fall nicht mehr nachvollziehbar.",
    },
}


def standard_gruppen() -> Set[str]:
    """Die Feldgruppen, die im Export-Dialog vorbelegt sind."""
    return {name for name, g in FELDGRUPPEN.items() if g["standard"]}


def _buchstaben(nummer: int) -> str:
    """1 -> A, 2 -> B, ... 27 -> AA. Für lesbare, kurze Pseudonyme."""
    text = ""
    while nummer > 0:
        nummer, rest = divmod(nummer - 1, 26)
        text = chr(ord("A") + rest) + text
    return text


class Anonymisierer:
    """
    Ersetzt personenbezogene Werte durch stabile Pseudonyme.

    Eine Instanz gehört zu genau einem Vorgang (einer Datei, einem Bericht).
    Die Zuordnung Original -> Pseudonym lebt in dieser Instanz und wird nicht
    gespeichert; ein neuer Export vergibt neue Pseudonyme.
    """

    def __init__(self, gruppen: Optional[Iterable[str]] = None,
                 stil: str = STIL_LESBAR):
        unbekannt = set(gruppen or ()) - set(FELDGRUPPEN)
        if unbekannt:
            raise ValueError(
                f"Unbekannte Feldgruppe(n): {', '.join(sorted(unbekannt))}. "
                f"Erlaubt: {', '.join(sorted(FELDGRUPPEN))}"
            )
        self.gruppen: Set[str] = set(gruppen) if gruppen is not None else standard_gruppen()
        self.stil = stil
        # kategorie -> {originalwert: pseudonym}
        self._zuordnung: Dict[str, Dict[str, str]] = {}
        # Alle Ersetzungen, um sie auch auf Freitexte anwenden zu können
        self._ersetzungen: Dict[str, str] = {}

    # ------------------------------------------------------------ Grundlagen

    @property
    def aktiv(self) -> bool:
        return bool(self.gruppen)

    def _pseudonym(self, kategorie: str, original: Any, vorlage: str = "") -> str:
        """
        Liefert für einen Originalwert immer dasselbe Pseudonym.

        'vorlage' ist der Wert, dessen Form im formattreuen Stil nachgebildet
        wird — meist der Originalwert selbst.
        """
        schluessel = str(original)
        tabelle = self._zuordnung.setdefault(kategorie, {})
        if schluessel in tabelle:
            return tabelle[schluessel]

        nummer = len(tabelle) + 1
        if kategorie == "ik" and self.stil == STIL_FORMATTREU:
            pseudonym = self._ik_pseudonym(vorlage or schluessel, nummer)
        elif self.stil == STIL_FORMATTREU and kategorie not in _FREITEXT_KATEGORIEN:
            pseudonym = self._formattreu(vorlage or schluessel, nummer, kategorie)
        else:
            pseudonym = f"{_LESBARE_NAMEN.get(kategorie, kategorie)} {_buchstaben(nummer)}"

        tabelle[schluessel] = pseudonym
        if schluessel:
            self._ersetzungen[schluessel] = pseudonym
        return pseudonym

    @staticmethod
    def _formattreu(vorlage: str, nummer: int, kategorie: str) -> str:
        """
        Baut einen Ersatzwert mit derselben Länge und Zeichenart wie die
        Vorlage. Wichtig für ESOL-Dateien: die Versichertennummer muss
        "Buchstabe + Ziffern" bleiben (Regel 1.3.5.1), BSNR und LANR müssen
        numerisch bleiben (1.3.9.1 / 1.3.9.2).
        """
        vorlage = str(vorlage)
        if not vorlage:
            return ""

        ziffern = f"{nummer:0{max(1, sum(c.isdigit() for c in vorlage))}d}"
        ziffern_iter = iter(ziffern[-max(1, sum(c.isdigit() for c in vorlage)):])

        ergebnis = []
        for zeichen in vorlage:
            if zeichen.isdigit():
                ergebnis.append(next(ziffern_iter, "0"))
            elif zeichen.isalpha():
                # Erster Buchstabe bleibt ein Buchstabe (KVNR-Format)
                ergebnis.append(_buchstaben(nummer)[0] if zeichen.isupper()
                                else _buchstaben(nummer)[0].lower())
            else:
                ergebnis.append(zeichen)
        return "".join(ergebnis)

    def _ik_pseudonym(self, original: str, nummer: int) -> str:
        """
        Ein Ersatz-IK, das die Prüfziffer erfüllt.

        Ein IK ist neunstellig. Die ersten zwei Stellen sind die Klassifikation
        (sie sagen, ob es sich um eine Krankenkasse, einen Leistungserbringer
        oder eine Abrechnungsstelle handelt) und bleiben deshalb erhalten — sie
        identifizieren niemanden, tragen aber die Bedeutung. Die Stellen 3 bis 8
        werden ersetzt, die 9. Stelle ist die Prüfziffer nach demselben
        Verfahren, das ContentHelper.is_valid_ik_check_digit prüft. Ohne diesen
        Schritt wäre die anonymisierte Datei ungültig.
        """
        original = str(original).strip()
        if not re.match(r"^\d{9}$", original):
            return self._formattreu(original, nummer, "ik")

        klassifikation = original[:2]
        mitte = f"{nummer:06d}"[-6:]

        gewichte = [2, 1, 2, 1, 2, 1]
        summe = 0
        for stelle, gewicht in zip((int(d) for d in mitte), gewichte):
            produkt = stelle * gewicht
            summe += (produkt // 10) + (produkt % 10)
        pruefziffer = summe % 10

        return f"{klassifikation}{mitte}{pruefziffer}"

    def _geburtsdatum(self, wert: Any) -> str:
        """
        Geburtsdatum kürzen. Das Jahr bleibt erhalten, damit Altersgrenzen
        (Verordnungsbedarf, Kinderbehandlung) weiter prüfbar sind.
        """
        text = str(wert or "").strip()
        treffer = re.match(r"^(\d{4})\d{4}$", text)
        if not treffer:
            return text
        jahr = treffer.group(1)
        if self.stil == STIL_FORMATTREU:
            # Gültiges Datum, aber erfundener Tag — siehe Modulkopf.
            return f"{jahr}0101"
        return f"Jahrgang {jahr}"

    # -------------------------------------------------------------- Berichte

    def beleg(self, beleg: Dict[str, Any]) -> Dict[str, Any]:
        """Ein einzelner Beleg aus parse_esol_belege_summary, anonymisiert."""
        return self.belege([beleg])[0]

    def belege(self, belege: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Kopiert die Belegliste und ersetzt die angewählten Felder. Das Original
        bleibt unberührt — die Bildschirmanzeige arbeitet weiter mit Klartext.
        """
        if not self.aktiv:
            return list(belege)

        ergebnis = copy.deepcopy(list(belege))
        for b in ergebnis:
            if "versicherter" in self.gruppen:
                # Ein Versicherter wird über die Versichertennummer erkannt;
                # fehlt sie, über Name und Geburtsdatum.
                kennung = str(b.get("versichertennummer") or "").strip() or "|".join([
                    str(b.get("nachname") or ""), str(b.get("vorname") or ""),
                    str(b.get("geburtstag") or ""),
                ])
                deckname = self._pseudonym("versicherter", kennung)

                if b.get("nachname") or b.get("vorname"):
                    self._merke(b.get("nachname"), deckname)
                    self._merke(b.get("vorname"), "")
                    b["nachname"] = deckname
                    b["vorname"] = ""
                if b.get("versichertennummer"):
                    ersatz = self._pseudonym(
                        "versichertennummer", b["versichertennummer"], b["versichertennummer"]
                    ) if self.stil == STIL_FORMATTREU else deckname
                    self._merke(b["versichertennummer"], ersatz)
                    b["versichertennummer"] = ersatz
                if b.get("geburtstag"):
                    ersatz = self._geburtsdatum(b["geburtstag"])
                    self._merke(b["geburtstag"], ersatz)
                    b["geburtstag"] = ersatz
                # Der Versichertenstatus bleibt stehen. Er ist ein Schlüssel,
                # kein Identifikator, und wird für die Fehlersuche gebraucht.
                # In der ESOL-Datei ist er zudem gefährlich zu leeren: Regel
                # 1.3.7.4 verlangt bei unbekannter Versichertennummer oder
                # unbekanntem Status eine vollständige Anschrift.

            if "arzt" in self.gruppen:
                self._ersetze_arzt(b)

            if "diagnosen" in self.gruppen:
                for d in b.get("diagnosen") or []:
                    if d.get("code"):
                        ersatz = self._pseudonym("diagnose", d["code"], d["code"])
                        self._merke(d["code"], ersatz)
                        d["code"] = ersatz
                    if d.get("text"):
                        self._merke(d["text"], "")
                        d["text"] = ""

            if "belegnummer" in self.gruppen:
                for feld, kategorie in (("belegnr", "beleg"),
                                        ("kostentraeger_ik", "ik"),
                                        ("krankenkasse_ik", "ik"),
                                        ("leistungserbringer_ik", "ik")):
                    if b.get(feld):
                        ersatz = self._pseudonym(kategorie, b[feld], b[feld])
                        self._merke(b[feld], ersatz)
                        b[feld] = ersatz

        # Sicherheitsnetz. Ein Beleg trägt neben den ausgewerteten Feldern auch
        # die Rohsegmente ('raw_segments', 'raw_fields', 'rohfelder') — dort
        # stand der Klartext nach den Ersetzungen oben noch drin. Eine
        # Feldliste zu pflegen reicht hier nicht: sie veraltet, sobald jemand
        # dem Beleg ein Feld hinzufügt. Deshalb wird zum Schluss der ganze
        # Beleg durchlaufen und jede Zeichenkette durch die bekannten
        # Ersetzungen geschickt.
        for b in ergebnis:
            self._durchsuchen(b)

        return ergebnis

    def _durchsuchen(self, knoten: Any) -> Any:
        """
        Wendet die bekannten Ersetzungen auf jede Zeichenkette in einer
        verschachtelten Struktur an. Verändert Dicts und Listen an ihrem Platz;
        Tupel werden neu gebaut, weil sie unveränderlich sind.
        """
        if isinstance(knoten, dict):
            for schluessel, wert in list(knoten.items()):
                knoten[schluessel] = self._durchsuchen(wert)
            return knoten
        if isinstance(knoten, list):
            for index, wert in enumerate(knoten):
                knoten[index] = self._durchsuchen(wert)
            return knoten
        if isinstance(knoten, tuple):
            return tuple(self._durchsuchen(w) for w in knoten)
        if isinstance(knoten, str):
            return self._ganzes_feld(knoten)
        return knoten

    def _ganzes_feld(self, wert: str) -> str:
        """
        Ersetzt einen Wert nur, wenn er dem Original VOLLSTÄNDIG entspricht.

        Absichtlich keine Teilstring-Suche: die Vornamen in echten Dateien sind
        teils kurz und stecken in anderen Wörtern. "Anna" käme in
        "Annahmestelle" vor, "Ort" in "Sortierung" — eine Teilstring-Ersetzung
        würde daraus "hmestelle" und "S***ierung" machen. In strukturierten
        Daten steht jeder Wert in seinem eigenen Feld, deshalb reicht der
        Vergleich auf Gleichheit und ist zugleich der sichere Weg.

        Für Freitexte, in denen der Wert mitten im Satz steht, gibt es text().
        """
        schluessel = wert.strip()
        if schluessel in self._ersetzungen:
            ersatz = self._ersetzungen[schluessel]
            return ersatz if ersatz else "***"
        return wert

    def _ersetze_arzt(self, beleg: Dict[str, Any]) -> None:
        """
        Die LANR identifiziert eine natürliche Person, die BSNR die
        Betriebsstätte. Ersetzt wird deshalb nur die LANR.
        """
        zhe = beleg.get("verordnung")
        if not isinstance(zhe, dict) or not zhe.get("lanr"):
            return
        ersatz = self._pseudonym("arzt", zhe["lanr"], zhe["lanr"])
        self._merke(zhe["lanr"], ersatz)
        zhe["lanr"] = ersatz
        # Der zusammengesetzte Anzeigetext wird neu gebaut, sonst steht die
        # echte LANR weiter im Bericht.
        if zhe.get("arzt_text"):
            zhe["arzt_text"] = " · ".join(p for p in [
                f"BSNR {zhe.get('bsnr')}" if zhe.get("bsnr") else "",
                f"LANR {ersatz}",
            ] if p)
        if isinstance(zhe.get("rohfelder"), list) and len(zhe["rohfelder"]) > 1:
            zhe["rohfelder"][1] = ersatz

    def _merke(self, original: Any, ersatz: str) -> None:
        """Merkt eine Ersetzung, damit sie auch in Freitexten greift."""
        text = str(original or "").strip()
        if len(text) >= 3:  # kürzere Werte träfen zu viel
            self._ersetzungen[text] = ersatz

    # -------------------------------------------------------------- Freitext

    def text(self, wert: Any) -> str:
        """
        Wendet alle bisher vergebenen Ersetzungen auf einen Freitext an.

        Nötig für die Fehlerliste: mehrere Prüfregeln zitieren den Wert im
        Meldungstext, etwa `Versichertennummer "E430685837" hat ungültiges
        Format`. Ohne diesen Schritt stünde der Klartext trotz Anonymisierung
        im Bericht.

        Erst nach belege() aufrufen — vorher sind noch keine Ersetzungen
        bekannt.
        """
        text = str(wert or "")
        if not self.aktiv or not text:
            return text
        # Längste Originale zuerst, damit Teiltreffer nichts zerreißen.
        # Wortgrenzen, damit ein kurzer Vorname wie "Anna" nicht mitten in
        # "Annahmestelle" ersetzt wird — Fundstelle aus den echten Testdaten.
        for original in sorted(self._ersetzungen, key=len, reverse=True):
            if original not in text:
                continue
            ersatz = self._ersetzungen[original] or "***"
            text = re.sub(
                rf"(?<![0-9A-Za-zÄÖÜäöüß]){re.escape(original)}(?![0-9A-Za-zÄÖÜäöüß])",
                ersatz.replace("\\", "\\\\"),
                text,
            )
        return text

    def texte(self, werte: Iterable[Any]) -> List[str]:
        return [self.text(w) for w in werte]

    # ---------------------------------------------------------- ESOL-Datei

    def esol(self, raw_content: str) -> str:
        """
        Anonymisiert eine ganze ESOL-Datei auf Segmentebene.

        Arbeitet absichtlich textnah statt über den Parser: die Datei soll
        Zeichen für Zeichen dieselbe bleiben, nur mit ersetzten Feldern. Die
        Segmentstruktur, die Zähler und die Summen bleiben damit gültig.
        """
        if not self.aktiv:
            return raw_content

        zeilen = raw_content.splitlines(keepends=True)
        ergebnis: List[str] = []

        for zeile in zeilen:
            rest = zeile.rstrip("\r\n")
            zeilenende = zeile[len(rest):]
            if not rest:
                ergebnis.append(zeile)
                continue

            tag = rest[:3]
            if tag == "NAD" and "versicherter" in self.gruppen:
                rest = self._ersetze_felder(rest, {0: "name", 1: "leer", 2: "geburt"})
            elif tag == "INV" and (
                "versicherter" in self.gruppen or "belegnummer" in self.gruppen
            ):
                zuordnung = {}
                if "versicherter" in self.gruppen:
                    zuordnung[0] = "versnr"
                if "belegnummer" in self.gruppen:
                    zuordnung[3] = "beleg"
                rest = self._ersetze_felder(rest, zuordnung)
            elif tag == "FKT" and "belegnummer" in self.gruppen:
                # IK Leistungserbringer, Kostenträger, Krankenkasse, Absender
                rest = self._ersetze_felder(rest, {2: "ik", 3: "ik", 4: "ik", 5: "ik"})
            elif tag == "UNB" and "belegnummer" in self.gruppen:
                # Absender und Empfänger des Datenaustauschs
                rest = self._ersetze_felder(rest, {1: "ik", 2: "ik"})
            elif tag == "URI" and "belegnummer" in self.gruppen:
                # Ursprungsrechnung: IK des Leistungserbringers und Belegnummer
                rest = self._ersetze_felder(rest, {0: "ik", 3: "beleg"})
            elif tag == "ZHE" and "arzt" in self.gruppen:
                rest = self._ersetze_felder(rest, {1: "lanr"})
            elif tag == "DIA" and "diagnosen" in self.gruppen:
                rest = self._ersetze_felder(rest, {0: "diagnose", 1: "leer"})
            elif tag == "NAM" and "praxis" in self.gruppen:
                rest = self._ersetze_felder(rest, {0: "praxis", 1: "leer",
                                                   2: "leer", 3: "leer"})

            ergebnis.append(rest + zeilenende)

        return "".join(ergebnis)

    def _ersetze_felder(self, segment: str, zuordnung: Dict[int, str]) -> str:
        """
        Ersetzt einzelne Felder eines Segments. Das Segment wird an '+'
        getrennt, wobei ein mit '?' maskiertes Plus kein Trenner ist.
        """
        endezeichen = "'" if segment.endswith("'") else ""
        kern = segment[:-1] if endezeichen else segment

        felder = _teile_felder(kern)
        if not felder:
            return segment

        for index, art in zuordnung.items():
            pos = index + 1  # Feld 0 ist der Tag
            if pos >= len(felder) or not felder[pos]:
                continue
            felder[pos] = self._ersatzwert(art, felder[pos])

        return "+".join(felder) + endezeichen

    def _ersatzwert(self, art: str, original: str) -> str:
        if art == "leer":
            return ""
        if art == "geburt":
            return self._geburtsdatum(original)
        kategorie = {
            "name": "versicherter", "versnr": "versichertennummer",
            "lanr": "arzt", "diagnose": "diagnose", "praxis": "praxis",
            "beleg": "beleg",
        }.get(art, art)
        ersatz = self._pseudonym(kategorie, original, original)
        self._merke(original, ersatz)
        return ersatz

    # ------------------------------------------------------------- Auskunft

    def bericht(self) -> List[str]:
        """
        Was ersetzt wurde, als Zeilen für den Kopf eines Berichts. Nennt
        Kategorien und Anzahlen, nie die Originalwerte.
        """
        if not self.aktiv:
            return ["Anonymisierung: aus — der Bericht enthält Klartextdaten."]

        zeilen = ["Anonymisierung: an"]
        for name in sorted(self.gruppen):
            zeilen.append(f"  {FELDGRUPPEN[name]['label']}: {FELDGRUPPEN[name]['felder']}")
        for kategorie, tabelle in sorted(self._zuordnung.items()):
            zeilen.append(f"  {len(tabelle)}× {kategorie} ersetzt")
        if "versicherter" in self.gruppen:
            zeilen.append("  Geburtsdatum auf das Geburtsjahr gekürzt")
        zeilen.append("  Pseudonyme gelten nur innerhalb dieses Exports.")
        return zeilen


# Kategorien, deren Feld im ESOL-Satz freier Text ist (Typ AN). Dort ist ein
# lesbares Pseudonym besser als eine formattreue Zeichenmaske: aus "Stein"
# würde sonst "Aaaaa", was niemandem hilft. Die Feldlängen (Nachname 47,
# Vorname 30) reichen für "Versicherter A" mit Abstand.
_FREITEXT_KATEGORIEN = {"versicherter", "praxis"}

_LESBARE_NAMEN = {
    "versicherter": "Versicherter",
    "versichertennummer": "Versicherter",
    "arzt": "Arzt",
    "praxis": "Praxis",
    "diagnose": "Diagnose",
    "beleg": "Beleg",
    "ik": "IK",
}


def _teile_felder(kern: str) -> List[str]:
    """
    Trennt ein Segment an '+', beachtet aber das ESOL-Maskierzeichen '?'.
    'NAD+Mü?+ller+Max' hat drei Felder, nicht vier.
    """
    felder: List[str] = []
    aktuell: List[str] = []
    maskiert = False
    for zeichen in kern:
        if maskiert:
            aktuell.append(zeichen)
            maskiert = False
            continue
        if zeichen == "?":
            aktuell.append(zeichen)
            maskiert = True
            continue
        if zeichen == "+":
            felder.append("".join(aktuell))
            aktuell = []
            continue
        aktuell.append(zeichen)
    felder.append("".join(aktuell))
    return felder


def kopfzeilen_esol(anonymisierer: "Anonymisierer", quelldatei: str = "") -> str:
    """
    Hinweistext für eine anonymisierte ESOL-Datei. Bewusst KEIN Kommentar in
    der Datei selbst — ESOL kennt keine Kommentare, jede Zeile wäre ein
    ungültiges Segment. Der Text ist für eine Begleitdatei gedacht.
    """
    zeilen = [
        "Anonymisierte Kopie einer ESOL-Abrechnungsdatei",
        "=" * 48,
    ]
    if quelldatei:
        zeilen.append(f"Quelldatei: {quelldatei}")
    zeilen.append(
        f"Erzeugt am: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    zeilen.append("")
    zeilen.extend(anonymisierer.bericht())
    zeilen.append("")
    zeilen.append(
        "Das Geburtsdatum wurde auf den 1. Januar des Geburtsjahres gesetzt, "
        "damit die Datei ein gültiges Datum enthält. Der Tag ist erfunden — "
        "nur das Jahr stammt aus dem Original."
    )
    zeilen.append(
        "Diese Datei ist zur Fehleranalyse gedacht und darf NICHT abgerechnet "
        "werden."
    )
    return "\n".join(zeilen) + "\n"
