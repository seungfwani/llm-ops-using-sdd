from __future__ import annotations

from typing import Sequence, Optional
from uuid import uuid4, UUID
from datetime import datetime
from sqlalchemy.orm import Session
from catalog import models
from catalog.repositories import PromptTemplateRepository
from catalog.schemas import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
)

class PromptTemplateService:
    def __init__(self, session: Session):
        self.session = session
        self.templates = PromptTemplateRepository(session)

    def list_templates(self, status: Optional[str] = None) -> Sequence[models.PromptTemplate]:
        return self.templates.list(status=status)

    def get_template(self, template_id: str | UUID) -> Optional[models.PromptTemplate]:
        return self.templates.get(template_id)

    def create_template(self, payload: PromptTemplateCreate) -> models.PromptTemplate:
        template = models.PromptTemplate(
            id=str(uuid4()),
            name=payload.name,
            version=payload.version,
            language=payload.language,
            content=payload.content,
            context_tags=payload.context_tags,
            status=payload.status or "draft",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.templates.save(template)
        return template

    def update_template(self, template_id: str | UUID, payload: PromptTemplateUpdate) -> models.PromptTemplate:
        template = self.templates.get(template_id)
        if not template:
            raise ValueError("PromptTemplate not found")
        update_fields = payload.dict(exclude_unset=True)
        for key, value in update_fields.items():
            setattr(template, key, value)
        template.updated_at = datetime.utcnow()
        self.templates.update(template)
        return template

    def delete_template(self, template_id: str | UUID) -> bool:
        return self.templates.delete(template_id)

