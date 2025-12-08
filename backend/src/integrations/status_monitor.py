"""Background helpers for monitoring integration status.

This module does not start its own scheduler; instead it offers
idempotent functions that can be wired into existing schedulers
or called on‑demand by API endpoints.
"""

from __future__ import annotations

import logging
from typing import Dict

from integrations.base_adapter import BaseAdapter
from integrations.observability import export_integration_health_metrics

logger = logging.getLogger(__name__)


def refresh_integration_status(adapters: Dict[str, BaseAdapter]) -> Dict[str, str]:
    """Refresh integration health metrics and return a snapshot of statuses.

    Args:
        adapters: mapping from integration type to adapter instance.

    Returns:
        Simple mapping {integration_type: status}.
    """
    snapshot: Dict[str, str] = {}

    for name, adapter in adapters.items():
        try:
            health = adapter.health_check()
            snapshot[name] = health.get("status", "unavailable")
        except Exception as exc:
            logger.exception("Failed to refresh health for %s: %s", name, exc)
            snapshot[name] = "unavailable"

    # Export Prometheus metrics in a single place to avoid duplication
    export_integration_health_metrics(adapters)
    return snapshot


