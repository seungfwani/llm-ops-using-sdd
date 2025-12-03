from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from typing import List, Optional

from catalog.schemas import (
    DatasetCreate,
    DatasetResponse,
    EnvelopeDataset,
    EnvelopeDatasetList,
    EnvelopeModelCatalog,
    EnvelopeModelCatalogList,
    ModelCatalogCreate,
    ModelCatalogResponse,
)
from pydantic import BaseModel
from catalog.services import CatalogService, DatasetService
from core.database import get_session

router = APIRouter(prefix="/llm-ops/v1/catalog", tags=["catalog"])


@router.get("/models", response_model=EnvelopeModelCatalogList)
def list_models(session=Depends(get_session)) -> EnvelopeModelCatalogList:
    service = CatalogService(session)
    entries = service.list_entries()
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
    model_id: str, status: str, session=Depends(get_session)
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
            ),
        )
    except ValueError as exc:
        return EnvelopeModelCatalog(
            status="fail",
            message=str(exc),
            data=None,
        )


@router.get("/datasets", response_model=EnvelopeDatasetList)
def list_datasets(session=Depends(get_session)) -> EnvelopeDatasetList:
    service = DatasetService(session)
    datasets = service.list_datasets()
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
    try:
        result = await service.upload_dataset_files(dataset_id, files)
        dataset = result["dataset"]
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

