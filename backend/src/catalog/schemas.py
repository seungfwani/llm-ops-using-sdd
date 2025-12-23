from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any

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
    model_family: str = Field(
        ...,
        description="Model family from training-serving-spec.md whitelist (llama, mistral, gemma, bert, etc.) - Required for TrainJobSpec/DeploymentSpec validation"
    )


class ModelCatalogResponse(BaseModel):
    id: str
    name: str
    version: str
    type: str
    status: str
    owner_team: str
    metadata: dict
    storage_uri: Optional[str] = None
    model_family: str

    class Config:
        from_attributes = True


class DatasetCreate(BaseModel):
    name: str
    version: str
    storage_uri: str
    owner_team: str
    change_log: Optional[str] = None
    quality_score: Optional[int] = None
    type: str = Field(
        ...,
        description="Dataset type from training-serving-spec.md (pretrain_corpus, sft_pair, rag_qa, rlhf_pair) - Required for TrainJobSpec validation"
    )


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
    type: str

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


class DatasetVersionCreate(BaseModel):
    """Request schema for creating a dataset version."""
    
    version_tag: Optional[str] = Field(None, description="Human-readable version tag")
    parent_version_id: Optional[str] = Field(None, description="Parent version ID for lineage")


class DatasetVersionResponse(BaseModel):
    """Response schema for dataset version."""
    
    id: str
    dataset_record_id: str
    versioning_system: str
    version_id: str
    parent_version_id: Optional[str] = None
    version_tag: Optional[str] = None
    checksum: str
    storage_uri: str
    diff_summary: Optional[Dict[str, Any]] = None
    file_count: int
    total_size_bytes: int
    compression_ratio: Optional[float] = None
    created_at: datetime
    created_by: str
    
    class Config:
        from_attributes = True


class DatasetVersionDiffResponse(BaseModel):
    """Response schema for dataset version diff."""
    
    added_files: List[str]
    removed_files: List[str]
    modified_files: List[str]
    added_rows: int
    removed_rows: int
    schema_changes: Dict[str, Any]


class EnvelopeDatasetVersion(BaseModel):
    """Standard API envelope for dataset version responses."""
    
    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[DatasetVersionResponse] = None


class EnvelopeDatasetVersionList(BaseModel):
    """Standard API envelope for dataset version list responses."""
    
    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[List[DatasetVersionResponse]] = None


class EnvelopeDatasetVersionDiff(BaseModel):
    """Standard API envelope for dataset version diff responses."""
    
    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[DatasetVersionDiffResponse] = None


class HuggingFaceImportRequest(BaseModel):
    """Request schema for importing a model from Hugging Face."""

    hf_model_id: str = Field(..., description="Hugging Face model ID (e.g., 'microsoft/DialoGPT-small')")
    name: Optional[str] = Field(None, description="Model name (defaults to last part of hf_model_id)")
    version: str = Field(default="1.0.0", description="Model version")
    model_type: str = Field(default="base", pattern="^(base|fine-tuned|external)$", description="Model type")
    owner_team: str = Field(default="ml-platform", description="Owner team name")
    hf_token: Optional[str] = Field(None, description="Hugging Face API token (for gated models)")
    model_family: str = Field(..., description="Model family from training-serving-spec.md whitelist (llama, mistral, gemma, bert, etc.) - Required")


class ImportModelRequest(BaseModel):
    """Request schema for importing a model from an external registry."""

    registry_type: str = Field(
        ...,
        description="Registry type (e.g., 'huggingface')",
        pattern="^(huggingface|modelscope)$",
    )
    registry_model_id: str = Field(
        ...,
        description="Model identifier in registry (e.g., 'microsoft/DialoGPT-medium')",
    )
    version: Optional[str] = Field(
        default=None,
        description="Optional specific version/tag in registry",
    )
    name: Optional[str] = Field(
        default=None,
        description="Optional platform catalog name (defaults to last part of registry_model_id)",
    )
    model_version: str = Field(
        default="1.0.0",
        description="Platform catalog version for the imported model",
    )
    model_type: str = Field(
        default="base",
        pattern="^(base|fine-tuned|external)$",
        description="Platform catalog model type",
    )
    owner_team: str = Field(
        default="ml-platform",
        description="Owner team name for the imported model",
    )
    model_family: Optional[str] = Field(
        default=None,
        description="Model family (llama, mistral, gemma, bert, etc.). If not provided, will be inferred from model metadata.",
    )


class ExportModelRequest(BaseModel):
    """Request schema for exporting a catalog model to a registry."""

    registry_type: str = Field(
        ...,
        description="Registry type (e.g., 'huggingface')",
        pattern="^(huggingface|modelscope)$",
    )
    registry_model_id: Optional[str] = Field(
        default=None,
        description="Target model ID in registry (defaults to derived from catalog name if omitted)",
    )
    repository_name: Optional[str] = Field(
        default=None,
        description="Optional repository name hint for registry (informational)",
    )
    private: bool = Field(
        default=False,
        description="Whether to create a private repository in registry (if supported)",
    )
    version_tag: Optional[str] = Field(
        default=None,
        description="Optional version/tag name to apply in registry",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata payload (model card, license, tags, etc.)",
    )


class RegistryModelResponse(BaseModel):
    """Response schema for registry model links."""

    id: str
    model_catalog_id: str
    registry_type: str
    registry_model_id: str
    registry_repo_url: str
    registry_version: Optional[str] = None
    imported: bool
    sync_status: str

    class Config:
        from_attributes = True


class EnvelopeRegistryModel(BaseModel):
    """Envelope for single registry model link."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[RegistryModelResponse] = None


class PromptTemplateCreate(BaseModel):
    name: str
    version: str
    language: Optional[str] = None
    content: str
    context_tags: Optional[list[str]] = None
    status: str = Field(default="draft")

class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    language: Optional[str] = None
    content: Optional[str] = None
    context_tags: Optional[list[str]] = None
    status: Optional[str] = None

from pydantic import field_serializer

from uuid import UUID
from pydantic import field_serializer

class PromptTemplateResponse(BaseModel):
    id: UUID
    name: str
    version: str
    language: Optional[str] = None
    content: str
    context_tags: Optional[list[str]] = None
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer('id')
    def uuid_to_str(self, v: UUID, _info):
        return str(v)

    class Config:
        from_attributes = True

class EnvelopePromptTemplate(BaseModel):
    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[PromptTemplateResponse] = None

class EnvelopePromptTemplateList(BaseModel):
    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[list[PromptTemplateResponse]] = None

class EnvelopeRegistryModelList(BaseModel):
    """Envelope for list of registry model links."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[List[RegistryModelResponse]] = None

