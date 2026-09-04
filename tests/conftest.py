import sys
from pathlib import Path
import pytest

# (Ihr bestehender Code für den Pfad)
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# HIER DEN IMPORT FÜR IHREN TOKENIZER ANPASSEN
# (Je nachdem, wie Ihre Ordnerstruktur genau heißt,
# z.B. from pyesol.parser.segment_tokenizer import SegmentTokenizer)
from parser.segment_tokenizer import SegmentTokenizer


@pytest.fixture
def tokenizer():
    """Stellt eine Instanz des SegmentTokenizers für alle Testfunktionen bereit."""
    return SegmentTokenizer()


# ---------------------------------------------------------------------------
# Modale Dialoge während der Tests neutralisieren
#
# Ein messagebox- oder filedialog-Aufruf blockiert den Testlauf, bis jemand
# klickt. Lokal ist das nur ärgerlich, im CI läuft der Job ins Timeout. Die
# folgende Fixture ersetzt daher alle Dialogfunktionen von tkinter durch
# Stubs, die sofort einen neutralen Wert liefern und den Aufruf protokollieren.
# ---------------------------------------------------------------------------

# Modulname -> {Funktionsname: Rückgabewert des Stubs}
_DIALOG_RUECKGABEN = {
    "tkinter.messagebox": {
        "showinfo": "ok",
        "showwarning": "ok",
        "showerror": "ok",
        "askquestion": "yes",
        "askyesno": True,
        "askokcancel": True,
        "askyesnocancel": True,
        "askretrycancel": False,
    },
    "tkinter.filedialog": {
        "askopenfilename": "",
        "askopenfilenames": (),
        "asksaveasfilename": "",
        "askdirectory": "",
        "askopenfile": None,
        "askopenfiles": (),
        "asksaveasfile": None,
    },
    "tkinter.simpledialog": {
        "askstring": None,
        "askinteger": None,
        "askfloat": None,
    },
}


class DialogProtokoll(list):
    """
    Liste der während eines Tests abgefangenen Dialogaufrufe.
    Einträge: (voller Funktionsname, args, kwargs).
    """

    def namen(self):
        return [eintrag[0] for eintrag in self]

    def wurde_aufgerufen(self, name: str) -> bool:
        """True, wenn ein Dialog aufgerufen wurde, dessen Name 'name' enthält."""
        return any(name in eintrag[0] for eintrag in self)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "echte_dialoge: Dialogfunktionen von tkinter NICHT durch Stubs ersetzen "
        "(der Test muss dann selbst dafür sorgen, dass nichts blockiert).",
    )


@pytest.fixture(autouse=True)
def dialog_protokoll(request, monkeypatch):
    """
    Ersetzt automatisch alle tkinter-Dialogfunktionen durch nicht blockierende
    Stubs. Ein Test, der das Protokoll auswerten will, fordert diese Fixture
    per Namen an:

        def test_x(dialog_protokoll):
            ...
            assert dialog_protokoll.wurde_aufgerufen("showinfo")

    Mit @pytest.mark.echte_dialoge bleibt tkinter unangetastet.
    """
    protokoll = DialogProtokoll()

    if request.node.get_closest_marker("echte_dialoge"):
        return protokoll

    for modulname, funktionen in _DIALOG_RUECKGABEN.items():
        try:
            __import__(modulname)
            modul = sys.modules[modulname]
        except Exception:
            # Kein tkinter verfügbar (z. B. headless Linux ohne python3-tk):
            # dann kann auch kein Dialog blockieren.
            continue

        for funktionsname, rueckgabe in funktionen.items():
            if not hasattr(modul, funktionsname):
                continue

            def stub(*args, _n=f"{modulname}.{funktionsname}", _r=rueckgabe, **kwargs):
                protokoll.append((_n, args, kwargs))
                return _r

            monkeypatch.setattr(modul, funktionsname, stub, raising=False)

    return protokoll
