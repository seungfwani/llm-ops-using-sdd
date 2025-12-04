"""Experiment tracking adapter interface.

Defines the interface for experiment tracking system adapters (MLflow, W&B, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID

from integrations.base_adapter import BaseAdapter


class ExperimentTrackingAdapter(BaseAdapter):
    """Interface for experiment tracking system adapters."""
    
    @abstractmethod
    def create_run(
        self,
        experiment_name: str,
        run_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Create a new experiment run.
        
        Args:
            experiment_name: Name of the experiment
            run_name: Optional name/tag for the run
            parameters: Hyperparameters and configuration
            tags: Additional metadata tags
        
        Returns:
            Dictionary with run information:
            {
                "run_id": str,
                "experiment_id": str,
                "status": str
            }
        """
        pass
    
    @abstractmethod
    def log_metrics(
        self,
        run_id: str,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log metrics for a run.
        
        Args:
            run_id: Run identifier
            metrics: Dictionary of metric names to values
            step: Optional step number for time-series metrics
        """
        pass
    
    @abstractmethod
    def log_parameters(
        self,
        run_id: str,
        parameters: Dict[str, Any],
    ) -> None:
        """Log parameters for a run.
        
        Args:
            run_id: Run identifier
            parameters: Dictionary of parameter names to values
        """
        pass
    
    @abstractmethod
    def log_artifacts(
        self,
        run_id: str,
        artifact_path: str,
        artifact_uri: str,
    ) -> None:
        """Log artifact URI for a run.
        
        Args:
            run_id: Run identifier
            artifact_path: Logical path/name for the artifact
            artifact_uri: Storage URI of the artifact
        """
        pass
    
    @abstractmethod
    def update_run_status(
        self,
        run_id: str,
        status: str,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Update run status.
        
        Args:
            run_id: Run identifier
            status: New status ("running", "completed", "failed", "killed")
            end_time: Optional end time for completed/failed runs
        """
        pass
    
    @abstractmethod
    def get_run(self, run_id: str) -> Dict[str, Any]:
        """Get run information.
        
        Args:
            run_id: Run identifier
        
        Returns:
            Dictionary with run details:
            {
                "run_id": str,
                "experiment_id": str,
                "status": str,
                "parameters": dict,
                "metrics": dict,
                "artifact_uris": list,
                "start_time": datetime,
                "end_time": datetime | None
            }
        """
        pass
    
    @abstractmethod
    def search_runs(
        self,
        experiment_name: Optional[str] = None,
        filter_string: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for experiment runs.
        
        Args:
            experiment_name: Optional experiment name filter
            filter_string: Optional filter expression (tool-specific syntax)
            max_results: Maximum number of results to return
        
        Returns:
            List of run dictionaries
        """
        pass

