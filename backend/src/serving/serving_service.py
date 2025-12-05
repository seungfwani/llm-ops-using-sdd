"""Serving endpoint orchestration services."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from core.image_config import get_image_config
from core.settings import get_settings
from serving.converters.kserve_converter import KServeConverter
from serving.converters.ray_serve_converter import RayServeConverter
from serving.repositories import ServingEndpointRepository
from serving.schemas import DeploymentSpec
from serving.services.deployer import ServingDeployer
from serving.validators.deployment_spec_validator import DeploymentSpecValidator
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
        cpu_request: Optional[str] = None,
        cpu_limit: Optional[str] = None,
        memory_request: Optional[str] = None,
        memory_limit: Optional[str] = None,
        deployment_spec: Optional[DeploymentSpec] = None,
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
            serving_runtime_image: Container image for serving runtime
            cpu_request: CPU request (e.g., '2', '1000m'). If None, uses default from settings
            cpu_limit: CPU limit (e.g., '4', '2000m'). If None, uses default from settings
            memory_request: Memory request (e.g., '4Gi', '2G'). If None, uses default from settings
            memory_limit: Memory limit (e.g., '8Gi', '4G'). If None, uses default from settings

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
        
        # If DeploymentSpec is provided, validate it and use it for configuration
        image_config = get_image_config()
        effective_runtime_image = serving_runtime_image or settings.serving_runtime_image
        effective_use_gpu = use_gpu if use_gpu is not None else settings.use_gpu
        
        if deployment_spec:
            # Validate DeploymentSpec
            training_model_family = None
            model_max_seq_len = None
            if model_entry.model_metadata:
                training_model_family = model_entry.model_metadata.get("model_family")
                model_max_seq_len = model_entry.model_metadata.get("max_position_embeddings")
            
            DeploymentSpecValidator.validate(
                deployment_spec,
                training_model_family,
                model_max_seq_len
            )
            
            # Select container image based on serve_target type and GPU availability
            effective_runtime_image = image_config.get_serve_image_with_fallback(
                deployment_spec.serve_target,
                deployment_spec.use_gpu
            )
            effective_use_gpu = deployment_spec.use_gpu
            
            logger.info(
                f"Using container image {effective_runtime_image} for serve_target {deployment_spec.serve_target} "
                f"(use_gpu={deployment_spec.use_gpu})"
            )
        
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
            use_gpu=effective_use_gpu,
            cpu_request=cpu_request,
            cpu_limit=cpu_limit,
            memory_request=memory_request,
            memory_limit=memory_limit,
        )

        # Store DeploymentSpec if provided
        if deployment_spec:
            endpoint.deployment_spec = deployment_spec.model_dump()

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
                    cpu_request=cpu_request,
                    cpu_limit=cpu_limit,
                    memory_request=memory_request,
                    memory_limit=memory_limit,
                    model_metadata=model_entry.model_metadata,
                    deployment_spec=deployment_spec,
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
                        # Map adapter status to valid DB status values
                        adapter_status = k8s_status.get("status", "deploying")
                        # Ensure status is one of: deploying, healthy, degraded, failed
                        if adapter_status not in ("deploying", "healthy", "degraded", "failed"):
                            logger.warning(f"Invalid adapter status '{adapter_status}', defaulting to 'deploying'")
                            adapter_status = "deploying"
                        endpoint.status = adapter_status
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
                        # Map adapter status to valid DB status values
                        adapter_status = k8s_status.get("status", endpoint.status)
                        # Ensure status is one of: deploying, healthy, degraded, failed
                        if adapter_status not in ("deploying", "healthy", "degraded", "failed"):
                            logger.warning(f"Invalid adapter status '{adapter_status}', defaulting to current status")
                            adapter_status = endpoint.status
                        # Only update if status changed to avoid unnecessary DB writes
                        if adapter_status != endpoint.status:
                            endpoint.status = adapter_status
                            endpoint = self.endpoint_repo.update(endpoint)
                            logger.debug(f"Synced endpoint {endpoint_id} status from {endpoint.status} to {adapter_status}")
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
        cpu_request: Optional[str] = None,
        cpu_limit: Optional[str] = None,
        memory_request: Optional[str] = None,
        memory_limit: Optional[str] = None,
        deployment_spec: Optional[DeploymentSpec] = None,
    ) -> catalog_models.ServingEndpoint:
        """Redeploy an existing serving endpoint with the same or updated configuration."""
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
        image_config = get_image_config()
        
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

            # Determine deployment_spec: new spec -> existing endpoint deployment_spec -> reconstruct from metadata
            effective_deployment_spec = deployment_spec
            if not effective_deployment_spec:
                # Try to get existing deployment_spec from endpoint
                if hasattr(endpoint, 'deployment_spec') and endpoint.deployment_spec:
                    try:
                        effective_deployment_spec = DeploymentSpec(**endpoint.deployment_spec)
                        logger.info(f"Using existing deployment_spec from endpoint {endpoint_id}")
                    except Exception as e:
                        logger.warning(f"Failed to parse existing deployment_spec for endpoint {endpoint_id}: {e}, will reconstruct from metadata")
                        effective_deployment_spec = None
                
                # If still no deployment_spec, try to reconstruct from model metadata
                if not effective_deployment_spec and model_entry.model_metadata:
                    model_family = model_entry.model_metadata.get("model_family")
                    job_type = model_entry.model_metadata.get("job_type")
                    if model_family and job_type:
                        # Reconstruct basic DeploymentSpec from metadata
                        # Determine serve_target based on job_type
                        if job_type == "RAG_TUNING":
                            serve_target = "RAG"
                        else:
                            serve_target = "GENERATION"
                        
                        # Determine use_gpu from endpoint or parameter
                        effective_use_gpu = (
                            use_gpu
                            if use_gpu is not None
                            else endpoint.use_gpu
                            if endpoint.use_gpu is not None
                            else settings.use_gpu
                        )
                        
                        # Reconstruct resources
                        gpus = 1 if effective_use_gpu else 0
                        
                        effective_deployment_spec = DeploymentSpec(
                            model_ref=f"{model_entry.name}-{model_entry.version}",
                            model_family=model_family,
                            job_type=job_type,
                            serve_target=serve_target,
                            resources={"gpus": gpus, "gpu_memory_gb": 80 if effective_use_gpu else None},
                            runtime={
                                "max_concurrent_requests": 256,
                                "max_input_tokens": model_entry.model_metadata.get("max_position_embeddings", 4096),
                                "max_output_tokens": 1024,
                            },
                            use_gpu=effective_use_gpu,
                        )
                        logger.info(f"Reconstructed deployment_spec from model metadata for endpoint {endpoint_id}")

            # If deployment_spec is provided, use it to determine runtime image and use_gpu
            if effective_deployment_spec:
                # Validate DeploymentSpec
                training_model_family = None
                model_max_seq_len = None
                if model_entry.model_metadata:
                    training_model_family = model_entry.model_metadata.get("model_family")
                    model_max_seq_len = model_entry.model_metadata.get("max_position_embeddings")
                
                DeploymentSpecValidator.validate(
                    effective_deployment_spec,
                    training_model_family,
                    model_max_seq_len
                )
                
                # Select container image based on serve_target type and GPU availability
                effective_runtime_image = image_config.get_serve_image_with_fallback(
                    effective_deployment_spec.serve_target,
                    effective_deployment_spec.use_gpu
                )
                effective_use_gpu = effective_deployment_spec.use_gpu
                
                logger.info(
                    f"Using container image {effective_runtime_image} for serve_target {effective_deployment_spec.serve_target} "
                    f"(use_gpu={effective_deployment_spec.use_gpu})"
                )
            else:
                # Fallback to legacy logic if no deployment_spec
                # Determine runtime image: explicit override -> existing endpoint value -> global setting
                effective_runtime_image = (
                    serving_runtime_image
                    or endpoint.runtime_image
                    or settings.serving_runtime_image
                )

                # Determine use_gpu: explicit override -> existing endpoint value -> global setting
                effective_use_gpu = (
                    use_gpu
                    if use_gpu is not None
                    else endpoint.use_gpu
                    if endpoint.use_gpu is not None
                    else settings.use_gpu
                )

            # Determine resource settings: explicit override -> existing endpoint value -> None (will use settings defaults in deployer)
            effective_cpu_request = cpu_request or endpoint.cpu_request
            effective_cpu_limit = cpu_limit or endpoint.cpu_limit
            effective_memory_request = memory_request or endpoint.memory_request
            effective_memory_limit = memory_limit or endpoint.memory_limit

            # Persist chosen settings on endpoint
            endpoint.runtime_image = effective_runtime_image
            endpoint.use_gpu = effective_use_gpu
            endpoint.cpu_request = effective_cpu_request
            endpoint.cpu_limit = effective_cpu_limit
            endpoint.memory_request = effective_memory_request
            endpoint.memory_limit = effective_memory_limit
            
            # Store DeploymentSpec if provided or reconstructed
            if effective_deployment_spec:
                endpoint.deployment_spec = effective_deployment_spec.model_dump()

            # Redeploy with same configuration (or new image/resources/deployment_spec if provided)
            k8s_uid = self.deployer.deploy_endpoint(
                endpoint_name=endpoint_name,
                model_storage_uri=model_entry.storage_uri,
                route=endpoint.route,
                min_replicas=endpoint.min_replicas,
                max_replicas=endpoint.max_replicas,
                autoscale_policy=endpoint.autoscale_policy,
                namespace=namespace,
                use_gpu=effective_use_gpu,
                serving_runtime_image=effective_runtime_image,
                cpu_request=effective_cpu_request,
                cpu_limit=effective_cpu_limit,
                memory_request=effective_memory_request,
                memory_limit=effective_memory_limit,
                model_metadata=model_entry.model_metadata,
                deployment_spec=effective_deployment_spec,
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
                    # Map adapter status to valid DB status values
                    adapter_status = k8s_status.get("status", "deploying")
                    # Ensure status is one of: deploying, healthy, degraded, failed
                    if adapter_status not in ("deploying", "healthy", "degraded", "failed"):
                        logger.warning(f"Invalid adapter status '{adapter_status}', defaulting to 'deploying'")
                        adapter_status = "deploying"
                    endpoint.status = adapter_status
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

