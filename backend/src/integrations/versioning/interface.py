"""Data versioning adapter interface.

Defines the interface for data versioning adapters (DVC, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID

from integrations.base_adapter import BaseAdapter


class VersioningAdapter(BaseAdapter):
    """Interface for data versioning adapters."""
    
    @abstractmethod
    def create_version(
        self,
        dataset_record_id: UUID,
        dataset_uri: str,
        version_tag: Optional[str] = None,
        parent_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new dataset version.
        
        Args:
            dataset_record_id: Platform dataset record ID
            dataset_uri: Storage URI of the dataset
            version_tag: Optional human-readable version tag
            parent_version_id: Optional parent version ID for lineage
        
        Returns:
            Dictionary with version information:
            {
                "version_id": str,
                "version_tag": str | None,
                "checksum": str,
                "storage_uri": str,
                "file_count": int,
                "total_size_bytes": int,
                "compression_ratio": float | None
            }
        """
        pass
    
    @abstractmethod
    def get_version(
        self,
        version_id: str,
        dataset_record_id: UUID,
    ) -> Dict[str, Any]:
        """Get version information.
        
        Args:
            version_id: Version identifier
            dataset_record_id: Platform dataset record ID
        
        Returns:
            Dictionary with version details
        """
        pass
    
    @abstractmethod
    def list_versions(
        self,
        dataset_record_id: UUID,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """List all versions for a dataset.
        
        Args:
            dataset_record_id: Platform dataset record ID
            limit: Maximum number of versions to return
        
        Returns:
            List of version dictionaries
        """
        pass
    
    @abstractmethod
    def calculate_diff(
        self,
        version_id: str,
        base_version_id: str,
        dataset_record_id: UUID,
    ) -> Dict[str, Any]:
        """Calculate diff between two versions.
        
        Args:
            version_id: Target version identifier
            base_version_id: Base version identifier for comparison
            dataset_record_id: Platform dataset record ID
        
        Returns:
            Dictionary with diff information:
            {
                "added_files": list,
                "removed_files": list,
                "modified_files": list,
                "added_rows": int,
                "removed_rows": int,
                "schema_changes": dict
            }
        """
        pass
    
    @abstractmethod
    def restore_version(
        self,
        version_id: str,
        dataset_record_id: UUID,
        target_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restore dataset to a specific version.
        
        Args:
            version_id: Version identifier to restore
            dataset_record_id: Platform dataset record ID
            target_uri: Optional target storage URI (defaults to dataset URI)
        
        Returns:
            Dictionary with restore information:
            {
                "restored_uri": str,
                "version_id": str
            }
        """
        pass
    
    @abstractmethod
    def get_lineage(
        self,
        version_id: str,
        dataset_record_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Get version lineage (ancestors and descendants).
        
        Args:
            version_id: Version identifier
            dataset_record_id: Platform dataset record ID
        
        Returns:
            List of version dictionaries in lineage order
        """
        pass

