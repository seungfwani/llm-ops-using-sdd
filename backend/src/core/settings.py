from __future__ import annotations

from functools import lru_cache
from pydantic import AnyUrl, AnyHttpUrl, SecretStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    See ENV_SETUP.md for detailed configuration guide.
    Create a .env file in the backend directory with your settings.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    # =========================================================================
    # Database Configuration
    # =========================================================================
    # PostgreSQL connection URL
    # Local: postgresql+psycopg://llmops:password@localhost:5432/llmops
    # Kubernetes: postgresql+psycopg://llmops:password@postgresql.llm-ops-dev.svc.cluster.local:5432/llmops
    database_url: AnyUrl = "postgresql+psycopg://llmops:password@localhost:5432/llmops"
    
    # Enable SQLAlchemy query logging (for debugging)
    sqlalchemy_echo: bool = False
    
    # =========================================================================
    # Redis Configuration
    # =========================================================================
    # Redis connection URL
    # Local: redis://localhost:6379/0
    # Kubernetes: redis://redis.llm-ops-dev.svc.cluster.local:6379/0
    redis_url: AnyUrl = "redis://localhost:6379/0"
    
    # =========================================================================
    # Object Storage Configuration (MinIO/S3)
    # =========================================================================
    # Object storage endpoint URL
    # Local: http://localhost:9000
    # Kubernetes: http://minio.llm-ops-dev.svc.cluster.local:9000
    # Production S3: https://s3.amazonaws.com
    object_store_endpoint: AnyUrl = "http://localhost:9000"
    
    # Object storage access credentials
    object_store_access_key: str = "llmops"
    object_store_secret_key: SecretStr = SecretStr("llmops-secret")
    
    # Use HTTPS for object storage (set to true for production S3)
    object_store_secure: bool = False
    
    # Object storage bucket name (unified bucket per namespace)
    # Format: llm-ops-{namespace} (e.g., llm-ops-dev, llm-ops-stg, llm-ops-prod)
    # If not set, will be derived from training_namespace
    # Folder structure within bucket:
    #   - models/{model_id}/{version}/
    #   - datasets/{dataset_id}/{version}/
    #   - training/{job_id}/
    object_store_bucket: str | None = None
    
    # =========================================================================
    # Application Configuration
    # =========================================================================
    # Prometheus metrics namespace
    prometheus_namespace: str = "llm_ops"
    
    # Default required role for API access
    default_required_role: str = "llm-ops-user"
    
    # Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    # Default: INFO
    log_level: str = "INFO"
    
    # =========================================================================
    # Kubernetes Configuration
    # =========================================================================
    # Path to kubeconfig file (leave empty to use default or in-cluster config)
    # Local: ~/.kube/config or /path/to/kubeconfig
    # In-cluster: leave empty (auto-detected)
    kubeconfig_path: str | None = None
    
    @field_validator("kubeconfig_path", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        """Convert empty string to None for optional path fields."""
        if v == "":
            return None
        return v
    
    # Disable SSL verification for Kubernetes API (for self-signed certificates)
    # WARNING: Only use this in development/testing environments
    # Set to True to disable SSL certificate verification (not recommended for production)
    kubernetes_verify_ssl: bool = True
    
    # =========================================================================
    # Serving Configuration
    # =========================================================================
    # Model serving runtime image (vLLM, TGI, etc.)
    # NOTE: This is only used as a last resort fallback. The platform automatically
    # selects appropriate images based on DeploymentSpec.serve_target and model metadata.
    # 
    # Options:
    #   - ghcr.io/huggingface/text-generation-inference:latest (TGI, for HuggingFace models)
    #   - ghcr.io/vllm/vllm:latest (vLLM, for other models)
    #   - python:3.11-slim (NOT RECOMMENDED - only for custom runtime development)
    # 
    # For proper image selection, configure SERVE_IMAGE_GENERATION_GPU/CPU and
    # SERVE_IMAGE_RAG_GPU/CPU environment variables instead. See image_config.py for details.
    # Default: TGI on GHCR as fallback for HuggingFace models
    serving_runtime_image: str = "ghcr.io/huggingface/text-generation-inference:latest"
    
    # Use KServe InferenceService (requires Knative + Istio)
    # Set to False if KServe is not properly installed (missing Knative/Istio dependencies)
    # Set to True if KServe with Knative Serving and Istio is installed
    # Default: False for minimum requirements (CPU-only development)
    use_kserve: bool = False
    
    # KServe controller namespace
    kserve_namespace: str = "kserve"
    
    # Request GPU resources for serving. Set to False to use CPU-only deployment
    # Default: False for minimum requirements (CPU-only development)
    use_gpu: bool = False
    
    # =========================================================================
    # Serving Resource Limits (GPU-enabled)
    # =========================================================================
    # CPU and memory requests/limits when GPU is enabled
    # Format: "1" (1 core), "500m" (0.5 core), "2Gi" (2 gibibytes), "512Mi" (512 mebibytes)
    # Adjust based on your cluster capacity
    # Note: Model download during startup may require additional memory
    # Increase memory_limit if you see OOM kills during model download
    # TGI model downloads can use significant memory - increase if needed
    serving_cpu_request: str = "1"  # CPU request
    serving_cpu_limit: str = "2"  # CPU limit
    serving_memory_request: str = "2Gi"  # Memory request
    serving_memory_limit: str = "16Gi"  # Memory limit (increased for large model downloads)
    
    # =========================================================================
    # Serving Resource Limits (CPU-only)
    # =========================================================================
    # CPU and memory requests/limits when GPU is disabled
    # Minimum requirements for local development (CPU-only mode)
    # These values are optimized for minimum resource usage
    # Note: Model download during startup may require additional memory
    # Increase memory_limit if you see OOM kills during model download
    serving_cpu_only_cpu_request: str = "500m"  # CPU request for CPU-only deployment (minimum)
    serving_cpu_only_cpu_limit: str = "1"  # CPU limit for CPU-only deployment (minimum)
    serving_cpu_only_memory_request: str = "512Mi"  # Memory request for CPU-only deployment (minimum)
    serving_cpu_only_memory_limit: str = "1Gi"  # Memory limit (minimum for small models)

    # Optional override for local development: if set, internal inference calls
    # will use this base URL instead of Kubernetes cluster DNS.
    # Example: http://localhost:8001 (port-forwarded serving service)
    serving_local_base_url: AnyHttpUrl | None = None
    
    # Optional override for inference calls when cluster DNS hostnames are not
    # reachable (e.g., external nodes reachable only via IP). If set, the API
    # will call this base URL directly for model inference.
    # Example: http://10.0.0.5:8000 or http://203.0.113.10:8000
    serving_inference_host_override: AnyHttpUrl | None = None
    
    # =========================================================================
    # Training Resource Limits (CPU-only)
    # =========================================================================
    # CPU and memory requests/limits for CPU-only training jobs
    # Use when useGpu=false is specified in training job submission
    # Format: "4" (4 cores), "8Gi" (8 gibibytes)
    # Note: Reduced defaults for local development (minikube typically has ~6GB memory)
    training_cpu_only_cpu_request: str = "2"  # CPU request for CPU-only training (reduced for local dev)
    training_cpu_only_cpu_limit: str = "4"  # CPU limit for CPU-only training (reduced for local dev)
    training_cpu_only_memory_request: str = "2Gi"  # Memory request for CPU-only training (reduced for local dev)
    training_cpu_only_memory_limit: str = "4Gi"  # Memory limit for CPU-only training (reduced for local dev)

    # =========================================================================
    # Training Resource Limits (GPU-enabled)
    # =========================================================================
    # CPU and memory requests/limits for GPU training jobs
    # Format: "4" (4 cores), "8Gi" (8 gibibytes)
    # Adjust based on your cluster capacity and model size
    training_gpu_cpu_request: str = "4"  # CPU request for GPU training
    training_gpu_cpu_limit: str = "8"  # CPU limit for GPU training
    training_gpu_memory_request: str = "4Gi"  # Memory request for GPU training (reduced for small clusters)
    training_gpu_memory_limit: str = "8Gi"  # Memory limit for GPU training (reduced for small clusters)
    
    # Distributed training uses more resources per pod
    training_gpu_distributed_memory_request: str = "16Gi"  # Memory request for distributed GPU training
    training_gpu_distributed_memory_limit: str = "32Gi"  # Memory limit for distributed GPU training
    
    # =========================================================================
    # Training Configuration
    # =========================================================================
    # Kubernetes namespace for training jobs
    # Format: llm-ops-{environment} (e.g., llm-ops-dev, llm-ops-stg, llm-ops-prod)
    # Default: llm-ops-dev for local development
    training_namespace: str = "llm-ops-dev"
    
    # GPU type options (per-environment). Accepts comma-separated strings or lists.
    training_gpu_types_dev: list[str] | str | None = None
    training_gpu_types_stg: list[str] | str | None = None
    training_gpu_types_prod: list[str] | str | None = None
    
    @field_validator(
        "training_gpu_types_dev",
        "training_gpu_types_stg",
        "training_gpu_types_prod",
        mode="before",
    )
    @classmethod
    def _parse_gpu_types(cls, v):
        """Normalize GPU type lists from env strings."""
        if v is None:
            return []
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, (list, tuple)):
            return [str(item).strip() for item in v if str(item).strip()]
        return []
    
    # GPU node selector (optional, for targeting specific GPU nodes)
    # Example: {"accelerator": "nvidia-tesla-v100"} or {"node-type": "gpu"}
    # Leave empty dict {} to allow scheduling on any node
    training_gpu_node_selector: dict = {}
    
    # GPU node tolerations (optional, for nodes with taints)
    # Example: [{"key": "nvidia.com/gpu", "operator": "Exists", "effect": "NoSchedule"}]
    # Leave empty list [] if no tolerations needed
    training_gpu_tolerations: list = []
    
    # API base URL for training pods to record metrics
    # Leave empty ("") to disable metric recording from training pods
    # Format options:
    #   - Same namespace: http://{service-name}:{port} (e.g., http://llm-ops-api:8000)
    #   - Cross namespace: http://{service-name}.{namespace}.svc.cluster.local:{port}
    #   - External URL: http://api.example.com:8000 (if API is accessible from cluster)
    #   - Local development (minikube): http://host.minikube.internal:8000/llm-ops/v1
    #   - Local development (Docker Desktop): http://host.docker.internal:8000/llm-ops/v1
    #   - Local development (general): http://{your-local-ip}:8000/llm-ops/v1
    #   - Example: http://llm-ops-api.llm-ops-dev.svc.cluster.local:8000/llm-ops/v1
    # Note: For local development, use host.minikube.internal (minikube) or host.docker.internal (Docker Desktop)
    #       or your local machine's IP address that is accessible from Kubernetes cluster
    training_api_base_url: str = ""
    
    # =========================================================================
    # Training Job Status Sync Configuration
    # =========================================================================
    # Interval in seconds for checking training job statuses (default: 30 seconds)
    # Set to 0 to disable automatic status checking
    training_job_status_sync_interval: int = 30
    
    # =========================================================================
    # Hugging Face Import Configuration
    # =========================================================================
    # Maximum model size in GB that can be imported from Hugging Face Hub
    # Set to 0 or negative value to disable size limit
    # Default: 5 GB
    huggingface_max_download_size_gb: float = 5.0
    
    # Number of concurrent uploads to MinIO/S3 when importing models
    # Higher values increase upload speed but may consume more resources
    # Recommended: 5-10 for most cases, adjust based on network bandwidth and server resources
    # Default: 5 concurrent uploads
    huggingface_concurrent_uploads: int = 5
    
    # =========================================================================
    # Open Source Integration Configuration
    # =========================================================================
    # Integration feature flags (enable/disable integrations)
    experiment_tracking_enabled: bool = False
    experiment_tracking_system: str = "mlflow"  # Options: "mlflow", "wandb", etc.
    serving_framework_enabled: bool = False
    serving_framework_default: str = "kserve"  # Options: "kserve", "ray_serve", etc.
    workflow_orchestration_enabled: bool = False
    workflow_orchestration_system: str = "argo_workflows"  # Options: "argo_workflows", "kubeflow", etc.
    model_registry_enabled: bool = True  # Default to True for better UX
    model_registry_default: str = "huggingface"  # Options: "huggingface", "modelscope", etc.
    data_versioning_enabled: bool = False
    data_versioning_system: str = "dvc"  # Options: "dvc", "lakefs", etc.
    
    # Environment identifier (dev, stg, prod)
    environment: str = "dev"
    
    # MLflow Configuration
    mlflow_tracking_uri: AnyHttpUrl | None = None  # e.g., http://mlflow-service.mlflow.svc.cluster.local:5000
    mlflow_enabled: bool = False
    mlflow_backend_store_uri: str | None = None  # PostgreSQL URI for MLflow backend
    mlflow_default_artifact_root: str | None = None  # S3 URI for MLflow artifacts
    
    # KServe Configuration (enhanced)
    kserve_namespace: str = "kserve"  # Already exists, keeping for reference
    
    # Argo Workflows Configuration
    argo_workflows_enabled: bool = False
    argo_workflows_namespace: str = "argo"
    argo_workflows_controller_service: str = "argo-workflows-server.argo.svc.cluster.local:2746"
    
    # Hugging Face Hub Configuration
    huggingface_hub_enabled: bool = False
    huggingface_hub_token: SecretStr | None = None  # Optional, for private repos
    huggingface_hub_cache_dir: str = "/tmp/hf_cache"
    
    # DVC Configuration
    dvc_enabled: bool = False
    dvc_remote_name: str = "minio"
    dvc_remote_url: str | None = None  # e.g., s3://datasets-dvc
    dvc_cache_dir: str = "/tmp/dvc-cache"


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    # If object_store_bucket is not set, derive it from training_namespace
    if settings.object_store_bucket is None:
        # training_namespace is already in format "llm-ops-{env}"
        settings.object_store_bucket = settings.training_namespace
    return settings


def get_object_store_bucket() -> str:
    """Get the unified bucket name for object storage."""
    settings = get_settings()
    return settings.object_store_bucket or settings.training_namespace

