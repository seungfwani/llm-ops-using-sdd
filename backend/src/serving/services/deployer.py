"""Serving deployment controller for Kubernetes."""
from __future__ import annotations

import logging
import time
from typing import Optional
from uuid import UUID, uuid4

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from core.image_config import get_image_config
from core.settings import get_settings
from integrations.serving.factory import ServingFrameworkFactory
from serving.converters.kserve_converter import KServeConverter
from serving.converters.ray_serve_converter import RayServeConverter
from serving.schemas import DeploymentSpec
from services.integration_config import IntegrationConfigService

logger = logging.getLogger(__name__)
settings = get_settings()


class ServingDeployer:
    """Controller for deploying model serving endpoints to Kubernetes with HPA."""

    def __init__(self):
        """Initialize Kubernetes client."""
        try:
            if settings.kubeconfig_path:
                config.load_kube_config(config_file=settings.kubeconfig_path)
            else:
                config.load_incluster_config()
        except Exception as e:
            logger.warning(f"Failed to load kubeconfig: {e}, using default")
            try:
                config.load_kube_config()
            except Exception:
                logger.error("Could not initialize Kubernetes client")
                raise

        self.apps_api = client.AppsV1Api()
        self.core_api = client.CoreV1Api()
        self.autoscaling_api = client.AutoscalingV1Api()
        self.networking_api = client.NetworkingV1Api()
        self.custom_api = client.CustomObjectsApi()  # For KServe InferenceService CRD

    def _normalize_route(self, route: str) -> str:
        """
        Normalize route path for Ingress.
        
        Args:
            route: Route path (may have leading/trailing spaces)
        
        Returns:
            Normalized route path (absolute path, no leading/trailing spaces)
        """
        # Remove leading and trailing whitespace
        route = route.strip()
        
        # Ensure it starts with /
        if not route.startswith("/"):
            route = "/" + route
        
        # Remove trailing slash (except for root)
        if route != "/" and route.endswith("/"):
            route = route.rstrip("/")
        
        return route

    def _check_resource_exists(
        self, endpoint_name: str, namespace: str, is_kserve: bool = None
    ) -> tuple[bool, bool]:
        """
        Check if a Kubernetes resource exists and if it's terminating.
        
        Args:
            endpoint_name: Name of the resource
            namespace: Kubernetes namespace
            is_kserve: Whether to check KServe InferenceService (None = auto-detect)
        
        Returns:
            Tuple of (exists: bool, is_terminating: bool)
        """
        if is_kserve is None:
            is_kserve = settings.use_kserve
        
        try:
            if is_kserve:
                resource = self.custom_api.get_namespaced_custom_object(
                    group="serving.kserve.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="inferenceservices",
                    name=endpoint_name
                )
                deletion_timestamp = resource.get("metadata", {}).get("deletionTimestamp")
                return True, deletion_timestamp is not None
            else:
                resource = self.apps_api.read_namespaced_deployment(
                    name=endpoint_name,
                    namespace=namespace
                )
                return True, resource.metadata.deletion_timestamp is not None
        except ApiException as e:
            if e.status == 404:
                return False, False
            raise

    def _ensure_resource_deleted(
        self,
        endpoint_name: str,
        namespace: str,
        resource_type: str = None,
        max_wait: int = 120,
        check_interval: int = 2,
    ) -> None:
        """
        Ensure a Kubernetes resource is completely deleted, waiting if necessary.
        
        Args:
            endpoint_name: Name of the resource
            namespace: Kubernetes namespace
            resource_type: Type of resource (None = auto-detect)
            max_wait: Maximum time to wait in seconds
            check_interval: Interval between checks in seconds
        
        Raises:
            ValueError: If resource still exists after max_wait
        """
        if resource_type is None:
            resource_type = "KServe InferenceService" if settings.use_kserve else "Deployment"
        
        is_kserve = settings.use_kserve
        waited = 0
        
        logger.info(f"Ensuring {resource_type} {endpoint_name} is completely deleted (max {max_wait}s)...")
        
        while waited < max_wait:
            try:
                exists, is_terminating = self._check_resource_exists(endpoint_name, namespace, is_kserve)
                
                if not exists:
                    logger.info(f"{resource_type} {endpoint_name} successfully deleted after {waited}s")
                    return
                
                if is_terminating:
                    logger.info(
                        f"{resource_type} {endpoint_name} is terminating, waiting... ({waited}s)"
                    )
                else:
                    logger.warning(
                        f"{resource_type} {endpoint_name} exists but not terminating. "
                        f"Attempting to delete... ({waited}s)"
                    )
                    try:
                        self.delete_endpoint(endpoint_name, namespace=namespace)
                    except Exception as delete_error:
                        logger.warning(f"Delete attempt failed: {delete_error}")
                
                time.sleep(check_interval)
                waited += check_interval
            except ApiException as e:
                if e.status == 404:
                    logger.info(f"{resource_type} {endpoint_name} successfully deleted after {waited}s")
                    return
                logger.warning(f"Error checking {resource_type} {endpoint_name} status: {e}")
                time.sleep(check_interval)
                waited += check_interval
        
        raise ValueError(
            f"Timeout waiting for {resource_type} {endpoint_name} to be deleted after {max_wait}s. "
            f"The resource may still be terminating. Please wait and try again, or manually delete "
            f"the resource '{endpoint_name}' in namespace '{namespace}'."
        )

    def _handle_409_conflict(
        self,
        endpoint_name: str,
        namespace: str,
        create_func,
        resource_type: str = None,
        max_wait: int = 120,
    ):
        """
        Handle 409 Conflict error by deleting existing resource and retrying creation.
        
        Args:
            endpoint_name: Name of the resource
            namespace: Kubernetes namespace
            create_func: Function to create the resource (will be called again on retry)
            resource_type: Type of resource (None = auto-detect)
            max_wait: Maximum time to wait for deletion
        
        Returns:
            Result from create_func
        
        Raises:
            ValueError: If deletion fails or retry still results in 409
        """
        if resource_type is None:
            resource_type = "KServe InferenceService" if settings.use_kserve else "Deployment"
        
        logger.warning(f"409 Conflict: {resource_type} {endpoint_name} already exists. Attempting to delete and retry...")
        
        # Try to delete (don't fail if deletion fails)
        try:
            logger.info(f"Deleting existing {resource_type} {endpoint_name} before retry...")
            self.delete_endpoint(endpoint_name, namespace=namespace)
        except Exception as delete_error:
            logger.warning(f"delete_endpoint() raised exception (will continue anyway): {delete_error}")
        
        # Wait for deletion to complete
        self._ensure_resource_deleted(endpoint_name, namespace, resource_type, max_wait)
        
        # Retry creation
        try:
            return create_func()
        except ApiException as retry_e:
            if retry_e.status == 409:
                logger.error(f"409 Conflict still occurs after deletion wait. Resource may not be fully deleted.")
                raise ValueError(
                    f"{resource_type} {endpoint_name} still exists after deletion attempt. "
                    f"This may indicate a Kubernetes API issue. Please check the resource status manually."
                ) from retry_e
            raise

    def deploy_endpoint(
        self,
        endpoint_name: str,
        model_storage_uri: str,
        route: str,
        min_replicas: int,
        max_replicas: int,
        autoscale_policy: Optional[dict] = None,
        namespace: str = "default",
        serving_runtime_image: Optional[str] = None,
        use_gpu: Optional[bool] = None,
        cpu_request: Optional[str] = None,
        cpu_limit: Optional[str] = None,
        memory_request: Optional[str] = None,
        memory_limit: Optional[str] = None,
        model_metadata: Optional[dict] = None,
        deployment_spec: Optional[DeploymentSpec] = None,
    ) -> str:
        """
        Deploy a serving endpoint to Kubernetes with HPA.

        Args:
            endpoint_name: Unique name for the deployment
            model_storage_uri: S3 URI to model files (e.g., s3://models/{model_id}/{version}/)
            route: Ingress route path (will be normalized)
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            autoscale_policy: HPA configuration (targetLatencyMs, gpuUtilization)
            namespace: Kubernetes namespace
            serving_runtime_image: Container image for model serving runtime (e.g., vLLM, TGI)
            use_gpu: Whether to request GPU resources. If None, uses settings.use_gpu
            cpu_request: CPU request (e.g., '2', '1000m'). If None, uses default from settings
            cpu_limit: CPU limit (e.g., '4', '2000m'). If None, uses default from settings
            memory_request: Memory request (e.g., '4Gi', '2G'). If None, uses default from settings
            memory_limit: Memory limit (e.g., '8Gi', '4G'). If None, uses default from settings

        Returns:
            Deployment UID
        """
        # Normalize route path
        route = self._normalize_route(route)
        
        deployment_id = str(uuid4())

        # Check if resource already exists and delete it first
        # This ensures idempotency and prevents 409 Conflict errors
        resource_type = "KServe InferenceService" if settings.use_kserve else "Deployment"
        
        try:
            exists, is_terminating = self._check_resource_exists(endpoint_name, namespace)
            if exists:
                logger.warning(
                    f"{resource_type} {endpoint_name} already exists in namespace {namespace}. "
                    f"Deleting it before deploying..."
                )
                try:
                    self.delete_endpoint(endpoint_name, namespace=namespace)
                except Exception as e:
                    logger.warning(f"delete_endpoint() raised exception: {e}, will continue anyway")
                
                # Wait for complete deletion
                self._ensure_resource_deleted(endpoint_name, namespace, resource_type)
        except Exception as e:
            logger.error(f"Error checking/deleting existing resource: {e}")
            raise ValueError(
                f"Failed to check/delete existing {resource_type} {endpoint_name} in namespace {namespace}. "
                f"Cannot proceed with deployment. Error: {e}"
            ) from e

        # Determine serving runtime image
        # Priority: explicit parameter > deployment_spec > model metadata > settings default
        image_config = get_image_config()
        
        # Helper function to validate and normalize serve_target
        def normalize_serve_target(serve_target: Optional[str]) -> str:
            """Normalize serve_target to valid value (GENERATION or RAG)."""
            if serve_target in ("GENERATION", "RAG"):
                return serve_target
            # Default to GENERATION if invalid or None
            logger.warning(f"Invalid serve_target '{serve_target}', defaulting to GENERATION")
            return "GENERATION"
        
        if serving_runtime_image is None:
            # If deployment_spec is provided, use it to determine image
            if deployment_spec:
                serve_target = normalize_serve_target(deployment_spec.serve_target)
                effective_use_gpu = (
                    deployment_spec.use_gpu 
                    if deployment_spec.use_gpu is not None 
                    else (use_gpu if use_gpu is not None else settings.use_gpu)
                )
                try:
                    serving_runtime_image = image_config.get_serve_image_with_fallback(
                        serve_target,
                        effective_use_gpu
                    )
                    logger.info(
                        f"Using image from deployment_spec: {serving_runtime_image} "
                        f"(serve_target={serve_target}, use_gpu={effective_use_gpu})"
                    )
                except ValueError as e:
                    logger.error(f"Failed to get image from deployment_spec: {e}. Using settings default.")
                    serving_runtime_image = settings.serving_runtime_image
            # If no deployment_spec, check model metadata for HuggingFace model
            elif model_metadata and isinstance(model_metadata, dict):
                hf_model_id = model_metadata.get("huggingface_model_id")
                serve_target = normalize_serve_target(model_metadata.get("serve_target"))
                effective_use_gpu = use_gpu if use_gpu is not None else settings.use_gpu
                try:
                    serving_runtime_image = image_config.get_serve_image_with_fallback(
                        serve_target,
                        effective_use_gpu
                    )
                    if hf_model_id:
                        logger.info(
                            f"Using image for HuggingFace model: {serving_runtime_image} "
                            f"(model_id={hf_model_id}, serve_target={serve_target}, use_gpu={effective_use_gpu})"
                        )
                    else:
                        logger.info(
                            f"Using image for non-HuggingFace model: {serving_runtime_image} "
                            f"(serve_target={serve_target}, use_gpu={effective_use_gpu})"
                        )
                except ValueError as e:
                    logger.error(f"Failed to get image from model metadata: {e}. Using settings default.")
                    serving_runtime_image = settings.serving_runtime_image
            else:
                # Fallback to settings default
                serving_runtime_image = settings.serving_runtime_image
                logger.info(f"Using default serving runtime image from settings: {serving_runtime_image}")
        
        # If generic Python image is still used, warn and try to replace with appropriate image
        if "python" in serving_runtime_image.lower() and "vllm" not in serving_runtime_image.lower() and "tgi" not in serving_runtime_image.lower():
            logger.warning(
                f"Generic Python image '{serving_runtime_image}' detected. "
                "This is not a serving runtime. Attempting to select appropriate image..."
            )
            # Try to determine appropriate image based on model metadata or deployment_spec
            try:
                if deployment_spec:
                    serve_target = normalize_serve_target(deployment_spec.serve_target)
                    effective_use_gpu = (
                        deployment_spec.use_gpu 
                        if deployment_spec.use_gpu is not None 
                        else (use_gpu if use_gpu is not None else settings.use_gpu)
                    )
                elif model_metadata and isinstance(model_metadata, dict):
                    serve_target = normalize_serve_target(model_metadata.get("serve_target"))
                    effective_use_gpu = use_gpu if use_gpu is not None else settings.use_gpu
                else:
                    serve_target = "GENERATION"
                    effective_use_gpu = use_gpu if use_gpu is not None else settings.use_gpu
                
                serving_runtime_image = image_config.get_serve_image_with_fallback(
                    serve_target,
                    effective_use_gpu
                )
                logger.info(f"Replaced Python image with: {serving_runtime_image}")
            except (ValueError, Exception) as e:
                logger.error(f"Failed to replace Python image: {e}. Keeping original image.")
                # Keep the original image - it will fail at runtime but at least we tried

        # Use GPU setting from parameter or fallback to settings
        if use_gpu is None:
            use_gpu = settings.use_gpu

        # Use KServe InferenceService if enabled, otherwise use raw Deployment
        if settings.use_kserve:
            # Check if KServe is actually available before using it
            try:
                from integrations.serving.factory import ServingFrameworkFactory
                config = {
                    "namespace": namespace,
                    "enabled": settings.use_kserve,
                }
                adapter = ServingFrameworkFactory.create_adapter("kserve", config)
                if adapter.is_available():
                    try:
                        return self._deploy_with_kserve_adapter(
                            endpoint_name=endpoint_name,
                            model_storage_uri=model_storage_uri,
                            route=route,
                            min_replicas=min_replicas,
                            max_replicas=max_replicas,
                            autoscale_policy=autoscale_policy,
                            namespace=namespace,
                            serving_runtime_image=serving_runtime_image,
                            use_gpu=use_gpu,
                            cpu_request=cpu_request,
                            cpu_limit=cpu_limit,
                            memory_request=memory_request,
                            memory_limit=memory_limit,
                            model_metadata=model_metadata,
                            deployment_spec=deployment_spec,
                        )
                    except Exception as e:
                        logger.error(f"KServe deployment failed: {e}")
                        logger.warning("Falling back to raw Kubernetes Deployment")
                        # Continue to raw Deployment below
                else:
                    logger.warning("KServe is enabled but not available. Falling back to raw Deployment.")
            except Exception as e:
                logger.warning(f"Failed to check KServe availability: {e}. Falling back to raw Deployment.")
        
        # Fallback to raw Deployment (when KServe is disabled or unavailable)
        
        # Fallback to raw Deployment (legacy mode)
        # Create Deployment with model serving runtime
        # The runtime (vLLM/TGI) will load models from object storage at startup
        
        # Build resource requirements
        # Priority: explicit parameters > settings defaults based on GPU setting
        if use_gpu:
            resource_requests = {
                "memory": memory_request or settings.serving_memory_request,
                "cpu": cpu_request or settings.serving_cpu_request,
                "nvidia.com/gpu": "1"
            }
            resource_limits = {
                "memory": memory_limit or settings.serving_memory_limit,
                "cpu": cpu_limit or settings.serving_cpu_limit,
                "nvidia.com/gpu": "1"
            }
        else:
            # CPU-only deployment with reduced resources
            resource_requests = {
                "memory": memory_request or settings.serving_cpu_only_memory_request,
                "cpu": cpu_request or settings.serving_cpu_only_cpu_request,
            }
            resource_limits = {
                "memory": memory_limit or settings.serving_cpu_only_memory_limit,
                "cpu": cpu_limit or settings.serving_cpu_only_cpu_limit,
            }
        
        # Determine if this is a vLLM image (check image name)
        is_vllm = "vllm" in serving_runtime_image.lower()
        
        # Determine if this is a TGI image (check image name)
        is_tgi = "text-generation" in serving_runtime_image.lower() or "tgi" in serving_runtime_image.lower()
        
        # TGI in CPU-only mode requires more memory for model download
        # Default CPU-only limit (1Gi) is too low and causes OOMKilled during download
        # Automatically increase memory limit to minimum 4Gi if not explicitly set
        if is_tgi and not use_gpu and memory_limit is None:
            default_memory_limit = settings.serving_cpu_only_memory_limit
            # Parse memory limit to check if it's too low
            try:
                # Convert to bytes for comparison (rough estimate)
                if default_memory_limit.endswith("Gi"):
                    limit_gb = float(default_memory_limit[:-2])
                elif default_memory_limit.endswith("Mi"):
                    limit_gb = float(default_memory_limit[:-2]) / 1024
                else:
                    limit_gb = 1.0  # Default assumption
                
                # If limit is less than 4Gi, increase to 4Gi for TGI model download
                if limit_gb < 4.0:
                    resource_limits["memory"] = "4Gi"
                    logger.warning(
                        f"TGI CPU-only mode detected: Auto-increasing memory limit from {default_memory_limit} "
                        f"to 4Gi to prevent OOM during model download. "
                        f"To override, explicitly set memory_limit parameter."
                    )
            except (ValueError, AttributeError):
                # If parsing fails, set to safe default
                resource_limits["memory"] = "4Gi"
                logger.warning(
                    f"TGI CPU-only mode detected: Setting memory limit to 4Gi "
                    f"(default was {default_memory_limit}). "
                    f"To override, explicitly set memory_limit parameter."
                )
        
        # Check if this is a generic Python image (needs custom command)
        is_python_image = "python" in serving_runtime_image.lower() and not is_vllm and not is_tgi
        
        # Build command arguments for vLLM or TGI
        container_args = None
        container_command = None
        
        if is_python_image:
            # Generic Python image - this shouldn't be used for serving
            # Log warning and set a basic command to prevent immediate exit
            logger.warning(
                f"Using generic Python image '{serving_runtime_image}' for serving. "
                f"This is not a serving runtime. Please use TGI or vLLM image."
            )
            # Set a command that will keep the container running but log an error
            container_command = ["/bin/sh", "-c"]
            container_args = [
                "echo 'ERROR: Generic Python image cannot serve models. Please use TGI or vLLM image.' && "
                "echo 'Current image: " + serving_runtime_image + "' && "
                "echo 'Model storage URI: " + model_storage_uri + "' && "
                "sleep infinity"
            ]
        elif is_vllm:
            # vLLM requires --model argument and supports S3 paths directly
            # For CPU mode, device must be specified BEFORE model argument
            # to prevent device type inference from failing
            if not use_gpu:
                container_args = [
                    "--device", "cpu",  # Must be first to prevent device inference
                    "--model", model_storage_uri,
                    "--host", "0.0.0.0",
                    "--port", "8000",
                    "--served-model-name", endpoint_name,
                ]
            else:
                container_args = [
                    "--model", model_storage_uri,
                    "--host", "0.0.0.0",
                    "--port", "8000",
                    "--served-model-name", endpoint_name,
                ]
        elif is_tgi:
            # TGI uses --model-id for Hugging Face model ID
            # Try to extract Hugging Face model ID from metadata
            hf_model_id = None
            if model_metadata and isinstance(model_metadata, dict):
                hf_model_id = model_metadata.get("huggingface_model_id")
            
            if hf_model_id:
                # Use Hugging Face model ID - TGI will download it
                container_args = [
                    "--model-id", hf_model_id,
                    "--hostname", "0.0.0.0",
                    "--port", "8000",
                ]
                # Add --disable-custom-kernels for CPU-only mode
                if not use_gpu:
                    container_args.append("--disable-custom-kernels")
                    logger.info("TGI CPU-only mode: Added --disable-custom-kernels flag")
                logger.info(f"Using Hugging Face model ID for TGI: {hf_model_id}")
            else:
                # Fallback: TGI may not work well without HF model ID
                logger.warning("No Hugging Face model ID found in metadata for TGI")
                logger.warning("TGI requires Hugging Face model ID. Model may fail to load.")
                # Still try to set MODEL_ID env var as fallback
                container_args = [
                    "--hostname", "0.0.0.0",
                    "--port", "8000",
                ]
                # Add --disable-custom-kernels for CPU-only mode
                if not use_gpu:
                    container_args.append("--disable-custom-kernels")
                    logger.info("TGI CPU-only mode: Added --disable-custom-kernels flag")
        
        # Build environment variables list
        env_vars = [
                # Model storage URI for runtime to load from object storage
                client.V1EnvVar(name="MODEL_STORAGE_URI", value=model_storage_uri),
                # Object storage access credentials (from Kubernetes secret)
                client.V1EnvVar(
                    name="AWS_ACCESS_KEY_ID",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name="llm-ops-object-store-credentials",
                            key="access-key-id",
                        )
                    ),
                ),
                client.V1EnvVar(
                    name="AWS_SECRET_ACCESS_KEY",
                    value_from=client.V1EnvVarSource(
                        secret_key_ref=client.V1SecretKeySelector(
                            name="llm-ops-object-store-credentials",
                            key="secret-access-key",
                        )
                    ),
                ),
                client.V1EnvVar(
                    name="AWS_ENDPOINT_URL",
                    value_from=client.V1EnvVarSource(
                        config_map_key_ref=client.V1ConfigMapKeySelector(
                            name="llm-ops-object-store-config",
                            key="endpoint-url",
                        )
                    ),
                ),
            # Additional AWS S3 environment variables for boto3 (required for vLLM to access S3)
            client.V1EnvVar(
                name="AWS_DEFAULT_REGION",
                value="us-east-1",  # Default region, can be made configurable
            ),
        ]
        
        # Add TGI-specific environment variables for better download handling
        if is_tgi:
            # Increase download timeout and retry settings
            env_vars.append(client.V1EnvVar(name="HF_HUB_DOWNLOAD_TIMEOUT", value="1800"))  # 30 minutes timeout
            env_vars.append(client.V1EnvVar(name="HF_HUB_DISABLE_EXPERIMENTAL_WARNING", value="1"))
            # Set Hugging Face cache directory to use ephemeral storage (if available)
            # This helps prevent OOM during download by using disk cache
            # Use HF_HOME only (TRANSFORMERS_CACHE is deprecated)
            env_vars.append(client.V1EnvVar(name="HF_HOME", value="/tmp/hf_cache"))
            # Disable progress bars to reduce memory usage during download
            env_vars.append(client.V1EnvVar(name="HF_HUB_DISABLE_PROGRESS_BARS", value="1"))
            # Use streaming download to reduce memory footprint
            env_vars.append(client.V1EnvVar(name="HF_HUB_ENABLE_HF_TRANSFER", value="1"))  # Faster downloads
            # Set low memory mode
            env_vars.append(client.V1EnvVar(name="HF_HUB_DISABLE_TELEMETRY", value="1"))
            # Reduce memory usage during model loading
            env_vars.append(client.V1EnvVar(name="PYTORCH_CUDA_ALLOC_CONF", value="max_split_size_mb:512"))
            
            # CPU mode specific: Disable Triton to prevent driver initialization errors
            if not use_gpu:
                # Disable Triton (used by Mamba models) in CPU mode
                env_vars.append(client.V1EnvVar(name="DISABLE_TRITON", value="1"))
                # Prevent Mamba from trying to use Triton
                env_vars.append(client.V1EnvVar(name="MAMBA_DISABLE_TRITON", value="1"))
                # Use CPU fallback for operations
                env_vars.append(client.V1EnvVar(name="TORCH_COMPILE_DISABLE", value="1"))
                # Additional memory optimization for CPU mode downloads
                # Use safetensors for lower memory footprint during loading
                env_vars.append(client.V1EnvVar(name="SAFETENSORS_FAST_GPU", value="0"))
                # Reduce memory usage during model download and loading
                env_vars.append(client.V1EnvVar(name="HF_HUB_DISABLE_SYMLINKS_WARNING", value="1"))
                # Use disk cache more aggressively to reduce memory usage
                env_vars.append(client.V1EnvVar(name="TRANSFORMERS_NO_ADVISORY_WARNINGS", value="1"))
        
        # Add vLLM-specific environment variables
        if is_vllm:
            # Enable debug logging for vLLM (helps diagnose device type issues)
            env_vars.append(client.V1EnvVar(name="VLLM_LOGGING_LEVEL", value="DEBUG"))
            
            # Force CPU mode if GPU is not available
            if not use_gpu:
                # vLLM CPU mode environment variables
                # Note: Some vLLM versions may not support CPU mode
                env_vars.append(client.V1EnvVar(name="VLLM_USE_CPU", value="1"))
                # Disable CUDA to prevent GPU detection attempts
                env_vars.append(client.V1EnvVar(name="CUDA_VISIBLE_DEVICES", value=""))
                # Additional environment variables to force CPU mode
                env_vars.append(client.V1EnvVar(name="VLLM_CPU_KVCACHE_SPACE", value="4"))  # CPU KV cache space in GB
                # Prevent vLLM from trying to detect GPU
                env_vars.append(client.V1EnvVar(name="NVIDIA_VISIBLE_DEVICES", value=""))
        
        # TGI requires Hugging Face model ID - if not available, log warning
        # vLLM supports S3 paths directly, so init container is not needed
        if is_tgi:
            hf_model_id_in_args = container_args and "--model-id" in container_args
            if not hf_model_id_in_args:
                logger.warning("TGI without Hugging Face model ID may not work correctly")
                logger.warning("Consider importing model from Hugging Face to get huggingface_model_id in metadata")
                logger.warning("Alternatively, use vLLM runtime which supports S3 paths directly")
        
        # No init containers needed:
        # - vLLM: Supports S3 paths directly via --model argument
        # - TGI: Should use Hugging Face model ID (--model-id) for direct download
        init_containers = None
        volumes = None
        volume_mounts = None
        
        # Ensure container_args is not None (empty list is OK, but None will cause issues)
        if container_args is None:
            container_args = []
        
        container = client.V1Container(
            name=f"{endpoint_name}-serving",
            image=serving_runtime_image,
            image_pull_policy="IfNotPresent",  # Avoid pulling latest from remote registry when local image exists
            command=container_command,  # Set command for Python images
            args=container_args if container_args else None,  # Add args for vLLM/TGI, None if empty
            ports=[client.V1ContainerPort(container_port=8000, name="http")],
            resources=client.V1ResourceRequirements(
                requests=resource_requests,
                limits=resource_limits,
            ),
            env=env_vars,
            volume_mounts=volume_mounts if volume_mounts else None,
            liveness_probe=client.V1Probe(
                http_get=client.V1HTTPGetAction(path="/health", port=8000),
                initial_delay_seconds=300 if is_tgi else 120,  # Longer delay for TGI model download (5 min)
                period_seconds=10,
                timeout_seconds=5,
                failure_threshold=5 if is_tgi else 3,  # More retries for TGI
            ),
            readiness_probe=client.V1Probe(
                http_get=client.V1HTTPGetAction(path="/ready", port=8000),
                initial_delay_seconds=300 if is_tgi else 60,  # Longer delay for TGI model download (5 min)
                period_seconds=10 if is_tgi else 5,  # Check less frequently during download
                timeout_seconds=5,
                failure_threshold=10 if is_tgi else 3,  # More retries for TGI (allow up to 5 min download)
            ),
        )

        deployment_spec = client.V1DeploymentSpec(
            replicas=min_replicas,
            selector=client.V1LabelSelector(
                match_labels={"app": endpoint_name, "endpoint-id": deployment_id}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={"app": endpoint_name, "endpoint-id": deployment_id}
                ),
                spec=client.V1PodSpec(
                    containers=[container],
                    init_containers=init_containers if init_containers else None,
                    volumes=volumes if volumes else None,
                ),
            ),
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=endpoint_name,
                namespace=namespace,
                labels={"endpoint-id": deployment_id, "managed-by": "llm-ops-platform"},
            ),
            spec=deployment_spec,
        )

        try:
            created_deployment = self.apps_api.create_namespaced_deployment(
                namespace=namespace, body=deployment
            )
            logger.info(f"Created deployment {endpoint_name} with UID {created_deployment.metadata.uid}")
        except ApiException as e:
            if e.status == 409:
                created_deployment = self._handle_409_conflict(
                    endpoint_name,
                    namespace,
                    lambda: self.apps_api.create_namespaced_deployment(
                        namespace=namespace, body=deployment
                    ),
                    "Deployment",
                )
                logger.info(f"Created deployment {endpoint_name} with UID {created_deployment.metadata.uid} after retry")
            else:
                raise

            # Create Service
            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(
                    name=f"{endpoint_name}-svc",
                    namespace=namespace,
                    labels={"app": endpoint_name},
                ),
                spec=client.V1ServiceSpec(
                    selector={"app": endpoint_name},
                    ports=[client.V1ServicePort(port=8000, target_port=8000)],
                    type="ClusterIP",
                ),
            )
            try:
                self.core_api.create_namespaced_service(namespace=namespace, body=service)
            except ApiException as e:
                if e.status == 409:
                    logger.warning(f"Service {endpoint_name}-svc already exists, deleting and recreating...")
                    try:
                        self.core_api.delete_namespaced_service(name=f"{endpoint_name}-svc", namespace=namespace)
                        time.sleep(2)
                        self.core_api.create_namespaced_service(namespace=namespace, body=service)
                    except Exception as retry_error:
                        logger.error(f"Failed to delete and recreate Service: {retry_error}")
                        raise
                else:
                    raise

            # Create HPA
            if autoscale_policy:
                hpa = client.V1HorizontalPodAutoscaler(
                    api_version="autoscaling/v1",
                    kind="HorizontalPodAutoscaler",
                    metadata=client.V1ObjectMeta(
                        name=f"{endpoint_name}-hpa",
                        namespace=namespace,
                    ),
                    spec=client.V1HorizontalPodAutoscalerSpec(
                        scale_target_ref=client.V1CrossVersionObjectReference(
                            api_version="apps/v1",
                            kind="Deployment",
                            name=endpoint_name,
                        ),
                        min_replicas=min_replicas,
                        max_replicas=max_replicas,
                        target_cpu_utilization_percentage=autoscale_policy.get("cpuUtilization", 70),
                    ),
                )
                try:
                    self.autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
                        namespace=namespace, body=hpa
                    )
                    logger.info(f"Created HPA for {endpoint_name}")
                except ApiException as e:
                    if e.status == 409:
                        logger.warning(f"HPA {endpoint_name}-hpa already exists, deleting and recreating...")
                        try:
                            self.autoscaling_api.delete_namespaced_horizontal_pod_autoscaler(
                                name=f"{endpoint_name}-hpa", namespace=namespace
                            )
                            time.sleep(2)
                            self.autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
                                namespace=namespace, body=hpa
                            )
                            logger.info(f"Created HPA for {endpoint_name} after retry")
                        except Exception as retry_error:
                            logger.error(f"Failed to delete and recreate HPA: {retry_error}")
                            raise
                    else:
                        raise

            # Create Ingress
            ingress = client.V1Ingress(
                api_version="networking.k8s.io/v1",
                kind="Ingress",
                metadata=client.V1ObjectMeta(
                    name=f"{endpoint_name}-ingress",
                    namespace=namespace,
                    annotations={
                        "nginx.ingress.kubernetes.io/rewrite-target": "/",
                    },
                ),
                spec=client.V1IngressSpec(
                    rules=[
                        client.V1IngressRule(
                            host="llm-ops.local",
                            http=client.V1HTTPIngressRuleValue(
                                paths=[
                                    client.V1HTTPIngressPath(
                                        path=route,
                                        path_type="Prefix",
                                        backend=client.V1IngressBackend(
                                            service=client.V1IngressServiceBackend(
                                                name=f"{endpoint_name}-svc",
                                                port=client.V1ServiceBackendPort(number=8000),
                                            )
                                        ),
                                    )
                                ]
                            ),
                        )
                    ]
                ),
            )
            try:
                self.networking_api.create_namespaced_ingress(namespace=namespace, body=ingress)
                logger.info(f"Created Ingress for {endpoint_name} at route {route}")
            except ApiException as e:
                if e.status == 409:
                    logger.warning(f"Ingress {endpoint_name}-ingress already exists, deleting and recreating...")
                    try:
                        self.networking_api.delete_namespaced_ingress(
                            name=f"{endpoint_name}-ingress", namespace=namespace
                        )
                        time.sleep(2)
                        self.networking_api.create_namespaced_ingress(namespace=namespace, body=ingress)
                        logger.info(f"Created Ingress for {endpoint_name} at route {route} after retry")
                    except Exception as retry_error:
                        logger.error(f"Failed to delete and recreate Ingress: {retry_error}")
                        raise
                else:
                    raise

            return created_deployment.metadata.uid
        except ApiException as e:
            logger.error(f"Failed to deploy {endpoint_name}: {e}")
            raise

    def _deploy_with_kserve_adapter(
        self,
        endpoint_name: str,
        model_storage_uri: str,
        route: str,
        min_replicas: int,
        max_replicas: int,
        autoscale_policy: Optional[dict] = None,
        namespace: str = "default",
        serving_runtime_image: str = "vllm/vllm-openai:latest",
        use_gpu: bool = True,
        cpu_request: Optional[str] = None,
        cpu_limit: Optional[str] = None,
        memory_request: Optional[str] = None,
        memory_limit: Optional[str] = None,
        model_metadata: Optional[dict] = None,
        deployment_spec: Optional[DeploymentSpec] = None,
    ) -> str:
        """
        Deploy a serving endpoint using KServe adapter.

        Args:
            endpoint_name: Unique name for the InferenceService (format: "serving-{uuid}" or "endpoint-{uuid}")
            model_storage_uri: S3 URI to model files
            route: Ingress route path (used for annotation, will be normalized)
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            autoscale_policy: HPA configuration
            namespace: Kubernetes namespace
            serving_runtime_image: Container image for model serving runtime
            use_gpu: Whether to request GPU resources
            cpu_request: CPU request
            cpu_limit: CPU limit
            memory_request: Memory request
            memory_limit: Memory limit
            model_metadata: Model metadata

        Returns:
            InferenceService UID
        """
        # Normalize route path
        route = self._normalize_route(route)

        try:
            # Extract endpoint ID from endpoint_name (format: "serving-{uuid}" or "endpoint-{uuid}")
            endpoint_id_str = endpoint_name.replace("serving-", "").replace("endpoint-", "")
            try:
                endpoint_id = UUID(endpoint_id_str)
            except ValueError:
                # If UUID extraction fails, generate a new one
                logger.warning(f"Could not extract UUID from endpoint_name {endpoint_name}, generating new UUID")
                endpoint_id = uuid4()
            
            # Get integration config (requires session, but we don't have one here)
            # For now, use settings-based config
            # TODO: Refactor to pass IntegrationConfigService or session
            config = {
                "namespace": namespace,
                "enabled": settings.use_kserve,
            }
            
            # Create KServe adapter
            adapter = ServingFrameworkFactory.create_adapter("kserve", config)
            
            # If DeploymentSpec is provided, use KServeConverter to generate InferenceService
            if deployment_spec:
                # Convert DeploymentSpec to KServe InferenceService
                inference_service = KServeConverter.to_kserve_inference_service(
                    spec=deployment_spec,
                    container_image=serving_runtime_image,
                    model_uri=model_storage_uri,
                    namespace=namespace,
                    endpoint_name=endpoint_name,
                )
                
                # Deploy InferenceService using Kubernetes CustomObjectsApi
                try:
                    created_service = self.custom_api.create_namespaced_custom_object(
                        group="serving.kserve.io",
                        version="v1beta1",
                        namespace=namespace,
                        plural="inferenceservices",
                        body=inference_service,
                    )
                    logger.info(f"Created KServe InferenceService {created_service['metadata']['name']} from DeploymentSpec")
                    return created_service["metadata"]["uid"]
                except ApiException as e:
                    if e.status == 409:
                        created_service = self._handle_409_conflict(
                            endpoint_name,
                            namespace,
                            lambda: self.custom_api.create_namespaced_custom_object(
                                group="serving.kserve.io",
                                version="v1beta1",
                                namespace=namespace,
                                plural="inferenceservices",
                                body=inference_service,
                            ),
                            "KServe InferenceService",
                        )
                        logger.info(f"Created KServe InferenceService {created_service['metadata']['name']} from DeploymentSpec after retry")
                        return created_service["metadata"]["uid"]
                    else:
                        logger.error(f"Failed to create KServe InferenceService from DeploymentSpec: {e}")
                        raise
            
            # Fallback to adapter-based deployment (legacy)
            # Build resource requests/limits
            resource_requests = {}
            resource_limits = {}
            
            if use_gpu:
                resource_requests = {
                    "memory": memory_request or settings.serving_memory_request,
                    "cpu": cpu_request or settings.serving_cpu_request,
                    "nvidia.com/gpu": "1",
                }
                resource_limits = {
                    "memory": memory_limit or settings.serving_memory_limit,
                    "cpu": cpu_limit or settings.serving_cpu_limit,
                    "nvidia.com/gpu": "1",
                }
            else:
                resource_requests = {
                    "memory": memory_request or settings.serving_cpu_only_memory_request,
                    "cpu": cpu_request or settings.serving_cpu_only_cpu_request,
                }
                resource_limits = {
                    "memory": memory_limit or settings.serving_cpu_only_memory_limit,
                    "cpu": cpu_limit or settings.serving_cpu_only_cpu_limit,
                }
            
            # Extract model name from metadata or use endpoint name
            model_name = endpoint_name
            if model_metadata and isinstance(model_metadata, dict):
                model_name = model_metadata.get("name", endpoint_name)
            
            # Convert autoscale_policy to autoscaling_metrics format expected by adapter
            autoscaling_metrics = None
            if autoscale_policy:
                autoscaling_metrics = {}
                if "targetLatencyMs" in autoscale_policy:
                    autoscaling_metrics["targetLatencyMs"] = autoscale_policy["targetLatencyMs"]
                if "gpuUtilization" in autoscale_policy:
                    autoscaling_metrics["gpuUtilization"] = autoscale_policy["gpuUtilization"]
            
            # Deploy using adapter
            deployment_info = adapter.deploy(
                endpoint_id=endpoint_id,
                model_uri=model_storage_uri,
                model_name=model_name,
                namespace=namespace,
                resource_requests=resource_requests,
                resource_limits=resource_limits,
                min_replicas=min_replicas,
                max_replicas=max_replicas,
                autoscaling_metrics=autoscaling_metrics,
                serving_runtime_image=serving_runtime_image,
                model_metadata=model_metadata,
                use_gpu=use_gpu,
            )
            
            # Return framework resource ID as UID (for compatibility)
            logger.info(f"Created KServe InferenceService {deployment_info['framework_resource_id']} via adapter")
            return deployment_info["framework_resource_id"]
            
        except Exception as e:
            logger.error(f"Failed to deploy KServe InferenceService {endpoint_name} via adapter: {e}")
            # Fallback to raw Deployment if KServe fails
            logger.warning("KServe deployment failed. Falling back to raw Kubernetes Deployment.")
            # Call the raw Deployment logic (which is the rest of deploy_endpoint method)
            # We need to extract the raw deployment logic into a separate method
            # For now, raise the exception to let the caller handle it
            # The caller should catch this and retry with raw Deployment
            raise RuntimeError(f"KServe deployment failed: {e}. Please use raw Deployment instead.") from e
    
    def _deploy_with_kserve_legacy(
        self,
        endpoint_name: str,
        model_storage_uri: str,
        route: str,
        min_replicas: int,
        max_replicas: int,
        autoscale_policy: Optional[dict] = None,
        namespace: str = "default",
        serving_runtime_image: str = "vllm/vllm-openai:latest",
        use_gpu: bool = True,
        model_metadata: Optional[dict] = None,
    ) -> str:
        """
        Legacy deployment using KServe InferenceService CRD (fallback).

        Args:
            endpoint_name: Unique name for the InferenceService
            model_storage_uri: S3 URI to model files
            route: Ingress route path (used for annotation, will be normalized)
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            autoscale_policy: HPA configuration
            namespace: Kubernetes namespace
            serving_runtime_image: Container image for model serving runtime
            use_gpu: Whether to request GPU resources

        Returns:
            InferenceService UID
        """
        # Normalize route path
        route = self._normalize_route(route)

        try:
            # Build resource requirements based on GPU setting and settings
            if use_gpu:
                resource_requests = {
                    "memory": settings.serving_memory_request,
                    "cpu": settings.serving_cpu_request,
                    "nvidia.com/gpu": "1",
                }
                resource_limits = {
                    "memory": settings.serving_memory_limit,
                    "cpu": settings.serving_cpu_limit,
                    "nvidia.com/gpu": "1",
                }
            else:
                # CPU-only deployment with reduced resources
                resource_requests = {
                    "memory": settings.serving_cpu_only_memory_request,
                    "cpu": settings.serving_cpu_only_cpu_request,
                }
                resource_limits = {
                    "memory": settings.serving_cpu_only_memory_limit,
                    "cpu": settings.serving_cpu_only_cpu_limit,
                }

            # Detect vLLM runtime from image name
            is_vllm = "vllm" in serving_runtime_image.lower()
            
            # Detect TGI image
            is_tgi_kserve = "text-generation" in serving_runtime_image.lower() or "tgi" in serving_runtime_image.lower()
            
            # TGI in CPU-only mode requires more memory for model download
            # Default CPU-only limit (1Gi) is too low and causes OOMKilled during download
            # Automatically increase memory limit to minimum 4Gi if not explicitly set
            if is_tgi_kserve and not use_gpu:
                default_memory_limit = settings.serving_cpu_only_memory_limit
                # Parse memory limit to check if it's too low
                try:
                    # Convert to bytes for comparison (rough estimate)
                    if default_memory_limit.endswith("Gi"):
                        limit_gb = float(default_memory_limit[:-2])
                    elif default_memory_limit.endswith("Mi"):
                        limit_gb = float(default_memory_limit[:-2]) / 1024
                    else:
                        limit_gb = 1.0  # Default assumption
                    
                    # If limit is less than 4Gi, increase to 4Gi for TGI model download
                    if limit_gb < 4.0:
                        resource_limits["memory"] = "4Gi"
                        logger.warning(
                            f"TGI CPU-only mode (KServe) detected: Auto-increasing memory limit from {default_memory_limit} "
                            f"to 4Gi to prevent OOM during model download."
                        )
                except (ValueError, AttributeError):
                    # If parsing fails, set to safe default
                    resource_limits["memory"] = "4Gi"
                    logger.warning(
                        f"TGI CPU-only mode (KServe) detected: Setting memory limit to 4Gi "
                        f"(default was {default_memory_limit})."
                    )

            # Build container args:
            # - vLLM: explicit --model/--host/--port args (and --device cpu if CPU mode)
            # - TGI: --model-id/--hostname/--port args (and --disable-custom-kernels if CPU mode)
            # - non‑vLLM/non-TGI: no args so the image can use its own entrypoint/CMD
            if is_vllm:
                if not use_gpu:
                    container_args = [
                        "--device",
                        "cpu",  # Must be first to prevent device inference
                        "--model",
                        model_storage_uri,
                        "--host",
                        "0.0.0.0",
                        "--port",
                        "8000",
                    ]
                else:
                    container_args = [
                        "--model",
                        model_storage_uri,
                        "--host",
                        "0.0.0.0",
                        "--port",
                        "8000",
                    ]
            elif is_tgi_kserve:
                # TGI uses --model-id for Hugging Face model ID
                # Try to extract Hugging Face model ID from metadata
                hf_model_id = None
                if model_metadata and isinstance(model_metadata, dict):
                    hf_model_id = model_metadata.get("huggingface_model_id")
                
                if hf_model_id:
                    # Use Hugging Face model ID - TGI will download it
                    container_args = [
                        "--model-id", hf_model_id,
                        "--hostname", "0.0.0.0",
                        "--port", "8000",
                    ]
                    # Add --disable-custom-kernels for CPU-only mode
                    if not use_gpu:
                        container_args.append("--disable-custom-kernels")
                        logger.info("TGI CPU-only mode (KServe): Added --disable-custom-kernels flag")
                    logger.info(f"Using Hugging Face model ID for TGI (KServe): {hf_model_id}")
                else:
                    # Fallback: TGI may not work well without HF model ID
                    logger.warning("No Hugging Face model ID found in metadata for TGI (KServe)")
                    logger.warning("TGI requires Hugging Face model ID. Model may fail to load.")
                    # Still try to set basic args
                    container_args = [
                        "--hostname", "0.0.0.0",
                        "--port", "8000",
                    ]
                    # Add --disable-custom-kernels for CPU-only mode
                    if not use_gpu:
                        container_args.append("--disable-custom-kernels")
                        logger.info("TGI CPU-only mode (KServe): Added --disable-custom-kernels flag")
            else:
                container_args = None

            # Base environment (S3/object store access)
            env_vars = [
                {
                    "name": "MODEL_STORAGE_URI",
                    "value": model_storage_uri,
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
                # Additional AWS S3 environment variables for boto3
                {
                    "name": "AWS_DEFAULT_REGION",
                    "value": "us-east-1",  # Default region, can be made configurable
                },
            ]

            # Add TGI-specific environment variables for better download handling
            if is_tgi_kserve:
                # Try to extract Hugging Face model ID from metadata if available
                hf_model_id = None
                if model_metadata and isinstance(model_metadata, dict):
                    hf_model_id = model_metadata.get("huggingface_model_id")
                
                env_vars.extend([
                    {
                        "name": "HF_HUB_DOWNLOAD_TIMEOUT",
                        "value": "1800",  # 30 minutes timeout
                    },
                    {
                        "name": "HF_HUB_DISABLE_EXPERIMENTAL_WARNING",
                        "value": "1",
                    },
                    {
                        "name": "HF_HOME",
                        "value": "/tmp/hf_cache",  # Use ephemeral storage for cache
                    },
                    {
                        "name": "HF_HUB_DISABLE_PROGRESS_BARS",
                        "value": "1",  # Disable progress bars to reduce memory usage
                    },
                    {
                        "name": "HF_HUB_ENABLE_HF_TRANSFER",
                        "value": "1",  # Faster downloads with hf-transfer
                    },
                    {
                        "name": "HF_HUB_DISABLE_TELEMETRY",
                        "value": "1",
                    },
                    {
                        "name": "PYTORCH_CUDA_ALLOC_CONF",
                        "value": "max_split_size_mb:512",  # Reduce memory usage
                    },
                ])
                
                # CPU mode specific: Disable Triton to prevent driver initialization errors
                if not use_gpu:
                    env_vars.extend([
                        {
                            "name": "DISABLE_TRITON",
                            "value": "1",
                        },
                        {
                            "name": "MAMBA_DISABLE_TRITON",
                            "value": "1",
                        },
                        {
                            "name": "TORCH_COMPILE_DISABLE",
                            "value": "1",
                        },
                        # Additional memory optimization for CPU mode downloads
                        {
                            "name": "SAFETENSORS_FAST_GPU",
                            "value": "0",  # Use safetensors for lower memory footprint
                        },
                        {
                            "name": "HF_HUB_DISABLE_SYMLINKS_WARNING",
                            "value": "1",  # Reduce memory usage during download
                        },
                        {
                            "name": "TRANSFORMERS_NO_ADVISORY_WARNINGS",
                            "value": "1",  # Use disk cache more aggressively
                        },
                    ])
                
                # Set MODEL_ID for TGI
                if hf_model_id:
                    env_vars.append({
                        "name": "MODEL_ID",
                        "value": hf_model_id,
                    })
                    logger.info(f"Using Hugging Face model ID for TGI (KServe): {hf_model_id}")
                else:
                    # TGI requires MODEL_ID - if not available, this will fail
                    logger.warning("No Hugging Face model ID found in metadata for TGI (KServe)")
                    logger.warning("TGI requires MODEL_ID environment variable. Model may fail to load.")

            # Add vLLM‑specific environment variables only when using a vLLM image
            if is_vllm:
                env_vars.append(
                    {
                        "name": "VLLM_LOGGING_LEVEL",
                        "value": "DEBUG",
                    }
                )

                if not use_gpu:
                    # vLLM CPU‑mode environment variables
                    env_vars.extend(
                        [
                            {
                                "name": "VLLM_USE_CPU",
                                "value": "1",
                            },
                            {
                                "name": "CUDA_VISIBLE_DEVICES",
                                "value": "",
                            },
                            {
                                "name": "NVIDIA_VISIBLE_DEVICES",
                                "value": "",
                            },
                            {
                                "name": "VLLM_CPU_KVCACHE_SPACE",
                                "value": "4",  # CPU KV cache space in GB
                            },
                        ]
                    )

            # KServe InferenceService CRD structure
            inference_service = {
                "apiVersion": "serving.kserve.io/v1beta1",
                "kind": "InferenceService",
                "metadata": {
                    "name": endpoint_name,
                    "namespace": namespace,
                    "labels": {
                        "managed-by": "llm-ops-platform",
                    },
                    "annotations": {
                        "serving.kserve.io/route": route,
                    },
                },
                "spec": {
                    "predictor": {
                        "containers": [
                            {
                                "name": "kserve-container",
                                "image": serving_runtime_image,
                                "imagePullPolicy": "IfNotPresent",  # Avoid ImagePullBackOff on frequent redeploys
                                "args": container_args,
                                "env": env_vars,
                                "resources": {
                                    "requests": resource_requests,
                                    "limits": resource_limits,
                                },
                            }
                        ],
                        "minReplicas": min_replicas,
                        "maxReplicas": max_replicas,
                    },
                },
            }

            # Add autoscaling configuration if provided
            if autoscale_policy:
                inference_service["spec"]["predictor"]["scaleTarget"] = {
                    "minReplicas": min_replicas,
                    "maxReplicas": max_replicas,
                }
                if "cpuUtilization" in autoscale_policy:
                    inference_service["spec"]["predictor"]["scaleTarget"]["cpuUtilization"] = autoscale_policy["cpuUtilization"]

            # Create InferenceService using CustomObjectsApi
            try:
                created = self.custom_api.create_namespaced_custom_object(
                    group="serving.kserve.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="inferenceservices",
                    body=inference_service,
                )

                uid = created.get("metadata", {}).get("uid", "")
                logger.info(f"Created KServe InferenceService {endpoint_name} with UID {uid}")
                return uid
            except ApiException as e:
                if e.status == 409:
                    created = self._handle_409_conflict(
                        endpoint_name,
                        namespace,
                        lambda: self.custom_api.create_namespaced_custom_object(
                            group="serving.kserve.io",
                            version="v1beta1",
                            namespace=namespace,
                            plural="inferenceservices",
                            body=inference_service,
                        ),
                        "KServe InferenceService",
                    )
                    uid = created.get("metadata", {}).get("uid", "")
                    logger.info(f"Created KServe InferenceService {endpoint_name} with UID {uid} after retry")
                    return uid
                else:
                    raise

        except ApiException as e:
            logger.error(f"Failed to deploy KServe InferenceService {endpoint_name}: {e}")
            raise

    def get_endpoint_status(
        self, endpoint_name: str, namespace: str = "default"
    ) -> Optional[dict]:
        """Retrieve deployment status from Kubernetes."""
        if settings.use_kserve:
            return self._get_kserve_status(endpoint_name, namespace)
        
        # Legacy: Get Deployment status
        try:
            deployment = self.apps_api.read_namespaced_deployment(
                name=endpoint_name, namespace=namespace
            )
            
            # Check actual pod status for more accurate status
            pod_status = self._check_pod_status(endpoint_name, namespace)
            deployment_status = self._map_deployment_status(deployment.status)
            
            # Use pod status if available, otherwise fall back to deployment status
            final_status = pod_status if pod_status else deployment_status
            
            return {
                "uid": deployment.metadata.uid,
                "replicas": deployment.spec.replicas,
                "ready_replicas": deployment.status.ready_replicas or 0,
                "available_replicas": deployment.status.available_replicas or 0,
                "status": final_status,
            }
        except ApiException as e:
            if e.status == 404:
                return None
            logger.error(f"Failed to get deployment status for {endpoint_name}: {e}")
            raise

    def _get_kserve_status(
        self, endpoint_name: str, namespace: str = "default"
    ) -> Optional[dict]:
        """Retrieve KServe InferenceService status using adapter."""
        try:
            # Try to use adapter first
            config = {
                "namespace": namespace,
                "enabled": settings.use_kserve,
            }
            adapter = ServingFrameworkFactory.create_adapter("kserve", config)
            
            status_info = adapter.get_deployment_status(
                framework_resource_id=endpoint_name,
                namespace=namespace,
            )
            
            # Map adapter status to deployer format
            return {
                "uid": endpoint_name,  # Use endpoint_name as UID for compatibility
                "replicas": status_info.get("replicas", 0),
                "ready_replicas": status_info.get("ready_replicas", 0),
                "available_replicas": status_info.get("ready_replicas", 0),
                "status": status_info.get("status", "deploying"),
            }
        except Exception as e:
            logger.warning(f"Failed to get KServe status via adapter: {e}, falling back to legacy")
            # Fallback to legacy implementation
            try:
                inference_service = self.custom_api.get_namespaced_custom_object(
                    group="serving.kserve.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="inferenceservices",
                    name=endpoint_name,
                )
                
                status = inference_service.get("status", {})
                conditions = status.get("conditions", [])
                
                # Find Ready condition
                ready_condition = next(
                    (c for c in conditions if c.get("type") == "Ready"),
                    None
                )
                
                ready_status = ready_condition.get("status", "Unknown") if ready_condition else "Unknown"
                
                # Check actual pod status for more accurate status
                pod_status = self._check_pod_status(endpoint_name, namespace, is_kserve=True)
                
                # Determine final status: prefer pod status, fall back to KServe condition
                if pod_status:
                    final_status = pod_status
                elif ready_status == "True":
                    final_status = "healthy"
                elif ready_status == "False":
                    final_status = "degraded"
                else:
                    final_status = "deploying"
                
                return {
                    "uid": inference_service.get("metadata", {}).get("uid", ""),
                    "replicas": status.get("components", {}).get("predictor", {}).get("replicas", 0),
                    "ready_replicas": status.get("components", {}).get("predictor", {}).get("readyReplicas", 0),
                    "available_replicas": status.get("components", {}).get("predictor", {}).get("availableReplicas", 0),
                    "status": final_status,
                }
            except ApiException as api_e:
                if api_e.status == 404:
                    return None
                logger.error(f"Failed to get KServe InferenceService status for {endpoint_name}: {api_e}")
                raise

    def rollback_endpoint(
        self, endpoint_name: str, namespace: str = "default"
    ) -> bool:
        """Rollback a deployment to the previous revision."""
        if settings.use_kserve:
            return self._rollback_kserve(endpoint_name, namespace)
        
        # Legacy: Rollback Deployment
        try:
            # Get deployment rollout history
            # In a real implementation, we'd track revisions and rollback to a specific one
            # For now, we'll scale down and delete, then recreate from rollback plan
            deployment = self.apps_api.read_namespaced_deployment(
                name=endpoint_name, namespace=namespace
            )
            # Scale down to 0
            deployment.spec.replicas = 0
            self.apps_api.patch_namespaced_deployment(
                name=endpoint_name, namespace=namespace, body=deployment
            )
            logger.info(f"Rolled back deployment {endpoint_name}")
            return True
        except ApiException as e:
            logger.error(f"Failed to rollback {endpoint_name}: {e}")
            return False

    def _rollback_kserve(
        self, endpoint_name: str, namespace: str = "default"
    ) -> bool:
        """Rollback KServe InferenceService by scaling down."""
        try:
            # Get current InferenceService
            inference_service = self.custom_api.get_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=endpoint_name,
            )
            
            # Scale down to 0 replicas
            inference_service["spec"]["predictor"]["minReplicas"] = 0
            inference_service["spec"]["predictor"]["maxReplicas"] = 0
            
            self.custom_api.patch_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=endpoint_name,
                body=inference_service,
            )
            logger.info(f"Rolled back KServe InferenceService {endpoint_name}")
            return True
        except ApiException as e:
            logger.error(f"Failed to rollback KServe InferenceService {endpoint_name}: {e}")
            return False

    def delete_endpoint(
        self, endpoint_name: str, namespace: str = "default"
    ) -> bool:
        """
        Delete a serving endpoint from Kubernetes with proper cleanup and verification.
        
        This method deletes both KServe InferenceService and Deployment resources if they exist,
        regardless of settings.use_kserve configuration. This ensures complete cleanup.
        """
        deleted_kserve = False
        deleted_deployment = False
        
        # Try to delete KServe InferenceService if it exists
        try:
            exists, is_terminating = self._check_resource_exists(endpoint_name, namespace, is_kserve=True)
            if exists:
                logger.info(f"Found KServe InferenceService {endpoint_name}, deleting...")
                deleted_kserve = self._delete_kserve(endpoint_name, namespace)
        except Exception as e:
            logger.warning(f"Error checking/deleting KServe InferenceService {endpoint_name}: {e}")
        
        # Try to delete Deployment if it exists
        try:
            exists, is_terminating = self._check_resource_exists(endpoint_name, namespace, is_kserve=False)
            if exists:
                logger.info(f"Found Deployment {endpoint_name}, deleting...")
                deleted_deployment = self._delete_deployment(endpoint_name, namespace)
        except Exception as e:
            logger.warning(f"Error checking/deleting Deployment {endpoint_name}: {e}")
        
        # Delete related resources (HPA, Ingress, Service, Pods) regardless of main resource type
        self._delete_related_resources(endpoint_name, namespace)
        
        # Return True if at least one resource was deleted or didn't exist
        return deleted_kserve or deleted_deployment

    def _delete_deployment(
        self, endpoint_name: str, namespace: str = "default"
    ) -> bool:
        """Delete raw Deployment and related resources."""
        try:
            # Check if Deployment already exists and is deleting
            if self._check_resource_deleting(endpoint_name, namespace, "Deployment"):
                logger.info(f"Deployment {endpoint_name} is already deleting, waiting for completion")
                if self._wait_for_deletion(endpoint_name, namespace, "Deployment", max_wait=60):
                    return True
                else:
                    # Timeout waiting, try to remove finalizers
                    logger.warning(f"Timeout waiting for Deployment {endpoint_name} to delete, attempting to remove finalizers")
                    self._remove_finalizers(endpoint_name, namespace, "Deployment")
                    # Wait again after removing finalizers
                    if self._wait_for_deletion(endpoint_name, namespace, "Deployment", max_wait=30):
                        return True
                    return False
            
            # Check if Deployment exists before attempting deletion
            logger.info(f"Checking if Deployment {endpoint_name} exists in namespace {namespace}")
            deployment_exists = False
            try:
                deployment = self.apps_api.read_namespaced_deployment(
                    name=endpoint_name,
                    namespace=namespace
                )
                deployment_exists = True
                logger.info(
                    f"Deployment {endpoint_name} exists. "
                    f"UID: {deployment.metadata.uid}, "
                    f"Generation: {deployment.metadata.generation}, "
                    f"DeletionTimestamp: {deployment.metadata.deletion_timestamp}"
                )
            except ApiException as e:
                if e.status == 404:
                    logger.info(f"Deployment {endpoint_name} not found, already deleted")
                    return True
                logger.error(f"Error checking Deployment {endpoint_name} existence: {e}")
                raise
            
            if not deployment_exists:
                logger.info(f"Deployment {endpoint_name} does not exist, nothing to delete")
                return True
            
            # First, scale down deployment to 0 replicas to stop pods immediately
            try:
                self.apps_api.patch_namespaced_deployment_scale(
                    name=endpoint_name,
                    namespace=namespace,
                    body={"spec": {"replicas": 0}},
                )
                logger.info(f"Scaled down Deployment {endpoint_name} to 0 replicas")
                # Wait a bit for pods to start terminating
                time.sleep(2)
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to scale down Deployment {endpoint_name}: {e}")
            
            # Delete related resources will be handled by _delete_related_resources
            
            # Remove finalizers before deletion to prevent blocking
            logger.info(f"Removing finalizers from Deployment {endpoint_name} before deletion")
            finalizer_removed = self._remove_finalizers(endpoint_name, namespace, "Deployment")
            if not finalizer_removed:
                logger.warning(f"Failed to remove finalizers from Deployment {endpoint_name}, but continuing with deletion")
            
            # Delete Deployment with Foreground propagation
            logger.info(f"Attempting to delete Deployment {endpoint_name} in namespace {namespace}")
            try:
                body = client.V1DeleteOptions(
                    propagation_policy="Foreground",
                    grace_period_seconds=0  # Force immediate deletion
                )
                logger.debug(f"Calling delete_namespaced_deployment with body: {body}")
                delete_response = self.apps_api.delete_namespaced_deployment(
                    name=endpoint_name,
                    namespace=namespace,
                    body=body,
                )
                logger.info(f"Delete API call successful for Deployment {endpoint_name}. Response: {delete_response}")
            except ApiException as e:
                logger.error(
                    f"ApiException when deleting Deployment {endpoint_name}: "
                    f"status={e.status}, reason={e.reason}, body={e.body}"
                )
                if e.status == 404:
                    logger.info(f"Deployment {endpoint_name} not found, already deleted")
                    return True
                # Re-raise to be caught by outer exception handler
                raise
            except Exception as e:
                logger.error(f"Unexpected exception when deleting Deployment {endpoint_name}: {e}", exc_info=True)
                raise
            
            # Wait for Deployment to be fully deleted
            if not self._wait_for_deletion(endpoint_name, namespace, "Deployment", max_wait=60):
                # If timeout, try to remove finalizers again
                logger.warning(f"Timeout waiting for Deployment {endpoint_name}, attempting to remove finalizers")
                self._remove_finalizers(endpoint_name, namespace, "Deployment")
                # Wait again after removing finalizers
                if not self._wait_for_deletion(endpoint_name, namespace, "Deployment", max_wait=30):
                    logger.warning(f"Deployment {endpoint_name} still exists after cleanup attempts")
            
            # Final verification that Deployment is deleted
            if self._wait_for_deletion(endpoint_name, namespace, "Deployment", max_wait=10):
                logger.info(f"Successfully deleted Deployment {endpoint_name}")
                return True
            else:
                logger.warning(f"Deployment {endpoint_name} may still exist after cleanup")
                return False
            
        except ApiException as e:
            if e.status == 404:
                logger.info(f"Deployment {endpoint_name} not found, already deleted")
                return True
            logger.error(f"Failed to delete endpoint {endpoint_name}: {e}")
            return False

    def _wait_for_deletion(
        self,
        endpoint_name: str,
        namespace: str,
        resource_type: str = "Deployment",
        max_wait: int = 60,
        check_interval: int = 2,
    ) -> bool:
        """
        Wait for a Kubernetes resource to be fully deleted.
        
        Args:
            endpoint_name: Name of the resource to check
            namespace: Kubernetes namespace
            resource_type: Type of resource ("Deployment" or "InferenceService")
            max_wait: Maximum time to wait in seconds
            check_interval: Interval between checks in seconds
            
        Returns:
            True if resource is deleted, False if timeout
        """
        waited = 0
        while waited < max_wait:
            try:
                if resource_type == "InferenceService":
                    # Check if KServe InferenceService still exists
                    self.custom_api.get_namespaced_custom_object(
                        group="serving.kserve.io",
                        version="v1beta1",
                        namespace=namespace,
                        plural="inferenceservices",
                        name=endpoint_name
                    )
                    # If we get here, InferenceService still exists
                    logger.debug(f"Waiting for {resource_type} {endpoint_name} to be deleted... ({waited}s)")
                else:
                    # Check if Deployment still exists
                    self.apps_api.read_namespaced_deployment(
                        name=endpoint_name,
                        namespace=namespace
                    )
                    # If we get here, deployment still exists
                    logger.debug(f"Waiting for {resource_type} {endpoint_name} to be deleted... ({waited}s)")
                
                time.sleep(check_interval)
                waited += check_interval
            except ApiException as e:
                if e.status == 404:
                    # Resource not found, deletion successful
                    logger.info(f"{resource_type} {endpoint_name} successfully deleted after {waited}s")
                    return True
                else:
                    # Other error, log and continue waiting
                    logger.warning(f"Error checking {resource_type} {endpoint_name} status: {e}")
                    time.sleep(check_interval)
                    waited += check_interval
            except Exception as e:
                logger.warning(f"Unexpected error checking {resource_type} {endpoint_name} status: {e}")
                time.sleep(check_interval)
                waited += check_interval
        
        logger.warning(f"Timeout waiting for {resource_type} {endpoint_name} to be deleted after {max_wait}s")
        return False

    def _remove_finalizers(
        self,
        endpoint_name: str,
        namespace: str,
        resource_type: str = "Deployment",
    ) -> bool:
        """
        Remove finalizers from a Kubernetes resource to allow deletion.
        
        Args:
            endpoint_name: Name of the resource
            namespace: Kubernetes namespace
            resource_type: Type of resource ("Deployment" or "InferenceService")
            
        Returns:
            True if finalizers were removed or didn't exist, False on error
        """
        try:
            if resource_type == "InferenceService":
                # Get InferenceService
                inference_service = self.custom_api.get_namespaced_custom_object(
                    group="serving.kserve.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="inferenceservices",
                    name=endpoint_name
                )
                
                # Check if it has finalizers
                if inference_service.get("metadata", {}).get("finalizers"):
                    logger.info(f"Removing finalizers from InferenceService {endpoint_name}")
                    inference_service["metadata"]["finalizers"] = []
                    self.custom_api.patch_namespaced_custom_object(
                        group="serving.kserve.io",
                        version="v1beta1",
                        namespace=namespace,
                        plural="inferenceservices",
                        name=endpoint_name,
                        body=inference_service
                    )
                    logger.info(f"Removed finalizers from InferenceService {endpoint_name}")
                    return True
            else:
                # Get Deployment
                deployment = self.apps_api.read_namespaced_deployment(
                    name=endpoint_name,
                    namespace=namespace
                )
                
                # Check if it has finalizers
                if deployment.metadata.finalizers:
                    logger.info(f"Removing finalizers from Deployment {endpoint_name}")
                    deployment.metadata.finalizers = []
                    self.apps_api.patch_namespaced_deployment(
                        name=endpoint_name,
                        namespace=namespace,
                        body=deployment
                    )
                    logger.info(f"Removed finalizers from Deployment {endpoint_name}")
                    return True
            
            return True  # No finalizers to remove
        except ApiException as e:
            if e.status == 404:
                # Resource doesn't exist, nothing to do
                return True
            logger.warning(f"Failed to remove finalizers from {resource_type} {endpoint_name}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error removing finalizers from {resource_type} {endpoint_name}: {e}")
            return False

    def _delete_related_resources(
        self, endpoint_name: str, namespace: str = "default"
    ) -> None:
        """
        Delete all related resources (HPA, Ingress, Service, Pods) for an endpoint.
        
        This method is called regardless of whether the main resource is KServe or Deployment
        to ensure complete cleanup.
        """
        # Delete HPA
        try:
            hpa_name = f"{endpoint_name}-hpa"
            try:
                self.autoscaling_api.delete_namespaced_horizontal_pod_autoscaler(
                    name=hpa_name,
                    namespace=namespace,
                )
                logger.info(f"Deleted HPA {hpa_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete HPA {hpa_name}: {e}")
                    # Try to find HPA dynamically
                    try:
                        hpas = self.autoscaling_api.list_namespaced_horizontal_pod_autoscaler(namespace=namespace)
                        for hpa in hpas.items:
                            if endpoint_name in hpa.metadata.name:
                                try:
                                    self.autoscaling_api.delete_namespaced_horizontal_pod_autoscaler(
                                        name=hpa.metadata.name,
                                        namespace=namespace,
                                    )
                                    logger.info(f"Deleted HPA {hpa.metadata.name} (found dynamically)")
                                except ApiException:
                                    pass
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Error deleting HPA for {endpoint_name}: {e}")
        
        # Delete Ingress
        try:
            ingress_name = f"{endpoint_name}-ingress"
            try:
                self.networking_api.delete_namespaced_ingress(
                    name=ingress_name,
                    namespace=namespace,
                )
                logger.info(f"Deleted Ingress {ingress_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete Ingress {ingress_name}: {e}")
                    # Try to find Ingress dynamically
                    try:
                        ingresses = self.networking_api.list_namespaced_ingress(namespace=namespace)
                        for ingress in ingresses.items:
                            if endpoint_name in ingress.metadata.name:
                                try:
                                    self.networking_api.delete_namespaced_ingress(
                                        name=ingress.metadata.name,
                                        namespace=namespace,
                                    )
                                    logger.info(f"Deleted Ingress {ingress.metadata.name} (found dynamically)")
                                except ApiException:
                                    pass
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Error deleting Ingress for {endpoint_name}: {e}")
        
        # Delete Service
        try:
            service_name = f"{endpoint_name}-svc"
            try:
                self.core_api.delete_namespaced_service(
                    name=service_name,
                    namespace=namespace,
                )
                logger.info(f"Deleted Service {service_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete Service {service_name}: {e}")
                    # Try to find Service dynamically
                    try:
                        services = self.core_api.list_namespaced_service(namespace=namespace)
                        for service in services.items:
                            if endpoint_name in service.metadata.name:
                                try:
                                    self.core_api.delete_namespaced_service(
                                        name=service.metadata.name,
                                        namespace=namespace,
                                    )
                                    logger.info(f"Deleted Service {service.metadata.name} (found dynamically)")
                                except ApiException:
                                    pass
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Error deleting Service for {endpoint_name}: {e}")
        
        # Delete Pods
        try:
            # Try multiple label selectors
            label_selectors = [
                f"app={endpoint_name}",
                f"app.kubernetes.io/name={endpoint_name}",
            ]
            
            for label_selector in label_selectors:
                try:
                    pods = self.core_api.list_namespaced_pod(
                        namespace=namespace,
                        label_selector=label_selector,
                    )
                    for pod in pods.items:
                        try:
                            body = client.V1DeleteOptions(
                                grace_period_seconds=0,
                                propagation_policy="Background"
                            )
                            self.core_api.delete_namespaced_pod(
                                name=pod.metadata.name,
                                namespace=namespace,
                                body=body,
                            )
                            logger.info(f"Force deleted Pod {pod.metadata.name}")
                        except ApiException as pod_e:
                            if pod_e.status != 404:
                                logger.warning(f"Failed to delete Pod {pod.metadata.name}: {pod_e}")
                except ApiException:
                    pass
            
            # Also try to find pods by name pattern
            try:
                all_pods = self.core_api.list_namespaced_pod(namespace=namespace)
                for pod in all_pods.items:
                    if endpoint_name in pod.metadata.name:
                        try:
                            body = client.V1DeleteOptions(
                                grace_period_seconds=0,
                                propagation_policy="Background"
                            )
                            self.core_api.delete_namespaced_pod(
                                name=pod.metadata.name,
                                namespace=namespace,
                                body=body,
                            )
                            logger.info(f"Force deleted Pod {pod.metadata.name} (by name pattern)")
                        except ApiException as pod_e:
                            if pod_e.status != 404:
                                logger.warning(f"Failed to delete Pod {pod.metadata.name}: {pod_e}")
            except ApiException:
                pass
        except Exception as e:
            logger.warning(f"Error deleting Pods for {endpoint_name}: {e}")

    def _check_resource_deleting(
        self,
        endpoint_name: str,
        namespace: str,
        resource_type: str = "Deployment",
    ) -> bool:
        """
        Check if a resource is already in Terminating state.
        
        Args:
            endpoint_name: Name of the resource
            namespace: Kubernetes namespace
            resource_type: Type of resource ("Deployment" or "InferenceService")
            
        Returns:
            True if resource is deleting, False otherwise
        """
        try:
            if resource_type == "InferenceService":
                inference_service = self.custom_api.get_namespaced_custom_object(
                    group="serving.kserve.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="inferenceservices",
                    name=endpoint_name
                )
                deletion_timestamp = inference_service.get("metadata", {}).get("deletionTimestamp")
                return deletion_timestamp is not None
            else:
                deployment = self.apps_api.read_namespaced_deployment(
                    name=endpoint_name,
                    namespace=namespace
                )
                return deployment.metadata.deletion_timestamp is not None
        except ApiException as e:
            if e.status == 404:
                return False  # Resource doesn't exist
            return False
        except Exception:
            return False

    def _delete_kserve(
        self, endpoint_name: str, namespace: str = "default"
    ) -> bool:
        """Delete KServe InferenceService with proper cleanup and verification."""
        try:
            # Check if resource already exists and is deleting
            if self._check_resource_deleting(endpoint_name, namespace, "InferenceService"):
                logger.info(f"InferenceService {endpoint_name} is already deleting, waiting for completion")
                if self._wait_for_deletion(endpoint_name, namespace, "InferenceService", max_wait=60):
                    return True
                else:
                    # Timeout waiting, try to remove finalizers
                    logger.warning(f"Timeout waiting for InferenceService {endpoint_name} to delete, attempting to remove finalizers")
                    self._remove_finalizers(endpoint_name, namespace, "InferenceService")
                    # Wait again after removing finalizers
                    if self._wait_for_deletion(endpoint_name, namespace, "InferenceService", max_wait=30):
                        return True
                    return False
            
            # Check if resource exists before attempting deletion
            logger.info(f"Checking if InferenceService {endpoint_name} exists in namespace {namespace}")
            inference_service_exists = False
            try:
                inference_service = self.custom_api.get_namespaced_custom_object(
                    group="serving.kserve.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="inferenceservices",
                    name=endpoint_name
                )
                inference_service_exists = True
                metadata = inference_service.get("metadata", {})
                logger.info(
                    f"InferenceService {endpoint_name} exists. "
                    f"UID: {metadata.get('uid')}, "
                    f"Generation: {metadata.get('generation')}, "
                    f"DeletionTimestamp: {metadata.get('deletionTimestamp')}"
                )
            except ApiException as e:
                if e.status == 404:
                    logger.info(f"InferenceService {endpoint_name} not found, already deleted")
                    return True
                logger.error(f"Error checking InferenceService {endpoint_name} existence: {e}")
                raise
            
            if not inference_service_exists:
                logger.info(f"InferenceService {endpoint_name} does not exist, nothing to delete")
                return True
            
            # Remove finalizers before deletion to prevent blocking
            logger.info(f"Removing finalizers from InferenceService {endpoint_name} before deletion")
            finalizer_removed = self._remove_finalizers(endpoint_name, namespace, "InferenceService")
            if not finalizer_removed:
                logger.warning(f"Failed to remove finalizers from InferenceService {endpoint_name}, but continuing with deletion")
            
            # Delete InferenceService with Foreground propagation to ensure proper cleanup
            # Note: Custom objects may not support Foreground propagation, so we use Background
            # and then wait for deletion
            logger.info(f"Attempting to delete KServe InferenceService {endpoint_name} in namespace {namespace}")
            try:
                delete_response = self.custom_api.delete_namespaced_custom_object(
                    group="serving.kserve.io",
                    version="v1beta1",
                    namespace=namespace,
                    plural="inferenceservices",
                    name=endpoint_name,
                    propagation_policy="Foreground",  # Try Foreground first
                )
                logger.info(f"Delete API call successful for InferenceService {endpoint_name}. Response: {delete_response}")
            except ApiException as e:
                logger.error(
                    f"ApiException when deleting InferenceService {endpoint_name} with Foreground: "
                    f"status={e.status}, reason={e.reason}, body={e.body}"
                )
                if e.status == 404:
                    logger.info(f"InferenceService {endpoint_name} not found, already deleted")
                    return True
                # If Foreground fails, try Background
                logger.warning(f"Foreground propagation failed for InferenceService {endpoint_name}, trying Background")
                try:
                    delete_response = self.custom_api.delete_namespaced_custom_object(
                        group="serving.kserve.io",
                        version="v1beta1",
                        namespace=namespace,
                        plural="inferenceservices",
                        name=endpoint_name,
                        propagation_policy="Background",
                    )
                    logger.info(f"Delete API call successful for InferenceService {endpoint_name} with Background. Response: {delete_response}")
                except ApiException as e2:
                    logger.error(
                        f"ApiException when deleting InferenceService {endpoint_name} with Background: "
                        f"status={e2.status}, reason={e2.reason}, body={e2.body}"
                    )
                    if e2.status == 404:
                        logger.info(f"InferenceService {endpoint_name} not found, already deleted")
                        return True
                    raise
            except Exception as e:
                logger.error(f"Unexpected exception when deleting InferenceService {endpoint_name}: {e}", exc_info=True)
                raise
            
            # Wait for InferenceService to be fully deleted
            if not self._wait_for_deletion(endpoint_name, namespace, "InferenceService", max_wait=60):
                # If timeout, try to remove finalizers and force delete pods
                logger.warning(f"Timeout waiting for InferenceService {endpoint_name}, attempting cleanup")
                self._remove_finalizers(endpoint_name, namespace, "InferenceService")
            
            # Force delete any remaining pods (KServe pods may have different labels)
            try:
                # Try common KServe pod label selectors
                label_selectors = [
                    f"serving.kserve.io/inferenceservice={endpoint_name}",
                    f"app={endpoint_name}",
                ]
                
                for label_selector in label_selectors:
                    try:
                        pods = self.core_api.list_namespaced_pod(
                            namespace=namespace,
                            label_selector=label_selector,
                        )
                        for pod in pods.items:
                            try:
                                # Force delete pod with grace period 0
                                body = client.V1DeleteOptions(
                                    grace_period_seconds=0,
                                    propagation_policy="Background"
                                )
                                self.core_api.delete_namespaced_pod(
                                    name=pod.metadata.name,
                                    namespace=namespace,
                                    body=body,
                                )
                                logger.info(f"Force deleted KServe Pod {pod.metadata.name}")
                            except ApiException as pod_e:
                                if pod_e.status != 404:
                                    logger.warning(f"Failed to delete Pod {pod.metadata.name}: {pod_e}")
                    except ApiException:
                        # Label selector may not match any pods, continue
                        pass
                
                # Also try to find pods by name pattern (KServe pods: {endpoint_name}-predictor-default-{hash})
                all_pods = self.core_api.list_namespaced_pod(namespace=namespace)
                for pod in all_pods.items:
                    if endpoint_name in pod.metadata.name:
                        try:
                            # Force delete pod with grace period 0
                            body = client.V1DeleteOptions(
                                grace_period_seconds=0,
                                propagation_policy="Background"
                            )
                            self.core_api.delete_namespaced_pod(
                                name=pod.metadata.name,
                                namespace=namespace,
                                body=body,
                            )
                            logger.info(f"Force deleted KServe Pod {pod.metadata.name} (by name pattern)")
                        except ApiException as pod_e:
                            if pod_e.status != 404:
                                logger.warning(f"Failed to delete Pod {pod.metadata.name}: {pod_e}")
            except ApiException as e:
                logger.warning(f"Failed to list/delete KServe pods for {endpoint_name}: {e}")
            
            # Final verification that resource is deleted
            if self._wait_for_deletion(endpoint_name, namespace, "InferenceService", max_wait=10):
                logger.info(f"Successfully deleted KServe InferenceService {endpoint_name}")
                return True
            else:
                logger.warning(f"InferenceService {endpoint_name} may still exist after cleanup")
                return False
            
        except ApiException as e:
            if e.status == 404:
                logger.info(f"InferenceService {endpoint_name} not found, already deleted")
                return True  # Already deleted, consider it success
            logger.error(f"Failed to delete KServe InferenceService {endpoint_name}: {e}")
            return False

    def _check_pod_status(self, endpoint_name: str, namespace: str = "default", is_kserve: bool = False) -> Optional[str]:
        """Check actual pod status to determine endpoint health."""
        try:
            # Get pods for this deployment
            # For KServe, pods are labeled with the InferenceService name
            # For raw Deployment, pods are labeled with app={endpoint_name}
            if is_kserve:
                # KServe pods are typically labeled with the service name
                # Try multiple label selectors for KServe
                label_selectors = [
                    f"serving.kserve.io/inferenceservice={endpoint_name}",
                    f"app={endpoint_name}",
                ]
                # Also try to find pods by name pattern (KServe pods are named like: {endpoint_name}-predictor-default-{hash})
                # If label selector fails, we'll try to list all pods and filter by name
            else:
                label_selectors = [f"app={endpoint_name}"]
            
            pods = None
            for label_selector in label_selectors:
                try:
                    pods = self.core_api.list_namespaced_pod(
                        namespace=namespace,
                        label_selector=label_selector,
                    )
                    if pods.items:
                        break
                except ApiException:
                    continue
            
            # For KServe, if label selector didn't work, try finding pods by name pattern
            if is_kserve and (not pods or not pods.items):
                try:
                    all_pods = self.core_api.list_namespaced_pod(namespace=namespace)
                    # Filter pods that start with endpoint_name (KServe naming: {endpoint_name}-predictor-default-{hash})
                    matching_pods = [p for p in all_pods.items if p.metadata.name.startswith(f"{endpoint_name}-predictor")]
                    if matching_pods:
                        # Create a mock response-like object
                        class PodList:
                            items = matching_pods
                        pods = PodList()
                except ApiException:
                    pass
            
            if not pods or not pods.items:
                return "deploying"  # No pods yet
            
            # Check for Pending pods with scheduling issues
            pending_pods = [p for p in pods.items if p.status.phase == "Pending"]
            if pending_pods:
                # Check why pods are pending
                for pod in pending_pods:
                    if pod.status.conditions:
                        for condition in pod.status.conditions:
                            if condition.type == "PodScheduled" and condition.status != "True":
                                reason = condition.reason or "Unknown"
                                message = condition.message or ""
                                logger.warning(
                                    f"Pod {pod.metadata.name} is Pending: {reason} - {message}"
                                )
                                # Common reasons: Unschedulable (resource shortage), WaitForFirstConsumer (storage)
                                if "Unschedulable" in reason or "Insufficient" in message:
                                    return "deploying"  # Resource issue, still deploying
                                elif "WaitForFirstConsumer" in reason:
                                    return "deploying"  # Storage issue, still deploying
                return "deploying"  # Pending pods mean still deploying
            
            # Check pod phases
            pod_phases = [pod.status.phase for pod in pods.items]
            ready_count = sum(1 for pod in pods.items if self._is_pod_ready(pod))
            total_count = len(pods.items)
            
            # If all pods are running and ready
            if all(phase == "Running" for phase in pod_phases) and ready_count == total_count and total_count > 0:
                return "healthy"
            
            # If any pod is in error state
            if any(phase in ["Failed", "Error"] for phase in pod_phases):
                return "failed"
            
            # If pods are still being created or starting
            if any(phase in ["Pending", "ContainerCreating"] for phase in pod_phases):
                return "deploying"
            
            # If some pods are ready but not all
            if ready_count > 0 and ready_count < total_count:
                return "degraded"
            
            return "deploying"
        except ApiException as e:
            logger.warning(f"Failed to check pod status for {endpoint_name}: {e}")
            return None
    
    @staticmethod
    def _is_pod_ready(pod) -> bool:
        """Check if a pod is ready."""
        if not pod.status.conditions:
            return False
        for condition in pod.status.conditions:
            if condition.type == "Ready":
                return condition.status == "True"
        return False

    @staticmethod
    def _map_deployment_status(status) -> str:
        """Map Kubernetes deployment status to our status enum."""
        if status.ready_replicas == status.replicas and status.replicas > 0:
            return "healthy"
        if status.unavailable_replicas:
            return "degraded"
        if status.replicas == 0:
            return "failed"
        return "deploying"

