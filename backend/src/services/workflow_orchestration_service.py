"""Workflow orchestration service.

Manages workflow pipelines and integrates with open-source orchestration systems.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from catalog.models import WorkflowPipeline
from services.integration_config import IntegrationConfigService
from integrations.orchestration.interface import OrchestrationAdapter
from integrations.orchestration.argo_adapter import ArgoWorkflowsAdapter
from integrations.orchestration.pipeline_parser import PipelineParser, PipelineParseError
from integrations.orchestration.argo_workflow_builder import ArgoWorkflowBuilder
from integrations.error_handler import ToolUnavailableError
from core.settings import get_settings

logger = logging.getLogger(__name__)


class WorkflowOrchestrationService:
    """Service for managing workflow orchestration."""
    
    def __init__(self, db: Session):
        """Initialize service with database session.
        
        Args:
            db: Database session
        """
        self.db = db
        self.config_service = IntegrationConfigService(db)
        self.parser = PipelineParser()
        self.builder = ArgoWorkflowBuilder()
        self.settings = get_settings()
        self._adapter: Optional[OrchestrationAdapter] = None
    
    def _get_adapter(self) -> Optional[OrchestrationAdapter]:
        """Get or create orchestration adapter.
        
        Returns:
            Orchestration adapter or None if not available
        """
        if self._adapter is None:
            config = self.config_service.get_config(
                integration_type="orchestration",
                tool_name="argo_workflows",
            )
            if config and config.get("enabled"):
                try:
                    adapter_config = {
                        "namespace": config.get("config", {}).get("namespace", self.settings.argo_workflows_namespace),
                        "controller_service": config.get("config", {}).get("controller_service", self.settings.argo_workflows_controller_service),
                        "enabled": config["enabled"],
                    }
                    self._adapter = ArgoWorkflowsAdapter(adapter_config)
                except Exception as e:
                    logger.warning(f"Failed to initialize Argo Workflows adapter: {e}")
                    return None
        return self._adapter
    
    def create_pipeline(
        self,
        pipeline_name: str,
        stages: List[Dict[str, Any]],
        orchestration_system: Optional[str] = None,
        namespace: Optional[str] = None,
        max_retries: Optional[int] = None,
    ) -> WorkflowPipeline:
        """Create a workflow pipeline.
        
        Args:
            pipeline_name: User-defined pipeline name
            stages: List of stage definitions
            orchestration_system: Orchestration system identifier (default: "argo_workflows")
            namespace: Kubernetes namespace (default: from settings)
            max_retries: Maximum retry attempts (default: 3)
        
        Returns:
            Created WorkflowPipeline entity
        
        Raises:
            PipelineParseError: If pipeline definition is invalid
            ValueError: If orchestration system is not available
        """
        # Parse and validate pipeline definition
        parsed = self.parser.parse_pipeline_definition(
            pipeline_name=pipeline_name,
            stages=stages,
            orchestration_system=orchestration_system,
            max_retries=max_retries,
        )
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled():
            logger.warning("Workflow orchestration is disabled - creating pipeline record without Argo Workflows")
            # Create pipeline record without orchestration integration
            pipeline = WorkflowPipeline(
                id=uuid4(),
                pipeline_name=pipeline_name,
                orchestration_system=parsed["orchestration_system"],
                workflow_id="",
                workflow_namespace=namespace or self.settings.argo_workflows_namespace,
                pipeline_definition=parsed["pipeline_definition"],
                stages=parsed["stages"],
                status="pending",
                retry_count=0,
                max_retries=parsed["max_retries"],
            )
            self.db.add(pipeline)
            self.db.commit()
            self.db.refresh(pipeline)
            return pipeline
        
        # Build workflow manifest
        pipeline_id = uuid4()
        workflow_namespace = namespace or self.settings.argo_workflows_namespace
        
        workflow_manifest = self.builder.build_workflow_manifest(
            pipeline_id=pipeline_id,
            pipeline_name=pipeline_name,
            stages=parsed["stages"],
            namespace=workflow_namespace,
            max_retries=parsed["max_retries"],
        )
        
        # Create workflow via adapter
        try:
            workflow_info = adapter.create_workflow(
                pipeline_id=pipeline_id,
                pipeline_name=pipeline_name,
                pipeline_definition=workflow_manifest["spec"],
                namespace=workflow_namespace,
                max_retries=parsed["max_retries"],
            )
        except ToolUnavailableError:
            logger.warning("Argo Workflows is unavailable - creating pipeline record without workflow")
            workflow_info = {
                "workflow_id": "",
                "workflow_namespace": workflow_namespace,
                "status": "pending",
            }
        except Exception as e:
            logger.error(f"Failed to create workflow: {e}")
            raise ValueError(f"Failed to create workflow: {e}")
        
        # Create pipeline record
        pipeline = WorkflowPipeline(
            id=pipeline_id,
            pipeline_name=pipeline_name,
            orchestration_system=parsed["orchestration_system"],
            workflow_id=workflow_info["workflow_id"],
            workflow_namespace=workflow_info["workflow_namespace"],
            pipeline_definition=parsed["pipeline_definition"],
            stages=parsed["stages"],
            status=self._map_workflow_status(workflow_info.get("status", "Pending")),
            retry_count=0,
            max_retries=parsed["max_retries"],
        )
        
        self.db.add(pipeline)
        self.db.commit()
        self.db.refresh(pipeline)
        
        return pipeline
    
    def get_pipeline(self, pipeline_id: UUID) -> Optional[WorkflowPipeline]:
        """Get pipeline by ID.
        
        Args:
            pipeline_id: Pipeline ID
        
        Returns:
            WorkflowPipeline entity or None if not found
        """
        return self.db.get(WorkflowPipeline, pipeline_id)
    
    def update_pipeline_status(
        self,
        pipeline_id: UUID,
    ) -> Optional[WorkflowPipeline]:
        """Update pipeline status from orchestration system.
        
        Args:
            pipeline_id: Pipeline ID
        
        Returns:
            Updated WorkflowPipeline entity or None if not found
        """
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            return None
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled() or not pipeline.workflow_id:
            return pipeline
        
        try:
            # Get status from orchestration system
            status_info = adapter.get_workflow_status(
                workflow_id=pipeline.workflow_id,
                namespace=pipeline.workflow_namespace,
            )
            
            # Update pipeline
            pipeline.status = status_info["status"]
            pipeline.current_stage = status_info.get("current_stage")
            pipeline.retry_count = status_info.get("retry_count", 0)
            
            if status_info.get("start_time"):
                pipeline.start_time = status_info["start_time"]
            if status_info.get("end_time"):
                pipeline.end_time = status_info["end_time"]
            
            # Update stages metadata if available
            if status_info.get("stages"):
                # Merge stage statuses into stages metadata
                stages_dict = {s["name"]: s for s in (pipeline.stages or [])}
                for stage_status in status_info["stages"]:
                    stage_name = stage_status.get("name")
                    if stage_name in stages_dict:
                        stages_dict[stage_name].update({
                            "phase": stage_status.get("phase"),
                            "started_at": stage_status.get("started_at"),
                            "finished_at": stage_status.get("finished_at"),
                        })
                pipeline.stages = list(stages_dict.values())
            
            self.db.commit()
            self.db.refresh(pipeline)
        except Exception as e:
            logger.error(f"Failed to update pipeline status: {e}")
        
        return pipeline
    
    def cancel_pipeline(self, pipeline_id: UUID) -> Optional[WorkflowPipeline]:
        """Cancel a running pipeline.
        
        Args:
            pipeline_id: Pipeline ID
        
        Returns:
            Updated WorkflowPipeline entity or None if not found
        """
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            return None
        
        # Get adapter
        adapter = self._get_adapter()
        if adapter and adapter.is_enabled() and pipeline.workflow_id:
            try:
                adapter.cancel_workflow(
                    workflow_id=pipeline.workflow_id,
                    namespace=pipeline.workflow_namespace,
                )
            except Exception as e:
                logger.error(f"Failed to cancel workflow: {e}")
        
        # Update pipeline status
        pipeline.status = "cancelled"
        if not pipeline.end_time:
            pipeline.end_time = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(pipeline)
        
        return pipeline
    
    def delete_pipeline(self, pipeline_id: UUID) -> bool:
        """Delete a pipeline.
        
        Args:
            pipeline_id: Pipeline ID
        
        Returns:
            True if deleted, False if not found
        """
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            return False
        
        # Get adapter
        adapter = self._get_adapter()
        if adapter and adapter.is_enabled() and pipeline.workflow_id:
            try:
                adapter.delete_workflow(
                    workflow_id=pipeline.workflow_id,
                    namespace=pipeline.workflow_namespace,
                )
            except Exception as e:
                logger.warning(f"Failed to delete workflow: {e}")
        
        # Delete pipeline record
        self.db.delete(pipeline)
        self.db.commit()
        
        return True
    
    def retry_pipeline(self, pipeline_id: UUID) -> Optional[WorkflowPipeline]:
        """Retry a failed pipeline.
        
        Args:
            pipeline_id: Pipeline ID
        
        Returns:
            New WorkflowPipeline entity for retry or None if not found
        """
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            return None
        
        # Check if retry is allowed
        if pipeline.retry_count >= pipeline.max_retries:
            raise ValueError(f"Maximum retries ({pipeline.max_retries}) exceeded")
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled() or not pipeline.workflow_id:
            raise ValueError("Orchestration system is not available for retry")
        
        try:
            # Retry workflow
            retry_info = adapter.retry_workflow(
                workflow_id=pipeline.workflow_id,
                namespace=pipeline.workflow_namespace,
            )
            
            # Create new pipeline record for retry
            retry_pipeline = WorkflowPipeline(
                id=uuid4(),
                pipeline_name=f"{pipeline.pipeline_name} (retry)",
                orchestration_system=pipeline.orchestration_system,
                workflow_id=retry_info["workflow_id"],
                workflow_namespace=retry_info["workflow_namespace"],
                pipeline_definition=pipeline.pipeline_definition,
                stages=pipeline.stages,
                status=self._map_workflow_status(retry_info.get("status", "Pending")),
                retry_count=pipeline.retry_count + 1,
                max_retries=pipeline.max_retries,
            )
            
            self.db.add(retry_pipeline)
            self.db.commit()
            self.db.refresh(retry_pipeline)
            
            return retry_pipeline
        except Exception as e:
            logger.error(f"Failed to retry pipeline: {e}")
            raise ValueError(f"Failed to retry pipeline: {e}")
    
    def list_pipelines(
        self,
        status: Optional[str] = None,
        orchestration_system: Optional[str] = None,
    ) -> List[WorkflowPipeline]:
        """List pipelines with optional filters.
        
        Args:
            status: Optional status filter
            orchestration_system: Optional orchestration system filter
        
        Returns:
            List of WorkflowPipeline entities
        """
        query = self.db.query(WorkflowPipeline)
        
        if status:
            query = query.filter(WorkflowPipeline.status == status)
        
        if orchestration_system:
            query = query.filter(WorkflowPipeline.orchestration_system == orchestration_system)
        
        return query.order_by(WorkflowPipeline.created_at.desc()).all()
    
    def get_pipeline_logs(
        self,
        pipeline_id: UUID,
        stage_name: Optional[str] = None,
    ) -> Optional[str]:
        """Get pipeline logs.
        
        Args:
            pipeline_id: Pipeline ID
            stage_name: Optional stage name to filter logs
        
        Returns:
            Log output as string or None if not available
        """
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            return None
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled() or not pipeline.workflow_id:
            return None
        
        try:
            return adapter.get_workflow_logs(
                workflow_id=pipeline.workflow_id,
                namespace=pipeline.workflow_namespace,
                stage_name=stage_name,
            )
        except Exception as e:
            logger.error(f"Failed to get pipeline logs: {e}")
            return None
    
    def _map_workflow_status(self, workflow_status: str) -> str:
        """Map orchestration system status to platform status.
        
        Args:
            workflow_status: Status from orchestration system
        
        Returns:
            Platform status string
        """
        status_mapping = {
            "Pending": "pending",
            "Running": "running",
            "Succeeded": "succeeded",
            "Failed": "failed",
            "Error": "failed",
            "Unknown": "pending",
        }
        return status_mapping.get(workflow_status, "pending")

