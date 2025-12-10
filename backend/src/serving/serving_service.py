"""Serving endpoint orchestration services."""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Optional
from uuid import uuid4

from kubernetes.client.rest import ApiException
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


def _get_endpoint_k8s_name(endpoint_id: str | UUID) -> str:
    """
    Generate short Kubernetes resource name from endpoint ID.
    
    KServe creates hostname: {name}-predictor-{namespace}
    Kubernetes DNS label limit: 63 characters
    Example: svc-2d4abaa49c00-predictor-llm-ops-dev = 43 chars (fits in 63)
    
    Args:
        endpoint_id: Endpoint UUID
        
    Returns:
        Short name like "svc-{first12chars}" (max 16 chars)
    """
    endpoint_id_str = str(endpoint_id).replace("-", "")
    short_id = endpoint_id_str[:12]  # Use first 12 chars of UUID (without hyphens)
    return f"svc-{short_id}"


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
        rollback_plan: Optional[str] = None,
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
        # Always use the catalog entry's version as the effective model version.
        effective_model_version = model_entry.version

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
            # If deployment_spec.use_gpu is None, fall back to effective_use_gpu (which may be from parameter or settings)
            deployment_use_gpu = (
                deployment_spec.use_gpu 
                if deployment_spec.use_gpu is not None 
                else effective_use_gpu
            )
            effective_runtime_image = image_config.get_serve_image_with_fallback(
                deployment_spec.serve_target,
                deployment_use_gpu
            )
            effective_use_gpu = deployment_use_gpu
            
            logger.info(
                f"Using container image {effective_runtime_image} for serve_target {deployment_spec.serve_target} "
                f"(use_gpu={deployment_spec.use_gpu})"
            )
        else:
            # If no deployment_spec, try to determine image from model metadata or use default
            # But still respect the use_gpu setting
            if not serving_runtime_image and model_entry.model_metadata:
                # Try to determine serve_target from model metadata
                serve_target = model_entry.model_metadata.get("serve_target", "GENERATION")
                if serve_target not in ("GENERATION", "RAG"):
                    serve_target = "GENERATION"
                
                try:
                    effective_runtime_image = image_config.get_serve_image_with_fallback(
                        serve_target,
                        effective_use_gpu
                    )
                    logger.info(
                        f"Using container image {effective_runtime_image} for serve_target {serve_target} "
                        f"(use_gpu={effective_use_gpu})"
                    )
                except ValueError:
                    # If serve_target is invalid, fall back to settings default
                    logger.warning(f"Invalid serve_target {serve_target}, using default image from settings")
                    effective_runtime_image = settings.serving_runtime_image
        
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
        # Store initial rollback plan if provided; will be updated after deployment
        if rollback_plan:
            endpoint.rollback_plan = rollback_plan

        # Store DeploymentSpec if provided
        if deployment_spec:
            endpoint.deployment_spec = deployment_spec.model_dump()
            logger.info(
                f"Storing DeploymentSpec for endpoint: model_family={deployment_spec.model_family}, "
                f"job_type={deployment_spec.job_type}, model_ref={deployment_spec.model_ref}"
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
                endpoint_name = _get_endpoint_k8s_name(endpoint.id)
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
                    use_gpu=effective_use_gpu,
                    serving_runtime_image=effective_runtime_image,
                    cpu_request=cpu_request,
                    cpu_limit=cpu_limit,
                    memory_request=memory_request,
                    memory_limit=memory_limit,
                    model_metadata=model_entry.model_metadata,
                    deployment_spec=deployment_spec,
                )
                # Store rollback plan (previous deployment state)
                endpoint.rollback_plan = rollback_plan or f"Previous deployment UID: {k8s_uid}"
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
                    endpoint_name = _get_endpoint_k8s_name(endpoint.id)
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
                            old_status = endpoint.status
                            endpoint.status = adapter_status
                            endpoint = self.endpoint_repo.update(endpoint)
                            logger.info(
                                f"Synced endpoint {endpoint_id} status from '{old_status}' to '{adapter_status}' "
                                f"(K8s: {k8s_status.get('ready_replicas', 0)}/{k8s_status.get('replicas', 0)} ready)"
                            )
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
        """List serving endpoints with optional filters and sync status from Kubernetes."""
        endpoints = list(self.endpoint_repo.list(environment=environment, model_entry_id=model_entry_id, status=status))
        
        # Sync status from Kubernetes for all internal model endpoints
        for endpoint in endpoints:
            if endpoint.model_entry_id:
                model_entry = self.session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
                if model_entry and model_entry.type != "external":
                    try:
                        endpoint_name = _get_endpoint_k8s_name(endpoint.id)
                        namespace = f"llm-ops-{endpoint.environment}"
                        k8s_status = self.deployer.get_endpoint_status(endpoint_name, namespace=namespace)
                        
                        if k8s_status:
                            # Map adapter status to valid DB status values
                            adapter_status = k8s_status.get("status", endpoint.status)
                            # Ensure status is one of: deploying, healthy, degraded, failed
                            if adapter_status not in ("deploying", "healthy", "degraded", "failed"):
                                logger.warning(f"Invalid adapter status '{adapter_status}' for endpoint {endpoint.id}, keeping current status")
                                continue
                            # Only update if status changed to avoid unnecessary DB writes
                            if adapter_status != endpoint.status:
                                old_status = endpoint.status
                                endpoint.status = adapter_status
                                endpoint = self.endpoint_repo.update(endpoint)
                                logger.info(
                                    f"Synced endpoint {endpoint.id} status from '{old_status}' to '{adapter_status}' "
                                    f"in list_endpoints (K8s: {k8s_status.get('ready_replicas', 0)}/{k8s_status.get('replicas', 0)} ready)"
                                )
                        else:
                            # Kubernetes resource not found, mark as failed
                            if endpoint.status != "failed":
                                endpoint.status = "failed"
                                endpoint = self.endpoint_repo.update(endpoint)
                                logger.warning(f"Endpoint {endpoint.id} Kubernetes resource not found, marked as failed")
                    except Exception as e:
                        logger.warning(f"Failed to sync Kubernetes status for endpoint {endpoint.id} in list_endpoints: {e}")
                        # Don't fail the request, just continue with current status
        
        return endpoints

    def refresh_endpoint_status(self, endpoint_id: str) -> Optional[catalog_models.ServingEndpoint]:
        """Force refresh endpoint status from Kubernetes."""
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            return None
        
        # For internal models, sync status from Kubernetes
        if endpoint.model_entry_id:
            model_entry = self.session.get(catalog_models.ModelCatalogEntry, endpoint.model_entry_id)
            if model_entry and model_entry.type != "external":
                try:
                    endpoint_name = _get_endpoint_k8s_name(endpoint.id)
                    namespace = f"llm-ops-{endpoint.environment}"
                    k8s_status = self.deployer.get_endpoint_status(endpoint_name, namespace=namespace)
                    
                    if k8s_status:
                        # Map adapter status to valid DB status values
                        adapter_status = k8s_status.get("status", endpoint.status)
                        # Ensure status is one of: deploying, healthy, degraded, failed
                        if adapter_status not in ("deploying", "healthy", "degraded", "failed"):
                            logger.warning(f"Invalid adapter status '{adapter_status}' for endpoint {endpoint_id}, keeping current status")
                            return endpoint
                        # Always update status (force refresh)
                        endpoint.status = adapter_status
                        endpoint = self.endpoint_repo.update(endpoint)
                        logger.info(f"Refreshed endpoint {endpoint_id} status to {adapter_status}")
                    else:
                        # Kubernetes resource not found, mark as failed
                        endpoint.status = "failed"
                        endpoint = self.endpoint_repo.update(endpoint)
                        logger.warning(f"Endpoint {endpoint_id} Kubernetes resource not found, marked as failed")
                except Exception as e:
                    logger.error(f"Failed to refresh Kubernetes status for endpoint {endpoint_id}: {e}", exc_info=True)
                    # Don't fail, just return current endpoint
        
        return endpoint

    def patch_endpoint(
        self,
        endpoint_id: str,
        autoscale_policy: Optional[dict] = None,
        prompt_policy_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Optional[catalog_models.ServingEndpoint]:
        """Apply partial updates to a serving endpoint (autoscaling/prompt/status)."""
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            return None

        if autoscale_policy is not None:
            endpoint.autoscale_policy = autoscale_policy
        if prompt_policy_id is not None:
            endpoint.prompt_policy_id = prompt_policy_id
        if status is not None:
            if status not in ("deploying", "healthy", "degraded", "failed"):
                raise ValueError(f"Invalid status {status}")
            endpoint.status = status

        endpoint.last_health_check = datetime.utcnow()
        return self.endpoint_repo.update(endpoint)

    def rollback_endpoint(self, endpoint_id: str) -> bool:
        """Rollback a serving endpoint to the previous version."""
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            return False

        if not endpoint.rollback_plan:
            raise ValueError(f"Endpoint {endpoint_id} has no rollback plan")

        try:
            endpoint_name = _get_endpoint_k8s_name(endpoint.id)
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
        autoscale_policy: Optional[dict] = None,
        serving_framework: Optional[str] = None,
        deployment_spec: Optional[DeploymentSpec] = None,
    ) -> catalog_models.ServingEndpoint:
        """
        Redeploy an existing serving endpoint with the same or updated configuration.
        
        This method ensures:
        1. No concurrent redeployments (checks endpoint status)
        2. Complete deletion of existing resources before redeployment
        3. Configuration backup for rollback on failure
        4. Atomic DB updates (only after successful Kubernetes deployment)
        """
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")

        # Check if endpoint is already being redeployed or deleted
        # But allow redeployment if Kubernetes resources don't exist (stuck in deploying state)
        if endpoint.status == "deploying":
            # Check if Kubernetes resources actually exist
            endpoint_name = _get_endpoint_k8s_name(endpoint.id)
            namespace = f"llm-ops-{endpoint.environment}"
            settings = get_settings()
            
            try:
                # Check if KServe InferenceService or Deployment exists
                resource_exists = False
                if settings.use_kserve:
                    try:
                        from kubernetes import client
                        custom_api = client.CustomObjectsApi()
                        custom_api.get_namespaced_custom_object(
                            group="serving.kserve.io",
                            version="v1beta1",
                            namespace=namespace,
                            plural="inferenceservices",
                            name=endpoint_name,
                        )
                        resource_exists = True
                        logger.info(f"InferenceService {endpoint_name} exists, deployment is in progress")
                    except Exception:
                        # InferenceService doesn't exist, check Deployment
                        try:
                            apps_api = client.AppsV1Api()
                            apps_api.read_namespaced_deployment(
                                name=endpoint_name,
                                namespace=namespace,
                            )
                            resource_exists = True
                            logger.info(f"Deployment {endpoint_name} exists, deployment is in progress")
                        except Exception:
                            # Neither exists, deployment likely failed
                            logger.warning(
                                f"Endpoint {endpoint_id} is in 'deploying' state but no Kubernetes resources found. "
                                "This indicates a failed deployment. Allowing redeployment."
                            )
                            resource_exists = False
                else:
                    # Check Deployment for raw deployment mode
                    try:
                        from kubernetes import client
                        apps_api = client.AppsV1Api()
                        apps_api.read_namespaced_deployment(
                            name=endpoint_name,
                            namespace=namespace,
                        )
                        resource_exists = True
                        logger.info(f"Deployment {endpoint_name} exists, deployment is in progress")
                    except Exception:
                        # Deployment doesn't exist, deployment likely failed
                        logger.warning(
                            f"Endpoint {endpoint_id} is in 'deploying' state but no Kubernetes resources found. "
                            "This indicates a failed deployment. Allowing redeployment."
                        )
                        resource_exists = False
                
                # If resources exist, deployment is actually in progress
                if resource_exists:
                    raise ValueError(
                        f"Endpoint {endpoint_id} is already being deployed. "
                        "Please wait for the current deployment to complete."
                    )
                else:
                    # Resources don't exist, mark as failed and allow redeployment
                    logger.info(
                        f"Endpoint {endpoint_id} was stuck in 'deploying' state. "
                        "Marking as 'failed' and allowing redeployment."
                    )
                    endpoint.status = "failed"
                    endpoint = self.endpoint_repo.update(endpoint)
            except Exception as e:
                # If we can't check Kubernetes resources, log warning but allow redeployment
                logger.warning(
                    f"Could not verify Kubernetes resources for endpoint {endpoint_id}: {e}. "
                    "Allowing redeployment to proceed."
                )
                endpoint.status = "failed"
                endpoint = self.endpoint_repo.update(endpoint)

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
        endpoint_name = _get_endpoint_k8s_name(endpoint.id)
        namespace = f"llm-ops-{endpoint.environment}"
        settings = get_settings()
        image_config = get_image_config()
        
        # Backup current configuration for rollback
        backup_config = {
            "runtime_image": endpoint.runtime_image,
            "use_gpu": endpoint.use_gpu,
            "cpu_request": endpoint.cpu_request,
            "cpu_limit": endpoint.cpu_limit,
            "memory_request": endpoint.memory_request,
            "memory_limit": endpoint.memory_limit,
            "autoscale_policy": endpoint.autoscale_policy,
            "deployment_spec": endpoint.deployment_spec if hasattr(endpoint, 'deployment_spec') else None,
            "status": endpoint.status,
        }
        
        try:
            # Mark endpoint as deploying to prevent concurrent redeployments
            endpoint.status = "deploying"
            endpoint = self.endpoint_repo.update(endpoint)
            logger.info(f"Starting redeployment for endpoint {endpoint_id} (name: {endpoint_name}, namespace: {namespace})")
            logger.debug(f"Backup configuration: {backup_config}")
            
            # Delete existing Kubernetes resources
            logger.info(f"Deleting existing Kubernetes resources for endpoint {endpoint_id}...")
            delete_success = self.deployer.delete_endpoint(endpoint_name, namespace=namespace)
            logger.info(f"delete_endpoint() returned {delete_success} for endpoint {endpoint_id}")

            # Use deployer-side unified deletion wait logic so redeploy == delete -> deploy
            resource_type = "KServe InferenceService" if settings.use_kserve else "Deployment"
            try:
                # Wait for full cleanup (includes handling terminating/finalizers)
                self.deployer._ensure_resource_deleted(
                    endpoint_name=endpoint_name,
                    namespace=namespace,
                    resource_type=resource_type,
                    max_wait=120,
                    check_interval=2,
                )
                logger.info(f"Verified deletion of {resource_type} {endpoint_name} for endpoint {endpoint_id}")
            except Exception as wait_error:
                logger.error(
                    f"Failed to verify deletion of {resource_type} {endpoint_name}: {wait_error}"
                )
                raise ValueError(
                    f"Timeout or error while waiting for {resource_type} {endpoint_name} deletion. "
                    f"Please try again after ensuring the resource is removed."
                ) from wait_error

            # Validate that model has storage_uri
            if not model_entry.storage_uri:
                raise ValueError(
                    f"Model entry {endpoint.model_entry_id} does not have storage_uri. "
                    "Please upload model files before redeploying."
                )

            # Determine deployment_spec: new spec -> existing endpoint deployment_spec -> reconstruct from metadata
            logger.info(f"Determining deployment_spec for endpoint {endpoint_id}...")
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
                # Preserve existing endpoint settings when reconstructing
                if not effective_deployment_spec and model_entry.model_metadata:
                    model_family = model_entry.model_metadata.get("model_family")
                    job_type = model_entry.model_metadata.get("job_type")
                    if model_family and job_type:
                        # Determine serve_target based on job_type
                        if job_type == "RAG_TUNING":
                            serve_target = "RAG"
                        else:
                            serve_target = "GENERATION"
                        
                        # Determine use_gpu: parameter -> endpoint -> settings
                        effective_use_gpu = (
                            use_gpu
                            if use_gpu is not None
                            else endpoint.use_gpu
                            if endpoint.use_gpu is not None
                            else settings.use_gpu
                        )
                        
                        # Preserve existing runtime settings if available from endpoint
                        # Otherwise use reasonable defaults
                        existing_runtime = None
                        if backup_config.get("deployment_spec"):
                            try:
                                existing_spec = DeploymentSpec(**backup_config["deployment_spec"])
                                existing_runtime = existing_spec.runtime
                            except Exception:
                                pass
                        
                        runtime_config = existing_runtime or {
                            "max_concurrent_requests": 256,
                            "max_input_tokens": model_entry.model_metadata.get("max_position_embeddings", 4096),
                            "max_output_tokens": 1024,
                        }
                        
                        # Preserve existing resources if available
                        existing_resources = None
                        if backup_config.get("deployment_spec"):
                            try:
                                existing_spec = DeploymentSpec(**backup_config["deployment_spec"])
                                existing_resources = existing_spec.resources
                            except Exception:
                                pass
                        
                        gpus = 1 if effective_use_gpu else 0
                        resources_config = existing_resources or {
                            "gpus": gpus,
                            "gpu_memory_gb": 80 if effective_use_gpu else None,
                        }
                        
                        effective_deployment_spec = DeploymentSpec(
                            model_ref=f"{model_entry.name}-{model_entry.version}",
                            model_family=model_family,
                            job_type=job_type,
                            serve_target=serve_target,
                            resources=resources_config,
                            runtime=runtime_config,
                            use_gpu=effective_use_gpu,
                        )
                        logger.info(f"Reconstructed deployment_spec from model metadata for endpoint {endpoint_id} (preserved existing settings where possible)")

            # Determine effective configuration values
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
                # Handle None use_gpu in deployment_spec
                deployment_use_gpu = (
                    effective_deployment_spec.use_gpu
                    if effective_deployment_spec.use_gpu is not None
                    else (use_gpu if use_gpu is not None else (endpoint.use_gpu if endpoint.use_gpu is not None else settings.use_gpu))
                )
                
                effective_runtime_image = image_config.get_serve_image_with_fallback(
                    effective_deployment_spec.serve_target,
                    deployment_use_gpu
                )
                effective_use_gpu = deployment_use_gpu
                
                logger.info(
                    f"Using container image {effective_runtime_image} for serve_target {effective_deployment_spec.serve_target} "
                    f"(use_gpu={effective_use_gpu})"
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
            
            # Determine autoscale_policy: explicit override -> existing endpoint value -> None
            effective_autoscale_policy = autoscale_policy if autoscale_policy is not None else endpoint.autoscale_policy

            # Deploy to Kubernetes FIRST (before updating DB)
            # This ensures atomicity: if deployment fails, DB is not updated
            logger.info(f"Deploying Kubernetes resources for endpoint {endpoint_id}...")
            logger.debug(
                f"Deployment parameters: endpoint_name={endpoint_name}, namespace={namespace}, "
                f"use_gpu={effective_use_gpu}, runtime_image={effective_runtime_image}, "
                f"cpu_request={effective_cpu_request}, cpu_limit={effective_cpu_limit}, "
                f"memory_request={effective_memory_request}, memory_limit={effective_memory_limit}"
            )
            try:
                k8s_uid = self.deployer.deploy_endpoint(
                    endpoint_name=endpoint_name,
                    model_storage_uri=model_entry.storage_uri,
                    route=endpoint.route,
                    min_replicas=endpoint.min_replicas,
                    max_replicas=endpoint.max_replicas,
                    autoscale_policy=effective_autoscale_policy,
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
                logger.info(f"Successfully deployed Kubernetes resources for endpoint {endpoint_id}")
            except Exception as deploy_error:
                # Deployment failed - restore backup configuration
                logger.error(f"Kubernetes deployment failed for endpoint {endpoint_id}: {deploy_error}")
                logger.info(f"Restoring backup configuration for endpoint {endpoint_id}")
                
                endpoint.runtime_image = backup_config["runtime_image"]
                endpoint.use_gpu = backup_config["use_gpu"]
                endpoint.cpu_request = backup_config["cpu_request"]
                endpoint.cpu_limit = backup_config["cpu_limit"]
                endpoint.memory_request = backup_config["memory_request"]
                endpoint.memory_limit = backup_config["memory_limit"]
                endpoint.autoscale_policy = backup_config["autoscale_policy"]
                if hasattr(endpoint, 'deployment_spec'):
                    endpoint.deployment_spec = backup_config["deployment_spec"]
                endpoint.status = backup_config["status"] or "failed"
                endpoint = self.endpoint_repo.update(endpoint)
                
                raise ValueError(
                    f"Failed to deploy Kubernetes resources for endpoint {endpoint_id}. "
                    f"Configuration has been restored to previous state. Error: {deploy_error}"
                ) from deploy_error
            
            # Update DB ONLY after successful Kubernetes deployment
            endpoint.runtime_image = effective_runtime_image
            endpoint.use_gpu = effective_use_gpu
            endpoint.cpu_request = effective_cpu_request
            endpoint.cpu_limit = effective_cpu_limit
            endpoint.memory_request = effective_memory_request
            endpoint.memory_limit = effective_memory_limit
            endpoint.autoscale_policy = effective_autoscale_policy
            
            # Store DeploymentSpec if provided or reconstructed
            if effective_deployment_spec:
                endpoint.deployment_spec = effective_deployment_spec.model_dump()
            
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
        except ValueError:
            # Re-raise ValueError as-is (these are expected errors)
            raise
        except Exception as e:
            logger.error(f"Failed to redeploy endpoint {endpoint_id}: {e}", exc_info=True)
            # Try to restore backup configuration
            try:
                endpoint.runtime_image = backup_config["runtime_image"]
                endpoint.use_gpu = backup_config["use_gpu"]
                endpoint.cpu_request = backup_config["cpu_request"]
                endpoint.cpu_limit = backup_config["cpu_limit"]
                endpoint.memory_request = backup_config["memory_request"]
                endpoint.memory_limit = backup_config["memory_limit"]
                endpoint.autoscale_policy = backup_config["autoscale_policy"]
                if hasattr(endpoint, 'deployment_spec'):
                    endpoint.deployment_spec = backup_config["deployment_spec"]
                endpoint.status = backup_config["status"] or "failed"
                endpoint = self.endpoint_repo.update(endpoint)
                logger.info(f"Restored backup configuration for endpoint {endpoint_id}")
            except Exception as restore_error:
                logger.error(f"Failed to restore backup configuration for endpoint {endpoint_id}: {restore_error}")
            raise

    def delete_endpoint(self, endpoint_id: str) -> bool:
        """Delete a serving endpoint and its Kubernetes resources."""
        endpoint = self.endpoint_repo.get(endpoint_id)
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")

        # Always try to delete Kubernetes resources, regardless of model type
        # The endpoint may have Kubernetes resources even if model_entry_id is None or external
            endpoint_name = _get_endpoint_k8s_name(endpoint.id)
        namespace = f"llm-ops-{endpoint.environment}"
        
        try:
            logger.info(f"Attempting to delete Kubernetes resources for endpoint {endpoint_id} (name: {endpoint_name}, namespace: {namespace})")
            success = self.deployer.delete_endpoint(endpoint_name, namespace=namespace)
            if success:
                logger.info(f"Successfully deleted Kubernetes resources for endpoint {endpoint_id}")
            else:
                logger.warning(f"Failed to delete Kubernetes resources for {endpoint_id}; skipping database deletion")
                return False
        except Exception as k8s_error:
            # Log the error and do NOT delete from DB if k8s cleanup failed
            logger.error(f"Exception while deleting Kubernetes resources for {endpoint_id}: {k8s_error}", exc_info=True)
            logger.warning("Skipping database deletion because Kubernetes resources were not cleaned up")
            return False

        # Delete from database only after Kubernetes resources are confirmed deleted
        try:
            self.endpoint_repo.delete(endpoint)
            logger.info(f"Deleted serving endpoint {endpoint_id} from database")
            return True
        except Exception as db_error:
            logger.error(f"Failed to delete endpoint {endpoint_id} from database: {db_error}")
            raise

    def get_prompt_for_endpoint(
        self,
        endpoint_id: str,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Optional[catalog_models.PromptTemplate]:
        """Get the prompt template for a serving endpoint (with A/B routing)."""
        return self.prompt_router.select_prompt(endpoint_id, user_id, request_id)

