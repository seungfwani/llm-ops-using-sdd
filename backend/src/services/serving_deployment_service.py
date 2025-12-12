"""Serving deployment service for managing framework-specific deployments."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from kubernetes.client.rest import ApiException
from sqlalchemy.orm import Session

from catalog import models as catalog_models
from catalog.repositories import ServingDeploymentRepository
from integrations.serving.factory import ServingFrameworkFactory
from integrations.serving.interface import ServingFrameworkAdapter
from services.integration_config import IntegrationConfigService
from core.settings import get_settings
from core.clients.kubernetes_client import KubernetesClient

logger = logging.getLogger(__name__)


class ServingDeploymentService:
    """Service for managing serving deployments with framework adapters."""
    
    def __init__(self, session: Session):
        """Initialize service.
        
        Args:
            session: Database session
        """
        self.session = session
        self.deployment_repo = ServingDeploymentRepository(session)
        self.integration_config = IntegrationConfigService(session)
        self.settings = get_settings()
        # Kubernetes client will be initialized lazily when needed (post-deployment management)
        self._k8s_client: Optional[KubernetesClient] = None
    
    @property
    def k8s_client(self) -> KubernetesClient:
        """Lazy initialization of Kubernetes client."""
        if self._k8s_client is None:
            self._k8s_client = KubernetesClient(logger_prefix="ServingDeploymentService")
        return self._k8s_client
    
    def create_deployment(
        self,
        endpoint_id: UUID,
        framework_name: str,
        model_uri: str,
        model_name: str,
        namespace: str,
        resource_requests: Optional[Dict[str, str]] = None,
        resource_limits: Optional[Dict[str, str]] = None,
        min_replicas: int = 1,
        max_replicas: int = 1,
        autoscaling_metrics: Optional[Dict[str, Any]] = None,
    ) -> catalog_models.ServingDeployment:
        """Create a serving deployment using the specified framework adapter.
        
        Args:
            endpoint_id: Serving endpoint ID
            framework_name: Framework name ("kserve", "ray_serve")
            model_uri: Model storage URI
            model_name: Model name
            namespace: Kubernetes namespace
            resource_requests: Resource requests
            resource_limits: Resource limits
            min_replicas: Minimum replicas
            max_replicas: Maximum replicas
            autoscaling_metrics: Autoscaling configuration
        
        Returns:
            Created ServingDeployment entity
        """
        # Get framework configuration
        config = self.integration_config.get_config("serving", framework_name)
        if not config or not config.get("enabled"):
            raise ValueError(f"Framework {framework_name} is not enabled or configured")
        
        # Create adapter
        adapter_config = {
            "namespace": namespace,
            "enabled": config["enabled"],
            **config.get("config", {}),
        }
        adapter = ServingFrameworkFactory.create_adapter(framework_name, adapter_config)
        
        # Deploy using adapter
        deployment_info = adapter.deploy(
            endpoint_id=endpoint_id,
            model_uri=model_uri,
            model_name=model_name,
            namespace=namespace,
            resource_requests=resource_requests,
            resource_limits=resource_limits,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            autoscaling_metrics=autoscaling_metrics,
        )
        
        # Create deployment record
        deployment = catalog_models.ServingDeployment(
            id=uuid4(),
            serving_endpoint_id=endpoint_id,
            serving_framework=framework_name,
            framework_resource_id=deployment_info["framework_resource_id"],
            framework_namespace=deployment_info["framework_namespace"],
            replica_count=min_replicas,
            min_replicas=min_replicas,
            max_replicas=max_replicas,
            autoscaling_metrics=autoscaling_metrics,
            resource_requests=resource_requests,
            resource_limits=resource_limits,
            framework_status=deployment_info.get("status"),
        )
        
        return self.deployment_repo.create(deployment)
    
    def get_deployment(
        self,
        endpoint_id: UUID,
    ) -> Optional[catalog_models.ServingDeployment]:
        """Get deployment for an endpoint.
        
        Args:
            endpoint_id: Serving endpoint ID
        
        Returns:
            ServingDeployment entity or None
        """
        return self.deployment_repo.get_by_endpoint_id(endpoint_id)
    
    def update_deployment(
        self,
        endpoint_id: UUID,
        min_replicas: Optional[int] = None,
        max_replicas: Optional[int] = None,
        resource_requests: Optional[Dict[str, str]] = None,
        resource_limits: Optional[Dict[str, str]] = None,
    ) -> catalog_models.ServingDeployment:
        """Update deployment configuration using Kubernetes API directly.
        
        Note: KServe adapter is only used for deployment. Post-deployment management
        (updates, scaling, etc.) uses Kubernetes API directly.
        
        If ServingDeployment record doesn't exist, this method will:
        1. Get ServingEndpoint information
        2. Generate Kubernetes resource name from endpoint ID
        3. Update Kubernetes resources directly
        4. Optionally create ServingDeployment record for future use
        
        Args:
            endpoint_id: Serving endpoint ID
            min_replicas: New minimum replicas
            max_replicas: New maximum replicas
            resource_requests: New resource requests
            resource_limits: New resource limits
        
        Returns:
            Updated ServingDeployment entity (may be newly created)
        """
        deployment = self.deployment_repo.get_by_endpoint_id(endpoint_id)
        
        # If deployment record doesn't exist, get info from ServingEndpoint
        if not deployment:
            from serving.repositories import ServingEndpointRepository
            endpoint_repo = ServingEndpointRepository(self.session)
            endpoint = endpoint_repo.get(endpoint_id)
            if not endpoint:
                raise ValueError(f"Endpoint {endpoint_id} not found")
            
            # Generate Kubernetes resource name from endpoint ID
            endpoint_id_str = str(endpoint_id).replace("-", "")
            short_id = endpoint_id_str[:12]
            base_name = f"svc-{short_id}"
            namespace = f"llm-ops-{endpoint.environment}"
            
            # Determine serving framework from settings
            serving_framework = "kserve" if self.settings.use_kserve else "deployment"
            
            # For KServe, framework_resource_id includes -predictor suffix
            # For Deployment, use base name
            if serving_framework == "kserve":
                framework_resource_id = f"{base_name}-predictor"
            else:
                framework_resource_id = base_name
            
            logger.info(
                f"ServingDeployment record not found for endpoint {endpoint_id}, "
                f"using endpoint info: resource_id={framework_resource_id}, "
                f"namespace={namespace}, framework={serving_framework}"
            )
        else:
            namespace = deployment.framework_namespace
            framework_resource_id = deployment.framework_resource_id
            serving_framework = deployment.serving_framework
        
        # Use Kubernetes API directly for post-deployment management
        if serving_framework == "kserve":
            # Update KServe InferenceService via Kubernetes CustomObjectsApi
            # framework_resource_id may include -predictor suffix, but InferenceService name doesn't
            # Remove -predictor suffix if present to get actual InferenceService name
            inferenceservice_name = framework_resource_id
            if inferenceservice_name.endswith("-predictor"):
                inferenceservice_name = inferenceservice_name[:-10]  # Remove "-predictor"
            
            try:
                # Get current InferenceService
                inference_service = self.k8s_client.call_with_401_retry(
                    lambda: self.k8s_client.custom_api.get_namespaced_custom_object(
                        group="serving.kserve.io",
                        version="v1beta1",
                        namespace=namespace,
                        plural="inferenceservices",
                        name=inferenceservice_name,
                    ),
                    f"get InferenceService {inferenceservice_name} for update"
                )
                
                # Update spec
                spec = inference_service.get("spec", {})
                predictor = spec.get("predictor", {})
                
                if min_replicas is not None:
                    predictor["minReplicas"] = min_replicas
                if max_replicas is not None:
                    predictor["maxReplicas"] = max_replicas
                
                # Update resources if provided
                predictor_type = next(iter(predictor.keys() - {"minReplicas", "maxReplicas"}), None)
                if predictor_type and predictor_type in predictor:
                    if resource_requests or resource_limits:
                        if "resources" not in predictor[predictor_type]:
                            predictor[predictor_type]["resources"] = {}
                        if resource_requests:
                            predictor[predictor_type]["resources"]["requests"] = resource_requests
                        if resource_limits:
                            predictor[predictor_type]["resources"]["limits"] = resource_limits
                
                # Patch InferenceService
                self.k8s_client.call_with_401_retry(
                    lambda: self.k8s_client.custom_api.patch_namespaced_custom_object(
                        group="serving.kserve.io",
                        version="v1beta1",
                        namespace=namespace,
                        plural="inferenceservices",
                        name=inferenceservice_name,
                        body=inference_service,
                    ),
                    f"patch InferenceService {inferenceservice_name}"
                )
                logger.info(f"Updated KServe InferenceService {inferenceservice_name} via Kubernetes API")
                
            except ApiException as e:
                logger.error(f"Failed to update KServe InferenceService {inferenceservice_name}: {e}")
                raise ValueError(f"Failed to update KServe InferenceService: {e.reason}")
        else:
            # For non-KServe deployments, update Deployment directly
            try:
                # Get current Deployment
                k8s_deployment = self.k8s_client.call_with_401_retry(
                    lambda: self.k8s_client.apps_api.read_namespaced_deployment(
                        name=framework_resource_id,
                        namespace=namespace,
                    ),
                    f"get Deployment {framework_resource_id} for update"
                )
                
                # Update replicas if provided
                if min_replicas is not None or max_replicas is not None:
                    # For Deployment, we typically update spec.replicas (which sets desired replicas)
                    # min/max replicas are usually handled by HPA
                    if min_replicas is not None and min_replicas > 0:
                        k8s_deployment.spec.replicas = min_replicas
                    elif max_replicas is not None and max_replicas > 0:
                        k8s_deployment.spec.replicas = max_replicas
                    elif min_replicas == 0 and max_replicas == 0:
                        k8s_deployment.spec.replicas = 0
                
                # Update resources if provided
                if resource_requests or resource_limits:
                    if k8s_deployment.spec.template.spec.containers:
                        container = k8s_deployment.spec.template.spec.containers[0]
                        if not container.resources:
                            from kubernetes import client
                            container.resources = client.V1ResourceRequirements()
                        if resource_requests:
                            if not container.resources.requests:
                                container.resources.requests = {}
                            container.resources.requests.update(resource_requests)
                        if resource_limits:
                            if not container.resources.limits:
                                container.resources.limits = {}
                            container.resources.limits.update(resource_limits)
                
                # Patch Deployment
                self.k8s_client.call_with_401_retry(
                    lambda: self.k8s_client.apps_api.patch_namespaced_deployment(
                        name=framework_resource_id,
                        namespace=namespace,
                        body=k8s_deployment,
                    ),
                    f"patch Deployment {framework_resource_id}"
                )
                logger.info(f"Updated Deployment {framework_resource_id} via Kubernetes API")
                
            except ApiException as e:
                logger.error(f"Failed to update Deployment {framework_resource_id}: {e}")
                raise ValueError(f"Failed to update Deployment: {e.reason}")
        
        # Update or create deployment record in database
        if not deployment:
            # Create new deployment record
            # Use framework_resource_id with -predictor suffix for KServe (as stored in DB)
            from catalog import models as catalog_models
            stored_resource_id = framework_resource_id
            if serving_framework == "kserve" and not stored_resource_id.endswith("-predictor"):
                stored_resource_id = f"{framework_resource_id}-predictor"
            
            deployment = catalog_models.ServingDeployment(
                id=uuid4(),
                serving_endpoint_id=endpoint_id,
                serving_framework=serving_framework,
                framework_resource_id=stored_resource_id,
                framework_namespace=namespace,
                replica_count=min_replicas if min_replicas is not None else 0,
                min_replicas=min_replicas if min_replicas is not None else 0,
                max_replicas=max_replicas if max_replicas is not None else 0,
                resource_requests=resource_requests,
                resource_limits=resource_limits,
            )
            deployment = self.deployment_repo.create(deployment)
            logger.info(f"Created new ServingDeployment record for endpoint {endpoint_id} with resource_id={stored_resource_id}")
        else:
            # Update existing deployment record
            if min_replicas is not None:
                deployment.min_replicas = min_replicas
            if max_replicas is not None:
                deployment.max_replicas = max_replicas
            if resource_requests is not None:
                deployment.resource_requests = resource_requests
            if resource_limits is not None:
                deployment.resource_limits = resource_limits
            
            deployment = self.deployment_repo.update(deployment)
        
        return deployment
    
    def refresh_deployment_status(
        self,
        endpoint_id: UUID,
    ) -> catalog_models.ServingDeployment:
        """Refresh deployment status from framework.
        
        Args:
            endpoint_id: Serving endpoint ID
        
        Returns:
            Updated ServingDeployment entity
        """
        deployment = self.deployment_repo.get_by_endpoint_id(endpoint_id)
        if not deployment:
            raise ValueError(f"Deployment not found for endpoint {endpoint_id}")
        
        # Get adapter
        config = self.integration_config.get_config("serving", deployment.serving_framework)
        if not config or not config.get("enabled"):
            # Graceful degradation: return current deployment without refresh
            logger.warning(f"Framework {deployment.serving_framework} is not enabled, skipping status refresh")
            return deployment
        
        adapter_config = {
            "namespace": deployment.framework_namespace,
            "enabled": config["enabled"],
            **config.get("config", {}),
        }
        adapter = ServingFrameworkFactory.create_adapter(deployment.serving_framework, adapter_config)
        
        # Get status from framework
        status_info = adapter.get_deployment_status(
            framework_resource_id=deployment.framework_resource_id,
            namespace=deployment.framework_namespace,
        )
        
        # Update deployment record
        deployment.replica_count = status_info.get("replicas", deployment.replica_count)
        deployment.framework_status = status_info
        
        return self.deployment_repo.update(deployment)
    
    def delete_deployment(
        self,
        endpoint_id: UUID,
    ) -> None:
        """Delete deployment.
        
        Args:
            endpoint_id: Serving endpoint ID
        """
        deployment = self.deployment_repo.get_by_endpoint_id(endpoint_id)
        if not deployment:
            logger.warning(f"Deployment not found for endpoint {endpoint_id}, skipping deletion")
            return
        
        # Get adapter
        config = self.integration_config.get_config("serving", deployment.serving_framework)
        if config and config.get("enabled"):
            adapter_config = {
                "namespace": deployment.framework_namespace,
                "enabled": config["enabled"],
                **config.get("config", {}),
            }
            adapter = ServingFrameworkFactory.create_adapter(deployment.serving_framework, adapter_config)
            
            # Delete using adapter (graceful degradation on failure)
            try:
                adapter.delete_deployment(
                    framework_resource_id=deployment.framework_resource_id,
                    namespace=deployment.framework_namespace,
                )
            except Exception as e:
                logger.warning(f"Failed to delete deployment from framework: {e}")
        
        # Delete deployment record
        self.deployment_repo.delete(deployment.id)

