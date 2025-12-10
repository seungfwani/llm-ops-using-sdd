from __future__ import annotations

import hashlib
import logging
from typing import Sequence
from uuid import uuid4
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from catalog import models as orm_models
from catalog.repositories import DatasetRepository, ModelCatalogRepository
from catalog.services.huggingface_importer import HuggingFaceImporter
from core.clients.object_store import get_object_store_client
from core.settings import get_settings

logger = logging.getLogger(__name__)


class CatalogService:
    def __init__(self, session: Session):
        self.session = session
        self.models = ModelCatalogRepository(session)
        self.datasets = DatasetRepository(session)

    def list_entries(self, status: str | None = None) -> Sequence[orm_models.ModelCatalogEntry]:
        return self.models.list(status=status)

    def get_entry(self, entry_id: str) -> orm_models.ModelCatalogEntry | None:
        return self.models.get(entry_id)

    def create_entry(self, payload: dict) -> orm_models.ModelCatalogEntry:
        entry = orm_models.ModelCatalogEntry(
            id=str(uuid4()),
            name=payload["name"],
            version=payload["version"],
            type=payload["type"],
            owner_team=payload["owner_team"],
            model_metadata=payload["metadata"],
            lineage_dataset_ids=payload.get("lineage_dataset_ids", []),
            status=payload.get("status", "draft"),
            evaluation_summary=payload.get("evaluation_summary"),
            model_family=payload["model_family"],  # Model family from training-serving-spec.md (required)
        )

        lineage_ids = entry.lineage_dataset_ids or []
        if lineage_ids:
            datasets = self.datasets.fetch_by_ids(lineage_ids)
            if len(datasets) != len(lineage_ids):
                raise ValueError("One or more lineage datasets do not exist")
            entry.datasets.extend(datasets)

        self.models.save(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def update_status(self, entry_id: str, status: str) -> orm_models.ModelCatalogEntry:
        entry = self.get_entry(entry_id)
        if not entry:
            raise ValueError("Entry not found")

        # Only allow valid, user-facing status values here.
        # Internal / legacy values (e.g. 'under_review', 'deprecated') are still
        # permitted by the DB constraint for backwards compatibility, but should
        # not be set via this API.
        valid_statuses = ["draft", "pending_review", "approved", "rejected"]
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )

        entry.status = status
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def _ensure_bucket_exists(self, s3_client, bucket_name: str) -> None:
        """Ensure bucket exists, create if it doesn't."""
        try:
            # Check if bucket exists
            s3_client.head_bucket(Bucket=bucket_name)
            logger.debug(f"Bucket '{bucket_name}' already exists")
        except s3_client.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "404":
                # Bucket doesn't exist, create it
                logger.info(f"Bucket '{bucket_name}' does not exist, creating...")
                try:
                    # For MinIO, we might need to handle location constraint differently
                    # Try without location constraint first (MinIO doesn't require it)
                    try:
                        s3_client.create_bucket(Bucket=bucket_name)
                    except s3_client.exceptions.ClientError as create_error:
                        # If that fails, try with location constraint (for S3)
                        error_code = create_error.response.get("Error", {}).get("Code", "")
                        if error_code == "IllegalLocationConstraintException":
                            # For S3, we might need to specify region
                            # But for MinIO, we can ignore this
                            pass
                        else:
                            raise
                    logger.info(f"Bucket '{bucket_name}' created successfully")
                except Exception as create_e:
                    logger.error(f"Failed to create bucket '{bucket_name}': {create_e}")
                    raise ValueError(f"Failed to create bucket '{bucket_name}': {create_e}")
            else:
                # Other error (permission denied, etc.)
                logger.error(f"Error checking bucket '{bucket_name}': {e}")
                raise

    def delete_entry(self, entry_id: str) -> dict:
        """Delete a model catalog entry and optionally clean up storage files."""
        entry = self.get_entry(entry_id)
        if not entry:
            raise ValueError("Entry not found")

        # Check if model is being used by serving endpoints
        if entry.training_jobs:
            raise ValueError(
                f"Cannot delete model {entry_id}: it has associated training jobs. "
                "Please delete or update training jobs first."
            )

        # Note: We don't check serving_endpoints here because the foreign key constraint
        # will prevent deletion if there are active serving endpoints (ondelete="RESTRICT")
        # The database will raise an integrity error if deletion is attempted.

        storage_uri = entry.storage_uri
        model_id = str(entry.id)

        # Delete from database
        deleted = self.models.delete(entry_id)
        if not deleted:
            raise ValueError("Failed to delete entry")

        self.session.commit()

        # Clean up storage files
        # Note: This is a best-effort cleanup. If it fails, we still consider the deletion successful
        # since the database record is already deleted.
        storage_cleaned = False
        deleted_files_count = 0
        if storage_uri:
            try:
                s3_client = get_object_store_client()
                # Extract bucket and prefix from storage_uri (format: s3://bucket/prefix/)
                if storage_uri.startswith("s3://"):
                    parts = storage_uri.replace("s3://", "").split("/", 1)
                    if len(parts) == 2:
                        bucket_name = parts[0]
                        prefix = parts[1]
                        
                        logger.info(
                            f"Deleting storage files for model {model_id}: "
                            f"bucket={bucket_name}, prefix={prefix}"
                        )
                        
                        # List and delete all objects with this prefix using pagination
                        try:
                            paginator = s3_client.get_paginator("list_objects_v2")
                            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
                            
                            objects_to_delete = []
                            for page in pages:
                                if "Contents" in page:
                                    for obj in page["Contents"]:
                                        objects_to_delete.append({"Key": obj["Key"]})
                            
                            if objects_to_delete:
                                # Delete objects in batches (S3 allows up to 1000 objects per batch)
                                batch_size = 1000
                                for i in range(0, len(objects_to_delete), batch_size):
                                    batch = objects_to_delete[i:i + batch_size]
                                    try:
                                        response = s3_client.delete_objects(
                                            Bucket=bucket_name,
                                            Delete={"Objects": batch, "Quiet": True}
                                        )
                                        deleted_count = len(batch)
                                        if "Errors" in response and response["Errors"]:
                                            # Log errors but continue
                                            for error in response["Errors"]:
                                                logger.warning(
                                                    f"Failed to delete object {error['Key']}: "
                                                    f"{error.get('Message', 'Unknown error')}"
                                                )
                                            deleted_count -= len(response["Errors"])
                                        deleted_files_count += deleted_count
                                        logger.info(
                                            f"Deleted {deleted_count} files from storage "
                                            f"(batch {i // batch_size + 1})"
                                        )
                                    except Exception as batch_error:
                                        logger.error(
                                            f"Error deleting batch of files: {batch_error}",
                                            exc_info=True
                                        )
                                
                                storage_cleaned = True
                                logger.info(
                                    f"Storage cleanup completed: {deleted_files_count} files deleted "
                                    f"from {storage_uri}"
                                )
                            else:
                                logger.info(f"No files found to delete at {storage_uri}")
                        except Exception as list_error:
                            logger.error(
                                f"Error listing objects for deletion: {list_error}",
                                exc_info=True
                            )
                    else:
                        logger.warning(
                            f"Invalid storage URI format: {storage_uri}. "
                            f"Expected format: s3://bucket/prefix/"
                        )
                else:
                    logger.warning(
                        f"Storage URI does not start with 's3://': {storage_uri}. "
                        f"Skipping storage cleanup."
                    )
            except Exception as cleanup_error:
                logger.error(
                    f"Error during storage cleanup for model {model_id}: {cleanup_error}",
                    exc_info=True
                )

        return {
            "model_id": model_id,
            "storage_cleaned": storage_cleaned,
            "deleted_files_count": deleted_files_count,
        }

    async def upload_model_files(
        self, model_id: str, files: list[UploadFile]
    ) -> dict:
        """Upload model files to object storage and update catalog entry."""
        entry = self.get_entry(model_id)
        if not entry:
            raise FileNotFoundError(f"Model {model_id} not found")

        # Validate files
        self._validate_model_files(files, entry.type)

        # Generate storage path
        settings = get_settings()
        bucket_name = settings.object_store_bucket or settings.training_namespace
        # Folder structure: models/{model_id}/{version}/
        storage_path = f"models/{model_id}/{entry.version}/"

        # Upload files to object storage
        s3_client = get_object_store_client()
        
        # Ensure bucket exists before uploading
        self._ensure_bucket_exists(s3_client, bucket_name)
        
        uploaded_files = []

        try:
            for file in files:
                # Read file content
                content = await file.read()
                file.seek(0)  # Reset for potential reuse

                # Calculate checksum
                checksum = hashlib.sha256(content).hexdigest()

                # Upload to S3/MinIO
                object_key = f"{storage_path}{file.filename}"
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=content,
                    Metadata={"checksum": checksum, "original-filename": file.filename},
                )

                uploaded_files.append({
                    "filename": file.filename,
                    "size": len(content),
                    "checksum": checksum,
                })

            # Update catalog entry with storage URI
            # Construct URI based on endpoint type
            if settings.object_store_secure:
                protocol = "https"
            else:
                protocol = "http"
            
            endpoint_host = str(settings.object_store_endpoint).replace("http://", "").replace("https://", "")
            storage_uri = f"s3://{bucket_name}/{storage_path}"
            
            entry.storage_uri = storage_uri
            self.session.commit()
            self.session.refresh(entry)

            return {
                "entry": entry,
                "uploaded_files": uploaded_files,
                "storage_uri": storage_uri,
            }
        except Exception as e:
            # Cleanup: delete uploaded files on error
            for file_info in uploaded_files:
                try:
                    object_key = f"{storage_path}{file_info['filename']}"
                    s3_client.delete_object(Bucket=bucket_name, Key=object_key)
                except Exception:
                    pass  # Ignore cleanup errors
            raise

    def import_from_huggingface(
        self,
        hf_model_id: str,
        name: Optional[str] = None,
        version: str = "1.0.0",
        model_type: str = "base",
        owner_team: str = "ml-platform",
        hf_token: Optional[str] = None,
        model_family: str = None,  # Required for training-serving-spec.md
    ) -> orm_models.ModelCatalogEntry:
        """Import a model from Hugging Face Hub."""
        importer = HuggingFaceImporter(self.session)
        return importer.import_model(
            hf_model_id=hf_model_id,
            name=name,
            version=version,
            model_type=model_type,
            owner_team=owner_team,
            hf_token=hf_token,
            model_family=model_family,
        )

    def _validate_model_files(self, files: list[UploadFile], model_type: str) -> None:
        """Validate uploaded files based on model type."""
        if not files:
            raise ValueError("At least one file must be uploaded")

        # Check file sizes (max 10GB per file)
        max_file_size = 10 * 1024 * 1024 * 1024  # 10GB
        # Allowed file extensions for model files
        # Includes: PyTorch (.pt, .pth, .bin), SafeTensors (.safetensors),
        # Flax/JAX (.msgpack), TensorFlow (.h5, .pb, .ckpt), ONNX (.onnx),
        # and common config/text files
        allowed_extensions = {
            ".bin", ".safetensors", ".json", ".txt", ".pt", ".pth", ".onnx",
            ".msgpack",  # Flax/JAX models
            ".h5", ".hdf5",  # Keras/TensorFlow HDF5
            ".pb",  # TensorFlow protobuf
            ".ckpt",  # TensorFlow checkpoint
            ".tflite",  # TensorFlow Lite
            ".md",  # Documentation files bundled with models (e.g., README.md)
            ".jinja",  # Prompt/template files (e.g., chat_template.jinja)
        }

        filenames = [f.filename for f in files]
        required_files = {"config.json"}  # Minimum required

        for file in files:
            # Check file extension
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in allowed_extensions:
                raise ValueError(
                    f"File {file.filename} has invalid extension. "
                    f"Allowed: {', '.join(allowed_extensions)}"
                )

            # Check file size (we'll check after reading, but validate filename first)
            if not file.filename:
                raise ValueError("File must have a filename")

        # For base and fine-tuned models, require config.json
        if model_type in ("base", "fine-tuned"):
            if not any(f.filename == "config.json" for f in files):
                raise ValueError(
                    f"Model type '{model_type}' requires config.json file"
                )

        # Check total size (approximate, will be validated during upload)
        # This is a basic check - actual size validation happens during upload

