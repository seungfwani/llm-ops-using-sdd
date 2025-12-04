#!/usr/bin/env python3
"""One‑off migration script: migrate existing experiment data to MLflow.

Usage:
    cd backend
    python -m scripts.migrate_experiments_to_mlflow

This script is intentionally conservative: it only reads from the existing
tables and pushes BEST‑EFFORT copies into MLflow via the configured adapter.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from core.database import SessionLocal
from core.settings import get_settings
from integrations.experiment_tracking.mlflow_adapter import MLflowAdapter


def migrate_experiments(session: Session) -> None:
    """Migrate existing training job experiment data into MLflow."""
    settings = get_settings()
    if not (settings.experiment_tracking_enabled and settings.mlflow_enabled and settings.mlflow_tracking_uri):
        print("✗ MLflow integration is not fully enabled. "
              "Set EXPERIMENT_TRACKING_ENABLED=true, MLFLOW_ENABLED=true, and MLFLOW_TRACKING_URI.")
        return

    adapter = MLflowAdapter(
        {
            "enabled": True,
            "tracking_uri": str(settings.mlflow_tracking_uri),
        }
    )

    print("Discovering training jobs without ExperimentRun records...")
    jobs = (
        session.query(catalog_models.TrainingJob)
        .outerjoin(catalog_models.ExperimentRun)
        .filter(catalog_models.ExperimentRun.id.is_(None))
        .all()
    )

    if not jobs:
        print("✓ No training jobs require migration.")
        return

    print(f"Found {len(jobs)} training job(s) without ExperimentRun; migrating to MLflow...")

    for job in jobs:
        try:
            experiment_name = f"training-job-{job.id}"
            run_name = job.job_type
            params = job.hyperparameters or {}

            result = adapter.create_run(
                experiment_name=experiment_name,
                run_name=run_name,
                parameters=params,
                tags={
                    "training_job_id": str(job.id),
                    "model_entry_id": str(job.model_entry_id),
                },
            )

            run_id = result.get("run_id")
            if not run_id:
                print(f"  ⚠ Failed to create MLflow run for job {job.id} (no run_id returned)")
                continue

            # Create ExperimentRun record in our catalog DB
            experiment_run = catalog_models.ExperimentRun(
                training_job_id=job.id,
                tracking_system="mlflow",
                tracking_run_id=run_id,
                experiment_name=experiment_name,
                run_name=run_name,
                parameters=params,
                metrics={},
                artifact_uris=[],
                status=job.status,
            )
            session.add(experiment_run)
            session.commit()

            print(f"  ✓ Migrated training job {job.id} to MLflow run {run_id}")
        except Exception as exc:
            session.rollback()
            print(f"  ✗ Error migrating training job {job.id}: {exc}")


def main() -> None:
    print("=" * 60)
    print("Migrating experiments to MLflow...")
    print("=" * 60)

    session = SessionLocal()
    try:
        migrate_experiments(session)
        print("✓ Experiment migration completed.")
    finally:
        session.close()


if __name__ == "__main__":
    main()


