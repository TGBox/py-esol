# -*- mode: python ; coding: utf-8 -*-
#
# Die maßgebliche Build-Spezifikation für py-esol.
#
#   pyinstaller py-esol.spec --noconfirm --clean
#
# Ergebnis: dist/py-esol.exe — eine einzelne Datei ohne Python-Installation,
# GUI-Modus (kein Konsolenfenster).
#
# Wichtig zum Verständnis: die GUI startet ihre Werkzeuge (Validieren,
# UTF-8 -> ISO, .auf, Korrektur) als eigenen Prozess über
# [sys.executable, <skriptpfad>, ...]. Im gefrorenen Zustand ist sys.executable
# die EXE selbst; main.py wertet sys.argv[1] aus und ruft das passende
# eingebettete Modul auf (siehe den Dispatcher am Ende von main.py). Die
# .py-Dateien müssen deshalb NICHT mitgeliefert werden — der Pfad dient nur
# als Wegweiser. Wer diesen Dispatcher ändert, macht die EXE unbrauchbar.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # Editierbare Klartext-Tabellen für die Verordnungs-Anzeige mitliefern.
    # Zur Laufzeit wird zuerst neben der EXE (data/codelisten.json) gesucht,
    # damit Bezeichnungen ohne Neu-Build gepflegt werden können.
    # Alle Nachschlagetabellen werden zur Laufzeit zuerst neben der EXE gesucht
    # (data/<name>.json) und erst danach im Bundle. So lässt sich ein neuer
    # Stand ohne Neu-Build einspielen: Datei daneben legen, im Verordnungsblatt
    # 'Codelisten neu laden'.
    datas=[
        ('data/codelisten.json', 'data'),
        # Positionsbezeichnungen aus der GKV-Heilmittelpreisstammdatei
        # (tools/import_hmp.py)
        ('data/heilmittelpreise.json', 'data'),
        # Positionsbezeichnungen aus Heilmittelkatalog, BG/UV und dem
        # Gebührenverzeichnis für Heilpraktiker (tools/import_heilmittelkatalog.py)
        ('data/heilmittelkatalog.json', 'data'),
        # IK-Verzeichnis: Kassenname, Anschrift, Datenannahmestelle
        # (tools/import_kostentraeger.py)
        ('data/kostentraeger.json', 'data'),
        # Diagnosegruppen und ICD-Verordnungsbedarf aus den
        # KBV-Stammdateien (tools/import_kbv_stammdaten.py)
        ('data/diagnosegruppen.json', 'data'),
        ('data/verordnungsbedarf.json', 'data'),
    ],
    # Alle Imports im Projekt sind statisch, PyInstaller findet sie selbst.
    # reportlab (Begleitzettel-PDF) wird über pyinstaller-hooks-contrib erfasst.
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Test- und Build-Werkzeuge gehören nicht in die Auslieferung.
    excludes=['pytest', '_pytest', 'PyInstaller'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='py-esol',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX aus: es bringt bei ~21 MB wenig, verlängert den Build und ist der
    # häufigste Grund für Fehlalarme von Virenscannern auf Kundenrechnern.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Eigenes Icon: Datei ablegen und die nächste Zeile einkommentieren.
    # icon='assets/py-esol.ico',
)
