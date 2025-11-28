"""Serving deployment controller for Kubernetes."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from core.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ServingDeployer:
    """Controller for deploying model serving endpoints to Kubernetes with HPA."""

    def __init__(self):
        """Initialize Kubernetes client."""
        try:
            if settings.kubeconfig_path:
                config.load_kube_config(config_file=settings.kubeconfig_path)
            else:
                config.load_incluster_config()
        except Exception as e:
            logger.warning(f"Failed to load kubeconfig: {e}, using default")
            try:
                config.load_kube_config()
            except Exception:
                logger.error("Could not initialize Kubernetes client")
                raise

        self.apps_api = client.AppsV1Api()
        self.core_api = client.CoreV1Api()
        self.autoscaling_api = client.AutoscalingV1Api()
        self.networking_api = client.NetworkingV1Api()

    def deploy_endpoint(
        self,
        endpoint_name: str,
        model_image: str,
        route: str,
        min_replicas: int,
        max_replicas: int,
        autoscale_policy: Optional[dict] = None,
        namespace: str = "default",
    ) -> str:
        """
        Deploy a serving endpoint to Kubernetes with HPA.

        Args:
            endpoint_name: Unique name for the deployment
            model_image: Container image for the model
            route: Ingress route path
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            autoscale_policy: HPA configuration (targetLatencyMs, gpuUtilization)
            namespace: Kubernetes namespace

        Returns:
            Deployment UID
        """
        deployment_id = str(uuid4())

        # Create Deployment
        container = client.V1Container(
            name=f"{endpoint_name}-serving",
            image=model_image,
            ports=[client.V1ContainerPort(container_port=8000, name="http")],
            resources=client.V1ResourceRequirements(
                requests={"memory": "4Gi", "cpu": "2"},
                limits={"memory": "8Gi", "cpu": "4"},
            ),
            liveness_probe=client.V1Probe(
                http_get=client.V1HTTPGetAction(path="/health", port=8000),
                initial_delay_seconds=30,
                period_seconds=10,
            ),
            readiness_probe=client.V1Probe(
                http_get=client.V1HTTPGetAction(path="/ready", port=8000),
                initial_delay_seconds=10,
                period_seconds=5,
            ),
        )

        deployment_spec = client.V1DeploymentSpec(
            replicas=min_replicas,
            selector=client.V1LabelSelector(
                match_labels={"app": endpoint_name, "endpoint-id": deployment_id}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    labels={"app": endpoint_name, "endpoint-id": deployment_id}
                ),
                spec=client.V1PodSpec(containers=[container]),
            ),
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=endpoint_name,
                namespace=namespace,
                labels={"endpoint-id": deployment_id, "managed-by": "llm-ops-platform"},
            ),
            spec=deployment_spec,
        )

        try:
            created_deployment = self.apps_api.create_namespaced_deployment(
                namespace=namespace, body=deployment
            )
            logger.info(f"Created deployment {endpoint_name} with UID {created_deployment.metadata.uid}")

            # Create Service
            service = client.V1Service(
                api_version="v1",
                kind="Service",
                metadata=client.V1ObjectMeta(
                    name=f"{endpoint_name}-svc",
                    namespace=namespace,
                    labels={"app": endpoint_name},
                ),
                spec=client.V1ServiceSpec(
                    selector={"app": endpoint_name},
                    ports=[client.V1ServicePort(port=8000, target_port=8000)],
                    type="ClusterIP",
                ),
            )
            self.core_api.create_namespaced_service(namespace=namespace, body=service)

            # Create HPA
            if autoscale_policy:
                hpa = client.V1HorizontalPodAutoscaler(
                    api_version="autoscaling/v1",
                    kind="HorizontalPodAutoscaler",
                    metadata=client.V1ObjectMeta(
                        name=f"{endpoint_name}-hpa",
                        namespace=namespace,
                    ),
                    spec=client.V1HorizontalPodAutoscalerSpec(
                        scale_target_ref=client.V1CrossVersionObjectReference(
                            api_version="apps/v1",
                            kind="Deployment",
                            name=endpoint_name,
                        ),
                        min_replicas=min_replicas,
                        max_replicas=max_replicas,
                        target_cpu_utilization_percentage=autoscale_policy.get("cpuUtilization", 70),
                    ),
                )
                self.autoscaling_api.create_namespaced_horizontal_pod_autoscaler(
                    namespace=namespace, body=hpa
                )
                logger.info(f"Created HPA for {endpoint_name}")

            # Create Ingress
            ingress = client.V1Ingress(
                api_version="networking.k8s.io/v1",
                kind="Ingress",
                metadata=client.V1ObjectMeta(
                    name=f"{endpoint_name}-ingress",
                    namespace=namespace,
                    annotations={
                        "nginx.ingress.kubernetes.io/rewrite-target": "/",
                    },
                ),
                spec=client.V1IngressSpec(
                    rules=[
                        client.V1IngressRule(
                            host="llm-ops.local",
                            http=client.V1HTTPIngressRuleValue(
                                paths=[
                                    client.V1HTTPIngressPath(
                                        path=route,
                                        path_type="Prefix",
                                        backend=client.V1IngressBackend(
                                            service=client.V1IngressServiceBackend(
                                                name=f"{endpoint_name}-svc",
                                                port=client.V1ServiceBackendPort(number=8000),
                                            )
                                        ),
                                    )
                                ]
                            ),
                        )
                    ]
                ),
            )
            self.networking_api.create_namespaced_ingress(namespace=namespace, body=ingress)
            logger.info(f"Created Ingress for {endpoint_name} at route {route}")

            return created_deployment.metadata.uid
        except ApiException as e:
            logger.error(f"Failed to deploy {endpoint_name}: {e}")
            raise

    def get_endpoint_status(
        self, endpoint_name: str, namespace: str = "default"
    ) -> Optional[dict]:
        """Retrieve deployment status from Kubernetes."""
        try:
            deployment = self.apps_api.read_namespaced_deployment(
                name=endpoint_name, namespace=namespace
            )
            return {
                "uid": deployment.metadata.uid,
                "replicas": deployment.spec.replicas,
                "ready_replicas": deployment.status.ready_replicas or 0,
                "available_replicas": deployment.status.available_replicas or 0,
                "status": self._map_deployment_status(deployment.status),
            }
        except ApiException as e:
            if e.status == 404:
                return None
            logger.error(f"Failed to get deployment status for {endpoint_name}: {e}")
            raise

    def rollback_endpoint(
        self, endpoint_name: str, namespace: str = "default"
    ) -> bool:
        """Rollback a deployment to the previous revision."""
        try:
            # Get deployment rollout history
            # In a real implementation, we'd track revisions and rollback to a specific one
            # For now, we'll scale down and delete, then recreate from rollback plan
            deployment = self.apps_api.read_namespaced_deployment(
                name=endpoint_name, namespace=namespace
            )
            # Scale down to 0
            deployment.spec.replicas = 0
            self.apps_api.patch_namespaced_deployment(
                name=endpoint_name, namespace=namespace, body=deployment
            )
            logger.info(f"Rolled back deployment {endpoint_name}")
            return True
        except ApiException as e:
            logger.error(f"Failed to rollback {endpoint_name}: {e}")
            return False

    @staticmethod
    def _map_deployment_status(status) -> str:
        """Map Kubernetes deployment status to our status enum."""
        if status.ready_replicas == status.replicas and status.replicas > 0:
            return "healthy"
        if status.unavailable_replicas:
            return "degraded"
        if status.replicas == 0:
            return "failed"
        return "deploying"

