"""Expose the aggregated metrics of the agent invocations (E5.5)."""

from __future__ import annotations

from application.ports.metrics import MetricsStore, MetricsSummary


class GetAgentMetrics:
    def __init__(self, metrics: MetricsStore) -> None:
        self._metrics = metrics

    async def execute(self) -> MetricsSummary:
        return await self._metrics.summary()
