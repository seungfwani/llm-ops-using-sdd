"""Serving endpoint API routes."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from catalog import models as catalog_models
from core.database import get_session
from serving import schemas
from serving.serving_service import ServingService
from services.serving_deployment_service import ServingDeploymentService
from integrations.serving.factory import ServingFrameworkFactory
from services.integration_config import IntegrationConfigService

router = APIRouter(prefix="/llm-ops/v1/serving", tags=["serving"])


def get_serving_service(session: Session = Depends(get_session)) -> ServingService:
    """Dependency to get serving service."""
    return ServingService(session)


def get_serving_deployment_service(session: Session = Depends(get_session)) -> ServingDeploymentService:
    """Dependency to get serving deployment service."""
    return ServingDeploymentService(session)


def _build_serving_endpoint_response(endpoint, service: ServingService) -> Optional[schemas.ServingEndpointResponse]:
    """Convert ORM endpoint to response schema with spec-aligned fields."""
    if not endpoint:
        return None

    deployment_spec = None
    if hasattr(endpoint, "deployment_spec") and endpoint.deployment_spec:
        try:
            deployment_spec = schemas.DeploymentSpec(**endpoint.deployment_spec)
        except Exception:
            pass

    version = ""
    model_entry = service.session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
    if model_entry:
        version = model_entry.version

    return schemas.ServingEndpointResponse(
        id=str(endpoint.id),
        modelId=str(endpoint.model_entry_id),
        version=version,
        environment=endpoint.environment,
        route=endpoint.route,
        runtimeImage=endpoint.runtime_image,
        status=endpoint.status,
        minReplicas=endpoint.min_replicas,
        maxReplicas=endpoint.max_replicas,
        promptPolicyId=endpoint.prompt_policy_id,
        useGpu=endpoint.use_gpu,
        cpuRequest=endpoint.cpu_request,
        cpuLimit=endpoint.cpu_limit,
        memoryRequest=endpoint.memory_request,
        memoryLimit=endpoint.memory_limit,
        autoscalePolicy=endpoint.autoscale_policy,
        deploymentSpec=deployment_spec,
        lastHealthCheck=endpoint.last_health_check,
        rollbackPlan=endpoint.rollback_plan,
        createdAt=endpoint.created_at,
    )


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
        endpoint_responses = [_build_serving_endpoint_response(endpoint, service) for endpoint in endpoints]
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
            model_version=request.version,
            environment=request.environment,
            route=request.route,
            min_replicas=request.minReplicas,
            max_replicas=request.maxReplicas,
            autoscale_policy=request.autoscalePolicy,
            prompt_policy_id=request.promptPolicyId,
            rollback_plan=request.rollbackPlan,
            use_gpu=request.useGpu,
            serving_runtime_image=request.servingRuntimeImage,
            cpu_request=request.cpuRequest,
            cpu_limit=request.cpuLimit,
            memory_request=request.memoryRequest,
            memory_limit=request.memoryLimit,
            deployment_spec=request.deploymentSpec,
        )
        return schemas.EnvelopeServingEndpoint(
            status="success",
            message="Serving endpoint deployed successfully",
            data=_build_serving_endpoint_response(endpoint, service),
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
        data=_build_serving_endpoint_response(endpoint, service),
    )


@router.patch("/endpoints/{endpointId}", response_model=schemas.EnvelopeServingEndpoint)
def patch_endpoint(
    endpointId: str,
    request: schemas.ServingEndpointPatch,
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpoint:
    """Update scaling, prompt routing policy, or status for an endpoint."""
    try:
        endpoint = service.patch_endpoint(
            endpointId,
            autoscale_policy=request.autoscalePolicy,
            prompt_policy_id=request.promptPolicyId,
            status=request.status,
        )
        if not endpoint:
            return schemas.EnvelopeServingEndpoint(
                status="fail",
                message=f"Serving endpoint {endpointId} not found",
                data=None,
            )
        return schemas.EnvelopeServingEndpoint(
            status="success",
            message="Serving endpoint updated successfully",
            data=_build_serving_endpoint_response(endpoint, service),
        )
    except ValueError as e:
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        logger.error(f"Failed to patch endpoint {endpointId}: {e}", exc_info=True)
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=f"Failed to update endpoint: {str(e)}",
            data=None,
        )


@router.post("/endpoints/{endpointId}/refresh-status", response_model=schemas.EnvelopeServingEndpoint)
def refresh_endpoint_status(
    endpointId: str,
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpoint:
    """Force refresh serving endpoint status from Kubernetes."""
    try:
        endpoint = service.refresh_endpoint_status(endpointId)
        if not endpoint:
            return schemas.EnvelopeServingEndpoint(
                status="fail",
                message=f"Serving endpoint {endpointId} not found",
                data=None,
            )
        
        return schemas.EnvelopeServingEndpoint(
            status="success",
            message="Endpoint status refreshed successfully",
            data=_build_serving_endpoint_response(endpoint, service),
        )
    except Exception as e:
        logger.error(f"Failed to refresh endpoint status: {e}", exc_info=True)
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=f"Failed to refresh endpoint status: {str(e)}",
            data=None,
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
            data=_build_serving_endpoint_response(endpoint, service) if endpoint else None,
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
    request: schemas.RedeployEndpointRequest,
    service: ServingService = Depends(get_serving_service),
) -> schemas.EnvelopeServingEndpoint:
    """Redeploy a serving endpoint with the same or updated configuration."""
    logger.info(f"Redeploy request received for endpoint {endpointId}")
    logger.debug(f"Redeploy request body: {request.model_dump() if hasattr(request, 'model_dump') else request}")
    
    try:
        logger.info(f"Calling service.redeploy_endpoint() for endpoint {endpointId}")
        endpoint = service.redeploy_endpoint(
            endpointId,
            use_gpu=request.useGpu,
            serving_runtime_image=request.servingRuntimeImage,
            cpu_request=request.cpuRequest,
            cpu_limit=request.cpuLimit,
            memory_request=request.memoryRequest,
            memory_limit=request.memoryLimit,
            autoscale_policy=request.autoscalePolicy,
            serving_framework=request.servingFramework,
            deployment_spec=request.deploymentSpec,
        )
        result = schemas.EnvelopeServingEndpoint(
            status="success",
            message="Serving endpoint redeployed successfully",
            data=_build_serving_endpoint_response(endpoint, service),
        )
        logger.info(f"Successfully redeployed endpoint {endpointId}")
        return result
    except ValueError as e:
        logger.error(f"Validation error for endpoint {endpointId}: {e}")
        return schemas.EnvelopeServingEndpoint(
            status="fail",
            message=f"Invalid request: {str(e)}",
            data=None,
        )
    except Exception as e:
        logger.error(f"Unexpected error redeploying endpoint {endpointId}: {e}", exc_info=True)
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
            data=_build_serving_endpoint_response(endpoint, service),
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


@router.get("/endpoints/{endpointId}/deployment", response_model=schemas.EnvelopeServingDeployment)
def get_deployment(
    endpointId: str,
    deployment_service: ServingDeploymentService = Depends(get_serving_deployment_service),
) -> schemas.EnvelopeServingDeployment:
    """Get serving deployment details for an endpoint."""
    try:
        deployment = deployment_service.get_deployment(UUID(endpointId))
        if not deployment:
            return schemas.EnvelopeServingDeployment(
                status="fail",
                message=f"Deployment not found for endpoint {endpointId}",
                data=None,
            )
        
        return schemas.EnvelopeServingDeployment(
            status="success",
            message="",
            data=schemas.ServingDeploymentResponse(
                id=str(deployment.id),
                serving_endpoint_id=str(deployment.serving_endpoint_id),
                serving_framework=deployment.serving_framework,
                framework_resource_id=deployment.framework_resource_id,
                framework_namespace=deployment.framework_namespace,
                replica_count=deployment.replica_count,
                min_replicas=deployment.min_replicas,
                max_replicas=deployment.max_replicas,
                autoscaling_metrics=deployment.autoscaling_metrics,
                resource_requests=deployment.resource_requests,
                resource_limits=deployment.resource_limits,
                framework_status=deployment.framework_status,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
            ),
        )
    except ValueError as e:
        return schemas.EnvelopeServingDeployment(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        return schemas.EnvelopeServingDeployment(
            status="fail",
            message=f"Failed to get deployment: {str(e)}",
            data=None,
        )


@router.patch("/endpoints/{endpointId}/deployment", response_model=schemas.EnvelopeServingDeployment)
def update_deployment(
    endpointId: str,
    request: schemas.UpdateDeploymentRequest,
    deployment_service: ServingDeploymentService = Depends(get_serving_deployment_service),
) -> schemas.EnvelopeServingDeployment:
    """Update serving deployment configuration."""
    try:
        deployment = deployment_service.update_deployment(
            endpoint_id=UUID(endpointId),
            min_replicas=request.min_replicas,
            max_replicas=request.max_replicas,
            resource_requests=request.resource_requests,
            resource_limits=request.resource_limits,
        )
        
        return schemas.EnvelopeServingDeployment(
            status="success",
            message="Deployment updated successfully",
            data=schemas.ServingDeploymentResponse(
                id=str(deployment.id),
                serving_endpoint_id=str(deployment.serving_endpoint_id),
                serving_framework=deployment.serving_framework,
                framework_resource_id=deployment.framework_resource_id,
                framework_namespace=deployment.framework_namespace,
                replica_count=deployment.replica_count,
                min_replicas=deployment.min_replicas,
                max_replicas=deployment.max_replicas,
                autoscaling_metrics=deployment.autoscaling_metrics,
                resource_requests=deployment.resource_requests,
                resource_limits=deployment.resource_limits,
                framework_status=deployment.framework_status,
                created_at=deployment.created_at,
                updated_at=deployment.updated_at,
            ),
        )
    except ValueError as e:
        return schemas.EnvelopeServingDeployment(
            status="fail",
            message=str(e),
            data=None,
        )
    except Exception as e:
        return schemas.EnvelopeServingDeployment(
            status="fail",
            message=f"Failed to update deployment: {str(e)}",
            data=None,
        )


@router.get("/frameworks", response_model=schemas.EnvelopeServingFrameworks)
def list_frameworks(
    session: Session = Depends(get_session),
) -> schemas.EnvelopeServingFrameworks:
    """List available serving frameworks and their capabilities."""
    try:
        from core.settings import get_settings
        
        settings = get_settings()
        integration_config = IntegrationConfigService(session)
        supported_frameworks = ServingFrameworkFactory.get_supported_frameworks()
        
        frameworks = []
        for framework_name in supported_frameworks:
            config = integration_config.get_config("serving", framework_name)
            enabled = config.get("enabled", False) if config else False
            
            # For KServe, use settings.use_kserve as the primary source (default framework)
            # If settings.use_kserve is True, KServe is enabled regardless of integration config
            if framework_name == "kserve":
                enabled = settings.use_kserve if settings.use_kserve else enabled
            
            # Map framework names to display names
            display_names = {
                "kserve": "KServe",
                "ray_serve": "Ray Serve",
            }
            
            # Define capabilities per framework
            capabilities_map = {
                "kserve": ["autoscaling", "canary_deployment", "gpu_support", "multi_framework"],
                "ray_serve": ["autoscaling", "gpu_support", "distributed_serving"],
            }
            
            frameworks.append(schemas.ServingFramework(
                name=framework_name,
                display_name=display_names.get(framework_name, framework_name.title()),
                enabled=enabled,
                capabilities=capabilities_map.get(framework_name, []),
            ))
        
        return schemas.EnvelopeServingFrameworks(
            status="success",
            message="",
            data={"frameworks": frameworks},
        )
    except Exception as e:
        return schemas.EnvelopeServingFrameworks(
            status="fail",
            message=f"Failed to list frameworks: {str(e)}",
            data=None,
        )


@router.get("/images", response_model=schemas.EnvelopeImageConfig)
def get_image_config(
    session: Session = Depends(get_session),
) -> schemas.EnvelopeImageConfig:
    """Get container image configuration for training and serving."""
    try:
        from core.image_config import get_image_config
        import logging
        
        logger = logging.getLogger(__name__)
        image_config = get_image_config()
        
        # Build response with all image configurations
        # Use the actual loaded images from image_config
        train_images = {}
        for job_type in image_config.train_images.keys():
            job_config = image_config.train_images[job_type]
            train_images[job_type] = {
                "gpu": job_config.get("gpu", ""),
                "cpu": job_config.get("cpu", ""),
            }
        
        serve_images = {}
        for serve_target in image_config.serve_images.keys():
            serve_config = image_config.serve_images[serve_target]
            serve_images[serve_target] = {
                "gpu": serve_config.get("gpu", ""),
                "cpu": serve_config.get("cpu", ""),
            }
        
        return schemas.EnvelopeImageConfig(
            status="success",
            message="",
            data=schemas.ImageConfigResponse(
                train_images=train_images,
                serve_images=serve_images,
            ),
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to get image configuration: {e}", exc_info=True)
        return schemas.EnvelopeImageConfig(
            status="fail",
            message=f"Failed to get image configuration: {str(e)}",
            data=None,
        )

