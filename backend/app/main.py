from __future__ import annotations

import statistics
import time
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

from backend.app.core.bootstrap import RuntimeServices, build_runtime_services
from backend.app.core.config import settings
from backend.app.evaluation.benchmark import BenchmarkRunner, load_evaluation_cases
from backend.app.evaluation.arbitration_benchmark import ArbitrationBenchmarkRunner
from backend.app.currency.exchange import ExchangeRateService
from backend.app.exports.audit_reports import build_audit_docx, build_audit_pdf
from backend.app.exports.professional_excel import build_professional_excel
from backend.app.ingestion.document_parser import UniversalEquipmentParser
from backend.app.ingestion.errors import IngestionError, ingestion_error_payload
from backend.app.metrics.performance import PerformanceProbe
from backend.app.quality.normalization import apply_professional_normalization
from backend.app.sector.coherence import assess_sector, infer_project_profile
from backend.app.models.domain import TariffAssessment


def _p95_ms(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return round(float(ordered[idx]), 3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with PerformanceProbe() as probe:
        services = build_runtime_services(settings)
        app.state.services = services
        snap = probe.finish({
            "camcis_records": len(services.repo.load()),
            "camcis_sha256": services.repo.sha256,
            "search_mode": services.engine.mode,
            "semantic_status": services.index_sync.status,
            "semantic_collection": services.index_sync.collection_name,
            "validated_cases": services.engine.history.count if services.engine.history else 0,
        })
    services.metrics.record_runtime("APP_STARTUP", snap)
    try:
        yield
    finally:
        services.engine.close()
        services.metrics.record_runtime("APP_SHUTDOWN", details={"search_mode": services.engine.mode})


app = FastAPI(
    title="CGS - Harmonisation Douanière API",
    version="2.6.0-sprint6-controlled-ai",
    description=(
        "Plateforme propriétaire CREATIV GROUP d'harmonisation douanière avec ingestion universelle, "
        "normalisation XAF automatique, contrôle sectoriel prudent, arbitrage IA fermé sur candidats du référentiel, exports professionnels et boucle de revue."
    ),
    lifespan=lifespan,
)


def svc(request: Request) -> RuntimeServices:
    services = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="CGS - Harmonisation Douanière n'est pas encore initialisé.")
    return services


@app.get("/health")
def health(request: Request):
    s = svc(request)
    semantic_expected = settings.enable_semantic
    semantic_ready = s.index_sync.ready and bool(s.engine.vector and s.engine.vector.available)
    status = "ok" if (not semantic_expected or semantic_ready) else "degraded"
    return {
        "status": status,
        "version": app.version,
        "camcis": s.repo.stats(),
        "search_mode": s.engine.mode,
        "semantic_index": s.index_sync.as_dict(),
        "semantic_reason": getattr(s.engine.vector, "reason_unavailable", None) if s.engine.vector else s.index_sync.reason,
        "validated_memory": s.engine.history.stats() if s.engine.history else {"cases": 0},
        "metrics": s.metrics.summary(),
        "ingestion": UniversalEquipmentParser().capabilities(),
        "llm_arbitration": {"enabled": settings.enable_llm_arbitration, "providers": s.arbitrator.provider_statuses(), "max_calls_per_dossier": settings.llm_max_calls_per_dossier},
        "docker_required": False,
    }


@app.get("/api/v2/reference/stats")
def reference_stats(request: Request):
    s = svc(request)
    return {
        "camcis": s.repo.stats(),
        "validated_memory": s.engine.history.stats() if s.engine.history else {"cases": 0},
        "semantic_index": s.index_sync.as_dict(),
    }


@app.get("/api/v2/reference/state")
def reference_state(request: Request):
    return svc(request).reference_state


@app.get("/api/v2/metrics/summary")
def metrics_summary(request: Request):
    return svc(request).metrics.summary()


@app.get("/api/v2/metrics/runtime")
def metrics_runtime(request: Request, limit: int = Query(50, ge=1, le=500)):
    return {"events": svc(request).metrics.recent_runtime(limit)}


@app.get("/api/v2/evaluation/results")
def evaluation_results(request: Request, limit: int = Query(100, ge=1, le=500)):
    return {"results": svc(request).metrics.benchmark_results(limit)}


@app.get("/api/v2/evaluation/llm-providers")
def evaluation_llm_providers(request: Request):
    s = svc(request)
    return {
        "enabled": settings.enable_llm_arbitration,
        "providers": s.arbitrator.provider_statuses(),
        "guardrail": "L'IA choisit uniquement parmi les candidats du référentiel douanier fournis ou s'abstient.",
        "max_calls_per_dossier": settings.llm_max_calls_per_dossier,
    }


@app.get("/api/v2/evaluation/arbitration-results")
def evaluation_arbitration_results(request: Request, limit: int = Query(100, ge=1, le=500)):
    return {"results": svc(request).metrics.arbitration_benchmark_results(limit)}


@app.post("/api/v2/evaluation/run-lexical-baseline")
def evaluation_run_lexical_baseline(request: Request, max_cases: int = Query(200, ge=10, le=2000)):
    s = svc(request)
    fixture_dir = settings.project_root / "tests" / "evaluation" / "fixtures"
    paths = [
        fixture_dir / "NETIC_reference.xlsx",
        fixture_dir / "FRANCY_GARDEN_reference.xlsx",
        fixture_dir / "SOCAAL_reference.xlsx",
    ]
    paths = [p for p in paths if p.exists()]
    if not paths:
        raise HTTPException(status_code=404, detail="Aucun jeu d'évaluation disponible.")
    try:
        with PerformanceProbe() as probe:
            cases = load_evaluation_cases(paths, max_cases=max_cases)
            runner = BenchmarkRunner(s.repo, s.metrics, settings.benchmark_cache_path)
            result = runner.run_lexical(cases, persist=True)
            snap = probe.finish({"cases": len(cases), "engine_type": "LEXICAL"})
        s.metrics.record_runtime("BENCHMARK_LEXICAL", snap)
        return result
    except Exception as exc:
        s.metrics.record_runtime("BENCHMARK_ERROR", details={"engine_type": "LEXICAL", "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))




@app.post("/api/v2/evaluation/run-arbitrator")
def evaluation_run_arbitrator(
    request: Request,
    provider: str = Query(...),
    max_cases: int = Query(100, ge=10, le=500),
    max_calls: int = Query(10, ge=1, le=50),
):
    provider = provider.strip().upper()
    s = svc(request)
    statuses = {x["provider"]: x for x in s.arbitrator.provider_statuses()}
    if provider not in statuses:
        raise HTTPException(status_code=400, detail="Fournisseur IA non reconnu.")
    if not statuses[provider].get("configured"):
        raise HTTPException(status_code=400, detail=f"{provider} n'est pas configuré sur cette machine.")
    fixture_dir = settings.project_root / "tests" / "evaluation" / "fixtures"
    paths = [fixture_dir / "NETIC_reference.xlsx", fixture_dir / "FRANCY_GARDEN_reference.xlsx", fixture_dir / "SOCAAL_reference.xlsx"]
    paths = [p for p in paths if p.exists()]
    if not paths:
        raise HTTPException(status_code=404, detail="Aucun jeu d'évaluation disponible.")
    try:
        cases = load_evaluation_cases(paths, max_cases=max_cases)
        runner = ArbitrationBenchmarkRunner(s.engine, s.arbitrator, s.metrics, s.repo)
        result = runner.run(cases, provider=provider, max_calls=max_calls, persist=True)
        s.metrics.record_runtime("BENCHMARK_ARBITRATION", details={
            "provider": provider, "cases": len(cases), "calls": result.get("calls"),
            "prompt_tokens": result.get("prompt_tokens"), "completion_tokens": result.get("completion_tokens"),
        })
        return result
    except Exception as exc:
        s.metrics.record_runtime("BENCHMARK_ARBITRATION_ERROR", details={"provider": provider, "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v2/fx/rate")
def fx_rate(currency: str = Query(..., min_length=3, max_length=5), manual_rate: float = Query(0.0, ge=0.0)):
    result = ExchangeRateService(settings.fx_cache_path).get_xaf_rate(currency, manual_rate or None)
    if result.xaf_per_unit is None:
        raise HTTPException(status_code=503, detail=f"Taux {currency}/XAF indisponible: {result.error or 'source indisponible'}")
    return result.as_dict()


@app.post("/api/v2/evaluation/run-local-model")
def evaluation_run_local_model(
    request: Request,
    model_name: str = Query(...),
    max_cases: int = Query(200, ge=10, le=1000),
):
    if model_name not in settings.benchmark_models:
        raise HTTPException(status_code=400, detail="Modèle non autorisé dans le laboratoire CGS.")
    s = svc(request)
    fixture_dir = settings.project_root / "tests" / "evaluation" / "fixtures"
    paths = [fixture_dir / "NETIC_reference.xlsx", fixture_dir / "FRANCY_GARDEN_reference.xlsx", fixture_dir / "SOCAAL_reference.xlsx"]
    paths = [p for p in paths if p.exists()]
    if not paths:
        raise HTTPException(status_code=404, detail="Aucun jeu d'évaluation disponible.")
    try:
        cases = load_evaluation_cases(paths, max_cases=max_cases)
        runner = BenchmarkRunner(s.repo, s.metrics, settings.benchmark_cache_path)
        return {"results": runner.run_semantic_model(cases, model_name, persist=True)}
    except Exception as exc:
        s.metrics.record_runtime("BENCHMARK_ERROR", details={"model_name": model_name, "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v2/export/excel")
def export_professional_excel(body: dict = Body(...)):
    payload = body.get("payload") or {}
    reference_dossier = str(body.get("reference_dossier") or payload.get("reference_prospect") or "DOSSIER-CGS")
    secteur = str(body.get("secteur") or "")
    description_projet = str(body.get("description_projet") or "")
    if not payload.get("resultats"):
        raise HTTPException(status_code=400, detail="Aucun résultat à exporter.")
    try:
        content = build_professional_excel(
            payload,
            reference_dossier=reference_dossier,
            secteur=secteur,
            description_projet=description_projet,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export Excel impossible: {exc}")
    source_name = str(payload.get("source_filename") or reference_dossier or "dossier")
    stem = Path(source_name).stem
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem).strip("_") or "DOSSIER"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{safe}_harmonise_CGS.xlsx"'},
    )


@app.post("/api/v2/export/audit/docx")
def export_audit_docx(body: dict = Body(...)):
    payload = body.get("payload") or {}
    if not payload.get("resultats"):
        raise HTTPException(status_code=400, detail="Aucun résultat à exporter.")
    reference_dossier = str(body.get("reference_dossier") or payload.get("reference_prospect") or "DOSSIER-CGS")
    secteur = str(body.get("secteur") or "")
    description_projet = str(body.get("description_projet") or "")
    content = build_audit_docx(payload, reference_dossier=reference_dossier, secteur=secteur, description_projet=description_projet)
    stem = Path(str(payload.get("source_filename") or reference_dossier)).stem
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem).strip("_") or "DOSSIER"
    return Response(content=content, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f'attachment; filename="{safe}_rapport_audit_CGS.docx"'})


@app.post("/api/v2/export/audit/pdf")
def export_audit_pdf(body: dict = Body(...)):
    payload = body.get("payload") or {}
    if not payload.get("resultats"):
        raise HTTPException(status_code=400, detail="Aucun résultat à exporter.")
    reference_dossier = str(body.get("reference_dossier") or payload.get("reference_prospect") or "DOSSIER-CGS")
    secteur = str(body.get("secteur") or "")
    description_projet = str(body.get("description_projet") or "")
    content = build_audit_pdf(payload, reference_dossier=reference_dossier, secteur=secteur, description_projet=description_projet)
    stem = Path(str(payload.get("source_filename") or reference_dossier)).stem
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem).strip("_") or "DOSSIER"
    return Response(content=content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe}_rapport_audit_CGS.pdf"'})


@app.post("/api/v2/feedback/import-validated")
async def import_validated_feedback(
    request: Request,
    file: UploadFile = File(...),
    expert_confirmation: bool = Form(False),
):
    if not expert_confirmation:
        raise HTTPException(status_code=400, detail="Confirmation explicite de validation expert requise.")
    s = svc(request)
    if s.engine.history is None:
        raise HTTPException(status_code=503, detail="Mémoire validée indisponible.")
    data = await file.read()
    parsed = UniversalEquipmentParser(enable_ocr=False).parse_bytes(data, file.filename or "harmonise.xlsx")
    valid_items = [i for i in parsed.items if i.code_sh_source and s.repo.get(i.code_sh_source) is not None]
    invalid = [i.designation_source for i in parsed.items if i.code_sh_source and s.repo.get(i.code_sh_source) is None]
    if not valid_items:
        raise HTTPException(status_code=400, detail="Aucune position tarifaire validable trouvée dans le fichier.")
    added = s.engine.history.append_validated_items(valid_items, file.filename or "harmonise.xlsx")
    s.engine.reload_history()
    return {
        "status": "ok",
        "added_cases": added,
        "valid_rows": len(valid_items),
        "invalid_codes": invalid[:20],
        "memory_cases": s.engine.history.count if s.engine.history else 0,
    }


@app.get("/api/v2/ingestion/capabilities")
def ingestion_capabilities():
    return UniversalEquipmentParser().capabilities()


@app.post("/api/v2/preview-bordereau")
async def preview_bordereau(request: Request, file: UploadFile = File(...)):
    s = svc(request)
    data = await file.read()
    try:
        with PerformanceProbe() as probe:
            parsed = UniversalEquipmentParser().parse_bytes(data, file.filename or "upload")
            snap = probe.finish({
                "filename": file.filename,
                "items_count": len(parsed.items),
                "header_score": parsed.header_score,
                "source_type": parsed.source_type,
                "extraction_method": parsed.extraction_method,
                "pages_ocr": parsed.pages_ocr,
            })
        s.metrics.record_runtime("PREVIEW_BORDEREAU", snap)
    except Exception as exc:
        s.metrics.record_runtime("PREVIEW_BORDEREAU_ERROR", details={"filename": file.filename, "error": str(exc)})
        detail = ingestion_error_payload(exc)
        raise HTTPException(status_code=422 if isinstance(exc, IngestionError) else 400, detail=detail)
    response = parsed.as_metadata()
    response["preview"] = [i.model_dump(mode="json", exclude={"raw_fields"}) for i in parsed.items[:20]]
    return response


@app.post("/api/v2/process-bordereau")
async def process_bordereau(
    request: Request,
    file: UploadFile = File(...),
    secteur: str = Form(""),
    reference_prospect: str = Form(...),
    description_projet: str = Form(""),
    top_k: int = Form(5),
    taux_change_xaf: float = Form(0.0),
    assistance_ia: bool = Form(True),
    llm_provider: str = Form("AUTO"),
):
    if top_k < 1 or top_k > 10:
        raise HTTPException(status_code=400, detail="top_k doit être compris entre 1 et 10.")

    s = svc(request)
    data = await file.read()
    total_started = time.perf_counter()
    rss_probe = PerformanceProbe()
    rss_probe.__enter__()
    try:
        ingestion_started = time.perf_counter()
        parsed = UniversalEquipmentParser().parse_bytes(data, file.filename or "upload")
        ingestion_ms = (time.perf_counter() - ingestion_started) * 1000.0

        # Normalize professional presentation and finances before any decision.
        # Automatic FX is the default. A positive dossier rate remains an explicit
        # override when the operator has an official customs/bank rate.
        fx_service = ExchangeRateService(settings.fx_cache_path)
        manual_rate = taux_change_xaf if taux_change_xaf and taux_change_xaf > 0 else None
        foreign_currencies = sorted({
            fx_service.normalize_currency(i.devise)
            for i in parsed.items
            if fx_service.normalize_currency(i.devise) not in {None, "XAF"}
        })
        fx_used: dict[str, dict] = {}
        for currency in foreign_currencies:
            # A single manual override is only safe when the file has one foreign currency.
            override = manual_rate if len(foreign_currencies) == 1 else None
            fx_used[currency] = fx_service.get_xaf_rate(currency, override).as_dict()

        for item in parsed.items:
            currency = fx_service.normalize_currency(item.devise)
            rate_for_item = None
            if currency in {None, "XAF"}:
                rate_for_item = 1.0
            elif currency in fx_used:
                rate_for_item = fx_used[currency].get("xaf_per_unit")
            apply_professional_normalization(item, exchange_rate_xaf=rate_for_item)

        project_profile = infer_project_profile(parsed.items, sector=secteur, description=description_projet)

        assessments: list[TariffAssessment] = []
        search_times_ms: list[float] = []
        llm_api_calls = 0
        llm_cache_hits = 0
        llm_selected = 0
        llm_abstained = 0
        llm_prompt_tokens = 0
        llm_completion_tokens = 0
        provider_statuses = s.arbitrator.provider_statuses()
        configured_by_name = {p.get("provider"): bool(p.get("configured")) for p in provider_statuses}
        requested_upper = (llm_provider or "AUTO").upper()
        llm_available = assistance_ia and (
            any(configured_by_name.values()) if requested_upper == "AUTO" else configured_by_name.get(requested_upper, False)
        )
        for item in parsed.items:
            query = item.designation_source
            if item.specifications:
                query = f"{query}. {item.specifications}"
            search_started = time.perf_counter()
            candidates = s.engine.search(query, top_k=top_k)
            search_times_ms.append((time.perf_counter() - search_started) * 1000.0)
            code, label, score, status, reason = s.engine.decide_for_item(item, candidates)
            arbitration = None
            if llm_available and s.arbitrator.should_arbitrate(status, candidates):
                if llm_api_calls < settings.llm_max_calls_per_dossier:
                    arbitration = s.arbitrator.arbitrate(
                        item, candidates, sector=secteur, project_description=description_projet,
                        requested_provider=llm_provider, use_cache=True,
                    )
                    if arbitration.cache_hit:
                        llm_cache_hits += 1
                    elif arbitration.provider:
                        llm_api_calls += 1
                        llm_prompt_tokens += int(arbitration.prompt_tokens or 0)
                        llm_completion_tokens += int(arbitration.completion_tokens or 0)
                    if arbitration.status == "SELECT" and arbitration.selected_code:
                        chosen = next((c for c in candidates if c.code_sh == arbitration.selected_code), None)
                        if chosen is not None:
                            code = chosen.code_sh
                            label = chosen.libelle_douanier
                            score = chosen.combined_score
                            status = "PROPOSITION_ARBITREE"
                            reason = (
                                "Arbitrage IA contrôlé sur une liste fermée de candidats du référentiel douanier. "
                                "Aucun code extérieur au référentiel candidat n'est accepté."
                            )
                            llm_selected += 1
                    elif arbitration.status == "ABSTENTION":
                        llm_abstained += 1
                else:
                    from backend.app.llm.arbitrator import ArbitrationOutcome
                    arbitration = ArbitrationOutcome(
                        status="BUDGET_ATTEINT",
                        reason=f"Budget de {settings.llm_max_calls_per_dossier} appels IA atteint; classement local conservé.",
                    )
            sector_result = assess_sector(item, project_profile)
            assessment = TariffAssessment(
                item=item,
                candidats=candidates,
                code_sh_propose=code,
                libelle_propose=label,
                score_retrieval=score,
                statut_tarifaire=status,
                motif_decision=reason,
                mode_recherche=s.engine.mode,
                arbitrage_ia_statut=arbitration.status if arbitration else ("NON_DISPONIBLE" if assistance_ia and not llm_available else "NON_REQUIS"),
                arbitrage_ia_provider=arbitration.provider if arbitration else None,
                arbitrage_ia_model=arbitration.model if arbitration else None,
                arbitrage_ia_confidence=arbitration.confidence if arbitration else None,
                arbitrage_ia_commentaire=arbitration.reason if arbitration else None,
                arbitrage_ia_latency_ms=arbitration.latency_ms if arbitration else None,
                arbitrage_ia_cache_hit=arbitration.cache_hit if arbitration else False,
                pertinence_sectorielle=sector_result.status,
                niveau_risque=sector_result.risk,
                commentaire_sectoriel=sector_result.comment,
                score_sectoriel=sector_result.score,
            )
            s.audit.append_assessment(reference_prospect, assessment, s.repo.sha256)
            assessments.append(assessment)

        statuses = Counter(a.statut_tarifaire for a in assessments)
        total_ms = (time.perf_counter() - total_started) * 1000.0
        perf = rss_probe.finish({
            "reference_prospect": reference_prospect,
            "filename": file.filename,
            "items_count": len(assessments),
            "ingestion_ms": round(ingestion_ms, 3),
            "source_type": parsed.source_type,
            "extraction_method": parsed.extraction_method,
            "pages_total": parsed.pages_total,
            "pages_ocr": parsed.pages_ocr,
            "avg_search_ms": round(statistics.mean(search_times_ms), 3) if search_times_ms else None,
            "p95_search_ms": _p95_ms(search_times_ms),
            "search_mode": s.engine.mode,
            "statuses": dict(statuses),
            "fx_currencies": fx_used,
            "llm_arbitration": {
                "enabled_for_dossier": bool(llm_available), "requested_provider": llm_provider,
                "api_calls": llm_api_calls, "cache_hits": llm_cache_hits, "selected": llm_selected, "abstained": llm_abstained,
                "prompt_tokens": llm_prompt_tokens, "completion_tokens": llm_completion_tokens,
            },
            "total_ms_check": round(total_ms, 3),
        })
        s.metrics.record_runtime("PROCESS_BORDEREAU", perf)
    except Exception as exc:
        try:
            perf = rss_probe.finish({"reference_prospect": reference_prospect, "filename": file.filename, "error": str(exc)})
            s.metrics.record_runtime("PROCESS_BORDEREAU_ERROR", perf)
        except Exception:
            pass
        detail = ingestion_error_payload(exc)
        raise HTTPException(status_code=422 if isinstance(exc, IngestionError) else 400, detail=detail)

    return {
        "reference_prospect": reference_prospect,
        "source_filename": file.filename or "upload",
        "project_profile": {
            "key": project_profile.key,
            "label": project_profile.label,
            "confidence": project_profile.confidence,
            "source": project_profile.source,
        },
        "camcis": s.repo.stats(),
        "exchange_rates": fx_used,
        "llm_arbitration": {
            "enabled": bool(llm_available), "requested_provider": llm_provider,
            "api_calls": llm_api_calls, "cache_hits": llm_cache_hits, "selected": llm_selected, "abstained": llm_abstained,
            "prompt_tokens": llm_prompt_tokens, "completion_tokens": llm_completion_tokens,
            "providers": provider_statuses,
        },
        "ingestion": parsed.as_metadata(),
        "performance": {
            "total_ms": perf.duration_ms,
            "rss_delta_mb": perf.rss_delta_mb,
            "ingestion_ms": round(ingestion_ms, 3),
            "source_type": parsed.source_type,
            "extraction_method": parsed.extraction_method,
            "pages_total": parsed.pages_total,
            "pages_ocr": parsed.pages_ocr,
            "avg_search_ms": round(statistics.mean(search_times_ms), 3) if search_times_ms else None,
            "p95_search_ms": _p95_ms(search_times_ms),
        },
        "search_mode": s.engine.mode,
        "semantic_index_status": s.index_sync.status,
        "resultats": [a.model_dump(mode="json") for a in assessments],
    }
