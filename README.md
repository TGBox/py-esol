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
python tools/convert_utf8_to_iso.py path/to/ESOL_FILE
```

---

## 🧪 Tests ausführen

Das Projekt verfügt über ein umfassendes `pytest`-Testpaket mit 44 Unit-Tests:

```bash
python -m pytest
```

Output:

```bash
============================= 44 passed in 0.19s ==============================
```

---

## 📁 Projektstruktur

```txt
py-esol/
├── esol_validator.py             # Hauptklasse EsolValidator
├── validate.py                   # CLI-Validator für Einzeldateien
├── batch_validate.py             # CLI-Batch-Validator für Ordner
├── main.py                        # Hauptfenster der Tkinter GUI
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
└── tests/                        # Pytest Test-Suite (44 Tests)
```

---

## 📜 Lizenz & Spezifikation

Implementiert gemäß **Technische Anlage 1 zur Vereinbarung über den Datenaustausch mit Leistungserbringern sonstiger Leistungserbringer (§ 302 SGB V)**.
