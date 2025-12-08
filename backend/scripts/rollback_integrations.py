#!/usr/bin/env python3
"""Rollback helper for open‑source integrations.

Usage:
    cd backend
    python -m scripts.rollback_integrations

This script provides a simple, manual rollback flow:
  1. Disables all integration feature flags in Settings (env driven).
  2. Optionally deletes KServe deployments created via ServingDeployment records.
  3. Leaves core platform data intact so that custom implementations continue to work.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from core.database import SessionLocal
from core.settings import get_settings
from integrations.serving.kserve_adapter import KServeAdapter


def disable_feature_flags() -> None:
    """Print guidance for disabling integration feature flags.

    Settings are environment‑driven, so we can't persist changes here,
    but we can tell the operator exactly what to do.
    """
    print("To rollback integrations, update your backend .env as follows:")
    print("  EXPERIMENT_TRACKING_ENABLED=false")
    print("  SERVING_FRAMEWORK_ENABLED=false")
    print("  WORKFLOW_ORCHESTRATION_ENABLED=false")
    print("  MODEL_REGISTRY_ENABLED=false")
    print("  DATA_VERSIONING_ENABLED=false")
    print("")
    print("Then restart the backend deployment (e.g., via Kubernetes rollout).")


def delete_kserve_deployments(session: Session) -> None:
    """Optionally delete KServe resources for existing ServingDeployment entries."""
    settings = get_settings()
    if not settings.use_kserve:
        print("KServe is not enabled in current Settings; skipping KServe cleanup.")
        return

    adapter = KServeAdapter(
        {
            "enabled": True,
            "namespace": settings.training_namespace,
        }
    )

    deployments = (
        session.query(catalog_models.ServingDeployment)
        .filter(catalog_models.ServingDeployment.serving_framework == "kserve")
        .all()
    )

    if not deployments:
        print("No KServe ServingDeployment records found; nothing to delete.")
        return

    print(f"Found {len(deployments)} KServe deployment record(s).")
    confirm = os.environ.get("ROLLBACK_CONFIRM", "").lower()
    if confirm not in ("yes", "y", "true", "1"):
        print(
            "Set ROLLBACK_CONFIRM=yes in the environment if you want this script "
            "to delete KServe InferenceService resources."
        )
        return

    for deployment in deployments:
        try:
            adapter.delete_deployment(
                framework_resource_id=deployment.framework_resource_id,
                namespace=deployment.framework_namespace or settings.training_namespace,
            )
            print(
                f"  ✓ Requested deletion of KServe resource "
                f"{deployment.framework_resource_id} "
                f"in namespace {deployment.framework_namespace or settings.training_namespace}"
            )
        except Exception as exc:
            print(
                f"  ✗ Failed to delete KServe resource {deployment.framework_resource_id}: {exc}"
            )


def main() -> None:
    print("=" * 60)
    print("Rolling back open‑source integrations (operator‑assisted)...")
    print("=" * 60)

    disable_feature_flags()

    session = SessionLocal()
    try:
        delete_kserve_deployments(session)
        print("Rollback helper completed. Apply env changes and restart backend.")
    finally:
        session.close()


if __name__ == "__main__":
    main()


