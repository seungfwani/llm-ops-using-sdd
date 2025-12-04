"""Pydantic schemas for workflow orchestration API requests/responses."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PipelineStage(BaseModel):
    """Pipeline stage definition."""
    
    name: str = Field(..., description="Stage name")
    type: str = Field(
        ...,
        pattern="^(data_validation|training|evaluation|deployment)$",
        description="Stage type"
    )
    dependencies: List[str] = Field(default=[], description="List of stage names this stage depends on")
    condition: Optional[Dict[str, Any]] = Field(default=None, description="Optional condition for stage execution")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Stage-specific configuration")


class CreatePipelineRequest(BaseModel):
    """Request schema for creating a workflow pipeline."""
    
    pipeline_name: str = Field(..., description="User-defined pipeline name")
    orchestration_system: Optional[str] = Field(
        default="argo_workflows",
        description="Orchestration system identifier"
    )
    stages: List[PipelineStage] = Field(..., description="List of pipeline stages")
    max_retries: Optional[int] = Field(default=3, ge=0, le=10, description="Maximum retry attempts")


class WorkflowPipelineResponse(BaseModel):
    """Response schema for workflow pipeline."""
    
    id: str = Field(..., description="Pipeline ID")
    pipeline_name: str = Field(..., description="Pipeline name")
    orchestration_system: str = Field(..., description="Orchestration system")
    workflow_id: str = Field(..., description="Workflow ID in orchestration system")
    workflow_namespace: str = Field(..., description="Kubernetes namespace")
    pipeline_definition: Dict[str, Any] = Field(..., description="Pipeline definition")
    stages: List[Dict[str, Any]] = Field(..., description="Pipeline stages")
    status: str = Field(
        ...,
        pattern="^(pending|running|succeeded|failed|cancelled)$",
        description="Pipeline status"
    )
    current_stage: Optional[str] = Field(None, description="Currently executing stage")
    start_time: Optional[datetime] = Field(None, description="Pipeline start time")
    end_time: Optional[datetime] = Field(None, description="Pipeline end time")
    retry_count: int = Field(..., description="Number of retries attempted")
    max_retries: int = Field(..., description="Maximum retries allowed")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class EnvelopeWorkflowPipeline(BaseModel):
    """Envelope response for workflow pipeline operations."""
    
    status: str = Field(..., pattern="^(success|fail)$")
    message: str = Field(default="")
    data: Optional[WorkflowPipelineResponse] = None


class EnvelopeWorkflowPipelineList(BaseModel):
    """Envelope response for workflow pipeline list operations."""
    
    status: str = Field(..., pattern="^(success|fail)$")
    message: str = Field(default="")
    data: Optional[List[WorkflowPipelineResponse]] = None


class EnvelopeWorkflowPipelineDelete(BaseModel):
    """Envelope response for workflow pipeline delete operations."""
    
    status: str = Field(..., pattern="^(success|fail)$")
    message: str = Field(default="")

