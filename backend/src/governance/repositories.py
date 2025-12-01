"""Repositories for governance, audit, and cost entities."""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from catalog import models as catalog_models


class GovernancePolicyRepository:
    """Repository for GovernancePolicy entities."""

    def __init__(self, session: Session):
        self.session = session

    def create(
        self, policy: catalog_models.GovernancePolicy
    ) -> catalog_models.GovernancePolicy:
        """Persist a new governance policy."""
        self.session.add(policy)
        self.session.commit()
        self.session.refresh(policy)
        return policy

    def get(self, policy_id: str | UUID) -> Optional[catalog_models.GovernancePolicy]:
        """Retrieve a governance policy by ID."""
        try:
            uuid_id = UUID(policy_id) if isinstance(policy_id, str) else policy_id
        except (ValueError, TypeError):
            return None
        return self.session.get(catalog_models.GovernancePolicy, uuid_id)

    def list(
        self,
        scope: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Sequence[catalog_models.GovernancePolicy]:
        """List governance policies with optional filters."""
        query = self.session.query(catalog_models.GovernancePolicy)
        if scope:
            query = query.filter(catalog_models.GovernancePolicy.scope == scope)
        if status:
            query = query.filter(catalog_models.GovernancePolicy.status == status)
        return query.order_by(catalog_models.GovernancePolicy.created_at.desc()).all()

    def update(
        self, policy: catalog_models.GovernancePolicy
    ) -> catalog_models.GovernancePolicy:
        """Update an existing governance policy."""
        self.session.commit()
        self.session.refresh(policy)
        return policy

    def delete(self, policy: catalog_models.GovernancePolicy) -> None:
        """Delete a governance policy."""
        self.session.delete(policy)
        self.session.commit()


class AuditLogRepository:
    """Repository for AuditLog entities."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, log: catalog_models.AuditLog) -> catalog_models.AuditLog:
        """Persist a new audit log entry."""
        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)
        return log

    def list(
        self,
        actor_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> Sequence[catalog_models.AuditLog]:
        """List audit logs with optional filters."""
        query = self.session.query(catalog_models.AuditLog)
        if actor_id:
            query = query.filter(catalog_models.AuditLog.actor_id == actor_id)
        if resource_type:
            query = query.filter(catalog_models.AuditLog.resource_type == resource_type)
        if action:
            query = query.filter(catalog_models.AuditLog.action == action)
        return (
            query.order_by(catalog_models.AuditLog.occurred_at.desc())
            .limit(limit)
            .all()
        )


class CostProfileRepository:
    """Repository for CostProfile entities."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, profile: catalog_models.CostProfile) -> catalog_models.CostProfile:
        """Persist a new cost profile."""
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def list(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[str | UUID] = None,
        time_window: Optional[str] = None,
    ) -> Sequence[catalog_models.CostProfile]:
        """List cost profiles with optional filters."""
        query = self.session.query(catalog_models.CostProfile)
        if resource_type:
            query = query.filter(catalog_models.CostProfile.resource_type == resource_type)
        if resource_id:
            query = query.filter(catalog_models.CostProfile.resource_id == resource_id)
        if time_window:
            query = query.filter(catalog_models.CostProfile.time_window == time_window)
        return query.order_by(catalog_models.CostProfile.created_at.desc()).all()

