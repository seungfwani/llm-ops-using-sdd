#!/usr/bin/env python3
"""One‑off migration script: migrate existing serving endpoints to KServe.

Usage:
    cd backend
    python -m scripts.migrate_serving_to_kserve

For each existing ServingEndpoint without a ServingDeployment record, this script
will attempt to create a corresponding KServe InferenceService via the adapter.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from core.database import SessionLocal
from core.settings import get_settings
from integrations.serving.kserve_adapter import KServeAdapter


def migrate_serving_endpoints(session: Session) -> None:
    """Create KServe deployments for existing serving endpoints."""
    settings = get_settings()
    if not (settings.serving_framework_enabled and settings.use_kserve):
        print("✗ KServe integration is not enabled. "
              "Set SERVING_FRAMEWORK_ENABLED=true and USE_KSERVE=true.")
        return

    adapter = KServeAdapter(
        {
            "enabled": True,
            "namespace": settings.training_namespace,
        }
    )

    print("Discovering serving endpoints without ServingDeployment records...")
    endpoints = (
        session.query(catalog_models.ServingEndpoint)
        .outerjoin(catalog_models.ServingDeployment)
        .filter(catalog_models.ServingDeployment.id.is_(None))
        .all()
    )

    if not endpoints:
        print("✓ No serving endpoints require migration.")
        return

    print(f"Found {len(endpoints)} endpoint(s) without ServingDeployment; migrating to KServe...")

    for endpoint in endpoints:
        try:
            # Derive a simple model URI; in a real deployment this should come
            # from model registry or training output metadata.
            model_uri = endpoint.runtime_image or settings.serving_runtime_image
            model_name = f"model-{endpoint.model_entry_id}"

            result = adapter.deploy(
                endpoint_id=endpoint.id,
                model_uri=model_uri,
                model_name=model_name,
                namespace=settings.training_namespace,
                resource_requests={
                    "cpu": settings.serving_cpu_request,
                    "memory": settings.serving_memory_request,
                },
                resource_limits={
                    "cpu": settings.serving_cpu_limit,
                    "memory": settings.serving_memory_limit,
                },
                min_replicas=endpoint.min_replicas or 1,
                max_replicas=endpoint.max_replicas or 1,
                autoscaling_metrics=None,
            )

            framework_resource_id = result.get("framework_resource_id")
            framework_namespace = result.get("framework_namespace")

            if not framework_resource_id:
                print(f"  ⚠ Failed to deploy KServe for endpoint {endpoint.id} (no framework_resource_id)")
                continue

            deployment = catalog_models.ServingDeployment(
                id=uuid4(),
                serving_endpoint_id=endpoint.id,
                serving_framework="kserve",
                framework_resource_id=framework_resource_id,
                framework_namespace=framework_namespace,
                replica_count=0,
                min_replicas=endpoint.min_replicas or 1,
                max_replicas=endpoint.max_replicas or 1,
                autoscaling_metrics={},
                resource_requests={
                    "cpu": settings.serving_cpu_request,
                    "memory": settings.serving_memory_request,
                },
                resource_limits={
                    "cpu": settings.serving_cpu_limit,
                    "memory": settings.serving_memory_limit,
                },
                framework_status={},
            )
            session.add(deployment)
            session.commit()

            print(
                f"  ✓ Migrated serving endpoint {endpoint.id} "
                f"to KServe resource {framework_resource_id}"
            )
        except Exception as exc:
            session.rollback()
            print(f"  ✗ Error migrating serving endpoint {endpoint.id}: {exc}")


def main() -> None:
    print("=" * 60)
    print("Migrating serving endpoints to KServe...")
    print("=" * 60)

    session = SessionLocal()
    try:
        migrate_serving_endpoints(session)
        print("✓ Serving migration completed.")
    finally:
        session.close()


if __name__ == "__main__":
    main()


