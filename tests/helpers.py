from validation_context import ValidationContext


def assert_error_code(errors, code: str, message: str = ""):
    """Prüft, ob ein Fehler mit dem angegebenen Fehlercode enthalten ist."""
    found = any(e.code == code for e in errors)
    assert found, message or f"Expected error code {code}"

def assert_no_error_code(errors, code: str, message: str = ""):
    """Prüft, dass kein Fehler mit dem angegebenen Code auftritt."""
    found = any(e.code == code for e in errors)
    assert not found, message or f"Expected no error code {code}"

def assert_warning_code(errors, code: str, message: str = ""):
    """Prüft, ob eine Warnung mit dem angegebenen Code vorliegt."""
    found = any(e.code == code and getattr(e, 'severity', None) == 'warning' for e in errors)
    assert found, message or f"Expected warning code {code}"

def make_context(content: str | bytes, tokenizer) -> ValidationContext:
    """Baut den ValidationContext aus einem ESOL-String auf."""
    ctx = ValidationContext()
    ctx.set_raw_content(content)
    
    raw_segments = tokenizer.tokenize_segments(content)
    ctx.set_raw_segments(raw_segments)
    
    parsed = [tokenizer.parse_segment(raw) for raw in raw_segments]
    ctx.set_parsed_segments(parsed)
    
    messages = []
    current_start = None
    current_ref_nr = None
    current_type = None

    for index, seg in enumerate(parsed):
        if seg.get('tag') == 'UNH':
            current_start = index
            current_ref_nr = seg['fields'][0] if seg.get('fields') else ''
            msg_id = seg['fields'][1] if len(seg.get('fields', [])) > 1 else ''
            current_type = msg_id[0] if isinstance(msg_id, list) else (msg_id.split(':')[0] if msg_id else '')
        
        if seg.get('tag') == 'UNT' and current_start is not None:
            msg_segments = parsed[current_start : index + 1]
            messages.append({
                'start': current_start,
                'end': index,
                'type': current_type or '',
                'refNr': current_ref_nr or '',
                'segments': msg_segments
            })
            current_start = None
            current_ref_nr = None
            current_type = None

    ctx.set_messages(messages)
    return ctx