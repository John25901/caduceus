from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.app.models.domain import TariffAssessment


SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    dossier_ref TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_document TEXT,
    source_row INTEGER,
    designation TEXT,
    payload_json TEXT NOT NULL,
    camcis_sha256 TEXT NOT NULL,
    engine_version TEXT NOT NULL
);
"""


class AuditStore:
    """Append-only by application convention. No update/delete methods are exposed."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self):
        return sqlite3.connect(self.path)

    def append_assessment(self, dossier_ref: str, assessment: TariffAssessment, camcis_sha256: str) -> str:
        event_id = str(uuid.uuid4())
        payload = assessment.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO audit_events
                   (event_id, created_at, dossier_ref, event_type, source_document, source_row,
                    designation, payload_json, camcis_sha256, engine_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    datetime.now(timezone.utc).isoformat(),
                    dossier_ref,
                    "TARIFF_ASSESSMENT_V2_6",
                    assessment.item.source_document,
                    assessment.item.source_row,
                    assessment.item.designation_source,
                    json.dumps(payload, ensure_ascii=False),
                    camcis_sha256,
                    "2.6-sprint6-controlled-ai",
                ),
            )
        return event_id
