from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any

from backend.app.evaluation.benchmark import EvaluationCase
from backend.app.llm.arbitrator import ControlledTariffArbitrator
from backend.app.models.domain import EquipmentItem


class ArbitrationBenchmarkRunner:
    """Cost-aware benchmark for cloud arbitration.

    Retrieval always runs locally. Paid/free-endpoint calls are used only when the
    expected code is already present in the closed top-5 candidate set AND top-1 is
    wrong. This measures the exact value of the arbitrator without spending calls on
    cases that no arbitrator is structurally allowed to repair.
    """

    def __init__(self, engine, arbitrator: ControlledTariffArbitrator, metrics, repo):
        self.engine = engine
        self.arbitrator = arbitrator
        self.metrics = metrics
        self.repo = repo

    def run(
        self,
        cases: list[EvaluationCase],
        *,
        provider: str,
        max_calls: int = 10,
        persist: bool = True,
    ) -> dict[str, Any]:
        total = len(cases)
        if total == 0:
            raise ValueError("Aucun cas d'évaluation disponible.")

        covered = 0
        baseline_correct = 0
        eligible = 0
        calls = 0
        correct_arbitrations = 0
        abstentions = 0
        invalid = 0
        api_errors = 0
        cache_hits = 0
        prompt_tokens = 0
        completion_tokens = 0
        latencies: list[float] = []
        tested_details: list[dict[str, Any]] = []

        for case in cases:
            candidates = self.engine.search(case.query, top_k=5, include_history=False)
            codes = [c.code_sh for c in candidates]
            if case.expected_code in codes:
                covered += 1
            if codes and codes[0] == case.expected_code:
                baseline_correct += 1
                continue
            if case.expected_code not in codes:
                continue
            eligible += 1
            if calls >= max_calls:
                continue

            item = EquipmentItem(
                source_document="benchmark",
                designation_source=case.query,
                designation_normalisee=case.query,
                extraction_confidence=1.0,
            )
            outcome = self.arbitrator.arbitrate(
                item,
                candidates,
                requested_provider=provider,
                use_cache=True,
            )
            calls += 0 if outcome.cache_hit else 1
            cache_hits += int(outcome.cache_hit)
            if outcome.latency_ms is not None:
                latencies.append(float(outcome.latency_ms))
            if not outcome.cache_hit:
                prompt_tokens += int(outcome.prompt_tokens or 0)
                completion_tokens += int(outcome.completion_tokens or 0)
            if outcome.status == "SELECT" and outcome.selected_code == case.expected_code:
                correct_arbitrations += 1
            elif outcome.status == "ABSTENTION":
                abstentions += 1
            elif outcome.guardrail_rejected or outcome.status in {"REJETE_GARDEFOU", "REPONSE_INVALIDE"}:
                invalid += 1
            elif outcome.status == "ERREUR_PROVIDER":
                api_errors += 1

            tested_details.append({
                "dataset": case.dataset,
                "expected_code": case.expected_code,
                "top1_before": codes[0] if codes else None,
                "selected_code": outcome.selected_code,
                "status": outcome.status,
                "confidence": outcome.confidence,
                "cache_hit": outcome.cache_hit,
            })

        # Every successful arbitration repairs one baseline error. Cases not called due
        # to the budget conservatively remain at baseline in the end-to-end measure.
        end_to_end_correct = baseline_correct + correct_arbitrations
        provider_status = {x["provider"]: x for x in self.arbitrator.provider_statuses()}.get(provider.upper(), {})
        tested_count = len(tested_details)
        result = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider.upper(),
            "model_name": provider_status.get("model"),
            "dataset_name": "+".join(sorted({c.dataset for c in cases})),
            "cases": total,
            "retrieval_coverage": covered / total,
            "baseline_top1_accuracy": baseline_correct / total,
            "arbitration_accuracy_on_covered": (correct_arbitrations / tested_count) if tested_count else 0.0,
            "end_to_end_accuracy": end_to_end_correct / total,
            "abstention_rate": (abstentions / tested_count) if tested_count else 0.0,
            "invalid_output_rate": (invalid / tested_count) if tested_count else 0.0,
            "api_error_rate": (api_errors / tested_count) if tested_count else 0.0,
            "avg_latency_ms": statistics.mean(latencies) if latencies else None,
            "calls": calls,
            "prompt_tokens": prompt_tokens or None,
            "completion_tokens": completion_tokens or None,
            "cache_hits": cache_hits,
            "camcis_sha256": self.repo.sha256,
            "details": {
                "eligible_ambiguous_cases": eligible,
                "tested_cases": tested_count,
                "corrected_cases": correct_arbitrations,
                "budget_max_calls": max_calls,
                "guardrail": "selected_code must be one of the closed top-5 CAMCIS candidates",
                "history_memory": False,
                "tested": tested_details,
            },
        }
        if persist:
            self.metrics.record_arbitration_benchmark(result)
        return result
