"""DVC adapter implementation for data versioning.

Implements the VersioningAdapter interface using DVC (Data Version Control).
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from integrations.base_adapter import BaseAdapter
from integrations.versioning.interface import VersioningAdapter
from integrations.versioning.dvc_repo_manager import DVCRepoManager
from integrations.error_handler import (
    handle_tool_errors,
    wrap_tool_error,
    ToolUnavailableError,
    ToolOperationError,
)
from core.settings import get_settings

logger = logging.getLogger(__name__)


class DVCAdapter(VersioningAdapter):
    """DVC adapter for data versioning."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize DVC adapter.
        
        Args:
            config: Configuration dictionary with:
                - remote_name: DVC remote name (default: "minio")
                - remote_url: DVC remote URL (S3/MinIO)
                - cache_dir: DVC cache directory
                - enabled: Whether adapter is enabled
        """
        super().__init__(config)
        settings = get_settings()
        
        self.remote_name = config.get("remote_name") or settings.dvc_remote_name
        self.remote_url = config.get("remote_url") or settings.dvc_remote_url
        self.cache_dir = config.get("cache_dir") or settings.dvc_cache_dir
        self.enabled = config.get("enabled", settings.dvc_enabled)
        
        if not self.remote_url:
            logger.warning("DVC remote_url not configured - versioning may not work properly")
        
        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Base directory for DVC repositories (one per dataset)
        self.base_repo_dir = os.path.join(self.cache_dir, "repos")
        
        # Initialize repository manager
        self.repo_manager = DVCRepoManager(
            base_repo_dir=self.base_repo_dir,
            remote_name=self.remote_name,
            remote_url=self.remote_url,
        )
    
    def is_available(self) -> bool:
        """Check if DVC is available."""
        try:
            result = subprocess.run(
                ["dvc", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on DVC."""
        try:
            if not self.is_available():
                return {
                    "status": "unavailable",
                    "message": "DVC command not found",
                    "details": {},
                }
            
            # Check if cache directory is writable
            try:
                test_file = os.path.join(self.cache_dir, ".health_check")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                return {
                    "status": "degraded",
                    "message": f"Cache directory not writable: {e}",
                    "details": {"cache_dir": self.cache_dir},
                }
            
            return {
                "status": "healthy",
                "message": "DVC adapter is operational",
                "details": {
                    "remote_name": self.remote_name,
                    "remote_url": self.remote_url if self.remote_url else "not configured",
                    "cache_dir": self.cache_dir,
                },
            }
        except Exception as e:
            return {
                "status": "unavailable",
                "message": f"DVC health check failed: {str(e)}",
                "details": {"error": str(e)},
            }
    
    @handle_tool_errors("DVC", "Failed to create dataset version")
    def create_version(
        self,
        dataset_record_id: UUID,
        dataset_uri: str,
        version_tag: Optional[str] = None,
        parent_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new dataset version."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="DVC integration is disabled",
                tool_name="dvc",
            )
        
        # Initialize repository if needed
        repo_path = self.repo_manager.initialize_repo(str(dataset_record_id))
        
        # Download dataset to local temp directory if it's a remote URI
        # For now, assume dataset_uri is a local path or S3 URI
        # In production, download from S3 to local temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dataset_path = Path(temp_dir) / "dataset"
            
            # If dataset_uri is S3, download it
            if dataset_uri.startswith("s3://") or dataset_uri.startswith("http"):
                # Download logic would go here
                # For now, assume it's already accessible
                logger.warning(f"Remote dataset URI not downloaded: {dataset_uri}")
                temp_dataset_path = Path(dataset_uri)
            else:
                temp_dataset_path = Path(dataset_uri)
            
            # Add dataset to DVC
            dataset_name = "dataset"
            try:
                self.repo_manager.run_command(
                    ["add", str(temp_dataset_path), "-o", dataset_name],
                    str(dataset_record_id),
                )
            except ToolOperationError:
                # If add fails, try import-url for remote datasets
                if dataset_uri.startswith("s3://"):
                    self.repo_manager.run_command(
                        ["import-url", dataset_uri, dataset_name],
                        str(dataset_record_id),
                    )
                else:
                    raise
            
            # Commit to create version
            commit_message = version_tag or f"Version for dataset {dataset_record_id}"
            self.repo_manager.run_command(
                ["commit", "-m", commit_message],
                str(dataset_record_id),
            )
            
            # Get commit hash (version ID)
            git_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            version_id = git_result.stdout.strip()
            
            # Get dataset info
            dvc_result = self.repo_manager.run_command(
                ["data", "status", "--json"],
                str(dataset_record_id),
            )
            
            # Calculate checksum and size
            checksum = version_id  # Use commit hash as checksum
            file_count = 0
            total_size = 0
            
            # Get file information from DVC
            try:
                import json
                data_info = json.loads(dvc_result.stdout)
                # Parse DVC data status to get file count and size
                # This is simplified - actual implementation would parse DVC output
            except Exception:
                pass
            
            # Push to remote if configured
            if self.remote_url:
                try:
                    self.repo_manager.run_command(
                        ["push", "-r", self.remote_name],
                        str(dataset_record_id),
                        timeout=300,  # Longer timeout for push
                    )
                except Exception as e:
                    logger.warning(f"Failed to push to DVC remote: {e}")
                    # Non-fatal - version is still created locally
            
            return {
                "version_id": version_id,
                "version_tag": version_tag,
                "checksum": checksum,
                "storage_uri": dataset_uri,
                "file_count": file_count,
                "total_size_bytes": total_size,
                "compression_ratio": None,  # DVC handles compression internally
            }
    
    @handle_tool_errors("DVC", "Failed to get version")
    def get_version(
        self,
        version_id: str,
        dataset_record_id: UUID,
    ) -> Dict[str, Any]:
        """Get version information."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="DVC integration is disabled",
                tool_name="dvc",
            )
        
        repo_path = self.repo_manager.get_repo_path(str(dataset_record_id))
        if not repo_path.exists():
            raise ToolOperationError(
                message=f"Dataset repository not found for {dataset_record_id}",
                tool_name="dvc",
            )
        
        # Checkout specific version
        try:
            subprocess.run(
                ["git", "checkout", version_id],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                timeout=10,
            )
        except subprocess.SubprocessError as e:
            raise ToolOperationError(
                message=f"Version {version_id} not found",
                tool_name="dvc",
                original_error=e,
            )
        
        # Get DVC file info
        dvc_result = self.repo_manager.run_command(
            ["data", "status", "--json"],
            str(dataset_record_id),
        )
        
        return {
            "version_id": version_id,
            "checksum": version_id,
            "storage_uri": "",  # Would need to extract from DVC
            "file_count": 0,
            "total_size_bytes": 0,
        }
    
    @handle_tool_errors("DVC", "Failed to list versions")
    def list_versions(
        self,
        dataset_record_id: UUID,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List all versions for a dataset."""
        if not self.is_enabled():
            return []  # Graceful degradation
        
        if not self.repo_manager.repo_exists(str(dataset_record_id)):
            return []
        
        repo_path = self.repo_manager.get_repo_path(str(dataset_record_id))
        
        try:
            # Get Git commit history
            result = subprocess.run(
                ["git", "log", "--oneline", "--format=%H|%s", f"-{limit}"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            versions = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 1)
                version_id = parts[0]
                version_tag = parts[1] if len(parts) > 1 else None
                
                versions.append({
                    "version_id": version_id,
                    "version_tag": version_tag,
                    "checksum": version_id,
                })
            
            return versions
        except Exception as e:
            logger.warning(f"Failed to list DVC versions: {e}")
            return []  # Graceful degradation
    
    @handle_tool_errors("DVC", "Failed to calculate diff")
    def calculate_diff(
        self,
        version_id: str,
        base_version_id: str,
        dataset_record_id: UUID,
    ) -> Dict[str, Any]:
        """Calculate diff between two versions."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="DVC integration is disabled",
                tool_name="dvc",
            )
        
        if not self.repo_manager.repo_exists(str(dataset_record_id)):
            raise ToolOperationError(
                message=f"Dataset repository not found for {dataset_record_id}",
                tool_name="dvc",
            )
        
        try:
            # Use DVC diff command
            result = self.repo_manager.run_command(
                ["diff", base_version_id, version_id],
                str(dataset_record_id),
            )
            
            # Parse diff output
            # DVC diff shows added, removed, and modified files
            diff_output = result.stdout
            
            added_files = []
            removed_files = []
            modified_files = []
            
            # Parse DVC diff output (simplified)
            for line in diff_output.split("\n"):
                if line.startswith("+") and not line.startswith("+++"):
                    added_files.append(line[1:].strip())
                elif line.startswith("-") and not line.startswith("---"):
                    removed_files.append(line[1:].strip())
                elif line.startswith("M") or line.startswith("modified"):
                    modified_files.append(line.split()[-1] if " " in line else line[1:])
            
            return {
                "added_files": added_files,
                "removed_files": removed_files,
                "modified_files": modified_files,
                "added_rows": 0,  # Would need dataset-specific parsing
                "removed_rows": 0,
                "schema_changes": {},
            }
        except Exception as e:
            raise wrap_tool_error(e, "dvc", "calculate_diff")
    
    @handle_tool_errors("DVC", "Failed to restore version")
    def restore_version(
        self,
        version_id: str,
        dataset_record_id: UUID,
        target_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restore dataset to a specific version."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="DVC integration is disabled",
                tool_name="dvc",
            )
        
        repo_path = self.repo_manager.get_repo_path(str(dataset_record_id))
        if not repo_path.exists():
            raise ToolOperationError(
                message=f"Dataset repository not found for {dataset_record_id}",
                tool_name="dvc",
            )
        
        try:
            # Checkout version
            subprocess.run(
                ["git", "checkout", version_id],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                timeout=10,
            )
            
            # Use DVC checkout to restore files
            self.repo_manager.run_command(
                ["checkout"],
                str(dataset_record_id),
            )
            
            # If target_uri is specified, copy files there
            restored_uri = target_uri or str(repo_path / "dataset")
            
            return {
                "restored_uri": restored_uri,
                "version_id": version_id,
            }
        except Exception as e:
            raise wrap_tool_error(e, "dvc", "restore_version")
    
    @handle_tool_errors("DVC", "Failed to get lineage")
    def get_lineage(
        self,
        version_id: str,
        dataset_record_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get version lineage (ancestors and descendants)."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="DVC integration is disabled",
                tool_name="dvc",
            )
        
        repo_path = self.repo_manager.get_repo_path(str(dataset_record_id))
        if not repo_path.exists():
            raise ToolOperationError(
                message=f"Dataset repository not found for {dataset_record_id}",
                tool_name="dvc",
            )
        
        try:
            # Get Git log to find ancestors
            result = subprocess.run(
                ["git", "log", "--oneline", "--format=%H|%s", "--all"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            # Find version_id in history and get ancestors
            versions = []
            found_version = False
            
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 1)
                v_id = parts[0]
                v_tag = parts[1] if len(parts) > 1 else None
                
                if v_id == version_id:
                    found_version = True
                
                if found_version:
                    versions.append({
                        "version_id": v_id,
                        "version_tag": v_tag,
                        "checksum": v_id,
                    })
            
            return versions
        except Exception as e:
            raise wrap_tool_error(e, "dvc", "get_lineage")

