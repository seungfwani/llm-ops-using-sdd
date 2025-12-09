"""Pydantic schemas for serving API requests/responses."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ServingEndpointRequest(BaseModel):
    """Request schema for deploying a serving endpoint."""

    modelId: str = Field(..., description="Model catalog entry ID")
    version: str = Field(..., description="Model version string")
    environment: str = Field(..., pattern="^(dev|stg|prod)$")
    route: str = Field(..., description="Ingress route path")
    minReplicas: int = Field(default=1, ge=1)
    maxReplicas: int = Field(default=3, ge=1)
    autoscalePolicy: Optional[dict] = Field(default=None)
    promptPolicyId: Optional[str] = Field(default=None)
    rollbackPlan: str = Field(..., description="Human-readable rollback plan or link to runbook")
    useGpu: Optional[bool] = Field(default=None, description="Whether to request GPU resources. If not provided, uses default from settings")
    servingRuntimeImage: Optional[str] = Field(default=None, description="Container image for model serving runtime (e.g., vLLM, TGI). If not provided, uses default from settings")
    cpuRequest: Optional[str] = Field(default=None, description="CPU request (e.g., '2', '1000m'). If not provided, uses default from settings")
    cpuLimit: Optional[str] = Field(default=None, description="CPU limit (e.g., '4', '2000m'). If not provided, uses default from settings")
    memoryRequest: Optional[str] = Field(default=None, description="Memory request (e.g., '4Gi', '2G'). If not provided, uses default from settings")
    memoryLimit: Optional[str] = Field(default=None, description="Memory limit (e.g., '8Gi', '4G'). If not provided, uses default from settings")
    servingFramework: Optional[str] = Field(default=None, description="Serving framework name (e.g., 'kserve', 'ray_serve')")
    deploymentSpec: Optional[DeploymentSpec] = Field(default=None, description="DeploymentSpec for training-serving-spec.md compliance")


class ServingEndpointResponse(BaseModel):
    """Response schema for serving endpoint operations."""

    id: str
    modelId: str
    version: str
    environment: str
    route: str
    runtimeImage: Optional[str] = None
    status: str
    minReplicas: int
    maxReplicas: int
    promptPolicyId: Optional[str] = None
    useGpu: Optional[bool] = None
    cpuRequest: Optional[str] = None
    cpuLimit: Optional[str] = None
    memoryRequest: Optional[str] = None
    memoryLimit: Optional[str] = None
    autoscalePolicy: Optional[dict] = None
    deploymentSpec: Optional[DeploymentSpec] = None
    lastHealthCheck: Optional[datetime] = None
    rollbackPlan: Optional[str] = None
    createdAt: datetime

    class Config:
        from_attributes = True


class ServingEndpointPatch(BaseModel):
    """Patch schema for updating a serving endpoint."""

    autoscalePolicy: Optional[dict] = Field(default=None, description="Updated autoscaling policy")
    promptPolicyId: Optional[str] = Field(default=None, description="Prompt policy binding")
    status: Optional[str] = Field(default=None, pattern="^(deploying|healthy|degraded|failed)$", description="Operational status override")


class EnvelopeServingEndpoint(BaseModel):
    """Standard API envelope for serving endpoint responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ServingEndpointResponse] = None


class EnvelopeServingEndpointList(BaseModel):
    """Standard API envelope for serving endpoint list responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[list[ServingEndpointResponse]] = None


class PromptExperimentRequest(BaseModel):
    """Request schema for creating a prompt A/B experiment."""

    templateAId: str = Field(..., description="Template A ID")
    templateBId: str = Field(..., description="Template B ID")
    allocation: int = Field(..., ge=0, le=100, description="Percentage allocation for template A")
    metric: str = Field(..., description="Metric to optimize (e.g., latency_ms, user_satisfaction)")


class PromptExperimentResponse(BaseModel):
    """Response schema for prompt experiment operations."""

    id: str
    templateAId: str
    templateBId: str
    allocation: int
    metric: str
    startAt: datetime
    endAt: Optional[datetime] = None
    winnerTemplateId: Optional[str] = None

    class Config:
        from_attributes = True


class EnvelopePromptExperiment(BaseModel):
    """Standard API envelope for prompt experiment responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[PromptExperimentResponse] = None


