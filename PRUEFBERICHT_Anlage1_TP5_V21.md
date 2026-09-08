# Abgleich py-esol gegen Technische Anlage 1 (TP 5, Version 21)

Grundlage: *Technische Anlage 1 zu den Richtlinien nach § 302 SGB V*,
GKV-Spitzenverband, Version 21, Stand 17.02.2025, anzuwenden ab 01.10.2025,
176 Seiten (`Anlage_1_TP5_V21_20250217.pdf`).

Stand des Abgleichs: 08.09.2026

---

## 1. Vorgehen

Die Anlage wurde nicht gelesen und verglichen, sondern maschinell ausgewertet:
ihre Segmenttabellen wurden in strukturierte Daten überführt und Feld für Feld
gegen `schema/schema.py` gestellt. Der Grund ist Verlässlichkeit — bei
57 Segmenten mit je bis zu 18 Feldern übersieht ein Mensch beim Vergleichen
zuverlässig etwas, eine Tabellenspalte nicht.

Die Auswertungsskripte liegen noch außerhalb des Projekts (siehe Abschnitt 6);
der Abgleich ist damit wiederholbar, wenn Version 22 erscheint.

**Abdeckung:**

| Kapitel der Anlage | Inhalt | Prüfung |
|---|---|---|
| 5.1 | Allgemeines, Steuerzeichen, Längenzählung | von Hand gelesen, Absätze (1)–(11) |
| 5.2 / 5.3 | Struktur und Darstellung der Datei, Rechnungsarten 1–3 | von Hand gelesen |
| 5.4 | Dateiaufbau UNB/UNH/UNT/UNZ | maschinell verglichen |
| 5.5.2 | SLGA (FKT, REC, UST, SKO, GES, NAM) | maschinell verglichen |
| 5.5.3.1 | SLLA Basis-Segmente (FKT, REC, INV, URI, NAD, IMG, EVO) | maschinell verglichen |
| 5.5.3.3 | SLLA: B Heilmittel (EHE, TXT, MWS, ZHE, DIA, SKZ, BES, GZF) | maschinell verglichen |
| 6 | Fehlerverfahren, Prüfstufen 1–4 | von Hand gelesen |
| 7 | Korrekturverfahren, VKZ 02/03/04/10 | von Hand gelesen |
| 5.5.3.2, 5.5.3.4 – 5.5.3.13 | Leistungsbereiche A, C–S | **nicht abgeschlossen**, siehe Abschnitt 5 |

---

## 2. Ergebnis der Feldbeschreibungen

**25 Segmente, 0 Abweichungen.**

Verglichen wurden je Feld: Anzahl Stellen, Nachkommastellen, Feldtyp (AN/N) und
Feldart (M/K). Über UNB, UNH, UNT, UNZ, FKT, REC, UST, SKO, GES, NAM, INV, URI,
NAD, IMG, EVO, EHE, TXT, MWS, ZHE, DIA, SKZ, BES und GZF hinweg stimmt das
Schema in jedem einzelnen Feld mit der Anlage überein — einschließlich der
zusammengesetzten Felder (`EHE.Leistungserbringergruppe`,
`REC.Rechnungsnummer`, `UNH.Nachrichtenkennung`, `UNB.Datum/Uhrzeit`) und
einschließlich des stillgelegten Feldes `ZHE.Behandlungsbeginn`.

Die Feldbeschreibung ist damit die belastbarste Stelle des Programms. Die
Befunde liegen alle in der Prüfung, nicht im Schema.

`tests/test_anlage1_konformitaet.py` schreibt die Tabellen für ZHE, BES und GZF
aus der Anlage ab und hält den Abgleich fest, damit er nicht unbemerkt
zurückfällt.

Die Tests arbeiten auf `tests/fixtures/valid_esol_smoke` und verändern daran
jeweils genau eine Stelle. Die erste Fassung nahm dafür `testdata/in/ESOL0001`
— das lief lokal, im CI aber nicht: `testdata/` enthält echte
Abrechnungsdateien und liegt nicht im Repository. Wo das Verzeichnis vorhanden
ist, prüft je Testdatei eine zusätzliche Gegenprobe, dass keine der
nachgebesserten Regeln auf echten Daten anschlägt; im CI wird sie
übersprungen.

---

## 3. Behobene Befunde

### 3.1 Die Prüfstufen 1 und 2 waren fast vollständig wirkungslos

**Der schwerste Fund.** `ValidationContext.create_validation_error` nahm die
Severity an vierter Stelle:

```python
create_validation_error(stufe, code, message, severity="error", segment=None, segment_index=None)
```

Alle 43 Aufrufstellen in `rules/level1/` und `rules/level2/` übergeben dort
positional das **Segmentkürzel**. In der Severity stand dadurch `"UNB"`,
`"FKT"`, `"REC"` — und `ValidationResult.get_errors()` filtert auf
`severity == "error"`. Die Meldungen wurden erzeugt und weggeworfen.

