"""Workflow orchestration API routes."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_session
from workflows import schemas
from services.workflow_orchestration_service import WorkflowOrchestrationService
from integrations.orchestration.pipeline_parser import PipelineParseError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-ops/v1/workflows", tags=["workflows"])


def get_workflow_service(session: Session = Depends(get_session)) -> WorkflowOrchestrationService:
    """Dependency to get workflow orchestration service."""
    return WorkflowOrchestrationService(session)


@router.post("/pipelines", response_model=schemas.EnvelopeWorkflowPipeline, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    request: schemas.CreatePipelineRequest,
    service: WorkflowOrchestrationService = Depends(get_workflow_service),
) -> schemas.EnvelopeWorkflowPipeline:
    """Create a workflow pipeline.
    
    Args:
        request: Pipeline creation request
        service: Workflow orchestration service
    
    Returns:
        Created pipeline response
    """
    try:
        # Convert request to service format
        stages_dict = [
            {
                "name": stage.name,
                "type": stage.type,
                "dependencies": stage.dependencies,
                "condition": stage.condition,
                "config": stage.config,
            }
            for stage in request.stages
        ]
        
        # Create pipeline
        pipeline = service.create_pipeline(
            pipeline_name=request.pipeline_name,
            stages=stages_dict,
            orchestration_system=request.orchestration_system,
            max_retries=request.max_retries,
        )
        
        # Convert to response
        response = schemas.WorkflowPipelineResponse(
            id=str(pipeline.id),
            pipeline_name=pipeline.pipeline_name,
            orchestration_system=pipeline.orchestration_system,
            workflow_id=pipeline.workflow_id,
            workflow_namespace=pipeline.workflow_namespace,
            pipeline_definition=pipeline.pipeline_definition,
            stages=pipeline.stages or [],
            status=pipeline.status,
            current_stage=pipeline.current_stage,
            start_time=pipeline.start_time,
            end_time=pipeline.end_time,
            retry_count=pipeline.retry_count,
            max_retries=pipeline.max_retries,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )
        
        return schemas.EnvelopeWorkflowPipeline(
            status="success",
            message="Pipeline created successfully",
            data=response,
        )
    except PipelineParseError as e:
        logger.error(f"Pipeline parse error: {e}")
        return schemas.EnvelopeWorkflowPipeline(
            status="fail",
            message=f"Invalid pipeline definition: {str(e)}",
            data=None,
        )
    except ValueError as e:
        logger.error(f"Pipeline creation error: {e}")
        return schemas.EnvelopeWorkflowPipeline(
            status="fail",
            message=f"Failed to create pipeline: {str(e)}",
            data=None,
        )
    except Exception as e:
        logger.exception(f"Unexpected error creating pipeline: {e}")
        return schemas.EnvelopeWorkflowPipeline(
            status="fail",
            message=f"Internal server error: {str(e)}",
            data=None,
        )


@router.get("/pipelines/{pipeline_id}", response_model=schemas.EnvelopeWorkflowPipeline)
def get_pipeline(
    pipeline_id: UUID,
    service: WorkflowOrchestrationService = Depends(get_workflow_service),
    update_status: bool = Query(default=False, description="Update status from orchestration system"),
) -> schemas.EnvelopeWorkflowPipeline:
    """Get workflow pipeline by ID.
    
    Args:
        pipeline_id: Pipeline ID
        service: Workflow orchestration service
        update_status: Whether to update status from orchestration system
    
    Returns:
        Pipeline response
    """
    try:
        # Get pipeline
        pipeline = service.get_pipeline(pipeline_id)
        
        if not pipeline:
            return schemas.EnvelopeWorkflowPipeline(
                status="fail",
                message=f"Pipeline {pipeline_id} not found",
                data=None,
            )
        
        # Update status if requested
        if update_status:
            pipeline = service.update_pipeline_status(pipeline_id)
            if not pipeline:
                return schemas.EnvelopeWorkflowPipeline(
                    status="fail",
                    message=f"Pipeline {pipeline_id} not found",
                    data=None,
                )
        
        # Convert to response
        response = schemas.WorkflowPipelineResponse(
            id=str(pipeline.id),
            pipeline_name=pipeline.pipeline_name,
            orchestration_system=pipeline.orchestration_system,
            workflow_id=pipeline.workflow_id,
            workflow_namespace=pipeline.workflow_namespace,
            pipeline_definition=pipeline.pipeline_definition,
            stages=pipeline.stages or [],
            status=pipeline.status,
            current_stage=pipeline.current_stage,
            start_time=pipeline.start_time,
            end_time=pipeline.end_time,
            retry_count=pipeline.retry_count,
            max_retries=pipeline.max_retries,
            created_at=pipeline.created_at,
            updated_at=pipeline.updated_at,
        )
        
        return schemas.EnvelopeWorkflowPipeline(
            status="success",
            message="",
            data=response,
        )
    except Exception as e:
        logger.exception(f"Error getting pipeline: {e}")
        return schemas.EnvelopeWorkflowPipeline(
            status="fail",
            message=f"Failed to get pipeline: {str(e)}",
            data=None,
        )


@router.delete("/pipelines/{pipeline_id}", response_model=schemas.EnvelopeWorkflowPipelineDelete)
def cancel_pipeline(
    pipeline_id: UUID,
    service: WorkflowOrchestrationService = Depends(get_workflow_service),
) -> schemas.EnvelopeWorkflowPipelineDelete:
    """Cancel a workflow pipeline.
    
    Args:
        pipeline_id: Pipeline ID
        service: Workflow orchestration service
    
    Returns:
        Delete response
    """
    try:
        # Cancel pipeline
        pipeline = service.cancel_pipeline(pipeline_id)
        
        if not pipeline:
            return schemas.EnvelopeWorkflowPipelineDelete(
                status="fail",
                message=f"Pipeline {pipeline_id} not found",
            )
        
        return schemas.EnvelopeWorkflowPipelineDelete(
            status="success",
            message="Pipeline cancelled successfully",
        )
    except Exception as e:
        logger.exception(f"Error cancelling pipeline: {e}")
        return schemas.EnvelopeWorkflowPipelineDelete(
            status="fail",
            message=f"Failed to cancel pipeline: {str(e)}",
        )


@router.get("/pipelines", response_model=schemas.EnvelopeWorkflowPipelineList)
def list_pipelines(
    status: Optional[str] = Query(
        None,
        pattern="^(pending|running|succeeded|failed|cancelled)$",
        description="Filter by pipeline status"
    ),
    orchestration_system: Optional[str] = Query(None, description="Filter by orchestration system"),
    service: WorkflowOrchestrationService = Depends(get_workflow_service),
) -> schemas.EnvelopeWorkflowPipelineList:
    """List workflow pipelines with optional filters.
    
    Args:
        status: Optional status filter
        orchestration_system: Optional orchestration system filter
        service: Workflow orchestration service
    
    Returns:
        List of pipelines
    """
    try:
        pipelines = service.list_pipelines(
            status=status,
            orchestration_system=orchestration_system,
        )
        
        pipeline_responses = [
            schemas.WorkflowPipelineResponse(
                id=str(pipeline.id),
                pipeline_name=pipeline.pipeline_name,
                orchestration_system=pipeline.orchestration_system,
                workflow_id=pipeline.workflow_id,
                workflow_namespace=pipeline.workflow_namespace,
                pipeline_definition=pipeline.pipeline_definition,
                stages=pipeline.stages or [],
                status=pipeline.status,
                current_stage=pipeline.current_stage,
                start_time=pipeline.start_time,
                end_time=pipeline.end_time,
                retry_count=pipeline.retry_count,
                max_retries=pipeline.max_retries,
                created_at=pipeline.created_at,
                updated_at=pipeline.updated_at,
            )
            for pipeline in pipelines
        ]
        
        return schemas.EnvelopeWorkflowPipelineList(
            status="success",
            message="",
            data=pipeline_responses,
        )
    except Exception as e:
        logger.exception(f"Error listing pipelines: {e}")
        return schemas.EnvelopeWorkflowPipelineList(
            status="fail",
            message=f"Failed to list pipelines: {str(e)}",
            data=None,
        )

