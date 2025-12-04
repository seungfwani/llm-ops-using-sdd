"""Serving framework adapter interface.

Defines the interface for serving framework adapters (KServe, Ray Serve, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from uuid import UUID

from integrations.base_adapter import BaseAdapter


class ServingFrameworkAdapter(BaseAdapter):
    """Interface for serving framework adapters."""
    
    @abstractmethod
    def deploy(
        self,
        endpoint_id: UUID,
        model_uri: str,
        model_name: str,
        namespace: str,
        resource_requests: Optional[Dict[str, str]] = None,
        resource_limits: Optional[Dict[str, str]] = None,
        min_replicas: int = 1,
        max_replicas: int = 1,
        autoscaling_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deploy a model serving endpoint.
        
        Args:
            endpoint_id: Platform serving endpoint ID
            model_uri: Storage URI of the model
            model_name: Name of the model
            namespace: Kubernetes namespace for deployment
            resource_requests: CPU/memory/GPU resource requests
            resource_limits: CPU/memory/GPU resource limits
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            autoscaling_metrics: Autoscaling configuration
        
        Returns:
            Dictionary with deployment information:
            {
                "framework_resource_id": str,
                "framework_namespace": str,
                "status": str
            }
        """
        pass
    
    @abstractmethod
    def get_deployment_status(
        self,
        framework_resource_id: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """Get deployment status.
        
        Args:
            framework_resource_id: Framework-specific resource identifier
            namespace: Kubernetes namespace
        
        Returns:
            Dictionary with status information:
            {
                "status": str,
                "replicas": int,
                "ready_replicas": int,
                "conditions": list,
                "framework_status": dict
            }
        """
        pass
    
    @abstractmethod
    def update_deployment(
        self,
        framework_resource_id: str,
        namespace: str,
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        resource_requests: Optional[Dict[str, str]] = None,
        resource_limits: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Update deployment configuration.
        
        Args:
            framework_resource_id: Framework-specific resource identifier
            namespace: Kubernetes namespace
            min_replicas: New minimum replicas (if provided)
            max_replicas: New maximum replicas (if provided)
            resource_requests: New resource requests (if provided)
            resource_limits: New resource limits (if provided)
        
        Returns:
            Updated deployment information
        """
        pass
    
    @abstractmethod
    def delete_deployment(
        self,
        framework_resource_id: str,
        namespace: str,
    ) -> None:
        """Delete a deployment.
        
        Args:
            framework_resource_id: Framework-specific resource identifier
            namespace: Kubernetes namespace
        """
        pass
    
    @abstractmethod
    def get_inference_url(
        self,
        framework_resource_id: str,
        namespace: str,
    ) -> str:
        """Get inference endpoint URL.
        
        Args:
            framework_resource_id: Framework-specific resource identifier
            namespace: Kubernetes namespace
        
        Returns:
            Inference endpoint URL
        """
        pass

