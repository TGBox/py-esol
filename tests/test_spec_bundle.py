"""
Wächter über py-esol.spec: alles, was zur Laufzeit von der Platte gelesen wird,
muss in der EXE mitgeliefert sein.

Hintergrund: die Vorlagenbilder des virtuellen Verordnungsblatts fehlten in der
Spec. Aus dem Projektbaum heraus fällt das nicht auf, weil assets/ dort immer
gefunden wird — in der gepackten EXE zeigte das Muster-13-Fenster dagegen eine
leere Seite, auf der die Daten an den richtigen Stellen standen. Der Renderer
prüft nämlich mit os.path.exists() und weicht bei fehlender Vorlage
stillschweigend auf eine leere Fläche aus.

Genau diese Kombination — stiller Rückfall plus Fehler nur im gepackten
Zustand — soll hier nicht mehr unbemerkt entstehen können.
"""

import ast
import re
from pathlib import Path

import pytest

PROJEKT = Path(__file__).resolve().parent.parent
SPEC = PROJEKT / "py-esol.spec"

# Dateien, die das Programm zur Laufzeit liest. Jede muss in der Spec stehen.
LAUFZEIT_DATEIEN = [
    "data/codelisten.json",
    "data/heilmittelpreise.json",
    "data/heilmittelkatalog.json",
    "data/kostentraeger.json",
    "data/diagnosegruppen.json",
    "data/verordnungsbedarf.json",
    "assets/Muster13_1280x1280.jpg",
    "assets/muster13_coords.json",
]

# Dateien, die bewusst NICHT mitgeliefert werden — nur Entwicklungshilfen.
NUR_ENTWICKLUNG = [
    "assets/muster13_feld_nummerierung.jpg",
    "assets/muster13_grid_overlay.jpg",
    "assets/BegleitzettelBsp.pdf",
]


def _spec_datas() -> list:
    """
    Liest die datas-Liste aus py-esol.spec.

    Die Spec ist keine gewöhnliche Python-Datei (Analysis, EXE und PYZ sind zur
    Laufzeit von PyInstaller bereitgestellt), deshalb wird sie geparst und nicht
    ausgeführt.
    """
    baum = ast.parse(SPEC.read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        if not (isinstance(knoten.func, ast.Name) and knoten.func.id == "Analysis"):
            continue
        for arg in knoten.keywords:
            if arg.arg == "datas":
                return ast.literal_eval(arg.value)
    raise AssertionError("In py-esol.spec ist kein Analysis(datas=[...]) zu finden")


def test_spec_ist_lesbar():
    assert SPEC.is_file(), "py-esol.spec fehlt — ohne sie kann der CI-Build keine EXE erzeugen"
    datas = _spec_datas()
    assert datas, "datas ist leer — dann liegt keine einzige Tabelle in der EXE"
    for eintrag in datas:
        assert isinstance(eintrag, tuple) and len(eintrag) == 2, eintrag


@pytest.mark.parametrize("relativ", LAUFZEIT_DATEIEN)
def test_laufzeitdatei_ist_in_der_spec(relativ):
    quellen = {q.replace("\\", "/") for q, _ in _spec_datas()}
    assert relativ in quellen, (
        f"{relativ} wird zur Laufzeit gelesen, steht aber nicht in py-esol.spec. "
        f"In der EXE fehlt die Datei dann — und weil der Code still auf einen "
        f"Ersatz ausweicht, fällt das erst beim Anwender auf."
    )


@pytest.mark.parametrize("relativ", LAUFZEIT_DATEIEN)
def test_laufzeitdatei_liegt_im_projekt(relativ):
    """Was die Spec verspricht, muss auch da sein — sonst bricht der Build."""
    assert (PROJEKT / relativ).is_file(), (
        f"{relativ} steht in py-esol.spec, fehlt aber im Projekt. "
        f"Der PyInstaller-Lauf bricht damit ab."
    )


@pytest.mark.parametrize("relativ", NUR_ENTWICKLUNG)
def test_entwicklungshilfen_bleiben_draussen(relativ):
    """
    Kalibrierhilfen und Referenzmuster gehören nicht in die Auslieferung. Wer
    eine davon braucht, hat sie zur Laufzeit gelesen — dann gehört sie nach
    LAUFZEIT_DATEIEN und dieser Test ist anzupassen.
    """
    quellen = {q.replace("\\", "/") for q, _ in _spec_datas()}
    assert relativ not in quellen, f"{relativ} ist eine Entwicklungshilfe und blähst die EXE auf"


def test_jede_spec_datei_hat_ein_zielverzeichnis():
    """
    Der zweite Wert jedes Eintrags ist das Zielverzeichnis in der EXE. Steht
    dort '.', landet die Datei im Wurzelverzeichnis und die Suchpfade in
    codelisten.py bzw. gui_muster13_preview.py finden sie nicht.
    """
    for quelle, ziel in _spec_datas():
        erwartet = quelle.replace("\\", "/").split("/")[0]
        assert ziel == erwartet, (
            f"{quelle} soll nach '{ziel}' — erwartet '{erwartet}', "
            f"weil der Code dort danach sucht"
        )


def test_pillow_ist_deklariert():
    """
    Pillow zeichnet das Verordnungsblatt. Es kam lange nur als Abhängigkeit von
    reportlab mit; fällt es dort weg, bricht gui_muster13_preview.py beim
    Import weg.
    """
    text = (PROJEKT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'"pillow[><=~]', text, re.IGNORECASE), (
        "pillow fehlt in den dependencies von pyproject.toml"
    )


def test_alle_asset_pfade_im_code_sind_abgedeckt():
    """
    Sucht im Quellcode nach os.path.join(..., "assets", "<datei>") und prüft,
    dass jede so gelesene Datei entweder mitgeliefert oder ausdrücklich als
    Entwicklungshilfe geführt wird. Damit fällt eine neu hinzugefügte Vorlage
    auf, ohne dass jemand an diesen Test denken muss.
    """
    muster = re.compile(r'"assets"\s*,\s*"([^"]+)"')
    gefunden = set()
    for pfad in PROJEKT.glob("*.py"):
        gefunden.update(muster.findall(pfad.read_text(encoding="utf-8")))

    assert gefunden, "keine assets-Zugriffe gefunden — ist der Renderer noch da?"

    quellen = {q.replace("\\", "/") for q, _ in _spec_datas()}
    bekannt = quellen | set(NUR_ENTWICKLUNG)
    for datei in sorted(gefunden):
        assert f"assets/{datei}" in bekannt, (
            f"assets/{datei} wird im Code gelesen, ist aber weder in py-esol.spec "
            f"noch als Entwicklungshilfe eingetragen"
        )
