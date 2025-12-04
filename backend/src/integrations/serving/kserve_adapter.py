"""KServe adapter implementation for model serving.

Implements the ServingFrameworkAdapter interface using KServe InferenceService CRD.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from integrations.serving.interface import ServingFrameworkAdapter
from integrations.error_handler import (
    handle_tool_errors,
    wrap_tool_error,
    ToolUnavailableError,
    ToolOperationError,
)
from core.settings import get_settings

logger = logging.getLogger(__name__)


class KServeAdapter(ServingFrameworkAdapter):
    """KServe adapter for model serving."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize KServe adapter.
        
        Args:
            config: Configuration dictionary with:
                - namespace: Kubernetes namespace for KServe resources
                - enabled: Whether adapter is enabled
        """
        super().__init__(config)
        self.namespace = config.get("namespace", "kserve")
        self.settings = get_settings()
        
        # Initialize Kubernetes client
        try:
            if self.settings.kubeconfig_path:
                config.load_kube_config(config_file=self.settings.kubeconfig_path)
            else:
                config.load_incluster_config()
        except Exception as e:
            logger.warning(f"Failed to load kubeconfig: {e}, using default")
            try:
                config.load_kube_config()
            except Exception:
                logger.error("Could not initialize Kubernetes client")
                raise
        
        self.custom_api = client.CustomObjectsApi()
        self.core_api = client.CoreV1Api()
    
    def is_available(self) -> bool:
        """Check if KServe is available."""
        try:
            # Check if KServe CRD is available
            self.custom_api.get_api_resources(group="serving.kserve.io")
            return True
        except Exception as e:
            logger.warning(f"KServe availability check failed: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on KServe."""
        try:
            # Check if KServe CRD is available
            resources = self.custom_api.get_api_resources(group="serving.kserve.io")
            if any(r.name == "inferenceservices" for r in resources.resources):
                return {
                    "status": "healthy",
                    "message": "KServe InferenceService CRD is available",
                    "details": {"namespace": self.namespace},
                }
            else:
                return {
                    "status": "degraded",
                    "message": "KServe CRD not found",
                    "details": {},
                }
        except Exception as e:
            return {
                "status": "unavailable",
                "message": f"KServe health check failed: {str(e)}",
                "details": {"error": str(e)},
            }
    
    @handle_tool_errors("KServe", "Failed to deploy model")
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
        canary_traffic_percent: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Deploy a model serving endpoint using KServe."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="KServe integration is disabled",
                tool_name="kserve",
            )
        
        endpoint_name = f"endpoint-{endpoint_id}"
        
        # Build InferenceService spec
        inference_service = self._build_inference_service(
            endpoint_name=endpoint_name,
            model_uri=model_uri,
            model_name=model_name,
            namespace=namespace,
            resource_requests=resource_requests or {},
            resource_limits=resource_limits or {},
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            autoscaling_metrics=autoscaling_metrics,
            canary_traffic_percent=canary_traffic_percent,
        )
        
        try:
            # Create InferenceService
            created = self.custom_api.create_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                body=inference_service,
            )
            
            uid = created.get("metadata", {}).get("uid", "")
            logger.info(f"Created KServe InferenceService {endpoint_name} with UID {uid}")
            
            return {
                "framework_resource_id": endpoint_name,
                "framework_namespace": namespace,
                "status": "deploying",
            }
        except ApiException as e:
            raise wrap_tool_error(e, "kserve", "deploy")
    
    def _build_inference_service(
        self,
        endpoint_name: str,
        model_uri: str,
        model_name: str,
        namespace: str,
        resource_requests: Dict[str, str],
        resource_limits: Dict[str, str],
        min_replicas: int,
        max_replicas: int,
        autoscaling_metrics: Optional[Dict[str, Any]],
        canary_traffic_percent: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build KServe InferenceService CRD specification."""
        # Determine predictor type based on model URI or image
        # For now, use vLLM predictor as default
        predictor_type = "vllm"
        
        # Build resource requirements
        resources = {}
        if resource_requests:
            resources["requests"] = resource_requests
        if resource_limits:
            resources["limits"] = resource_limits
        
        # Build autoscaling configuration
        autoscaling = {}
        if min_replicas > 0:
            autoscaling["minReplicas"] = min_replicas
        if max_replicas > min_replicas:
            autoscaling["maxReplicas"] = max_replicas
        
        # Add autoscaling metrics if provided
        if autoscaling_metrics:
            metrics = []
            if "targetLatencyMs" in autoscaling_metrics:
                metrics.append({
                    "type": "Latency",
                    "latency": {
                        "target": f"{autoscaling_metrics['targetLatencyMs']}ms",
                    },
                })
            if "gpuUtilization" in autoscaling_metrics:
                metrics.append({
                    "type": "Resource",
                    "resource": {
                        "name": "gpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": autoscaling_metrics["gpuUtilization"],
                        },
                    },
                })
            if metrics:
                autoscaling["metrics"] = metrics
        
        # Build InferenceService spec
        inference_service = {
            "apiVersion": "serving.kserve.io/v1beta1",
            "kind": "InferenceService",
            "metadata": {
                "name": endpoint_name,
                "namespace": namespace,
                "labels": {
                    "app": "llm-ops-serving",
                    "model-name": model_name,
                },
            },
            "spec": {
                "predictor": {
                    predictor_type: {
                        "storageUri": model_uri,
                        "resources": resources if resources else None,
                    },
                    "minReplicas": min_replicas,
                    "maxReplicas": max_replicas,
                },
            },
        }
        
        # Add autoscaling if configured
        if autoscaling:
            inference_service["spec"]["predictor"].update(autoscaling)
        
        # Add canary traffic splitting if configured
        # KServe supports canary deployments via traffic splitting
        # This is a basic implementation - full canary requires separate InferenceService
        if canary_traffic_percent is not None and 0 < canary_traffic_percent < 100:
            # For canary deployment, we would typically create a separate InferenceService
            # and use KServe's traffic splitting mechanism
            # This is a placeholder for future enhancement
            logger.info(f"Canary deployment requested with {canary_traffic_percent}% traffic")
            # Note: Full canary implementation would require:
            # 1. Creating a canary InferenceService
            # 2. Using KServe's traffic splitting (via Route or TrafficSplit CRD)
            # 3. Managing traffic distribution between stable and canary versions
        
        # Remove None values
        if not resources:
            del inference_service["spec"]["predictor"][predictor_type]["resources"]
        
        return inference_service
    
    @handle_tool_errors("KServe", "Failed to get deployment status")
    def get_deployment_status(
        self,
        framework_resource_id: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """Get deployment status."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="KServe integration is disabled",
                tool_name="kserve",
            )
        
        try:
            inference_service = self.custom_api.get_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=framework_resource_id,
            )
            
            status = inference_service.get("status", {})
            conditions = status.get("conditions", [])
            
            # Determine status from conditions
            ready_condition = next(
                (c for c in conditions if c.get("type") == "Ready"),
                None
            )
            
            if ready_condition and ready_condition.get("status") == "True":
                deployment_status = "healthy"
            elif ready_condition and ready_condition.get("status") == "False":
                deployment_status = "degraded"
            else:
                deployment_status = "deploying"
            
            # Get replica information
            predictor_status = status.get("components", {}).get("predictor", {})
            replicas = predictor_status.get("replicas", 0)
            ready_replicas = predictor_status.get("readyReplicas", 0)
            
            return {
                "status": deployment_status,
                "replicas": replicas,
                "ready_replicas": ready_replicas,
                "conditions": conditions,
                "framework_status": status,
            }
        except ApiException as e:
            if e.status == 404:
                return {
                    "status": "not_found",
                    "replicas": 0,
                    "ready_replicas": 0,
                    "conditions": [],
                    "framework_status": {},
                }
            raise wrap_tool_error(e, "kserve", "get_deployment_status")
    
    @handle_tool_errors("KServe", "Failed to update deployment")
    def update_deployment(
        self,
        framework_resource_id: str,
        namespace: str,
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        resource_requests: Optional[Dict[str, str]] = None,
        resource_limits: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Update deployment configuration."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="KServe integration is disabled",
                tool_name="kserve",
            )
        
        try:
            # Get current InferenceService
            inference_service = self.custom_api.get_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=framework_resource_id,
            )
            
            # Update spec
            spec = inference_service.get("spec", {})
            predictor = spec.get("predictor", {})
            
            if min_replicas is not None:
                predictor["minReplicas"] = min_replicas
            if max_replicas is not None:
                predictor["maxReplicas"] = max_replicas
            
            # Update resources if provided
            predictor_type = next(iter(predictor.keys() - {"minReplicas", "maxReplicas"}))
            if predictor_type in predictor:
                if resource_requests or resource_limits:
                    if "resources" not in predictor[predictor_type]:
                        predictor[predictor_type]["resources"] = {}
                    if resource_requests:
                        predictor[predictor_type]["resources"]["requests"] = resource_requests
                    if resource_limits:
                        predictor[predictor_type]["resources"]["limits"] = resource_limits
            
            # Update InferenceService
            updated = self.custom_api.patch_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=framework_resource_id,
                body=inference_service,
            )
            
            return {
                "framework_resource_id": framework_resource_id,
                "framework_namespace": namespace,
                "status": "updating",
            }
        except ApiException as e:
            raise wrap_tool_error(e, "kserve", "update_deployment")
    
    @handle_tool_errors("KServe", "Failed to delete deployment")
    def delete_deployment(
        self,
        framework_resource_id: str,
        namespace: str,
    ) -> None:
        """Delete a deployment."""
        if not self.is_enabled():
            return  # Graceful degradation
        
        try:
            self.custom_api.delete_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=framework_resource_id,
            )
            logger.info(f"Deleted KServe InferenceService {framework_resource_id}")
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"InferenceService {framework_resource_id} not found, may already be deleted")
                return  # Graceful degradation
            raise wrap_tool_error(e, "kserve", "delete_deployment")
    
    @handle_tool_errors("KServe", "Failed to get inference URL")
    def get_inference_url(
        self,
        framework_resource_id: str,
        namespace: str,
    ) -> str:
        """Get inference endpoint URL."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="KServe integration is disabled",
                tool_name="kserve",
            )
        
        try:
            inference_service = self.custom_api.get_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=framework_resource_id,
            )
            
            status = inference_service.get("status", {})
            url = status.get("url", "")
            
            if not url:
                # Fallback: construct URL from service name
                url = f"http://{framework_resource_id}-predictor-default.{namespace}.svc.cluster.local:80"
            
            return url
        except ApiException as e:
            raise wrap_tool_error(e, "kserve", "get_inference_url")

