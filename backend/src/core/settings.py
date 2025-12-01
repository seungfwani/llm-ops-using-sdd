from __future__ import annotations

from functools import lru_cache
from pydantic import AnyUrl, AnyHttpUrl, SecretStr, field_validator
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
    
    # =========================================================================
    # Application Configuration
    # =========================================================================
    # Prometheus metrics namespace
    prometheus_namespace: str = "llm_ops"
    
    # Default required role for API access
    default_required_role: str = "llm-ops-user"
    
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
    
    # =========================================================================
    # Serving Configuration
    # =========================================================================
    # Model serving runtime image (vLLM, TGI, etc.)
    # Options:
    #   - vllm/vllm-server:latest (official vLLM server image)
    #   - vllm/vllm:latest (may not exist, use vllm/vllm-server instead)
    #   - ghcr.io/vllm/vllm:latest (GitHub Container Registry)
    #   - huggingface/text-generation-inference:latest (TGI alternative)
    #   - python:3.11-slim (for custom runtime, requires building your own image)
    # Note: For local development, you may need to build a custom image or use a different runtime
    serving_runtime_image: str = "python:3.11-slim"  # Default to lightweight image for local testing
    
    # Use KServe InferenceService (requires Knative + Istio)
    # Set to False if KServe is not properly installed (missing Knative/Istio dependencies)
    # Set to True if KServe with Knative Serving and Istio is installed
    use_kserve: bool = False
    
    # KServe controller namespace
    kserve_namespace: str = "kserve"
    
    # Request GPU resources for serving. Set to False to use CPU-only deployment
    use_gpu: bool = True
    
    # =========================================================================
    # Serving Resource Limits (GPU-enabled)
    # =========================================================================
    # CPU and memory requests/limits when GPU is enabled
    # Format: "1" (1 core), "500m" (0.5 core), "2Gi" (2 gibibytes), "512Mi" (512 mebibytes)
    # Adjust based on your cluster capacity
    serving_cpu_request: str = "1"  # CPU request
    serving_cpu_limit: str = "2"  # CPU limit
    serving_memory_request: str = "2Gi"  # Memory request
    serving_memory_limit: str = "4Gi"  # Memory limit
    
    # =========================================================================
    # Serving Resource Limits (CPU-only)
    # =========================================================================
    # CPU and memory requests/limits when GPU is disabled
    # Use smaller values for local development
    serving_cpu_only_cpu_request: str = "1"  # CPU request for CPU-only deployment
    serving_cpu_only_cpu_limit: str = "2"  # CPU limit for CPU-only deployment
    serving_cpu_only_memory_request: str = "1Gi"  # Memory request for CPU-only deployment
    serving_cpu_only_memory_limit: str = "2Gi"  # Memory limit for CPU-only deployment

    # Optional override for local development: if set, internal inference calls
    # will use this base URL instead of Kubernetes cluster DNS.
    # Example: http://localhost:8001 (port-forwarded serving service)
    serving_local_base_url: AnyHttpUrl | None = None


@lru_cache()
def get_settings() -> Settings:
    return Settings()

