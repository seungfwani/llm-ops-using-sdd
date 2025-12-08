"""Experiment tracking service.

Manages experiment runs and integrates with open-source tracking systems.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from catalog.models import ExperimentRun, TrainingJob
from services.integration_config import IntegrationConfigService
from integrations.experiment_tracking.mlflow_adapter import MLflowAdapter
from integrations.error_handler import ToolUnavailableError

logger = logging.getLogger(__name__)


class ExperimentTrackingService:
    """Service for managing experiment tracking."""
    
    def __init__(self, db: Session):
        """Initialize service with database session.
        
        Args:
            db: Database session
        """
        self.db = db
        self.config_service = IntegrationConfigService(db)
        self._adapter: Optional[MLflowAdapter] = None
    
    def _get_adapter(self) -> Optional[MLflowAdapter]:
        """Get or create experiment tracking adapter."""
        if self._adapter is None:
            config = self.config_service.get_config(
                integration_type="experiment_tracking",
                tool_name="mlflow",
            )
            if config and config.get("enabled"):
                try:
                    self._adapter = MLflowAdapter(config.get("config", {}))
                except Exception as e:
                    logger.warning(f"Failed to initialize MLflow adapter: {e}")
                    return None
        return self._adapter
    
    def create_experiment_run(
        self,
        training_job_id: UUID,
        experiment_name: Optional[str] = None,
        run_name: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> ExperimentRun:
        """Create an experiment run for a training job.
        
        Args:
            training_job_id: Training job ID
            experiment_name: Optional experiment name (defaults to model name)
            run_name: Optional run name
            parameters: Optional parameters to log
        
        Returns:
            Created ExperimentRun entity
        """
        # Get training job
        training_job = self.db.get(TrainingJob, training_job_id)
        if not training_job:
            raise ValueError(f"Training job {training_job_id} not found")
        
        # Check if run already exists
        existing_run = self.db.query(ExperimentRun).filter(
            ExperimentRun.training_job_id == training_job_id
        ).first()
        if existing_run:
            logger.info(f"Experiment run already exists for training job {training_job_id}")
            return existing_run
        
        # Get adapter
        adapter = self._get_adapter()
        if not adapter or not adapter.is_enabled():
            logger.warning("Experiment tracking is disabled - creating run record without MLflow")
            # Create run record without MLflow integration
            experiment_run = ExperimentRun(
                id=uuid4(),
                training_job_id=training_job_id,
                tracking_system="none",
                tracking_run_id=str(uuid4()),
                experiment_name=experiment_name or f"experiment-{training_job_id}",
                run_name=run_name,
                parameters=parameters,
                status="running",
                start_time=datetime.utcnow(),
            )
            self.db.add(experiment_run)
            self.db.commit()
            self.db.refresh(experiment_run)
            return experiment_run
        
        # Create run in MLflow
        try:
            if not experiment_name:
                # Use model name as experiment name
                model_entry = training_job.model_entry
                experiment_name = f"{model_entry.name}-{model_entry.version}"
            
            mlflow_result = adapter.create_run(
                experiment_name=experiment_name,
                run_name=run_name or f"run-{training_job_id}",
                parameters=parameters,
                tags={
                    "training_job_id": str(training_job_id),
                    "job_type": training_job.job_type,
                    "submitted_by": training_job.submitted_by,
                },
            )
            
            # Create run record
            experiment_run = ExperimentRun(
                id=uuid4(),
                training_job_id=training_job_id,
                tracking_system="mlflow",
                tracking_run_id=mlflow_result["run_id"],
                experiment_name=experiment_name,
                run_name=run_name,
                parameters=parameters,
                status="running",
                start_time=datetime.utcnow(),
            )
            self.db.add(experiment_run)
            self.db.commit()
            self.db.refresh(experiment_run)
            
            logger.info(f"Created experiment run {experiment_run.id} for training job {training_job_id}")
            return experiment_run
        
        except Exception as e:
            logger.error(f"Failed to create MLflow run: {e}")
            # Graceful degradation - create run record without MLflow
            experiment_run = ExperimentRun(
                id=uuid4(),
                training_job_id=training_job_id,
                tracking_system="none",
                tracking_run_id=str(uuid4()),
                experiment_name=experiment_name or f"experiment-{training_job_id}",
                run_name=run_name,
                parameters=parameters,
                status="running",
                start_time=datetime.utcnow(),
            )
            self.db.add(experiment_run)
            self.db.commit()
            self.db.refresh(experiment_run)
            return experiment_run
    
    def log_metrics(
        self,
        training_job_id: UUID,
        metrics: Dict[str, float],
        step: Optional[int] = None,
    ) -> None:
        """Log metrics for a training job's experiment run.
        
        Args:
            training_job_id: Training job ID
            metrics: Dictionary of metric names to values
            step: Optional step number
        """
        # Get experiment run
        experiment_run = self.db.query(ExperimentRun).filter(
            ExperimentRun.training_job_id == training_job_id
        ).first()
        
        if not experiment_run:
            logger.warning(f"No experiment run found for training job {training_job_id}")
            return
        
        # Update metrics in database
        if experiment_run.metrics:
            experiment_run.metrics.update(metrics)
        else:
            experiment_run.metrics = metrics
        self.db.commit()
        
        # Log to MLflow if enabled
        adapter = self._get_adapter()
        if adapter and adapter.is_enabled() and experiment_run.tracking_system == "mlflow":
            try:
                adapter.log_metrics(
                    run_id=experiment_run.tracking_run_id,
                    metrics=metrics,
                    step=step,
                )
            except Exception as e:
                logger.warning(f"Failed to log metrics to MLflow: {e}")
                # Graceful degradation - continue without MLflow
    
    def update_run_status(
        self,
        training_job_id: UUID,
        status: str,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Update experiment run status.
        
        Args:
            training_job_id: Training job ID
            status: New status ("running", "completed", "failed", "killed")
            end_time: Optional end time
        """
        # Get experiment run
        experiment_run = self.db.query(ExperimentRun).filter(
            ExperimentRun.training_job_id == training_job_id
        ).first()
        
        if not experiment_run:
            logger.warning(f"No experiment run found for training job {training_job_id}")
            return
        
        # Update status in database
        experiment_run.status = status
        if end_time:
            experiment_run.end_time = end_time
        self.db.commit()
        
        # Update in MLflow if enabled
        adapter = self._get_adapter()
        if adapter and adapter.is_enabled() and experiment_run.tracking_system == "mlflow":
            try:
                adapter.update_run_status(
                    run_id=experiment_run.tracking_run_id,
                    status=status,
                    end_time=end_time,
                )
            except Exception as e:
                logger.warning(f"Failed to update run status in MLflow: {e}")
                # Graceful degradation
    
    def get_experiment_run(self, training_job_id: UUID) -> Optional[ExperimentRun]:
        """Get experiment run for a training job.
        
        Args:
            training_job_id: Training job ID
        
        Returns:
            ExperimentRun entity or None
        """
        return self.db.query(ExperimentRun).filter(
            ExperimentRun.training_job_id == training_job_id
        ).first()
    
    def search_experiments(
        self,
        experiment_name: Optional[str] = None,
        filter_string: Optional[str] = None,
        max_results: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search for experiment runs.
        
        Args:
            experiment_name: Optional experiment name filter
            filter_string: Optional filter expression
            max_results: Maximum number of results
        
        Returns:
            List of experiment run dictionaries
        """
        adapter = self._get_adapter()
        if adapter and adapter.is_enabled():
            try:
                return adapter.search_runs(
                    experiment_name=experiment_name,
                    filter_string=filter_string,
                    max_results=max_results,
                )
            except Exception as e:
                logger.warning(f"Failed to search experiments in MLflow: {e}")
        
        # Fallback to database search
        query = self.db.query(ExperimentRun)
        if experiment_name:
            query = query.filter(ExperimentRun.experiment_name == experiment_name)
        
        runs = query.limit(max_results).all()
        return [
            {
                "run_id": str(run.id),
                "experiment_name": run.experiment_name,
                "status": run.status,
                "parameters": run.parameters or {},
                "metrics": run.metrics or {},
                "start_time": run.start_time,
                "end_time": run.end_time,
            }
            for run in runs
        ]

