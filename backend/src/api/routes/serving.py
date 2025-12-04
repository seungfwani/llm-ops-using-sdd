"""Serving endpoint API routes."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.database import get_session
from serving import schemas
from serving.serving_service import ServingService

router = APIRouter(prefix="/llm-ops/v1/serving", tags=["serving"])


def get_serving_service(session: Session = Depends(get_session)) -> ServingService:
    """Dependency to get serving service."""
    return ServingService(session)


@router.get("/endpoints", response_model=schemas.EnvelopeServingEndpointList)
def list_endpoints(
    environment: Optional[str] = Query(None, pattern="^(dev|stg|prod)$", description="Filter by deployment environment"),
    modelId: Optional[str] = Query(None, description="Filter by model catalog entry ID"),
    status: Optional[str] = Query(None, pattern="^(deploying|healthy|degraded|failed)$", description="Filter by endpoint status"),
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpointList:
    """List serving endpoints with optional filters."""
    try:
        endpoints = service.list_endpoints(
            environment=environment,
            model_entry_id=modelId,
            status=status,
        )
        endpoint_responses = [
            schemas.ServingEndpointResponse(
                id=str(endpoint.id),
                modelId=str(endpoint.model_entry_id),
                environment=endpoint.environment,
                route=endpoint.route,
                runtimeImage=endpoint.runtime_image,
                status=endpoint.status,
                minReplicas=endpoint.min_replicas,
                maxReplicas=endpoint.max_replicas,
                useGpu=endpoint.use_gpu,
                cpuRequest=endpoint.cpu_request,
                cpuLimit=endpoint.cpu_limit,
                memoryRequest=endpoint.memory_request,
                memoryLimit=endpoint.memory_limit,
                createdAt=endpoint.created_at,
            )
            for endpoint in endpoints
        ]
        return schemas.EnvelopeServingEndpointList(
            status="success",
            message="",
            data=endpoint_responses,
        )
    except Exception as e:
        return schemas.EnvelopeServingEndpointList(
            status="fail",
            message=f"Failed to list endpoints: {str(e)}",
            data=None,
        )


@router.post("/endpoints", response_model=schemas.EnvelopeServingEndpoint)
def deploy_endpoint(
    request: schemas.ServingEndpointRequest,
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpoint:
    """Deploy an approved model to a serving endpoint."""
    try:
        endpoint = service.deploy_endpoint(
            model_entry_id=request.modelId,
            environment=request.environment,
            route=request.route,
            min_replicas=request.minReplicas,
            max_replicas=request.maxReplicas,
            autoscale_policy=request.autoscalePolicy,
            prompt_policy_id=request.promptPolicyId,
            use_gpu=request.useGpu,
            serving_runtime_image=request.servingRuntimeImage,
            cpu_request=request.cpuRequest,
            cpu_limit=request.cpuLimit,
            memory_request=request.memoryRequest,
            memory_limit=request.memoryLimit,
        )
        return schemas.EnvelopeServingEndpoint(
            status="success",
            message="Serving endpoint deployed successfully",
            data=schemas.ServingEndpointResponse(
                id=str(endpoint.id),
                modelId=str(endpoint.model_entry_id),
                environment=endpoint.environment,
                route=endpoint.route,
                runtimeImage=endpoint.runtime_image,
                status=endpoint.status,
                minReplicas=endpoint.min_replicas,
                maxReplicas=endpoint.max_replicas,
                useGpu=endpoint.use_gpu,
                cpuRequest=endpoint.cpu_request,
                cpuLimit=endpoint.cpu_limit,
                memoryRequest=endpoint.memory_request,
                memoryLimit=endpoint.memory_limit,
                createdAt=endpoint.created_at,
            ),
        )
    except ValueError as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=f"Failed to deploy endpoint: {str(e)}",
            data=None,
        )


@router.get("/endpoints/{endpointId}", response_model=schemas.EnvelopeServingEndpoint)
def get_endpoint(
    endpointId: str,
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpoint:
    """Retrieve serving endpoint status."""
    endpoint = service.get_endpoint(endpointId)
    if not endpoint:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=f"Serving endpoint {endpointId} not found",
            data=None,
        )

    return schemas.EnvelopeServingEndpoint(
        status="success",
        message="",
        data=schemas.ServingEndpointResponse(
            id=str(endpoint.id),
            modelId=str(endpoint.model_entry_id),
            environment=endpoint.environment,
            route=endpoint.route,
            runtimeImage=endpoint.runtime_image,
            status=endpoint.status,
            minReplicas=endpoint.min_replicas,
            maxReplicas=endpoint.max_replicas,
            useGpu=endpoint.use_gpu,
            cpuRequest=endpoint.cpu_request,
            cpuLimit=endpoint.cpu_limit,
            memoryRequest=endpoint.memory_request,
            memoryLimit=endpoint.memory_limit,
            createdAt=endpoint.created_at,
        ),
    )


@router.post("/endpoints/{endpointId}/rollback", response_model=schemas.EnvelopeServingEndpoint)
def rollback_endpoint(
    endpointId: str,
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpoint:
    """Rollback a serving endpoint to the previous version."""
    try:
        success = service.rollback_endpoint(endpointId)
        if not success:
            return schemas.EnvelopeServingEndpoint(
                status="fail",
                message=f"Could not rollback endpoint {endpointId}",
                data=None,
            )

        endpoint = service.get_endpoint(endpointId)
        return schemas.EnvelopeServingEndpoint(
            status="success",
            message="Endpoint rolled back successfully",
            data=schemas.ServingEndpointResponse(
                id=str(endpoint.id),
                modelId=str(endpoint.model_entry_id),
                environment=endpoint.environment,
                route=endpoint.route,
                runtimeImage=endpoint.runtime_image,
                status=endpoint.status,
                minReplicas=endpoint.min_replicas,
                maxReplicas=endpoint.max_replicas,
                useGpu=endpoint.use_gpu,
                cpuRequest=endpoint.cpu_request,
                cpuLimit=endpoint.cpu_limit,
                memoryRequest=endpoint.memory_request,
                memoryLimit=endpoint.memory_limit,
                createdAt=endpoint.created_at,
            ) if endpoint else None,
        )
    except ValueError as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=f"Failed to rollback endpoint: {str(e)}",
            data=None,
        )


@router.post("/endpoints/{endpointId}/redeploy", response_model=schemas.EnvelopeServingEndpoint)
def redeploy_endpoint(
    endpointId: str,
    useGpu: Optional[bool] = Query(None, description="Whether to request GPU resources. If not provided, uses endpoint's current setting"),
    servingRuntimeImage: Optional[str] = Query(None, description="Container image for model serving runtime. If not provided, uses endpoint's current setting"),
    cpuRequest: Optional[str] = Query(None, description="CPU request (e.g., '2', '1000m'). If not provided, uses endpoint's current/default setting"),
    cpuLimit: Optional[str] = Query(None, description="CPU limit (e.g., '4', '2000m'). If not provided, uses endpoint's current/default setting"),
    memoryRequest: Optional[str] = Query(None, description="Memory request (e.g., '4Gi', '2G'). If not provided, uses endpoint's current/default setting"),
    memoryLimit: Optional[str] = Query(None, description="Memory limit (e.g., '8Gi', '4G'). If not provided, uses endpoint's current/default setting"),
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpoint:
    """Redeploy a serving endpoint with the same or updated configuration."""
    try:
        endpoint = service.redeploy_endpoint(
            endpointId,
            use_gpu=useGpu,
            serving_runtime_image=servingRuntimeImage,
            cpu_request=cpuRequest,
            cpu_limit=cpuLimit,
            memory_request=memoryRequest,
            memory_limit=memoryLimit,
        )
        return schemas.EnvelopeServingEndpoint(
            status="success",
            message="Serving endpoint redeployed successfully",
            data=schemas.ServingEndpointResponse(
                id=str(endpoint.id),
                modelId=str(endpoint.model_entry_id),
                environment=endpoint.environment,
                route=endpoint.route,
                runtimeImage=endpoint.runtime_image,
                status=endpoint.status,
                minReplicas=endpoint.min_replicas,
                maxReplicas=endpoint.max_replicas,
                useGpu=endpoint.use_gpu,
                cpuRequest=endpoint.cpu_request,
                cpuLimit=endpoint.cpu_limit,
                memoryRequest=endpoint.memory_request,
                memoryLimit=endpoint.memory_limit,
                createdAt=endpoint.created_at,
            ),
        )
    except ValueError as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=f"Failed to redeploy endpoint: {str(e)}",
            data=None,
        )


@router.delete("/endpoints/{endpointId}", response_model=schemas.EnvelopeServingEndpoint)
def delete_endpoint(
    endpointId: str,
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpoint:
    """Delete a serving endpoint and its Kubernetes resources."""
    try:
        # Get endpoint before deletion for response
        endpoint = service.get_endpoint(endpointId)
        if not endpoint:
            return schemas.EnvelopeServingEndpoint(
                status="fail",
                message=f"Serving endpoint {endpointId} not found",
                data=None,
            )
        
        # Delete the endpoint
        success = service.delete_endpoint(endpointId)
        if not success:
            return schemas.EnvelopeServingEndpoint(
                status="fail",
                message=f"Failed to delete endpoint {endpointId}",
                data=None,
            )
        
        return schemas.EnvelopeServingEndpoint(
            status="success",
            message="Serving endpoint deleted successfully",
            data=schemas.ServingEndpointResponse(
                id=str(endpoint.id),
                modelId=str(endpoint.model_entry_id),
                environment=endpoint.environment,
                route=endpoint.route,
                runtimeImage=endpoint.runtime_image,
                status=endpoint.status,
                minReplicas=endpoint.min_replicas,
                maxReplicas=endpoint.max_replicas,
                useGpu=endpoint.use_gpu,
                cpuRequest=endpoint.cpu_request,
                cpuLimit=endpoint.cpu_limit,
                memoryRequest=endpoint.memory_request,
                memoryLimit=endpoint.memory_limit,
                createdAt=endpoint.created_at,
            ),
        )
    except ValueError as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=f"Failed to delete endpoint: {str(e)}",
            data=None,
        )

