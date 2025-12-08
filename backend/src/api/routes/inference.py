"""Inference API routes for serving models."""
from __future__ import annotations

import logging
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from core.database import get_session
from core.settings import get_settings
from serving import schemas
from serving.serving_service import ServingService
from serving.repositories import ServingEndpointRepository
from serving.external_models import get_external_model_client
from catalog import models as catalog_models
from catalog.repositories import ServingDeploymentRepository
from integrations.serving.factory import ServingFrameworkFactory
from services.integration_config import IntegrationConfigService

logger = logging.getLogger(__name__)

# Note: This router handles inference requests at /llm-ops/v1/serve/{route_name}/chat
router = APIRouter(prefix="/llm-ops/v1/serve", tags=["inference"])


@router.get("/health")
async def health_check():
    """Health check endpoint for inference router."""
    return {"status": "ok", "router": "inference"}


def get_serving_service(session: Session = Depends(get_session)) -> ServingService:
    """Dependency to get serving service."""
    return ServingService(session)


def extract_route_name(full_route: str) -> str:
    """Extract route name from full route path.
    
    Examples:
        "/llm-ops/v1/serve/chat-model" -> "chat-model"
        "chat-model" -> "chat-model"
    """
    # Remove prefix if present
    route_name = full_route.replace("/llm-ops/v1/serve/", "").lstrip("/")
    return route_name


def get_endpoint_by_route_name(
    route_name: str,
    session: Session,
) -> tuple[str | None, str | None]:
    """Find endpoint by route name.
    
    Searches across all environments for a healthy endpoint matching the route name.
    
    Returns:
        Tuple of (endpoint_id, full_route) or (None, None) if not found
    """
    repo = ServingEndpointRepository(session)
    
    # Try to find endpoint by matching route name
    # Route format is typically: /llm-ops/v1/serve/{route_name}
    possible_routes = [
        f"/llm-ops/v1/serve/{route_name}",
        f"/serve/{route_name}",
        route_name,
    ]
    
    # Search in all environments, preferring dev, then stg, then prod
    environments = ["dev", "stg", "prod"]
    
    for env in environments:
        for route in possible_routes:
            endpoint = repo.get_by_route(env, route)
            if endpoint and endpoint.status == "healthy":
                return str(endpoint.id), endpoint.route
    
    # If not found by exact route match, try finding by route name in all endpoints
    all_endpoints = repo.list()
    for endpoint in all_endpoints:
        if endpoint.status != "healthy":
            continue
        
        # Extract route name from full route
        endpoint_route_name = extract_route_name(endpoint.route)
        if endpoint_route_name == route_name:
            return str(endpoint.id), endpoint.route
    
    return None, None


