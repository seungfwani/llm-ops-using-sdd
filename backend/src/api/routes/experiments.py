"""Experiments API routes."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_session
from services.experiment_tracking_service import ExperimentTrackingService
from training import schemas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-ops/v1/experiments", tags=["experiments"])


def get_experiment_tracking_service(session: Session = Depends(get_session)) -> ExperimentTrackingService:
    """Dependency to get experiment tracking service."""
    return ExperimentTrackingService(session)


@router.post("/search", response_model=schemas.EnvelopeExperimentSearch)
def search_experiments(
    request: schemas.SearchExperimentsRequest,
    experiment_service: ExperimentTrackingService = Depends(get_experiment_tracking_service),
) -> schemas.EnvelopeExperimentSearch:
    """Search experiments in the tracking system."""
    try:
        experiments = experiment_service.search_experiments(
            experiment_name=request.experimentName,
            filter_string=request.filterString,
            max_results=request.maxResults,
        )
        
        experiment_responses = [
            schemas.ExperimentRunResponse(
                id=exp.get("run_id", ""),
                trainingJobId=exp.get("training_job_id", ""),
                trackingSystem=exp.get("tracking_system", "mlflow"),
                trackingRunId=exp.get("run_id", ""),
                experimentName=exp.get("experiment_name", ""),
                runName=exp.get("run_name"),
                parameters=exp.get("parameters"),
                metrics=exp.get("metrics"),
                artifactUris=exp.get("artifact_uris"),
                status=exp.get("status", "running"),
                startTime=exp.get("start_time"),
                endTime=exp.get("end_time"),
                createdAt=exp.get("start_time"),
                updatedAt=exp.get("end_time") or exp.get("start_time"),
            )
            for exp in experiments
        ]
        
        return schemas.EnvelopeExperimentSearch(
            status="success",
            message="Experiments retrieved successfully",
            data=schemas.ExperimentSearchResponse(
                experiments=experiment_responses,
                total=len(experiment_responses),
            ),
        )
    except Exception as e:
        logger.error(f"Failed to search experiments: {e}", exc_info=True)
        return schemas.EnvelopeExperimentSearch(
            status="fail",
            message=f"Failed to search experiments: {str(e)}",
            data=None,
        )

