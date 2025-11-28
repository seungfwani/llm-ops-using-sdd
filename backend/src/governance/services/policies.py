"""Governance policy CRUD and evaluation service."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as catalog_models
from governance.repositories import (
    AuditLogRepository,
    CostProfileRepository,
    GovernancePolicyRepository,
)

logger = logging.getLogger(__name__)


class PolicyEvaluationResult:
    """Result of a policy evaluation."""

    def __init__(self, allowed: bool, reason: str, policy_id: Optional[str] = None):
        self.allowed = allowed
        self.reason = reason
        self.policy_id = policy_id


class GovernancePolicyService:
    """Service for managing governance policies and evaluation."""

    def __init__(self, session: Session):
        self.policy_repo = GovernancePolicyRepository(session)
        self.audit_repo = AuditLogRepository(session)
        self.session = session

    def create_policy(
        self,
        name: str,
        scope: str,
        rules: dict,
        status: str = "draft",
    ) -> catalog_models.GovernancePolicy:
        """
        Create a new governance policy.

        Args:
            name: Policy name
            scope: Policy scope (e.g., "catalog", "training", "serving", "global")
            rules: Policy rules (JSON structure)
            status: Policy status (draft, active, deprecated)

        Returns:
            Created GovernancePolicy entity
        """
        policy = catalog_models.GovernancePolicy(
            id=uuid4(),
            name=name,
            scope=scope,
            rules=rules,
            status=status,
            created_at=datetime.utcnow(),
        )
        return self.policy_repo.create(policy)

    def get_policy(self, policy_id: str) -> Optional[catalog_models.GovernancePolicy]:
        """Retrieve a governance policy by ID."""
        return self.policy_repo.get(policy_id)

    def list_policies(
        self,
        scope: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[catalog_models.GovernancePolicy]:
        """List governance policies with optional filters."""
        return list(self.policy_repo.list(scope=scope, status=status))

    def update_policy(
        self,
        policy_id: str,
        name: Optional[str] = None,
        rules: Optional[dict] = None,
        status: Optional[str] = None,
    ) -> Optional[catalog_models.GovernancePolicy]:
        """Update an existing governance policy."""
        policy = self.policy_repo.get(policy_id)
        if not policy:
            return None

        if name:
            policy.name = name
        if rules:
            policy.rules = rules
        if status:
            policy.status = status
            if status == "active":
                policy.last_reviewed_at = datetime.utcnow()

        return self.policy_repo.update(policy)

    def delete_policy(self, policy_id: str) -> bool:
        """Delete a governance policy."""
        policy = self.policy_repo.get(policy_id)
        if not policy:
            return False

        self.policy_repo.delete(policy)
        return True

    def evaluate_policy(
        self,
        scope: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_roles: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> PolicyEvaluationResult:
        """
        Evaluate policies for a given action.

        Args:
            scope: Policy scope to evaluate
            action: Action being performed (e.g., "create", "delete", "approve")
            resource_type: Type of resource (e.g., "model", "dataset", "training_job")
            resource_id: Optional resource ID
            user_roles: User roles for RBAC evaluation
            metadata: Additional metadata for policy evaluation

        Returns:
            PolicyEvaluationResult indicating if action is allowed
        """
        # Get active policies for the scope
        policies = self.policy_repo.list(scope=scope, status="active")
        if not policies:
            # No active policies, allow by default
            return PolicyEvaluationResult(allowed=True, reason="No active policies")

        # Evaluate each policy
        for policy in policies:
            result = self._evaluate_single_policy(
                policy, action, resource_type, resource_id, user_roles, metadata
            )
            if not result.allowed:
                # Log policy violation
                self.audit_repo.create(
                    catalog_models.AuditLog(
                        id=uuid4(),
                        actor_id=metadata.get("user_id", "system") if metadata else "system",
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        result="denied",
                        metadata={"policy_id": str(policy.id), "reason": result.reason},
                        occurred_at=datetime.utcnow(),
                    )
                )
                return result

        return PolicyEvaluationResult(allowed=True, reason="All policies passed")

    def _evaluate_single_policy(
        self,
        policy: catalog_models.GovernancePolicy,
        action: str,
        resource_type: str,
        resource_id: Optional[str],
        user_roles: Optional[list[str]],
        metadata: Optional[dict],
    ) -> PolicyEvaluationResult:
        """Evaluate a single policy's rules."""
        rules = policy.rules

        # Check action restrictions
        if "allowed_actions" in rules:
            if action not in rules["allowed_actions"]:
                return PolicyEvaluationResult(
                    allowed=False,
                    reason=f"Action '{action}' not allowed by policy '{policy.name}'",
                    policy_id=str(policy.id),
                )

        # Check role-based restrictions
        if "required_roles" in rules:
            if not user_roles or not any(role in rules["required_roles"] for role in user_roles):
                return PolicyEvaluationResult(
                    allowed=False,
                    reason=f"Insufficient roles. Required: {rules['required_roles']}",
                    policy_id=str(policy.id),
                )

        # Check resource type restrictions
        if "allowed_resource_types" in rules:
            if resource_type not in rules["allowed_resource_types"]:
                return PolicyEvaluationResult(
                    allowed=False,
                    reason=f"Resource type '{resource_type}' not allowed",
                    policy_id=str(policy.id),
                )

        # Check custom conditions (e.g., cost limits, time windows)
        if "conditions" in rules:
            for condition in rules["conditions"]:
                if not self._evaluate_condition(condition, metadata):
                    return PolicyEvaluationResult(
                        allowed=False,
                        reason=f"Condition failed: {condition}",
                        policy_id=str(policy.id),
                    )

        return PolicyEvaluationResult(allowed=True, reason="Policy passed", policy_id=str(policy.id))

    @staticmethod
    def _evaluate_condition(condition: dict, metadata: Optional[dict]) -> bool:
        """Evaluate a custom condition."""
        if not metadata:
            return True

        condition_type = condition.get("type")
        if condition_type == "cost_limit":
            cost = metadata.get("cost", 0)
            limit = condition.get("limit", float("inf"))
            return cost <= limit
        elif condition_type == "time_window":
            # Check if action is within allowed time window
            # This is a simplified check; real implementation would parse time windows
            return True
        elif condition_type == "resource_limit":
            resource_count = metadata.get("resource_count", 0)
            limit = condition.get("limit", float("inf"))
            return resource_count < limit

        return True

