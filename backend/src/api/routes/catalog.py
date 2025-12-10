from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query, BackgroundTasks
from typing import List, Optional

from catalog.schemas import (
    DatasetCreate,
    DatasetResponse,
    EnvelopeDataset,
    EnvelopeDatasetList,
    EnvelopeModelCatalog,
    EnvelopeModelCatalogList,
    EnvelopeRegistryModel,
    EnvelopeRegistryModelList,
    HuggingFaceImportRequest,
    ImportModelRequest,
    ExportModelRequest,
    ModelCatalogCreate,
    ModelCatalogResponse,
    RegistryModelResponse,
    DatasetVersionCreate,
    DatasetVersionResponse,
    EnvelopeDatasetVersion,
    EnvelopeDatasetVersionList,
    DatasetVersionDiffResponse,
    EnvelopeDatasetVersionDiff,
)
from pydantic import BaseModel
from catalog.services import CatalogService, DatasetService
from services.model_registry_service import ModelRegistryService
from services.data_versioning_service import DataVersioningService
from core.database import get_session
from integrations.error_handler import IntegrationError, ToolUnavailableError
from uuid import UUID

router = APIRouter(prefix="/llm-ops/v1/catalog", tags=["catalog"])
logger = logging.getLogger(__name__)


@router.get("/models", response_model=EnvelopeModelCatalogList)
def list_models(
    status: str | None = Query(
        None,
        description="Optional status filter (e.g., approved, draft, pending_review)",
    ),
    session=Depends(get_session),
) -> EnvelopeModelCatalogList:
    service = CatalogService(session)
    entries = service.list_entries(status=status)
    return EnvelopeModelCatalogList(
        status="success",
        message="",
        data=[
            ModelCatalogResponse(
                id=str(entry.id),
                name=entry.name,
                version=entry.version,
                type=entry.type,
                status=entry.status,
                owner_team=entry.owner_team,
                metadata=entry.model_metadata,
                storage_uri=entry.storage_uri,
                model_family=entry.model_family,
            )
            for entry in entries
        ],
    )


@router.get("/models/{model_id}", response_model=EnvelopeModelCatalog)
def get_model(model_id: str, session=Depends(get_session)) -> EnvelopeModelCatalog:
    service = CatalogService(session)
    entry = service.get_entry(model_id)
    if not entry:
        return EnvelopeModelCatalog(
            status="fail",
            message=f"Model {model_id} not found",
            data=None,
        )
    return EnvelopeModelCatalog(
        status="success",
        message="",
        data=ModelCatalogResponse(
            id=str(entry.id),
            name=entry.name,
            version=entry.version,
            type=entry.type,
            status=entry.status,
            owner_team=entry.owner_team,
            metadata=entry.model_metadata,
            storage_uri=entry.storage_uri,
            model_family=entry.model_family,
        ),
    )


@router.post("/models", response_model=EnvelopeModelCatalog, status_code=201)
def create_model(
    payload: ModelCatalogCreate, session=Depends(get_session)
) -> EnvelopeModelCatalog:
    service = CatalogService(session)
    try:
        entry = service.create_entry(payload.dict())
        return EnvelopeModelCatalog(
            status="success",
            message="Model created successfully",
            data=ModelCatalogResponse(
                id=str(entry.id),
                name=entry.name,
                version=entry.version,
                type=entry.type,
                status=entry.status,
                owner_team=entry.owner_team,
                metadata=entry.model_metadata,
                storage_uri=entry.storage_uri,
                model_family=entry.model_family,
            ),
        )
    except ValueError as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=str(exc),
            data=None,
        )


@router.patch("/models/{model_id}/status", response_model=EnvelopeModelCatalog)
def update_model_status(
    model_id: str, status: str = Query(...), session=Depends(get_session)
) -> EnvelopeModelCatalog:
    service = CatalogService(session)
    try:
        entry = service.update_status(model_id, status)
        return EnvelopeModelCatalog(
            status="success",
            message="Model status updated successfully",
            data=ModelCatalogResponse(
                id=str(entry.id),
                name=entry.name,
                version=entry.version,
                type=entry.type,
                status=entry.status,
                owner_team=entry.owner_team,
                metadata=entry.model_metadata,
                storage_uri=entry.storage_uri,
                model_family=entry.model_family,
            ),
        )
    except ValueError as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=str(exc),
            data=None,
        )


