"""Scheduled worker for aggregating costs from training jobs and serving endpoints."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.src.core.database import get_session
from backend.src.catalog import models as catalog_models
from backend.src.governance.services.cost import CostService

logger = logging.getLogger(__name__)

# Cost rates (in USD)
GPU_HOUR_RATE = {
    "nvidia-tesla-v100": 2.50,
    "nvidia-tesla-a100": 4.00,
    "nvidia-rtx-3090": 1.00,
    "default": 2.00,
}
TOKEN_COST_PER_1K = 0.002  # $0.002 per 1K tokens


class CostAggregator:
    """Worker that aggregates costs from training jobs and serving endpoints."""

    def __init__(self, session: Session):
        self.cost_service = CostService(session)
        self.session = session

    def aggregate_training_costs(self, time_window: str) -> None:
        """Aggregate costs from completed training jobs."""
        # Get completed training jobs in the time window
        cutoff_date = datetime.utcnow() - timedelta(days=1)
        jobs = (
            self.session.query(catalog_models.TrainingJob)
            .filter(
                catalog_models.TrainingJob.status.in_(["succeeded", "failed"]),
                catalog_models.TrainingJob.completed_at >= cutoff_date,
            )
            .all()
        )

        for job in jobs:
            try:
                resource_profile = job.resource_profile or {}
                gpu_count = resource_profile.get("gpuCount", 1)
                gpu_type = resource_profile.get("gpuType", "default")
                max_duration = resource_profile.get("maxDuration", 60)  # minutes

                # Calculate GPU hours (approximate, based on max duration)
                gpu_hours = (gpu_count * max_duration) / 60.0

                # Calculate cost
                gpu_rate = GPU_HOUR_RATE.get(gpu_type, GPU_HOUR_RATE["default"])
                cost_amount = gpu_hours * gpu_rate

                # Create or update cost profile
                self.cost_service.create_cost_profile(
                    resource_type="training_job",
                    resource_id=str(job.id),
                    time_window=time_window,
                    gpu_hours=gpu_hours,
                    cost_amount=cost_amount,
                )

                logger.info(
                    f"Aggregated cost for training job {job.id}: "
                    f"{gpu_hours:.2f} GPU hours, ${cost_amount:.2f}"
                )
            except Exception as e:
                logger.error(f"Failed to aggregate cost for training job {job.id}: {e}")

    def aggregate_serving_costs(self, time_window: str) -> None:
        """Aggregate costs from serving endpoints (token-based)."""
        # Get active serving endpoints
        endpoints = (
            self.session.query(catalog_models.ServingEndpoint)
            .filter(catalog_models.ServingEndpoint.status == "healthy")
            .all()
        )

        for endpoint in endpoints:
            try:
                # Get observability snapshots for token count
                snapshots = (
                    self.session.query(catalog_models.ObservabilitySnapshot)
                    .filter(
                        catalog_models.ObservabilitySnapshot.serving_endpoint_id == endpoint.id,
                        catalog_models.ObservabilitySnapshot.time_bucket
                        >= datetime.utcnow() - timedelta(days=1),
                    )
                    .all()
                )

                total_tokens = 0
                for snapshot in snapshots:
                    if snapshot.token_per_request:
                        # Estimate total tokens (simplified)
                        total_tokens += int(snapshot.token_per_request * 100)  # Assume 100 requests per snapshot

                # Calculate cost
                cost_amount = (total_tokens / 1000) * TOKEN_COST_PER_1K

                if total_tokens > 0:
                    self.cost_service.create_cost_profile(
                        resource_type="serving_endpoint",
                        resource_id=str(endpoint.id),
                        time_window=time_window,
                        token_count=total_tokens,
                        cost_amount=cost_amount,
                    )

                    logger.info(
                        f"Aggregated cost for serving endpoint {endpoint.id}: "
                        f"{total_tokens} tokens, ${cost_amount:.2f}"
                    )
            except Exception as e:
                logger.error(f"Failed to aggregate cost for serving endpoint {endpoint.id}: {e}")

    def run_aggregation(self, interval_hours: int = 24) -> None:
        """Continuously run cost aggregation."""
        logger.info("Starting cost aggregation worker")
        while True:
            try:
                time_window = datetime.utcnow().strftime("%Y-%m-%d")
                logger.info(f"Running cost aggregation for time window: {time_window}")

                self.aggregate_training_costs(time_window)
                self.aggregate_serving_costs(time_window)

                logger.info(f"Cost aggregation completed for {time_window}")
                time.sleep(interval_hours * 3600)  # Sleep for interval_hours
            except KeyboardInterrupt:
                logger.info("Cost aggregation worker stopped")
                break
            except Exception as e:
                logger.error(f"Error in cost aggregation worker: {e}")
                time.sleep(3600)  # Sleep 1 hour on error


if __name__ == "__main__":
    # Standalone worker entry point
    session = next(get_session())
    aggregator = CostAggregator(session)
    aggregator.run_aggregation()

