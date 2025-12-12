"""Inference API routes for serving models."""
from __future__ import annotations

import logging
from uuid import UUID, uuid4

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


def _get_endpoint_k8s_name(endpoint_id: str | UUID) -> str:
    """
    Generate short Kubernetes resource name from endpoint ID.
    
    KServe creates hostname: {name}-predictor-{namespace}
    Kubernetes DNS label limit: 63 characters
    Example: svc-2d4abaa49c00-predictor-llm-ops-dev = 43 chars (fits in 63)
    
    Args:
        endpoint_id: Endpoint UUID
        
    Returns:
        - If SERVING_INFERENCE_HOST_OVERRIDE is set, return that base host/IP
          (e.g., http://10.0.0.5:8000) for direct access.
        - Otherwise, short name like "svc-{first12chars}" (max 16 chars)
    """
    settings = get_settings()
    
    # If an override is provided (e.g., direct IP to node/service), use it
    # so that subsequent URL building can skip cluster DNS hostnames.
    if settings.serving_inference_host_override:
        return str(settings.serving_inference_host_override).rstrip("/")
    
    endpoint_id_str = str(endpoint_id).replace("-", "")
    short_id = endpoint_id_str[:12]  # Use first 12 chars of UUID (without hyphens)
    return f"svc-{short_id}"


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
        logger.info(f"Found endpoint: {endpoint_id} for route_name: {route_name}, full_route: {full_route}")
        
        if not endpoint_id:
            # Debug: Log available endpoints for troubleshooting
            repo = ServingEndpointRepository(session)
            all_endpoints = repo.list()
            available_routes = [f"{ep.environment}:{ep.route} (status: {ep.status})" for ep in all_endpoints]
            logger.warning(f"Endpoint not found for route: {route_name}. Available endpoints: {available_routes}")

            # Provide helpful error message with available options
            available_healthy = [f"{ep.environment}:{extract_route_name(ep.route)}" for ep in all_endpoints if ep.status == "healthy"]
            if available_healthy:
                available_msg = f"Available healthy endpoints: {', '.join(available_healthy)}"
            else:
                available_msg = "No healthy endpoints found. Please deploy a model first."

            return schemas.ChatCompletionResponse(
                status="fail",
                message=f"Endpoint not found for route: {route_name}. {available_msg}",
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
                    template=request.template,
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
    template: str | None,
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
    endpoint_name_or_host = _get_endpoint_k8s_name(endpoint.id)
    namespace = f"llm-ops-{endpoint.environment}"
    service_name = None  # Set per-branch for accurate logging

    # If a local override is configured (e.g., port-forwarded service), use that.
    if settings.serving_local_base_url is not None:
        service_name = f"{endpoint_name_or_host}-local"
        service_url = str(settings.serving_local_base_url).rstrip("/")
        namespace = "local"
        inference_url = f"{service_url}/v1/chat/completions"
    # If DNS is unreachable (e.g., external node), allow direct host/IP override.
    elif settings.serving_inference_host_override is not None:
        service_name = str(endpoint_name_or_host)
        service_url = str(endpoint_name_or_host).rstrip("/")
        inference_url = f"{service_url}/v1/chat/completions"
    else:
        endpoint_name = endpoint_name_or_host
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

    # Ensure service_name is populated for logging paths (e.g., override branches)
    if service_name is None:
        service_name = str(endpoint_name_or_host)

    logger.info(f"Calling model inference at: {inference_url} (service: {service_name}, namespace: {namespace})")
    
    # Prepare request payload (OpenAI-compatible chat completions schema)
    payload = {
        "model": model_entry.name,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if template:
        # Optional custom field for runtimes that support template name
        payload["template"] = template
    
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
        status_code = e.response.status_code
        base_msg = f"Model service returned error {status_code}"
        error_msg = base_msg
        # 4xx 에러일 경우, 모델 서버가 내려준 human-friendly 메시지를 최대한 그대로 노출
        try:
            error_detail = e.response.json()
            # OpenAI 호환 런타임에서 {'error': '...', 'error_type': '...'} 형태로 내려오는 경우 처리
            if isinstance(error_detail, dict) and "error" in error_detail:
                detail_error = error_detail.get("error")
                detail_type = error_detail.get("error_type")
                if detail_type:
                    error_msg = f"{detail_type}: {detail_error}"
                else:
                    error_msg = str(detail_error)
            else:
                error_msg = f"{base_msg}: {error_detail}"
        except Exception:
            # JSON 파싱이 안 되면 원문 텍스트를 그대로 사용
            error_msg = f"{base_msg}: {e.response.text}"
        logger.error(f"HTTP error calling model inference: {error_msg}")
        raise ValueError(error_msg) from e
    except httpx.TimeoutException:
        logger.error(f"Timeout calling model inference at {inference_url}")
        raise ValueError("Model inference request timed out") from None
    except httpx.ConnectError as e:
        logger.error(f"Connection error calling model inference: {e}")
        error_msg = (
            f"Cannot connect to model service at {inference_url}. "
            f"Make sure the endpoint is deployed and healthy. "
            f"Service: {service_name}, Namespace: {namespace}"
        )

        # Add troubleshooting suggestions
        if settings.use_kserve:
            error_msg += (
                ". For KServe deployments, ensure InferenceService is created and "
                "predictor pod is running. Check: kubectl get inferenceservice -n {namespace}"
            )
        else:
            error_msg += (
                ". For raw Kubernetes deployments, ensure deployment and service exist. "
                "Check: kubectl get deployments,svc -n {namespace}"
            )

        # Suggest local development override if available
        if not settings.serving_inference_host_override:
            error_msg += (
                ". For local development, set SERVING_INFERENCE_HOST_OVERRIDE "
                "to your local model service URL."
            )

        raise ValueError(error_msg) from e
    except Exception as e:
        logger.error(f"Unexpected error calling model inference: {e}", exc_info=True)
        raise ValueError(f"Model inference failed: {str(e)}") from e