@router.get("/datasets", response_model=EnvelopeDatasetList)
def list_datasets(
    approved_only: bool = Query(
        False,
        description="If true, return only approved datasets",
    ),
    session=Depends(get_session),
) -> EnvelopeDatasetList:
    service = DatasetService(session)
    datasets = service.list_datasets(approved_only=approved_only)
    return EnvelopeDatasetList(
        status="success",
        message="",
        data=[
            DatasetResponse(
                id=str(dataset.id),
                name=dataset.name,
                version=dataset.version,
                storage_uri=dataset.storage_uri,
                owner_team=dataset.owner_team,
                pii_scan_status=dataset.pii_scan_status,
                quality_score=dataset.quality_score,
                change_log=dataset.change_log,
                approved_at=dataset.approved_at,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
                type=dataset.type,
            )
            for dataset in datasets
        ],
    )


@router.get("/datasets/{dataset_id}", response_model=EnvelopeDataset)
def get_dataset(
    dataset_id: str, session=Depends(get_session)
) -> EnvelopeDataset:
    service = DatasetService(session)
    dataset = service.get_dataset(dataset_id)
    if not dataset:
        return EnvelopeDataset(
            status="fail",
            message=f"Dataset {dataset_id} not found",
            data=None,
        )
    return EnvelopeDataset(
        status="success",
        message="",
        data=DatasetResponse(
            id=str(dataset.id),
            name=dataset.name,
            version=dataset.version,
            storage_uri=dataset.storage_uri,
            owner_team=dataset.owner_team,
            pii_scan_status=dataset.pii_scan_status,
            quality_score=dataset.quality_score,
            change_log=dataset.change_log,
            approved_at=dataset.approved_at,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
            type=dataset.type,
        ),
    )


