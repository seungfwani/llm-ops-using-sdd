"""Unified observability helpers for open source integrations.

This module exposes Prometheus metrics that aggregate the health and
status of all configured open‑source tools (MLflow, KServe, Argo, DVC, etc.).

The intent is NOT to replace the tools' own metrics, but to provide
high‑level, platform‑centric signals that can be used in Grafana dashboards
and alerting.
"""

from __future__ import annotations

import logging
from typing import Dict

from prometheus_client import Gauge

from core.settings import get_settings
from integrations.base_adapter import BaseAdapter

logger = logging.getLogger(__name__)


# Status mapping for integrations:
#   healthy   -> 2
#   degraded  -> 1
#   disabled/unavailable/other -> 0
INTEGRATION_STATUS_GAUGE = Gauge(
    "llm_ops_integration_status",
    "Status of open‑source integrations "
    "(0=unavailable/disabled, 1=degraded, 2=healthy)",
    labelnames=("integration_type", "tool_name"),
)


def _status_to_value(status: str) -> int:
    status = (status or "").lower()
    if status == "healthy":
        return 2
    if status == "degraded":
        return 1
    return 0


def export_integration_health_metrics(adapters: Dict[str, BaseAdapter]) -> None:
    """Export health information for all integrations to Prometheus gauges.

    Args:
        adapters: dict mapping logical integration keys to adapter instances.
                  Keys are expected to be stable identifiers such as
                  \"experiment_tracking\", \"serving\", \"orchestration\",
                  \"registry\", \"versioning\".
    """
    settings = get_settings()

    for name, adapter in adapters.items():
        try:
            health = adapter.health_check()
            status = health.get("status", "unavailable")

            # Try to infer concrete tool name from settings + adapter type
            tool_name = "unknown"
            if name == "experiment_tracking":
                tool_name = settings.experiment_tracking_system
            elif name == "serving":
                tool_name = settings.serving_framework_default
            elif name == "orchestration":
                tool_name = settings.workflow_orchestration_system
            elif name == "registry":
                tool_name = settings.model_registry_default
            elif name == "versioning":
                tool_name = settings.data_versioning_system

            INTEGRATION_STATUS_GAUGE.labels(
                integration_type=name,
                tool_name=tool_name,
            ).set(_status_to_value(status))
        except Exception as exc:  # defensive – metrics must never break requests
            logger.exception("Failed to export health metrics for %s: %s", name, exc)
            INTEGRATION_STATUS_GAUGE.labels(
                integration_type=name,
                tool_name="unknown",
            ).set(0)


