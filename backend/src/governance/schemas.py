"""Pydantic schemas for governance API requests/responses."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GovernancePolicyRequest(BaseModel):
    """Request schema for creating/updating a governance policy."""

    name: str = Field(..., description="Policy name")
    scope: str = Field(..., description="Policy scope (catalog, training, serving, global)")
    rules: dict = Field(..., description="Policy rules (JSON structure)")
    status: str = Field(default="draft", pattern="^(draft|active|deprecated)$")


class GovernancePolicyResponse(BaseModel):
    """Response schema for governance policy operations."""

    id: str
    name: str
    scope: str
    rules: dict
    status: str
    lastReviewedAt: Optional[datetime] = None
    createdAt: datetime

    class Config:
        from_attributes = True


class EnvelopeGovernancePolicy(BaseModel):
    """Standard API envelope for governance policy responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[GovernancePolicyResponse] = None


class EnvelopeGovernancePolicyList(BaseModel):
    """Standard API envelope for governance policy list responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[list[GovernancePolicyResponse]] = None


class AuditLogResponse(BaseModel):
    """Response schema for audit log entries."""

    id: str
    actorId: str
    action: str
    resourceType: str
    resourceId: Optional[str] = None
    result: str
    metadata: Optional[dict] = None
    occurredAt: datetime

    class Config:
        from_attributes = True


class EnvelopeAuditLogs(BaseModel):
    """Standard API envelope for audit log responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[list[AuditLogResponse]] = None


class CostProfileResponse(BaseModel):
    """Response schema for cost profile operations."""

    id: str
    resourceType: str
    resourceId: str
    timeWindow: str
    gpuHours: Optional[float] = None
    tokenCount: Optional[int] = None
    costAmount: Optional[float] = None
    costCurrency: str
    budgetVariance: Optional[float] = None
    createdAt: datetime

    class Config:
        from_attributes = True


class EnvelopeCostProfile(BaseModel):
    """Standard API envelope for cost profile responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[CostProfileResponse] = None


class EnvelopeCostProfileList(BaseModel):
    """Standard API envelope for cost profile list responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[list[CostProfileResponse]] = None


class CostAggregateResponse(BaseModel):
    """Response schema for cost aggregation."""

    totalGpuHours: float
    totalTokens: int
    totalCost: float
    currency: str
    resourceCount: int


class EnvelopeCostAggregate(BaseModel):
    """Standard API envelope for cost aggregation responses."""

    status: str = Field(..., pattern="^(success|fail)$")
    message: str = ""
    data: Optional[CostAggregateResponse] = None

