# py-esol — ESOL Abrechnungs- & Validierungs-Toolkit (§ 302 SGB V)

`py-esol` ist ein mächtiges Python-Framework und Desktop-Tool zur **Validierung, Konvertierung und Generierung von ESOL-Abrechnungsdateien** (Elektronische Datenübertragung Sonstiger Leistungserbringer) gemäß **§ 302 SGB V und Technische Anlage 1**.

Es unterstützt Leistungserbringer im Heilmittelbereich (Physiotherapie, Ergotherapie, Logopädie, Podologie, Ernährungsberatung) sowie Softwareentwickler bei der Prüfung und Erstellung von EDIFACT-Abrechnungen.

---

## 🌟 Hauptfunktionen

* **🔍 4-Stufige Validierungs-Engine**:
  * **Stufe 1 (Struktur & Hülle)**: EDIFACT-Umschläge (`UNB`, `UNH`, `UNT`, `UNZ`), Zeichensatz (ISO-8859-15), Segment-Trennzeichen (`'`) und Element-Trennzeichen (`+`, `:`).
  * **Stufe 2 (Syntax & Segmentfolge)**: Reihenfolgeprüfungen für Nachrichten (`SLGA`, `SLLA`) und `INV`-Blöcke.
  * **Stufe 3 (Inhalt & Semantik)**: IK-Prüfziffern (Modulo 10), Datumsformate, Komma-Dezimalwerte, Diagnose-Codes (`DIA`), Abgleich von `GES`-Summen mit `BES`-Einzelsummen.
  * **Stufe 4 (Sammelgruppen-Regeln)**: Heilmittelspezifische Regeln für die Sammelgruppen 1 bis 6 (Physio, Ergo, Logo, Podologie, etc.).
* **💰 Korrektur- & Nachforderungs-Generator (VKZ 02, 03, 04, 10)**:
  * **VKZ 02 (Nachforderung)**: Erstellung von Teilnachforderungen nach Absetzungen.
  * **VKZ 03 (Zuzahlungsforderung § 43c SGB V)**: Generierung von Zuzahlungsforderungen bei Verweigerung/Nichtzahlung durch Patienten (`GZF`-Segment).
  * **VKZ 04 (Korrekturrechnung)**: Neuberechnung/Korrektur abgesetzter Rechnungsbelege.
  * **VKZ 10 (Wiederaufnahme Blankoverordnung § 125a SGB V)**: Abrechnung nach Unterbrechung bei Blankoverordnungen.
  * **Interaktive Belegauswahl**: Gezielte Auswahl einzelner Belege per Checkbox-Dialog in der GUI mit automatischer Neuberechnung aller `GES`-Gesamtsummen.
* **📄 Auftragsdatei-Generator (`.auf`)**:
  * Automatische Erstellung von EDIFACT-Begleitdateien (`50000001...`) für die physikalische Datenübertragung.
* **🔄 UTF-8 ➔ ISO-8859-15 Konverter**:
  * Stapelkonvertierung fehlerhaft kodierter Dateien in den geforderten ISO-8859-15 EDIFACT-Standard.
* **📋 Verordnungs-Ansicht (Support & Hotline)**:
  * **Virtuelles Muster 13/18**: Eigene Box „Verordnung / verordnender Arzt" mit Verordnungsdatum,
    BSNR/LANR, Verordnungsart, Diagnosegruppe, dekodierter Leitsymptomatik (Stellen a/b/c/X),
    Therapiefrequenz, Therapiebericht, Hausbesuch, Dringlichkeit, Verordnungsbesonderheiten,
    ICD-10-Diagnosen (`DIA`), Genehmigung (`SKZ`) und Ursprungsrechnung (`URI`) — alle
    17 `ZHE`-Felder statt bisher nur dem Zuzahlungskennzeichen.
  * **Behandlungsverlauf statt Positionsflut**: Gleiche Leistungen werden zu Leistungsgruppen
    zusammengefasst (Anzahl Termine, Zeitraum von–bis, Summen); die Einzeltermine bleiben
    aufklappbar. Aus 54 `EHE`-Zeilen werden 4 lesbare Gruppen.
  * **Plausibilitätshinweise**: Behandlung vor Verordnungsdatum, fehlende Pflichtfelder,
    fehlendes `DIA`, Zuzahlungs-Widersprüche, fehlende individuelle Leitsymptomatik.
  * **Rezept-Baum**: `UNB → Nachricht → Verordnung/Beleg → Verordnungsdaten / Diagnosen /
    Leistungen / Belegsumme`, jedes Feld mit Namen aus der `SchemaRegistry`; Filter durchsucht
    den gesamten Baum inklusive Unterknoten.
  * **Editierbare Klartexte**: `data/codelisten.json` (Verordnungsart, Diagnosegruppe,
    Positionsnummern, …). Codes ohne Eintrag werden ausdrücklich als
    *„kein Klartext hinterlegt"* angezeigt — es wird nie ein Text geraten.
