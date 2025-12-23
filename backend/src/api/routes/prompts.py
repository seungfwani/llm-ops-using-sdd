from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from catalog.schemas import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
    PromptTemplateResponse,
    EnvelopePromptTemplate,
    EnvelopePromptTemplateList
)
from catalog.services.prompt_templates import PromptTemplateService
from core.database import get_session

router = APIRouter(prefix="/llm-ops/v1/prompts/templates", tags=["PromptTemplates"])

@router.post("", response_model=EnvelopePromptTemplate, status_code=status.HTTP_201_CREATED)
def create_prompt_template(payload: PromptTemplateCreate, db: Session = Depends(get_session)):
    svc = PromptTemplateService(db)
    template = svc.create_template(payload)
    return EnvelopePromptTemplate(status="success", data=PromptTemplateResponse.from_orm(template))

@router.get("", response_model=EnvelopePromptTemplateList)
def list_prompt_templates(status: str = None, db: Session = Depends(get_session)):
    svc = PromptTemplateService(db)
    templates = svc.list_templates(status=status)
    responses = [PromptTemplateResponse.from_orm(t) for t in templates]
    return EnvelopePromptTemplateList(status="success", data=responses)

@router.get("/{template_id}", response_model=EnvelopePromptTemplate)
def get_prompt_template(template_id: UUID, db: Session = Depends(get_session)):
    svc = PromptTemplateService(db)
    template = svc.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="PromptTemplate not found")
    return EnvelopePromptTemplate(status="success", data=PromptTemplateResponse.from_orm(template))

@router.put("/{template_id}", response_model=EnvelopePromptTemplate)
def update_prompt_template(
    template_id: UUID, payload: PromptTemplateUpdate, db: Session = Depends(get_session)
):
    svc = PromptTemplateService(db)
    try:
        template = svc.update_template(template_id, payload)
    except ValueError:
        raise HTTPException(status_code=404, detail="PromptTemplate not found")
    return EnvelopePromptTemplate(status="success", data=PromptTemplateResponse.from_orm(template))

@router.delete("/{template_id}", response_model=EnvelopePromptTemplate)
def delete_prompt_template(template_id: UUID, db: Session = Depends(get_session)):
    svc = PromptTemplateService(db)
    ok = svc.delete_template(template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="PromptTemplate not found")
    return EnvelopePromptTemplate(status="success", data=None, message="PromptTemplate deleted.")