@router.post("/datasets", response_model=EnvelopeDataset, status_code=201)
def create_dataset(
    payload: DatasetCreate, session=Depends(get_session)
) -> EnvelopeDataset:
    service = DatasetService(session)
    try:
        dataset = service.create_dataset(payload.dict())
        return EnvelopeDataset(
            status="success",
            message="Dataset created successfully",
            data=DatasetResponse(
                id=str(dataset.id),
                name=dataset.name,
                version=dataset.version,
                storage_uri=dataset.storage_uri,
                owner_team=dataset.owner_team,
                pii_scan_status=dataset.pii_scan_status,
                quality_score=dataset.quality_score,
                change_log=dataset.change_log,
                approved_at=dataset.approved_at,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
                type=dataset.type,
            ),
        )
    except ValueError as exc:
        return EnvelopeDataset(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        return EnvelopeDataset(
            status="fail",
            message=f"Failed to create dataset: {str(exc)}",
            data=None,
        )


@router.post("/datasets/{dataset_id}/upload", response_model=EnvelopeDataset)
async def upload_dataset_files(
    dataset_id: str,
    files: List[UploadFile] = File(...),
    session=Depends(get_session),
) -> EnvelopeDataset:
    """Upload dataset files (CSV, JSONL, Parquet) to object storage."""
    service = DatasetService(session)
    versioning_service = DataVersioningService(session)
    try:
        result = await service.upload_dataset_files(dataset_id, files)
        dataset = result["dataset"]

        # Automatically create a new dataset version after successful upload (T124)
        try:
            versioning_service.create_version(
                dataset_record_id=UUID(dataset_id),
                dataset_uri=dataset.storage_uri,
                created_by="system",  # TODO: propagate user identity from auth
            )
        except Exception:
            # Graceful degradation: log and continue without failing upload
            # (actual logging handled inside service/adapter)
            pass

        return EnvelopeDataset(
            status="success",
            message="Dataset files uploaded successfully",
            data=DatasetResponse(
                id=str(dataset.id),
                name=dataset.name,
                version=dataset.version,
                storage_uri=dataset.storage_uri,
                owner_team=dataset.owner_team,
                pii_scan_status=dataset.pii_scan_status,
                quality_score=dataset.quality_score,
                change_log=dataset.change_log,
                approved_at=dataset.approved_at,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
                type=dataset.type,
            ),
        )
    except ValueError as exc:
        return EnvelopeDataset(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        return EnvelopeDataset(
            status="fail",
            message=f"Upload failed: {str(exc)}",
            data=None,
        )


@router.get("/datasets/{dataset_id}/preview")
def get_dataset_preview(
    dataset_id: str,
    limit: int = Query(10, ge=1, le=100),
    session=Depends(get_session),
) -> dict:
    """Get dataset preview with sample rows, schema, and statistics."""
    service = DatasetService(session)
    try:
        preview = service.get_dataset_preview(dataset_id, limit)
        return {
            "status": "success",
            "message": "",
            "data": preview,
        }
    except ValueError as exc:
        return {
            "status": "fail",
            "message": str(exc),
            "data": None,
        }


@router.get("/datasets/{dataset_id}/validation")
def get_dataset_validation(
    dataset_id: str,
    session=Depends(get_session),
) -> dict:
    """Get dataset validation results (PII scan and quality score)."""
    service = DatasetService(session)
    try:
        validation = service.get_validation_results(dataset_id)
        return {
            "status": "success",
            "message": "",
            "data": validation,
        }
    except ValueError as exc:
        return {
            "status": "fail",
            "message": str(exc),
            "data": None,
        }


@router.patch("/datasets/{dataset_id}/status", response_model=EnvelopeDataset)
def update_dataset_status(
    dataset_id: str, status: str = Query(...), session=Depends(get_session)
) -> EnvelopeDataset:
    """Update dataset approval status (draft, under_review, approved, rejected)."""
    service = DatasetService(session)
    try:
        dataset = service.update_dataset_status(dataset_id, status)
        return EnvelopeDataset(
            status="success",
            message="Dataset status updated successfully",
            data=DatasetResponse(
                id=str(dataset.id),
                name=dataset.name,
                version=dataset.version,
                storage_uri=dataset.storage_uri,
                owner_team=dataset.owner_team,
                pii_scan_status=dataset.pii_scan_status,
                quality_score=dataset.quality_score,
                change_log=dataset.change_log,
                approved_at=dataset.approved_at,
                created_at=dataset.created_at,
                updated_at=dataset.updated_at,
                type=dataset.type,
            ),
        )
    except ValueError as exc:
        return EnvelopeDataset(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        return EnvelopeDataset(
            status="fail",
            message=f"Failed to update dataset status: {str(exc)}",
            data=None,
        )


@router.get("/datasets/{dataset_id}/versions/{version1}/compare/{version2}")
def compare_dataset_versions(
    dataset_id: str,
    version1: str,
    version2: str,
    session=Depends(get_session),
) -> dict:
    """Compare two dataset versions."""
    service = DatasetService(session)
    try:
        comparison = service.compare_versions(dataset_id, version1, version2)
        return {
            "status": "success",
            "message": "",
            "data": comparison,
        }
    except ValueError as exc:
        return {
            "status": "fail",
            "message": str(exc),
            "data": None,
        }


@router.delete("/models/{model_id}", status_code=200)
def delete_model(
    model_id: str,
    session=Depends(get_session),
) -> dict:
    """Delete a model catalog entry."""
    service = CatalogService(session)
    try:
        result = service.delete_entry(model_id)
        return {
            "status": "success",
            "message": f"Model {model_id} deleted successfully",
            "data": result,
        }
    except ValueError as exc:
        return {
            "status": "fail",
            "message": str(exc),
            "data": None,
        }
    except Exception as exc:
        # Handle database integrity errors (e.g., model is referenced by serving endpoints)
        error_msg = str(exc)
        if "foreign key constraint" in error_msg.lower() or "integrity" in error_msg.lower():
            return {
                "status": "fail",
                "message": f"Cannot delete model {model_id}: it is being used by serving endpoints or other resources. Please remove dependencies first.",
                "data": None,
            }
        return {
            "status": "fail",
            "message": f"Deletion failed: {error_msg}",
            "data": None,
        }


@router.post("/models/{model_id}/upload", response_model=EnvelopeModelCatalog)
async def upload_model_files(
    model_id: str,
    files: List[UploadFile] = File(...),
    session=Depends(get_session),
) -> EnvelopeModelCatalog:
    """Upload model files (weights, configs, tokenizers) to object storage."""
    service = CatalogService(session)
    try:
        result = await service.upload_model_files(model_id, files)
        return EnvelopeModelCatalog(
            status="success",
            message="Model files uploaded successfully",
            data=ModelCatalogResponse(
                id=str(result["entry"].id),
                name=result["entry"].name,
                version=result["entry"].version,
                type=result["entry"].type,
                status=result["entry"].status,
                owner_team=result["entry"].owner_team,
                metadata=result["entry"].model_metadata,
                storage_uri=result["entry"].storage_uri,
                model_family=result["entry"].model_family,
            ),
        )
    except ValueError as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=str(exc),
            data=None,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=f"Upload failed: {str(exc)}",
            data=None,
        )


@router.post("/models/import-from-huggingface", response_model=EnvelopeModelCatalog)
def import_from_huggingface(
    request: HuggingFaceImportRequest,
    session=Depends(get_session),
) -> EnvelopeModelCatalog:
    """Import a model from Hugging Face Hub automatically."""
    service = CatalogService(session)
    try:
        entry = service.import_from_huggingface(
            hf_model_id=request.hf_model_id,
            name=request.name,
            version=request.version,
            model_type=request.model_type,
            owner_team=request.owner_team,
            hf_token=request.hf_token,
            model_family=request.model_family,  # Required for training-serving-spec.md
        )
        return EnvelopeModelCatalog(
            status="success",
            message=f"Model '{entry.name}' imported successfully from Hugging Face",
            data=ModelCatalogResponse(
                id=str(entry.id),
                name=entry.name,
                version=entry.version,
                type=entry.type,
                status=entry.status,
                owner_team=entry.owner_team,
                metadata=entry.model_metadata,
                storage_uri=entry.storage_uri,
                model_family=entry.model_family,
            ),
        )
    except IntegrationError as exc:
        # Use the error message from IntegrationError which is more descriptive
        return EnvelopeModelCatalog(
            status="fail",
            message=exc.message,
            data=None,
        )
    except ImportError as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=str(exc),
            data=None,
        )
    except ValueError as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=f"Import failed: {str(exc)}",
            data=None,
        )


