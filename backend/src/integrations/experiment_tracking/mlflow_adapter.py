"""MLflow adapter implementation for experiment tracking.

Implements the ExperimentTrackingAdapter interface using MLflow.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from integrations.experiment_tracking.interface import ExperimentTrackingAdapter
from integrations.experiment_tracking.mlflow_client import MLflowClient
from integrations.error_handler import (
    handle_tool_errors,
    wrap_tool_error,
    ToolUnavailableError,
    ToolOperationError,
)

logger = logging.getLogger(__name__)


class MLflowAdapter(ExperimentTrackingAdapter):
    """MLflow adapter for experiment tracking."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize MLflow adapter.
        
        Args:
            config: Configuration dictionary with:
                - tracking_uri: MLflow Tracking Server URI
                - enabled: Whether adapter is enabled
        """
        super().__init__(config)
        self.tracking_uri = config.get("tracking_uri")
        if not self.tracking_uri:
            raise ValueError("MLflow tracking_uri is required")
        
        self._client: Optional[MLflowClient] = None
    
    def _get_client(self) -> MLflowClient:
        """Get or create MLflow client."""
        if self._client is None:
            self._client = MLflowClient(self.tracking_uri)
        return self._client
    
    def is_available(self) -> bool:
        """Check if MLflow service is available."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop is running, we can't use async here
                # Return True optimistically
                return True
            else:
                health = loop.run_until_complete(self._get_client().health_check())
                return health["status"] == "healthy"
        except Exception as e:
            logger.warning(f"MLflow availability check failed: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on MLflow service."""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop is running, return optimistic status
                return {
                    "status": "healthy",
                    "message": "MLflow adapter initialized",
                    "details": {},
                }
            else:
                return loop.run_until_complete(self._get_client().health_check())
        except Exception as e:
            return {
                "status": "unavailable",
                "message": f"MLflow health check failed: {str(e)}",
                "details": {"error": str(e)},
            }
    
    @handle_tool_errors("MLflow", "Failed to create experiment run")
    def create_run(
        self,
        experiment_name: str,
        run_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a new experiment run."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="MLflow integration is disabled",
                tool_name="mlflow",
            )
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # For async context, we need to handle differently
                # This is a limitation - in production, use async adapter methods
                raise RuntimeError("MLflow adapter requires async context")
            
            # Create run
            result = loop.run_until_complete(
                self._get_client().create_run(
                    experiment_id=experiment_name,
                    run_name=run_name,
                    tags=tags or {},
                )
            )
            
            # Log parameters if provided
            if parameters:
                loop.run_until_complete(
                    self._get_client().log_params(result["run_id"], parameters)
                )
            
            return result
        except Exception as e:
            raise wrap_tool_error(e, "mlflow", "create_run")
    
    @handle_tool_errors("MLflow", "Failed to log metrics")
    def log_metrics(
        self,
        run_id: str,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log metrics for a run."""
        if not self.is_enabled():
            return  # Graceful degradation - silently skip if disabled
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning("MLflow log_metrics called from async context - skipping")
                return
            
            loop.run_until_complete(
                self._get_client().log_metrics(run_id, metrics, step)
            )
        except Exception as e:
            logger.warning(f"Failed to log metrics to MLflow: {e}")
            # Graceful degradation - don't raise, just log warning
    
    @handle_tool_errors("MLflow", "Failed to log parameters")
    def log_parameters(
        self,
        run_id: str,
        parameters: Dict[str, Any],
    ) -> None:
        """Log parameters for a run."""
        if not self.is_enabled():
            return  # Graceful degradation
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning("MLflow log_parameters called from async context - skipping")
                return
            
            loop.run_until_complete(
                self._get_client().log_params(run_id, parameters)
            )
        except Exception as e:
            logger.warning(f"Failed to log parameters to MLflow: {e}")
            # Graceful degradation
    
    @handle_tool_errors("MLflow", "Failed to log artifacts")
    def log_artifacts(
        self,
        run_id: str,
        artifact_path: str,
        artifact_uri: str,
    ) -> None:
        """Log artifact URI for a run."""
        if not self.is_enabled():
            return  # Graceful degradation
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning("MLflow log_artifacts called from async context - skipping")
                return
            
            loop.run_until_complete(
                self._get_client().log_artifact_uri(run_id, artifact_path, artifact_uri)
            )
        except Exception as e:
            logger.warning(f"Failed to log artifacts to MLflow: {e}")
            # Graceful degradation
    
    @handle_tool_errors("MLflow", "Failed to update run status")
    def update_run_status(
        self,
        run_id: str,
        status: str,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Update run status."""
        if not self.is_enabled():
            return  # Graceful degradation
        
        # Map platform status to MLflow status
        mlflow_status_map = {
            "running": "RUNNING",
            "completed": "FINISHED",
            "failed": "FAILED",
            "killed": "KILLED",
        }
        mlflow_status = mlflow_status_map.get(status.lower(), "RUNNING")
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.warning("MLflow update_run_status called from async context - skipping")
                return
            
            loop.run_until_complete(
                self._get_client().update_run_status(run_id, mlflow_status, end_time)
            )
        except Exception as e:
            logger.warning(f"Failed to update run status in MLflow: {e}")
            # Graceful degradation
    
    @handle_tool_errors("MLflow", "Failed to get run")
    def get_run(self, run_id: str) -> Dict[str, Any]:
        """Get run information."""
        if not self.is_enabled():
            raise ToolUnavailableError(
                message="MLflow integration is disabled",
                tool_name="mlflow",
            )
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError("MLflow adapter requires async context")
            
            return loop.run_until_complete(self._get_client().get_run(run_id))
        except Exception as e:
            raise wrap_tool_error(e, "mlflow", "get_run")
    
    @handle_tool_errors("MLflow", "Failed to search runs")
    def search_runs(
        self,
        experiment_name: Optional[str] = None,
        filter_string: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for experiment runs."""
        if not self.is_enabled():
            return []  # Graceful degradation - return empty list
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                raise RuntimeError("MLflow adapter requires async context")
            
            # Convert experiment name to ID if needed
            experiment_ids = None
            if experiment_name:
                # This is simplified - in production, resolve experiment name to ID
                experiment_ids = [experiment_name]
            
            return loop.run_until_complete(
                self._get_client().search_runs(
                    experiment_ids=experiment_ids,
                    filter_string=filter_string,
                    max_results=max_results,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to search runs in MLflow: {e}")
            return []  # Graceful degradation

