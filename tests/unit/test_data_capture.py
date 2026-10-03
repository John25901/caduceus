from backend.app.ingestion.data_capture import capture_label_value_records, capture_text_lines


def test_capture_lines_preserves_ocr_text_without_schema_assumption():
    text = """
    RAISON SOCIALE : STE COMPTOIR AGRICOLE
    ADRESSE : RUE JABIR BEN HAYANE
    TEL : 0524434109
    """
    rows = capture_text_lines(text)
    assert len(rows) == 3
    assert rows[0]["text"].startswith("RAISON SOCIALE")


def test_capture_label_value_records_groups_repeated_blocks():
    text = """
    RAISON SOCIALE : STE COMPTOIR AGRICOLE
    ADRESSE : RUE JABIR BEN HAYANE
    TEL : 0524434109
    RAISON SOCIALE : STE AGRODEP
    ADRESSE : MARRAKECH
    TEL : 0524420252
    """
    records = capture_label_value_records(text)
    assert len(records) == 2
    assert records[0]["RAISON SOCIALE"] == "STE COMPTOIR AGRICOLE"
    assert records[1]["RAISON SOCIALE"] == "STE AGRODEP"
