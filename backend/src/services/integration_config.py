"""Integration configuration service.

Manages configuration for open-source tool integrations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
from sqlalchemy import select

from core.settings import get_settings

logger = logging.getLogger(__name__)


class IntegrationConfigService:
    """Service for managing integration configurations."""
    
    def __init__(self, db: Session):
        """Initialize service with database session.
        
        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
    
    def get_config(
        self,
        integration_type: str,
        tool_name: str,
        environment: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get integration configuration.
        
        Args:
            integration_type: Type of integration (experiment_tracking, serving, etc.)
            tool_name: Name of the tool (mlflow, kserve, etc.)
            environment: Optional environment (defaults to settings.environment)
        
        Returns:
            Configuration dictionary or None if not found
        """
        env = environment or self.settings.environment
        
        # TODO: Query integration_configs table once model is created
        # For now, return configuration from settings
        return self._get_config_from_settings(integration_type, tool_name, env)
    
    def _get_config_from_settings(
        self,
        integration_type: str,
        tool_name: str,
        environment: str,
    ) -> Optional[Dict[str, Any]]:
        """Get configuration from settings (temporary implementation).
        
        Args:
            integration_type: Type of integration
            tool_name: Name of the tool
            environment: Environment name
        
        Returns:
            Configuration dictionary
        """
        config = {
            "integration_type": integration_type,
            "tool_name": tool_name,
            "enabled": False,
            "environment": environment,
            "config": {},
            "feature_flags": {},
        }
        
        # Map settings to configuration
        if integration_type == "experiment_tracking":
            config["enabled"] = self.settings.experiment_tracking_enabled
            if tool_name == "mlflow":
                config["config"] = {
                    "tracking_uri": str(self.settings.mlflow_tracking_uri) if self.settings.mlflow_tracking_uri else None,
                    "backend_store_uri": self.settings.mlflow_backend_store_uri,
                    "artifact_root": self.settings.mlflow_default_artifact_root,
                }
        
        elif integration_type == "serving":
            config["enabled"] = self.settings.serving_framework_enabled
            if tool_name == "kserve":
                config["config"] = {
                    "namespace": self.settings.kserve_namespace,
                }
        
        elif integration_type == "orchestration":
            config["enabled"] = self.settings.workflow_orchestration_enabled
            if tool_name == "argo_workflows":
                config["config"] = {
                    "namespace": self.settings.argo_workflows_namespace,
                    "controller_service": self.settings.argo_workflows_controller_service,
                }
        
        elif integration_type == "registry":
            config["enabled"] = self.settings.model_registry_enabled
            if tool_name == "huggingface":
                config["config"] = {
                    "token": self.settings.huggingface_hub_token.get_secret_value() if self.settings.huggingface_hub_token else None,
                    "cache_dir": self.settings.huggingface_hub_cache_dir,
                }
        
        elif integration_type == "versioning":
            config["enabled"] = self.settings.data_versioning_enabled
            if tool_name == "dvc":
                config["config"] = {
                    "remote_name": self.settings.dvc_remote_name,
                    "remote_url": self.settings.dvc_remote_url,
                    "cache_dir": self.settings.dvc_cache_dir,
                }
        
        return config
    
    def get_gpu_types(
        self,
        environment: Optional[str] = None,
        enabled_only: bool = True,
    ) -> list[Dict[str, Any]]:
        """
        Return GPU type options sourced from settings (placeholder until DB-backed config).
        
        Args:
            environment: Environment name (dev/stg/prod). Defaults to settings.environment.
            enabled_only: Keep flag for future compatibility; currently all returned items are enabled.
        
        Returns:
            List of GPU type dicts: {"id": str, "label": str, "enabled": bool, "priority": int}
        """
        env = (environment or self.settings.environment or "").lower()
        env_map = {
            "dev": self.settings.training_gpu_types_dev,
            "stg": self.settings.training_gpu_types_stg,
            "prod": self.settings.training_gpu_types_prod,
        }
        values = env_map.get(env, [])
        gpu_types: list[Dict[str, Any]] = []
        for idx, gpu_id in enumerate(values):
            if not gpu_id:
                continue
            label = gpu_id.replace("-", " ").upper()
            gpu_types.append(
                {
                    "id": gpu_id,
                    "label": label,
                    "enabled": True,
                    "priority": (idx + 1) * 10,
                }
            )
        
        if not gpu_types:
            logger.warning(f"No GPU types configured for env={env}; returning empty list")
        return gpu_types
    
    def update_config(
        self,
        integration_type: str,
        tool_name: str,
        config: Dict[str, Any],
        environment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update integration configuration.
        
        Args:
            integration_type: Type of integration
            tool_name: Name of the tool
            config: Configuration dictionary to update
            environment: Optional environment (defaults to settings.environment)
        
        Returns:
            Updated configuration dictionary
        
        Note:
            This is a placeholder. Full implementation will update database.
        """
        env = environment or self.settings.environment
        logger.info(f"Updating config for {integration_type}/{tool_name} in {env}")
        # TODO: Update database once model is created
        return config
    
    def list_configs(
        self,
        integration_type: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all integration configurations.
        
        Args:
            integration_type: Optional filter by integration type
            environment: Optional filter by environment
        
        Returns:
            List of configuration dictionaries
        """
        env = environment or self.settings.environment
        configs = []
        
        # Return configurations for all known integrations
        integration_types = [
            "experiment_tracking",
            "serving",
            "orchestration",
            "registry",
            "versioning",
        ]
        
        if integration_type:
            integration_types = [integration_type]
        
        for itype in integration_types:
            if itype == "experiment_tracking":
                config = self.get_config(itype, "mlflow", env)
                if config:
                    configs.append(config)
            elif itype == "serving":
                for tool in ["kserve", "ray_serve"]:
                    config = self.get_config(itype, tool, env)
                    if config:
                        configs.append(config)
            elif itype == "orchestration":
                config = self.get_config(itype, "argo_workflows", env)
                if config:
                    configs.append(config)
            elif itype == "registry":
                config = self.get_config(itype, "huggingface", env)
                if config:
                    configs.append(config)
            elif itype == "versioning":
                config = self.get_config(itype, "dvc", env)
                if config:
                    configs.append(config)
        
        return configs