@router.post("/models/import", response_model=EnvelopeModelCatalog)
def import_model_from_registry(
    request: ImportModelRequest,
    background_tasks: BackgroundTasks,
    session=Depends(get_session),
) -> EnvelopeModelCatalog:
    """Import a model from an external registry into the platform catalog.
    
    The model is registered immediately, and the download is processed in the background.
    """
    service = ModelRegistryService(session)
    try:
        # Register model in database first (returns immediately)
        entry = service.import_model_from_registry(
            registry_type=request.registry_type,
            registry_model_id=request.registry_model_id,
            name=request.name,
            version=request.model_version,
            model_type=request.model_type,
            owner_team=request.owner_team,
            registry_version=request.version,
            model_family=request.model_family,
        )
        
        # Schedule background download task
        background_tasks.add_task(
            service.download_and_update_model,
            model_id=entry.id,
            registry_type=request.registry_type,
            registry_model_id=request.registry_model_id,
            registry_version=request.version,
        )
        
        logger.info(f"Model {entry.id} registered, download scheduled in background")
        
        return EnvelopeModelCatalog(
            status="success",
            message="Model registered successfully. Download is in progress.",
            data=ModelCatalogResponse(
                id=str(entry.id),
                name=entry.name,
                version=entry.version,
                type=entry.type,
                status=entry.status,
                owner_team=entry.owner_team,
                metadata=entry.model_metadata,
                storage_uri=entry.storage_uri,
                model_family=entry.model_family,
            ),
        )
    except ToolUnavailableError as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=exc.message,
            data=None,
        )
    except ValueError as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        logger.error(f"Unexpected error importing model: {exc}", exc_info=True)
        return EnvelopeModelCatalog(
            status="fail",
            message=f"Import failed: {str(exc)}",
            data=None,
        )


@router.post(
    "/models/{model_id}/export",
    response_model=EnvelopeRegistryModel,
)
def export_model_to_registry(
    model_id: str,
    request: ExportModelRequest,
    session=Depends(get_session),
) -> EnvelopeRegistryModel:
    """Export a platform catalog model to an external registry."""
    service = ModelRegistryService(session)
    try:
        target_model_id = request.registry_model_id
        if not target_model_id:
            # 기본값: catalog 이름을 기반으로 registry 식별자 유추
            catalog_service = CatalogService(session)
            entry = catalog_service.get_entry(model_id)
            if not entry:
                return EnvelopeRegistryModel(
                    status="fail",
                    message=f"Model {model_id} not found",
                    data=None,
                )
            target_model_id = f"{entry.name}".replace("_", "-")

        registry_model = service.export_model_to_registry(
            model_catalog_id=model_id,
            registry_type=request.registry_type,
            registry_model_id=target_model_id,
            metadata=request.metadata,
        )
        return EnvelopeRegistryModel(
            status="success",
            message="Model exported successfully to registry",
            data=RegistryModelResponse(
                id=str(registry_model.id),
                model_catalog_id=str(registry_model.model_catalog_id),
                registry_type=registry_model.registry_type,
                registry_model_id=registry_model.registry_model_id,
                registry_repo_url=registry_model.registry_repo_url,
                registry_version=registry_model.registry_version,
                imported=registry_model.imported,
                sync_status=registry_model.sync_status,
            ),
        )
    except Exception as exc:
        return EnvelopeRegistryModel(
            status="fail",
            message=str(exc),
            data=None,
        )


