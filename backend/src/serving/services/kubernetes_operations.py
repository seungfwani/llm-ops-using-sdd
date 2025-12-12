"""Kubernetes operations service for serving endpoints.

This service handles operational tasks for deployed serving endpoints:
- Pod status checking
- Pod log retrieval
- Pod deletion/restart
- Deployment status checking (for resources created by KServe)

Following the principle: "KServe handles deployment, Kubernetes handles operations"
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
from kubernetes import client
from kubernetes.client.rest import ApiException

from core.clients.kubernetes_client import KubernetesClient

logger = logging.getLogger(__name__)


class KubernetesOperations:
    """Service for Kubernetes operational tasks on serving endpoints."""
    
    def __init__(self):
        """Initialize Kubernetes client."""
        # Initialize Kubernetes client using shared utility
        self.k8s_client = KubernetesClient(logger_prefix="KubernetesOperations")
        self.core_api = self.k8s_client.core_api
        self.apps_api = self.k8s_client.apps_api
        self.custom_api = self.k8s_client.custom_api
    
    def get_pod_status(
        self,
        endpoint_name: str,
        namespace: str = "default",
        is_kserve: bool = False,
    ) -> Optional[str]:
        """
        Check actual pod status to determine endpoint health.
        
        This is the operational status check - after KServe has deployed the resources,
        we use Kubernetes to check the actual pod status.
        
        Args:
            endpoint_name: Name of the endpoint (KServe InferenceService name or Deployment name)
            namespace: Kubernetes namespace
            is_kserve: Whether this is a KServe InferenceService (affects pod label selectors)
            
        Returns:
            Status string: "healthy", "degraded", "deploying", or "failed"
        """
        logger.debug(f"Checking pod status for {endpoint_name} in namespace {namespace} (is_kserve={is_kserve})")
        try:
            # Get pods for this deployment
            # For KServe, pods are labeled with the InferenceService name
            # For raw Deployment, pods are labeled with app={endpoint_name}
            if is_kserve:
                label_selectors = [
                    f"serving.kserve.io/inferenceservice={endpoint_name}",
                    f"app={endpoint_name}",
                ]
            else:
                label_selectors = [f"app={endpoint_name}"]
            
            pods = None
            for label_selector in label_selectors:
                try:
                    logger.debug(f"Querying pods with label selector: {label_selector} in namespace {namespace}")
                    pods = self.core_api.list_namespaced_pod(
                        namespace=namespace,
                        label_selector=label_selector,
                    )
                    logger.debug(f"Found {len(pods.items)} pods with selector {label_selector}")
                    if pods.items:
                        break
                except ApiException as e:
                    logger.warning(f"Failed to query pods with selector {label_selector}: {e.status} - {e.reason}")
                    continue
            
            # For KServe, if label selector didn't work, try finding pods by name pattern
            if is_kserve and (not pods or not pods.items):
                try:
                    logger.debug(f"Label selector didn't find pods, trying to list all pods in namespace {namespace}")
                    all_pods = self.core_api.list_namespaced_pod(namespace=namespace)
                    logger.debug(f"Found {len(all_pods.items)} total pods in namespace {namespace}")
                    # Filter pods that start with endpoint_name (KServe naming: {endpoint_name}-predictor-{hash})
                    matching_pods = [p for p in all_pods.items if p.metadata.name.startswith(f"{endpoint_name}-predictor")]
                    logger.debug(f"Found {len(matching_pods)} pods matching name pattern {endpoint_name}-predictor")
                    if matching_pods:
                        class PodList:
                            items = matching_pods
                        pods = PodList()
                except ApiException as e:
                    logger.warning(f"Failed to list pods in namespace {namespace}: {e.status} - {e.reason}")
                    pass
            
            if not pods or not pods.items:
                logger.debug(f"No pods found for endpoint {endpoint_name} in namespace {namespace}, returning 'deploying'")
                return "deploying"  # No pods yet
            
            # Check for Pending pods with scheduling issues
            pending_pods = [p for p in pods.items if p.status.phase == "Pending"]
            if pending_pods:
                # Check why pods are pending
                for pod in pending_pods:
                    container_creating = False
                    if pod.status.container_statuses:
                        for container_status in pod.status.container_statuses:
                            if container_status.state and container_status.state.waiting:
                                waiting_reason = container_status.state.waiting.reason or ""
                                logger.debug(
                                    f"Pod {pod.metadata.name} waiting: reason={waiting_reason}, "
                                    f"message={container_status.state.waiting.message or 'N/A'}"
                                )
                                if "ContainerCreating" in waiting_reason or "Creating" in waiting_reason:
                                    container_creating = True
                                    logger.info(
                                        f"Pod {pod.metadata.name} is ContainerCreating, returning 'deploying' status"
                                    )
                                    break
                    
                    if container_creating:
                        return "deploying"  # Container is being created, still deploying
                    
                    if pod.status.conditions:
                        for condition in pod.status.conditions:
                            if condition.type == "PodScheduled" and condition.status != "True":
                                reason = condition.reason or "Unknown"
                                message = condition.message or ""
                                logger.warning(
                                    f"Pod {pod.metadata.name} is Pending: {reason} - {message}"
                                )
                                if "Unschedulable" in reason or "Insufficient" in message:
                                    return "deploying"  # Resource issue, still deploying
                                elif "WaitForFirstConsumer" in reason:
                                    return "deploying"  # Storage issue, still deploying
                return "deploying"  # Pending pods mean still deploying
            
            # Check pod phases and container statuses
            pod_phases = [pod.status.phase for pod in pods.items]
            ready_count = sum(1 for pod in pods.items if self._is_pod_ready(pod))
            total_count = len(pods.items)
            
            # Check for failed pods
            failed_pods = [p for p in pods.items if p.status.phase == "Failed"]
            if failed_pods:
                logger.warning(f"Found {len(failed_pods)} failed pods for endpoint {endpoint_name}")
                return "failed"
            
            # Check for error states in containers
            for pod in pods.items:
                if pod.status.container_statuses:
                    for container_status in pod.status.container_statuses:
                        if container_status.state:
                            # Check for terminated with error
                            if container_status.state.terminated:
                                if container_status.state.terminated.exit_code != 0:
                                    logger.warning(
                                        f"Pod {pod.metadata.name} container {container_status.name} "
                                        f"terminated with exit code {container_status.state.terminated.exit_code}"
                                    )
                                    return "failed"
                            # Check for waiting with error
                            elif container_status.state.waiting:
                                waiting_reason = container_status.state.waiting.reason or ""
                                if any(err in waiting_reason for err in ["Error", "CrashLoopBackOff", "ImagePullBackOff"]):
                                    logger.warning(
                                        f"Pod {pod.metadata.name} container {container_status.name} "
                                        f"in error state: {waiting_reason}"
                                    )
                                    return "failed"
            
            # Determine status based on ready count
            if ready_count == total_count and total_count > 0:
                return "healthy"
            elif ready_count > 0:
                return "degraded"  # Some pods ready, but not all
            else:
                return "deploying"  # No pods ready yet
                
        except ApiException as e:
            logger.error(f"Failed to check pod status for {endpoint_name}: {e}")
            return None
    
    def _is_pod_ready(self, pod: client.V1Pod) -> bool:
        """Check if a pod is ready."""
        if pod.status.conditions:
            for condition in pod.status.conditions:
                if condition.type == "Ready" and condition.status == "True":
                    return True
        return False
    
    def get_pod_logs(
        self,
        endpoint_name: str,
        namespace: str = "default",
        is_kserve: bool = False,
        tail_lines: int = 100,
        container: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get logs from pods for an endpoint.
        
        Args:
            endpoint_name: Name of the endpoint
            namespace: Kubernetes namespace
            is_kserve: Whether this is a KServe InferenceService
            tail_lines: Number of lines to retrieve
            container: Container name (optional, uses first container if not specified)
            
        Returns:
            Dictionary with pod names as keys and log content as values
        """
        logger.debug(f"Getting pod logs for {endpoint_name} in namespace {namespace}")
        logs = {}
        
        try:
            # Get pods (same logic as get_pod_status)
            if is_kserve:
                label_selectors = [
                    f"serving.kserve.io/inferenceservice={endpoint_name}",
                    f"app={endpoint_name}",
                ]
            else:
                label_selectors = [f"app={endpoint_name}"]
            
            pods = None
            for label_selector in label_selectors:
                try:
                    pods = self.core_api.list_namespaced_pod(
                        namespace=namespace,
                        label_selector=label_selector,
                    )
                    if pods.items:
                        break
                except ApiException:
                    continue
            
            if not pods or not pods.items:
                logger.warning(f"No pods found for endpoint {endpoint_name}")
                return logs
            
            # Get logs from each pod
            for pod in pods.items:
                pod_name = pod.metadata.name
                try:
                    # Determine container name
                    container_name = container
                    if not container_name and pod.spec.containers:
                        container_name = pod.spec.containers[0].name
                    
                    log_content = self.core_api.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace,
                        container=container_name,
                        tail_lines=tail_lines,
                    )
                    logs[pod_name] = log_content
                except ApiException as e:
                    logger.warning(f"Failed to get logs for pod {pod_name}: {e}")
                    logs[pod_name] = f"Error retrieving logs: {str(e)}"
            
            return logs
            
        except Exception as e:
            logger.error(f"Failed to get pod logs for {endpoint_name}: {e}")
            return logs
    
    def delete_pod(
        self,
        pod_name: str,
        namespace: str = "default",
        force: bool = False,
    ) -> bool:
        """
        Delete a pod (forces restart if managed by Deployment/ReplicaSet).
        
        Args:
            pod_name: Name of the pod to delete
            namespace: Kubernetes namespace
            force: Whether to force deletion (grace period = 0)
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Deleting pod {pod_name} in namespace {namespace} (force={force})")
        try:
            body = client.V1DeleteOptions()
            if force:
                body.grace_period_seconds = 0
            
            self.core_api.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                body=body,
            )
            logger.info(f"Successfully deleted pod {pod_name}")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.info(f"Pod {pod_name} not found, may already be deleted")
                return True
            logger.error(f"Failed to delete pod {pod_name}: {e}")
            return False
    
    def get_deployment_status(
        self,
        endpoint_name: str,
        namespace: str = "default",
    ) -> Optional[Dict[str, Any]]:
        """
        Get Deployment status (for raw Kubernetes Deployments, not KServe).
        
        Args:
            endpoint_name: Name of the Deployment
            namespace: Kubernetes namespace
            
        Returns:
            Dictionary with deployment status information
        """
        logger.debug(f"Getting Deployment status for {endpoint_name} in namespace {namespace}")
        try:
            deployment = self.apps_api.read_namespaced_deployment(
                name=endpoint_name,
                namespace=namespace,
            )
            
            # Get pod status for more accurate health check
            pod_status = self.get_pod_status(endpoint_name, namespace, is_kserve=False)
            
            return {
                "uid": deployment.metadata.uid,
                "replicas": deployment.spec.replicas,
                "ready_replicas": deployment.status.ready_replicas or 0,
                "available_replicas": deployment.status.available_replicas or 0,
                "status": pod_status or "deploying",
            }
        except ApiException as e:
            if e.status == 404:
                logger.debug(f"Deployment {endpoint_name} not found in namespace {namespace}")
                return None
            logger.error(f"Failed to get Deployment status for {endpoint_name}: {e}")
            raise
    
    def get_kserve_inferenceservice_status(
        self,
        endpoint_name: str,
        namespace: str = "default",
    ) -> Optional[Dict[str, Any]]:
        """
        Get KServe InferenceService status from Kubernetes (operational check).
        
        This checks the InferenceService resource that KServe created,
        and combines it with actual pod status for accurate health information.
        
        Args:
            endpoint_name: Name of the InferenceService
            namespace: Kubernetes namespace
            
        Returns:
            Dictionary with InferenceService and pod status information
        """
        logger.debug(f"Getting KServe InferenceService status for {endpoint_name} in namespace {namespace}")
        try:
            inference_service = self.custom_api.get_namespaced_custom_object(
                group="serving.kserve.io",
                version="v1beta1",
                namespace=namespace,
                plural="inferenceservices",
                name=endpoint_name,
            )
        except ApiException as e:
            if e.status == 401:
                # Use KubernetesClient's retry mechanism
                try:
                    inference_service = self.k8s_client.call_with_401_retry(
                        lambda: self.custom_api.get_namespaced_custom_object(
                            group="serving.kserve.io",
                            version="v1beta1",
                            namespace=namespace,
                            plural="inferenceservices",
                            name=endpoint_name,
                        ),
                        f"get KServe InferenceService {endpoint_name} status"
                    )
                except ApiException as retry_e:
                    if retry_e.status == 404:
                        logger.debug(f"KServe InferenceService {endpoint_name} not found in namespace {namespace}")
                        return None
                    raise
            elif e.status == 404:
                logger.debug(f"KServe InferenceService {endpoint_name} not found in namespace {namespace}")
                return None
            logger.error(f"Failed to get KServe InferenceService status for {endpoint_name}: {e}")
            raise
        
        status = inference_service.get("status", {})
        conditions = status.get("conditions", [])
        
        # Get actual pod status for accurate health check
        pod_status = self.get_pod_status(endpoint_name, namespace, is_kserve=True)
        
        # Use pod status if available, otherwise use InferenceService conditions
        if pod_status:
            final_status = pod_status
        else:
            # Fall back to InferenceService Ready condition
            ready_condition = next(
                (c for c in conditions if c.get("type") == "Ready"),
                None
            )
            ready_status = ready_condition.get("status", "Unknown") if ready_condition else "Unknown"
            
            if ready_status == "True":
                final_status = "healthy"
            elif ready_status == "False":
                final_status = "degraded"
            else:
                final_status = "deploying"
        
        return {
            "uid": inference_service.get("metadata", {}).get("uid", ""),
            "replicas": status.get("components", {}).get("predictor", {}).get("replicas", 0),
            "ready_replicas": status.get("components", {}).get("predictor", {}).get("readyReplicas", 0),
            "available_replicas": status.get("components", {}).get("predictor", {}).get("availableReplicas", 0),
            "status": final_status,
            "conditions": conditions,
            "framework_status": status,
        }

