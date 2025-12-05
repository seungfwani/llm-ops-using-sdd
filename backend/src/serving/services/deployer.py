"""Serving deployment controller for Kubernetes."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID, uuid4

from kubernetes import client, config
from kubernetes.client.rest import ApiException

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

        # Use default serving runtime image from settings if not provided
        if serving_runtime_image is None:
            serving_runtime_image = settings.serving_runtime_image

        # Use GPU setting from parameter or fallback to settings
        if use_gpu is None:
            use_gpu = settings.use_gpu

        # Use KServe InferenceService if enabled, otherwise use raw Deployment
        if settings.use_kserve:
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
        
        # Build command arguments for vLLM or TGI
        container_args = None
        if is_vllm:
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
        
        # For TGI, check if we need init container (only if no HF model ID)
        init_containers = []
        volumes = []
        volume_mounts = []
        
        if is_tgi:
            # Check if we have Hugging Face model ID (already set in container_args above)
            # If we have HF model ID, TGI will download directly - no init container needed
            hf_model_id_in_args = container_args and "--model-id" in container_args
            
            if not hf_model_id_in_args:
                # No HF model ID - try to use init container to download from S3
                # But TGI doesn't work well with local paths, so this is a fallback
                logger.warning("TGI without Hugging Face model ID may not work correctly")
                logger.warning("Consider importing model from Hugging Face to get huggingface_model_id in metadata")
                
                # Create init container to download model from S3 to shared volume
                # This prevents OOM during model download in the main container
                model_local_path = "/models/model"
                
                # Create volume for sharing model files between init and main containers
                volumes.append(
                    client.V1Volume(
                        name="model-storage",
                        empty_dir=client.V1EmptyDirVolumeSource(size_limit="100Gi"),  # Adjust based on model size
                    )
                )
                
                # Volume mount for both containers
                volume_mount = client.V1VolumeMount(
                    name="model-storage",
                    mount_path=model_local_path,
                )
                volume_mounts.append(volume_mount)
                
                # Init container to download from S3
                init_container = client.V1Container(
                    name=f"{endpoint_name}-model-downloader",
                    image="amazon/aws-cli:latest",  # AWS CLI image for S3 access
                    command=["/bin/sh"],
                    args=[
                        "-c",
                        f"""
                        set -e
                        echo "Downloading model from {model_storage_uri}..."
                        # Extract bucket and prefix from S3 URI
                        BUCKET=$(echo {model_storage_uri} | sed 's|s3://||' | cut -d'/' -f1)
                        PREFIX=$(echo {model_storage_uri} | sed 's|s3://||' | cut -d'/' -f2-)
                        echo "Bucket: $BUCKET, Prefix: $PREFIX"
                        # Download all files recursively
                        aws s3 sync s3://$BUCKET/$PREFIX {model_local_path} --endpoint-url $AWS_ENDPOINT_URL
                        echo "Model download completed"
                        ls -lah {model_local_path}
                        """,
                    ],
                    env=[
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
                        client.V1EnvVar(name="AWS_DEFAULT_REGION", value="us-east-1"),
                    ],
                    volume_mounts=[volume_mount],
                    resources=client.V1ResourceRequirements(
                        requests={"memory": "2Gi", "cpu": "1"},
                        limits={"memory": "4Gi", "cpu": "2"},  # Separate resources for download
                    ),
                )
                init_containers.append(init_container)
                
                # Set MODEL_ID env var to local path as fallback
                if not container_args:
                    container_args = []
                env_vars.append(client.V1EnvVar(name="MODEL_ID", value=model_local_path))
        
        container = client.V1Container(
            name=f"{endpoint_name}-serving",
            image=serving_runtime_image,
            image_pull_policy="IfNotPresent",  # Avoid pulling latest from remote registry when local image exists
            args=container_args,  # Add args for vLLM
            ports=[client.V1ContainerPort(container_port=8000, name="http")],
            resources=client.V1ResourceRequirements(
                requests=resource_requests,
                limits=resource_limits,
            ),
            env=env_vars,
            volume_mounts=volume_mounts,
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
            self.core_api.create_namespaced_service(namespace=namespace, body=service)

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
                self.autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
                    namespace=namespace, body=hpa
                )
                logger.info(f"Created HPA for {endpoint_name}")

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
            self.networking_api.create_namespaced_ingress(namespace=namespace, body=ingress)
            logger.info(f"Created Ingress for {endpoint_name} at route {route}")

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
            # Fallback to legacy implementation if adapter fails
            logger.warning("Falling back to legacy KServe deployment")
            return self._deploy_with_kserve_legacy(
                endpoint_name=endpoint_name,
                model_storage_uri=model_storage_uri,
                route=route,
                min_replicas=min_replicas,
                max_replicas=max_replicas,
                autoscale_policy=autoscale_policy,
                namespace=namespace,
                serving_runtime_image=serving_runtime_image,
                use_gpu=use_gpu,
                model_metadata=model_metadata,
            )
    
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

            # Build container args:
            # - vLLM: explicit --model/--host/--port args (and --device cpu if CPU mode)
            # - non‑vLLM: no args so the image can use its own entrypoint/CMD
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
            else:
                container_args = None

            # Detect TGI image
            is_tgi_kserve = "text-generation" in serving_runtime_image.lower() or "tgi" in serving_runtime_image.lower()

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
        """Delete a serving endpoint from Kubernetes."""
        if settings.use_kserve:
            return self._delete_kserve(endpoint_name, namespace)
        
        # Legacy: Delete raw Deployment and related resources
        try:
            # Delete HPA if it exists
            try:
                self.autoscaling_api.delete_namespaced_horizontal_pod_autoscaler(
                    name=f"{endpoint_name}-hpa",
                    namespace=namespace,
                )
                logger.info(f"Deleted HPA for {endpoint_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete HPA for {endpoint_name}: {e}")
            
            # Delete Ingress if it exists
            try:
                self.networking_api.delete_namespaced_ingress(
                    name=f"{endpoint_name}-ingress",
                    namespace=namespace,
                )
                logger.info(f"Deleted Ingress for {endpoint_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete Ingress for {endpoint_name}: {e}")
            
            # Delete Service if it exists
            try:
                self.core_api.delete_namespaced_service(
                    name=f"{endpoint_name}-svc",
                    namespace=namespace,
                )
                logger.info(f"Deleted Service for {endpoint_name}")
            except ApiException as e:
                if e.status != 404:
                    logger.warning(f"Failed to delete Service for {endpoint_name}: {e}")
            
            # Delete Deployment
            try:
                self.apps_api.delete_namespaced_deployment(
                    name=endpoint_name,
                    namespace=namespace,
                )
                logger.info(f"Deleted Deployment {endpoint_name}")
            except ApiException as e:
                if e.status == 404:
                    logger.warning(f"Deployment {endpoint_name} not found, may already be deleted")
                else:
                    logger.error(f"Failed to delete Deployment {endpoint_name}: {e}")
                    raise
            
            return True
        except ApiException as e:
            logger.error(f"Failed to delete endpoint {endpoint_name}: {e}")
            return False

    def _delete_kserve(
        self, endpoint_name: str, namespace: str = "default"
    ) -> bool:
        """Delete KServe InferenceService."""
        try:
            self.custom_api.delete_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=endpoint_name,
            )
            logger.info(f"Deleted KServe InferenceService {endpoint_name}")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"InferenceService {endpoint_name} not found, may already be deleted")
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

