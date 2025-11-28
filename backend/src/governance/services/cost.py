"""Cost aggregation and analysis service."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from governance.repositories import CostProfileRepository

logger = logging.getLogger(__name__)


class CostService:
    """Service for aggregating and analyzing costs."""

    def __init__(self, session: Session):
        self.cost_repo = CostProfileRepository(session)
        self.session = session

    def create_cost_profile(
        self,
        resource_type: str,
        resource_id: str,
        time_window: str,
        gpu_hours: Optional[float] = None,
        token_count: Optional[int] = None,
        cost_amount: Optional[float] = None,
        cost_currency: str = "USD",
    ) -> catalog_models.CostProfile:
        """
        Create a cost profile for a resource.

        Args:
            resource_type: Type of resource (training_job, serving_endpoint, etc.)
            resource_id: Resource ID
            time_window: Time window (e.g., "2025-11-27", "2025-11")
            gpu_hours: GPU hours consumed
            token_count: Token count
            cost_amount: Total cost amount
            cost_currency: Currency code

        Returns:
            Created CostProfile entity
        """
        profile = catalog_models.CostProfile(
            id=uuid4(),
            resource_type=resource_type,
            resource_id=resource_id,
            time_window=time_window,
            gpu_hours=gpu_hours,
            token_count=token_count,
            cost_amount=cost_amount,
            cost_currency=cost_currency,
            created_at=datetime.utcnow(),
        )
        return self.cost_repo.create(profile)

    def list_cost_profiles(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        time_window: Optional[str] = None,
    ) -> list[catalog_models.CostProfile]:
        """List cost profiles with optional filters."""
        return list(self.cost_repo.list(resource_type=resource_type, resource_id=resource_id, time_window=time_window))

    def aggregate_costs(
        self,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """
        Aggregate costs across resources.

        Args:
            resource_type: Optional resource type filter
            start_date: Start date for aggregation
            end_date: End date for aggregation

        Returns:
            Aggregated cost summary
        """
        profiles = self.cost_repo.list(resource_type=resource_type)

        total_gpu_hours = 0.0
        total_tokens = 0
        total_cost = 0.0

        for profile in profiles:
            # Filter by date if provided
            if start_date and profile.created_at < start_date:
                continue
            if end_date and profile.created_at > end_date:
                continue

            if profile.gpu_hours:
                total_gpu_hours += profile.gpu_hours
            if profile.token_count:
                total_tokens += profile.token_count
            if profile.cost_amount:
                total_cost += profile.cost_amount

        return {
            "total_gpu_hours": total_gpu_hours,
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "currency": "USD",
            "resource_count": len(profiles),
        }

