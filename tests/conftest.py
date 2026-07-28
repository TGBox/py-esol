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