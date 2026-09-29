from pathlib import Path

from backend.app.currency.exchange import ExchangeRateService, EUR_XAF_PEG
from backend.app.ingestion.document_parser import UniversalEquipmentParser


class _FakeResponse:
    def raise_for_status(self):
        return None
    def json(self):
        return {"date": "2026-09-29", "base": "USD", "quote": "EUR", "rate": 0.85}


def test_eur_xaf_fixed_parity(tmp_path):
    svc = ExchangeRateService(tmp_path / "fx.json", http_get=lambda *a, **k: None)
    r = svc.get_xaf_rate("EUR")
    assert round(r.xaf_per_unit, 3) == round(float(EUR_XAF_PEG), 3)
    assert "BEAC" in r.source


def test_usd_xaf_derived_and_cached(tmp_path):
    calls = []
    def fake_get(*args, **kwargs):
        calls.append(args[0])
        return _FakeResponse()
    svc = ExchangeRateService(tmp_path / "fx.json", http_get=fake_get)
    r1 = svc.get_xaf_rate("USD")
    r2 = svc.get_xaf_rate("USD")
    assert round(r1.xaf_per_unit, 3) == round(0.85 * float(EUR_XAF_PEG), 3)
    assert r2.cached is True
    assert len(calls) == 1


def test_manual_rate_overrides_network(tmp_path):
    svc = ExchangeRateService(tmp_path / "fx.json", http_get=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network")))
    r = svc.get_xaf_rate("USD", 565.124)
    assert r.xaf_per_unit == 565.124
    assert "manuellement" in r.source


def test_steel_quotation_keeps_all_22_commercial_lines():
    source = Path("/mnt/data/Steel Structure Workshop 90m×50m×12m Quotation-SHANDONG LANJING-20260403.pdf")
    if not source.exists():
        return
    parsed = UniversalEquipmentParser(enable_ocr=False).parse_bytes(source.read_bytes(), source.name)
    assert len(parsed.items) == 22
    names = {x.designation_source for x in parsed.items}
    assert "Turnbuckle bolts" in names
    assert "Sandwich panel container loading cost" in names
