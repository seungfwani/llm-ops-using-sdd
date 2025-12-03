from __future__ import annotations

from typing import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


class ModelCatalogRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self) -> Sequence[models.ModelCatalogEntry]:
        return self.session.execute(select(models.ModelCatalogEntry)).scalars().all()

    def get(self, entry_id: str | UUID) -> models.ModelCatalogEntry | None:
        try:
            uuid_id = UUID(entry_id) if isinstance(entry_id, str) else entry_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.ModelCatalogEntry, uuid_id)

    def save(self, entry: models.ModelCatalogEntry) -> models.ModelCatalogEntry:
        self.session.add(entry)
        return entry

    def delete(self, entry_id: str | UUID) -> bool:
        """Delete a model catalog entry by ID. Returns True if deleted, False if not found."""
        entry = self.get(entry_id)
        if not entry:
            return False
        self.session.delete(entry)
        return True


class DatasetRepository:
    def __init__(self, session: Session):
        self.session = session

    def list(self) -> Sequence[models.DatasetRecord]:
        return self.session.execute(select(models.DatasetRecord)).scalars().all()

    def get(self, dataset_id: str | UUID) -> models.DatasetRecord | None:
        try:
            uuid_id = UUID(dataset_id) if isinstance(dataset_id, str) else dataset_id
        except (ValueError, TypeError):
            return None
        return self.session.get(models.DatasetRecord, uuid_id)

    def save(self, dataset: models.DatasetRecord) -> models.DatasetRecord:
        self.session.add(dataset)
        return dataset

    def fetch_by_ids(self, dataset_ids: Sequence[str]) -> Sequence[models.DatasetRecord]:
        stmt = select(models.DatasetRecord).where(models.DatasetRecord.id.in_(dataset_ids))
        return self.session.execute(stmt).scalars().all()

    def get_by_name_version(self, name: str, version: str) -> models.DatasetRecord | None:
        """Get a dataset by name and version combination."""
        stmt = select(models.DatasetRecord).where(
            models.DatasetRecord.name == name,
            models.DatasetRecord.version == version
        )
        return self.session.execute(stmt).scalar_one_or_none()