* **🖥️ Grafische Benutzeroberfläche (Tkinter GUI)**:
  * Moderne Desktop-Oberfläche zur einfachen Bedienung ohne Kommandozeilenkenntnisse.

---

## 🚀 Installation

### Voraussetzungen

* Python **3.10+**

### Repository klonen & Abhängigkeiten installieren

```bash
git clone https://github.com/user/py-esol.git
cd py-esol

# Virtuelle Umgebung erstellen (optional, aber empfohlen)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/macOS

# Entwicklungs- & Test-Abhängigkeiten installieren
pip install -r requirements.txt
```

---

## 💻 Benutzung

### 1. Grafische Benutzeroberfläche (GUI)

Starten der Desktop-Anwendung:

```bash
python main.py
```

Oder Verwenden der vorkompilierten Binärdatei `dist/pyesol.exe`.

**Funktionen in der GUI**:

* **Dateiauswahl**: Einzelne Datei, mehrere Dateien oder Ordner auswählen.
* **`▶ Validieren`**: Führt die 4-stufige Prüfung durch und gibt detaillierte Fehlermeldungen aus.
* **`🔄 UTF-8 ➔ ISO`**: Konvertiert ausgewählte Dateien zu ISO-8859-15.
* **`📄 .auf erstellen`**: Erstellt passende `.auf`-Auftragsdateien.
* **`🛠️ Korrektur / Zuzahlung`**: Öffnet den interaktiven Konfigurator zur Belegauswahl und VKZ-Generierung (02, 03, 04, 10).
* **Tab `📜 Virtuelles Verordnungsblatt`**: Verordnung im Muster-13/18-Layout inklusive
  Arzt-, Diagnose- und Leitsymptomatik-Daten sowie gruppiertem Behandlungsverlauf.
* **Tab `📊 Beleg-Dashboard & Rezept-Baum`**: Belegtabelle mit Fehlerstatus und darunter der
  Klartext-Baum der gesamten Datei.

### Klartexte pflegen

Bezeichnungen zu Verordnungsart, Diagnosegruppe, Therapiefrequenz, Heilmittel-Bereich und
Abrechnungspositionsnummern stehen in `data/codelisten.json`. Leere Einträge (`""`) sind
absichtlich leer und erscheinen in der GUI als *„kein Klartext hinterlegt"*, damit in der
Hotline kein geratener Text genannt wird. Nach dem Nachtragen genügt der Button
**`🔄 Codelisten neu laden`** im Verordnungsblatt — kein Neustart nötig.

Positionsnummern dürfen nach Abrechnungscode gestaffelt werden:

```json
"positionsnummern": {
  "*":  { "59702": "Allgemeine Position" },
  "26": { "54103": "Ergotherapeutische Einzelbehandlung" }
}
```

Im gebauten `.exe` wird zuerst `data/codelisten.json` **neben der EXE** gesucht, danach die
gebündelte Datei. Mit der Umgebungsvariablen `PY_ESOL_CODELISTEN` lässt sich ein beliebiger
Pfad erzwingen.

---

### 2. Kommandozeile (CLI)

#### A. Einzeldatei validieren

```bash
python validate.py path/to/ESOL_FILE --stufe=4 --warnings
```

Options:

* `--stufe=1..4`: Prüfstufe wählen (Standard: 4).
* `--warnings`: Zeigt auch Warnungen an.

#### B. Batch-Validierung eines ganzen Ordners

```bash
python batch_validate.py path/to/directory --stufe=4 --report=validation_report.txt
```

#### C. Korrektur- / Zuzahlungsdatei generieren

```bash
# VK 03 (Zuzahlungsforderung § 43c SGB V)
python tools/generate_correction.py path/to/ESOL_FILE -t 03

# VK 02 (Nachforderung) mit gefilterten Belegen
python tools/generate_correction.py path/to/ESOL_FILE -t 02 --belege A123456789 A987654321

# VK 10 (Wiederaufnahme Blankoverordnung § 125a SGB V)
python tools/generate_correction.py path/to/ESOL_FILE -t 10
```

