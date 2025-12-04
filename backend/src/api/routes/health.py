"""Integration health check API routes."""

from __future__ import annotations

from fastapi import APIRouter

from core.settings import get_settings
from integrations.experiment_tracking.mlflow_adapter import MLflowAdapter
from integrations.orchestration.argo_adapter import ArgoWorkflowsAdapter
from integrations.serving.kserve_adapter import KServeAdapter
from integrations.versioning.dvc_adapter import DVCAdapter
from integrations.health_check import IntegrationHealthCheck
from integrations.status_monitor import refresh_integration_status

router = APIRouter(prefix="/llm-ops/v1/health", tags=["health"])


def _build_adapters():
    """Construct adapters based on current settings.

    This keeps the endpoint self‑contained and avoids adding new
    dependencies to the main application wiring.
    """
    settings = get_settings()

    adapters = {
        "experiment_tracking": MLflowAdapter(
            {
                "enabled": settings.experiment_tracking_enabled and settings.mlflow_enabled,
                "tracking_uri": str(settings.mlflow_tracking_uri)
                if settings.mlflow_tracking_uri
                else "",
            }
        ),
        "serving": KServeAdapter(
            {
                "enabled": settings.serving_framework_enabled and settings.use_kserve,
                "namespace": settings.kserve_namespace,
            }
        ),
        "orchestration": ArgoWorkflowsAdapter(
            {
                "enabled": settings.workflow_orchestration_enabled and settings.argo_workflows_enabled,
                "namespace": settings.argo_workflows_namespace,
                "controller_service": settings.argo_workflows_controller_service,
            }
        ),
        "versioning": DVCAdapter(
            {
                "enabled": settings.data_versioning_enabled and settings.dvc_enabled,
                "remote_name": settings.dvc_remote_name,
                "remote_url": settings.dvc_remote_url,
                "cache_dir": settings.dvc_cache_dir,
            }
        ),
    }
    return adapters


@router.get("/integrations")
def get_integrations_health():
    """Return health status for all configured integrations.

    Response format follows the existing `{status,message,data}` envelope
    convention used by other `/llm-ops/v1` endpoints.
    """
    adapters = _build_adapters()
    health_service = IntegrationHealthCheck(adapters)
    result = health_service.check_all()

    # Also refresh Prometheus metrics (best‑effort)
    refresh_integration_status(adapters)

    return {
        "status": "success",
        "message": "",
        "data": result,
    }


