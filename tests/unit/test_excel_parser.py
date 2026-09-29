from pathlib import Path

from backend.app.ingestion.tabular_parser import TabularEquipmentParser

FIX = Path(__file__).resolve().parents[1] / "evaluation" / "fixtures"


def test_netic_header_detection_and_designation():
    parsed = TabularEquipmentParser().parse_path(FIX / "NETIC_reference.xlsx")
    assert parsed.header_row == 2
    assert parsed.column_mapping["designation"].lower().startswith("designation")
    assert parsed.items[0].designation_source == "Solar Cell"
    assert parsed.items[0].code_sh_source == "85414200000"


def test_francy_header_detection():
    parsed = TabularEquipmentParser().parse_path(FIX / "FRANCY_GARDEN_reference.xlsx")
    assert parsed.header_row == 2
    assert parsed.items[0].designation_source.startswith("Plateau tournant")
    assert parsed.items[0].code_sh_source == "70200000900"
