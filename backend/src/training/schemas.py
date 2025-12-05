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


# TrainJobSpec schema based on training-serving-spec.md
class DatasetRef(BaseModel):
    """Dataset reference schema."""

    name: str = Field(..., description="Dataset name")
    version: str = Field(..., description="Dataset version")
    type: str = Field(..., description="Dataset type: pretrain_corpus, sft_pair, rag_qa, rlhf_pair")
    storage_uri: str = Field(..., description="Storage URI for dataset")


class Hyperparams(BaseModel):
    """Training hyperparameters schema."""

    lr: float = Field(..., description="Learning rate", gt=0.0)
    batch_size: int = Field(..., description="Batch size", gt=0)
    num_epochs: int = Field(..., description="Number of epochs", gt=0)
    max_seq_len: int = Field(..., description="Maximum sequence length", gt=0)
    precision: str = Field(..., pattern="^(fp16|bf16)$", description="Precision: fp16 or bf16")


class Resources(BaseModel):
    """Resource requirements schema."""

    gpus: int = Field(default=0, ge=0, description="Number of GPUs")
    gpu_type: Optional[str] = Field(None, description="GPU type (e.g., 'A100', 'V100')")
    nodes: int = Field(default=1, ge=1, description="Number of nodes")


class OutputSpec(BaseModel):
    """Output specification schema."""

    artifact_name: str = Field(..., description="Output artifact name")
    save_format: str = Field(..., pattern="^(hf|safetensors)$", description="Save format: hf or safetensors")


class TrainJobSpec(BaseModel):
    """
    Training job specification schema based on training-serving-spec.md.
    
    Enforces standardized structure for all training jobs:
    - job_type: PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING
    - model_family: Whitelist validation (llama, mistral, gemma, bert, etc.)
    - base_model_ref: Required for SFT/RAG_TUNING/RLHF, null for PRETRAIN
    - dataset_ref: Must include name, version, type, storage_uri
    - hyperparams: lr, batch_size, num_epochs, max_seq_len, precision
    - method: full, lora, qlora (method constraints per job_type)
    - resources: gpus, gpu_type, nodes
    - output: artifact_name, save_format
    """

    job_type: str = Field(
        ...,
        pattern="^(PRETRAIN|SFT|RAG_TUNING|RLHF|EMBEDDING)$",
        description="Job type: PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING"
    )
    model_family: str = Field(..., description="Model family (llama, mistral, gemma, bert, etc.)")
    base_model_ref: Optional[str] = Field(
        None,
        description="Base model reference (required for SFT/RAG_TUNING/RLHF, null for PRETRAIN)"
    )
    dataset_ref: DatasetRef = Field(..., description="Dataset reference")
    hyperparams: Hyperparams = Field(..., description="Training hyperparameters")
    method: str = Field(
        ...,
        pattern="^(full|lora|qlora)$",
        description="Training method: full, lora, qlora"
    )
    resources: Resources = Field(..., description="Resource requirements")
    output: OutputSpec = Field(..., description="Output specification")
    use_gpu: bool = Field(default=True, description="Whether to use GPU resources (for CPU fallback)")

    class Config:
        json_schema_extra = {
            "example": {
                "job_type": "SFT",
                "model_family": "llama",
                "base_model_ref": "llama-3-8b-pretrain-v1",
                "dataset_ref": {
                    "name": "enterprise-instruction",
                    "version": "v1",
                    "type": "sft_pair",
                    "storage_uri": "s3://llm-datasets/enterprise-instruction/v1"
                },
                "hyperparams": {
                    "lr": 0.0001,
                    "batch_size": 4,
                    "num_epochs": 3,
                    "max_seq_len": 4096,
                    "precision": "bf16"
                },
                "method": "lora",
                "resources": {
                    "gpus": 2,
                    "gpu_type": "A100",
                    "nodes": 1
                },
                "output": {
                    "artifact_name": "llama-3-8b-sft-v1",
                    "save_format": "hf"
                },
                "use_gpu": True
            }
        }

