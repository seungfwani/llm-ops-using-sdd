"""Serving deployment service for managing framework-specific deployments."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from catalog.repositories import ServingDeploymentRepository
from integrations.serving.factory import ServingFrameworkFactory
from integrations.serving.interface import ServingFrameworkAdapter
from services.integration_config import IntegrationConfigService
from core.settings import get_settings

logger = logging.getLogger(__name__)


class ServingDeploymentService:
    """Service for managing serving deployments with framework adapters."""
    
    def __init__(self, session: Session):
        """Initialize service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.deployment_repo = ServingDeploymentRepository(session)
        self.integration_config = IntegrationConfigService(session)
        self.settings = get_settings()
    
    def create_deployment(
        self,
        endpoint_id: UUID,
        framework_name: str,
        model_uri: str,
        model_name: str,
        namespace: str,
        resource_requests: Optional[Dict[str, str]] = None,
        resource_limits: Optional[Dict[str, str]] = None,
        min_replicas: int = 1,
        max_replicas: int = 1,
        autoscaling_metrics: Optional[Dict[str, Any]] = None,
    ) -> catalog_models.ServingDeployment:
        """Create a serving deployment using the specified framework adapter.
        
        Args:
            endpoint_id: Serving endpoint ID
            framework_name: Framework name ("kserve", "ray_serve")
            model_uri: Model storage URI
            model_name: Model name
            namespace: Kubernetes namespace
            resource_requests: Resource requests
            resource_limits: Resource limits
            min_replicas: Minimum replicas
            max_replicas: Maximum replicas
            autoscaling_metrics: Autoscaling configuration
        
        Returns:
            Created ServingDeployment entity
        """
        # Get framework configuration
        config = self.integration_config.get_config("serving", framework_name)
        if not config or not config.get("enabled"):
            raise ValueError(f"Framework {framework_name} is not enabled or configured")
        
        # Create adapter
        adapter_config = {
            "namespace": namespace,
            "enabled": config["enabled"],
            **config.get("config", {}),
        }
        adapter = ServingFrameworkFactory.create_adapter(framework_name, adapter_config)
        
        # Deploy using adapter
        deployment_info = adapter.deploy(
            endpoint_id=endpoint_id,
            model_uri=model_uri,
            model_name=model_name,
            namespace=namespace,
            resource_requests=resource_requests,
            resource_limits=resource_limits,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            autoscaling_metrics=autoscaling_metrics,
        )
        
        # Create deployment record
        deployment = catalog_models.ServingDeployment(
            id=uuid4(),
            serving_endpoint_id=endpoint_id,
            serving_framework=framework_name,
            framework_resource_id=deployment_info["framework_resource_id"],
            framework_namespace=deployment_info["framework_namespace"],
            replica_count=min_replicas,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            autoscaling_metrics=autoscaling_metrics,
            resource_requests=resource_requests,
            resource_limits=resource_limits,
            framework_status=deployment_info.get("status"),
        )
        
        return self.deployment_repo.create(deployment)
    
    def get_deployment(
        self,
        endpoint_id: UUID,
    ) -> Optional[catalog_models.ServingDeployment]:
        """Get deployment for an endpoint.
        
        Args:
            endpoint_id: Serving endpoint ID
        
        Returns:
            ServingDeployment entity or None
        """
        return self.deployment_repo.get_by_endpoint_id(endpoint_id)
    
    def update_deployment(
        self,
        endpoint_id: UUID,
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        resource_requests: Optional[Dict[str, str]] = None,
        resource_limits: Optional[Dict[str, str]] = None,
    ) -> catalog_models.ServingDeployment:
        """Update deployment configuration.
        
        Args:
            endpoint_id: Serving endpoint ID
            min_replicas: New minimum replicas
            max_replicas: New maximum replicas
            resource_requests: New resource requests
            resource_limits: New resource limits
        
        Returns:
            Updated ServingDeployment entity
        """
        deployment = self.deployment_repo.get_by_endpoint_id(endpoint_id)
        if not deployment:
            raise ValueError(f"Deployment not found for endpoint {endpoint_id}")
        
        # Get adapter
        config = self.integration_config.get_config("serving", deployment.serving_framework)
        if not config or not config.get("enabled"):
            raise ValueError(f"Framework {deployment.serving_framework} is not enabled")
        
        adapter_config = {
            "namespace": deployment.framework_namespace,
            "enabled": config["enabled"],
            **config.get("config", {}),
        }
        adapter = ServingFrameworkFactory.create_adapter(deployment.serving_framework, adapter_config)
        
        # Update using adapter
        adapter.update_deployment(
            framework_resource_id=deployment.framework_resource_id,
            namespace=deployment.framework_namespace,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            resource_requests=resource_requests,
            resource_limits=resource_limits,
        )
        
        # Update deployment record
        if min_replicas is not None:
            deployment.min_replicas = min_replicas
        if max_replicas is not None:
            deployment.max_replicas = max_replicas
        if resource_requests is not None:
            deployment.resource_requests = resource_requests
        if resource_limits is not None:
            deployment.resource_limits = resource_limits
        
        return self.deployment_repo.update(deployment)
    
    def refresh_deployment_status(
        self,
        endpoint_id: UUID,
    ) -> catalog_models.ServingDeployment:
        """Refresh deployment status from framework.
        
        Args:
            endpoint_id: Serving endpoint ID
        
        Returns:
            Updated ServingDeployment entity
        """
        deployment = self.deployment_repo.get_by_endpoint_id(endpoint_id)
        if not deployment:
            raise ValueError(f"Deployment not found for endpoint {endpoint_id}")
        
        # Get adapter
        config = self.integration_config.get_config("serving", deployment.serving_framework)
        if not config or not config.get("enabled"):
            # Graceful degradation: return current deployment without refresh
            logger.warning(f"Framework {deployment.serving_framework} is not enabled, skipping status refresh")
            return deployment
        
        adapter_config = {
            "namespace": deployment.framework_namespace,
            "enabled": config["enabled"],
            **config.get("config", {}),
        }
        adapter = ServingFrameworkFactory.create_adapter(deployment.serving_framework, adapter_config)
        
        # Get status from framework
        status_info = adapter.get_deployment_status(
            framework_resource_id=deployment.framework_resource_id,
            namespace=deployment.framework_namespace,
        )
        
        # Update deployment record
        deployment.replica_count = status_info.get("replicas", deployment.replica_count)
        deployment.framework_status = status_info
        
        return self.deployment_repo.update(deployment)
    
    def delete_deployment(
        self,
        endpoint_id: UUID,
    ) -> None:
        """Delete deployment.
        
        Args:
            endpoint_id: Serving endpoint ID
        """
        deployment = self.deployment_repo.get_by_endpoint_id(endpoint_id)
        if not deployment:
            logger.warning(f"Deployment not found for endpoint {endpoint_id}, skipping deletion")
            return
        
        # Get adapter
        config = self.integration_config.get_config("serving", deployment.serving_framework)
        if config and config.get("enabled"):
            adapter_config = {
                "namespace": deployment.framework_namespace,
                "enabled": config["enabled"],
                **config.get("config", {}),
            }
            adapter = ServingFrameworkFactory.create_adapter(deployment.serving_framework, adapter_config)
            
            # Delete using adapter (graceful degradation on failure)
            try:
                adapter.delete_deployment(
                    framework_resource_id=deployment.framework_resource_id,
                    namespace=deployment.framework_namespace,
                )
            except Exception as e:
                logger.warning(f"Failed to delete deployment from framework: {e}")
        
        # Delete deployment record
        self.deployment_repo.delete(deployment.id)

