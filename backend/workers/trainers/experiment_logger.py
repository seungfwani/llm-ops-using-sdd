"""Worker for logging training experiment metrics to MLflow-compatible store."""
from __future__ import annotations

import logging
import time
from typing import Optional

import mlflow
from sqlalchemy.orm import Session

from backend.src.core.database import get_session
from backend.src.training.repositories import ExperimentMetricRepository, TrainingJobRepository

logger = logging.getLogger(__name__)


class ExperimentLogger:
    """Worker that polls training jobs and logs metrics to MLflow."""

    def __init__(self, session: Session):
        self.job_repo = TrainingJobRepository(session)
        self.metric_repo = ExperimentMetricRepository(session)
        self.session = session
        mlflow.set_tracking_uri("sqlite:///mlflow.db")  # TODO: Use settings

    def log_experiment(self, job_id: str) -> None:
        """Log a training job's experiment to MLflow."""
        job = self.job_repo.get(job_id)
        if not job:
            logger.warning(f"Training job {job_id} not found")
            return

        try:
            with mlflow.start_run(run_name=f"training-{job_id}"):
                # Log job metadata
                mlflow.log_param("job_id", str(job.id))
                mlflow.log_param("model_entry_id", str(job.model_entry_id))
                mlflow.log_param("dataset_id", str(job.dataset_id))
                mlflow.log_param("job_type", job.job_type)
                mlflow.log_param("status", job.status)

                # Log resource profile
                if job.resource_profile:
                    for key, value in job.resource_profile.items():
                        mlflow.log_param(f"resource_{key}", value)

                # Log all metrics
                metrics = self.metric_repo.list_by_job(job_id)
                for metric in metrics:
                    mlflow.log_metric(
                        metric.name,
                        metric.value,
                        step=int(metric.recorded_at.timestamp()),
                    )

                # Log tags
                mlflow.set_tag("submitted_by", job.submitted_by)
                mlflow.set_tag("submitted_at", job.submitted_at.isoformat())

                if job.completed_at:
                    mlflow.set_tag("completed_at", job.completed_at.isoformat())

                logger.info(f"Logged experiment for job {job_id} to MLflow")
        except Exception as e:
            logger.error(f"Failed to log experiment for job {job_id}: {e}")
            raise

    def poll_and_log(self, interval_seconds: int = 60) -> None:
        """Continuously poll running jobs and log their metrics."""
        logger.info("Starting experiment logger worker")
        while True:
            try:
                # Find all running jobs
                running_jobs = self.job_repo.list(status="running")
                for job in running_jobs:
                    try:
                        # Log metrics for this job
                        metrics = self.metric_repo.list_by_job(str(job.id))
                        if metrics:
                            with mlflow.start_run(run_name=f"training-{job.id}", nested=True):
                                for metric in metrics:
                                    mlflow.log_metric(
                                        metric.name,
                                        metric.value,
                                        step=int(metric.recorded_at.timestamp()),
                                    )
                    except Exception as e:
                        logger.error(f"Failed to log metrics for job {job.id}: {e}")

                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                logger.info("Experiment logger worker stopped")
                break
            except Exception as e:
                logger.error(f"Error in experiment logger worker: {e}")
                time.sleep(interval_seconds)


if __name__ == "__main__":
    # Standalone worker entry point
    session = next(get_session())
    logger_worker = ExperimentLogger(session)
    logger_worker.poll_and_log()

