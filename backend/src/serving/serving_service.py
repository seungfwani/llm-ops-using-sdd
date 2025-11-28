"""Serving endpoint orchestration services."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from serving.repositories import ServingEndpointRepository
from serving.services.deployer import ServingDeployer
from serving.prompt_router import PromptRouter

logger = logging.getLogger(__name__)


class ServingService:
    """Service for managing serving endpoints and prompt operations."""

    def __init__(self, session: Session):
        self.endpoint_repo = ServingEndpointRepository(session)
        self.deployer = ServingDeployer()
        self.prompt_router = PromptRouter(session)
        self.session = session

    def deploy_endpoint(
        self,
        model_entry_id: str,
        environment: str,
        route: str,
        min_replicas: int = 1,
        max_replicas: int = 3,
        autoscale_policy: Optional[dict] = None,
        prompt_policy_id: Optional[str] = None,
    ) -> catalog_models.ServingEndpoint:
        """
        Deploy an approved model to a serving endpoint.

        Args:
            model_entry_id: Catalog model entry ID (must be approved)
            environment: Deployment environment (dev/stg/prod)
            route: Ingress route path (e.g., "/llm-ops/v1/serve/model-name")
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            autoscale_policy: HPA configuration
            prompt_policy_id: Optional prompt template ID

        Returns:
            Created ServingEndpoint entity
        """
        # Validate model exists and is approved
        model_entry = self.session.get(catalog_models.ModelCatalogEntry, model_entry_id)
        if not model_entry:
            raise ValueError(f"Model entry {model_entry_id} not found")
        if model_entry.status != "approved":
            raise ValueError(f"Model entry {model_entry_id} is not approved")

        # Check if route already exists in this environment
        existing = self.endpoint_repo.get_by_route(environment, route)
        if existing:
            raise ValueError(f"Route {route} already exists in {environment}")

        # Create endpoint entity
        endpoint = catalog_models.ServingEndpoint(
            id=uuid4(),
            model_entry_id=model_entry_id,
            environment=environment,
            route=route,
            status="deploying",
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            autoscale_policy=autoscale_policy,
            prompt_policy_id=prompt_policy_id,
        )

        endpoint = self.endpoint_repo.create(endpoint)

        # For external models, skip Kubernetes deployment
        if model_entry.type == "external":
            # External models are accessed via API, no deployment needed
            endpoint.status = "healthy"
            endpoint.rollback_plan = "External model - no Kubernetes deployment"
            endpoint = self.endpoint_repo.update(endpoint)
            logger.info(
                f"Created external model endpoint {endpoint.id} for {model_entry.name} "
                f"at {route} (no Kubernetes deployment needed)"
            )
        else:
            # Deploy to Kubernetes for internal models
            try:
                endpoint_name = f"serving-{endpoint.id}"
                model_image = f"llm-ops/model:{model_entry.name}-{model_entry.version}"
                k8s_uid = self.deployer.deploy_endpoint(
                    endpoint_name=endpoint_name,
                    model_image=model_image,
                    route=route,
                    min_replicas=min_replicas,
                    max_replicas=max_replicas,
                    autoscale_policy=autoscale_policy,
                )
                # Store rollback plan (previous deployment state)
                endpoint.rollback_plan = f"Previous deployment UID: {k8s_uid}"
                endpoint.status = "healthy"
                endpoint = self.endpoint_repo.update(endpoint)
                logger.info(f"Deployed serving endpoint {endpoint.id} to {environment} at {route}")
            except Exception as e:
                logger.error(f"Failed to deploy endpoint {endpoint.id}: {e}")
                endpoint.status = "failed"
                endpoint = self.endpoint_repo.update(endpoint)
                raise

        return endpoint

    def get_endpoint(self, endpoint_id: str) -> Optional[catalog_models.ServingEndpoint]:
        """Retrieve a serving endpoint by ID."""
        return self.endpoint_repo.get(endpoint_id)

    def list_endpoints(
        self,
        environment: Optional[str] = None,
        model_entry_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[catalog_models.ServingEndpoint]:
        """List serving endpoints with optional filters."""
        return list(self.endpoint_repo.list(environment=environment, model_entry_id=model_entry_id, status=status))

    def rollback_endpoint(self, endpoint_id: str) -> bool:
        """Rollback a serving endpoint to the previous version."""
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            return False

        if not endpoint.rollback_plan:
            raise ValueError(f"Endpoint {endpoint_id} has no rollback plan")

        try:
            endpoint_name = f"serving-{endpoint.id}"
            success = self.deployer.rollback_endpoint(endpoint_name)
            if success:
                endpoint.status = "rollback"
                endpoint = self.endpoint_repo.update(endpoint)
                logger.info(f"Rolled back endpoint {endpoint_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to rollback endpoint {endpoint_id}: {e}")
            return False

    def get_prompt_for_endpoint(
        self,
        endpoint_id: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Optional[catalog_models.PromptTemplate]:
        """Get the prompt template for a serving endpoint (with A/B routing)."""
        return self.prompt_router.select_prompt(endpoint_id, user_id, request_id)

