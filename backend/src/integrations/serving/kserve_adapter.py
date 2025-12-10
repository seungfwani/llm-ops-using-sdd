"""KServe adapter implementation for model serving.

Implements the ServingFrameworkAdapter interface using KServe InferenceService CRD.

🟦 Deployment Mode: RawDeployment (Standard)
- Uses KServe v0.16.0 with serving.kserve.io/v1beta1 API
- Creates standard Kubernetes resources: Deployment, Service, (optional) HPA
- No Knative dependencies (no Knative Serving, Istio, Kourier required)
- Uses Kubernetes HPA for autoscaling (not Knative autoscaler)

🟦 Created Resources:
- apps/v1 Deployment
- v1 Service
- (optional) autoscaling/v2 HorizontalPodAutoscaler
- (optional) Ingress or Gateway API

🟦 No Knative Resources:
- No Knative Service, Route, Revision
- No Knative autoscaling annotations
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
    """
    KServe adapter for model serving using RawDeployment mode.
    
    🟦 Mode: RawDeployment (Standard)
    - KServe version: 0.16.0
    - API version: serving.kserve.io/v1beta1
    - Creates standard Kubernetes Deployment (not Knative Service)
    - Uses Kubernetes HPA for autoscaling
    
    🟦 Requirements:
    - KServe controller installed (no Knative/Istio needed)
    - InferenceService CRD available
    """
    
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
                logger.info(f"KServeAdapter: Loading Kubernetes config from: {self.settings.kubeconfig_path}")
                k8s_config.load_kube_config(config_file=self.settings.kubeconfig_path)
            else:
                logger.info("KServeAdapter: Loading in-cluster Kubernetes config")
                k8s_config.load_incluster_config()
        except Exception as e:
            logger.warning(f"KServeAdapter: Failed to load kubeconfig: {e}, using default")
            try:
                logger.info("KServeAdapter: Trying default kubeconfig location")
                k8s_config.load_kube_config()
            except Exception:
                logger.error("KServeAdapter: Could not initialize Kubernetes client")
                raise
        
        # Configure SSL verification based on settings
        configuration = client.Configuration.get_default_copy()
        if not self.settings.kubernetes_verify_ssl:
            logger.warning("SSL verification is disabled for Kubernetes API client")
            configuration.verify_ssl = False
            # Also disable SSL warnings
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            # Update all API clients to use this configuration
            client.Configuration.set_default(configuration)
        
        self.custom_api = client.CustomObjectsApi()
        self.core_api = client.CoreV1Api()
        
        # Test Kubernetes connection
        try:
            logger.info("KServeAdapter: Testing Kubernetes API connection...")
            # Test connection by listing namespaces (simple API call)
            namespaces = self.core_api.list_namespace(limit=1)
            logger.info(f"KServeAdapter: Kubernetes API connection successful. Cluster accessible (tested via namespace list)")
        except Exception as e:
            logger.error(f"KServeAdapter: Failed to connect to Kubernetes API: {e}", exc_info=True)
            raise
    
    def is_available(self) -> bool:
        """Check if KServe is available."""
        try:
            # Method 1: Try to get API resources for the group
            try:
                resources = self.custom_api.get_api_resources(group="serving.kserve.io")
                # Check if inferenceservices resource exists
                if resources and hasattr(resources, 'resources'):
                    for resource in resources.resources:
                        if resource.name == "inferenceservices":
                            logger.info("KServe InferenceService CRD is available via API resources")
                            return True
            except Exception as api_resources_error:
                logger.debug(f"get_api_resources failed: {api_resources_error}, trying direct CRD check")
            
            # Method 2: Try to directly check CRD existence using CoreV1Api
            try:
                from kubernetes.client import ApiextensionsV1Api
                crd_api = ApiextensionsV1Api()
                crd = crd_api.read_custom_resource_definition(name="inferenceservices.serving.kserve.io")
                if crd:
                    # Check if CRD is established
                    conditions = crd.status.conditions if hasattr(crd, 'status') and crd.status else []
                    for condition in conditions:
                        if condition.type == "Established" and condition.status == "True":
                            logger.info("KServe InferenceService CRD exists and is established")
                            return True
                    logger.warning(
                        "KServe InferenceService CRD exists but is not established. "
                        "This may indicate the controller is not running."
                    )
                    # Still return True if CRD exists, even if not established
                    # (it may become available soon)
                    return True
            except ApiException as crd_error:
                if crd_error.status == 404:
                    logger.warning(
                        "KServe InferenceService CRD not found. "
                        "Please install KServe: kubectl get crd inferenceservices.serving.kserve.io"
                    )
                else:
                    logger.warning(f"Failed to check CRD: {crd_error}")
            except Exception as crd_error:
                logger.debug(f"CRD check failed: {crd_error}")
            
            # Method 3: Try to list InferenceServices (most reliable check)
            try:
                # Try to list InferenceServices in a test namespace
                # This will fail if CRD doesn't exist or API group is not registered
                test_namespaces = [self.namespace, "default", "kserve"]
                for test_ns in test_namespaces:
                    try:
                        self.custom_api.list_namespaced_custom_object(
                            group="serving.kserve.io",
                            version="v1beta1",
                            namespace=test_ns,
                            plural="inferenceservices",
                            limit=1,
                        )
                        logger.info(f"KServe InferenceService CRD is available (verified via list in {test_ns})")
                        return True
                    except ApiException as list_error:
                        if list_error.status == 404:
                            # Namespace doesn't exist, try next
                            continue
                        elif list_error.status == 403:
                            # Permission denied, but CRD exists
                            logger.info("KServe InferenceService CRD exists (permission denied on list, but CRD is available)")
                            return True
                        else:
                            # Other error, might mean CRD doesn't exist
                            raise
            except Exception as list_error:
                logger.debug(f"List check failed: {list_error}")
            
            logger.warning(
                "KServe InferenceService CRD is not available. "
                "Please check KServe installation: "
                "kubectl get crd inferenceservices.serving.kserve.io"
            )
            return False
        except Exception as e:
            logger.warning(f"KServe availability check failed: {e}", exc_info=True)
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
        
        # Generate short name for Kubernetes resource (max 43 chars to fit in 63-char hostname limit)
        # Format: svc-{hash} where hash is first 12 chars of UUID (without hyphens)
        # KServe creates hostname: {name}-predictor-{namespace} (max 63 chars)
        endpoint_id_str = str(endpoint_id).replace("-", "")
        short_id = endpoint_id_str[:12]  # Use first 12 chars of UUID (without hyphens)
        endpoint_name = f"svc-{short_id}"
        
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
            
            # Wait a bit and check if pods are being created
            import time
            time.sleep(2)
            
            # Check InferenceService status and events for debugging
            try:
                # Get InferenceService status
                status = created.get("status", {})
                conditions = status.get("conditions", [])
                logger.info(f"InferenceService {endpoint_name} conditions: {conditions}")
                
                # Check for pods
                pods = self.core_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"serving.kserve.io/inferenceservice={endpoint_name}",
                )
                logger.info(f"Found {len(pods.items)} pods for InferenceService {endpoint_name}")
                
                # Check events for errors
                events = self.core_api.list_namespaced_event(
                    namespace=namespace,
                    field_selector=f"involvedObject.name={endpoint_name}",
                )
                if events.items:
                    recent_events = sorted(events.items, key=lambda x: x.last_timestamp or x.first_timestamp, reverse=True)[:5]
                    for event in recent_events:
                        if event.type == "Warning":
                            logger.warning(f"InferenceService event: {event.reason} - {event.message}")
                        else:
                            logger.info(f"InferenceService event: {event.reason} - {event.message}")
            except Exception as debug_error:
                logger.debug(f"Could not check InferenceService status/events: {debug_error}")
            
            return {
                "framework_resource_id": endpoint_name,
                "framework_namespace": namespace,
                "status": "deploying",
            }
        except ApiException as e:
            # Handle CRD not registered errors
            if "no kind" in str(e.body).lower() and "registered" in str(e.body).lower():
                error_msg = (
                    f"KServe InferenceService CRD is not registered in Kubernetes API server.\n"
                    f"Error: {e.reason}\n"
                    f"This usually means:\n"
                    f"  1. CRD was installed but API server hasn't refreshed its discovery cache\n"
                    f"  2. CRD installation failed or was incomplete\n"
                    f"  3. API server needs to be restarted\n\n"
                    f"To fix this:\n"
                    f"  1. Check CRD exists: kubectl get crd inferenceservices.serving.kserve.io\n"
                    f"  2. Check CRD is registered: kubectl api-resources | grep inferenceservice\n"
                    f"  3. Reinstall KServe: ./infra/scripts/setup-kserve.sh {namespace} reinstall\n"
                    f"  4. Or wait a few minutes for API server to refresh\n"
                )
                logger.error(error_msg)
                raise ToolOperationError(
                    message=error_msg,
                    tool_name="kserve",
                    operation="deploy",
                    original_error=str(e),
                ) from e
            
            # Handle webhook certificate errors specifically
            if e.status == 500 and "certificate" in str(e.body).lower():
                error_msg = (
                    f"KServe webhook certificate error: {e.reason}\n"
                    f"This usually means the webhook certificate is not properly configured.\n"
                    f"To fix this, run: ./infra/scripts/setup-kserve.sh {namespace} fix-cert\n"
                    f"Or check webhook configuration: kubectl get validatingwebhookconfiguration | grep kserve"
                )
                logger.error(error_msg)
                raise ToolOperationError(
                    message=error_msg,
                    tool_name="kserve",
                    operation="deploy",
                    original_error=str(e),
                ) from e
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
        """
        Build KServe InferenceService CRD specification using RawDeployment (Standard) mode.
        
        🟦 Deployment Mode: RawDeployment (Standard)
        - Default mode for KServe when Knative is not available
        - Creates standard Kubernetes resources: Deployment, Service, (optional) Ingress/Gateway
        - Uses Kubernetes HPA for autoscaling (not Knative autoscaler)
        - No Knative dependencies (no Knative Service, Route, Revision)
        
        🟦 Created Resources:
        - apps/v1 Deployment
        - v1 Service
        - (optional) Ingress or Gateway API
        - (optional) autoscaling/v2 HorizontalPodAutoscaler (via scaleMetrics)
        
        🟦 Autoscaling:
        - Uses Kubernetes HPA (not Knative autoscaler)
        - scaleMetrics in InferenceService spec will be converted to HPA by KServe controller
        - No Knative autoscaling annotations (autoscaling.knative.dev/*) are used
        
        🟦 API Version:
        - serving.kserve.io/v1beta1
        """
        # Use default serving runtime image from settings if not provided
        if not serving_runtime_image:
            serving_runtime_image = self.settings.serving_runtime_image
        
        # Use GPU setting from parameter or fallback to settings
        if use_gpu is None:
            use_gpu = self.settings.use_gpu
        
        # Detect vLLM and TGI from image name
        is_vllm = "vllm" in serving_runtime_image.lower()
        is_tgi = "text-generation" in serving_runtime_image.lower() or "tgi" in serving_runtime_image.lower()
        
        # Get Hugging Face model ID if available (used for TGI)
        hf_model_id = None
        if model_metadata and isinstance(model_metadata, dict):
            hf_model_id = model_metadata.get("huggingface_model_id")
        
        # Build container args for vLLM and TGI
        # Note: TGI는 기본 80이지만, 요청에 따라 8080으로 노출하도록 설정한다.
        container_args = None
        if is_vllm:
            if not use_gpu:
                container_args = [
                    "--device", "cpu",
                    "--model", model_uri,
                    "--host", "0.0.0.0",
                    "--port", "80",
                ]
            else:
                container_args = [
                    "--model", model_uri,
                    "--host", "0.0.0.0",
                    "--port", "80",
                ]
        elif is_tgi:
            # TGI requires --port argument; also set PORT env for consistency
            tgi_port = 8080
            # TGI also needs --model-id argument
            container_args = [
                "--port", str(tgi_port),  # expose TGI on 8080
                "--hostname", "0.0.0.0",
            ]
            
            # Add model ID if available (TGI prefers HuggingFace model ID)
            if hf_model_id:
                container_args.extend(["--model-id", hf_model_id])
            else:
                # Fallback to MODEL_STORAGE_URI if MODEL_ID not available
                # TGI can use S3 URIs directly
                container_args.extend(["--model-id", model_uri])
        
        # Build environment variables (include runtime limits for visibility)
        env_vars = [
            {
                "name": "PORT",
                "value": "8080" if is_tgi else str(serving_port if 'serving_port' in locals() else 8000),
            },
            {
                "name": "MODEL_URI",
                "value": model_uri,
            },
            {
                "name": "MODEL_STORAGE_URI",
                "value": model_uri,
            },
            {
                "name": "MAX_CONCURRENT_REQUESTS",
                "value": str(self.settings.max_concurrent_requests or 256),
            },
            {
                "name": "MAX_INPUT_TOKENS",
                "value": str(
                    (model_metadata or {}).get("max_position_embeddings")
                    or self.settings.max_input_tokens
                    or 4096
                ),
            },
            {
                "name": "MAX_OUTPUT_TOKENS",
                "value": str(self.settings.max_output_tokens or 1024),
            },
            {
                "name": "SERVE_TARGET",
                "value": (model_metadata or {}).get("serve_target") or "GENERATION",
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
            env_vars.extend([
                # Note: PORT env var is not used by TGI, we use --port arg instead
                {"name": "HF_HUB_DOWNLOAD_TIMEOUT", "value": "1800"},
                {"name": "HF_HUB_DISABLE_EXPERIMENTAL_WARNING", "value": "1"},
                {"name": "HF_HOME", "value": "/tmp/hf_cache"},
                {"name": "HF_HUB_DISABLE_PROGRESS_BARS", "value": "1"},
                {"name": "HF_HUB_ENABLE_HF_TRANSFER", "value": "1"},
                {"name": "HF_HUB_DISABLE_TELEMETRY", "value": "1"},
                {"name": "PYTORCH_CUDA_ALLOC_CONF", "value": "max_split_size_mb:512"},
            ])
            
            # Set MODEL_ID if available (TGI uses this for model loading)
            if hf_model_id:
                env_vars.append({"name": "MODEL_ID", "value": hf_model_id})
                logger.info(f"Using Hugging Face model ID for TGI: {hf_model_id}")
            else:
                # Fallback: Use MODEL_STORAGE_URI as MODEL_ID if no hf_model_id
                # TGI can handle S3 URIs directly
                env_vars.append({"name": "MODEL_ID", "value": model_uri})
                logger.info(f"Using MODEL_STORAGE_URI as MODEL_ID for TGI: {model_uri}")
            
            if not use_gpu:
                env_vars.extend([
                    {"name": "DISABLE_TRITON", "value": "1"},
                    {"name": "MAMBA_DISABLE_TRITON", "value": "1"},
                    {"name": "TORCH_COMPILE_DISABLE", "value": "1"},
                ])
        
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
        
        # Decide serving port per runtime (HuggingFace TGI set to 8080, vLLM defaults 8000)
        serving_port = 8080 if is_tgi else 8000
        
        # Probe 설정: KServe 기본 프로브가 8080으로 잡히는 것을 방지하기 위해 직접 지정
        readiness_delay = 120 if is_tgi else 60
        liveness_delay = 180 if is_tgi else 90

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
                    "containerPort": serving_port,
                    "name": "http",
                    "protocol": "TCP",
                }
            ],
            "readinessProbe": {
                "tcpSocket": {"port": serving_port},
                "initialDelaySeconds": readiness_delay,
                "periodSeconds": 10,
                "timeoutSeconds": 5,
                "failureThreshold": 6,
            },
            "livenessProbe": {
                "tcpSocket": {"port": serving_port},
                "initialDelaySeconds": liveness_delay,
                "periodSeconds": 20,
                "timeoutSeconds": 5,
                "failureThreshold": 6,
            },
        }
        
        if container_args:
            container["args"] = container_args
        
        # Note: We don't set health probes here because:
        # 1. KServe automatically adds probes in RawDeployment mode
        # 2. KServe uses the containerPort we set above (vLLM 8000, TGI 80)
        # 3. KServe handles probe timing based on container startup
        # If custom probes are needed, they can be added via annotations or
        # by modifying the generated Deployment after KServe creates it
        
        # Build InferenceService spec for RawDeployment (Standard) mode
        # 
        # 🟦 RawDeployment Mode Requirements:
        # - Annotation: "serving.kserve.io/deploymentMode": "RawDeployment" (explicitly set)
        # - API Version: "serving.kserve.io/v1beta1"
        # - Structure: Use podSpec (not direct containers array)
        #
        # 🟦 Created Kubernetes Resources (by KServe controller):
        # - apps/v1 Deployment
        # - v1 Service
        # - (optional) autoscaling/v2 HorizontalPodAutoscaler (if scaleMetrics provided)
        #
        # 🟦 No Knative Resources:
        # - No Knative Service (serving.knative.dev/v1)
        # - No Knative Route
        # - No Knative Revision
        # - No Knative autoscaling annotations
        #
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
                    # Explicitly set RawDeployment mode (also called Standard mode)
                    # This ensures KServe creates standard Kubernetes Deployment, not Knative Service
                    "serving.kserve.io/deploymentMode": "RawDeployment",
                },
            },
            "spec": {
                "predictor": {
                    # Use podSpec structure for RawDeployment mode
                    # This tells KServe controller to create apps/v1 Deployment
                    "podSpec": {
                    "containers": [container],
                    },
                    "minReplicas": min_replicas,
                    "maxReplicas": max_replicas,
                },
            },
        }
        
        # Add autoscaling metrics for Kubernetes HPA (RawDeployment mode)
        # 
        # 🟦 Autoscaling in RawDeployment Mode:
        # - Uses Kubernetes HPA (autoscaling/v2), NOT Knative autoscaler
        # - scaleMetrics in InferenceService spec will be converted to HPA by KServe controller
        # - No Knative autoscaling annotations (autoscaling.knative.dev/*) are used
        # - HPA targets the Deployment created by KServe
        #
        if autoscaling_metrics:
            metrics = []
            if "targetLatencyMs" in autoscaling_metrics:
                # Latency-based scaling (converted to HPA custom metrics)
                metrics.append({
                    "type": "Latency",
                    "latency": {
                        "target": f"{autoscaling_metrics['targetLatencyMs']}ms",
                    },
                })
            if "gpuUtilization" in autoscaling_metrics:
                # GPU utilization-based scaling (converted to HPA resource metrics)
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
                # KServe controller will create autoscaling/v2 HorizontalPodAutoscaler
                # targeting the Deployment created in RawDeployment mode
                inference_service["spec"]["predictor"]["scaleMetrics"] = metrics
        
        # Note: Canary traffic splitting in RawDeployment mode
        # RawDeployment mode does NOT support Knative-based canary traffic splitting
        # Canary deployments would need to be handled via:
        # - Multiple InferenceServices with different versions + Service Mesh (Istio) routing
        # - Or separate Deployments with manual traffic management
        # For now, we log but don't implement canary in RawDeployment mode
        if canary_traffic_percent is not None and 0 < canary_traffic_percent < 100:
            logger.warning(
                f"Canary deployment requested ({canary_traffic_percent}% traffic) but "
                f"RawDeployment mode does not support Knative-based canary traffic splitting. "
                f"Canary feature will be ignored. Use multiple InferenceServices or Service Mesh for canary."
            )
        
        return inference_service
    
    @handle_tool_errors("KServe", "Failed to get deployment status")
    def get_deployment_status(
        self,
        framework_resource_id: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """
        Get deployment status.
        
        Note: This method delegates to Kubernetes operations service for operational status checks.
        KServe handles deployment, Kubernetes handles operations.
        """
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="KServe integration is disabled",
                tool_name="kserve",
            )
        
        # Use Kubernetes operations service for status checking (operational task)
        from serving.services.kubernetes_operations import KubernetesOperations
        k8s_ops = KubernetesOperations()
        
        try:
            status_info = k8s_ops.get_kserve_inferenceservice_status(
                endpoint_name=framework_resource_id,
                namespace=namespace,
            )
            
            if status_info:
                return {
                    "status": status_info.get("status", "deploying"),
                    "replicas": status_info.get("replicas", 0),
                    "ready_replicas": status_info.get("ready_replicas", 0),
                    "conditions": status_info.get("conditions", []),
                    "framework_status": status_info.get("framework_status", {}),
                }
            else:
                # InferenceService not found
                return {
                    "status": "failed",
                    "replicas": 0,
                    "ready_replicas": 0,
                    "conditions": [],
                    "framework_status": {},
                }
        except Exception as e:
            logger.warning(f"Failed to get deployment status via Kubernetes operations: {e}, falling back to direct check")
            # Fallback to direct InferenceService check (for compatibility)
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