class ChatMessage(BaseModel):
    """Chat message schema."""

    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    """Request schema for chat completion."""

    messages: list[ChatMessage] = Field(..., description="List of chat messages")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    max_tokens: int = Field(default=500, ge=1, le=4000, description="Maximum tokens to generate")
    # Optional template name expected by the serving runtime (e.g., vLLM prompt template)
    # If provided, it is forwarded to the model service as-is.
    template: str | None = Field(default=None, description="Prompt template name expected by the model service")


class ChatCompletionChoice(BaseModel):
    """Chat completion choice schema."""

    message: ChatMessage
    finish_reason: Optional[str] = Field(default=None, description="Reason for finishing")


class ChatCompletionUsage(BaseModel):
    """Token usage schema."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionData(BaseModel):
    """Chat completion response data."""

    choices: list[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None


class ChatCompletionResponse(BaseModel):
    """Response schema for chat completion."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ChatCompletionData] = None


class ServingDeploymentResponse(BaseModel):
    """Response schema for serving deployment operations."""

    id: str
    serving_endpoint_id: str
    serving_framework: str
    framework_resource_id: str
    framework_namespace: str
    replica_count: int
    min_replicas: int
    max_replicas: int
    autoscaling_metrics: Optional[dict] = None
    resource_requests: Optional[dict] = None
    resource_limits: Optional[dict] = None
    framework_status: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UpdateDeploymentRequest(BaseModel):
    """Request schema for updating a serving deployment."""

    min_replicas: Optional[int] = Field(None, ge=0)
    max_replicas: Optional[int] = Field(None, ge=1)
    autoscaling_metrics: Optional[dict] = None
    resource_requests: Optional[dict] = None
    resource_limits: Optional[dict] = None


class EnvelopeServingDeployment(BaseModel):
    """Standard API envelope for serving deployment responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ServingDeploymentResponse] = None


class ServingFramework(BaseModel):
    """Response schema for serving framework information."""

    name: str
    display_name: str
    enabled: bool
    capabilities: list[str]


class EnvelopeServingFrameworks(BaseModel):
    """Standard API envelope for serving frameworks list."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[dict] = None  # Will contain {"frameworks": list[ServingFramework]}


class ImageConfigResponse(BaseModel):
    """Response schema for image configuration."""

    train_images: dict[str, dict[str, str]] = Field(
        ..., description="Training images by job type (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING) and variant (gpu, cpu)"
    )
    serve_images: dict[str, dict[str, str]] = Field(
        ..., description="Serving images by serve target (GENERATION, RAG) and variant (gpu, cpu)"
    )