Zweite Folge, schwerer als die erste: `has_stufe_errors()` sah eine
fehlerfreie Stufe und die Prüfung lief in Stufe 3 weiter, obwohl Kapitel 6.2
der Anlage verlangt, dass bei verletzter Syntax „die gesamte Datei
zurückzuweisen" ist.

Wirkungslos waren:

| Stufe | Regeln |
|---|---|
| 1 | 1.1.3, 1.1.4, 1.1.5, 1.1.6, 1.1.7, 1.1.8, 1.1.9, 1.1.10, 1.1.11, 1.1.12, 1.1.13 |
| 2 | 1.2.1.1, 1.2.1.2, 1.2.1.3, 1.2.1.4, 1.2.1.5, 1.2.2.3, 1.2.2.5, 1.2.2.6, 1.2.2.7, 1.2.2.9 |

Gearbeitet haben nur 1.1.1 (Kodierung), 1.1.2 (Segmentendezeichen), Teile von
1.1.5 und 1.2.3.1 (Aufhebungszeichen) — genau die Regeln, deren Aufrufe drei
Argumente übergeben. Das erklärt, warum in allen 53 Dateien in `testdata/`
ausschließlich 1.2.3.1 je auftauchte.

Belegbar an dem, was jetzt auffällt und vorher nicht:

| Manipulation an einer fehlerfreien Datei | vorher | jetzt |
|---|---|---|
| FKT-Segment entfernt | 0 Fehler | 1.2.1.1, 1.2.1.2, 1.2.1.3 |
| REC-Segment entfernt | 0 Fehler | 1.2.1.1, 1.2.1.2, 1.2.1.3 |
| Buchstabe in ein numerisches Feld | 0 Fehler | 1.2.2.5 |
| Betrag mit 11 Ziffern in `BES` (..10,2) | 0 Fehler | 1.2.2.6 |
| zwei Rechnungsarten in einer Datei (5.2 Abs. 5) | 0 Fehler | 1.1.11 |
| zwei Verarbeitungskennzeichen in einer Datei (7.3) | 0 Fehler | 1.2.1.5 |

**Behoben** in `validation_context.py`: `severity` steht jetzt hinten, alle 43
Aufrufstellen sind damit auf einen Schlag richtig. Eine abweichende Severity
wird per Schlüsselwort übergeben.

**Auswirkung auf die echten Dateien: keine.** Alle 53 Dateien in `testdata/in/`
melden nach der Reparatur genau dieselben 7 Fehler wie vorher (1.2.3.1 in
ESOL0167, ESOL0305, ESOL0325). Es entstehen keine Fehlalarme; die beiden Stufen
haben schlicht bis jetzt nie etwas gemeldet.

### 3.2 Zuzahlungskennzeichen „1" war falsch ausgelegt

Aus dem vorigen Durchgang stammt die Annahme, das Kennzeichen „1"
(Zuzahlungsbefreit) schließe eine Zuzahlungsforderung aus. **Das ist falsch.**
Abschnitt 7.4.2.2 der Anlage führt genau diesen Fall als zulässige
Zuzahlungsforderung auf:

> „Der Versicherte zahlt dem Leistungserbringer die Zuzahlungen jedoch nicht,
> weil eine Befreiung wegen Ereichens der Belastungsgrenze vorliegt. […] mit
> dem Unterschied, dass in der neuen Rechnung die Zuzahlung vom
> Rechnungsbetrag nicht abgesetzt wird (Schlüssel 8.1.3 ‚Zuzahlung' hat den
> Wert '1')."

Die Anlage ordnet jedem Fall ein eigenes Kennzeichen zu:

| Abschnitt | Sachverhalt | Kennzeichen |
|---|---|---|
| 7.4.2.1 | Versicherter ist zuzahlungspflichtig und verweigert | **2** |
| 7.4.2.2 | Befreiung wegen Belastungsgrenze | **1** |
| 7.4.2.3 | Übergang zuzahlungsfrei → pflichtig (jahresübergreifend) | **5** |
| 7.4.2.4 | Kasse kürzte die Rechnung, Versicherter verweigert | **2** |

Drei Stellen waren betroffen und sind behoben:

* `rules/level3/gzf_content_rule.py` — Regel 1.3.12.3 meldete eine
  Forderung neben Kennzeichen „1" als Widerspruch. Sie greift jetzt nur noch
  bei „0" (keine gesetzliche Zuzahlung): dort wurde nie eine Zuzahlung
  abgesetzt, es gibt also nichts zurückzuholen.
* `tools/generate_correction.py`, `vk03_ausgeschlossene_belege` — sortierte
  Belege mit Kennzeichen „1" aus der VK-03-Datei aus. Das hätte **berechtigte
  Forderungen verloren**. Ausgeschlossen wird jetzt nur noch „0" und die
  Forderung über 0,00 €.
