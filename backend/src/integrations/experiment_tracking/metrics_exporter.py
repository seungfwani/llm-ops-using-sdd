"""Prometheus metrics exporter for experiment tracking tools (e.g. MLflow)."""

from __future__ import annotations

import logging
from typing import Dict

from prometheus_client import Gauge

logger = logging.getLogger(__name__)


MLFLOW_EXPERIMENTS_TOTAL = Gauge(
    "llm_ops_mlflow_experiments_total",
    "Number of experiments visible to the MLflow adapter "
    "(best‑effort, exported when adapter can query the tracking server).",
)

MLFLOW_RUNS_TOTAL = Gauge(
    "llm_ops_mlflow_runs_total",
    "Number of runs visible to the MLflow adapter "
    "(best‑effort, exported when adapter can query the tracking server).",
)


def export_mlflow_metrics(stats: Dict[str, int]) -> None:
    """Export high‑level MLflow statistics as Prometheus metrics.

    This helper is intentionally generic so that callers (services or
    background jobs) can decide when and how to collect the underlying
    data from MLflow.

    Expected keys in ``stats``:
      - experiments: int
      - runs: int
    """
    try:
        if "experiments" in stats:
            MLFLOW_EXPERIMENTS_TOTAL.set(int(stats["experiments"]))
        if "runs" in stats:
            MLFLOW_RUNS_TOTAL.set(int(stats["runs"]))
    except Exception as exc:
        # Never break the request path because of metrics
        logger.exception("Failed to export MLflow metrics: %s", exc)