#### D. Auftragsdatei (.auf) erstellen

```bash
python tools/generate_auf.py path/to/ESOL_FILE
```

#### E. UTF-8 zu ISO-8859-15 konvertieren

```bash
# Ersetzt die Datei an ihrem Platz — der Dateiname bleibt unverändert
python tools/convert_utf8_to_iso.py path/to/ESOL0253

# Ganzen Ordner konvertieren (alle Dateien werden ersetzt)
python tools/convert_utf8_to_iso.py path/to/ordner

# Kopien in einen anderen Ordner schreiben, Dateinamen bleiben gleich
python tools/convert_utf8_to_iso.py path/to/ESOL0253 --out-dir konvertiert/
```

> **Der Dateiname wird nie verändert.** ESOL-Dateien tragen bewusst keine Endung
> (`ESOL0253`), und der Name gehört zur Einreichung — eine angehängte Endung würde
> die Datei beim Abrechnungszentrum unbrauchbar machen. Zeigt das Ziel auf die
> Quelle (das ist der Standard, und auch was die GUI tut), wird die Datei ersetzt.
> Geschrieben wird über eine temporäre Datei und ein atomares Umbenennen, damit ein
> Abbruch das Original nicht halb überschrieben zurücklässt.
> `--inplace` ist dadurch wirkungslos und nur noch aus Kompatibilität vorhanden.

---

## 🧪 Tests ausführen

Das Projekt verfügt über ein umfassendes `pytest`-Testpaket:

```bash
python -m pytest
```

Output:

```bash
============================= 78 passed ==============================
```

Die Testsuite darf keine modalen Dialoge öffnen — eine `autouse`-Fixture in
`tests/conftest.py` ersetzt alle `messagebox`-, `filedialog`- und
`simpledialog`-Funktionen durch nicht blockierende Stubs und protokolliert die
Aufrufe. Ein Test kann das Protokoll auswerten:

```python
def test_x(dialog_protokoll):
    ...
    assert dialog_protokoll.wurde_aufgerufen("showinfo")
```

Braucht ein Test wirklich echte Dialoge, hebt `@pytest.mark.echte_dialoge` das auf.

---

## 📁 Projektstruktur

```txt
py-esol/
├── esol_validator.py             # Hauptklasse EsolValidator
├── verordnung.py                 # Verordnungs-Auswertung (ZHE/DIA/SKZ, Positionsgruppen)
├── codelisten.py                 # Loader für die editierbaren Klartext-Tabellen
├── data/
│   └── codelisten.json           # Editierbare Klartexte (Verordnungsart, Positionsnummern, …)
├── validate.py                   # CLI-Validator für Einzeldateien
├── batch_validate.py             # CLI-Batch-Validator für Ordner
├── main.py                       # Hauptfenster der Tkinter GUI
├── gui_muster13_preview.py       # Virtuelles Verordnungsblatt (Muster 13/18)
├── gui_recipe_tree.py            # Klartext-Rezept-Baum
├── gui_beleg_dashboard.py        # Beleg-Dashboard mit KPI-Kacheln
├── support_helper.py             # Fehlerübersetzung, Ticket-/HTML-Bericht, Baumaufbau
├── gui_correction_dialog.py      # Interaktiver Korrektur- & Belegauswahl-Dialog
├── pyesol.spec                   # PyInstaller Build-Spezifikation
├── parser/
│   ├── segment_tokenizer.py      # EDIFACT Segment-Tokenizer
│   └── edifact_parser.py         # EDIFACT Parser für Nachrichtenstrukturen
├── rules/                        # Modulare Validierungsregeln
│   ├── level1/                   # Struktur & Encoding
│   ├── level2/                   # Syntax & Segmentfolge
│   ├── level3/                   # Semantik, IK-Prüfziffern, GES-Summen
│   └── level4/                   # Sammelgruppen 1-6 (Physio, Ergo, Logo, Podologie)
├── tools/
│   ├── convert_utf8_to_iso.py    # UTF-8 -> ISO-8859-15 Konverter
│   ├── generate_auf.py           # Generierung von .auf Auftragsdateien
│   └── generate_correction.py    # Generator für VKZ 02, 03, 04, 10
└── tests/                       # Pytest Test-Suite
```

---

## 📜 Lizenz & Spezifikation

Implementiert gemäß **Technische Anlage 1 zur Vereinbarung über den Datenaustausch mit Leistungserbringern sonstiger Leistungserbringer (§ 302 SGB V)**.
