"""Model registry service for managing open-source registry integrations.

Manages model import/export, registry links, and metadata synchronization
with open-source model registries (Hugging Face Hub, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import select

from catalog import models as catalog_models
from catalog.repositories import ModelCatalogRepository
from integrations.registry.interface import RegistryAdapter
from integrations.registry.huggingface_adapter import HuggingFaceAdapter
from services.integration_config import IntegrationConfigService
from integrations.error_handler import ToolUnavailableError

logger = logging.getLogger(__name__)


class ModelRegistryService:
    """Service for managing model registry integrations."""
    
    def __init__(self, session: Session):
        """Initialize service with database session.
        
        Args:
            session: Database session
        """
        self.session = session
        self.catalog_repo = ModelCatalogRepository(session)
        self.config_service = IntegrationConfigService(session)
        self._adapters: Dict[str, RegistryAdapter] = {}
    
    def _get_adapter(self, registry_type: str) -> Optional[RegistryAdapter]:
        """Get or create registry adapter.
        
        Args:
            registry_type: Registry type ("huggingface", "modelscope", etc.)
        
        Returns:
            Registry adapter instance or None if not available
        """
        if registry_type not in self._adapters:
            config = self.config_service.get_config("registry", registry_type)
            if not config or not config.get("enabled"):
                logger.debug(f"Registry {registry_type} is not enabled")
                return None
            
            try:
                if registry_type == "huggingface":
                    adapter_config = {
                        "enabled": config["enabled"],
                        **config.get("config", {}),
                    }
                    adapter = HuggingFaceAdapter(adapter_config)
                    # Graceful degradation: 어댑터가 활성화되어 있지만 실제로는
                    # 외부 서비스에 접근할 수 없는 경우, 사용하지 않도록 함.
                    if not adapter.is_available():
                        logger.warning(
                            "Hugging Face Hub is configured but not available; "
                            "registry integration will gracefully degrade."
                        )
                        return None
                    self._adapters[registry_type] = adapter
                else:
                    logger.warning(f"Unsupported registry type: {registry_type}")
                    return None
            except Exception as e:
                logger.warning(f"Failed to initialize {registry_type} adapter: {e}")
                return None
        
        return self._adapters.get(registry_type)
    
    def import_model_from_registry(
        self,
        registry_type: str,
        registry_model_id: str,
        name: Optional[str] = None,
        version: str = "1.0.0",
        model_type: str = "base",
        owner_team: str = "ml-platform",
        registry_version: Optional[str] = None,
        model_family: Optional[str] = None,
    ) -> catalog_models.ModelCatalogEntry:
        """Import a model from an open-source registry.
        
        Args:
            registry_type: Registry type ("huggingface", etc.)
            registry_model_id: Model ID in registry (e.g., "microsoft/DialoGPT-medium")
            name: Optional model name (defaults to registry model ID)
            version: Model version in platform catalog
            model_type: Model type ("base", "fine-tuned", "external")
            owner_team: Owner team name
            registry_version: Optional specific version/tag in registry
        
        Returns:
            Created ModelCatalogEntry
        
        Raises:
            ValueError: If model already exists or import fails
            ToolUnavailableError: If registry adapter is not available
        """
        # Get adapter
        adapter = self._get_adapter(registry_type)
        if not adapter or not adapter.is_enabled():
            raise ToolUnavailableError(
                message=f"Registry {registry_type} is not enabled or available",
                tool_name=registry_type,
            )
        
        # Generate model name if not provided
        if not name:
            name = registry_model_id.split("/")[-1].replace("-", "_").lower()
        
        # Check if model already exists
        existing = self.catalog_repo.get_by_name_type_version(name, model_type, version)
        if existing:
            raise ValueError(
                f"Model with name '{name}', type '{model_type}', and version '{version}' already exists"
            )
        
        # Create catalog entry first to get model ID
        model_id = uuid4()
        logger.info(f"Creating catalog entry for model: {name}")
        
        # Get model metadata first (without downloading) to determine model_family
        try:
            metadata_info = adapter.get_model_metadata(
                registry_model_id=registry_model_id,
                version=registry_version,
            )
            # Extract basic metadata for initial registration
            initial_metadata = {
                "source": "huggingface",
                "huggingface_model_id": registry_model_id,
                "registry_version": metadata_info.get("version"),
            }
        except Exception as e:
            logger.warning(f"Failed to get model metadata, using minimal metadata: {e}")
            initial_metadata = {
                "source": "huggingface",
                "huggingface_model_id": registry_model_id,
            }
        
        # Determine model_family: use provided value, or infer from model_id, or default
        if model_family:
            final_model_family = model_family
        else:
            # Try to infer from model_id
            model_id_lower = registry_model_id.lower()
            supported_families = ["llama", "mistral", "gemma", "bert"]
            inferred_family = None
            for family in supported_families:
                if family in model_id_lower:
                    inferred_family = family
                    break
            final_model_family = inferred_family or "llama"
            if not inferred_family:
                logger.warning(f"Could not determine model_family for {registry_model_id}, using 'llama' as default")
        
        # Create catalog entry first (without storage_uri - will be updated after download)
        entry = catalog_models.ModelCatalogEntry(
            id=model_id,
            name=name,
            version=version,
            type=model_type,
            owner_team=owner_team,
            model_metadata=initial_metadata,
            storage_uri=None,  # Will be set after download completes
            status="draft",
            model_family=final_model_family,
        )
        
        self.catalog_repo.save(entry)
        self.session.commit()
        self.session.refresh(entry)
        
        logger.info(f"Model entry created: {model_id}, download will be processed in background")
        
        # Return entry immediately - download will be processed in background
        return entry
    
    def download_and_update_model(
        self,
        model_id: UUID,
        registry_type: str,
        registry_model_id: str,
        registry_version: Optional[str] = None,
    ) -> None:
        """Download model from registry and update catalog entry in background.
        
        Args:
            model_id: Model catalog entry ID
            registry_type: Registry type ("huggingface", etc.)
            registry_model_id: Model ID in registry
            registry_version: Optional specific version/tag in registry
        """
        from core.database import SessionLocal
        from catalog.repositories import ModelCatalogRepository
        
        # Create new session for background task
        session = SessionLocal()
        try:
            # Create new service instance with new session
            background_service = ModelRegistryService(session)
            
            # Get adapter
            adapter = background_service._get_adapter(registry_type)
            if not adapter or not adapter.is_enabled():
                logger.error(f"Registry {registry_type} is not available for model {model_id}")
                return
            
            # Get model entry
            catalog_repo = ModelCatalogRepository(session)
            entry = catalog_repo.get(model_id)
            if not entry:
                logger.error(f"Model entry {model_id} not found")
                return
            
            logger.info(f"Starting background download for model {model_id}: {registry_model_id}")
            
            # Import model (download and upload to storage)
            import_info = adapter.import_model(
                registry_model_id=registry_model_id,
                model_catalog_id=model_id,
                version=registry_version,
            )
            
            # Update entry with full metadata and storage_uri
            from sqlalchemy.orm.attributes import flag_modified
            
            registry_metadata = import_info.get("registry_metadata", {})
            entry.model_metadata.update(registry_metadata)
            entry.model_metadata["import_status"] = "completed"
            flag_modified(entry, "model_metadata")  # Tell SQLAlchemy that JSON field was modified
            
            entry.storage_uri = import_info.get("storage_uri")
            
            # Create registry link record
            registry_model = catalog_models.RegistryModel(
                id=uuid4(),
                model_catalog_id=model_id,
                registry_type=registry_type,
                registry_model_id=registry_model_id,
                registry_repo_url=import_info.get("registry_repo_url", ""),
                registry_version=import_info.get("registry_version"),
                imported=True,
                imported_at=datetime.utcnow(),
                registry_metadata=import_info.get("registry_metadata"),
                sync_status="synced",
                last_sync_check=datetime.utcnow(),
            )
            
            session.add(registry_model)
            session.commit()
            session.refresh(entry)
            session.refresh(registry_model)
            
            logger.info(f"Model download completed: {model_id}, storage_uri: {entry.storage_uri}")
            logger.info(f"Successfully imported model {model_id} from {registry_type}: {registry_model_id}")
        except Exception as e:
            # If download fails, update metadata to indicate error
            logger.error(f"Model download failed for {model_id}: {e}", exc_info=True)
            try:
                from sqlalchemy.orm.attributes import flag_modified
                catalog_repo = ModelCatalogRepository(session)
                entry = catalog_repo.get(model_id)
                if entry:
                    entry.model_metadata["import_error"] = str(e)
                    entry.model_metadata["import_status"] = "failed"
                    flag_modified(entry, "model_metadata")
                    session.commit()
            except Exception as update_error:
                logger.error(f"Failed to update error status for {model_id}: {update_error}")
        finally:
            session.close()
    
    def export_model_to_registry(
        self,
        model_catalog_id: UUID,
        registry_type: str,
        registry_model_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> catalog_models.RegistryModel:
        """Export a model to an open-source registry.
        
        Args:
            model_catalog_id: Platform catalog model ID
            registry_type: Registry type ("huggingface", etc.)
            registry_model_id: Target model ID in registry
            metadata: Optional model metadata (model card, license, etc.)
        
        Returns:
            Created RegistryModel entity
        
        Raises:
            ValueError: If model not found or export fails
            ToolUnavailableError: If registry adapter is not available
        """
        # Get catalog entry
        entry = self.catalog_repo.get(model_catalog_id)
        if not entry:
            raise ValueError(f"Model {model_catalog_id} not found")
        
        if not entry.storage_uri:
            raise ValueError(f"Model {model_catalog_id} has no storage URI")
        
        # Get adapter
        adapter = self._get_adapter(registry_type)
        if not adapter or not adapter.is_enabled():
            raise ToolUnavailableError(
                message=f"Registry {registry_type} is not enabled or available",
                tool_name=registry_type,
            )
        
        # Export model using adapter
        export_info = adapter.export_model(
            model_catalog_id=model_catalog_id,
            registry_model_id=registry_model_id,
            model_uri=entry.storage_uri,
            metadata=metadata or entry.model_metadata,
        )
        
        # Create or update registry link record
        existing_link = self.session.query(catalog_models.RegistryModel).filter(
            catalog_models.RegistryModel.model_catalog_id == model_catalog_id,
            catalog_models.RegistryModel.registry_type == registry_type,
            catalog_models.RegistryModel.registry_model_id == registry_model_id,
        ).first()
        
        if existing_link:
            # Update existing link
            existing_link.exported_at = datetime.utcnow()
            existing_link.registry_version = export_info.get("registry_version")
            existing_link.sync_status = "synced"
            existing_link.last_sync_check = datetime.utcnow()
            registry_model = existing_link
        else:
            # Create new link
            registry_model = catalog_models.RegistryModel(
                id=uuid4(),
                model_catalog_id=model_catalog_id,
                registry_type=registry_type,
                registry_model_id=registry_model_id,
                registry_repo_url=export_info.get("registry_repo_url", ""),
                registry_version=export_info.get("registry_version"),
                imported=False,
                exported_at=datetime.utcnow(),
                sync_status="synced",
                last_sync_check=datetime.utcnow(),
            )
            self.session.add(registry_model)
        
        self.session.commit()
        self.session.refresh(registry_model)
        
        logger.info(f"Successfully exported model {model_catalog_id} to {registry_type}: {registry_model_id}")
        return registry_model
    
    def get_registry_links(
        self,
        model_catalog_id: UUID,
    ) -> List[catalog_models.RegistryModel]:
        """Get all registry links for a catalog model.
        
        Args:
            model_catalog_id: Platform catalog model ID
        
        Returns:
            List of RegistryModel entities
        """
        stmt = select(catalog_models.RegistryModel).where(
            catalog_models.RegistryModel.model_catalog_id == model_catalog_id
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def get_registry_metadata(
        self,
        registry_type: str,
        registry_model_id: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get model metadata from registry.
        
        Args:
            registry_type: Registry type ("huggingface", etc.)
            registry_model_id: Model ID in registry
            version: Optional specific version/tag
        
        Returns:
            Dictionary with metadata
        
        Raises:
            ToolUnavailableError: If registry adapter is not available
        """
        adapter = self._get_adapter(registry_type)
        if not adapter or not adapter.is_enabled():
            raise ToolUnavailableError(
                message=f"Registry {registry_type} is not enabled or available",
                tool_name=registry_type,
            )
        
        return adapter.get_model_metadata(
            registry_model_id=registry_model_id,
            version=version,
        )
    
    def check_registry_updates(
        self,
        model_catalog_id: UUID,
        registry_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check if registry models have updates available.
        
        Args:
            model_catalog_id: Platform catalog model ID
            registry_type: Optional registry type filter
        
        Returns:
            Dictionary with update information:
            {
                "updates_available": bool,
                "registry_links": [
                    {
                        "registry_type": str,
                        "registry_model_id": str,
                        "has_updates": bool,
                        "latest_version": str,
                        "current_version": str,
                    }
                ]
            }
        """
        # Get all registry links for this model
        links = self.get_registry_links(model_catalog_id)
        
        if registry_type:
            links = [link for link in links if link.registry_type == registry_type]
        
        updates_info = {
            "updates_available": False,
            "registry_links": [],
        }
        
        for link in links:
            adapter = self._get_adapter(link.registry_type)
            if not adapter or not adapter.is_enabled():
                continue
            
            try:
                update_info = adapter.check_updates(
                    registry_model_id=link.registry_model_id,
                    current_version=link.registry_version,
                )
                
                has_updates = update_info.get("has_updates", False)
                if has_updates:
                    updates_info["updates_available"] = True
                
                updates_info["registry_links"].append({
                    "registry_type": link.registry_type,
                    "registry_model_id": link.registry_model_id,
                    "has_updates": has_updates,
                    "latest_version": update_info.get("latest_version"),
                    "current_version": link.registry_version,
                })
                
                # Update last_sync_check
                link.last_sync_check = datetime.utcnow()
                if has_updates:
                    link.sync_status = "out_of_sync"
                else:
                    link.sync_status = "synced"
                
            except Exception as e:
                logger.warning(f"Failed to check updates for {link.registry_model_id}: {e}")
                updates_info["registry_links"].append({
                    "registry_type": link.registry_type,
                    "registry_model_id": link.registry_model_id,
                    "has_updates": False,
                    "error": str(e),
                })
        
        self.session.commit()
        return updates_info
    
    def search_registry_models(
        self,
        registry_type: str,
        query: str,
        limit: int = 20,
        task: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for models in registry.
        
        Args:
            registry_type: Registry type ("huggingface", etc.)
            query: Search query string
            limit: Maximum number of results
            task: Optional task filter (e.g., "text-generation")
        
        Returns:
            List of model dictionaries
        
        Raises:
            ToolUnavailableError: If registry adapter is not available
        """
        adapter = self._get_adapter(registry_type)
        if not adapter or not adapter.is_enabled():
            raise ToolUnavailableError(
                message=f"Registry {registry_type} is not enabled or available",
                tool_name=registry_type,
            )
        
        return adapter.search_models(
            query=query,
            limit=limit,
            task=task,
        )

