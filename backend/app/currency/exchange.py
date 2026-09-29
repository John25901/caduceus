from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

import requests

EUR_XAF_PEG = Decimal("655.957")


@dataclass(frozen=True)
class ExchangeRateResult:
    currency: str
    xaf_per_unit: float | None
    rate_date: str | None
    source: str
    cached: bool = False
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "currency": self.currency,
            "xaf_per_unit": self.xaf_per_unit,
            "rate_date": self.rate_date,
            "source": self.source,
            "cached": self.cached,
            "error": self.error,
        }


class ExchangeRateService:
    """Automatic XAF conversion with an auditable, frugal daily cache.

    XAF/EUR uses the fixed BEAC parity (1 EUR = 655.957 XAF). For other
    currencies, CADUCEUS fetches the latest currency->EUR reference rate from
    Frankfurter and derives XAF deterministically from the fixed peg. A manual
    dossier rate can still override the automatic rate when an official customs
    rate is known.
    """

    def __init__(self, cache_path: Path, http_get: Callable = requests.get):
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.http_get = http_get

    @staticmethod
    def normalize_currency(currency: str | None) -> str | None:
        if not currency:
            return None
        c = str(currency).strip().upper()
        aliases = {"FCFA": "XAF", "CFA": "XAF", "$": "USD", "US$": "USD", "€": "EUR"}
        return aliases.get(c, c)

    def _load_cache(self) -> dict:
        try:
            if self.cache_path.exists():
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _save_cache(self, data: dict) -> None:
        tmp = self.cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.cache_path)

    def get_xaf_rate(self, currency: str | None, manual_rate: float | None = None) -> ExchangeRateResult:
        c = self.normalize_currency(currency)
        if c in {None, "XAF"}:
            return ExchangeRateResult(c or "XAF", 1.0, None, "XAF source", False)
        if manual_rate and manual_rate > 0:
            return ExchangeRateResult(c, float(manual_rate), None, "Taux dossier saisi manuellement", False)
        if c == "EUR":
            return ExchangeRateResult("EUR", float(EUR_XAF_PEG), None, "Parité fixe BEAC EUR/XAF", False)

        cache = self._load_cache()
        today = datetime.now(timezone.utc).date().isoformat()
        key = f"{c}_XAF"
        cached = cache.get(key) or {}
        if cached.get("fetched_on") == today and cached.get("xaf_per_unit"):
            return ExchangeRateResult(c, float(cached["xaf_per_unit"]), cached.get("rate_date"), cached.get("source", "cache"), True)

        try:
            url = f"https://api.frankfurter.dev/v2/rate/{c.lower()}/eur"
            response = self.http_get(url, timeout=8)
            response.raise_for_status()
            payload = response.json()
            eur_per_unit = Decimal(str(payload["rate"]))
            xaf = eur_per_unit * EUR_XAF_PEG
            result = {
                "currency": c,
                "xaf_per_unit": float(xaf),
                "rate_date": payload.get("date"),
                "source": "Frankfurter (références banques centrales) + parité fixe BEAC EUR/XAF",
                "fetched_on": today,
            }
            cache[key] = result
            self._save_cache(cache)
            return ExchangeRateResult(c, result["xaf_per_unit"], result["rate_date"], result["source"], False)
        except Exception as exc:
            # A stale cached rate is safer than inventing a new one; expose the age/source.
            if cached.get("xaf_per_unit"):
                return ExchangeRateResult(c, float(cached["xaf_per_unit"]), cached.get("rate_date"), cached.get("source", "cache antérieur"), True, str(exc))
            return ExchangeRateResult(c, None, None, "indisponible", False, str(exc))
