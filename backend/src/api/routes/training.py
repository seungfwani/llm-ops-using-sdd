"""Training job API routes."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_session
from training import schemas
from training.services import TrainingJobService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-ops/v1/training", tags=["training"])


def get_training_service(session: Session = Depends(get_session)) -> TrainingJobService:
    """Dependency to get training job service."""
    return TrainingJobService(session)


@router.get("/jobs", response_model=schemas.EnvelopeTrainingJobList)
def list_training_jobs(
    modelId: Optional[str] = Query(None, alias="modelId", description="Filter by model ID"),
    status: Optional[str] = Query(None, description="Filter by status (queued, running, succeeded, failed, cancelled)"),
    service: TrainingJobService = Depends(get_training_service),
) -> schemas.EnvelopeTrainingJobList:
    """List training jobs with optional filters."""
    try:
        jobs = service.list_jobs(model_entry_id=modelId, status=status)
        job_responses = [
            schemas.TrainingJobResponse(
                id=str(job.id),
                modelId=str(job.model_entry_id),
                datasetId=str(job.dataset_id),
                jobType=job.job_type,
                status=job.status,
                submittedAt=job.submitted_at,
                startedAt=job.started_at,
                completedAt=job.completed_at,
                experimentUrl=f"/experiments/{job.id}",
                resourceProfile=job.resource_profile,
                outputModelStorageUri=job.output_model_storage_uri,
                outputModelEntryId=str(job.output_model_entry_id) if job.output_model_entry_id else None,
            )
            for job in jobs
        ]
        return schemas.EnvelopeTrainingJobList(
            status="success",
            message="",
            data=schemas.TrainingJobListResponse(jobs=job_responses),
        )
    except Exception as e:
        return schemas.EnvelopeTrainingJobList(
            status="fail",
            message=f"Failed to list training jobs: {str(e)}",
            data=None,
        )


@router.post("/jobs", response_model=schemas.EnvelopeTrainingJob)
def submit_training_job(
    request: schemas.TrainingJobRequest,
    service: TrainingJobService = Depends(get_training_service),
    user_id: str = "system",  # TODO: Extract from auth middleware
) -> schemas.EnvelopeTrainingJob:
    """Submit a fine-tuning or distributed training job."""
    try:
        # Job type validation
        if request.jobType == "finetune":
            # Fine-tuning requires base model
            if not request.modelId:
                return schemas.EnvelopeTrainingJob(
                    status="fail",
                    message="Fine-tuning job requires a base model (modelId must be provided)",
                    data=None,
                )
        elif request.jobType in ("from_scratch", "pretrain"):
            # From-scratch and pre-training require architecture configuration
            if not request.hyperparameters or "architecture" not in request.hyperparameters:
                return schemas.EnvelopeTrainingJob(
                    status="fail",
                    message=f"{request.jobType} job requires architecture configuration in hyperparameters",
                    data=None,
                )
        elif request.jobType == "distributed":
            # Distributed can combine with any type, but requires resource profile with multiple GPUs/nodes (when useGpu=true)
            if request.useGpu:
                gpu_count = request.resourceProfile.get("gpuCount", request.resourceProfile.get("gpu_count", 1))
                if gpu_count < 2:
                    return schemas.EnvelopeTrainingJob(
                        status="fail",
                        message="Distributed training requires at least 2 GPUs in resource profile",
                        data=None,
                    )
        
        job = service.submit_job(
            model_entry_id=request.modelId,
            dataset_id=request.datasetId,
            job_type=request.jobType,
            resource_profile=request.resourceProfile,
            hyperparameters=request.hyperparameters,
            retry_policy=request.retryPolicy,
            submitted_by=user_id,
            use_gpu=request.useGpu,
            api_base_url=request.apiBaseUrl,
            output_model_name=request.outputModelName,
            output_model_version=request.outputModelVersion,
            auto_register_output_model=request.autoRegisterOutputModel,
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
                resourceProfile=job.resource_profile,
                outputModelStorageUri=job.output_model_storage_uri,
                outputModelEntryId=str(job.output_model_entry_id) if job.output_model_entry_id else None,
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
            resourceProfile=job.resource_profile,
            outputModelStorageUri=job.output_model_storage_uri,
            outputModelEntryId=str(job.output_model_entry_id) if job.output_model_entry_id else None,
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


@router.post("/jobs/{jobId}/resubmit", response_model=schemas.EnvelopeTrainingJob)
def resubmit_training_job(
    jobId: str,
    request: schemas.ResubmitTrainingJobRequest,
    service: TrainingJobService = Depends(get_training_service),
    user_id: str = "system",  # TODO: Extract from auth middleware
) -> schemas.EnvelopeTrainingJob:
    """Resubmit a training job with updated resource profile."""
    try:
        job = service.resubmit_job(
            job_id=jobId,
            resource_profile=request.resourceProfile,
            use_gpu=request.useGpu,
            submitted_by=user_id,
        )
        return schemas.EnvelopeTrainingJob(
            status="success",
            message="Training job resubmitted successfully with updated resources",
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
                resourceProfile=job.resource_profile,
                outputModelStorageUri=job.output_model_storage_uri,
                outputModelEntryId=str(job.output_model_entry_id) if job.output_model_entry_id else None,
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
            message=f"Failed to resubmit training job: {str(e)}",
            data=None,
        )


@router.get("/jobs/{jobId}/pods")
def get_training_job_pods(
    jobId: str,
    service: TrainingJobService = Depends(get_training_service),
) -> dict:
    """Get pod status and events for a training job (for debugging pending pods)."""
    job = service.get_job(jobId)
    if not job:
        return {
            "status": "fail",
            "message": f"Training job {jobId} not found",
            "data": None,
        }
    
    if not job.scheduler_id:
        return {
            "status": "fail",
            "message": "Job has not been submitted to Kubernetes yet",
            "data": None,
        }
    
    job_name = f"training-{job.id}"
    pod_status = service.scheduler.get_pod_status(job_name)
    
    if pod_status is None:
        return {
            "status": "fail",
            "message": "Could not retrieve pod status",
            "data": None,
        }
    
    return {
        "status": "success",
        "message": "",
        "data": pod_status,
    }


@router.get("/experiments/{jobId}", response_model=schemas.EnvelopeExperiment)
def get_experiment(
    jobId: str,
    service: TrainingJobService = Depends(get_training_service),
) -> schemas.EnvelopeExperiment:
    """Get experiment metrics for a training job."""
    try:
        job = service.get_job(jobId)
        if not job:
            return schemas.EnvelopeExperiment(
                status="fail",
                message=f"Training job {jobId} not found",
                data=None,
            )
        
        metrics = service.get_job_metrics(jobId)
        metric_responses = [
            schemas.ExperimentMetricResponse(
                id=str(metric.id),
                trainingJobId=str(metric.training_job_id),
                name=metric.name,
                value=metric.value,
                unit=metric.unit,
                recordedAt=metric.recorded_at,
            )
            for metric in metrics
        ]
        
        return schemas.EnvelopeExperiment(
            status="success",
            message="",
            data=schemas.ExperimentResponse(
                jobId=str(job.id),
                metrics=metric_responses,
            ),
        )
    except Exception as e:
        return schemas.EnvelopeExperiment(
            status="fail",
            message=f"Failed to retrieve experiment: {str(e)}",
            data=None,
        )


@router.post("/jobs/{jobId}/metrics", response_model=schemas.EnvelopeMetric)
def record_metric(
    jobId: str,
    request: schemas.RecordMetricRequest,
    service: TrainingJobService = Depends(get_training_service),
) -> schemas.EnvelopeMetric:
    """Record a metric for a training job."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Recording metric: job_id={jobId}, name={request.name}, value={request.value}, unit={request.unit}")
        metric = service.record_metric(
            job_id=jobId,
            name=request.name,
            value=request.value,
            unit=request.unit,
        )
        logger.info(f"Successfully recorded metric {request.name} for job {jobId}")
        return schemas.EnvelopeMetric(
            status="success",
            message="Metric recorded successfully",
            data=schemas.ExperimentMetricResponse(
                id=str(metric.id),
                trainingJobId=str(metric.training_job_id),
                name=metric.name,
                value=metric.value,
                unit=metric.unit,
                recordedAt=metric.recorded_at,
            ),
        )
    except ValueError as e:
        logger.warning(f"Failed to record metric for job {jobId}: {e}")
        return schemas.EnvelopeMetric(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        logger.error(f"Unexpected error recording metric for job {jobId}: {e}", exc_info=True)
        return schemas.EnvelopeMetric(
            status="fail",
            message=f"Failed to record metric: {str(e)}",
            data=None,
        )


@router.post("/jobs/{jobId}/register-model", response_model=schemas.EnvelopeTrainingJob)
def register_output_model(
    jobId: str,
    request: schemas.RegisterOutputModelRequest,
    service: TrainingJobService = Depends(get_training_service),
) -> schemas.EnvelopeTrainingJob:
    """Register the output model from a completed training job to the catalog."""
    try:
        model_entry = service.register_output_model(
            job_id=jobId,
            model_name=request.modelName,
            model_version=request.modelVersion,
            storage_uri=request.storageUri if request.storageUri else None,
            owner_team=request.ownerTeam or "ml-platform",
            metadata=request.metadata,
        )
        
        # Get updated job
        job = service.get_job(jobId)
        if not job:
            raise HTTPException(status_code=404, detail=f"Training job {jobId} not found")
        
        return schemas.EnvelopeTrainingJob(
            status="success",
            message=f"Model registered successfully: {model_entry.id}",
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
                resourceProfile=job.resource_profile,
                outputModelStorageUri=job.output_model_storage_uri,
                outputModelEntryId=str(job.output_model_entry_id) if job.output_model_entry_id else None,
            ),
        )
    except ValueError as e:
        logger.warning(f"Failed to register model for job {jobId}: {e}")
        return schemas.EnvelopeTrainingJob(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        logger.error(f"Unexpected error registering model for job {jobId}: {e}", exc_info=True)
        return schemas.EnvelopeTrainingJob(
            status="fail",
            message=f"Failed to register model: {str(e)}",
            data=None,
        )

