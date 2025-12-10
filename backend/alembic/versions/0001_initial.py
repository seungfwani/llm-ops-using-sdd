"""Initial schema (consolidated from previous 0001-0015 migrations)."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # model_catalog_entries
    op.create_table(
        "model_catalog_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("owner_team", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("lineage_dataset_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
        sa.Column("evaluation_summary", postgresql.JSONB()),
        sa.Column("storage_uri", sa.Text()),
        sa.Column("model_family", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("type IN ('base','fine-tuned','external')", name="ck_model_catalog_type"),
        sa.CheckConstraint(
            "status IN ('draft','under_review','approved','deprecated','pending_review','rejected')",
            name="ck_model_catalog_status",
        ),
        sa.UniqueConstraint("name", "type", "version", name="uq_model_catalog_name_type_version"),
    )
    op.create_index("idx_catalog_status", "model_catalog_entries", ["status"])

    # dataset_records
    op.create_table(
        "dataset_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("pii_scan_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("quality_score", sa.Integer()),
        sa.Column("change_log", sa.Text()),
        sa.Column("owner_team", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("pii_scan_status IN ('pending','clean','failed')", name="ck_dataset_pii_status"),
        sa.CheckConstraint("quality_score BETWEEN 0 AND 100", name="ck_dataset_quality_score"),
        sa.UniqueConstraint("name", "version", name="uq_dataset_name_version"),
    )
    op.create_index("idx_dataset_owner", "dataset_records", ["owner_team"])

    # catalog_entry_datasets
    op.create_table(
        "catalog_entry_datasets",
        sa.Column("catalog_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_entry_id"], ["model_catalog_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("catalog_entry_id", "dataset_id"),
    )

    # prompt_templates
    op.create_table(
        "prompt_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("language", sa.Text()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("context_tags", postgresql.ARRAY(sa.Text())),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft','live','retired')", name="ck_prompt_status"),
        sa.UniqueConstraint("name", "version", name="uq_prompt_name_version"),
    )

    # prompt_experiments
    op.create_table(
        "prompt_experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("template_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allocation", sa.Integer(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("start_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("winner_template_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("allocation BETWEEN 0 AND 100", name="ck_prompt_experiment_allocation"),
        sa.ForeignKeyConstraint(["template_a_id"], ["prompt_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["template_b_id"], ["prompt_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["winner_template_id"], ["prompt_templates.id"]),
    )

    # training_jobs
    op.create_table(
        "training_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column("resource_profile", postgresql.JSONB(), nullable=False),
        sa.Column("scheduler_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("retry_policy", postgresql.JSONB()),
        sa.Column("submitted_by", sa.Text(), nullable=False),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("output_model_storage_uri", sa.Text()),
        sa.Column("output_model_entry_id", postgresql.UUID(as_uuid=True)),
        sa.Column("train_job_spec", postgresql.JSONB()),
        sa.CheckConstraint("job_type IN ('finetune','distributed')", name="ck_training_job_type"),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="ck_training_status"),
        sa.ForeignKeyConstraint(["model_entry_id"], ["model_catalog_entries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["dataset_records.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["output_model_entry_id"], ["model_catalog_entries.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_training_status", "training_jobs", ["status"])
    op.create_index("idx_training_jobs_train_job_spec", "training_jobs", ["train_job_spec"], postgresql_using="gin")

    # experiment_metrics
    op.create_table(
        "experiment_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("training_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.Text()),
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["training_job_id"], ["training_jobs.id"], ondelete="CASCADE"),
    )

    # experiment_runs
    op.create_table(
        "experiment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("training_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tracking_system", sa.Text(), nullable=False),
        sa.Column("tracking_run_id", sa.Text(), nullable=False),
        sa.Column("experiment_name", sa.Text(), nullable=False),
        sa.Column("run_name", sa.Text()),
        sa.Column("parameters", postgresql.JSONB()),
        sa.Column("metrics", postgresql.JSONB()),
        sa.Column("artifact_uris", postgresql.JSONB()),
        sa.Column("status", sa.Text(), nullable=False, server_default="running"),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('running','completed','failed','killed')",
            name="ck_experiment_run_status",
        ),
        sa.UniqueConstraint("tracking_system", "tracking_run_id", name="uq_tracking_system_run_id"),
        sa.ForeignKeyConstraint(["training_job_id"], ["training_jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_experiment_run_training_job_id", "experiment_runs", ["training_job_id"])
    op.create_index(
        "idx_experiment_run_tracking_system_run_id",
        "experiment_runs",
        ["tracking_system", "tracking_run_id"],
    )
    op.create_index("idx_experiment_run_status", "experiment_runs", ["status"])

    # serving_endpoints
    op.create_table(
        "serving_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("route", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="deploying"),
        sa.Column("min_replicas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_replicas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("autoscale_policy", postgresql.JSONB()),
        sa.Column("prompt_policy_id", postgresql.UUID(as_uuid=True)),
        sa.Column("last_health_check", sa.TIMESTAMP(timezone=True)),
        sa.Column("rollback_plan", sa.Text()),
        sa.Column("runtime_image", sa.Text()),
        sa.Column("use_gpu", sa.Boolean()),
        sa.Column("cpu_request", sa.Text()),
        sa.Column("cpu_limit", sa.Text()),
        sa.Column("memory_request", sa.Text()),
        sa.Column("memory_limit", sa.Text()),
        sa.Column("deployment_spec", postgresql.JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("environment IN ('dev','stg','prod')", name="ck_serving_env"),
        sa.CheckConstraint(
            "status IN ('deploying','healthy','degraded','failed')",
            name="ck_serving_status",
        ),
        sa.UniqueConstraint("environment", "route", name="uq_serving_environment_route"),
        sa.ForeignKeyConstraint(["model_entry_id"], ["model_catalog_entries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prompt_policy_id"], ["prompt_templates.id"]),
    )
    op.create_index("idx_serving_env", "serving_endpoints", ["environment"])
    op.create_index(
        "idx_serving_endpoints_deployment_spec",
        "serving_endpoints",
        ["deployment_spec"],
        postgresql_using="gin",
    )

    # observability_snapshots
    op.create_table(
        "observability_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("serving_endpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("time_bucket", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("latency_p50", sa.Float()),
        sa.Column("latency_p95", sa.Float()),
        sa.Column("error_rate", sa.Float()),
        sa.Column("token_per_request", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.UniqueConstraint("serving_endpoint_id", "time_bucket", name="uq_observability_time_bucket"),
        sa.ForeignKeyConstraint(["serving_endpoint_id"], ["serving_endpoints.id"], ondelete="CASCADE"),
    )

    # serving_deployments
    op.create_table(
        "serving_deployments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("serving_endpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("serving_framework", sa.Text(), nullable=False),
        sa.Column("framework_resource_id", sa.Text(), nullable=False),
        sa.Column("framework_namespace", sa.Text(), nullable=False),
        sa.Column("replica_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("min_replicas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_replicas", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("autoscaling_metrics", postgresql.JSONB()),
        sa.Column("resource_requests", postgresql.JSONB()),
        sa.Column("resource_limits", postgresql.JSONB()),
        sa.Column("framework_status", postgresql.JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("min_replicas >= 0", name="check_min_replicas"),
        sa.CheckConstraint("max_replicas >= min_replicas", name="check_max_replicas"),
        sa.CheckConstraint(
            "replica_count >= min_replicas AND replica_count <= max_replicas",
            name="check_replica_count",
        ),
        sa.UniqueConstraint(
            "serving_framework",
            "framework_resource_id",
            "framework_namespace",
            name="uq_framework_resource",
        ),
        sa.ForeignKeyConstraint(["serving_endpoint_id"], ["serving_endpoints.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_serving_deployment_endpoint_id", "serving_deployments", ["serving_endpoint_id"])
    op.create_index(
        "idx_serving_deployment_framework_resource",
        "serving_deployments",
        ["serving_framework", "framework_resource_id", "framework_namespace"],
    )

    # evaluation_runs
    op.create_table(
        "evaluation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True)),
        sa.Column("prompt_template_id", postgresql.UUID(as_uuid=True)),
        sa.Column("run_type", sa.Text(), nullable=False),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("run_by", sa.Text()),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True)),
        sa.CheckConstraint(
            "run_type IN ('automated','human','llm_judge')",
            name="evaluation_runs_run_type_check",
        ),
        sa.ForeignKeyConstraint(
            ["model_entry_id"], ["model_catalog_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["dataset_records.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["prompt_template_id"], ["prompt_templates.id"], ondelete="SET NULL"
        ),
    )

    # workflow_pipelines
    op.create_table(
        "workflow_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_name", sa.Text(), nullable=False),
        sa.Column("orchestration_system", sa.Text(), nullable=False),
        sa.Column("workflow_id", sa.Text(), nullable=False),
        sa.Column("workflow_namespace", sa.Text(), nullable=False),
        sa.Column("pipeline_definition", postgresql.JSONB(), nullable=False),
        sa.Column("stages", postgresql.JSONB()),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("current_stage", sa.Text()),
        sa.Column("start_time", sa.TIMESTAMP(timezone=True)),
        sa.Column("end_time", sa.TIMESTAMP(timezone=True)),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','failed','cancelled')",
            name="check_workflow_pipeline_status",
        ),
        sa.CheckConstraint("retry_count >= 0", name="check_retry_count"),
        sa.CheckConstraint("max_retries >= 0", name="check_max_retries"),
        sa.UniqueConstraint(
            "orchestration_system",
            "workflow_id",
            "workflow_namespace",
            name="uq_orchestration_workflow",
        ),
    )
    op.create_index("idx_workflow_pipeline_status", "workflow_pipelines", ["status"])
    op.create_index(
        "idx_workflow_pipeline_orchestration_workflow",
        "workflow_pipelines",
        ["orchestration_system", "workflow_id", "workflow_namespace"],
    )

    # registry_models
    op.create_table(
        "registry_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_catalog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("registry_type", sa.Text(), nullable=False),
        sa.Column("registry_model_id", sa.Text(), nullable=False),
        sa.Column("registry_repo_url", sa.Text(), nullable=False),
        sa.Column("registry_version", sa.Text()),
        sa.Column("imported", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("imported_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("exported_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("registry_metadata", postgresql.JSONB()),
        sa.Column("sync_status", sa.Text(), nullable=False, server_default="never_synced"),
        sa.Column("last_sync_check", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "sync_status in ('synced','out_of_sync','never_synced')",
            name="check_registry_sync_status",
        ),
        sa.ForeignKeyConstraint(["model_catalog_id"], ["model_catalog_entries.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_registry_model_catalog_id", "registry_models", ["model_catalog_id"])
    op.create_index(
        "idx_registry_model_registry",
        "registry_models",
        ["registry_type", "registry_model_id"],
    )

    # dataset_versions
    op.create_table(
        "dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("dataset_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("versioning_system", sa.Text(), nullable=False),
        sa.Column("version_id", sa.Text(), nullable=False),
        sa.Column("parent_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("version_tag", sa.Text()),
        sa.Column("checksum", sa.Text(), nullable=False),
        sa.Column("storage_uri", sa.Text(), nullable=False),
        sa.Column("diff_summary", postgresql.JSONB()),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_size_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("compression_ratio", sa.Float()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.CheckConstraint("file_count >= 0", name="check_file_count"),
        sa.CheckConstraint("total_size_bytes >= 0", name="check_total_size"),
        sa.UniqueConstraint(
            "versioning_system", "version_id", "dataset_record_id", name="uq_versioning_system_version"
        ),
        sa.ForeignKeyConstraint(
            ["dataset_record_id"], ["dataset_records.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_version_id"], ["dataset_versions.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("idx_dataset_version_record_id", "dataset_versions", ["dataset_record_id"])
    op.create_index("idx_dataset_version_parent", "dataset_versions", ["parent_version_id"])
    op.create_index("idx_dataset_version_checksum", "dataset_versions", ["checksum"])

    # governance_policies
    op.create_table(
        "governance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("rules", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("last_reviewed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("scope IN ('model','dataset','user','project')", name="ck_governance_scope"),
        sa.CheckConstraint("status IN ('draft','active','retired')", name="ck_governance_status"),
        sa.UniqueConstraint("name", "scope", name="uq_governance_name_scope"),
    )

    # audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Text()),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB()),
        sa.Column("occurred_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("result IN ('allowed','denied')", name="ck_audit_result"),
    )
    op.create_index("idx_audit_resource", "audit_logs", ["resource_type", "resource_id"])

    # cost_profiles
    op.create_table(
        "cost_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("time_window", sa.Text(), nullable=False),
        sa.Column("gpu_hours", sa.Float()),
        sa.Column("token_count", sa.BigInteger()),
        sa.Column("cost_currency", sa.Text(), server_default="USD"),
        sa.Column("cost_amount", sa.Numeric(14, 2)),
        sa.Column("budget_variance", sa.Numeric(14, 2)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("resource_type IN ('training','serving')", name="ck_cost_resource_type"),
        sa.UniqueConstraint("resource_type", "resource_id", "time_window", name="uq_cost_resource_window"),
    )

    # integration_configs
    op.create_table(
        "integration_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("integration_type", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("environment", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("feature_flags", postgresql.JSONB()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "integration_type in ('experiment_tracking','serving','orchestration','registry','versioning')",
            name="check_integration_type",
        ),
        sa.CheckConstraint("environment in ('dev','stg','prod')", name="check_environment"),
        sa.UniqueConstraint(
            "integration_type", "tool_name", "environment", name="idx_integration_config_type_tool_env"
        ),
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("integration_configs")
    op.drop_table("cost_profiles")
    op.drop_index("idx_audit_resource", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("governance_policies")
    op.drop_index("idx_dataset_version_checksum", table_name="dataset_versions")
    op.drop_index("idx_dataset_version_parent", table_name="dataset_versions")
    op.drop_index("idx_dataset_version_record_id", table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_index("idx_registry_model_registry", table_name="registry_models")
    op.drop_index("idx_registry_model_catalog_id", table_name="registry_models")
    op.drop_table("registry_models")
    op.drop_index("idx_workflow_pipeline_orchestration_workflow", table_name="workflow_pipelines")
    op.drop_index("idx_workflow_pipeline_status", table_name="workflow_pipelines")
    op.drop_table("workflow_pipelines")
    op.drop_index("idx_serving_deployment_framework_resource", table_name="serving_deployments")
    op.drop_index("idx_serving_deployment_endpoint_id", table_name="serving_deployments")
    op.drop_table("serving_deployments")
    op.drop_table("observability_snapshots")
    op.drop_index("idx_serving_endpoints_deployment_spec", table_name="serving_endpoints")
    op.drop_index("idx_serving_env", table_name="serving_endpoints")
    op.drop_table("serving_endpoints")
    op.drop_table("evaluation_runs")
    op.drop_index("idx_experiment_run_status", table_name="experiment_runs")
    op.drop_index("idx_experiment_run_tracking_system_run_id", table_name="experiment_runs")
    op.drop_index("idx_experiment_run_training_job_id", table_name="experiment_runs")
    op.drop_table("experiment_runs")
    op.drop_table("experiment_metrics")
    op.drop_index("idx_training_jobs_train_job_spec", table_name="training_jobs")
    op.drop_index("idx_training_status", table_name="training_jobs")
    op.drop_table("training_jobs")
    op.drop_table("prompt_experiments")
    op.drop_table("prompt_templates")
    op.drop_table("catalog_entry_datasets")
    op.drop_index("idx_dataset_owner", table_name="dataset_records")
    op.drop_table("dataset_records")
    op.drop_index("idx_catalog_status", table_name="model_catalog_entries")
    op.drop_table("model_catalog_entries")

