"""Training job orchestration services."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from training.repositories import ExperimentMetricRepository, TrainingJobRepository
from training.scheduler import KubernetesScheduler

logger = logging.getLogger(__name__)


class TrainingJobService:
    """Service for managing training jobs and experiment tracking."""

    def __init__(self, session: Session):
        self.job_repo = TrainingJobRepository(session)
        self.metric_repo = ExperimentMetricRepository(session)
        self.scheduler = KubernetesScheduler()
        self.session = session

    def submit_job(
        self,
        model_entry_id: str,
        dataset_id: str,
        job_type: str,
        resource_profile: dict,
        hyperparameters: Optional[dict] = None,
        retry_policy: Optional[dict] = None,
        submitted_by: str = "system",
    ) -> catalog_models.TrainingJob:
        """
        Submit a training job to the scheduler.

        Args:
            model_entry_id: Catalog model entry ID
            dataset_id: Dataset record ID
            job_type: 'finetune' or 'distributed'
            resource_profile: GPU count, GPU type, max duration
            hyperparameters: Training hyperparameters
            retry_policy: Retry configuration
            submitted_by: User ID who submitted the job

        Returns:
            Created TrainingJob entity
        """
        # Validate model and dataset exist and are approved
        model_entry = self.session.get(catalog_models.ModelCatalogEntry, model_entry_id)
        if not model_entry:
            raise ValueError(f"Model entry {model_entry_id} not found")
        if model_entry.status != "approved":
            raise ValueError(f"Model entry {model_entry_id} is not approved")

        dataset = self.session.get(catalog_models.DatasetRecord, dataset_id)
        if not dataset:
            raise ValueError(f"Dataset {dataset_id} not found")
        if not dataset.approved_at:
            raise ValueError(f"Dataset {dataset_id} is not approved")

        # Create job entity
        job = catalog_models.TrainingJob(
            id=uuid4(),
            model_entry_id=model_entry_id,
            dataset_id=dataset_id,
            job_type=job_type,
            resource_profile=resource_profile,
            retry_policy=retry_policy or {"maxRetries": 3, "backoffSeconds": 60},
            status="queued",
            submitted_by=submitted_by,
            submitted_at=datetime.utcnow(),
        )

        job = self.job_repo.create(job)

        # Submit to Kubernetes scheduler
        try:
            job_name = f"training-{job.id}"
            k8s_uid = self.scheduler.submit_job(
                job_name=job_name,
                image=resource_profile.get("image", "pytorch/pytorch:latest"),
                gpu_count=resource_profile.get("gpuCount", 1),
                gpu_type=resource_profile.get("gpuType", "nvidia-tesla-v100"),
                command=self._build_command(job_type, hyperparameters or {}),
                env_vars={
                    "MODEL_ENTRY_ID": str(model_entry_id),
                    "DATASET_ID": str(dataset_id),
                    "JOB_ID": str(job.id),
                    "HYPERPARAMETERS": str(hyperparameters or {}),
                },
            )
            job.scheduler_id = k8s_uid
            job.status = "running"
            job.started_at = datetime.utcnow()
            job = self.job_repo.update(job)
            logger.info(f"Training job {job.id} submitted to Kubernetes with UID {k8s_uid}")
        except Exception as e:
            logger.error(f"Failed to submit job {job.id} to scheduler: {e}")
            job.status = "failed"
            job = self.job_repo.update(job)
            raise

        return job

    def get_job(self, job_id: str) -> Optional[catalog_models.TrainingJob]:
        """Retrieve a training job by ID."""
        return self.job_repo.get(job_id)

    def list_jobs(
        self,
        model_entry_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[catalog_models.TrainingJob]:
        """List training jobs with optional filters."""
        return list(self.job_repo.list(model_entry_id=model_entry_id, status=status))

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or running training job."""
        job = self.job_repo.get(job_id)
        if not job:
            return False

        if job.status in ("succeeded", "failed", "cancelled"):
            return False

        try:
            if job.scheduler_id:
                job_name = f"training-{job.id}"
                self.scheduler.delete_job(job_name)
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
            self.job_repo.update(job)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    def record_metric(
        self,
        job_id: str,
        name: str,
        value: float,
        unit: Optional[str] = None,
    ) -> catalog_models.ExperimentMetric:
        """Record an experiment metric for a training job."""
        job = self.job_repo.get(job_id)
        if not job:
            raise ValueError(f"Training job {job_id} not found")

        metric = catalog_models.ExperimentMetric(
            id=uuid4(),
            training_job_id=job_id,
            name=name,
            value=value,
            unit=unit,
            recorded_at=datetime.utcnow(),
        )
        return self.metric_repo.create(metric)

    def get_job_metrics(self, job_id: str) -> list[catalog_models.ExperimentMetric]:
        """Retrieve all metrics for a training job."""
        return list(self.metric_repo.list_by_job(job_id))

    @staticmethod
    def _build_command(job_type: str, hyperparameters: dict) -> list[str]:
        """Build the command to run in the training container."""
        if job_type == "finetune":
            return [
                "python",
                "-m",
                "training.finetune",
                "--hyperparameters",
                str(hyperparameters),
            ]
        elif job_type == "distributed":
            return [
                "python",
                "-m",
                "training.distributed",
                "--hyperparameters",
                str(hyperparameters),
            ]
        else:
            raise ValueError(f"Unknown job type: {job_type}")

