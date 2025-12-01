"""Repositories for training job and experiment metric entities."""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from catalog import models as catalog_models


class TrainingJobRepository:
    """Repository for TrainingJob entities."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, job: catalog_models.TrainingJob) -> catalog_models.TrainingJob:
        """Persist a new training job."""
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get(self, job_id: str | UUID) -> Optional[catalog_models.TrainingJob]:
        """Retrieve a training job by ID."""
        try:
            uuid_id = UUID(job_id) if isinstance(job_id, str) else job_id
        except (ValueError, TypeError):
            return None
        return self.session.get(catalog_models.TrainingJob, uuid_id)

    def list(
        self,
        model_entry_id: Optional[str | UUID] = None,
        status: Optional[str] = None,
    ) -> Sequence[catalog_models.TrainingJob]:
        """List training jobs with optional filters."""
        query = self.session.query(catalog_models.TrainingJob)
        if model_entry_id:
            query = query.filter(catalog_models.TrainingJob.model_entry_id == model_entry_id)
        if status:
            query = query.filter(catalog_models.TrainingJob.status == status)
        return query.order_by(catalog_models.TrainingJob.submitted_at.desc()).all()

    def update(self, job: catalog_models.TrainingJob) -> catalog_models.TrainingJob:
        """Update an existing training job."""
        self.session.commit()
        self.session.refresh(job)
        return job

    def delete(self, job: catalog_models.TrainingJob) -> None:
        """Delete a training job."""
        self.session.delete(job)
        self.session.commit()


class ExperimentMetricRepository:
    """Repository for ExperimentMetric entities."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, metric: catalog_models.ExperimentMetric) -> catalog_models.ExperimentMetric:
        """Persist a new experiment metric."""
        self.session.add(metric)
        self.session.commit()
        self.session.refresh(metric)
        return metric

    def list_by_job(
        self, job_id: str | UUID
    ) -> Sequence[catalog_models.ExperimentMetric]:
        """List all metrics for a training job."""
        return (
            self.session.query(catalog_models.ExperimentMetric)
            .filter(catalog_models.ExperimentMetric.training_job_id == job_id)
            .order_by(catalog_models.ExperimentMetric.recorded_at.asc())
            .all()
        )

