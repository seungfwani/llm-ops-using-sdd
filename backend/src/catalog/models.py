from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    CheckConstraint,
    ForeignKey,
    Integer,
    Float,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class ModelCatalogEntry(Base):
    __tablename__ = "model_catalog_entries"
    __table_args__ = (
        UniqueConstraint("name", "type", "version"),
        CheckConstraint("type in ('base','fine-tuned','external')"),
        CheckConstraint("status in ('draft','under_review','approved','deprecated')"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="draft", nullable=False)
    owner_team: Mapped[str] = mapped_column(Text, nullable=False)
    model_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False)
    storage_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lineage_dataset_ids: Mapped[Optional[List[str]]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    evaluation_summary: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    datasets: Mapped[List["DatasetRecord"]] = relationship(
        secondary="catalog_entry_datasets", back_populates="catalog_entries"
    )
    training_jobs: Mapped[List["TrainingJob"]] = relationship(back_populates="model_entry")


class DatasetRecord(Base):
    __tablename__ = "dataset_records"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    pii_scan_status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer)
    change_log: Mapped[Optional[str]] = mapped_column(Text)
    owner_team: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    catalog_entries: Mapped[List[ModelCatalogEntry]] = relationship(
        secondary="catalog_entry_datasets", back_populates="datasets"
    )
    training_jobs: Mapped[List["TrainingJob"]] = relationship(back_populates="dataset")


class CatalogEntryDataset(Base):
    __tablename__ = "catalog_entry_datasets"

    catalog_entry_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_catalog_entries.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_records.id", ondelete="CASCADE"), primary_key=True
    )


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    __table_args__ = (UniqueConstraint("name", "version"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(Text, default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PromptExperiment(Base):
    __tablename__ = "prompt_experiments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    template_a_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_templates.id", ondelete="CASCADE"), nullable=False
    )
    template_b_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_templates.id", ondelete="CASCADE"), nullable=False
    )
    allocation: Mapped[int] = mapped_column(Integer, nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    start_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    winner_template_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_entry_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_catalog_entries.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_records.id", ondelete="RESTRICT"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    scheduler_id: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="queued", nullable=False)
    retry_policy: Mapped[Optional[dict]] = mapped_column(JSON)
    submitted_by: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))

    model_entry: Mapped[ModelCatalogEntry] = relationship(back_populates="training_jobs")
    dataset: Mapped[DatasetRecord] = relationship(back_populates="training_jobs")
    metrics: Mapped[List["ExperimentMetric"]] = relationship(back_populates="training_job")


class ExperimentMetric(Base):
    __tablename__ = "experiment_metrics"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    training_job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_jobs.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(Text)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    training_job: Mapped[TrainingJob] = relationship(back_populates="metrics")


class ServingEndpoint(Base):
    __tablename__ = "serving_endpoints"
    __table_args__ = (UniqueConstraint("environment", "route"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_entry_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_catalog_entries.id", ondelete="RESTRICT"), nullable=False
    )
    environment: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="deploying", nullable=False)
    min_replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    autoscale_policy: Mapped[Optional[dict]] = mapped_column(JSON)
    prompt_policy_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"))
    last_health_check: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    rollback_plan: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    observability: Mapped[List["ObservabilitySnapshot"]] = relationship(back_populates="endpoint")


class ObservabilitySnapshot(Base):
    __tablename__ = "observability_snapshots"
    __table_args__ = (UniqueConstraint("serving_endpoint_id", "time_bucket"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    serving_endpoint_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("serving_endpoints.id", ondelete="CASCADE"), nullable=False
    )
    time_bucket: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    latency_p50: Mapped[Optional[float]] = mapped_column(Float)
    latency_p95: Mapped[Optional[float]] = mapped_column(Float)
    error_rate: Mapped[Optional[float]] = mapped_column(Float)
    token_per_request: Mapped[Optional[float]] = mapped_column(Float)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    endpoint: Mapped[ServingEndpoint] = relationship(back_populates="observability")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_entry_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_catalog_entries.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("dataset_records.id"))
    prompt_template_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"))
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    run_by: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class GovernancePolicy(Base):
    __tablename__ = "governance_policies"
    __table_args__ = (UniqueConstraint("name", "scope"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    rules: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="draft", nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    log_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON)
    occurred_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class CostProfile(Base):
    __tablename__ = "cost_profiles"
    __table_args__ = (UniqueConstraint("resource_type", "resource_id", "time_window"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    resource_id: Mapped[str] = mapped_column(UUID(as_uuid=True), nullable=False)
    time_window: Mapped[str] = mapped_column(Text, nullable=False)
    gpu_hours: Mapped[Optional[float]] = mapped_column(Float)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    cost_currency: Mapped[str] = mapped_column(Text, default="USD")
    cost_amount: Mapped[Optional[float]] = mapped_column(Float)
    budget_variance: Mapped[Optional[float]] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

