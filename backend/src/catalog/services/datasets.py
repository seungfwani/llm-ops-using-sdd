from __future__ import annotations

import csv
import json
import re
from typing import Sequence, Optional, List, Dict, Any
from uuid import uuid4
from io import BytesIO, StringIO

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from fastapi import UploadFile
from sqlalchemy.orm import Session

from catalog import models as orm_models
from catalog.repositories import DatasetRepository
from core.clients.object_store import get_object_store_client
from core.settings import get_settings
import logging

logger = logging.getLogger(__name__)


class DatasetService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = DatasetRepository(session)

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

    def list_datasets(self) -> Sequence[orm_models.DatasetRecord]:
        return self.repo.list()

    def get_dataset(self, dataset_id: str) -> Optional[orm_models.DatasetRecord]:
        return self.repo.get(dataset_id)

    def create_dataset(self, payload: dict) -> orm_models.DatasetRecord:
        # Check for duplicate name+version combination
        existing = self.repo.get_by_name_version(payload["name"], payload["version"])
        if existing:
            raise ValueError(
                f"Dataset with name '{payload['name']}' and version '{payload['version']}' already exists. "
                f"Please use a different version or update the existing dataset."
            )
        
        dataset = orm_models.DatasetRecord(
            id=str(uuid4()),
            name=payload["name"],
            version=payload["version"],
            storage_uri=payload.get("storage_uri", ""),  # Will be set after upload
            owner_team=payload["owner_team"],
            change_log=payload.get("change_log"),
            pii_scan_status=payload.get("pii_scan_status", "pending"),
            quality_score=payload.get("quality_score"),
        )
        self.repo.save(dataset)
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    def update_dataset_status(self, dataset_id: str, status: str) -> orm_models.DatasetRecord:
        """Update dataset approval status (draft, under_review, approved, rejected)."""
        dataset = self.repo.get(dataset_id)
        if not dataset:
            raise ValueError("Dataset not found")
        
        valid_statuses = ["draft", "under_review", "approved", "rejected"]
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
        
        # Validate PII scan status and quality score before allowing approval
        if status == "approved":
            if dataset.pii_scan_status != "clean":
                raise ValueError(
                    f"Cannot approve dataset: PII scan status is '{dataset.pii_scan_status}'. "
                    "PII scan must be 'clean' before approval."
                )
            if dataset.quality_score is None or dataset.quality_score < 60:
                raise ValueError(
                    f"Cannot approve dataset: Quality score is {dataset.quality_score}. "
                    "Quality score must be at least 60 before approval."
                )
            from datetime import datetime
            dataset.approved_at = datetime.utcnow()
        elif status in ["draft", "rejected"]:
            dataset.approved_at = None
        
        # Note: We're using approved_at to track approval, but status field doesn't exist in the model
        # For now, we'll track it via approved_at. If needed, we can add a status field later.
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    async def upload_dataset_files(
        self, dataset_id: str, files: List[UploadFile]
    ) -> Dict[str, Any]:
        """Upload dataset files to object storage and trigger validation."""
        dataset = self.repo.get(dataset_id)
        if not dataset:
            raise ValueError("Dataset not found")

        # Validate file formats
        allowed_extensions = {".csv", ".jsonl", ".parquet"}
        for file in files:
            file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""
            if file_ext not in allowed_extensions:
                raise ValueError(f"Unsupported file format: {file_ext}. Allowed: CSV, JSONL, Parquet")

        # Upload to object storage
        settings = get_settings()
        s3_client = get_object_store_client()
        # Use unified bucket per namespace
        bucket_name = settings.object_store_bucket or settings.training_namespace
        
        # Ensure bucket exists before uploading
        self._ensure_bucket_exists(s3_client, bucket_name)
        
        # Folder structure: datasets/{dataset_id}/{version}/
        storage_prefix = f"datasets/{dataset_id}/{dataset.version}/"

        uploaded_files = []
        for file in files:
            file_content = await file.read()
            file_key = f"{storage_prefix}{file.filename}"
            
            s3_client.put_object(
                Bucket=bucket_name,
                Key=file_key,
                Body=file_content,
            )
            uploaded_files.append(file.filename)

        # Update storage URI
        storage_uri = f"s3://{bucket_name}/{storage_prefix}"
        dataset.storage_uri = storage_uri
        self.session.commit()
        self.session.refresh(dataset)

        # Trigger validation asynchronously (in production, use background tasks)
        # For now, we'll run it synchronously
        try:
            validation_results = await self._run_validation(dataset_id, file_content, file.filename)
            dataset.pii_scan_status = validation_results["pii_status"]
            dataset.quality_score = validation_results["quality_score"]
            self.session.commit()
            self.session.refresh(dataset)
        except Exception as e:
            # Log error but don't fail upload
            print(f"Validation error: {e}")

        return {
            "dataset": dataset,
            "uploaded_files": uploaded_files,
            "storage_uri": storage_uri,
        }

    async def _run_validation(self, dataset_id: str, file_content: bytes, filename: str) -> Dict[str, Any]:
        """Run PII scan and quality scoring on dataset."""
        # PII detection
        pii_status = self._detect_pii(file_content, filename)
        
        # Quality scoring
        quality_score = self._calculate_quality_score(file_content, filename)
        
        return {
            "pii_status": pii_status,
            "quality_score": quality_score,
        }

    def _detect_pii(self, file_content: bytes, filename: str) -> str:
        """Detect PII using regex patterns."""
        # PII patterns (basic examples)
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        ssn_pattern = r'\b\d{3}-\d{2}-\d{4}\b'
        
        content_str = file_content.decode('utf-8', errors='ignore')
        
        if re.search(email_pattern, content_str) or \
           re.search(phone_pattern, content_str) or \
           re.search(ssn_pattern, content_str):
            return "failed"
        
        return "clean"

    def _calculate_quality_score(self, file_content: bytes, filename: str) -> int:
        """Calculate quality score (0-100) based on data quality metrics."""
        try:
            file_ext = filename.split(".")[-1].lower()
            
            if HAS_PANDAS:
                if file_ext == "csv":
                    df = pd.read_csv(BytesIO(file_content))
                elif file_ext == "jsonl":
                    lines = file_content.decode('utf-8').strip().split('\n')
                    df = pd.DataFrame([json.loads(line) for line in lines if line])
                elif file_ext == "parquet":
                    df = pd.read_parquet(BytesIO(file_content))
                else:
                    return 50  # Default score for unknown formats

                # Calculate quality metrics
                total_rows = len(df)
                if total_rows == 0:
                    return 0

                missing_pct = (df.isnull().sum().sum() / (total_rows * len(df.columns))) * 100
                duplicate_pct = (df.duplicated().sum() / total_rows) * 100

                # Quality score calculation (simplified)
                score = 100
                score -= min(missing_pct * 0.5, 30)  # Penalize missing values
                score -= min(duplicate_pct * 0.3, 20)  # Penalize duplicates
                
                return max(0, int(score))
            else:
                # Fallback: basic quality check without pandas
                content_str = file_content.decode('utf-8', errors='ignore')
                lines = content_str.strip().split('\n')
                if len(lines) == 0:
                    return 0
                
                # Basic quality metrics
                empty_lines = sum(1 for line in lines if not line.strip())
                empty_pct = (empty_lines / len(lines)) * 100
                
                score = 100
                score -= min(empty_pct * 0.5, 30)
                return max(0, int(score))
        except Exception:
            return 50  # Default score on error

    def get_dataset_preview(self, dataset_id: str, limit: int = 10) -> Dict[str, Any]:
        """Get dataset preview with sample rows and schema."""
        dataset = self.repo.get(dataset_id)
        if not dataset:
            raise ValueError("Dataset not found")
        
        if not dataset.storage_uri:
            raise ValueError("Dataset files not uploaded yet")

        # Parse storage URI (format: s3://bucket/path/)
        # Example: s3://datasets/{dataset_id}/{version}/
        storage_uri = dataset.storage_uri
        if not storage_uri.startswith("s3://"):
            raise ValueError(f"Invalid storage URI format: {storage_uri}")
        
        uri_parts = storage_uri.replace("s3://", "").split("/", 1)
        bucket_name = uri_parts[0]
        prefix = uri_parts[1] if len(uri_parts) > 1 else ""
        
        # Download and parse dataset files
        s3_client = get_object_store_client()
        settings = get_settings()
        
        # List objects in the dataset directory
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            if "Contents" not in response or len(response["Contents"]) == 0:
                raise ValueError("No files found in dataset storage")
            
            # Get the first file (or find CSV/JSONL/Parquet file)
            files = sorted(response["Contents"], key=lambda x: x["Key"])
            dataset_file = None
            file_format = None
            
            for obj in files:
                key = obj["Key"]
                if key.endswith(".csv"):
                    dataset_file = key
                    file_format = "csv"
                    break
                elif key.endswith(".jsonl"):
                    dataset_file = key
                    file_format = "jsonl"
                    break
                elif key.endswith(".parquet"):
                    dataset_file = key
                    file_format = "parquet"
                    break
            
            if not dataset_file:
                # Use first file if no recognized format found
                dataset_file = files[0]["Key"]
                file_format = dataset_file.split(".")[-1] if "." in dataset_file else "unknown"
            
            # Download file
            file_obj = s3_client.get_object(Bucket=bucket_name, Key=dataset_file)
            file_content = file_obj["Body"].read()
            file_size = len(file_content)
            
            # Parse file based on format
            sample_rows = []
            schema = {}
            total_rows = 0
            
            if file_format == "csv" and HAS_PANDAS:
                # Read sample rows for preview
                df_sample = pd.read_csv(BytesIO(file_content), nrows=limit)
                sample_rows = df_sample.values.tolist()
                schema = {col: str(dtype) for col, dtype in df_sample.dtypes.items()}
                # Count total rows efficiently
                df_count = pd.read_csv(BytesIO(file_content), usecols=[0])
                total_rows = len(df_count)
            elif file_format == "jsonl":
                lines = file_content.decode('utf-8').strip().split('\n')
                total_rows = len(lines)
                sample_rows = []
                for line in lines[:limit]:
                    try:
                        row = json.loads(line)
                        sample_rows.append(list(row.values()) if isinstance(row, dict) else row)
                        if not schema and isinstance(row, dict):
                            schema = {key: type(value).__name__ for key, value in row.items()}
                    except json.JSONDecodeError:
                        continue
            elif file_format == "parquet" and HAS_PANDAS:
                df = pd.read_parquet(BytesIO(file_content))
                total_rows = len(df)
                sample_rows = df.head(limit).values.tolist()
                schema = {col: str(dtype) for col, dtype in df.dtypes.items()}
            else:
                # Fallback: try to parse as CSV without pandas
                content_str = file_content.decode('utf-8', errors='ignore')
                lines = content_str.strip().split('\n')
                total_rows = len(lines)
                if lines:
                    reader = csv.reader(StringIO('\n'.join(lines[:limit])))
                    sample_rows = [row for row in reader]
                    if sample_rows:
                        schema = {f"column_{i+1}": "string" for i in range(len(sample_rows[0]))}
            
            return {
                "sample_rows": sample_rows,
                "schema": schema,
                "statistics": {
                    "total_rows": total_rows,
                    "column_count": len(schema),
                    "file_size": file_size,
                    "format": file_format,
                },
            }
        except Exception as e:
            raise ValueError(f"Failed to load dataset preview: {str(e)}")

    def get_validation_results(self, dataset_id: str) -> Dict[str, Any]:
        """Get PII scan and quality score results."""
        dataset = self.repo.get(dataset_id)
        if not dataset:
            raise ValueError("Dataset not found")
        
        return {
            "pii_scan": {
                "status": dataset.pii_scan_status,
                "detected_types": [],
                "locations": [],
            },
            "quality_score": {
                "overall": dataset.quality_score or 0,
                "breakdown": {
                    "missing_values": 0,
                    "duplicates": 0,
                    "distribution": 0,
                    "schema_compliance": 0,
                },
            },
        }

    def compare_versions(
        self, dataset_id: str, version1: str, version2: str
    ) -> Dict[str, Any]:
        """Compare two dataset versions."""
        # Implementation would fetch both versions and compare
        return {
            "added_rows": 0,
            "removed_rows": 0,
            "modified_rows": 0,
            "schema_changes": [],
        }

