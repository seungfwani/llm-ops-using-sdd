"""Serving endpoint orchestration services."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from core.settings import get_settings
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
        use_gpu: Optional[bool] = None,
        serving_runtime_image: Optional[str] = None,
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
            use_gpu: Whether to request GPU resources. If None, uses settings.use_gpu

        Returns:
            Created ServingEndpoint entity
        """
        settings = get_settings()

        # Normalize route path (remove leading/trailing spaces, ensure absolute path)
        route = route.strip()
        if not route.startswith("/"):
            route = "/" + route
        if route != "/" and route.endswith("/"):
            route = route.rstrip("/")
        
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

        # Determine runtime image for this endpoint (per-endpoint override or global default)
        effective_runtime_image = serving_runtime_image or settings.serving_runtime_image

        # Create endpoint entity
        endpoint = catalog_models.ServingEndpoint(
            id=uuid4(),
            model_entry_id=model_entry_id,
            environment=environment,
            route=route,
            runtime_image=effective_runtime_image,
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
            # Validate that model has storage_uri (model files uploaded)
            if not model_entry.storage_uri:
                raise ValueError(
                    f"Model entry {model_entry_id} does not have storage_uri. "
                    "Please upload model files before deploying to serving."
                )
            
            try:
                endpoint_name = f"serving-{endpoint.id}"
                # Use llm-ops-{environment} as Kubernetes namespace (llm-ops-dev/llm-ops-stg/llm-ops-prod)
                namespace = f"llm-ops-{environment}"
                # Deploy using model storage_uri from catalog (object storage)
                # The serving runtime (vLLM/TGI) will load the model from storage_uri at startup
                k8s_uid = self.deployer.deploy_endpoint(
                    endpoint_name=endpoint_name,
                    model_storage_uri=model_entry.storage_uri,
                    route=route,
                    min_replicas=min_replicas,
                    max_replicas=max_replicas,
                    autoscale_policy=autoscale_policy,
                    namespace=namespace,
                    use_gpu=use_gpu,
                    serving_runtime_image=effective_runtime_image,
                )
                # Store rollback plan (previous deployment state)
                endpoint.rollback_plan = f"Previous deployment UID: {k8s_uid}"
                # Status will be updated based on actual Kubernetes pod status
                # For now, set to deploying since pods may still be starting
                endpoint.status = "deploying"
                endpoint = self.endpoint_repo.update(endpoint)
                logger.info(f"Deployed serving endpoint {endpoint.id} to {environment} at {route} (status: deploying)")
                
                # Try to get actual status from Kubernetes (non-blocking)
                try:
                    k8s_status = self.deployer.get_endpoint_status(endpoint_name, namespace=namespace)
                    if k8s_status:
                        endpoint.status = k8s_status.get("status", "deploying")
                        endpoint = self.endpoint_repo.update(endpoint)
                        logger.info(f"Updated endpoint {endpoint.id} status to {endpoint.status} based on Kubernetes status")
                except Exception as e:
                    logger.warning(f"Could not fetch Kubernetes status for {endpoint.id}: {e}, keeping status as deploying")
            except Exception as e:
                logger.error(f"Failed to deploy endpoint {endpoint.id}: {e}")
                endpoint.status = "failed"
                endpoint = self.endpoint_repo.update(endpoint)
                raise

        return endpoint

    def get_endpoint(self, endpoint_id: str) -> Optional[catalog_models.ServingEndpoint]:
        """Retrieve a serving endpoint by ID and sync status from Kubernetes."""
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            return None
        
        # For internal models, sync status from Kubernetes
        if endpoint.model_entry_id:
            model_entry = self.session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
            if model_entry and model_entry.type != "external":
                try:
                    endpoint_name = f"serving-{endpoint.id}"
                    namespace = f"llm-ops-{endpoint.environment}"
                    k8s_status = self.deployer.get_endpoint_status(endpoint_name, namespace=namespace)
                    
                    if k8s_status:
                        new_status = k8s_status.get("status", endpoint.status)
                        # Only update if status changed to avoid unnecessary DB writes
                        if new_status != endpoint.status:
                            endpoint.status = new_status
                            endpoint = self.endpoint_repo.update(endpoint)
                            logger.debug(f"Synced endpoint {endpoint_id} status from {endpoint.status} to {new_status}")
                    else:
                        # Kubernetes resource not found, mark as failed
                        if endpoint.status != "failed":
                            endpoint.status = "failed"
                            endpoint = self.endpoint_repo.update(endpoint)
                            logger.warning(f"Endpoint {endpoint_id} Kubernetes resource not found, marked as failed")
                except Exception as e:
                    logger.warning(f"Failed to sync Kubernetes status for endpoint {endpoint_id}: {e}")
                    # Don't fail the request, just return current status
        
        return endpoint

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
            # Use llm-ops-{environment} as Kubernetes namespace
            namespace = f"llm-ops-{endpoint.environment}"
            success = self.deployer.rollback_endpoint(endpoint_name, namespace=namespace)
            if success:
                endpoint.status = "rollback"
                endpoint = self.endpoint_repo.update(endpoint)
                logger.info(f"Rolled back endpoint {endpoint_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to rollback endpoint {endpoint_id}: {e}")
            return False

    def redeploy_endpoint(
        self,
        endpoint_id: str,
        use_gpu: Optional[bool] = None,
        serving_runtime_image: Optional[str] = None,
    ) -> catalog_models.ServingEndpoint:
        """Redeploy an existing serving endpoint with the same configuration."""
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")

        # Get model entry
        model_entry = self.session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
        if not model_entry:
            raise ValueError(f"Model entry {endpoint.model_entry_id} not found")
        
        if model_entry.status != "approved":
            raise ValueError(f"Model entry {endpoint.model_entry_id} is not approved")

        # For external models, no redeployment needed
        if model_entry.type == "external":
            endpoint.status = "healthy"
            endpoint = self.endpoint_repo.update(endpoint)
            logger.info(f"Redeployed external model endpoint {endpoint_id} (no Kubernetes deployment needed)")
            return endpoint

        # For internal models, delete existing Kubernetes resources and redeploy
        endpoint_name = f"serving-{endpoint.id}"
        namespace = f"llm-ops-{endpoint.environment}"
        settings = get_settings()
        
        try:
            # Delete existing Kubernetes resources
            try:
                self.deployer.delete_endpoint(endpoint_name, namespace=namespace)
                logger.info(f"Deleted existing Kubernetes resources for endpoint {endpoint_id}")
            except Exception as e:
                logger.warning(f"Failed to delete existing Kubernetes resources for {endpoint_id}: {e}, continuing with redeployment")

            # Validate that model has storage_uri
            if not model_entry.storage_uri:
                raise ValueError(
                    f"Model entry {endpoint.model_entry_id} does not have storage_uri. "
                    "Please upload model files before redeploying."
                )

            # Determine runtime image: explicit override -> existing endpoint value -> global setting
            effective_runtime_image = (
                serving_runtime_image
                or endpoint.runtime_image
                or settings.serving_runtime_image
            )

            # Persist chosen runtime image on endpoint
            endpoint.runtime_image = effective_runtime_image

            # Redeploy with same configuration (or new image if provided)
            k8s_uid = self.deployer.deploy_endpoint(
                endpoint_name=endpoint_name,
                model_storage_uri=model_entry.storage_uri,
                route=endpoint.route,
                min_replicas=endpoint.min_replicas,
                max_replicas=endpoint.max_replicas,
                autoscale_policy=endpoint.autoscale_policy,
                namespace=namespace,
                use_gpu=use_gpu,
                serving_runtime_image=effective_runtime_image,
            )
            
            # Update endpoint status
            endpoint.rollback_plan = f"Previous deployment UID: {k8s_uid}"
            endpoint.status = "deploying"
            endpoint = self.endpoint_repo.update(endpoint)
            logger.info(f"Redeployed serving endpoint {endpoint_id} to {endpoint.environment} at {endpoint.route} (status: deploying)")
            
            # Try to get actual status from Kubernetes (non-blocking)
            try:
                k8s_status = self.deployer.get_endpoint_status(endpoint_name, namespace=namespace)
                if k8s_status:
                    endpoint.status = k8s_status.get("status", "deploying")
                    endpoint = self.endpoint_repo.update(endpoint)
                    logger.info(f"Updated endpoint {endpoint_id} status to {endpoint.status} based on Kubernetes status")
            except Exception as e:
                logger.warning(f"Could not fetch Kubernetes status for {endpoint_id}: {e}, keeping status as deploying")
            
            return endpoint
        except Exception as e:
            logger.error(f"Failed to redeploy endpoint {endpoint_id}: {e}")
            endpoint.status = "failed"
            endpoint = self.endpoint_repo.update(endpoint)
            raise

    def delete_endpoint(self, endpoint_id: str) -> bool:
        """Delete a serving endpoint and its Kubernetes resources."""
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")

        try:
            # For internal models, delete Kubernetes resources
            if endpoint.model_entry_id:
                model_entry = self.session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
                if model_entry and model_entry.type != "external":
                    endpoint_name = f"serving-{endpoint.id}"
                    namespace = f"llm-ops-{endpoint.environment}"
                    success = self.deployer.delete_endpoint(endpoint_name, namespace=namespace)
                    if not success:
                        logger.warning(f"Failed to delete Kubernetes resources for {endpoint_id}, but continuing with database deletion")
            
            # Delete from database
            self.endpoint_repo.delete(endpoint)
            logger.info(f"Deleted serving endpoint {endpoint_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete endpoint {endpoint_id}: {e}")
            raise

    def get_prompt_for_endpoint(
        self,
        endpoint_id: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Optional[catalog_models.PromptTemplate]:
        """Get the prompt template for a serving endpoint (with A/B routing)."""
        return self.prompt_router.select_prompt(endpoint_id, user_id, request_id)

