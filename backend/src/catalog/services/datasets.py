from __future__ import annotations

from typing import Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from catalog import models as orm_models
from catalog.repositories import DatasetRepository


class DatasetService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = DatasetRepository(session)

    def list_datasets(self) -> Sequence[orm_models.DatasetRecord]:
        return self.repo.list()

    def create_dataset(self, payload: dict) -> orm_models.DatasetRecord:
        dataset = orm_models.DatasetRecord(
            id=str(uuid4()),
            name=payload["name"],
            version=payload["version"],
            storage_uri=payload["storage_uri"],
            owner_team=payload["owner_team"],
            change_log=payload.get("change_log"),
            pii_scan_status=payload.get("pii_scan_status", "pending"),
            quality_score=payload.get("quality_score"),
        )
        self.repo.save(dataset)
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

    def approve_dataset(self, dataset_id: str) -> orm_models.DatasetRecord:
        dataset = self.repo.get(dataset_id)
        if not dataset:
            raise ValueError("Dataset not found")
        dataset.pii_scan_status = "clean"
        self.session.commit()
        self.session.refresh(dataset)
        return dataset

