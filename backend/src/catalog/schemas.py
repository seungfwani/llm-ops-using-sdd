from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ModelCatalogCreate(BaseModel):
    name: str
    version: str
    type: str = Field(pattern="^(base|fine-tuned|external)$")
    owner_team: str
    metadata: dict
    lineage_dataset_ids: List[str] = []
    status: str = "draft"
    evaluation_summary: Optional[dict] = None


class ModelCatalogResponse(BaseModel):
    id: str
    name: str
    version: str
    type: str
    status: str
    owner_team: str
    metadata: dict
    storage_uri: Optional[str] = None

    class Config:
        from_attributes = True


class DatasetCreate(BaseModel):
    name: str
    version: str
    storage_uri: str
    owner_team: str
    change_log: Optional[str] = None
    quality_score: Optional[int] = None


class DatasetResponse(BaseModel):
    id: str
    name: str
    version: str
    storage_uri: str
    owner_team: str
    pii_scan_status: str
    quality_score: Optional[int] = None
    change_log: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EnvelopeModelCatalog(BaseModel):
    """Standard API envelope for model catalog responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ModelCatalogResponse] = None


class EnvelopeModelCatalogList(BaseModel):
    """Standard API envelope for model catalog list responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[List[ModelCatalogResponse]] = None


class EnvelopeDataset(BaseModel):
    """Standard API envelope for dataset responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[DatasetResponse] = None


class EnvelopeDatasetList(BaseModel):
    """Standard API envelope for dataset list responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[List[DatasetResponse]] = None


class HuggingFaceImportRequest(BaseModel):
    """Request schema for importing a model from Hugging Face."""

    hf_model_id: str = Field(..., description="Hugging Face model ID (e.g., 'microsoft/DialoGPT-small')")
    name: Optional[str] = Field(None, description="Model name (defaults to last part of hf_model_id)")
    version: str = Field(default="1.0.0", description="Model version")
    model_type: str = Field(default="base", pattern="^(base|fine-tuned|external)$", description="Model type")
    owner_team: str = Field(default="ml-platform", description="Owner team name")
    hf_token: Optional[str] = Field(None, description="Hugging Face API token (for gated models)")

