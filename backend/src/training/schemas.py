"""Pydantic schemas for training API requests/responses."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TrainingJobRequest(BaseModel):
    """Request schema for submitting a training job."""

    modelId: str = Field(..., description="Model catalog entry ID")
    datasetId: str = Field(..., description="Dataset record ID")
    jobType: str = Field(..., pattern="^(finetune|distributed)$")
    hyperparameters: Optional[dict] = Field(default=None)
    resourceProfile: dict = Field(
        ...,
        description="GPU count, GPU type, max duration in minutes",
    )
    retryPolicy: Optional[dict] = Field(default=None)
    notifications: Optional[dict] = Field(default=None)


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

    class Config:
        from_attributes = True


class EnvelopeTrainingJob(BaseModel):
    """Standard API envelope for training job responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[TrainingJobResponse] = None

