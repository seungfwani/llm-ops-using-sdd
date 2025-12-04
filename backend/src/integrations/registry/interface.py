"""Model registry adapter interface.

Defines the interface for model registry adapters (Hugging Face Hub, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID

from integrations.base_adapter import BaseAdapter


class RegistryAdapter(BaseAdapter):
    """Interface for model registry adapters."""
    
    @abstractmethod
    def import_model(
        self,
        registry_model_id: str,
        model_catalog_id: UUID,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Import a model from the registry.
        
        Args:
            registry_model_id: Model identifier in registry (e.g., "microsoft/DialoGPT-medium")
            model_catalog_id: Platform catalog entry ID
            version: Optional specific version/tag
        
        Returns:
            Dictionary with import information:
            {
                "registry_model_id": str,
                "registry_repo_url": str,
                "registry_version": str | None,
                "registry_metadata": dict,
                "storage_uri": str
            }
        """
        pass
    
    @abstractmethod
    def export_model(
        self,
        model_catalog_id: UUID,
        registry_model_id: str,
        model_uri: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Export a model to the registry.
        
        Args:
            model_catalog_id: Platform catalog entry ID
            registry_model_id: Target model identifier in registry
            model_uri: Storage URI of the model to export
            metadata: Optional model metadata (model card, license, etc.)
        
        Returns:
            Dictionary with export information:
            {
                "registry_model_id": str,
                "registry_repo_url": str,
                "registry_version": str
            }
        """
        pass
    
    @abstractmethod
    def get_model_metadata(
        self,
        registry_model_id: str,
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get model metadata from registry.
        
        Args:
            registry_model_id: Model identifier in registry
            version: Optional specific version/tag
        
        Returns:
            Dictionary with metadata:
            {
                "model_id": str,
                "version": str,
                "model_card": dict,
                "license": str,
                "tags": list,
                "downloads": int,
                "likes": int
            }
        """
        pass
    
    @abstractmethod
    def check_updates(
        self,
        registry_model_id: str,
        current_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check if model has updates in registry.
        
        Args:
            registry_model_id: Model identifier in registry
            current_version: Current version in platform
        
        Returns:
            Dictionary with update information:
            {
                "has_updates": bool,
                "latest_version": str,
                "current_version": str | None,
                "changelog": list
            }
        """
        pass
    
    @abstractmethod
    def search_models(
        self,
        query: str,
        limit: int = 20,
        task: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for models in registry.
        
        Args:
            query: Search query string
            limit: Maximum number of results
            task: Optional task filter (e.g., "text-generation", "text-classification")
        
        Returns:
            List of model dictionaries
        """
        pass

