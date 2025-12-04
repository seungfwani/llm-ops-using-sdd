"""Pydantic schemas for serving API requests/responses."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ServingEndpointRequest(BaseModel):
    """Request schema for deploying a serving endpoint."""

    modelId: str = Field(..., description="Model catalog entry ID")
    environment: str = Field(..., pattern="^(dev|stg|prod)$")
    route: str = Field(..., description="Ingress route path")
    minReplicas: int = Field(default=1, ge=1)
    maxReplicas: int = Field(default=3, ge=1)
    autoscalePolicy: Optional[dict] = Field(default=None)
    promptPolicyId: Optional[str] = Field(default=None)
    useGpu: Optional[bool] = Field(default=None, description="Whether to request GPU resources. If not provided, uses default from settings")
    servingRuntimeImage: Optional[str] = Field(default=None, description="Container image for model serving runtime (e.g., vLLM, TGI). If not provided, uses default from settings")
    cpuRequest: Optional[str] = Field(default=None, description="CPU request (e.g., '2', '1000m'). If not provided, uses default from settings")
    cpuLimit: Optional[str] = Field(default=None, description="CPU limit (e.g., '4', '2000m'). If not provided, uses default from settings")
    memoryRequest: Optional[str] = Field(default=None, description="Memory request (e.g., '4Gi', '2G'). If not provided, uses default from settings")
    memoryLimit: Optional[str] = Field(default=None, description="Memory limit (e.g., '8Gi', '4G'). If not provided, uses default from settings")


class ServingEndpointResponse(BaseModel):
    """Response schema for serving endpoint operations."""

    id: str
    modelId: str
    environment: str
    route: str
    runtimeImage: Optional[str] = None
    status: str
    minReplicas: int
    maxReplicas: int
    useGpu: Optional[bool] = None
    cpuRequest: Optional[str] = None
    cpuLimit: Optional[str] = None
    memoryRequest: Optional[str] = None
    memoryLimit: Optional[str] = None
    createdAt: datetime

    class Config:
        from_attributes = True


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

