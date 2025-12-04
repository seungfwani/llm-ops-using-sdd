"""Prometheus metrics exporter for orchestration tools (e.g. Argo Workflows)."""

from __future__ import annotations

import logging
from typing import Dict

from prometheus_client import Gauge

logger = logging.getLogger(__name__)


ARGO_WORKFLOWS_TOTAL = Gauge(
    "llm_ops_argo_workflows_total",
    "Number of workflows tracked by the orchestration adapter "
    "(best‑effort, exported when adapter can query the cluster).",
)

ARGO_WORKFLOWS_RUNNING = Gauge(
    "llm_ops_argo_workflows_running",
    "Number of running workflows tracked by the orchestration adapter "
    "(best‑effort, exported when adapter can query the cluster).",
)


def export_argo_metrics(stats: Dict[str, int]) -> None:
    """Export high‑level Argo Workflows statistics as Prometheus metrics.

    Expected keys in ``stats``:
      - total: int
      - running: int
    """
    try:
        if "total" in stats:
            ARGO_WORKFLOWS_TOTAL.set(int(stats["total"]))
        if "running" in stats:
            ARGO_WORKFLOWS_RUNNING.set(int(stats["running"]))
    except Exception as exc:
        logger.exception("Failed to export Argo Workflows metrics: %s", exc)