* `tools/generate_correction.py`, Berechnung der pauschalen Zuzahlung — nullte
  den Betrag bei Kennzeichen „1".

Dazu die Vorgabe beim Erzeugen: bislang wurde bei VKZ 03 immer „2" gesetzt, ein
ursprüngliches „1" oder „5" also stillschweigend überschrieben — die Datei
behauptete damit einen anderen Sachverhalt als den tatsächlichen. Trägt der
Originalbeleg „1" oder „5", bleibt das Kennzeichen jetzt stehen; sonst gilt
weiterhin „2". Nicht abgedeckt ist „4" (Übergang pflichtig → frei), das
Abschnitt 7.4.2 nicht nennt — das wird wie bisher zu „2".

### 3.3 Fehlende Muss-Segmente fielen nicht auf

Geprüft wurde bisher nur die Position der vorhandenen Segmente, nicht ihr
Vorkommen. Eine Datei ohne `NAD` — also ohne Namen und Adresse des
Versicherten — lief fehlerfrei durch, ebenso eine ohne `ZHE` und eine SLGA ohne
`NAM`. Alle drei sind laut Segmentzusammenstellung Muss-Segmente.

**Behoben** als neue Regel 1.2.1.6 in `rules/level2/segment_order_rule.py`.
Geprüft wird gegen die Segmentzusammenstellung der Anlage:

* je INV-Block: `NAD` und (im Leistungsbereich B) `ZHE` müssen vorhanden sein;
  `INV`, `URI`, `NAD`, `IMG`, `EVO`, `ZHE`, `SKZ`, `BES`, `GZF` höchstens einmal
* je SLGA-Nachricht: `FKT` 1×, `REC` 1×, `UST` ≤ 1, `SKO` ≤ 9, `GES` 2–9,
  `NAM` 1×
* `BES` und `GZF` schließen sich aus (BES bei VKZ 01/02/04/10, GZF bei 03)

Die Tabelle deckt die Leistungsbereiche A, B, C, F, G–N, Q, R und S ab; für
D, E, O und P greifen nur die Basis-Segmente (siehe Abschnitt 5).

### 3.4 Überzählige Felder fielen nicht auf

Ein Segment mit mehr Feldern als vorgesehen — ein `+` zu viel, oder ein Feld
aus einem anderen Leistungsbereich mitgeschleppt — wurde nicht gemeldet.
Kapitel 6.2 verlangt die Prüfung des Vorkommens der Felder.

**Behoben** als Regel 1.2.2.8 in `rules/level2/field_presence_rule.py`. Zur
Einordnung: in allen 140 ZHE-Segmenten der echten Dateien stehen genau 17
Felder — der Fall kommt in echten Daten nicht vor, aber über den
Korrektur-Editor lässt er sich bauen. Eine der Testvorlagen enthielt ihn.

### 3.5 EVO.eVO-ID: Mindestlänge fehlte

Die Anlage gibt für `EVO.eVO-ID` die Länge **„22..256"** an — die einzige
Mindestlängenangabe der ganzen Anlage: „Mindestens anzugeben ist die
22-stellige eID aus der eVerordnung." Das Schema kannte nur `maxLen` und ließ
jede Länge bis 256 durch.

**Behoben**: `minLen` in `schema/schema.py` für dieses eine Feld,
Prüfung in `rules/level2/field_length_rule.py` (Regel 1.2.2.6).

---

## 4. Offene Befunde — hier brauche ich eine Entscheidung

### 4.1 `brutto_nullen=False` erzeugt eine nicht konforme Datei

Beim letzten Durchgang habe ich das Nullen des Bruttobetrags bei einer
Zuzahlungsforderung auf Knopfdruck umgestellt. Der Schalter sitzt am
**GES-Feld „Gesamtbruttobetrag"** — und genau dieses Feld legt die Anlage fest
(Kapitel 5.5.2, GES):

> „Bei Verarbeitungskennzeichen ‚03': Ist der Gesamtbruttobetrag mit 0,00 zu
> übermitteln."

Mit `brutto_nullen=False` entsteht also eine Datei, die die eigene Regel
1.3.13.5 verletzt — was im Code auch so dokumentiert ist. Die Vorgabe bleibt
`True`, der Korrektur-Editor setzt `False`.

Wichtig für die Einordnung: **die Beträge der einzelnen Leistungspositionen
werden bei VKZ 03 ohnehin nie genullt**, sie werden unverändert übernommen. Was
Sie im Editor als „genullt" gesehen haben, war dieses GES-Feld.

Ich sehe drei Wege und würde den ersten nehmen:

1. Schalter entfernen, GES-Bruttobetrag immer 0,00 (konform, Verhalten wie vor
   meiner Änderung)
