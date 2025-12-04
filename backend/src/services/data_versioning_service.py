"""Data versioning service.

Manages dataset versions and integrates with open-source versioning systems (DVC).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from catalog.models import DatasetVersion, DatasetRecord
from services.integration_config import IntegrationConfigService
from integrations.versioning.dvc_adapter import DVCAdapter
from integrations.error_handler import ToolUnavailableError

logger = logging.getLogger(__name__)


class DataVersioningService:
    """Service for managing data versioning."""
    
    def __init__(self, db: Session):
        """Initialize service with database session.
        
        Args:
            db: Database session
        """
        self.db = db
        self.config_service = IntegrationConfigService(db)
        self._adapter: Optional[DVCAdapter] = None
    
    def _get_adapter(self) -> Optional[DVCAdapter]:
        """Get or create data versioning adapter."""
        if self._adapter is None:
            config = self.config_service.get_config(
                integration_type="versioning",
                tool_name="dvc",
            )
            if config and config.get("enabled"):
                try:
                    self._adapter = DVCAdapter(config.get("config", {}))
                except Exception as e:
                    logger.warning(f"Failed to initialize DVC adapter: {e}")
                    return None
        return self._adapter
    
    def create_version(
        self,
        dataset_record_id: UUID,
        dataset_uri: str,
        version_tag: Optional[str] = None,
        parent_version_id: Optional[UUID] = None,
        created_by: str = "system",
    ) -> DatasetVersion:
        """Create a new dataset version.
        
        Args:
            dataset_record_id: Dataset record ID
            dataset_uri: Storage URI of the dataset
            version_tag: Optional human-readable version tag
            parent_version_id: Optional parent version ID for lineage
            created_by: User who created the version
            
        Returns:
            Created DatasetVersion entity
        """
        # Get dataset record
        dataset_record = self.db.get(DatasetRecord, dataset_record_id)
        if not dataset_record:
            raise ValueError(f"Dataset record {dataset_record_id} not found")
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled():
            logger.warning("Data versioning is disabled - creating version record without DVC")
            # Create version record without DVC integration
            version = DatasetVersion(
                id=uuid4(),
                dataset_record_id=dataset_record_id,
                versioning_system="none",
                version_id=str(uuid4()),
                parent_version_id=parent_version_id,
                version_tag=version_tag,
                checksum="",
                storage_uri=dataset_uri,
                file_count=0,
                total_size_bytes=0,
                created_at=datetime.utcnow(),
                created_by=created_by,
            )
            self.db.add(version)
            self.db.commit()
            self.db.refresh(version)
            return version
        
        # Create version using adapter
        try:
            adapter_result = adapter.create_version(
                dataset_record_id=dataset_record_id,
                dataset_uri=dataset_uri,
                version_tag=version_tag,
                parent_version_id=str(parent_version_id) if parent_version_id else None,
            )
            
            # Create database record
            version = DatasetVersion(
                id=uuid4(),
                dataset_record_id=dataset_record_id,
                versioning_system="dvc",
                version_id=adapter_result["version_id"],
                parent_version_id=UUID(adapter_result.get("parent_version_id")) if adapter_result.get("parent_version_id") else parent_version_id,
                version_tag=adapter_result.get("version_tag") or version_tag,
                checksum=adapter_result["checksum"],
                storage_uri=adapter_result["storage_uri"],
                file_count=adapter_result.get("file_count", 0),
                total_size_bytes=adapter_result.get("total_size_bytes", 0),
                compression_ratio=adapter_result.get("compression_ratio"),
                created_at=datetime.utcnow(),
                created_by=created_by,
            )
            self.db.add(version)
            self.db.commit()
            self.db.refresh(version)
            return version
        except ToolUnavailableError:
            logger.warning("DVC adapter unavailable - creating version record without DVC")
            # Fallback to basic version record
            version = DatasetVersion(
                id=uuid4(),
                dataset_record_id=dataset_record_id,
                versioning_system="none",
                version_id=str(uuid4()),
                parent_version_id=parent_version_id,
                version_tag=version_tag,
                checksum="",
                storage_uri=dataset_uri,
                file_count=0,
                total_size_bytes=0,
                created_at=datetime.utcnow(),
                created_by=created_by,
            )
            self.db.add(version)
            self.db.commit()
            self.db.refresh(version)
            return version
        except Exception as e:
            logger.error(f"Failed to create dataset version: {e}")
            raise
    
    def get_version(
        self,
        version_id: UUID,
        dataset_record_id: UUID,
    ) -> Optional[DatasetVersion]:
        """Get a dataset version.
        
        Args:
            version_id: Version ID
            dataset_record_id: Dataset record ID
            
        Returns:
            DatasetVersion entity or None if not found
        """
        version = self.db.query(DatasetVersion).filter(
            DatasetVersion.id == version_id,
            DatasetVersion.dataset_record_id == dataset_record_id,
        ).first()
        return version
    
    def list_versions(
        self,
        dataset_record_id: UUID,
        limit: int = 100,
    ) -> List[DatasetVersion]:
        """List all versions for a dataset.
        
        Args:
            dataset_record_id: Dataset record ID
            limit: Maximum number of versions to return
            
        Returns:
            List of DatasetVersion entities
        """
        versions = self.db.query(DatasetVersion).filter(
            DatasetVersion.dataset_record_id == dataset_record_id,
        ).order_by(
            DatasetVersion.created_at.desc()
        ).limit(limit).all()
        
        return list(versions)
    
    def calculate_diff(
        self,
        version_id: UUID,
        base_version_id: UUID,
        dataset_record_id: UUID,
    ) -> Dict[str, Any]:
        """Calculate diff between two versions.
        
        Args:
            version_id: Target version ID
            base_version_id: Base version ID for comparison
            dataset_record_id: Dataset record ID
            
        Returns:
            Dictionary with diff information
        """
        # Get versions from database
        version = self.get_version(version_id, dataset_record_id)
        base_version = self.get_version(base_version_id, dataset_record_id)
        
        if not version or not base_version:
            raise ValueError("One or both versions not found")
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled() or version.versioning_system != "dvc":
            # Return basic diff from database
            return {
                "added_files": [],
                "removed_files": [],
                "modified_files": [],
                "added_rows": 0,
                "removed_rows": 0,
                "schema_changes": {},
            }
        
        # Calculate diff using adapter
        try:
            diff_result = adapter.calculate_diff(
                version_id=version.version_id,
                base_version_id=base_version.version_id,
                dataset_record_id=dataset_record_id,
            )
            
            # Update version diff_summary if needed
            if not version.diff_summary:
                version.diff_summary = diff_result
                self.db.commit()
            
            return diff_result
        except Exception as e:
            logger.error(f"Failed to calculate diff: {e}")
            raise
    
    def restore_version(
        self,
        version_id: UUID,
        dataset_record_id: UUID,
        target_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Restore dataset to a specific version.
        
        Args:
            version_id: Version ID to restore
            dataset_record_id: Dataset record ID
            target_uri: Optional target storage URI
            
        Returns:
            Dictionary with restore information
        """
        # Get version from database
        version = self.get_version(version_id, dataset_record_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled() or version.versioning_system != "dvc":
            raise ValueError("DVC adapter not available for version restore")
        
        # Restore using adapter (graceful degradation on ToolUnavailableError)
        try:
            restore_result = adapter.restore_version(
                version_id=version.version_id,
                dataset_record_id=dataset_record_id,
                target_uri=target_uri,
            )
            return restore_result
        except ToolUnavailableError as e:
            logger.warning(f"DVC unavailable during restore, falling back gracefully: {e}")
            raise ValueError("Data versioning backend is currently unavailable")
        except Exception as e:
            logger.error(f"Failed to restore version: {e}")
            raise
    
    def get_lineage(
        self,
        version_id: UUID,
        dataset_record_id: UUID,
    ) -> List[DatasetVersion]:
        """Get version lineage (ancestors and descendants).
        
        Args:
            version_id: Version ID
            dataset_record_id: Dataset record ID
            
        Returns:
            List of DatasetVersion entities in lineage order
        """
        # Get version from database
        version = self.get_version(version_id, dataset_record_id)
        if not version:
            raise ValueError(f"Version {version_id} not found")
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled() or version.versioning_system != "dvc":
            # Return basic lineage from database (parent chain)
            lineage = []
            current = version
            while current:
                lineage.append(current)
                if current.parent_version_id:
                    current = self.get_version(current.parent_version_id, dataset_record_id)
                else:
                    break
            return lineage
        
        # Get lineage using adapter (graceful degradation on ToolUnavailableError)
        try:
            adapter_lineage = adapter.get_lineage(
                version_id=version.version_id,
                dataset_record_id=dataset_record_id,
            )
            
            # Map adapter lineage to database versions
            lineage = []
            for item in adapter_lineage:
                db_version = self.db.query(DatasetVersion).filter(
                    DatasetVersion.version_id == item["version_id"],
                    DatasetVersion.dataset_record_id == dataset_record_id,
                ).first()
                if db_version:
                    lineage.append(db_version)
            
            return lineage
        except ToolUnavailableError as e:
            logger.warning(f"DVC unavailable during lineage lookup, falling back to DB lineage: {e}")
        except Exception as e:
            logger.error(f"Failed to get lineage: {e}")
        
        # Fallback to database lineage
        lineage = []
        current = version
        while current:
            lineage.append(current)
            if current.parent_version_id:
                current = self.get_version(current.parent_version_id, dataset_record_id)
            else:
                break
        return lineage

