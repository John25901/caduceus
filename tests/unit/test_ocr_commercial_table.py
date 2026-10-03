from backend.app.ingestion.document_parser import (
    _estimate_commercial_row_count,
    _parse_ocr_commercial_triplet,
    parse_ocr_commercial_lines,
)


OCR_TABLE_TEXT = """
TABLEAU 3 : PETITS MATERIELS
Designation Quantité Prix unitaire Montant
Grande poubelle 3 28 000 84 000
Bac pour fruit 6 6 500 39 000
Bac pour jus de fruit 6 5 500 33 000
Tamis 4 500 2 000
Bassine moyen 4 2 500 10 000
Grande Bassine 2 6 000 12 000
Seau en plastique 4 2 500 10 000
Couteau 4 2 000 8 000
Gobelet 4 1 500 6 000
Louche 4 1 500 6 000
Entonnoire 4 250 1 000
Gant Latex 12 2 500 30 000
Multiprise 6 2 500 15 000
Sachet rouleaux 2 10 000 20 000
Epi 12 12 000 144 000
TOTAL 420 000
"""


def test_arithmetic_split_handles_spaced_thousands():
    assert _parse_ocr_commercial_triplet("Epi 12 12 000 144 000") == (
        "Epi", 12.0, 12000.0, 144000.0
    )
    assert _parse_ocr_commercial_triplet("Tamis 4 500 2 000") == (
        "Tamis", 4.0, 500.0, 2000.0
    )


def test_commercial_ocr_table_recovers_all_rows_and_values():
    items = parse_ocr_commercial_lines(OCR_TABLE_TEXT, "table.png")
    assert len(items) == 15

    by_name = {item.designation_source: item for item in items}
    assert by_name["Grande poubelle"].quantite == 3
    assert by_name["Grande poubelle"].prix_unitaire == 28000
    assert by_name["Grande poubelle"].prix_total == 84000

    assert by_name["Bac pour jus de fruit"].quantite == 6
    assert by_name["Bac pour jus de fruit"].prix_unitaire == 5500
    assert by_name["Bac pour jus de fruit"].prix_total == 33000

    assert by_name["Entonnoire"].prix_unitaire == 250
    assert by_name["Entonnoire"].prix_total == 1000

    assert by_name["Epi"].quantite == 12
    assert by_name["Epi"].prix_unitaire == 12000
    assert by_name["Epi"].prix_total == 144000
    assert "TOTAL" not in by_name


def test_commercial_row_denominator_matches_visible_table():
    assert _estimate_commercial_row_count(OCR_TABLE_TEXT) == 15


def test_total_row_with_inline_amount_is_never_an_item():
    items = parse_ocr_commercial_lines("TOTAL 420 000", "table.png")
    assert items == []
