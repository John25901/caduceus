from pathlib import Path

from backend.app.core.config import Settings
from backend.app.llm.arbitrator import ControlledTariffArbitrator
from backend.app.llm.providers import ProviderResponse
from backend.app.metrics.store import MetricsStore
from backend.app.models.domain import EquipmentItem, TariffCandidate


def _candidate(code: str, rank: int, score: float) -> TariffCandidate:
    return TariffCandidate(
        code_sh=code,
        code_sh_affiche=code,
        libelle_douanier=f"Libellé {code}",
        combined_score=score,
        rank=rank,
    )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        llm_cache_path=tmp_path / "llm_cache.db",
        nvidia_api_key="test-key",
        nvidia_model="test-model",
        enable_llm_arbitration=True,
        llm_min_confidence=0.70,
        llm_min_retrieval_score=0.35,
    )


def test_arbitrator_rejects_code_outside_closed_candidate_set(tmp_path):
    arb = ControlledTariffArbitrator(_settings(tmp_path))
    arb.providers["NVIDIA"].complete_json = lambda **kwargs: ProviderResponse(
        ok=True,
        content='{"decision":"SELECT","selected_code":"99999999999","confidence":0.99,"reason":"test"}',
    )
    item = EquipmentItem(source_document="x", designation_source="Machine", designation_normalisee="Machine")
    out = arb.arbitrate(item, [_candidate("84414000000", 1, 0.6), _candidate("84418000000", 2, 0.5)], requested_provider="NVIDIA", use_cache=False)
    assert out.status == "REJETE_GARDEFOU"
    assert out.selected_code is None
    assert out.guardrail_rejected is True


def test_arbitrator_accepts_only_existing_candidate_and_honours_confidence(tmp_path):
    arb = ControlledTariffArbitrator(_settings(tmp_path))
    arb.providers["NVIDIA"].complete_json = lambda **kwargs: ProviderResponse(
        ok=True,
        content='{"decision":"SELECT","selected_code":"84418000000","confidence":0.91,"reason":"La fonction correspond au second candidat."}',
    )
    item = EquipmentItem(source_document="x", designation_source="Machine", designation_normalisee="Machine")
    out = arb.arbitrate(item, [_candidate("84414000000", 1, 0.6), _candidate("84418000000", 2, 0.5)], requested_provider="NVIDIA", use_cache=False)
    assert out.status == "SELECT"
    assert out.selected_code == "84418000000"
    assert out.confidence == 0.91


def test_arbitrator_abstains_when_reported_confidence_is_low(tmp_path):
    arb = ControlledTariffArbitrator(_settings(tmp_path))
    arb.providers["NVIDIA"].complete_json = lambda **kwargs: ProviderResponse(
        ok=True,
        content='{"decision":"SELECT","selected_code":"84414000000","confidence":0.40,"reason":"incertain"}',
    )
    item = EquipmentItem(source_document="x", designation_source="Machine", designation_normalisee="Machine")
    out = arb.arbitrate(item, [_candidate("84414000000", 1, 0.6), _candidate("84418000000", 2, 0.5)], requested_provider="NVIDIA", use_cache=False)
    assert out.status == "ABSTENTION"
    assert out.selected_code is None


def test_should_arbitrate_only_ambiguous_retrieval(tmp_path):
    arb = ControlledTariffArbitrator(_settings(tmp_path))
    cands = [_candidate("84414000000", 1, 0.6), _candidate("84418000000", 2, 0.5)]
    assert arb.should_arbitrate("A_REVOIR", cands) is True
    assert arb.should_arbitrate("CONFIRME_SOURCE", cands) is False
    assert arb.should_arbitrate("A_REVOIR", [cands[0]]) is False


def test_metrics_store_persists_arbitration_benchmark(tmp_path):
    store = MetricsStore(tmp_path / "metrics.db")
    store.record_arbitration_benchmark({
        "created_at": "2026-09-29T00:00:00+00:00",
        "provider": "NVIDIA",
        "model_name": "test",
        "dataset_name": "fixture",
        "cases": 10,
        "retrieval_coverage": 0.8,
        "baseline_top1_accuracy": 0.5,
        "arbitration_accuracy_on_covered": 0.75,
        "end_to_end_accuracy": 0.65,
        "abstention_rate": 0.1,
        "invalid_output_rate": 0.0,
        "api_error_rate": 0.0,
        "avg_latency_ms": 100.0,
        "calls": 4,
        "prompt_tokens": 1000,
        "completion_tokens": 120,
        "cache_hits": 1,
        "camcis_sha256": "abc",
        "details": {"guardrail": "closed-set"},
    })
    rows = store.arbitration_benchmark_results(10)
    assert rows[0]["provider"] == "NVIDIA"
    assert rows[0]["invalid_output_rate"] == 0.0
    assert rows[0]["details"]["guardrail"] == "closed-set"
