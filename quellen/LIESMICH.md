# Quelldateien der Stammdaten-Importer

Hier liegen die unveränderten Original-Verzeichnisse. Die Importer in `tools/`
lesen sie und schreiben daraus die Nachschlagetabellen in `data/`. Nichts hier
wird zur Laufzeit gelesen — das Programm braucht nur `data/`.

| Datei | Herkunft | Wird gelesen von |
|---|---|---|
| `ktr_parsed.json` | Kostenträgerdatei nach § 302 SGB V, geparst | `import_kostentraeger.py` |
| `ktr_heilfuersorge.json` | Heilfürsorgestellen (Polizei, Bundeswehr, PBeaKK) | `import_kostentraeger.py` |
| `gkvliste.txt` | GKV-IK-Verzeichnis (Tab-getrennt) | `import_kostentraeger.py` |
| `bgliste.txt` | Unfallversicherungsträger (DGUV) | `import_kostentraeger.py` |
| `sdhm_2.10_74_tf2024q0.xml` | KBV-Heilmittelstammdatei | `import_kbv_stammdaten.py` |
| `sdhma_1.30_74_tf2022q1.xml` | KBV-Stammdatei Heilmittelanlagen | `import_kbv_stammdaten.py` |
| `codes.csv` | Heilmittelkatalog, X-Codes mit Leistungstext | `import_heilmittelkatalog.py` |
| `heilmittelpreise.csv` | X-Codes mit Bezeichnung und Kapitel | `import_heilmittelkatalog.py` |
| `codesgroups.csv` | zweistellige Leistungsgruppen | `import_heilmittelkatalog.py` |
| `bgleistungen.csv` | Positionen der UV-Träger | `import_heilmittelkatalog.py` |
| `bgleistungen_alt.csv` | älterer Stand derselben Liste | `import_heilmittelkatalog.py` |
| `heilmittelleistungen_heilpraktiker.csv` | Gebührenverzeichnis Heilpraktiker | `import_heilmittelkatalog.py` |
| `HMP_Stand_01.07.2026.xml` | GKV-Heilmittelpreisstammdatei | `import_hmp.py` |
| `blanko_leistungen_ergo_20250801.xml` | § 125a-Blankoleistungen Ergotherapie | `import_hmp.py` |

## Nicht eingelesen

`heilmittelleistungen_physio.csv` liegt hier zur Vollständigkeit, wird aber
nicht importiert: die `code`-Spalte ist dort mit der Bezeichnung identisch
(`KG;KG;24.08;Physiotherapie`), es gibt also keine Positionsnummer, die sich
nachschlagen ließe.

`blanko_leistungen_ergo_20250801.xml` ist inhaltlich vollständig in
`HMP_Stand_01.07.2026.xml` enthalten — dort mit neuerem Stand und dem Zusatz
"zum Vertrag nach § 125a SGB V" in der Bezeichnung. Der Import führt beide
zusammen, wobei die neuere Datei gewinnt; die Blanko-Datei trägt deshalb
derzeit keine eigene Position bei.

## Einen neuen Stand einspielen

Datei hier ersetzen (Name beibehalten), dann den passenden Importer aufrufen:

```bash
python tools/import_kostentraeger.py
python tools/import_kbv_stammdaten.py
python tools/import_heilmittelkatalog.py
python tools/import_hmp.py quellen/HMP_Stand_01.07.2026.xml
```

Die Importer brechen mit einer Fehlermeldung ab, wenn eine Datei nicht wie
erwartet aussieht — besser das als eine stillschweigend halbleere Zieldatei.
