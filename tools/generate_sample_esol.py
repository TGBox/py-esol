#!/usr/bin/env python3
"""
Generator für reale, 100% gültige ESOL-Testdateien zur Überprüfung der Muster 13 Verordnungsblatt-Vorschau.
Generiert verschiedene Szenarien (Physiotherapie, Ergotherapie, Logopädie, Zuzahlungspflichtig, Befreit).
"""

import os
import sys
from pathlib import Path

# Project root setup
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from esol_validator import EsolValidator
from rules.level1.encoding_rule import EncodingRule
from rules.level1.msg_count_rule import MessageCountRule
from rules.level1.reference_number_rule import ReferenceNumberRule
from rules.level1.single_invoice_kind_rule import SingleRechnungsartRule
from rules.level1.structure_rule import StructureRule
from rules.level1.version_rule import VersionRule
from rules.level2.decimal_format_rule import DecimalFormatRule
from rules.level2.escape_sequence_rule import EscapeSequenceRule
from rules.level2.field_length_rule import FieldLengthRule
from rules.level2.field_presence_rule import FieldPresenceRule
from rules.level2.field_type_rule import FieldTypeRule
from rules.level2.segment_order_rule import SegmentOrderRule
from rules.level3.bes_content_rule import BesContentRule
from rules.level3.cross_message_rule import CrossMessageRule
from rules.level3.dia_content_rule import DiaContentRule
from rules.level3.ehe_content_rule import EheContentRule
from rules.level3.fkt_content_rule import FktContentRule
from rules.level3.ges_content_rule import GesContentRule
from rules.level3.gzf_content_rule import GzfContentRule
from rules.level3.inv_content_rule import InvContentRule
from rules.level3.nad_content_rule import NadContentRule
from rules.level3.nam_content_rule import NamContentRule
from rules.level3.rec_content_rule import RecContentRule
from rules.level3.unb_content_rule import UnbContentRule
from rules.level3.unt_content_rule import UntContentRule
from rules.level3.uri_content_rule import UriContentRule
from rules.level3.zhe_content_rule import ZheContentRule
from rules.level4.unique_ehe_date_service_rule import UniqueEheDateServiceRule

