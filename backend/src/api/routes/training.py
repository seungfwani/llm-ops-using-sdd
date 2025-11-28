"""Training job API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_session
from training import schemas
from training.services import TrainingJobService

router = APIRouter(prefix="/llm-ops/v1/training", tags=["training"])


def get_training_service(session: Session = Depends(get_session)) -> TrainingJobService:
    """Dependency to get training job service."""
    return TrainingJobService(session)


@router.post("/jobs", response_model=schemas.EnvelopeTrainingJob)
def submit_training_job(
    request: schemas.TrainingJobRequest,
    service: TrainingJobService = Depends(get_training_service),
    user_id: str = "system",  # TODO: Extract from auth middleware
) -> schemas.EnvelopeTrainingJob:
    """Submit a fine-tuning or distributed training job."""
    try:
        job = service.submit_job(
            model_entry_id=request.modelId,
            dataset_id=request.datasetId,
            job_type=request.jobType,
            resource_profile=request.resourceProfile,
            hyperparameters=request.hyperparameters,
            retry_policy=request.retryPolicy,
            submitted_by=user_id,
        )
        return schemas.EnvelopeTrainingJob(
            status="success",
            message="Training job submitted successfully",
            data=schemas.TrainingJobResponse(
                id=str(job.id),
                modelId=str(job.model_entry_id),
                datasetId=str(job.dataset_id),
                jobType=job.job_type,
                status=job.status,
                submittedAt=job.submitted_at,
                startedAt=job.started_at,
                completedAt=job.completed_at,
                experimentUrl=f"/experiments/{job.id}",
            ),
        )
    except ValueError as e:
        return schemas.EnvelopeTrainingJob(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        return schemas.EnvelopeTrainingJob(
            status="fail",
            message=f"Failed to submit training job: {str(e)}",
            data=None,
        )


@router.get("/jobs/{jobId}", response_model=schemas.EnvelopeTrainingJob)
def get_training_job(
    jobId: str,
    service: TrainingJobService = Depends(get_training_service),
) -> schemas.EnvelopeTrainingJob:
    """Retrieve training job status and experiment metadata."""
    job = service.get_job(jobId)
    if not job:
        return schemas.EnvelopeTrainingJob(
            status="fail",
            message=f"Training job {jobId} not found",
            data=None,
        )

    return schemas.EnvelopeTrainingJob(
        status="success",
        message="",
        data=schemas.TrainingJobResponse(
            id=str(job.id),
            modelId=str(job.model_entry_id),
            datasetId=str(job.dataset_id),
            jobType=job.job_type,
            status=job.status,
            submittedAt=job.submitted_at,
            startedAt=job.started_at,
            completedAt=job.completed_at,
            experimentUrl=f"/experiments/{job.id}",
        ),
    )


@router.delete("/jobs/{jobId}", response_model=schemas.EnvelopeTrainingJob)
def cancel_training_job(
    jobId: str,
    service: TrainingJobService = Depends(get_training_service),
) -> schemas.EnvelopeTrainingJob:
    """Cancel a queued or running job."""
    success = service.cancel_job(jobId)
    if not success:
        return schemas.EnvelopeTrainingJob(
            status="fail",
            message=f"Could not cancel training job {jobId}",
            data=None,
        )

    job = service.get_job(jobId)
    return schemas.EnvelopeTrainingJob(
        status="success",
        message="Training job cancelled",
        data=schemas.TrainingJobResponse(
            id=str(job.id),
            modelId=str(job.model_entry_id),
            datasetId=str(job.dataset_id),
            jobType=job.job_type,
            status=job.status,
            submittedAt=job.submitted_at,
            startedAt=job.started_at,
            completedAt=job.completed_at,
            experimentUrl=f"/experiments/{job.id}",
        ) if job else None,
    )