class EnvelopeImageConfig(BaseModel):
    """Standard API envelope for image configuration responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[ImageConfigResponse] = None


class RedeployEndpointRequest(BaseModel):
    """Request schema for redeploying a serving endpoint."""

    useGpu: Optional[bool] = Field(default=None, description="Whether to request GPU resources. If not provided, uses endpoint's current setting")
    servingRuntimeImage: Optional[str] = Field(default=None, description="Container image for model serving runtime. If not provided, uses endpoint's current setting")
    cpuRequest: Optional[str] = Field(default=None, description="CPU request (e.g., '2', '1000m'). If not provided, uses endpoint's current/default setting")
    cpuLimit: Optional[str] = Field(default=None, description="CPU limit (e.g., '4', '2000m'). If not provided, uses endpoint's current/default setting")
    memoryRequest: Optional[str] = Field(default=None, description="Memory request (e.g., '4Gi', '2G'). If not provided, uses endpoint's current/default setting")
    memoryLimit: Optional[str] = Field(default=None, description="Memory limit (e.g., '8Gi', '4G'). If not provided, uses endpoint's current/default setting")
    autoscalePolicy: Optional[dict] = Field(default=None, description="Autoscaling policy configuration. If not provided, uses endpoint's current setting")
    servingFramework: Optional[str] = Field(default=None, description="Serving framework name (e.g., 'kserve', 'ray_serve'). If not provided, uses endpoint's current setting")
    deploymentSpec: Optional[DeploymentSpec] = Field(default=None, description="DeploymentSpec for redeployment. If not provided, uses endpoint's existing deployment_spec or reconstructs from endpoint metadata")


# DeploymentSpec schema based on training-serving-spec.md
class DeploymentResources(BaseModel):
    """Deployment resource requirements schema."""

    gpus: int = Field(default=0, ge=0, description="Number of GPUs")
    gpu_memory_gb: Optional[int] = Field(None, ge=0, description="GPU memory in GB")


class RuntimeConstraints(BaseModel):
    """Runtime constraints schema."""

    max_concurrent_requests: int = Field(default=256, ge=1, description="Maximum concurrent requests")
    max_input_tokens: int = Field(default=4096, ge=1, description="Maximum input tokens")
    max_output_tokens: int = Field(default=1024, ge=1, description="Maximum output tokens")


class TrafficSplit(BaseModel):
    """Traffic split configuration for rollout strategies."""

    old: int = Field(..., ge=0, le=100, description="Percentage for old version")
    new: int = Field(..., ge=0, le=100, description="Percentage for new version")

    def model_post_init(self, __context) -> None:
        """Validate that old + new equals 100."""
        if self.old + self.new != 100:
            raise ValueError("Traffic split percentages must sum to 100")


class RolloutStrategy(BaseModel):
    """Rollout strategy configuration."""

    strategy: str = Field(..., pattern="^(blue-green|canary)$", description="Rollout strategy: blue-green or canary")
    traffic_split: Optional[TrafficSplit] = Field(
        None,
        description="Traffic split configuration (required for canary, optional for blue-green)"
    )


class DeploymentSpec(BaseModel):
    """
    Deployment specification schema based on training-serving-spec.md.
    
    Enforces standardized structure for all serving deployments:
    - model_ref: Reference to trained model artifact
    - model_family: Must match training job's model_family
    - job_type: Inherited from training job (SFT, RAG_TUNING, RLHF, etc.)
    - serve_image: Automatically selected based on serve_target type (GENERATION or RAG)
    - resources: gpus, gpu_memory_gb
    - runtime: max_concurrent_requests, max_input_tokens, max_output_tokens
    - rollout: strategy (blue-green|canary), traffic_split
    """

    model_ref: str = Field(..., description="Reference to trained model artifact")
    model_family: str = Field(..., description="Model family (must match training job's model_family)")
    job_type: str = Field(
        ...,
        pattern="^(SFT|RAG_TUNING|RLHF|PRETRAIN|EMBEDDING)$",
        description="Job type inherited from training job"
    )
    serve_target: str = Field(
        ...,
        pattern="^(GENERATION|RAG)$",
        description="Serve target type: GENERATION or RAG"
    )
    resources: DeploymentResources = Field(..., description="Resource requirements")
    runtime: RuntimeConstraints = Field(..., description="Runtime constraints")
    rollout: Optional[RolloutStrategy] = Field(None, description="Rollout strategy configuration")
    use_gpu: bool = Field(default=True, description="Whether to use GPU resources (for CPU fallback)")

    class Config:
        json_schema_extra = {
            "example": {
                "model_ref": "llama-3-8b-sft-v1",
                "model_family": "llama",
                "job_type": "SFT",
                "serve_target": "GENERATION",
                "resources": {
                    "gpus": 2,
                    "gpu_memory_gb": 80
                },
                "runtime": {
                    "max_concurrent_requests": 256,
                    "max_input_tokens": 4096,
                    "max_output_tokens": 1024
                },
                "rollout": {
                    "strategy": "canary",
                    "traffic_split": {
                        "old": 90,
                        "new": 10
                    }
                },
                "use_gpu": True
            }
        }