def create_sample_files(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Physiotherapie (Lumbago - Zuzahlungspflichtig)
    physio_esol = "\n".join([
        "UNB+UNOC:3+104212505+661430035+20260323:1040+00118+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++104212505+101777502+101777502+104212505'",
        "REC+51:0+20260122+1'",
        "GES+00+206,42+240,48+34,06'",
        "GES+31+206,42+240,48+34,06'",
        "NAM+Physio Praxis Muster+++info@physio.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++104212505+101777502+101777502'",
        "REC+51:0+20260122+1'",
        "INV+Z123456789+10001+1+00001'",
        "NAD+Mustermann+Max+19820815'",
        "ZHE+110178400+906716934+20251001+2+WS2a+04+++++1++1110++0+1+2+00501'",
        "DIA+M54.5'",
        "EHE+26:00501+20501+6,00+30,00+20251002+3,00'",
        "EHE+26:00501+29901+6,00+10,08+20251002+1,01'",
        "BES+240,48+34,06+24,06+10,00'",
        "UNT+000011+00002'",
        "UNZ+000002+00118'",
    ]) + "\n"

    (output_dir / "muster13_physio_lumbago.esol").write_text(physio_esol, encoding="iso-8859-15")

    # 2. Ergotherapie (Zuzahlungsbefreit - Erstverordnung EN1)
    ergo_esol = "\n".join([
        "UNB+UNOC:3+101520012+661430035+20260410:0915+00220+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++101520012+101777502+101777502+101520012'",
        "REC+51:0+20260210+1'",
        "GES+00+385,00+385,00+0,00'",
        "GES+11+385,00+385,00+0,00'",
        "NAM+Ergo Therapie Zentrum+++info@ergo.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++101520012+101777502+101777502'",
        "REC+51:0+20260210+1'",
        "INV+A987654321+10000+1+00002'",
        "NAD+Schmidt+Erica+19690930'",
        "ZHE+110178400+906716934+20260201+1+EN1+04+++++1++1110++0+2+2+00501'",
        "DIA+G35'",
        "EHE+26:00501+54001+10,00+38,50+20260205+0,00'",
        "BES+385,00+0,00+0,00+0,00'",
        "UNT+000010+00002'",
        "UNZ+000002+00220'",
    ]) + "\n"

    (output_dir / "muster13_ergo_befreit.esol").write_text(ergo_esol, encoding="iso-8859-15")

    # 3. Logopädie (Folgeverordnung SP1 - Zuzahlungspflichtig)
    logo_esol = "\n".join([
        "UNB+UNOC:3+108018007+661430035+20260505:1420+00305+B+SL030179S03+2'",
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++108018007+101777502+101777502+108018007'",
        "REC+51:0+20260315+1'",
        "GES+00+368,00+420,00+52,00'",
        "GES+31+368,00+420,00+52,00'",
        "NAM+Logopaedie Praxis+++info@logo.de'",
        "UNT+000007+00001'",
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++108018007+101777502+101777502'",
        "REC+51:0+20260315+1'",
        "INV+B456789012+10001+1+00003'",
        "NAD+Weber+Tobias+20150412'",
        "ZHE+110178400+906716934+20260301+2+SP1+04+++++1++1110++0+3+2+00501'",
        "DIA+F80.1'",
        "EHE+26:00501+40101+10,00+42,00+20260305+4,20'",
        "BES+420,00+52,00+42,00+10,00'",
        "UNT+000010+00002'",
        "UNZ+000002+00305'",
    ]) + "\n"

    (output_dir / "muster13_logopaedie.esol").write_text(logo_esol, encoding="iso-8859-15")

    # 4. Mehrere Belege in einer Datei (Sammeldatei)
    sammel_esol = "\n".join([
        "UNB+UNOC:3+104212505+661430035+20260601:1000+00400+B+SL030179S03+2'",
        # Summary Header
        "UNH+00001+SLGA:21:0:0'",
        "FKT+01++104212505+101777502+101777502+104212505'",
        "REC+51:0+20260501+1'",
        "GES+00+591,42+625,48+34,06'",
        "GES+31+206,42+240,48+34,06'",
        "GES+11+385,00+385,00+0,00'",
        "NAM+Therapiezentrum Nord+++info@tz-nord.de'",
        "UNT+000008+00001'",
        # Message 1 (Beleg 00101)
        "UNH+00002+SLLA:21:0:0'",
        "FKT+01++104212505+101777502+101777502'",
        "REC+51:0+20260501+1'",
        "INV+Z123456789+10001+1+00101'",
        "NAD+Mustermann+Max+19820815'",
        "ZHE+110178400+906716934+20251001+2+WS2a+04+++++1++1110++0+1+2+00501'",
        "DIA+M54.5'",
        "EHE+26:00501+20501+6,00+30,00+20251002+3,00'",
        "EHE+26:00501+29901+6,00+10,08+20251002+1,01'",
        "BES+240,48+34,06+24,06+10,00'",
        "UNT+000011+00002'",
        # Message 2 (Beleg 00102)
        "UNH+00003+SLLA:21:0:0'",
        "FKT+01++104212505+101777502+101777502'",
        "REC+51:0+20260501+1'",
        "INV+A987654321+10000+1+00102'",
        "NAD+Schmidt+Erica+19690930'",
        "ZHE+110178400+906716934+20260201+1+EN1+04+++++1++1110++0+2+2+00501'",
        "DIA+G35'",
        "EHE+26:00501+54001+10,00+38,50+20260205+0,00'",
        "BES+385,00+0,00+0,00+0,00'",
        "UNT+000010+00003'",
        "UNZ+000003+00400'",
    ]) + "\n"

    (output_dir / "muster13_sammeldatei_mehrere_belege.esol").write_text(sammel_esol, encoding="iso-8859-15")

    print(f"ESOL Testdateien erfolgreich in '{output_dir}' erstellt!")

    # Validierung prüfen
    validator = EsolValidator(_max_stufe=4, _include_warnings=True)
    validator.register_rule(EncodingRule())
    validator.register_rule(StructureRule())
    validator.register_rule(VersionRule())
    validator.register_rule(SingleRechnungsartRule())
    validator.register_rule(ReferenceNumberRule())
    validator.register_rule(MessageCountRule())
    validator.register_rule(SegmentOrderRule())
    validator.register_rule(FieldPresenceRule())
    validator.register_rule(FieldLengthRule())
    validator.register_rule(FieldTypeRule())
    validator.register_rule(DecimalFormatRule())
    validator.register_rule(EscapeSequenceRule())
    validator.register_rule(UnbContentRule())
    validator.register_rule(FktContentRule())
    validator.register_rule(RecContentRule())
    validator.register_rule(GesContentRule())
    validator.register_rule(NamContentRule())
    validator.register_rule(InvContentRule())
    validator.register_rule(NadContentRule())
    validator.register_rule(ZheContentRule())
    validator.register_rule(DiaContentRule())
    validator.register_rule(EheContentRule())
    validator.register_rule(BesContentRule())
    validator.register_rule(UntContentRule())
    validator.register_rule(GzfContentRule())
    validator.register_rule(UriContentRule())
    validator.register_rule(CrossMessageRule())
    validator.register_rule(UniqueEheDateServiceRule())

    for p in output_dir.glob("*.esol"):
        res = validator.validate(str(p))
        status = "GÜLTIG" if res.is_valid() else "UNGÜLTIG"
        print(f"File {p.name}: {status} ({res.error_count()} Fehler, {res.warning_count()} Warnungen)")
        for err in res.get_all():
            msg = str(err.message).encode("ascii", "replace").decode("ascii")
            print(f"   -> [{err.severity.upper()}] [{err.code}]: {msg}")

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    target_dir = project_root / "test_esol_dateien"
    create_sample_files(target_dir)
