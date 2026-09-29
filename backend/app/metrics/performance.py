from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import psutil


@dataclass
class PerformanceSnapshot:
    duration_ms: float
    rss_before_mb: float
    rss_after_mb: float
    rss_delta_mb: float
    details: dict[str, Any] = field(default_factory=dict)


class PerformanceProbe:
    """Lightweight wall-clock + process RSS probe.

    This deliberately avoids continuous sampling so observability itself remains cheap.
    RSS delta is not a true peak-memory measurement; it is an operational signal.
    """

    def __init__(self):
        self._process = psutil.Process(os.getpid())
        self._start = 0.0
        self._rss_before = 0

    def __enter__(self) -> "PerformanceProbe":
        self._rss_before = self._process.memory_info().rss
        self._start = time.perf_counter()
        return self

    def finish(self, details: dict[str, Any] | None = None) -> PerformanceSnapshot:
        elapsed = (time.perf_counter() - self._start) * 1000.0
        rss_after = self._process.memory_info().rss
        before_mb = self._rss_before / (1024 * 1024)
        after_mb = rss_after / (1024 * 1024)
        return PerformanceSnapshot(
            duration_ms=round(elapsed, 3),
            rss_before_mb=round(before_mb, 3),
            rss_after_mb=round(after_mb, 3),
            rss_delta_mb=round(after_mb - before_mb, 3),
            details=details or {},
        )

    def __exit__(self, exc_type, exc, tb) -> None:
        return None
