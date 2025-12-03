from __future__ import annotations

import hashlib
from typing import Sequence
from uuid import uuid4
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from catalog import models as orm_models
from catalog.repositories import DatasetRepository, ModelCatalogRepository
from core.clients.object_store import get_object_store_client
from core.settings import get_settings


class CatalogService:
    def __init__(self, session: Session):
        self.session = session
        self.models = ModelCatalogRepository(session)
        self.datasets = DatasetRepository(session)

    def list_entries(self) -> Sequence[orm_models.ModelCatalogEntry]:
        return self.models.list()

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

        # Optionally clean up storage files
        # Note: This is a best-effort cleanup. If it fails, we still consider the deletion successful
        # since the database record is already deleted.
        storage_cleaned = False
        if storage_uri:
            try:
                s3_client = get_object_store_client()
                # Extract bucket and prefix from storage_uri (format: s3://bucket/prefix/)
                if storage_uri.startswith("s3://"):
                    parts = storage_uri.replace("s3://", "").split("/", 1)
                    if len(parts) == 2:
                        bucket_name = parts[0]
                        prefix = parts[1]
                        # List and delete all objects with this prefix
                        try:
                            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
                            if "Contents" in response:
                                for obj in response["Contents"]:
                                    s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
                                storage_cleaned = True
                        except Exception:
                            pass  # Ignore storage cleanup errors
            except Exception:
                pass  # Ignore storage cleanup errors

        return {
            "model_id": model_id,
            "storage_cleaned": storage_cleaned,
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
        bucket_name = "models"  # Could be configurable
        storage_path = f"models/{model_id}/{entry.version}/"

        # Upload files to object storage
        s3_client = get_object_store_client()
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