2. Schalter behalten, aber im Editor deutlich als „erzeugt eine Datei, die die
   Kasse abweisen wird" beschriften
3. so lassen

### 4.2 Die Reihenfolge innerhalb des INV-Blocks wird nicht geprüft

Die Anlage schreibt die Segmentfolge fest (5.1 Abs. 3 und 4: „in einer fest
definierten Reihenfolge"; 5.5.3.3 im Text; 7.3 für URI: „befindet sich […]
zwischen den Segmenten INV und NAD"):

```
INV → [URI] → NAD → [IMG] → [EVO] → EHE(1-n) [je EHE: TXT, MWS] → ZHE → DIA(1-n) → [SKZ] → BES | GZF
```

Geprüft wird bisher nur, welche Segmente im Block **erlaubt** sind, nicht in
welcher Ordnung. Eine Datei mit `ZHE` vor den `EHE`-Segmenten läuft fehlerfrei
durch — nachgestellt und bestätigt. Eine Testvorlage
(`test_vk02_add_and_delete_positions`) enthält diese Reihenfolge.

Das ist der größte verbliebene Befund. Umsetzbar als Zustandsautomat über die
Segmentfolge je Leistungsbereich; ich habe die Segmentzusammenstellungen dafür
schon extrahiert. Soll ich?

### 4.3 Verarbeitungskennzeichen je Leistungsbereich (Kapitel 7.1)

| Leistungsbereich | verpflichtend ab | zulässige VKZ |
|---|---|---|
| Heilmittel | 01.07.2020 | 02, 03, 04 |
| Heilmittel (Physiotherapie) | 01.10.2025 | 02, 03, 04, **10** |
| Hebammen | 01.10.2025 | 02, 04 |

Geprüft wird derzeit nur, ob das Kennzeichen zur Gesamtliste 01–10 gehört
(`fkt_content_rule`, `VALID_VK`), nicht ob es im jeweiligen Leistungsbereich
zulässig ist. VKZ 10 (Wiederaufnahme) ist im Bereich Heilmittel nur für
Physiotherapie vorgesehen.

Ich habe das **nicht** umgesetzt, weil die Abgrenzung nicht eindeutig aus der
Datei hervorgeht: „Physiotherapie" steckt im `ZHE.Heilmittel-Bereich` (Wert 1)
— das ist aber ein Kann-Feld und darf leer sein. Eine Regel, die bei leerem
Feld anschlägt, würde berechtigte Dateien blockieren. Wie soll sie sich
verhalten: nur warnen, nur bei gefülltem Feld prüfen, oder gar nicht?

### 4.4 BES, DIA und SKZ sind je Leistungsbereich unterschiedlich definiert

Das Schema hat je Segment **eine** Definition. Die Anlage definiert BES, DIA und
SKZ aber je Leistungsbereich neu. Beispiel `BES` im Bereich S (Modellvorhaben,
5.5.3.13): dort hat es **genau ein Feld** (Gesamtbetrag Brutto), im Schema hat
es fünf. Eine Datei im Bereich S mit Zuzahlungsbeträgen im BES läuft durch.

Für Ihren Bereich B ist die Definition richtig. Die Wirkung ist durchweg
„zu nachsichtig", nicht „weist Richtiges ab" — kritisch ist es also nicht.
Umsetzbar über den Kontextmechanismus, den `SchemaRegistry` schon hat (heute
`SLGA`/`SLLA`, dann zusätzlich der Leistungsbereich).

### 4.5 ZHE.Behandlungsbeginn ist stillgelegt

Die Anlage gibt für dieses Feld Länge und Typ als „-" an, mit dem Hinweis
„Dieses Feld wird nicht mehr gefüllt." Das Schema führt es als `8 AN K`. Eine
Datei, die es füllt, wird nicht beanstandet. Kleinigkeit, aber ein Hinweis wäre
korrekter als Stillschweigen.

---

## 5. Was ich nicht geprüft habe

* **Leistungsbereiche A und C–S** (Kapitel 5.5.3.2 und 5.5.3.4–5.5.3.13). Der
  maschinelle Abgleich läuft dort und zeigt 62 Abweichungen — davon geht der
  größte Teil auf 4.4 zurück (eine BES-Definition für alle Bereiche). Ich habe
  die Tabellenauswertung für diese Kapitel **nicht von Hand nachgeprüft**, wie
  ich es für 5.4, 5.5.2, 5.5.3.1 und 5.5.3.3 getan habe; einzelne der 62 können
  also Artefakte der Auswertung sein. Ich stelle sie deshalb nicht als Befunde
  hin. Wenn diese Bereiche für Sie eine Rolle spielen, arbeite ich sie durch.
* **Anlage 3** (Schlüsselverzeichnis). Die Anlage 1 verweist für die
  Schlüsselausprägungen durchweg auf Anlage 3; geprüft wurden hier nur die
  Verweise, nicht die Schlüssellisten selbst. Für die Codelisten fehlen
  weiterhin die Seiten 27/28 und 35/36 der Anlage 3
  (`verordnungsart`, `verordnungsbesonderheiten`, `genehmigungsart`).
* **Anlage 4** (Begleitzettel) und **Anhang 1 zur Anlage 1** (logischer
  Dateiname), auf die Kapitel 5.4 verweist.
* **Prüfstufe 4** (Kapitel 6.4). Die Anlage vereinbart dafür ausdrücklich keine
  kassenartenübergreifenden Regeln — hier ist nichts zu prüfen.
* **Kapitel 1–4** (Grundsätze, Datenübermittlung, Verschlüsselung). Betrifft
  den Transportweg, nicht den Dateiinhalt.

---

## 6. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `validation_context.py` | Parameterreihenfolge `create_validation_error` — Kern der Reparatur |
| `rules/level2/segment_order_rule.py` | neue Regel 1.2.1.6 (Vorkommen der Segmente) |
| `rules/level2/field_presence_rule.py` | neue Regel 1.2.2.8 (überzählige Felder) |
| `rules/level2/field_length_rule.py` | Mindestlängenprüfung |
| `rules/level3/gzf_content_rule.py` | 1.3.12.3 greift nur noch bei Kennzeichen „0" |
| `schema/schema.py` | `minLen: 22` für `EVO.eVO-ID` |
| `tools/generate_correction.py` | Kennzeichen „1" schließt nicht mehr aus; „1"/„5" bleiben erhalten |
| `tests/test_anlage1_konformitaet.py` | **neu** — 18 Tests gegen die Anlage |
| `tests/test_vk02_correction.py` | Tests zum Kennzeichen „1" umgestellt; zwei unvollständige Vorlagen ergänzt |
| `tests/test_generate_correction.py` | ein Test zum Kennzeichen umgestellt |

Testlauf: **318 erfolgreich, 0 Fehler** (6 übersprungen — parametrisierte
Tests, die der lokale Läufer nicht aufklappt).

Die Auswertungsskripte der Anlage (`parse_anlage.py`, `diff_schema.py`) liegen
noch außerhalb des Projekts. Sie wären in `werkzeuge/anlage1/` gut aufgehoben —
beim nächsten Versionswechsel der Technischen Anlage ist der Abgleich damit
eine Sache von Minuten statt eines Tages. Sagen Sie Bescheid, dann lege ich sie
mit ab.

---

# Teil 2: Abgleich mit Anlage 3 (Schlüsselverzeichnisse)

Grundlage: *Schlüsselverzeichnisse — Anlage 3 zu den Richtlinien nach § 302
SGB V*, GKV-Spitzenverband, Version 21, Stand 19.09.2025, anzuwenden ab
01.10.2025, 58 Seiten.

Anlage 1 verweist für jede Schlüsselausprägung auf Anlage 3. Der erste Teil
dieses Berichts konnte diese Verweise deshalb nur feststellen, nicht prüfen.
Das ist hiermit nachgeholt.

## 1. Vorgehen und Abdeckung

Aus Anlage 1 wurde zunächst maschinell erhoben, welche Felder der von py-esol
verarbeiteten Segmente auf welchen Abschnitt der Anlage 3 verweisen. Genau
diese Abschnitte wurden gelesen und mit den Codelisten und den Prüfregeln
verglichen.

| Abschnitt | Schlüssel | Verwendung | Ergebnis |
|---|---|---|---|
| 8.1.2 | Unfall/Sonstiges | ZHE.Unfallkennzeichen | Liste richtig, Prüfung fehlte — ergänzt |
| 8.1.2.1 | BVG/SER | ZHE.Kennzeichen BVG/Sonstiges/SER | Liste richtig, Prüfung fehlte — ergänzt |
| 8.1.3 | Zuzahlung | ZHE.Zuzahlungskennzeichen | Liste richtig, **Prüfung zu weit** — korrigiert |
| 8.1.4 | Rechnungsart | REC.Rechnungsart | in Ordnung |
| 8.1.5.1 | Abrechnungscode | EHE.Abrechnungscode | Liste unvollständig — ergänzt; neue Prüfung gegen 8.1.14 |
| 8.1.5.2 | Tarifkennzeichen | EHE.Tarifkennzeichen | Liste unvollständig — ergänzt; neue Prüfung des Tarifbereichs |
| 8.1.6 | Summenstatus | GES.Status | **Zuordnungsregel falsch umgesetzt** — korrigiert |
| 8.1.7 | Verarbeitungskennzeichen | FKT.Verarbeitungskennzeichen | in Ordnung |
| 8.1.11 | Verordnungsbesonderheiten | ZHE | **Liste falsch belegt** — korrigiert, Prüfung ergänzt |
| 8.1.12 | Verordnungsart bei Heilmitteln | ZHE | **Liste und Prüfung falsch** — korrigiert |
| 8.1.14 | Sammelgruppenschlüssel | UNB.Leistungsbereich | in Ordnung; jetzt auch Grundlage der EHE-Prüfung |
| 8.1.17 | Art der Genehmigung | SKZ | Liste war leer, keine Prüfung — beides ergänzt |
| 8.1.18 | Beleginformation | INV.Beleginformation | Liste richtig, **Prüfung zu weit** — korrigiert |
| 8.2.1 | Abrechnungspositionsnummer Heilmittel | EHE | **Prüfung zu weit** — korrigiert |
| 8.5 | Länderkennzeichen | NAD | verweist auf ein Dokument außerhalb der Anlage |
| 8.6 | Mengeneinheiten | (andere Leistungsbereiche) | Liste ergänzt |

Nicht bearbeitet, weil sie andere Leistungsbereiche betreffen: 8.1.10
(Hilfsmittel), 8.1.13 (Zuzahlungsart, Hilfsmittel), 8.1.15 (Anwendungsort,
Hilfsmittel), 8.1.16 (Geburtsdatum des Kindes, Hebammen), 8.1.19
(Ersatz-Beschäftigtennummer, Intensivpflege), 8.2.2 bis 8.2.14, 8.3 und 8.4.
Ebenfalls nicht bearbeitet: 8.1.1 (Versichertenstatus KVK, wird seit
01.10.2014 nicht mehr verwendet) und 8.1.8 (entfällt ab TA 3 Version 16).

## 2. Befunde

### 2.1 Vier Prüfungen waren zu weit gefasst

Vier Regeln akzeptierten Werte, die es in den Schlüsselverzeichnissen nicht
gibt. Alle vier folgen demselben Muster: die Regel prüfte "eine Stelle,
numerisch" statt gegen die Schlüsselwerte.

| Feld | Schlüssel | erlaubt laut Anlage | Regel akzeptierte |
|---|---|---|---|
| ZHE.Zuzahlungskennzeichen | 8.1.3 | 0–5 | 0–9 |
| ZHE.Kennzeichen Verordnungsart | 8.1.12 (+99 aus Anlage 1) | 01–05, 10, 11, 99 | 01–20, 99 |
| INV.Beleginformation | 8.1.18 | 0, 1, 2 | 0–9 |
| EHE.Abrechnungspositionsnummer | 8.2.1 | genau 5 Stellen | bis 5 Stellen |

Bei der Verordnungsart lag der Fall doppelt: die Liste `VALID_VERORDNUNGSART`
stand im Regelcode, wurde aber **nie benutzt** — geprüft wurde nur
"zweistellig numerisch". Alle vier sind jetzt gegen die Schlüsselwerte geprüft.

### 2.2 Der Summenstatus wurde falsch abgeleitet

Anlage 3, Abschnitt 8.1.6 ist eindeutig: es zählt allein die **erste** Ziffer
des Versichertenstatus — 1 → 11 (Mitglieder), 3 → 31 (Angehörige), 5 → 51
(Rentner). "Die zweite bis fünfte Ziffer im Feld Versichertenstatus wird bei
der Kennzeichnung der Summenstatus nicht berücksichtigt."

An zwei Stellen wurden die ersten **zwei** Stellen genommen:

* `ges_content_rule` bildete daraus "10", "30", "50" — Werte, die der
  Schlüssel nicht kennt. Kein GES-Status stimmte damit je überein. Der
  Abgleich je Status lief ins Leere; er wurde berechnet und nie ausgewertet.
* `generate_correction` nahm ebenfalls die zwei Stellen, verglich sie mit den
  GES-Zeilen der Ursprungsdatei und griff bei Nichttreffen auf den ersten
  passenden oder gar den ersten überhaupt vorhandenen Status zurück.

Die zweite Stelle war ein echter Fehler beim Erzeugen. Nachgestellt: eine
Datei mit einem Angehörigen (Status 30000) und einem Rentner (50000), deren
SLGA nur GES+00 und GES+31 enthält. Erzeugt wurde daraus

```
GES+00+180,00+200,00+20,00'
GES+31+180,00+200,00+20,00'      <- beide Belege unter "Angehörige"
```

statt richtig

```
GES+00+180,00+200,00+20,00'
GES+31+90,00+100,00+10,00'
GES+51+90,00+100,00+10,00'
```

Die Gesamtsumme stimmte, die Aufteilung nach Versichertenstatus nicht — und
keine Regel hat es gemerkt. Behoben durch `ContentHelper.summenstatus()`, die
8.1.6 direkt umsetzt und von beiden Stellen benutzt wird.

Dazu die fehlende Prüfung, neue Regel **1.3.13.7**: jede GES-Statuszeile wird
jetzt gegen die Belege dieses Versichertenstatus gestellt (Anlage 1 zum
GES-Segment: "Die Betragssumme des Versichertenstatus (SLGA) entspricht den
Summen der Abrechnungsfälle (SLLA), die diesen Status beinhalten"), und ein
Status mit Belegen aber ohne Statuszeile fällt auf. Alle 53 Echtdateien
bestehen die Prüfung.

### 2.3 Zwei Codelisten waren falsch belegt

* **Verordnungsbesonderheiten (8.1.11)** stand mit den Codes 0, 1, 2, 3 in der
  Liste. Der Schlüssel besetzt **1, 2, 3, 4, 7, 8 und 9** — es gibt keine 0,
  und 4, 7, 8, 9 fehlten. Ein Beleg mit "4" (Entlassmanagement) wäre in der
  Anzeige als unbekannt erschienen.
* **Verordnungsart (8.1.12)** stand mit 01 bis 20 und 99 in der Liste. Der
  Schlüssel besetzt **01 bis 05, 10 und 11**; 06–09 und 12–20 gibt es nicht.

Beide sind jetzt wortgleich aus der Anlage übernommen, einschließlich der
Werte, die die Anlage selbst als "nicht belegt" führt — das ist eine Aussage
der Quelle und kein fehlender Klartext.

### 2.4 Die offenen Listen sind gefüllt

Die Lücken aus dem vorigen Durchgang sind geschlossen:

| Liste | vorher | jetzt | Quelle |
|---|---|---|---|
| verordnungsart | 21 Codes ohne Text | 8 Codes mit Text | 8.1.12 + Anlage 1 |
| verordnungsbesonderheiten | 4 Codes ohne Text | 7 Codes mit Text | 8.1.11 |
| genehmigungsart | leer | 22 Codes | 8.1.17 |
| abrechnungscode | 16 Codes | 64 Codes (vollständig) | 8.1.5.1 |
| tarifbereich | 12 Codes | 62 Codes (alle vergebenen) | 8.1.5.2 |
| heilmittelbereich | 5 Codes ohne Text | 5 Codes mit Text | Anlage 1, ZHE |
| mengeneinheiten | — | 14 Codes | 8.6 |
| sondertarif | 2 Codes | über Bereiche aufgelöst | 8.1.5.2 |

Zum Sondertarif: Anlage 3 definiert die 3. bis 5. Stelle des
Tarifkennzeichens nicht als Einzelschlüssel, sondern in Bereichen. Eine
Codetabelle kann das nicht abbilden, deshalb löst
`codelisten.sondertarif_bereich()` die Bereiche auf. Damit bekommt das in
Ihren Dateien durchgehend verwendete **"501"** erstmals einen Text
("Sondertarifvereinbarung zwischen Leistungserbringern und Kostenträgern") —
vorher stand dort nichts. Ein Eintrag in `codelisten.json` hat weiterhin
Vorrang, dort können hauseigene Sondertarife benannt werden.

### 2.5 Vier Prüfungen fehlten ganz

Neu, alle unmittelbar aus den Schlüsselverzeichnissen:

* **1.3.9.12 bis 1.3.9.14** — ZHE.Verordnungsbesonderheiten gegen 8.1.11,
  ZHE.Unfallkennzeichen gegen 8.1.2, ZHE.Kennzeichen BVG/Sonstiges/SER gegen
  8.1.2.1.
* **1.3.9.15** (Warnung) — ZHE.Behandlungsbeginn ist laut Anlage 1
  stillgelegt: "Dieses Feld wird nicht mehr gefüllt." Ein gefülltes Feld macht
  die Datei nicht ungültig, wird aber jetzt angemahnt. Das schließt den offenen
  Punkt 4.5 aus Teil 1.
* **1.3.8.7** — der Abrechnungscode muss zum Leistungsbereich des UNB-Segments
  passen. Anlage 3, Abschnitt 8.1.14 ordnet die Codes den
  Sammelgruppenschlüsseln zu; im Leistungsbereich B sind 21–29 und 71–74
  zulässig. Eine Datei mit "B" im UNB und einem Hilfsmittelcode im EHE ist in
  sich widersprüchlich und lief vorher durch.
* **1.3.8.8** — der Tarifbereich (1. und 2. Stelle des Tarifkennzeichens) muss
  vergeben sein. 26–49 und 76–89 führt die Anlage als "noch zu vergeben".
* **1.3.13.8** — GES.Status muss ein Schlüsselwert nach 8.1.6 sein.
* **1.3.14.1 bis 1.3.14.4** — das SKZ-Segment (Kostenzusage/Genehmigung) hatte
  gar keine Inhaltsprüfung. Neu in `rules/level3/skz_content_rule.py`:
  Genehmigungskennzeichen, Datum der Genehmigung, und die Art der Genehmigung
  gegen 8.1.17 — samt der Prüfung, dass deren erste Stelle zum Leistungsbereich
  passt. Für Heilmittel ist allein **B2** besetzt; B1 führt die Anlage als
  nicht belegt. In Ihren 53 Dateien kommt kein SKZ vor, die Regel greift also
  erst, wenn eine Kostenzusage übermittelt wird — dann aber genau dort, wo
  sonst niemand hinschaut.

## 3. Offen

* **Therapiefrequenz (ZHE, 17. Feld).** Anlage 3 hat dazu keinen Schlüssel.
  Anlage 1 sagt nur, wie der Wert zu bilden ist: bei einer Frequenzspanne der
  höchste Wert ("1-3 = 3"), und "0" bei Podologie, Ernährungstherapie oder
  Verordnungen ohne Frequenzangabe. Was 1 bis 9 im Klartext bedeuten, steht
  dort nicht — die Liste bleibt daher leer und zeigt "kein Klartext
  hinterlegt". Wenn Sie die Bedeutung nennen, trage ich sie nach.
* **Länderkennzeichen (8.5).** Die Anlage verweist auf *Anlage 8 zum
  Gemeinsamen Rundschreiben DEÜV* auf gkv-datenaustausch.de. Damit ist jetzt
  klar, wo die früher gesuchten Länderdateien herkommen.
* **Verarbeitungskennzeichen je Leistungsbereich (Punkt 4.3 aus Teil 1).**
  Anlage 3, Abschnitt 8.1.7 verweist ausdrücklich zurück: "Die Anwendbarkeit
  der Schlüsselwerte (außer '01') ergeben sich aus der Tabelle in Anlage 1,
  Abschnitt 7.1." Eine Beobachtung dazu: in allen 140 ZHE-Segmenten Ihrer
  Dateien steht im Feld Heilmittel-Bereich die **"1" — Physiotherapie**. Damit
  ist VKZ 10 für Ihre Dateien zulässig, und eine Prüfung wäre umsetzbar, wenn
  wir uns auf das Verhalten bei leerem Feld einigen.
* **Schlüssel Prüfvermerk (8.1.9).** Betrifft die Antwort der Kasse an den
  Leistungserbringer (01 = wird bezahlt, 02 = zurückgewiesen, 03 = berichtigt,
  04 = gekürzt, 05 = wird geprüft), nicht die Abrechnungsdatei. Als Codeliste
  wäre er für die Hotline nützlich, wenn dort Kassenantworten gelesen werden —
  sagen Sie Bescheid.

## 4. Geänderte Dateien (Teil 2)

| Datei | Änderung |
|---|---|
| `data/codelisten.json` | sieben Listen gefüllt oder berichtigt, Quellenangaben je Liste |
| `codelisten.py` | `sondertarif_bereich()` — Bereiche der 3.-5. Stelle nach 8.1.5.2 |
| `verordnung.py` | Sondertarif-Text kommt jetzt aus den Bereichen |
| `rules/level3/content_helper.py` | `summenstatus()` nach 8.1.6 |
| `rules/level3/zhe_content_rule.py` | Zuzahlung 0-5, Verordnungsart gegen 8.1.12, drei neue Prüfungen, Warnung zum Behandlungsbeginn |
| `rules/level3/ehe_content_rule.py` | Positionsnummer genau 5-stellig, Abrechnungscode gegen 8.1.14, Tarifbereich gegen 8.1.5.2 |
| `rules/level3/inv_content_rule.py` | Beleginformation 0-2 |
| `rules/level3/ges_content_rule.py` | Summenstatus nach 8.1.6, Abgleich je Statuszeile (1.3.13.7), Schlüsselprüfung (1.3.13.8) |
| `rules/level3/skz_content_rule.py` | **neu** — Inhaltsprüfung des SKZ-Segmentes |
| `esol_validator.py` | SKZ-Regel registriert |
| `tools/generate_correction.py` | Summenstatus aus dem Versichertenstatus statt aus den GES-Zeilen des Originals |
| `tests/test_anlage3_schluessel.py` | **neu** — 19 Tests gegen die Schlüsselverzeichnisse |
| `tests/anlage_basis.py` | **neu** — gemeinsame Hilfen beider Abgleichstests |
| `tests/test_verordnung.py` | Tests an die gefüllten Listen angepasst |

Testlauf: **318 erfolgreich, 0 Fehler** (6 übersprungen — parametrisierte
Tests, die der lokale Läufer nicht aufklappt). Alle 53 Dateien in
`testdata/in/` melden weiterhin genau dieselben 7 Fehler wie vor dem Abgleich
(1.2.3.1 in ESOL0167, ESOL0305, ESOL0325) — keine der neuen Prüfungen erzeugt
einen Fehlalarm auf echten Daten.
