"""KServe adapter implementation for model serving.

Implements the ServingFrameworkAdapter interface using KServe InferenceService CRD.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from kubernetes import client
from kubernetes import config as k8s_config
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
                k8s_config.load_kube_config(config_file=self.settings.kubeconfig_path)
            else:
                k8s_config.load_incluster_config()
        except Exception as e:
            logger.warning(f"Failed to load kubeconfig: {e}, using default")
            try:
                k8s_config.load_kube_config()
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
        serving_runtime_image: Optional[str] = None,
        model_metadata: Optional[Dict[str, Any]] = None,
        use_gpu: Optional[bool] = None,
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
            serving_runtime_image=serving_runtime_image,
            model_metadata=model_metadata,
            use_gpu=use_gpu,
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
        serving_runtime_image: Optional[str] = None,
        model_metadata: Optional[Dict[str, Any]] = None,
        use_gpu: Optional[bool] = None,
        canary_traffic_percent: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Build KServe InferenceService CRD specification using PodSpec for custom containers."""
        # Use default serving runtime image from settings if not provided
        if not serving_runtime_image:
            serving_runtime_image = self.settings.serving_runtime_image
        
        # Use GPU setting from parameter or fallback to settings
        if use_gpu is None:
            use_gpu = self.settings.use_gpu
        
        # Detect vLLM and TGI from image name
        is_vllm = "vllm" in serving_runtime_image.lower()
        is_tgi = "text-generation" in serving_runtime_image.lower() or "tgi" in serving_runtime_image.lower()
        
        # Build container args for vLLM
        container_args = None
        if is_vllm:
            if not use_gpu:
                container_args = [
                    "--device", "cpu",
                    "--model", model_uri,
                    "--host", "0.0.0.0",
                    "--port", "8000",
                ]
            else:
                container_args = [
                    "--model", model_uri,
                    "--host", "0.0.0.0",
                    "--port", "8000",
                ]
        
        # Build environment variables
        env_vars = [
            {
                "name": "MODEL_STORAGE_URI",
                "value": model_uri,
            },
            {
                "name": "AWS_ACCESS_KEY_ID",
                "valueFrom": {
                    "secretKeyRef": {
                        "name": "llm-ops-object-store-credentials",
                        "key": "access-key-id",
                    }
                },
            },
            {
                "name": "AWS_SECRET_ACCESS_KEY",
                "valueFrom": {
                    "secretKeyRef": {
                        "name": "llm-ops-object-store-credentials",
                        "key": "secret-access-key",
                    }
                },
            },
            {
                "name": "AWS_ENDPOINT_URL",
                "valueFrom": {
                    "configMapKeyRef": {
                        "name": "llm-ops-object-store-config",
                        "key": "endpoint-url",
                    }
                },
            },
            {
                "name": "AWS_DEFAULT_REGION",
                "value": "us-east-1",
            },
        ]
        
        # Add TGI-specific environment variables
        if is_tgi:
            hf_model_id = None
            if model_metadata and isinstance(model_metadata, dict):
                hf_model_id = model_metadata.get("huggingface_model_id")
            
            env_vars.extend([
                {"name": "HF_HUB_DOWNLOAD_TIMEOUT", "value": "1800"},
                {"name": "HF_HUB_DISABLE_EXPERIMENTAL_WARNING", "value": "1"},
                {"name": "HF_HOME", "value": "/tmp/hf_cache"},
                {"name": "HF_HUB_DISABLE_PROGRESS_BARS", "value": "1"},
                {"name": "HF_HUB_ENABLE_HF_TRANSFER", "value": "1"},
                {"name": "HF_HUB_DISABLE_TELEMETRY", "value": "1"},
                {"name": "PYTORCH_CUDA_ALLOC_CONF", "value": "max_split_size_mb:512"},
            ])
            
            if not use_gpu:
                env_vars.extend([
                    {"name": "DISABLE_TRITON", "value": "1"},
                    {"name": "MAMBA_DISABLE_TRITON", "value": "1"},
                    {"name": "TORCH_COMPILE_DISABLE", "value": "1"},
                ])
            
            if hf_model_id:
                env_vars.append({"name": "MODEL_ID", "value": hf_model_id})
                logger.info(f"Using Hugging Face model ID for TGI: {hf_model_id}")
        
        # Add vLLM-specific environment variables
        if is_vllm:
            env_vars.append({"name": "VLLM_LOGGING_LEVEL", "value": "DEBUG"})
            if not use_gpu:
                env_vars.extend([
                    {"name": "VLLM_USE_CPU", "value": "1"},
                    {"name": "CUDA_VISIBLE_DEVICES", "value": ""},
                    {"name": "NVIDIA_VISIBLE_DEVICES", "value": ""},
                    {"name": "VLLM_CPU_KVCACHE_SPACE", "value": "4"},
                ])
        
        # Build container spec using PodSpec (containers array)
        container = {
            "name": "kserve-container",
            "image": serving_runtime_image,
            "imagePullPolicy": "IfNotPresent",
            "env": env_vars,
            "resources": {
                "requests": resource_requests,
                "limits": resource_limits,
            },
            "ports": [
                {
                    "containerPort": 8000,
                    "name": "http",
                    "protocol": "TCP",
                }
            ],
        }
        
        if container_args:
            container["args"] = container_args
        
        # Add health probes for better pod lifecycle management
        # Note: KServe may add its own probes, but we set defaults
        if is_vllm or is_tgi:
            # vLLM and TGI typically expose /health and /ready endpoints
            container["livenessProbe"] = {
                "httpGet": {
                    "path": "/health",
                    "port": 8000,
                },
                "initialDelaySeconds": 120,
                "periodSeconds": 10,
                "timeoutSeconds": 5,
                "failureThreshold": 3,
            }
            container["readinessProbe"] = {
                "httpGet": {
                    "path": "/ready",
                    "port": 8000,
                },
                "initialDelaySeconds": 60,
                "periodSeconds": 5,
                "timeoutSeconds": 5,
                "failureThreshold": 3,
            }
        
        # Build InferenceService spec with PodSpec
        # Use annotations to disable Knative dependencies if not available
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
                "annotations": {
                    # Disable Knative if not available - use raw Kubernetes Deployment
                    "serving.kserve.io/deploymentMode": "RawDeployment",
                    # Alternative: try to use serverless mode without Knative
                    # "serving.kserve.io/deploymentMode": "Serverless",
                },
            },
            "spec": {
                "predictor": {
                    "containers": [container],
                    "minReplicas": min_replicas,
                    "maxReplicas": max_replicas,
                },
            },
        }
        
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
                inference_service["spec"]["predictor"]["scaleMetrics"] = metrics
        
        # Add canary traffic splitting if configured
        if canary_traffic_percent is not None and 0 < canary_traffic_percent < 100:
            logger.info(f"Canary deployment requested with {canary_traffic_percent}% traffic")
        
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
                # Return "failed" instead of "not_found" to comply with DB check constraint
                # The deployment doesn't exist, which means it failed or was never created
                return {
                    "status": "failed",
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

