"""In-memory, bounded metrics store (E5.5).

Each replica exposes the metrics it served; the JSON logs remain the source for
a centralised dashboard when several replicas run.
"""

from __future__ import annotations

import math
from collections import Counter, deque

from application.ports.metrics import InvocationRecord, MetricsSummary


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(math.ceil(percentile * len(ordered)) - 1, 0)
    return round(ordered[index], 2)


class InMemoryMetricsStore:
    def __init__(self, *, window_size: int = 200) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._window_size = window_size
        self._records: deque[InvocationRecord] = deque(maxlen=window_size)

    async def record(self, record: InvocationRecord) -> None:
        self._records.append(record)

    async def summary(self) -> MetricsSummary:
        records = list(self._records)
        latencies = [record.latency_total_ms for record in records]
        outcomes = Counter(record.outcome for record in records)
        return MetricsSummary(
            invocations=len(records),
            window_size=self._window_size,
            avg_latency_ms=round(sum(latencies) / len(latencies), 2)
            if latencies
            else 0.0,
            p95_latency_ms=_percentile(latencies, 0.95),
            input_tokens=sum(record.input_tokens for record in records),
            output_tokens=sum(record.output_tokens for record in records),
            cost_usd=round(sum(record.cost_usd for record in records), 8),
            by_outcome=dict(outcomes),
        )