@router.post("/{route_name}/chat", response_model=schemas.ChatCompletionResponse)
async def chat_completion(
    route_name: str,
    request: schemas.ChatCompletionRequest,
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_user_roles: str = Header(..., alias="X-User-Roles"),
    session: Session = Depends(get_session),
    service: ServingService = Depends(get_serving_service),
) -> schemas.ChatCompletionResponse:
    """Chat completion endpoint for serving models.
    
    Args:
        route_name: Model route name (e.g., "chat-model")
        request: Chat completion request
        x_user_id: User ID from header
        x_user_roles: User roles from header
        session: Database session
        service: Serving service
    
    Returns:
        Chat completion response
    """
    logger.info(f"Chat completion request for route: {route_name}, user: {x_user_id}")
    try:
        # Find endpoint by route name
        endpoint_id, full_route = get_endpoint_by_route_name(route_name, session)
        logger.info(f"Found endpoint: {endpoint_id} for route_name: {route_name}")
        
        if not endpoint_id:
            return schemas.ChatCompletionResponse(
                status="fail",
                message=f"Endpoint not found for route: {route_name}. Make sure the endpoint is deployed and healthy.",
                data=None,
            )
        
        # Get endpoint details
        endpoint = service.get_endpoint(endpoint_id)
        if not endpoint:
            return schemas.ChatCompletionResponse(
                status="fail",
                message=f"Endpoint {endpoint_id} not found",
                data=None,
            )
        
        if endpoint.status != "healthy":
            return schemas.ChatCompletionResponse(
                status="fail",
                message=f"Endpoint is not healthy (status: {endpoint.status})",
                data=None,
            )
        
        # Get prompt template if available
        request_id = str(uuid4())
        prompt_template = service.get_prompt_for_endpoint(
            endpoint_id=endpoint_id,
            user_id=x_user_id,
            request_id=request_id,
        )
        
        # Apply prompt template if available
        messages = [msg.model_dump() for msg in request.messages]
        if prompt_template and prompt_template.content:
            # Apply template to system message if present
            system_msg_idx = next(
                (i for i, msg in enumerate(messages) if msg["role"] == "system"),
                None
            )
            if system_msg_idx is not None:
                # Apply template to system message
                template_content = prompt_template.content
                # Simple template substitution (could be more sophisticated)
                # If template contains {system_message}, replace it, otherwise prepend
                if "{system_message}" in template_content:
                    messages[system_msg_idx]["content"] = template_content.format(
                        system_message=messages[system_msg_idx]["content"]
                    )
                else:
                    # If no placeholder, use template as is or append
                    messages[system_msg_idx]["content"] = template_content
        
        # Get model entry
        model_entry = session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
        if not model_entry:
            return schemas.ChatCompletionResponse(
                status="fail",
                message=f"Model entry {endpoint.model_entry_id} not found",
                data=None,
            )
        
        # Check if this is an external model
        external_client = get_external_model_client(model_entry)
        
        if external_client:
            # Use external model client
            try:
                result = await external_client.chat_completion(
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                response_content = result["content"]
                usage = result["usage"]
                finish_reason = result.get("finish_reason", "stop")
            except Exception as e:
                logger.error(f"External model inference failed: {e}")
                return schemas.ChatCompletionResponse(
                    status="fail",
                    message=f"External model inference failed: {str(e)}",
                    data=None,
                )
        else:
            # Call internal model inference (KServe or raw deployment)
            try:
                result = await _call_model_inference(
                    endpoint=endpoint,
                    model_entry=model_entry,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    session=session,
                )
                response_content = result["content"]
                usage = result.get("usage", {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                })
                finish_reason = result.get("finish_reason", "stop")
            except Exception as e:
                logger.error(f"Internal model inference failed: {e}", exc_info=True)
                return schemas.ChatCompletionResponse(
                    status="fail",
                    message=f"Model inference failed: {str(e)}",
                    data=None,
                )
        
        return schemas.ChatCompletionResponse(
            status="success",
            message="",
            data=schemas.ChatCompletionData(
                choices=[
                    schemas.ChatCompletionChoice(
                        message=schemas.ChatMessage(
                            role="assistant",
                            content=response_content,
                        ),
                        finish_reason=finish_reason,
                    )
                ],
                usage=schemas.ChatCompletionUsage(
                    prompt_tokens=usage["prompt_tokens"],
                    completion_tokens=usage["completion_tokens"],
                    total_tokens=usage["total_tokens"],
                ),
            ),
        )
        
    except Exception as e:
        logger.error(f"Chat completion error: {e}", exc_info=True)
        return schemas.ChatCompletionResponse(
            status="fail",
            message=f"Failed to process chat completion: {str(e)}",
            data=None,
        )


async def _call_model_inference(
    endpoint,
    model_entry: catalog_models.ModelCatalogEntry,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    session: Session,
) -> dict:
    """Call the actual model for inference via KServe or raw Kubernetes deployment.
    
    Args:
        endpoint: ServingEndpoint entity
        model_entry: ModelCatalogEntry entity
        messages: List of chat messages
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
    
    Returns:
        Dict with 'content', 'usage', and 'finish_reason'
    """
    settings = get_settings()
    endpoint_name = f"serving-{endpoint.id}"
    namespace = f"llm-ops-{endpoint.environment}"

    # If a local override is configured (e.g., port-forwarded service), use that.
    if settings.serving_local_base_url is not None:
        service_name = f"{endpoint_name}-local"
        service_url = str(settings.serving_local_base_url).rstrip("/")
        namespace = "local"
        inference_url = f"{service_url}/v1/chat/completions"
    else:
        # Check if endpoint has a framework deployment
        deployment_repo = ServingDeploymentRepository(session)
        deployment = deployment_repo.get_by_endpoint_id(endpoint.id)
        
        if deployment:
            # Use framework adapter to get inference URL
            try:
                integration_config = IntegrationConfigService(session)
                config = integration_config.get_config("serving", deployment.serving_framework)
                if config and config.get("enabled"):
                    adapter_config = {
                        "namespace": deployment.framework_namespace,
                        "enabled": config["enabled"],
                        **config.get("config", {}),
                    }
                    adapter = ServingFrameworkFactory.create_adapter(deployment.serving_framework, adapter_config)
                    inference_url = adapter.get_inference_url(
                        framework_resource_id=deployment.framework_resource_id,
                        namespace=deployment.framework_namespace,
                    )
                    # Append /v1/chat/completions if not already present
                    if "/v1/chat/completions" not in inference_url:
                        inference_url = f"{inference_url.rstrip('/')}/v1/chat/completions"
                else:
                    # Framework not enabled, fall back to default
                    raise ValueError(f"Framework {deployment.serving_framework} is not enabled")
            except Exception as e:
                logger.warning(f"Failed to get inference URL from framework adapter: {e}, falling back to default")
                # Fall back to default behavior
                if settings.use_kserve:
                    service_name = f"{endpoint_name}-predictor-default"
                    service_url = f"http://{service_name}.{namespace}.svc.cluster.local"
                    inference_url = f"{service_url}/v1/chat/completions"
                else:
                    service_name = f"{endpoint_name}-svc"
                    service_url = f"http://{service_name}.{namespace}.svc.cluster.local:8000"
                    inference_url = f"{service_url}/v1/chat/completions"
        else:
            # No framework deployment, use default behavior
            if settings.use_kserve:
                # KServe InferenceService URL
                # KServe creates a service named: {inference-service-name}-predictor-default
                # For vLLM, we use OpenAI-compatible API at /v1/chat/completions
                service_name = f"{endpoint_name}-predictor-default"
                service_url = f"http://{service_name}.{namespace}.svc.cluster.local"
                inference_url = f"{service_url}/v1/chat/completions"
            else:
                # Raw Kubernetes Deployment URL
                service_name = f"{endpoint_name}-svc"
                service_url = f"http://{service_name}.{namespace}.svc.cluster.local:8000"
                # Assume OpenAI-compatible API (vLLM/TGI)
                inference_url = f"{service_url}/v1/chat/completions"

    logger.info(f"Calling model inference at: {inference_url}")
    
    # Prepare request payload (OpenAI-compatible format)
    payload = {
        "model": model_entry.name,  # Model name for vLLM
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    # Call KServe InferenceService or raw deployment
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                inference_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()
            
            # Parse OpenAI-compatible response
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")
                
                # Extract usage information if available
                usage = data.get("usage", {})
                if not usage:
                    # Estimate if not provided
                    prompt_tokens = sum(len(msg["content"].split()) for msg in messages) * 1.3
                    completion_tokens = len(content.split()) * 1.3
                    usage = {
                        "prompt_tokens": int(prompt_tokens),
                        "completion_tokens": int(completion_tokens),
                        "total_tokens": int(prompt_tokens + completion_tokens),
                    }
                
                return {
                    "content": content,
                    "usage": usage,
                    "finish_reason": finish_reason,
                }
            else:
                raise ValueError(f"Invalid response format from model service: {data}")
                
    except httpx.HTTPStatusError as e:
        error_msg = f"Model service returned error {e.response.status_code}"
        try:
            error_detail = e.response.json()
            error_msg += f": {error_detail}"
        except:
            error_msg += f": {e.response.text}"
        logger.error(f"HTTP error calling model inference: {error_msg}")
        raise ValueError(error_msg) from e
    except httpx.TimeoutException:
        logger.error(f"Timeout calling model inference at {inference_url}")
        raise ValueError("Model inference request timed out") from None
    except httpx.ConnectError as e:
        logger.error(f"Connection error calling model inference: {e}")
        raise ValueError(
            f"Cannot connect to model service at {inference_url}. "
            f"Make sure the endpoint is deployed and healthy. "
            f"Service: {service_name}, Namespace: {namespace}"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error calling model inference: {e}", exc_info=True)
        raise ValueError(f"Model inference failed: {str(e)}") from e

