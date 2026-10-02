from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.models.domain import EquipmentItem


@dataclass
class ParsedDocument:
    """Canonical result returned by every ingestion adapter.

    The customs engine only receives EquipmentItem objects and therefore remains
    independent from the client's original file format.
    """

    items: list[EquipmentItem]
    source_type: str
    extraction_method: str
    warnings: list[str] = field(default_factory=list)
    source_sheet: str | None = None
    header_row: int | None = None
    header_score: float | None = None
    column_mapping: dict[str, str] = field(default_factory=dict)
    pages_total: int | None = None
    pages_ocr: int = 0
    raw_text_chars: int = 0
    document_kind: str | None = None
    document_label: str | None = None
    document_confidence: float | None = None
    equipment_likelihood: float | None = None
    ocr_confidence: float | None = None
    raw_text_preview: str | None = None
    captured_lines: list[dict] = field(default_factory=list)
    captured_records: list[dict] = field(default_factory=list)
    capture_completeness: float | None = None

    def as_metadata(self) -> dict:
        return {
            "source_type": self.source_type,
            "extraction_method": self.extraction_method,
            "source_sheet": self.source_sheet,
            "header_row_zero_based": self.header_row,
            "header_score": self.header_score,
            "column_mapping": self.column_mapping,
            "warnings": self.warnings,
            "pages_total": self.pages_total,
            "pages_ocr": self.pages_ocr,
            "raw_text_chars": self.raw_text_chars,
            "items_count": len(self.items),
            "document_kind": self.document_kind,
            "document_label": self.document_label,
            "document_confidence": self.document_confidence,
            "equipment_likelihood": self.equipment_likelihood,
            "ocr_confidence": self.ocr_confidence,
            "raw_text_preview": self.raw_text_preview,
            "captured_lines": self.captured_lines,
            "captured_records": self.captured_records,
            "capture_completeness": self.capture_completeness,
        }
