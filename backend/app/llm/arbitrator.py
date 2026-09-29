from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import Settings
from backend.app.llm.cache import LLMDecisionCache
from backend.app.llm.providers import OpenAICompatibleChatProvider, ProviderConfig
from backend.app.models.domain import EquipmentItem, TariffCandidate

PROMPT_VERSION = "tariff-arbitration-v1"


@dataclass
class ArbitrationOutcome:
    status: str
    provider: str | None = None
    model: str | None = None
    selected_code: str | None = None
    confidence: float | None = None
    reason: str = ""
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cache_hit: bool = False
    guardrail_rejected: bool = False
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "selected_code": self.selected_code,
            "confidence": self.confidence,
            "reason": self.reason,
            "latency_ms": self.latency_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cache_hit": self.cache_hit,
            "guardrail_rejected": self.guardrail_rejected,
            "error": self.error,
            "prompt_version": PROMPT_VERSION,
        }


class ControlledTariffArbitrator:
    """LLM arbitration that is structurally unable to create a new CAMCIS code.

    The model receives only the merchandise description, limited project-use context and
    a closed list of CAMCIS candidates. Any output outside this candidate set is rejected.
    Prices, client names and source-document identifiers are never sent to cloud providers.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.cache = LLMDecisionCache(settings.llm_cache_path)
        self.providers = {
            "NVIDIA": OpenAICompatibleChatProvider(
                ProviderConfig(
                    name="NVIDIA",
                    model=settings.nvidia_model,
                    base_url=settings.nvidia_base_url,
                    api_key=settings.nvidia_api_key,
                    max_tokens_field="max_tokens",
                ),
                timeout_seconds=settings.llm_timeout_seconds,
            ),
            "OPENAI": OpenAICompatibleChatProvider(
                ProviderConfig(
                    name="OPENAI",
                    model=settings.openai_model,
                    base_url=settings.openai_base_url,
                    api_key=settings.openai_api_key,
                    max_tokens_field="max_completion_tokens",
                ),
                timeout_seconds=settings.llm_timeout_seconds,
            ),
        }

    def provider_statuses(self) -> list[dict[str, Any]]:
        statuses = []
        for name, provider in self.providers.items():
            item = provider.status()
            item["preferred"] = name == self._resolve_provider_name("AUTO")
            statuses.append(item)
        return statuses

    def _resolve_provider_name(self, requested: str | None) -> str | None:
        if not self.settings.enable_llm_arbitration:
            return None
        requested = (requested or self.settings.llm_provider or "AUTO").strip().upper()
        if requested in {"OFF", "NONE", "DISABLED"}:
            return None
        if requested in self.providers:
            return requested if self.providers[requested].config.configured else None
        # PoC priority: NVIDIA/Kimi if configured, then OpenAI. This is explicit and overridable.
        for name in ("NVIDIA", "OPENAI"):
            if self.providers[name].config.configured:
                return name
        return None

    def should_arbitrate(self, initial_status: str, candidates: list[TariffCandidate]) -> bool:
        if not self.settings.enable_llm_arbitration:
            return False
        if initial_status != "A_REVOIR" or len(candidates) < 2:
            return False
        if float(candidates[0].combined_score or 0.0) < self.settings.llm_min_retrieval_score:
            return False
        return True

    @staticmethod
    def _safe_text(value: str | None, max_chars: int) -> str:
        return " ".join((value or "").split())[:max_chars]

    def _prompts(
        self,
        item: EquipmentItem,
        candidates: list[TariffCandidate],
        *,
        sector: str = "",
        project_description: str = "",
    ) -> tuple[str, str]:
        system = (
            "Tu es un arbitre de classement tarifaire pour CADUCEUS. Tu ne peux PAS inventer, modifier ou compléter un code SH. "
            "Tu dois soit choisir EXACTEMENT un code parmi la liste fermée de candidats CAMCIS fournie, soit t'abstenir. "
            "Le contexte d'activité sert seulement à comprendre l'usage; il ne doit jamais remplacer les caractéristiques intrinsèques de la marchandise. "
            "N'utilise aucune connaissance tarifaire extérieure pour créer une position absente des candidats. "
            "Réponds uniquement par un objet JSON strict avec les clés: decision, selected_code, confidence, reason. "
            "decision vaut SELECT ou ABSTAIN. confidence est un nombre entre 0 et 1. reason est bref, factuel et en français."
        )
        candidate_rows = [
            {
                "rank": idx,
                "code": c.code_sh,
                "label": self._safe_text(c.libelle_douanier, 600),
            }
            for idx, c in enumerate(candidates[:5], start=1)
        ]
        body = {
            "designation": self._safe_text(item.designation_normalisee or item.designation_source, 500),
            "specifications": self._safe_text(item.specifications, 1200),
            "usage_context": {
                "sector": self._safe_text(sector, 300),
                "project_process": self._safe_text(project_description, 900),
            },
            "candidate_camcis_codes": candidate_rows,
            "mandatory_output_example": {
                "decision": "SELECT ou ABSTAIN",
                "selected_code": "code exact de la liste ou null",
                "confidence": 0.0,
                "reason": "justification courte",
            },
        }
        return system, json.dumps(body, ensure_ascii=False, separators=(",", ":"))

    def _cache_key(
        self,
        *,
        provider: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        payload = "\n".join([PROMPT_VERSION, provider, model, system_prompt, user_prompt])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def arbitrate(
        self,
        item: EquipmentItem,
        candidates: list[TariffCandidate],
        *,
        sector: str = "",
        project_description: str = "",
        requested_provider: str | None = None,
        use_cache: bool = True,
    ) -> ArbitrationOutcome:
        provider_name = self._resolve_provider_name(requested_provider)
        if not provider_name:
            return ArbitrationOutcome(status="NON_DISPONIBLE", reason="Aucun fournisseur IA d'arbitrage n'est configuré.")
        provider = self.providers[provider_name]
        model = provider.config.model
        system_prompt, user_prompt = self._prompts(item, candidates, sector=sector, project_description=project_description)
        cache_key = self._cache_key(provider=provider_name, model=model, system_prompt=system_prompt, user_prompt=user_prompt)
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached:
                cached["cache_hit"] = True
                return ArbitrationOutcome(**{k: v for k, v in cached.items() if k in ArbitrationOutcome.__dataclass_fields__})

        response = provider.complete_json(system_prompt=system_prompt, user_prompt=user_prompt, temperature=0.0)
        if not response.ok:
            outcome = ArbitrationOutcome(
                status="ERREUR_PROVIDER", provider=provider_name, model=model, latency_ms=response.latency_ms, error=response.error,
                reason="Le fournisseur IA n'a pas retourné de décision exploitable; le classement initial est conservé.",
            )
            return outcome

        allowed = {c.code_sh for c in candidates[:5]}
        try:
            data = provider.parse_json(response.content)
            decision = str(data.get("decision") or "").strip().upper()
            selected_raw = str(data.get("selected_code") or "").strip()
            selected_code = "".join(ch for ch in selected_raw if ch.isdigit()) or None
            try:
                confidence = float(data.get("confidence"))
            except Exception:
                confidence = 0.0
            confidence = max(0.0, min(1.0, confidence))
            reason = self._safe_text(str(data.get("reason") or ""), 600)
        except Exception as exc:
            return ArbitrationOutcome(
                status="REPONSE_INVALIDE", provider=provider_name, model=model, latency_ms=response.latency_ms,
                prompt_tokens=response.prompt_tokens, completion_tokens=response.completion_tokens, total_tokens=response.total_tokens,
                error=str(exc), reason="Réponse IA non conforme au format attendu; classement initial conservé.",
            )

        guardrail_rejected = False
        if decision == "SELECT":
            if selected_code not in allowed:
                guardrail_rejected = True
                outcome = ArbitrationOutcome(
                    status="REJETE_GARDEFOU", provider=provider_name, model=model, selected_code=None,
                    confidence=confidence, reason="Le modèle a proposé un code absent de la liste fermée CAMCIS; réponse rejetée.",
                    latency_ms=response.latency_ms, prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens, total_tokens=response.total_tokens,
                    guardrail_rejected=True,
                )
            elif confidence < self.settings.llm_min_confidence:
                outcome = ArbitrationOutcome(
                    status="ABSTENTION", provider=provider_name, model=model, selected_code=None,
                    confidence=confidence, reason=reason or "Confiance IA insuffisante; abstention.",
                    latency_ms=response.latency_ms, prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens, total_tokens=response.total_tokens,
                )
            else:
                outcome = ArbitrationOutcome(
                    status="SELECT", provider=provider_name, model=model, selected_code=selected_code,
                    confidence=confidence, reason=reason,
                    latency_ms=response.latency_ms, prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens, total_tokens=response.total_tokens,
                )
        elif decision == "ABSTAIN":
            outcome = ArbitrationOutcome(
                status="ABSTENTION", provider=provider_name, model=model, selected_code=None,
                confidence=confidence, reason=reason or "Le modèle ne dispose pas d'éléments suffisants pour départager les candidats.",
                latency_ms=response.latency_ms, prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens, total_tokens=response.total_tokens,
            )
        else:
            outcome = ArbitrationOutcome(
                status="REPONSE_INVALIDE", provider=provider_name, model=model, selected_code=None,
                confidence=confidence, reason="Décision IA hors schéma SELECT/ABSTAIN; classement initial conservé.",
                latency_ms=response.latency_ms, prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens, total_tokens=response.total_tokens,
            )

        if use_cache and outcome.status in {"SELECT", "ABSTENTION", "REJETE_GARDEFOU"}:
            self.cache.put(
                cache_key,
                provider=provider_name,
                model_name=model,
                prompt_version=PROMPT_VERSION,
                decision=outcome.as_dict(),
            )
        return outcome
