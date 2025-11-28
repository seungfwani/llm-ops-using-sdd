"""Inference API routes for serving models."""
from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from core.database import get_session
from serving import schemas
from serving.serving_service import ServingService
from serving.repositories import ServingEndpointRepository
from serving.external_models import get_external_model_client
from catalog import models as catalog_models

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
            # Call internal model inference
            response_content = await _call_model_inference(
                endpoint=endpoint,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            # Estimate token usage (simplified)
            prompt_tokens = sum(len(msg["content"].split()) for msg in messages) * 1.3
            completion_tokens = len(response_content.split()) * 1.3
            usage = {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens + completion_tokens),
            }
            finish_reason = "stop"
        
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
    messages: list[dict],
    temperature: float,
    max_tokens: int,
) -> str:
    """Call the actual model for inference.
    
    This is a placeholder implementation. In a real system, this would:
    1. Call the deployed model service (Kubernetes service)
    2. Use an inference client (e.g., OpenAI, vLLM, TensorRT-LLM)
    3. Handle errors and retries
    
    For now, this returns a mock response.
    """
    # TODO: Implement actual model inference
    # Example approaches:
    # 1. HTTP call to Kubernetes service
    # 2. gRPC call to model server
    # 3. Use model inference library
    
    # Mock response for demonstration
    user_message = next(
        (msg["content"] for msg in reversed(messages) if msg["role"] == "user"),
        "Hello"
    )
    
    # Simple echo response with some variation
    mock_responses = [
        f"I understand you said: {user_message}. This is a mock response from the LLM Ops platform. "
        f"The endpoint is configured but actual model inference is not yet implemented.",
        f"Thank you for your message. I'm processing: '{user_message}'. "
        f"In a production system, this would be sent to the actual model for inference.",
        f"Received your message: {user_message}. The serving endpoint is working correctly. "
        f"Model inference will be implemented to connect to the deployed model service.",
    ]
    
    import random
    response = random.choice(mock_responses)
    
    # Truncate to max_tokens if needed
    words = response.split()
    if len(words) > max_tokens // 2:  # Rough word-to-token estimate
        response = " ".join(words[:max_tokens // 2]) + "..."
    
    return response

