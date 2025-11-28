"""Integration tests for training job failure and retry scenarios."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from backend.src.core.database import get_session
from backend.src.training.services import TrainingJobService
from backend.src.catalog import models as catalog_models
from backend.src.training.repositories import TrainingJobRepository


@pytest.fixture
def db_session():
    """Provide a test database session."""
    # TODO: Use test database fixture
    session = next(get_session())
    yield session
    session.rollback()


@pytest.fixture
def training_service(db_session: Session):
    """Provide a training service instance."""
    return TrainingJobService(db_session)


@pytest.fixture
def mock_model_entry(db_session: Session):
    """Create a mock approved model entry."""
    from uuid import uuid4
    entry = catalog_models.ModelCatalogEntry(
        id=uuid4(),
        name="test-model",
        version="1.0.0",
        type="base",
        status="approved",
        owner_team="test-team",
        metadata={"purpose": "test"},
    )
    db_session.add(entry)
    db_session.commit()
    return entry


@pytest.fixture
def mock_dataset(db_session: Session):
    """Create a mock approved dataset."""
    from uuid import uuid4
    from datetime import datetime
    dataset = catalog_models.DatasetRecord(
        id=uuid4(),
        name="test-dataset",
        version="1.0.0",
        storage_uri="s3://test/dataset",
        pii_scan_status="clean",
        quality_score=95,
        approved_at=datetime.utcnow(),
        owner_team="test-team",
    )
    db_session.add(dataset)
    db_session.commit()
    return dataset


def test_job_submission_with_invalid_model(training_service: TrainingJobService):
    """Test that submitting a job with invalid model fails gracefully."""
    with pytest.raises(ValueError, match="not found"):
        training_service.submit_job(
            model_entry_id="00000000-0000-0000-0000-000000000000",
            dataset_id="00000000-0000-0000-0000-000000000001",
            job_type="finetune",
            resource_profile={"gpuCount": 1, "gpuType": "v100", "maxDuration": 60},
        )


def test_job_submission_with_unapproved_model(
    training_service: TrainingJobService,
    db_session: Session,
    mock_dataset: catalog_models.DatasetRecord,
):
    """Test that submitting a job with unapproved model fails."""
    from uuid import uuid4
    unapproved_model = catalog_models.ModelCatalogEntry(
        id=uuid4(),
        name="unapproved-model",
        version="1.0.0",
        type="base",
        status="draft",
        owner_team="test-team",
        metadata={},
    )
    db_session.add(unapproved_model)
    db_session.commit()

    with pytest.raises(ValueError, match="not approved"):
        training_service.submit_job(
            model_entry_id=str(unapproved_model.id),
            dataset_id=str(mock_dataset.id),
            job_type="finetune",
            resource_profile={"gpuCount": 1, "gpuType": "v100", "maxDuration": 60},
        )


@patch("backend.src.training.services.KubernetesScheduler")
def test_job_retry_on_scheduler_failure(
    mock_scheduler_class,
    training_service: TrainingJobService,
    mock_model_entry: catalog_models.ModelCatalogEntry,
    mock_dataset: catalog_models.DatasetRecord,
):
    """Test that job status is updated when scheduler fails."""
    mock_scheduler = Mock()
    mock_scheduler.submit_job.side_effect = Exception("Kubernetes API error")
    mock_scheduler_class.return_value = mock_scheduler

    with pytest.raises(Exception):
        training_service.submit_job(
            model_entry_id=str(mock_model_entry.id),
            dataset_id=str(mock_dataset.id),
            job_type="finetune",
            resource_profile={"gpuCount": 1, "gpuType": "v100", "maxDuration": 60},
        )

    # Verify job was created but marked as failed
    jobs = training_service.list_jobs(model_entry_id=str(mock_model_entry.id))
    assert len(jobs) == 1
    assert jobs[0].status == "failed"


def test_job_cancellation(
    training_service: TrainingJobService,
    db_session: Session,
    mock_model_entry: catalog_models.ModelCatalogEntry,
    mock_dataset: catalog_models.DatasetRecord,
):
    """Test that a queued job can be cancelled."""
    from uuid import uuid4
    from datetime import datetime

    job = catalog_models.TrainingJob(
        id=uuid4(),
        model_entry_id=mock_model_entry.id,
        dataset_id=mock_dataset.id,
        job_type="finetune",
        resource_profile={"gpuCount": 1},
        status="queued",
        submitted_by="test-user",
        submitted_at=datetime.utcnow(),
    )
    db_session.add(job)
    db_session.commit()

    success = training_service.cancel_job(str(job.id))
    assert success is True

    updated_job = training_service.get_job(str(job.id))
    assert updated_job.status == "cancelled"
    assert updated_job.completed_at is not None


def test_job_cancellation_fails_for_completed_job(
    training_service: TrainingJobService,
    db_session: Session,
    mock_model_entry: catalog_models.ModelCatalogEntry,
    mock_dataset: catalog_models.DatasetRecord,
):
    """Test that a completed job cannot be cancelled."""
    from uuid import uuid4
    from datetime import datetime

    job = catalog_models.TrainingJob(
        id=uuid4(),
        model_entry_id=mock_model_entry.id,
        dataset_id=mock_dataset.id,
        job_type="finetune",
        resource_profile={"gpuCount": 1},
        status="succeeded",
        submitted_by="test-user",
        submitted_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add(job)
    db_session.commit()

    success = training_service.cancel_job(str(job.id))
    assert success is False

