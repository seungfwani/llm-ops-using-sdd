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
    Boolean,
    BigInteger,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, foreign

from core.database import Base


class ModelCatalogEntry(Base):
    __tablename__ = "model_catalog_entries"
    __table_args__ = (
        UniqueConstraint("name", "type", "version"),
        CheckConstraint("type in ('base','fine-tuned','external')"),
        # NOTE:
        # - Historically the spec used: draft, under_review, approved, deprecated
        # - The frontend now also uses: pending_review, rejected
        # To avoid runtime DB integrity errors (e.g. when setting status='rejected')
        # we support the superset of values here. The service layer is responsible
        # for constraining which values are actually used in workflows.
        CheckConstraint(
            "status in ('draft','under_review','approved','deprecated','pending_review','rejected')"
        ),
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
    training_jobs: Mapped[List["TrainingJob"]] = relationship(
        back_populates="model_entry",
        primaryjoin="ModelCatalogEntry.id == TrainingJob.model_entry_id"
    )
    output_training_jobs: Mapped[List["TrainingJob"]] = relationship(
        back_populates="output_model_entry",
        primaryjoin="ModelCatalogEntry.id == TrainingJob.output_model_entry_id"
    )
    registry_models: Mapped[List["RegistryModel"]] = relationship(
        back_populates="model_catalog_entry",
        cascade="all, delete-orphan"
    )


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
    dataset_versions: Mapped[List["DatasetVersion"]] = relationship(
        back_populates="dataset_record",
        cascade="all, delete-orphan",
    )


class CatalogEntryDataset(Base):
    __tablename__ = "catalog_entry_datasets"

    catalog_entry_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_catalog_entries.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dataset_records.id", ondelete="CASCADE"), primary_key=True
    )


