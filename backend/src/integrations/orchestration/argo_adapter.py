"""Argo Workflows adapter implementation for workflow orchestration.

Implements the OrchestrationAdapter interface using Argo Workflows.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datetime import datetime
from uuid import UUID

from integrations.orchestration.interface import OrchestrationAdapter
from integrations.error_handler import (
    handle_tool_errors,
    wrap_tool_error,
    ToolUnavailableError,
    ToolOperationError,
)

logger = logging.getLogger(__name__)


class ArgoWorkflowsAdapter(OrchestrationAdapter):
    """Argo Workflows adapter for workflow orchestration."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Argo Workflows adapter.
        
        Args:
            config: Configuration dictionary with:
                - namespace: Kubernetes namespace for workflows
                - controller_service: Argo Workflows controller service URL
                - enabled: Whether adapter is enabled
        """
        super().__init__(config)
        self.namespace = config.get("namespace", "argo")
        self.controller_service = config.get("controller_service")
        
        # Try to import Argo Workflows client
        try:
            from argo_workflows.api import WorkflowServiceApi
            from argo_workflows.configuration import Configuration
            from argo_workflows.api_client import ApiClient
            self._has_client = True
        except ImportError:
            logger.warning("Argo Workflows Python SDK not available, using Kubernetes client fallback")
            self._has_client = False
        
        # Initialize Kubernetes client as fallback
        try:
            from core.clients.kubernetes_client import KubernetesClient
            
            self.k8s_client = KubernetesClient(logger_prefix="ArgoAdapter")
            self._k8s_client = self.k8s_client.custom_api
            self._k8s_core_api = self.k8s_client.core_api
            self._k8s_available = True
        except Exception as e:
            logger.warning(f"ArgoAdapter: Failed to initialize Kubernetes client: {e}", exc_info=True)
            self._k8s_client = None
            self._k8s_core_api = None
            self._k8s_available = False
    
    def is_available(self) -> bool:
        """Check if Argo Workflows service is available."""
        if not self.is_enabled():
            return False
        
        if not self._k8s_available:
            return False
        
        try:
            # Check if Argo Workflows CRD exists
            self._k8s_client.get_cluster_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                plural="workflows",
                name="test",  # This will fail, but we check the error type
            )
            return True
        except Exception as e:
            # If it's a 404, the CRD exists but workflow doesn't (expected)
            # If it's a 403 or other error, Argo might not be installed
            error_str = str(e)
            if "404" in error_str or "NotFound" in error_str:
                return True  # CRD exists, service is available
            logger.debug(f"Argo Workflows availability check: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on Argo Workflows service."""
        if not self.is_enabled():
            return {
                "status": "unavailable",
                "message": "Argo Workflows adapter is disabled",
                "details": {},
            }
        
        if not self._k8s_available:
            return {
                "status": "unavailable",
                "message": "Kubernetes client not available",
                "details": {},
            }
        
        try:
            # Try to list workflows (limit 1) to check connectivity
            workflows = self._k8s_client.list_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=self.namespace,
                plural="workflows",
                limit=1,
            )
            return {
                "status": "healthy",
                "message": "Argo Workflows service is available",
                "details": {
                    "namespace": self.namespace,
                    "workflows_count": len(workflows.get("items", [])),
                },
            }
        except Exception as e:
            return {
                "status": "unavailable",
                "message": f"Argo Workflows health check failed: {str(e)}",
                "details": {"error": str(e)},
            }
    
    @handle_tool_errors("Argo Workflows", "Failed to create workflow")
    def create_workflow(
        self,
        pipeline_id: UUID,
        pipeline_name: str,
        pipeline_definition: Dict[str, Any],
        namespace: str,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Create a workflow from pipeline definition."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Argo Workflows integration is disabled",
                tool_name="argo_workflows",
            )
        
        if not self._k8s_available:
            raise ToolUnavailableError(
                message="Kubernetes client not available",
                tool_name="argo_workflows",
            )
        
        try:
            # Generate workflow name from pipeline name and ID
            workflow_name = f"{pipeline_name.lower().replace(' ', '-')}-{str(pipeline_id)[:8]}"
            
            # Build Argo Workflow manifest
            workflow_manifest = {
                "apiVersion": "argoproj.io/v1alpha1",
                "kind": "Workflow",
                "metadata": {
                    "name": workflow_name,
                    "namespace": namespace or self.namespace,
                    "labels": {
                        "pipeline-id": str(pipeline_id),
                        "pipeline-name": pipeline_name,
                    },
                },
                "spec": {
                    "entrypoint": pipeline_definition.get("entrypoint", "main"),
                    "retryStrategy": {
                        "limit": max_retries,
                    },
                    "templates": pipeline_definition.get("templates", []),
                    "arguments": pipeline_definition.get("arguments", {}),
                },
            }
            
            # Create workflow via Kubernetes API
            created_workflow = self._k8s_client.create_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace or self.namespace,
                plural="workflows",
                body=workflow_manifest,
            )
            
            workflow_id = created_workflow.get("metadata", {}).get("name")
            
            return {
                "workflow_id": workflow_id,
                "workflow_namespace": namespace or self.namespace,
                "status": created_workflow.get("status", {}).get("phase", "Pending"),
            }
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="argo_workflows",
                operation="create_workflow",
                context={"pipeline_id": str(pipeline_id), "pipeline_name": pipeline_name},
            )
    
    @handle_tool_errors("Argo Workflows", "Failed to get workflow status")
    def get_workflow_status(
        self,
        workflow_id: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """Get workflow status."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Argo Workflows integration is disabled",
                tool_name="argo_workflows",
            )
        
        if not self._k8s_available:
            raise ToolUnavailableError(
                message="Kubernetes client not available",
                tool_name="argo_workflows",
            )
        
        try:
            workflow = self._k8s_client.get_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace or self.namespace,
                plural="workflows",
                name=workflow_id,
            )
            
            status = workflow.get("status", {})
            phase = status.get("phase", "Unknown")
            
            # Extract node statuses for stage information
            nodes = status.get("nodes", {})
            current_stage = None
            stages = []
            
            for node_id, node_info in nodes.items():
                node_phase = node_info.get("phase", "")
                node_name = node_info.get("displayName", node_id)
                stages.append({
                    "name": node_name,
                    "id": node_id,
                    "phase": node_phase,
                    "started_at": node_info.get("startedAt"),
                    "finished_at": node_info.get("finishedAt"),
                })
                
                # Find currently running stage
                if node_phase in ["Running", "Pending"] and current_stage is None:
                    current_stage = node_name
            
            # Parse timestamps
            start_time = None
            end_time = None
            
            if status.get("startedAt"):
                try:
                    start_time = datetime.fromisoformat(status["startedAt"].replace("Z", "+00:00"))
                except Exception:
                    pass
            
            if status.get("finishedAt"):
                try:
                    end_time = datetime.fromisoformat(status["finishedAt"].replace("Z", "+00:00"))
                except Exception:
                    pass
            
            # Map Argo phases to platform statuses
            status_mapping = {
                "Pending": "pending",
                "Running": "running",
                "Succeeded": "succeeded",
                "Failed": "failed",
                "Error": "failed",
                "Unknown": "pending",
            }
            platform_status = status_mapping.get(phase, "pending")
            
            return {
                "status": platform_status,
                "current_stage": current_stage,
                "start_time": start_time,
                "end_time": end_time,
                "retry_count": status.get("retryStrategy", {}).get("retryCount", 0),
                "stages": stages,
            }
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="argo_workflows",
                operation="get_workflow_status",
                context={"workflow_id": workflow_id, "namespace": namespace},
            )
    
    @handle_tool_errors("Argo Workflows", "Failed to cancel workflow")
    def cancel_workflow(
        self,
        workflow_id: str,
        namespace: str,
    ) -> None:
        """Cancel a running workflow."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Argo Workflows integration is disabled",
                tool_name="argo_workflows",
            )
        
        if not self._k8s_available:
            raise ToolUnavailableError(
                message="Kubernetes client not available",
                tool_name="argo_workflows",
            )
        
        try:
            # Patch workflow to stop it
            patch_body = {
                "spec": {
                    "shutdown": "Stop",
                },
            }
            
            self._k8s_client.patch_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace or self.namespace,
                plural="workflows",
                name=workflow_id,
                body=patch_body,
            )
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="argo_workflows",
                operation="cancel_workflow",
                context={"workflow_id": workflow_id, "namespace": namespace},
            )
    
    @handle_tool_errors("Argo Workflows", "Failed to delete workflow")
    def delete_workflow(
        self,
        workflow_id: str,
        namespace: str,
    ) -> None:
        """Delete a workflow."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Argo Workflows integration is disabled",
                tool_name="argo_workflows",
            )
        
        if not self._k8s_available:
            raise ToolUnavailableError(
                message="Kubernetes client not available",
                tool_name="argo_workflows",
            )
        
        try:
            self._k8s_client.delete_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace or self.namespace,
                plural="workflows",
                name=workflow_id,
            )
        except Exception as e:
            # Ignore 404 errors (workflow already deleted)
            error_str = str(e)
            if "404" not in error_str and "NotFound" not in error_str:
                raise wrap_tool_error(
                    e,
                    tool_name="argo_workflows",
                    operation="delete_workflow",
                    context={"workflow_id": workflow_id, "namespace": namespace},
                )
    
    @handle_tool_errors("Argo Workflows", "Failed to retry workflow")
    def retry_workflow(
        self,
        workflow_id: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """Retry a failed workflow."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Argo Workflows integration is disabled",
                tool_name="argo_workflows",
            )
        
        if not self._k8s_available:
            raise ToolUnavailableError(
                message="Kubernetes client not available",
                tool_name="argo_workflows",
            )
        
        try:
            # Retry workflow by creating a new workflow with same spec
            workflow = self._k8s_client.get_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace or self.namespace,
                plural="workflows",
                name=workflow_id,
            )
            
            # Create new workflow with retry suffix
            retry_workflow_name = f"{workflow_id}-retry"
            workflow["metadata"]["name"] = retry_workflow_name
            workflow["metadata"].pop("uid", None)
            workflow["metadata"].pop("resourceVersion", None)
            workflow["status"] = {}
            
            retry_workflow = self._k8s_client.create_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace or self.namespace,
                plural="workflows",
                body=workflow,
            )
            
            return {
                "workflow_id": retry_workflow.get("metadata", {}).get("name"),
                "workflow_namespace": namespace or self.namespace,
                "status": retry_workflow.get("status", {}).get("phase", "Pending"),
            }
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="argo_workflows",
                operation="retry_workflow",
                context={"workflow_id": workflow_id, "namespace": namespace},
            )
    
    @handle_tool_errors("Argo Workflows", "Failed to get workflow logs")
    def get_workflow_logs(
        self,
        workflow_id: str,
        namespace: str,
        stage_name: Optional[str] = None,
    ) -> str:
        """Get workflow logs."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="Argo Workflows integration is disabled",
                tool_name="argo_workflows",
            )
        
        if not self._k8s_available:
            raise ToolUnavailableError(
                message="Kubernetes client not available",
                tool_name="argo_workflows",
            )
        
        try:
            from kubernetes import client as k8s_client
            
            # Get workflow to find pod names
            workflow = self._k8s_client.get_namespaced_custom_object(
                group="argoproj.io",
                version="v1alpha1",
                namespace=namespace or self.namespace,
                plural="workflows",
                name=workflow_id,
            )
            
            # Extract pod names from workflow status
            nodes = workflow.get("status", {}).get("nodes", {})
            logs = []
            
            for node_id, node_info in nodes.items():
                node_name = node_info.get("displayName", node_id)
                
                # Filter by stage name if provided
                if stage_name and node_name != stage_name:
                    continue
                
                # Get pod name
                pod_name = node_info.get("id")
                if not pod_name:
                    continue
                
                # Get logs from pod
                try:
                    core_api = k8s_client.CoreV1Api()
                    pod_logs = core_api.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=namespace or self.namespace,
                    )
                    logs.append(f"=== {node_name} ({pod_name}) ===\n{pod_logs}")
                except Exception as e:
                    logs.append(f"=== {node_name} ({pod_name}) ===\nError retrieving logs: {e}")
            
            return "\n\n".join(logs) if logs else "No logs available"
        except Exception as e:
            raise wrap_tool_error(
                e,
                tool_name="argo_workflows",
                operation="get_workflow_logs",
                context={"workflow_id": workflow_id, "namespace": namespace, "stage_name": stage_name},
            )

