from __future__ import annotations

import logging
from typing import Sequence

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from core.settings import get_settings

logger = logging.getLogger(__name__)


class PolicyEngine:
    """Placeholder policy evaluation. Real implementation will query governance tables."""

    def __init__(self):
        self.settings = get_settings()

    def is_allowed(self, actor_id: str, roles: Sequence[str], method: str, path: str) -> bool:
        if self.settings.default_required_role not in roles:
            return False
        # additional policy checks will be added when governance service is available
        return True


class RBACMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, policy_engine: PolicyEngine | None = None):
        super().__init__(app)
        self.policy_engine = policy_engine or PolicyEngine()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Apply RBAC only to API endpoints (/llm-ops/v1/*)
        # Skip all non-API paths (frontend, static files, docs, health, etc.)
        if not request.url.path.startswith("/llm-ops/v1"):
            return await call_next(request)

        # For API endpoints, check if it's a documentation or health endpoint to skip
        skip_api_paths = [
            "/llm-ops/v1/docs",
            "/llm-ops/v1/openapi.json",
            "/llm-ops/v1/redoc",
        ]
        if request.url.path in skip_api_paths or request.url.path.startswith("/llm-ops/v1/health"):
            return await call_next(request)
        
        actor_id = request.headers.get("X-User-Id")
        role_header = request.headers.get("X-User-Roles", "")
        roles = [role.strip() for role in role_header.split(",") if role.strip()]

        if not actor_id or not roles:
            raise HTTPException(status_code=401, detail="Missing identity headers")

        request.state.actor_id = actor_id
        request.state.roles = roles

        if not self.policy_engine.is_allowed(actor_id, roles, request.method, request.url.path):
            raise HTTPException(status_code=403, detail="Access denied by policy")

        return await call_next(request)