class DatasetVersion(Base):
    """Dataset version managed by an open-source data versioning tool (e.g., DVC)."""

    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("versioning_system", "version_id", "dataset_record_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    dataset_record_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    versioning_system: Mapped[str] = mapped_column(Text, nullable=False)
    version_id: Mapped[str] = mapped_column(Text, nullable=False)
    parent_version_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dataset_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    version_tag: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checksum: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    diff_summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    compression_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    dataset_record: Mapped["DatasetRecord"] = relationship(
        back_populates="dataset_versions",
        primaryjoin="DatasetVersion.dataset_record_id == DatasetRecord.id",
    )
    parent_version: Mapped[Optional["DatasetVersion"]] = relationship(
        remote_side="DatasetVersion.id",
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
    output_model_storage_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_model_entry_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_catalog_entries.id", ondelete="SET NULL"), nullable=True
    )

    model_entry: Mapped[ModelCatalogEntry] = relationship(
        back_populates="training_jobs",
        primaryjoin="TrainingJob.model_entry_id == ModelCatalogEntry.id"
    )
    output_model_entry: Mapped[Optional[ModelCatalogEntry]] = relationship(
        back_populates="output_training_jobs",
        primaryjoin="TrainingJob.output_model_entry_id == ModelCatalogEntry.id"
    )
    dataset: Mapped[DatasetRecord] = relationship(back_populates="training_jobs")
    metrics: Mapped[List["ExperimentMetric"]] = relationship(back_populates="training_job")
    experiment_run: Mapped[Optional["ExperimentRun"]] = relationship(
        back_populates="training_job",
        uselist=False,
        cascade="all, delete-orphan"
    )


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


class ExperimentRun(Base):
    """Experiment run tracked in open-source experiment tracking system (e.g., MLflow)."""
    __tablename__ = "experiment_runs"
    __table_args__ = (
        UniqueConstraint("tracking_system", "tracking_run_id"),
        CheckConstraint("status in ('running', 'completed', 'failed', 'killed')"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    training_job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_jobs.id", ondelete="CASCADE"), nullable=False
    )
    tracking_system: Mapped[str] = mapped_column(Text, nullable=False)
    tracking_run_id: Mapped[str] = mapped_column(Text, nullable=False)
    experiment_name: Mapped[str] = mapped_column(Text, nullable=False)
    run_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[Optional[dict]] = mapped_column(JSON)
    metrics: Mapped[Optional[dict]] = mapped_column(JSON)
    artifact_uris: Mapped[Optional[dict]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(Text, default="running", nullable=False)
    start_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    training_job: Mapped[TrainingJob] = relationship(back_populates="experiment_run")


class ServingEndpoint(Base):
    __tablename__ = "serving_endpoints"
    __table_args__ = (UniqueConstraint("environment", "route"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_entry_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_catalog_entries.id", ondelete="RESTRICT"), nullable=False
    )
    environment: Mapped[str] = mapped_column(Text, nullable=False)
    route: Mapped[str] = mapped_column(Text, nullable=False)
    runtime_image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="deploying", nullable=False)
    min_replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    autoscale_policy: Mapped[Optional[dict]] = mapped_column(JSON)
    prompt_policy_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("prompt_templates.id"))
    use_gpu: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    cpu_request: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cpu_limit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    memory_request: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    memory_limit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_health_check: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    rollback_plan: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)

    observability: Mapped[List["ObservabilitySnapshot"]] = relationship(back_populates="endpoint")
    serving_deployment: Mapped[Optional["ServingDeployment"]] = relationship(
        back_populates="serving_endpoint",
        uselist=False,
        cascade="all, delete-orphan"
    )


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


class ServingDeployment(Base):
    """Serving deployment tracked in open-source serving framework (e.g., KServe, Ray Serve)."""
    __tablename__ = "serving_deployments"
    __table_args__ = (
        UniqueConstraint("serving_framework", "framework_resource_id", "framework_namespace"),
        CheckConstraint("min_replicas >= 0"),
        CheckConstraint("max_replicas >= min_replicas"),
        CheckConstraint("replica_count >= min_replicas AND replica_count <= max_replicas"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    serving_endpoint_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("serving_endpoints.id", ondelete="CASCADE"), nullable=False
    )
    serving_framework: Mapped[str] = mapped_column(Text, nullable=False)
    framework_resource_id: Mapped[str] = mapped_column(Text, nullable=False)
    framework_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    replica_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    min_replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_replicas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    autoscaling_metrics: Mapped[Optional[dict]] = mapped_column(JSON)
    resource_requests: Mapped[Optional[dict]] = mapped_column(JSON)
    resource_limits: Mapped[Optional[dict]] = mapped_column(JSON)
    framework_status: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    serving_endpoint: Mapped[ServingEndpoint] = relationship(back_populates="serving_deployment")


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


class RegistryModel(Base):
    """Model imported from or exported to open-source registry (e.g., Hugging Face Hub)."""
    __tablename__ = "registry_models"
    __table_args__ = (
        CheckConstraint("sync_status in ('synced', 'out_of_sync', 'never_synced')"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    model_catalog_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("model_catalog_entries.id", ondelete="CASCADE"), nullable=False
    )
    registry_type: Mapped[str] = mapped_column(Text, nullable=False)
    registry_model_id: Mapped[str] = mapped_column(Text, nullable=False)
    registry_repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    registry_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    imported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    imported_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    exported_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    registry_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    sync_status: Mapped[str] = mapped_column(Text, default="never_synced", nullable=False)
    last_sync_check: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    model_catalog_entry: Mapped["ModelCatalogEntry"] = relationship(
        back_populates="registry_models",
        primaryjoin="RegistryModel.model_catalog_id == ModelCatalogEntry.id"
    )


class WorkflowPipeline(Base):
    """Workflow pipeline tracked in open-source orchestration system (e.g., Argo Workflows)."""
    __tablename__ = "workflow_pipelines"
    __table_args__ = (
        UniqueConstraint("orchestration_system", "workflow_id", "workflow_namespace"),
        CheckConstraint("status in ('pending', 'running', 'succeeded', 'failed', 'cancelled')"),
        CheckConstraint("retry_count >= 0"),
        CheckConstraint("max_retries >= 0"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True)
    pipeline_name: Mapped[str] = mapped_column(Text, nullable=False)
    orchestration_system: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_id: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_namespace: Mapped[str] = mapped_column(Text, nullable=False)
    pipeline_definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    stages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="pending", nullable=False)
    current_stage: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

