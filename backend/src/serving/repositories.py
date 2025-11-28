"""Repositories for serving endpoint entities."""
from __future__ import annotations

from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from catalog import models as catalog_models


class ServingEndpointRepository:
    """Repository for ServingEndpoint entities."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, endpoint: catalog_models.ServingEndpoint) -> catalog_models.ServingEndpoint:
        """Persist a new serving endpoint."""
        self.session.add(endpoint)
        self.session.commit()
        self.session.refresh(endpoint)
        return endpoint

    def get(self, endpoint_id: str | UUID) -> Optional[catalog_models.ServingEndpoint]:
        """Retrieve a serving endpoint by ID."""
        try:
            uuid_id = UUID(endpoint_id) if isinstance(endpoint_id, str) else endpoint_id
        except (ValueError, TypeError):
            return None
        return self.session.get(catalog_models.ServingEndpoint, uuid_id)

    def get_by_route(
        self, environment: str, route: str
    ) -> Optional[catalog_models.ServingEndpoint]:
        """Retrieve a serving endpoint by environment and route."""
        return (
            self.session.query(catalog_models.ServingEndpoint)
            .filter(
                catalog_models.ServingEndpoint.environment == environment,
                catalog_models.ServingEndpoint.route == route,
            )
            .first()
        )

    def list(
        self,
        environment: Optional[str] = None,
        model_entry_id: Optional[str | UUID] = None,
        status: Optional[str] = None,
    ) -> Sequence[catalog_models.ServingEndpoint]:
        """List serving endpoints with optional filters."""
        query = self.session.query(catalog_models.ServingEndpoint)
        if environment:
            query = query.filter(catalog_models.ServingEndpoint.environment == environment)
        if model_entry_id:
            query = query.filter(catalog_models.ServingEndpoint.model_entry_id == model_entry_id)
        if status:
            query = query.filter(catalog_models.ServingEndpoint.status == status)
        return query.order_by(catalog_models.ServingEndpoint.created_at.desc()).all()

    def update(self, endpoint: catalog_models.ServingEndpoint) -> catalog_models.ServingEndpoint:
        """Update an existing serving endpoint."""
        self.session.commit()
        self.session.refresh(endpoint)
        return endpoint

    def delete(self, endpoint: catalog_models.ServingEndpoint) -> None:
        """Delete a serving endpoint."""
        self.session.delete(endpoint)
        self.session.commit()

