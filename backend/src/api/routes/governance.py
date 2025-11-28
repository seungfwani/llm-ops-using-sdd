"""Governance, observability, and cost API routes."""
from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.database import get_session
from governance import schemas
from governance.schemas import EnvelopeCostProfileList, EnvelopeGovernancePolicyList
from governance.repositories import AuditLogRepository
from governance.services.cost import CostService
from governance.services.policies import GovernancePolicyService

router = APIRouter(prefix="/llm-ops/v1/governance", tags=["governance"])


def get_governance_service(session: Session = Depends(get_session)) -> GovernancePolicyService:
    """Dependency to get governance policy service."""
    return GovernancePolicyService(session)


def get_cost_service(session: Session = Depends(get_session)) -> CostService:
    """Dependency to get cost service."""
    return CostService(session)


@router.post("/policies", response_model=schemas.EnvelopeGovernancePolicy)
def create_policy(
    request: schemas.GovernancePolicyRequest,
    service: GovernancePolicyService = Depends(get_governance_service),
) -> schemas.EnvelopeGovernancePolicy:
    """Create a new governance policy."""
    try:
        policy = service.create_policy(
            name=request.name,
            scope=request.scope,
            rules=request.rules,
            status=request.status,
        )
        return schemas.EnvelopeGovernancePolicy(
            status="success",
            message="Policy created successfully",
            data=schemas.GovernancePolicyResponse(
                id=str(policy.id),
                name=policy.name,
                scope=policy.scope,
                rules=policy.rules,
                status=policy.status,
                lastReviewedAt=policy.last_reviewed_at,
                createdAt=policy.created_at,
            ),
        )
    except Exception as e:
        return schemas.EnvelopeGovernancePolicy(
            status="fail",
            message=f"Failed to create policy: {str(e)}",
            data=None,
        )


@router.get("/policies", response_model=EnvelopeGovernancePolicyList)
def list_policies(
    scope: str | None = Query(None),
    status: str | None = Query(None),
    service: GovernancePolicyService = Depends(get_governance_service),
) -> EnvelopeGovernancePolicyList:
    """List governance policies with optional filters."""
    policies = service.list_policies(scope=scope, status=status)
    return EnvelopeGovernancePolicyList(
        status="success",
        message="",
        data=[
            schemas.GovernancePolicyResponse(
                id=str(p.id),
                name=p.name,
                scope=p.scope,
                rules=p.rules,
                status=p.status,
                lastReviewedAt=p.last_reviewed_at,
                createdAt=p.created_at,
            )
            for p in policies
        ],
    )


@router.get("/policies/{policyId}", response_model=schemas.EnvelopeGovernancePolicy)
def get_policy(
    policyId: str,
    service: GovernancePolicyService = Depends(get_governance_service),
) -> schemas.EnvelopeGovernancePolicy:
    """Retrieve a governance policy by ID."""
    policy = service.get_policy(policyId)
    if not policy:
        return schemas.EnvelopeGovernancePolicy(
            status="fail",
            message=f"Policy {policyId} not found",
            data=None,
        )

    return schemas.EnvelopeGovernancePolicy(
        status="success",
        message="",
        data=schemas.GovernancePolicyResponse(
            id=str(policy.id),
            name=policy.name,
            scope=policy.scope,
            rules=policy.rules,
            status=policy.status,
            lastReviewedAt=policy.last_reviewed_at,
            createdAt=policy.created_at,
        ),
    )


@router.get("/audit/logs", response_model=schemas.EnvelopeAuditLogs)
def list_audit_logs(
    actorId: str | None = Query(None, alias="actor_id"),
    resourceType: str | None = Query(None, alias="resource_type"),
    action: str | None = Query(None),
    limit: int = Query(100, le=1000),
    session: Session = Depends(get_session),
) -> schemas.EnvelopeAuditLogs:
    """List audit logs with optional filters."""
    audit_repo = AuditLogRepository(session)
    logs = audit_repo.list(actor_id=actorId, resource_type=resourceType, action=action, limit=limit)
    return schemas.EnvelopeAuditLogs(
        status="success",
        message="",
        data=[
            schemas.AuditLogResponse(
                id=str(log.id),
                actorId=log.actor_id,
                action=log.action,
                resourceType=log.resource_type,
                resourceId=log.resource_id,
                result=log.result,
                metadata=log.log_metadata,
                occurredAt=log.occurred_at,
            )
            for log in logs
        ],
    )


@router.get("/observability/cost-profiles", response_model=EnvelopeCostProfileList)
def list_cost_profiles(
    resourceType: str | None = Query(None, alias="resource_type"),
    resourceId: str | None = Query(None, alias="resource_id"),
    timeWindow: str | None = Query(None, alias="time_window"),
    service: CostService = Depends(get_cost_service),
) -> EnvelopeCostProfileList:
    """List cost profiles with optional filters."""
    profiles = service.list_cost_profiles(
        resource_type=resourceType, resource_id=resourceId, time_window=timeWindow
    )
    return EnvelopeCostProfileList(
        status="success",
        message="",
        data=[
            schemas.CostProfileResponse(
                id=str(p.id),
                resourceType=p.resource_type,
                resourceId=str(p.resource_id),
                timeWindow=p.time_window,
                gpuHours=p.gpu_hours,
                tokenCount=p.token_count,
                costAmount=p.cost_amount,
                costCurrency=p.cost_currency,
                budgetVariance=p.budget_variance,
                createdAt=p.created_at,
            )
            for p in profiles
        ],
    )


@router.get("/observability/cost-aggregate", response_model=schemas.EnvelopeCostAggregate)
def get_cost_aggregate(
    resourceType: str | None = Query(None, alias="resource_type"),
    startDate: datetime | None = Query(None, alias="start_date"),
    endDate: datetime | None = Query(None, alias="end_date"),
    service: CostService = Depends(get_cost_service),
) -> schemas.EnvelopeCostAggregate:
    """Get aggregated cost summary."""
    try:
        aggregate = service.aggregate_costs(
            resource_type=resourceType, start_date=startDate, end_date=endDate
        )
        return schemas.EnvelopeCostAggregate(
            status="success",
            message="",
            data=schemas.CostAggregateResponse(
                totalGpuHours=aggregate["total_gpu_hours"],
                totalTokens=aggregate["total_tokens"],
                totalCost=aggregate["total_cost"],
                currency=aggregate["currency"],
                resourceCount=aggregate["resource_count"],
            ),
        )
    except Exception as e:
        return schemas.EnvelopeCostAggregate(
            status="fail",
            message=f"Failed to aggregate costs: {str(e)}",
            data=None,
        )