@router.get(
    "/models/{model_id}/registry-links",
    response_model=EnvelopeRegistryModelList,
)
def get_model_registry_links(
    model_id: str,
    session=Depends(get_session),
) -> EnvelopeRegistryModelList:
    """Get all registry links for a catalog model."""
    service = ModelRegistryService(session)
    try:
        links = service.get_registry_links(model_id)
        return EnvelopeRegistryModelList(
            status="success",
            message="",
            data=[
                RegistryModelResponse(
                    id=str(link.id),
                    model_catalog_id=str(link.model_catalog_id),
                    registry_type=link.registry_type,
                    registry_model_id=link.registry_model_id,
                    registry_repo_url=link.registry_repo_url,
                    registry_version=link.registry_version,
                    imported=link.imported,
                    sync_status=link.sync_status,
                )
                for link in links
            ],
        )
    except Exception as exc:
        return EnvelopeRegistryModelList(
            status="fail",
            message=str(exc),
            data=None,
        )


@router.post("/models/{model_id}/check-updates")
def check_model_registry_updates(
    model_id: str,
    session=Depends(get_session),
) -> dict:
    """Check if registry models linked to a catalog model have updates available."""
    service = ModelRegistryService(session)
    try:
        updates = service.check_registry_updates(model_catalog_id=model_id)
        return {
            "status": "success",
            "message": "",
            "data": updates,
        }
    except Exception as exc:
        return {
            "status": "fail",
            "message": str(exc),
            "data": None,
        }


