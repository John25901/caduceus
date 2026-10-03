from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    base_url: str
    api_key: str
    max_tokens_field: str = "max_tokens"

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip() and self.model.strip() and self.base_url.strip())


@dataclass
class ProviderResponse:
    ok: bool
    content: str = ""
    latency_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    error: str | None = None
    http_status: int | None = None


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        raise ValueError("Réponse IA sans objet JSON exploitable.")
    obj = json.loads(match.group(0))
    if not isinstance(obj, dict):
        raise ValueError("Réponse IA JSON invalide.")
    return obj


class OpenAICompatibleChatProvider:
    """Minimal provider client using the OpenAI-compatible chat-completions envelope.

    We intentionally use requests, already present in CADUCEUS, to avoid a new heavy
    dependency during workstation upgrades.
    """

    def __init__(self, config: ProviderConfig, timeout_seconds: int = 45):
        self.config = config
        self.timeout_seconds = timeout_seconds

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.config.name,
            "model": self.config.model,
            "configured": self.config.configured,
            "base_url": self.config.base_url,
        }

    def complete_json(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> ProviderResponse:
        if not self.config.configured:
            return ProviderResponse(ok=False, error=f"{self.config.name} non configuré.")
        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "stream": False,
        }
        payload[self.config.max_tokens_field] = 420
        started = time.perf_counter()
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout_seconds)
            latency_ms = (time.perf_counter() - started) * 1000.0
            if not response.ok:
                detail = response.text[:800]
                return ProviderResponse(
                    ok=False, latency_ms=latency_ms, error=f"HTTP {response.status_code}: {detail}", http_status=response.status_code
                )
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return ProviderResponse(ok=False, latency_ms=latency_ms, error="Réponse IA sans choix.", http_status=response.status_code)
            content = ((choices[0].get("message") or {}).get("content") or "").strip()
            usage = data.get("usage") or {}
            return ProviderResponse(
                ok=True,
                content=content,
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens") or usage.get("input_tokens"),
                completion_tokens=usage.get("completion_tokens") or usage.get("output_tokens"),
                total_tokens=usage.get("total_tokens"),
                http_status=response.status_code,
            )
        except Exception as exc:
            return ProviderResponse(ok=False, latency_ms=(time.perf_counter() - started) * 1000.0, error=str(exc))


    def complete_multimodal_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/png",
        temperature: float = 0.0,
        max_tokens: int = 1400,
    ) -> ProviderResponse:
        """OpenAI-compatible multimodal request with an inline base64 image.

        Used only as a rescue path after local OCR. The provider receives the
        source image plus the local OCR transcription so it can reconstruct
        columns without being asked to invent missing values.
        """
        if not self.config.configured:
            return ProviderResponse(ok=False, error=f"{self.config.name} non configuré.")
        if not image_bytes:
            return ProviderResponse(ok=False, error="Image vide.")

        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        encoded = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:{mime_type};base64,{encoded}"
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                },
            ],
            "temperature": temperature,
            "stream": False,
        }
        payload[self.config.max_tokens_field] = max_tokens
        started = time.perf_counter()
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=self.timeout_seconds)
            latency_ms = (time.perf_counter() - started) * 1000.0
            if not response.ok:
                detail = response.text[:800]
                return ProviderResponse(
                    ok=False,
                    latency_ms=latency_ms,
                    error=f"HTTP {response.status_code}: {detail}",
                    http_status=response.status_code,
                )
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                return ProviderResponse(
                    ok=False,
                    latency_ms=latency_ms,
                    error="Réponse IA sans choix.",
                    http_status=response.status_code,
                )
            content = ((choices[0].get("message") or {}).get("content") or "").strip()
            usage = data.get("usage") or {}
            return ProviderResponse(
                ok=True,
                content=content,
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens") or usage.get("input_tokens"),
                completion_tokens=usage.get("completion_tokens") or usage.get("output_tokens"),
                total_tokens=usage.get("total_tokens"),
                http_status=response.status_code,
            )
        except Exception as exc:
            return ProviderResponse(
                ok=False,
                latency_ms=(time.perf_counter() - started) * 1000.0,
                error=str(exc),
            )

    @staticmethod
    def parse_json(text: str) -> dict[str, Any]:
        return _extract_json_object(text)
