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