@router.post(
    "/datasets/{dataset_id}/versions",
    response_model=EnvelopeDatasetVersion,
    status_code=201,
)
def create_dataset_version(
    dataset_id: str,
    payload: DatasetVersionCreate,
    session=Depends(get_session),
) -> EnvelopeDatasetVersion:
    """Create a new dataset version using DVC."""
    versioning_service = DataVersioningService(session)
    dataset_service = DatasetService(session)
    
    try:
        # Get dataset to get storage URI
        dataset = dataset_service.repo.get(dataset_id)
        if not dataset:
            return EnvelopeDatasetVersion(
                status="fail",
                message=f"Dataset {dataset_id} not found",
                data=None,
            )
        
        # Create version
        version = versioning_service.create_version(
            dataset_record_id=UUID(dataset_id),
            dataset_uri=dataset.storage_uri,
            version_tag=payload.version_tag,
            parent_version_id=UUID(payload.parent_version_id) if payload.parent_version_id else None,
            created_by="system",  # TODO: Get from auth context
        )
        
        return EnvelopeDatasetVersion(
            status="success",
            message="Dataset version created successfully",
            data=DatasetVersionResponse(
                id=str(version.id),
                dataset_record_id=str(version.dataset_record_id),
                versioning_system=version.versioning_system,
                version_id=version.version_id,
                parent_version_id=str(version.parent_version_id) if version.parent_version_id else None,
                version_tag=version.version_tag,
                checksum=version.checksum,
                storage_uri=version.storage_uri,
                diff_summary=version.diff_summary,
                file_count=version.file_count,
                total_size_bytes=version.total_size_bytes,
                compression_ratio=version.compression_ratio,
                created_at=version.created_at,
                created_by=version.created_by,
            ),
        )
    except ValueError as exc:
        return EnvelopeDatasetVersion(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        return EnvelopeDatasetVersion(
            status="fail",
            message=f"Failed to create dataset version: {str(exc)}",
            data=None,
        )


@router.get(
    "/datasets/{dataset_id}/versions",
    response_model=EnvelopeDatasetVersionList,
)
def list_dataset_versions(
    dataset_id: str,
    session=Depends(get_session),
) -> EnvelopeDatasetVersionList:
    """List all versions for a dataset (T121)."""
    versioning_service = DataVersioningService(session)
    try:
        versions = versioning_service.list_versions(
            dataset_record_id=UUID(dataset_id),
        )
        return EnvelopeDatasetVersionList(
            status="success",
            message="",
            data=[
                DatasetVersionResponse(
                    id=str(v.id),
                    dataset_record_id=str(v.dataset_record_id),
                    versioning_system=v.versioning_system,
                    version_id=v.version_id,
                    parent_version_id=str(v.parent_version_id) if v.parent_version_id else None,
                    version_tag=v.version_tag,
                    checksum=v.checksum,
                    storage_uri=v.storage_uri,
                    diff_summary=v.diff_summary,
                    file_count=v.file_count,
                    total_size_bytes=v.total_size_bytes,
                    compression_ratio=v.compression_ratio,
                    created_at=v.created_at,
                    created_by=v.created_by,
                )
                for v in versions
            ],
        )
    except ValueError as exc:
        return EnvelopeDatasetVersionList(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        return EnvelopeDatasetVersionList(
            status="fail",
            message=f"Failed to list dataset versions: {str(exc)}",
            data=None,
        )


@router.get(
    "/datasets/{dataset_id}/versions/{version_id}/diff",
    response_model=EnvelopeDatasetVersionDiff,
)
def get_dataset_version_diff(
    dataset_id: str,
    version_id: str,
    baseVersionId: str = Query(..., alias="baseVersionId"),
    session=Depends(get_session),
) -> EnvelopeDatasetVersionDiff:
    """Get diff between two dataset versions (T122)."""
    versioning_service = DataVersioningService(session)
    try:
        diff = versioning_service.calculate_diff(
            version_id=UUID(version_id),
            base_version_id=UUID(baseVersionId),
            dataset_record_id=UUID(dataset_id),
        )
        diff_response = DatasetVersionDiffResponse(
            added_files=diff.get("added_files", []),
            removed_files=diff.get("removed_files", []),
            modified_files=diff.get("modified_files", []),
            added_rows=diff.get("added_rows", 0),
            removed_rows=diff.get("removed_rows", 0),
            schema_changes=diff.get("schema_changes", {}),
        )
        return EnvelopeDatasetVersionDiff(
            status="success",
            message="",
            data=diff_response,
        )
    except ValueError as exc:
        return EnvelopeDatasetVersionDiff(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        return EnvelopeDatasetVersionDiff(
            status="fail",
            message=f"Failed to calculate dataset version diff: {str(exc)}",
            data=None,
        )


@router.post(
    "/datasets/{dataset_id}/versions/{version_id}/restore",
    response_model=EnvelopeDatasetVersion,
)
def restore_dataset_version(
    dataset_id: str,
    version_id: str,
    session=Depends(get_session),
) -> EnvelopeDatasetVersion:
    """Restore dataset to a specific version (T123)."""
    versioning_service = DataVersioningService(session)
    try:
        # Perform restore operation
        versioning_service.restore_version(
            version_id=UUID(version_id),
            dataset_record_id=UUID(dataset_id),
        )

        # Return the restored version metadata
        version = versioning_service.get_version(
            version_id=UUID(version_id),
            dataset_record_id=UUID(dataset_id),
        )
        if not version:
            return EnvelopeDatasetVersion(
                status="fail",
                message=f"Version {version_id} not found after restore",
                data=None,
            )

        return EnvelopeDatasetVersion(
            status="success",
            message="Dataset version restored successfully",
            data=DatasetVersionResponse(
                id=str(version.id),
                dataset_record_id=str(version.dataset_record_id),
                versioning_system=version.versioning_system,
                version_id=version.version_id,
                parent_version_id=str(version.parent_version_id) if version.parent_version_id else None,
                version_tag=version.version_tag,
                checksum=version.checksum,
                storage_uri=version.storage_uri,
                diff_summary=version.diff_summary,
                file_count=version.file_count,
                total_size_bytes=version.total_size_bytes,
                compression_ratio=version.compression_ratio,
                created_at=version.created_at,
                created_by=version.created_by,
            ),
        )
    except ValueError as exc:
        return EnvelopeDatasetVersion(
            status="fail",
            message=str(exc),
            data=None,
        )
    except Exception as exc:
        return EnvelopeDatasetVersion(
            status="fail",
            message=f"Failed to restore dataset version: {str(exc)}",
            data=None,
        )

