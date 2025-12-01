"""Prompt routing and A/B experiment logic."""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from catalog import models as catalog_models

logger = logging.getLogger(__name__)


class PromptRouter:
    """Router for selecting prompt templates based on A/B experiments."""

    def __init__(self, session: Session):
        self.session = session

    def select_prompt(
        self,
        endpoint_id: str | UUID,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Optional[catalog_models.PromptTemplate]:
        """
        Select a prompt template for a serving endpoint based on active experiments.

        Args:
            endpoint_id: Serving endpoint ID
            user_id: User ID for consistent routing
            request_id: Request ID for logging

        Returns:
            Selected PromptTemplate or None if no active experiment
        """
        endpoint = self.session.get(catalog_models.ServingEndpoint, endpoint_id)
        if not endpoint:
            logger.warning(f"Serving endpoint {endpoint_id} not found")
            return None

        # If endpoint has a direct prompt policy, use it
        if endpoint.prompt_policy_id:
            template = self.session.get(catalog_models.PromptTemplate, endpoint.prompt_policy_id)
            if template and template.status == "approved":
                return template

        # Check for active A/B experiments
        active_experiment = self._get_active_experiment(endpoint_id)
        if active_experiment:
            return self._select_from_experiment(active_experiment, user_id, request_id)

        return None

    def _get_active_experiment(
        self, endpoint_id: str | UUID
    ) -> Optional[catalog_models.PromptExperiment]:
        """Get the active prompt experiment for an endpoint."""
        # In a real implementation, we'd link experiments to endpoints
        # For now, we'll check for any active experiment
        now = datetime.utcnow()
        experiment = (
            self.session.query(catalog_models.PromptExperiment)
            .filter(
                catalog_models.PromptExperiment.start_at <= now,
                catalog_models.PromptExperiment.end_at.is_(None)
                | (catalog_models.PromptExperiment.end_at > now),
            )
            .order_by(catalog_models.PromptExperiment.start_at.desc())
            .first()
        )
        return experiment

    def _select_from_experiment(
        self,
        experiment: catalog_models.PromptExperiment,
        user_id: Optional[str],
        request_id: Optional[str],
    ) -> catalog_models.PromptTemplate:
        """
        Select template A or B based on allocation percentage.

        Args:
            experiment: Active prompt experiment
            user_id: User ID for consistent assignment
            request_id: Request ID for logging

        Returns:
            Selected PromptTemplate (A or B)
        """
        # Use user_id for consistent routing, fallback to request_id
        routing_key = user_id or request_id or "default"
        hash_value = int(hashlib.md5(routing_key.encode()).hexdigest(), 16)
        allocation_percent = hash_value % 100

        if allocation_percent < experiment.allocation:
            selected_template_id = experiment.template_a_id
            variant = "A"
        else:
            selected_template_id = experiment.template_b_id
            variant = "B"

        template = self.session.get(catalog_models.PromptTemplate, selected_template_id)
        if template:
            logger.info(
                f"Selected prompt template {variant} (ID: {selected_template_id}) "
                f"for experiment {experiment.id} (allocation: {experiment.allocation}%)"
            )
            return template

        # Fallback to template A if B is not found
        logger.warning(f"Template {selected_template_id} not found, falling back to template A")
        return self.session.get(catalog_models.PromptTemplate, experiment.template_a_id)

    def record_experiment_metric(
        self,
        experiment_id: str | UUID,
        template_id: str | UUID,
        metric_name: str,
        metric_value: float,
        request_id: Optional[str] = None,
    ) -> None:
        """
        Record a metric for an A/B experiment.

        Args:
            experiment_id: Prompt experiment ID
            template_id: Template variant used (A or B)
            metric_name: Metric name (e.g., "latency_ms", "user_satisfaction")
            metric_value: Metric value
            request_id: Request ID for correlation
        """
        # In a real implementation, we'd store this in a metrics table
        # For now, we'll log it
        logger.info(
            f"Experiment metric: experiment={experiment_id} template={template_id} "
            f"metric={metric_name} value={metric_value} request={request_id}"
        )

    def conclude_experiment(
        self,
        experiment_id: str | UUID,
        winner_template_id: str | UUID,
        notes: Optional[str] = None,
    ) -> catalog_models.PromptExperiment:
        """
        Conclude an A/B experiment and set the winner.

        Args:
            experiment_id: Prompt experiment ID
            winner_template_id: Winning template ID
            notes: Notes about the conclusion

        Returns:
            Updated PromptExperiment
        """
        experiment = self.session.get(catalog_models.PromptExperiment, experiment_id)
        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        experiment.winner_template_id = winner_template_id
        experiment.end_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(experiment)

        logger.info(
            f"Concluded experiment {experiment_id}: winner={winner_template_id}, notes={notes}"
        )
        return experiment

