"""Workflow orchestration adapter interface.

Defines the interface for orchestration system adapters (Argo Workflows, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import UUID

from integrations.base_adapter import BaseAdapter


class OrchestrationAdapter(BaseAdapter):
    """Interface for workflow orchestration adapters."""
    
    @abstractmethod
    def create_workflow(
        self,
        pipeline_id: UUID,
        pipeline_name: str,
        pipeline_definition: Dict[str, Any],
        namespace: str,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Create a workflow from pipeline definition.
        
        Args:
            pipeline_id: Platform pipeline ID
            pipeline_name: User-defined pipeline name
            pipeline_definition: DAG definition with stages and dependencies
            namespace: Kubernetes namespace for workflow
            max_retries: Maximum retry attempts
        
        Returns:
            Dictionary with workflow information:
            {
                "workflow_id": str,
                "workflow_namespace": str,
                "status": str
            }
        """
        pass
    
    @abstractmethod
    def get_workflow_status(
        self,
        workflow_id: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """Get workflow status.
        
        Args:
            workflow_id: Workflow identifier
            namespace: Kubernetes namespace
        
        Returns:
            Dictionary with status information:
            {
                "status": str,
                "current_stage": str | None,
                "start_time": datetime | None,
                "end_time": datetime | None,
                "retry_count": int,
                "stages": list
            }
        """
        pass
    
    @abstractmethod
    def cancel_workflow(
        self,
        workflow_id: str,
        namespace: str,
    ) -> None:
        """Cancel a running workflow.
        
        Args:
            workflow_id: Workflow identifier
            namespace: Kubernetes namespace
        """
        pass
    
    @abstractmethod
    def delete_workflow(
        self,
        workflow_id: str,
        namespace: str,
    ) -> None:
        """Delete a workflow.
        
        Args:
            workflow_id: Workflow identifier
            namespace: Kubernetes namespace
        """
        pass
    
    @abstractmethod
    def retry_workflow(
        self,
        workflow_id: str,
        namespace: str,
    ) -> Dict[str, Any]:
        """Retry a failed workflow.
        
        Args:
            workflow_id: Workflow identifier
            namespace: Kubernetes namespace
        
        Returns:
            Updated workflow information
        """
        pass
    
    @abstractmethod
    def get_workflow_logs(
        self,
        workflow_id: str,
        namespace: str,
        stage_name: Optional[str] = None,
    ) -> str:
        """Get workflow logs.
        
        Args:
            workflow_id: Workflow identifier
            namespace: Kubernetes namespace
            stage_name: Optional stage name to filter logs
        
        Returns:
            Log output as string
        """
        pass

