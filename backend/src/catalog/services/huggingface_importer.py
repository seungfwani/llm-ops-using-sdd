"""Hugging Face model importer service."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as orm_models
from catalog.repositories import ModelCatalogRepository
from core.clients.object_store import get_object_store_client
from core.settings import get_settings

logger = logging.getLogger(__name__)


class HuggingFaceImporter:
    """Service for importing models from Hugging Face Hub."""

    def __init__(self, session: Session):
        self.session = session
        self.models = ModelCatalogRepository(session)
        self.settings = get_settings()

    def import_model(
        self,
        hf_model_id: str,
        name: Optional[str] = None,
        version: str = "1.0.0",
        model_type: str = "base",
        owner_team: str = "ml-platform",
        hf_token: Optional[str] = None,
    ) -> orm_models.ModelCatalogEntry:
        """
        Import a model from Hugging Face Hub.

        Steps:
        1. Download model from Hugging Face
        2. Upload files to object storage
        3. Create catalog entry
        4. Return catalog entry

        Args:
            hf_model_id: Hugging Face model ID (e.g., "microsoft/DialoGPT-small")
            name: Model name (defaults to last part of hf_model_id)
            version: Model version
            model_type: Model type (base, fine-tuned, external)
            owner_team: Owner team name
            hf_token: Hugging Face API token (for gated models)

        Returns:
            Created ModelCatalogEntry
        """
        try:
            from huggingface_hub import snapshot_download, model_info
        except ImportError:
            raise ImportError(
                "huggingface_hub is required for importing models. "
                "Install it with: pip install huggingface_hub"
            )

        # Get model info from Hugging Face
        logger.info(f"Fetching model info from Hugging Face: {hf_model_id}")
        try:
            info = model_info(hf_model_id, token=hf_token)
        except Exception as e:
            raise ValueError(f"Failed to fetch model info from Hugging Face: {e}")

        # Generate model name if not provided
        if not name:
            name = hf_model_id.split("/")[-1].replace("-", "_").lower()

        # Check if model already exists
        existing = self.models.get_by_name_type_version(name, model_type, version)
        if existing:
            raise ValueError(
                f"Model with name '{name}', type '{model_type}', and version '{version}' already exists"
            )

        # Check model size before downloading (if available)
        model_size_gb = self._calculate_model_size(info)
        max_size_gb = self.settings.huggingface_max_download_size_gb
        
        if max_size_gb > 0:
            if model_size_gb > 0:
                # Size is known - check before download
                if model_size_gb > max_size_gb:
                    size_mb = model_size_gb * 1024
                    max_size_mb = max_size_gb * 1024
                    logger.error(
                        f"Model size limit exceeded for {hf_model_id}: "
                        f"Model size: {model_size_gb:.2f} GB ({size_mb:.0f} MB), "
                        f"Maximum allowed: {max_size_gb:.2f} GB ({max_size_mb:.0f} MB), "
                        f"Exceeds by: {model_size_gb - max_size_gb:.2f} GB ({(model_size_gb - max_size_gb) * 1024:.0f} MB)."
                    )
                    raise ValueError(
                        f"This operation is not possible with the current system configuration. "
                        f"Model size: {model_size_gb:.2f} GB ({size_mb:.0f} MB) "
                        f"exceeds the maximum allowed size: {max_size_gb:.2f} GB ({max_size_mb:.0f} MB). "
                        f"Exceeds by {model_size_gb - max_size_gb:.2f} GB ({(model_size_gb - max_size_gb) * 1024:.0f} MB). "
                        f"Download is not allowed. Please use a smaller model or contact administrator to increase the limit."
                    )
                logger.info(f"Model size verified: {model_size_gb:.2f} GB ({model_size_gb * 1024:.0f} MB) - within limit: {max_size_gb:.2f} GB ({max_size_gb * 1024:.0f} MB) - download approved")
            else:
                # Size is unknown - allow download but verify after download
                logger.warning(
                    f"Model size could not be determined before download for {hf_model_id}. "
                    f"Proceeding with download. Size will be verified after download "
                    f"(maximum allowed: {max_size_gb:.2f} GB / {max_size_gb * 1024:.0f} MB)."
                )

        # Create temporary directory for download
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            download_dir = temp_path / "model"

            logger.info(f"Downloading model from Hugging Face: {hf_model_id}")
            try:
                # Download model files
                snapshot_download(
                    repo_id=hf_model_id,
                    local_dir=str(download_dir),
                    token=hf_token,
                    local_dir_use_symlinks=False,
                )
                logger.info(f"Model downloaded successfully to {download_dir}")
                
                # Verify downloaded size (safety check)
                downloaded_size_gb = self._calculate_downloaded_size(download_dir)
                max_size_gb = self.settings.huggingface_max_download_size_gb
                
                if max_size_gb > 0 and downloaded_size_gb > max_size_gb:
                    downloaded_size_mb = downloaded_size_gb * 1024
                    max_size_mb = max_size_gb * 1024
                    excess_gb = downloaded_size_gb - max_size_gb
                    excess_mb = excess_gb * 1024
                    logger.error(
                        f"Downloaded model size limit exceeded for {hf_model_id}: "
                        f"Downloaded size: {downloaded_size_gb:.2f} GB ({downloaded_size_mb:.0f} MB), "
                        f"Maximum allowed: {max_size_gb:.2f} GB ({max_size_mb:.0f} MB), "
                        f"Exceeds by: {excess_gb:.2f} GB ({excess_mb:.0f} MB). "
                        f"Files will be cleaned up."
                    )
                    raise ValueError(
                        f"This operation is not possible with the current system configuration. "
                        f"Downloaded model size: {downloaded_size_gb:.2f} GB ({downloaded_size_mb:.0f} MB) "
                        f"exceeds the maximum allowed size: {max_size_gb:.2f} GB ({max_size_mb:.0f} MB). "
                        f"Exceeds by {excess_gb:.2f} GB ({excess_mb:.0f} MB). "
                        f"Downloaded files will be cleaned up. Please use a smaller model."
                    )
                
                logger.info(f"Downloaded model size verified: {downloaded_size_gb:.2f} GB ({downloaded_size_gb * 1024:.0f} MB) - within limit: {max_size_gb:.2f} GB ({max_size_gb * 1024:.0f} MB)")
            except ValueError:
                # Re-raise ValueError as-is (size limit exceeded)
                raise
            except Exception as e:
                raise ValueError(f"Failed to download model from Hugging Face: {e}")

            # Extract metadata from Hugging Face model info
            metadata = self._extract_metadata(hf_model_id, info)
            
            # Add model size to metadata
            downloaded_size_gb = self._calculate_downloaded_size(download_dir)
            metadata["model_size_gb"] = round(downloaded_size_gb, 2)

            # Create catalog entry first to get the model ID
            model_id = str(uuid4())
            logger.info(f"Creating catalog entry for model: {name}")
            entry = orm_models.ModelCatalogEntry(
                id=model_id,
                name=name,
                version=version,
                type=model_type,
                owner_team=owner_team,
                model_metadata=metadata,
                storage_uri=None,  # Will be set after upload
                status="draft",
            )

            self.models.save(entry)
            self.session.commit()
            self.session.refresh(entry)

            # Upload files to object storage with actual model ID
            logger.info("Uploading model files to object storage...")
            storage_uri = self._upload_to_storage(
                model_id=str(entry.id),
                version=version,
                local_dir=download_dir,
            )

            # Update entry with storage URI
            entry.storage_uri = storage_uri
            self.session.commit()
            self.session.refresh(entry)

            logger.info(f"Successfully imported model: {entry.id}")
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

    def _upload_to_storage(
        self,
        model_id: str,
        version: str,
        local_dir: Path,
    ) -> str:
        """Upload model files to object storage."""
        s3_client = get_object_store_client()
        bucket_name = self.settings.object_store_bucket or self.settings.training_namespace
        
        # Ensure bucket exists before uploading
        self._ensure_bucket_exists(s3_client, bucket_name)
        
        # Folder structure: models/{model_id}/{version}/
        storage_path = f"models/{model_id}/{version}/"

        # Collect all files to upload
        files_to_upload = []
        for file_path in local_dir.rglob("*"):
            if file_path.is_file():
                files_to_upload.append(file_path)

        logger.info(f"Uploading {len(files_to_upload)} files to object storage...")

        uploaded_count = 0
        # Multipart upload threshold: 100MB (use multipart for larger files)
        MULTIPART_THRESHOLD = 100 * 1024 * 1024  # 100MB
        
        for file_path in files_to_upload:
            relative_path = file_path.relative_to(local_dir)
            object_key = f"{storage_path}{relative_path}".replace("\\", "/")
            file_size = file_path.stat().st_size

            try:
                # Use multipart upload for large files to avoid memory issues
                if file_size > MULTIPART_THRESHOLD:
                    logger.info(
                        f"Uploading large file {relative_path} "
                        f"({file_size / (1024*1024):.2f} MB) using multipart upload..."
                    )
                    self._upload_large_file(
                        s3_client, bucket_name, object_key, file_path, file_size
                    )
                    logger.info(f"Completed multipart upload for {relative_path}")
                else:
                    # For smaller files, use regular upload with streaming
                    logger.debug(f"Uploading {relative_path} ({file_size / (1024*1024):.2f} MB)...")
                    with open(file_path, "rb") as f:
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=object_key,
                            Body=f,
                        )
                    logger.debug(f"Completed upload for {relative_path}")
                
                uploaded_count += 1
                if uploaded_count % 10 == 0:
                    logger.info(f"Uploaded {uploaded_count}/{len(files_to_upload)} files...")
            except Exception as e:
                logger.error(
                    f"Failed to upload {relative_path} (size: {file_size / (1024*1024):.2f} MB): {e}",
                    exc_info=True
                )
                raise

        logger.info(f"Successfully uploaded {uploaded_count} files to {storage_path}")

        # Construct storage URI (use s3:// format for consistency with model registration API)
        storage_uri = f"s3://{bucket_name}/{storage_path}"
        logger.info(f"Storage URI: {storage_uri}")
        
        return storage_uri

    def _upload_large_file(
        self,
        s3_client,
        bucket_name: str,
        object_key: str,
        file_path: Path,
        file_size: int,
        chunk_size: int = 50 * 1024 * 1024,  # 50MB chunks
        max_retries: int = 3,
    ) -> None:
        """Upload large file using multipart upload with retry logic."""
        import time
        
        for attempt in range(max_retries):
            try:
                # Create multipart upload
                multipart_response = s3_client.create_multipart_upload(
                    Bucket=bucket_name,
                    Key=object_key,
                )
                upload_id = multipart_response["UploadId"]
                
                parts = []
                part_number = 1
                
                with open(file_path, "rb") as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        
                        # Upload part with retry
                        part_uploaded = False
                        for part_attempt in range(max_retries):
                            try:
                                part_response = s3_client.upload_part(
                                    Bucket=bucket_name,
                                    Key=object_key,
                                    PartNumber=part_number,
                                    UploadId=upload_id,
                                    Body=chunk,
                                )
                                parts.append({
                                    "PartNumber": part_number,
                                    "ETag": part_response["ETag"],
                                })
                                part_uploaded = True
                                break
                            except Exception as part_e:
                                if part_attempt < max_retries - 1:
                                    logger.warning(
                                        f"Part {part_number} upload failed (attempt {part_attempt + 1}/{max_retries}): {part_e}. Retrying..."
                                    )
                                    time.sleep(2 ** part_attempt)  # Exponential backoff
                                else:
                                    raise
                        
                        if not part_uploaded:
                            raise Exception(f"Failed to upload part {part_number} after {max_retries} attempts")
                        
                        part_number += 1
                        logger.debug(f"Uploaded part {part_number - 1} of {object_key}")
                
                # Complete multipart upload
                s3_client.complete_multipart_upload(
                    Bucket=bucket_name,
                    Key=object_key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
                logger.info(f"Successfully completed multipart upload for {object_key}")
                return
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Multipart upload failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying..."
                    )
                    # Try to abort the multipart upload if it exists
                    try:
                        if 'upload_id' in locals():
                            s3_client.abort_multipart_upload(
                                Bucket=bucket_name,
                                Key=object_key,
                                UploadId=upload_id,
                            )
                    except Exception:
                        pass  # Ignore abort errors
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # Final attempt failed, try to abort
                    try:
                        if 'upload_id' in locals():
                            s3_client.abort_multipart_upload(
                                Bucket=bucket_name,
                                Key=object_key,
                                UploadId=upload_id,
                            )
                    except Exception:
                        pass
                    raise Exception(f"Failed to upload {object_key} after {max_retries} attempts: {e}")


    def _calculate_model_size(self, info) -> float:
        """
        Calculate total model size in GB from Hugging Face model info.
        
        Args:
            info: Hugging Face model info object
            
        Returns:
            Total size in GB
        """
        total_size_bytes = 0
        
        # Try to get file sizes from model info
        if hasattr(info, "siblings"):
            # siblings contains file information including size
            for sibling in info.siblings:
                if hasattr(sibling, "rfilename"):
                    # Try multiple ways to get file size
                    size = None
                    
                    # Method 1: direct size attribute
                    if hasattr(sibling, "size") and sibling.size is not None:
                        size = sibling.size
                    # Method 2: size from file info
                    elif hasattr(sibling, "file") and hasattr(sibling.file, "size"):
                        size = sibling.file.size
                    # Method 3: size attribute directly on sibling
                    elif hasattr(sibling, "__dict__"):
                        size = sibling.__dict__.get("size")
                    
                    if size:
                        total_size_bytes += size
        
        # Convert bytes to GB
        size_gb = total_size_bytes / (1024 ** 3)
        
        return size_gb

    def _calculate_downloaded_size(self, download_dir: Path) -> float:
        """
        Calculate total size of downloaded files in GB.
        
        Args:
            download_dir: Path to directory containing downloaded files
            
        Returns:
            Total size in GB
        """
        total_size_bytes = 0
        
        try:
            for file_path in download_dir.rglob("*"):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    total_size_bytes += file_size
        except Exception as e:
            logger.warning(f"Error calculating downloaded size: {e}")
        
        # Convert bytes to GB
        size_gb = total_size_bytes / (1024 ** 3)
        return size_gb

    def _extract_metadata(
        self,
        hf_model_id: str,
        info,
    ) -> dict:
        """Extract metadata from Hugging Face model info."""
        metadata = {
            "source": "huggingface",
            "huggingface_model_id": hf_model_id,
            "description": f"Model imported from Hugging Face: {hf_model_id}",
        }

        # Add available fields from model info
        if hasattr(info, "model_type"):
            metadata["architecture"] = info.model_type
        if hasattr(info, "library_name"):
            metadata["framework"] = info.library_name
        if hasattr(info, "tags") and info.tags:
            metadata["tags"] = list(info.tags)
        if hasattr(info, "pipeline_tag"):
            metadata["pipeline_tag"] = info.pipeline_tag
        if hasattr(info, "author"):
            metadata["author"] = info.author

        # Try to get model card content
        try:
            from huggingface_hub import hf_hub_download

            readme_path = hf_hub_download(
                repo_id=hf_model_id,
                filename="README.md",
                repo_type="model",
            )
            if os.path.exists(readme_path):
                with open(readme_path, "r", encoding="utf-8") as f:
                    metadata["readme"] = f.read()[:5000]  # Limit to first 5000 chars
        except Exception:
            pass  # README is optional

        return metadata

