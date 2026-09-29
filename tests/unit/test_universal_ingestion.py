from __future__ import annotations

import io

import fitz
from docx import Document

from backend.app.ingestion.document_parser import (
    UniversalEquipmentParser,
    parse_ocr_commercial_lines,
)


def test_docx_table_ingestion():
    doc = Document()
    table = doc.add_table(rows=3, cols=6)
    headers = ["Description", "Quantity", "Unit", "Unit Price USD", "Amount USD", "Origin"]
    for i, value in enumerate(headers):
        table.rows[0].cells[i].text = value
    values = [
        ["Industrial pump", "2", "pcs", "150", "300", "CHINA"],
        ["Air compressor", "1", "set", "800", "800", "CHINA"],
    ]
    for r, row in enumerate(values, start=1):
        for c, value in enumerate(row):
            table.rows[r].cells[c].text = value
    bio = io.BytesIO()
    doc.save(bio)

    parsed = UniversalEquipmentParser().parse_bytes(bio.getvalue(), "supplier.docx")
    assert parsed.source_type == "WORD"
    assert len(parsed.items) == 2
    assert parsed.items[0].designation_source == "Industrial pump"
    assert parsed.items[0].quantite == 2
    assert parsed.items[0].prix_total == 300


def test_native_pdf_text_ingestion():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 80), "PROFORMA INVOICE", fontsize=14)
    page.insert_text((50, 120), "1 Industrial pump 2 pcs 150 300", fontsize=10)
    page.insert_text((50, 140), "2 Air compressor 1 set 800 800", fontsize=10)
    data = doc.tobytes()
    doc.close()

    parsed = UniversalEquipmentParser().parse_bytes(data, "supplier.pdf")
    assert parsed.source_type == "PDF"
    assert parsed.pages_ocr == 0
    assert [x.designation_source for x in parsed.items] == ["Industrial pump", "Air compressor"]


def test_ocr_line_fallback_does_not_invent_quantity():
    text = "PROFORMA INVOICE\nDescription Quantity Unit Price USD Total Price USD\n4*4 Egg tray machine 38000 38000\nFOB TOTAL USD 38000"
    items = parse_ocr_commercial_lines(text, "scan.png")
    assert len(items) == 1
    assert items[0].designation_source == "4*4 Egg tray machine"
    assert items[0].quantite is None
    assert items[0].prix_unitaire == 38000
    assert items[0].prix_total == 38000


def test_capabilities_are_declared_without_forcing_ocr():
    caps = UniversalEquipmentParser().capabilities()
    assert ".xlsx" in caps["extensions"]
    assert ".pdf" in caps["extensions"]
    assert ".docx" in caps["extensions"]
    assert ".png" in caps["extensions"]
    assert caps["strategy"] == "native-first-ocr-on-demand"


def test_numbered_equipment_schedule_without_prices():
    from backend.app.ingestion.document_parser import _parse_numbered_equipment_table

    rows = [
        ["1", "", "Convoyeur d'alimentation", "Préparation matière", "Transfert vers le tri", "A importer"],
        ["2", "", "Pompe de process", "Utilités", "Circulation des fluides", "A importer"],
    ]
    items = _parse_numbered_equipment_table(rows, "schedule.pdf", 1)
    assert len(items) == 2
    assert items[0].designation_source == "Convoyeur d'alimentation"
    assert items[0].specifications == "Transfert vers le tri"
    assert items[0].prix_total is None


def test_customs_table_is_not_misread_as_price_table():
    from backend.app.ingestion.document_parser import _parse_simple_price_table

    rows = [
        ["N° D'ORDRE", "DESIGNATION", "CODE SH", "LIBELLE DOUANIER", "QTE", "UNITE", "PRIX TOTAL (XAF)", "ORIGINE"],
        ["1", "Convoyeur", "84283900000", "Autres convoyeurs", "1", "set", "11300000", "CHINE"],
    ]
    assert _parse_simple_price_table(rows, "customs.pdf", 1) == []
