"""Pydantic schemas for training API requests/responses."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TrainingJobRequest(BaseModel):
    """Request schema for submitting a training job."""

    modelId: Optional[str] = Field(None, description="Model catalog entry ID (required for finetune, optional for from_scratch/pretrain)")
    datasetId: str = Field(..., description="Dataset record ID")
    jobType: str = Field(..., pattern="^(finetune|from_scratch|pretrain|distributed)$", description="Training job type: finetune (requires modelId), from_scratch (requires architecture), pretrain (requires architecture), distributed (can combine with any type)")
    useGpu: bool = Field(default=True, description="Whether to use GPU resources (default: true). Set to false for CPU-only training suitable for development/testing")
    hyperparameters: Optional[dict] = Field(default=None, description="Training hyperparameters and architecture configuration (required for from_scratch/pretrain)")
    resourceProfile: dict = Field(
        ...,
        description="GPU count, GPU type, max duration in minutes (when useGpu=true) or CPU cores, memory, max duration (when useGpu=false)",
    )
    retryPolicy: Optional[dict] = Field(default=None)
    notifications: Optional[dict] = Field(default=None)
    apiBaseUrl: Optional[str] = Field(
        None,
        description="API base URL for training pod to record metrics. If not provided, uses server configuration. Leave empty to disable metric recording."
    )
    outputModelName: Optional[str] = Field(
        None,
        description="Name for the output model (optional, auto-generated if not provided). Model will be automatically registered when job succeeds."
    )
    outputModelVersion: Optional[str] = Field(
        None,
        description="Version for the output model (optional, auto-generated if not provided). Model will be automatically registered when job succeeds."
    )
    autoRegisterOutputModel: bool = Field(
        default=True,
        description="Whether to automatically register output model when job succeeds (default: True)"
    )


class TrainingJobResponse(BaseModel):
    """Response schema for training job operations."""

    id: str
    modelId: str
    datasetId: str
    jobType: str
    status: str
    submittedAt: datetime
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    experimentUrl: Optional[str] = None
    resourceProfile: Optional[dict] = None
    outputModelStorageUri: Optional[str] = None
    outputModelEntryId: Optional[str] = None

    class Config:
        from_attributes = True


class TrainingJobListResponse(BaseModel):
    """Response schema for training job list."""

    jobs: list[TrainingJobResponse]

    class Config:
        from_attributes = True


class EnvelopeTrainingJob(BaseModel):
    """Standard API envelope for training job responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[TrainingJobResponse] = None


class EnvelopeTrainingJobList(BaseModel):
    """Standard API envelope for training job list responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[TrainingJobListResponse] = None


class ResubmitTrainingJobRequest(BaseModel):
    """Request schema for resubmitting a training job with updated resources."""

    resourceProfile: dict = Field(
        ...,
        description="Updated resource profile (GPU/CPU configuration)",
    )
    useGpu: Optional[bool] = Field(
        None,
        description="Whether to use GPU (if None, inferred from resourceProfile)",
    )


class ExperimentMetricResponse(BaseModel):
    """Response schema for experiment metrics."""

    id: str
    trainingJobId: str
    name: str
    value: float
    unit: Optional[str] = None
    recordedAt: datetime

    class Config:
        from_attributes = True


class ExperimentResponse(BaseModel):
    """Response schema for experiment details."""

    jobId: str
    metrics: list[ExperimentMetricResponse]

    class Config:
        from_attributes = True


class EnvelopeExperiment(BaseModel):
    """Standard API envelope for experiment responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ExperimentResponse] = None


class RecordMetricRequest(BaseModel):
    """Request schema for recording a training metric."""

    name: str = Field(..., description="Metric name (e.g., 'loss', 'accuracy')")
    value: float = Field(..., description="Metric value")
    unit: Optional[str] = Field(None, description="Metric unit (e.g., 'percentage', 'seconds')")


class EnvelopeMetric(BaseModel):
    """Standard API envelope for metric recording responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ExperimentMetricResponse] = None


class RegisterOutputModelRequest(BaseModel):
    """Request schema for registering output model from training job."""

    modelName: str = Field(..., description="Name for the output model")
    modelVersion: str = Field(..., description="Version for the output model")
    storageUri: Optional[str] = Field(
        default=None,
        description="Storage URI where the trained model artifacts are stored (optional, auto-generated if not provided)"
    )
    ownerTeam: Optional[str] = Field(default="ml-platform", description="Owner team for the model")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata for the model")


class ExperimentRunResponse(BaseModel):
    """Response schema for experiment run."""

    id: str
    trainingJobId: str
    trackingSystem: str
    trackingRunId: str
    experimentName: str
    runName: Optional[str] = None
    parameters: Optional[dict] = None
    metrics: Optional[dict] = None
    artifactUris: Optional[list] = None
    status: str
    startTime: datetime
    endTime: Optional[datetime] = None
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True


class EnvelopeExperimentRun(BaseModel):
    """Standard API envelope for experiment run responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ExperimentRunResponse] = None


class CreateExperimentRunRequest(BaseModel):
    """Request schema for creating an experiment run."""

    experimentName: Optional[str] = Field(None, description="Experiment name (defaults to model name)")
    runName: Optional[str] = Field(None, description="Run name/tag")
    parameters: Optional[dict] = Field(None, description="Parameters to log")


class LogExperimentMetricsRequest(BaseModel):
    """Request schema for logging experiment metrics."""

    metrics: dict = Field(..., description="Dictionary of metric names to values")
    step: Optional[int] = Field(None, description="Optional step number for time-series metrics")


class SearchExperimentsRequest(BaseModel):
    """Request schema for searching experiments."""

    experimentName: Optional[str] = Field(None, description="Filter by experiment name")
    filterString: Optional[str] = Field(None, description="Filter expression (tool-specific syntax)")
    maxResults: int = Field(default=100, ge=1, le=1000, description="Maximum number of results")


class ExperimentSearchResponse(BaseModel):
    """Response schema for experiment search."""

    experiments: list[ExperimentRunResponse]
    total: int

    class Config:
        from_attributes = True


class EnvelopeExperimentSearch(BaseModel):
    """Standard API envelope for experiment search responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ExperimentSearchResponse] = None

