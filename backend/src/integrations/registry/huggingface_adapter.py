"""Hugging Face Hub adapter implementation for model registry.

Implements the RegistryAdapter interface using Hugging Face Hub.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID

from integrations.registry.interface import RegistryAdapter
from integrations.error_handler import (
    handle_tool_errors,
    wrap_tool_error,
    ToolUnavailableError,
    ToolOperationError,
)
from core.clients.object_store import get_object_store_client
from core.settings import get_settings

logger = logging.getLogger(__name__)


class HuggingFaceAdapter(RegistryAdapter):
    """Hugging Face Hub adapter for model registry."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Hugging Face adapter.
        
        Args:
            config: Configuration dictionary with:
                - token: Optional Hugging Face API token
                - cache_dir: Cache directory for downloads
                - enabled: Whether adapter is enabled
        """
        super().__init__(config)
        self.token = config.get("token")
        self.cache_dir = config.get("cache_dir", "/tmp/hf_cache")
        self.settings = get_settings()
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def is_available(self) -> bool:
        """Check if Hugging Face Hub is available."""
        try:
            from huggingface_hub import HfApi
            
            api = HfApi(token=self.token)
            # Try a simple API call
            api.list_models(limit=1)
            return True
        except Exception as e:
            logger.debug(f"Hugging Face Hub availability check failed: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on Hugging Face Hub."""
        try:
            from huggingface_hub import HfApi
            
            api = HfApi(token=self.token)
            # Try a simple API call
            models = api.list_models(limit=1)
            
            return {
                "status": "healthy",
                "message": "Hugging Face Hub is available",
                "details": {
                    "api_accessible": True,
                    "cache_dir": self.cache_dir,
                },
            }
        except Exception as e:
            return {
                "status": "unavailable",
                "message": f"Hugging Face Hub health check failed: {str(e)}",
                "details": {"error": str(e)},
            }
    
    @handle_tool_errors("Hugging Face Hub", "Failed to import model")
    def import_model(
        self,
        registry_model_id: str,
        model_catalog_id: UUID,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import a model from Hugging Face Hub."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Hugging Face Hub integration is disabled",
                tool_name="huggingface",
            )
        
        # Normalize version: empty string or whitespace-only should be None
        # Hugging Face Hub uses None to mean "default branch" (usually "main")
        if version is not None:
            version = version.strip()
            if not version:
                version = None
        
        try:
            from huggingface_hub import snapshot_download, model_info, HfApi
            
            # Get model info
            logger.info(f"Fetching model info from Hugging Face: {registry_model_id}, revision={version or 'default'}")
            info = model_info(registry_model_id, token=self.token, revision=version)
            
            # Build repository URL
            repo_url = f"https://huggingface.co/{registry_model_id}"
            
            # Check model size
            model_size_gb = self._calculate_model_size(info)
            max_size_gb = self.settings.huggingface_max_download_size_gb
            
            if max_size_gb > 0 and model_size_gb > 0 and model_size_gb > max_size_gb:
                raise ValueError(
                    f"Model size ({model_size_gb:.2f} GB) exceeds maximum allowed size ({max_size_gb:.2f} GB)"
                )
            
            # Download model files
            with tempfile.TemporaryDirectory() as temp_dir:
                download_dir = Path(temp_dir) / "model"
                
                logger.info(f"Downloading model from Hugging Face: {registry_model_id}")
                snapshot_download(
                    repo_id=registry_model_id,
                    local_dir=str(download_dir),
                    token=self.token,
                    revision=version,
                    local_dir_use_symlinks=False,
                    cache_dir=self.cache_dir,
                )
                
                # Verify downloaded size
                downloaded_size_gb = self._calculate_downloaded_size(download_dir)
                if max_size_gb > 0 and downloaded_size_gb > max_size_gb:
                    raise ValueError(
                        f"Downloaded model size ({downloaded_size_gb:.2f} GB) exceeds maximum allowed size ({max_size_gb:.2f} GB)"
                    )
                
                # Upload to object storage
                storage_uri = self._upload_to_storage(
                    model_id=str(model_catalog_id),
                    version=version or "latest",
                    local_dir=download_dir,
                )
            
            # Extract metadata
            metadata = self._extract_metadata(registry_model_id, info)
            metadata["model_size_gb"] = round(downloaded_size_gb, 2)
            
            return {
                "registry_model_id": registry_model_id,
                "registry_repo_url": repo_url,
                "registry_version": version or info.sha if hasattr(info, "sha") else None,
                "registry_metadata": metadata,
                "storage_uri": storage_uri,
            }
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="huggingface",
                operation="import_model",
                context={"registry_model_id": registry_model_id, "version": version},
            )
    
    @handle_tool_errors("Hugging Face Hub", "Failed to export model")
    def export_model(
        self,
        model_catalog_id: UUID,
        registry_model_id: str,
        model_uri: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Export a model to Hugging Face Hub."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Hugging Face Hub integration is disabled",
                tool_name="huggingface",
            )
        
        if not self.token:
            raise ToolUnavailableError(
                message="Hugging Face API token is required for exporting models",
                tool_name="huggingface",
            )
        
        try:
            from huggingface_hub import HfApi, upload_folder
            from core.clients.object_store import get_object_store_client
            
            api = HfApi(token=self.token)
            
            # Create repository if it doesn't exist
            try:
                api.create_repo(repo_id=registry_model_id, exist_ok=True, repo_type="model")
            except Exception as e:
                logger.warning(f"Repository creation check failed: {e}")
            
            # Download model from object storage to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                local_dir = Path(temp_dir) / "model"
                local_dir.mkdir(parents=True, exist_ok=True)
                
                # Parse storage URI (s3://bucket/path)
                if model_uri.startswith("s3://"):
                    parts = model_uri[5:].split("/", 1)
                    bucket = parts[0]
                    prefix = parts[1] if len(parts) > 1 else ""
                    
                    # Download from S3
                    s3_client = get_object_store_client()
                    self._download_from_storage(s3_client, bucket, prefix, local_dir)
                else:
                    raise ValueError(f"Unsupported storage URI format: {model_uri}")
                
                # Upload to Hugging Face Hub
                logger.info(f"Uploading model to Hugging Face Hub: {registry_model_id}")
                api.upload_folder(
                    folder_path=str(local_dir),
                    repo_id=registry_model_id,
                    repo_type="model",
                    token=self.token,
                )
                
                # Upload model card if provided
                if metadata:
                    self._upload_model_card(api, registry_model_id, metadata)
            
            repo_url = f"https://huggingface.co/{registry_model_id}"
            
            return {
                "registry_model_id": registry_model_id,
                "registry_repo_url": repo_url,
                "registry_version": "main",  # Default branch
            }
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="huggingface",
                operation="export_model",
                context={"registry_model_id": registry_model_id, "model_uri": model_uri},
            )
    
    @handle_tool_errors("Hugging Face Hub", "Failed to get model metadata")
    def get_model_metadata(
        self,
        registry_model_id: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get model metadata from Hugging Face Hub."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Hugging Face Hub integration is disabled",
                tool_name="huggingface",
            )
        
        # Normalize version: empty string or whitespace-only should be None
        if version is not None:
            version = version.strip()
            if not version:
                version = None
        
        try:
            from huggingface_hub import model_info, HfApi
            
            info = model_info(registry_model_id, token=self.token, revision=version)
            api = HfApi(token=self.token)
            
            # Get model card
            model_card = None
            try:
                from huggingface_hub import hf_hub_download
                readme_path = hf_hub_download(
                    repo_id=registry_model_id,
                    filename="README.md",
                    repo_type="model",
                    revision=version,
                    token=self.token,
                )
                if os.path.exists(readme_path):
                    with open(readme_path, "r", encoding="utf-8") as f:
                        model_card = f.read()
            except Exception:
                pass  # README is optional
            
            return {
                "model_id": registry_model_id,
                "version": version or (info.sha if hasattr(info, "sha") else None),
                "model_card": model_card,
                "license": getattr(info, "cardData", {}).get("license", None) if hasattr(info, "cardData") else None,
                "tags": list(info.tags) if hasattr(info, "tags") and info.tags else [],
                "downloads": getattr(info, "downloads", 0),
                "likes": getattr(info, "likes", 0),
                "pipeline_tag": getattr(info, "pipeline_tag", None),
                "library_name": getattr(info, "library_name", None),
                "model_type": getattr(info, "model_type", None),
            }
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="huggingface",
                operation="get_model_metadata",
                context={"registry_model_id": registry_model_id, "version": version},
            )
    
    @handle_tool_errors("Hugging Face Hub", "Failed to check updates")
    def check_updates(
        self,
        registry_model_id: str,
        current_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check if model has updates in Hugging Face Hub."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Hugging Face Hub integration is disabled",
                tool_name="huggingface",
            )
        
        try:
            from huggingface_hub import model_info, HfApi
            
            # Get latest model info
            latest_info = model_info(registry_model_id, token=self.token)
            latest_version = latest_info.sha if hasattr(latest_info, "sha") else None
            
            has_updates = False
            if current_version and latest_version:
                has_updates = current_version != latest_version
            
            return {
                "has_updates": has_updates,
                "latest_version": latest_version,
                "current_version": current_version,
                "changelog": [],  # Hugging Face doesn't provide changelog API
            }
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="huggingface",
                operation="check_updates",
                context={"registry_model_id": registry_model_id, "current_version": current_version},
            )
    
    @handle_tool_errors("Hugging Face Hub", "Failed to search models")
    def search_models(
        self,
        query: str,
        limit: int = 20,
        task: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for models in Hugging Face Hub."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Hugging Face Hub integration is disabled",
                tool_name="huggingface",
            )
        
        try:
            from huggingface_hub import HfApi
            
            api = HfApi(token=self.token)
            
            # Build search parameters
            search_params: Dict[str, Any] = {
                "search": query,
                "limit": limit,
            }
            if task:
                search_params["pipeline_tag"] = task
            
            # Search models
            models = api.list_models(**search_params)
            
            results = []
            for model in models:
                results.append({
                    "model_id": model.id,
                    "author": model.author if hasattr(model, "author") else None,
                    "downloads": model.downloads if hasattr(model, "downloads") else 0,
                    "likes": model.likes if hasattr(model, "likes") else 0,
                    "pipeline_tag": model.pipeline_tag if hasattr(model, "pipeline_tag") else None,
                    "library_name": model.library_name if hasattr(model, "library_name") else None,
                    "tags": list(model.tags) if hasattr(model, "tags") and model.tags else [],
                })
            
            return results
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="huggingface",
                operation="search_models",
                context={"query": query, "limit": limit, "task": task},
            )
    
    def _calculate_model_size(self, info) -> float:
        """Calculate total model size in GB from Hugging Face model info."""
        total_size_bytes = 0
        
        if hasattr(info, "siblings"):
            for sibling in info.siblings:
                size = None
                if hasattr(sibling, "size") and sibling.size is not None:
                    size = sibling.size
                elif hasattr(sibling, "file") and hasattr(sibling.file, "size"):
                    size = sibling.file.size
                elif hasattr(sibling, "__dict__"):
                    size = sibling.__dict__.get("size")
                
                if size:
                    total_size_bytes += size
        
        return total_size_bytes / (1024 ** 3)
    
    def _calculate_downloaded_size(self, download_dir: Path) -> float:
        """Calculate total size of downloaded files in GB."""
        total_size_bytes = 0
        
        try:
            for file_path in download_dir.rglob("*"):
                if file_path.is_file():
                    total_size_bytes += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"Error calculating downloaded size: {e}")
        
        return total_size_bytes / (1024 ** 3)
    
    def _extract_metadata(
        self,
        registry_model_id: str,
        info,
    ) -> Dict[str, Any]:
        """Extract metadata from Hugging Face model info."""
        metadata: Dict[str, Any] = {
            "source": "huggingface",
            "huggingface_model_id": registry_model_id,
        }
        
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
        
        # Try to infer model_family from model_type or model_id
        model_family = self._infer_model_family(registry_model_id, info)
        if model_family:
            metadata["model_family"] = model_family
        
        # Try to get model card
        try:
            from huggingface_hub import hf_hub_download
            readme_path = hf_hub_download(
                repo_id=registry_model_id,
                filename="README.md",
                repo_type="model",
                token=self.token,
            )
            if os.path.exists(readme_path):
                with open(readme_path, "r", encoding="utf-8") as f:
                    metadata["readme"] = f.read()[:5000]  # Limit to first 5000 chars
        except Exception:
            pass  # README is optional
        
        return metadata
    
    def _infer_model_family(
        self,
        registry_model_id: str,
        info,
    ) -> Optional[str]:
        """Infer model_family from Hugging Face model info.
        
        Args:
            registry_model_id: Model ID in registry
            info: Hugging Face model info object
            
        Returns:
            Inferred model_family or None
        """
        # Supported model families from training-serving-spec.md
        supported_families = {"llama", "mistral", "gemma", "bert"}
        
        # Try to infer from model_type
        if hasattr(info, "model_type") and info.model_type:
            model_type_lower = info.model_type.lower()
            for family in supported_families:
                if family in model_type_lower:
                    return family
        
        # Try to infer from model_id (e.g., "meta-llama/Llama-2-7b-chat-hf")
        model_id_lower = registry_model_id.lower()
        for family in supported_families:
            if family in model_id_lower:
                return family
        
        # Try to infer from tags
        if hasattr(info, "tags") and info.tags:
            tags_lower = [tag.lower() for tag in info.tags]
            for family in supported_families:
                if any(family in tag for tag in tags_lower):
                    return family
        
        return None
    
    def _upload_to_storage(
        self,
        model_id: str,
        version: str,
        local_dir: Path,
    ) -> str:
        """Upload model files to object storage."""
        s3_client = get_object_store_client()
        bucket_name = self.settings.object_store_bucket or self.settings.training_namespace
        
        storage_path = f"models/{model_id}/{version}/"
        
        files_to_upload = []
        for file_path in local_dir.rglob("*"):
            if file_path.is_file():
                files_to_upload.append(file_path)
        
        logger.info(f"Uploading {len(files_to_upload)} files to object storage...")
        
        for file_path in files_to_upload:
            relative_path = file_path.relative_to(local_dir)
            object_key = f"{storage_path}{relative_path}".replace("\\", "/")
            
            with open(file_path, "rb") as f:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=f,
                )
        
        return f"s3://{bucket_name}/{storage_path}"
    
    def _download_from_storage(
        self,
        s3_client,
        bucket: str,
        prefix: str,
        local_dir: Path,
    ) -> None:
        """Download model files from object storage."""
        # List all objects with prefix
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        for page in pages:
            if "Contents" not in page:
                continue
            
            for obj in page["Contents"]:
                key = obj["Key"]
                relative_path = key[len(prefix):].lstrip("/")
                local_path = local_dir / relative_path
                
                # Create parent directories
                local_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Download file
                s3_client.download_file(bucket, key, str(local_path))
    
    def _upload_model_card(
        self,
        api,
        registry_model_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        """Upload model card (README.md) to Hugging Face Hub."""
        try:
            from huggingface_hub import upload_file
            
            # Create README content from metadata
            readme_content = self._generate_readme(metadata)
            
            # Write to temp file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
                f.write(readme_content)
                readme_path = f.name
            
            try:
                # Upload README
                upload_file(
                    path_or_fileobj=readme_path,
                    path_in_repo="README.md",
                    repo_id=registry_model_id,
                    repo_type="model",
                    token=self.token,
                )
            finally:
                os.unlink(readme_path)
        except Exception as e:
            logger.warning(f"Failed to upload model card: {e}")
    
    def _generate_readme(self, metadata: Dict[str, Any]) -> str:
        """Generate README.md content from metadata."""
        lines = ["# Model"]
        
        if "name" in metadata:
            lines.append(f"\n## {metadata['name']}")
        
        if "description" in metadata:
            lines.append(f"\n{metadata['description']}")
        
        if "license" in metadata:
            lines.append(f"\n## License\n{metadata['license']}")
        
        if "tags" in metadata and metadata["tags"]:
            lines.append(f"\n## Tags\n{', '.join(metadata['tags'])}")
        
        return "\n".join(lines)

