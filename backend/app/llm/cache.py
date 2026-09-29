from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_decision_cache (
    cache_key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    decision_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_cache_created_at ON llm_decision_cache(created_at DESC);
"""


class LLMDecisionCache:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def get(self, cache_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT decision_json FROM llm_decision_cache WHERE cache_key=?", (cache_key,)
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["decision_json"])
        except Exception:
            return None

    def put(self, cache_key: str, *, provider: str, model_name: str, prompt_version: str, decision: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO llm_decision_cache
                   (cache_key, created_at, provider, model_name, prompt_version, decision_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    cache_key,
                    datetime.now(timezone.utc).isoformat(),
                    provider,
                    model_name,
                    prompt_version,
                    json.dumps(decision, ensure_ascii=False),
                ),
            )
