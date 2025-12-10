# Data Model - 001-open-source-integration

## Entities

- **GpuTypeOption**
  - Fields: `id` (string, stable key), `label` (string, display), `enabled` (bool), `env` (enum: dev/stg/prod), `priority` (int, optional for ordering), `updated_at` (timestamp).
  - Rules: `id` must be lowercase kebab/pascal-safe; `label` non-empty; uniqueness per `env`.
  - Lifecycle: defined via config/DB; read-only to clients; toggled by admins via config changes.

- **TrainingJobRequest (delta)**
  - Fields (relevant): `resources.gpus`, `resources.gpu_type` (string, optional when CPU), `use_gpu` (bool).
  - Rules: if `use_gpu=true` then `resources.gpu_type` is required and must exist in `GpuTypeOption.enabled` for the target `env`; if `use_gpu=false`, `gpu_type` must be null/absent.

## Relationships
- `GpuTypeOption (env)` 1..n → `TrainingJobRequest.env` validation scope.

## Validation Logic
- Lookup by `env`: reject submission if requested `gpu_type` not in enabled list for that environment.
- Enforce case-insensitive match on `id`; store canonical `id`.
- Return ordered list to UI by `priority` then `label`.
# Data Model: Open Source Integration

**Branch**: `001-open-source-integration`  
**Date**: 2025-01-27  
**Related**: [spec.md](./spec.md), [research.md](./research.md)

---

## Overview

This document defines the data model for open-source tool integrations. The model extends existing platform entities with integration-specific metadata while maintaining backward compatibility. All integrations use adapter patterns with common interfaces, allowing tool swapping without schema changes.

---

## Integration Entities

### ExperimentRun (Integration Entity)

Represents a training job execution tracked in an open-source experiment tracking system (e.g., MLflow).

**Fields**:
- `id` (UUID, Primary Key): Platform-generated unique identifier
- `training_job_id` (UUID, Foreign Key → TrainingJob): Links to platform training job
- `tracking_system` (String): Tool identifier ("mlflow", "wandb", etc.)
- `tracking_run_id` (String): Run ID in the tracking system
- `experiment_name` (String): Experiment name in tracking system
- `run_name` (String): Run name/tag in tracking system
- `parameters` (JSONB): Hyperparameters and job configuration
- `metrics` (JSONB): Aggregated metrics (latest values)
- `artifact_uris` (JSONB): Array of artifact storage URIs
- `status` (String): Run status ("running", "completed", "failed", "killed")
- `start_time` (Timestamp): Run start time
- `end_time` (Timestamp, Nullable): Run end time
- `created_at` (Timestamp): Record creation time
- `updated_at` (Timestamp): Last update time

**Relationships**:
- Many-to-One with `TrainingJob`: One training job can have one experiment run (1:1 in practice, but allows multiple runs per job for retries)

**Validation Rules**:
- `tracking_system` must be one of supported systems (configurable)
- `tracking_run_id` must be unique per `tracking_system`
- `status` transitions: "running" → "completed"/"failed"/"killed"

**State Transitions**:
```
created → running → completed
                  → failed
                  → killed
```

---

### ServingDeployment (Integration Entity)

Represents a model serving endpoint deployed through an open-source serving framework (e.g., KServe, Ray Serve).

**Fields**:
- `id` (UUID, Primary Key): Platform-generated unique identifier
- `serving_endpoint_id` (UUID, Foreign Key → ServingEndpoint): Links to platform serving endpoint
- `serving_framework` (String): Framework identifier ("kserve", "ray_serve", etc.)
- `framework_resource_id` (String): Resource ID in the framework (e.g., InferenceService name, Ray Serve deployment name)
- `framework_namespace` (String): Kubernetes namespace for framework resource
- `replica_count` (Integer): Current replica count
- `min_replicas` (Integer): Minimum replicas for autoscaling
- `max_replicas` (Integer): Maximum replicas for autoscaling
- `autoscaling_metrics` (JSONB): Autoscaling configuration (CPU, memory, GPU thresholds)
- `resource_requests` (JSONB): Resource requests (CPU, memory, GPU)
- `resource_limits` (JSONB): Resource limits (CPU, memory, GPU)
- `framework_status` (JSONB): Framework-specific status (raw status from framework API)
- `created_at` (Timestamp): Record creation time
- `updated_at` (Timestamp): Last update time

**Relationships**:
- One-to-One with `ServingEndpoint`: Each serving endpoint has one deployment record

**Validation Rules**:
- `serving_framework` must be one of supported frameworks (configurable)
- `min_replicas` >= 0
- `max_replicas` >= `min_replicas`
- `replica_count` between `min_replicas` and `max_replicas`

**State Transitions**:
```
created → deploying → healthy
                   → degraded
                   → failed
```

---

### WorkflowPipeline (Integration Entity)

Represents a multi-stage pipeline definition and execution in an open-source orchestration tool (e.g., Argo Workflows).

**Fields**:
- `id` (UUID, Primary Key): Platform-generated unique identifier
- `pipeline_name` (String): User-defined pipeline name
- `orchestration_system` (String): Tool identifier ("argo_workflows", "kubeflow", etc.)
- `workflow_id` (String): Workflow ID in orchestration system
- `workflow_namespace` (String): Kubernetes namespace for workflow
- `pipeline_definition` (JSONB): Pipeline DAG definition (stages, dependencies, conditions)
- `stages` (JSONB): Array of stage definitions with metadata
- `status` (String): Pipeline status ("pending", "running", "succeeded", "failed", "cancelled")
- `current_stage` (String, Nullable): Currently executing stage name
- `start_time` (Timestamp, Nullable): Pipeline start time
- `end_time` (Timestamp, Nullable): Pipeline end time
- `retry_count` (Integer): Number of retries attempted
- `max_retries` (Integer): Maximum retries allowed
- `created_at` (Timestamp): Record creation time
- `updated_at` (Timestamp): Last update time

**Relationships**:
- One-to-Many with `TrainingJob`: Pipeline can contain multiple training jobs as stages
- One-to-Many with `EvaluationRun`: Pipeline can contain evaluation stages

**Validation Rules**:
- `orchestration_system` must be one of supported systems (configurable)
- `workflow_id` must be unique per `orchestration_system` and `workflow_namespace`
- `status` transitions follow orchestration system state machine
- `pipeline_definition` must be valid DAG (no cycles)

**State Transitions**:
```
created → pending → running → succeeded
                          → failed → retrying → running
                          → cancelled
```

---

### RegistryModel (Integration Entity)

Represents a model imported from or exported to an open-source model registry (e.g., Hugging Face Hub).

**Fields**:
- `id` (UUID, Primary Key): Platform-generated unique identifier
- `model_catalog_id` (UUID, Foreign Key → ModelCatalogEntry): Links to platform catalog entry
- `registry_type` (String): Registry identifier ("huggingface", "modelscope", etc.)
- `registry_model_id` (String): Model ID in registry (e.g., "microsoft/DialoGPT-medium")
- `registry_repo_url` (String): Repository URL in registry
- `registry_version` (String, Nullable): Specific version/tag in registry
- `imported` (Boolean): True if imported from registry, False if exported to registry
- `imported_at` (Timestamp, Nullable): Import timestamp
- `exported_at` (Timestamp, Nullable): Export timestamp
- `registry_metadata` (JSONB): Registry-specific metadata (model card, license, usage examples)
- `sync_status` (String): Sync status ("synced", "out_of_sync", "never_synced")
- `last_sync_check` (Timestamp, Nullable): Last time registry was checked for updates
- `created_at` (Timestamp): Record creation time
- `updated_at` (Timestamp): Last update time

**Relationships**:
- Many-to-One with `ModelCatalogEntry`: One catalog entry can have multiple registry links (import/export to different registries)

**Validation Rules**:
- `registry_type` must be one of supported registries (configurable)
- `registry_model_id` format validated per registry type
- `sync_status` transitions: "never_synced" → "synced" → "out_of_sync" → "synced"

**State Transitions**:
```
created → synced → out_of_sync → synced
```

---

### DatasetVersion (Integration Entity)

Represents a dataset version managed by an open-source data versioning tool (e.g., DVC).

**Fields**:
- `id` (UUID, Primary Key): Platform-generated unique identifier
- `dataset_record_id` (UUID, Foreign Key → DatasetRecord): Links to platform dataset record
- `versioning_system` (String): Tool identifier ("dvc", "lakefs", etc.)
- `version_id` (String): Version identifier in versioning system (e.g., DVC commit hash)
- `parent_version_id` (String, Nullable): Parent version ID for lineage tracking
- `version_tag` (String, Nullable): Human-readable version tag
- `checksum` (String): Dataset checksum/hash for integrity verification
- `storage_uri` (String): Storage URI for this version (object storage path)
- `diff_summary` (JSONB): Summary of changes from parent version (added/removed rows, schema changes)
- `file_count` (Integer): Number of files in this version
- `total_size_bytes` (BigInteger): Total dataset size in bytes
- `compression_ratio` (Float, Nullable): Compression ratio compared to full copy
- `created_at` (Timestamp): Version creation time
- `created_by` (String): User who created the version

**Relationships**:
- Many-to-One with `DatasetRecord`: One dataset can have multiple versions
- Self-referential (parent_version_id → version_id): Forms version lineage tree

**Validation Rules**:
- `versioning_system` must be one of supported systems (configurable)
- `version_id` must be unique per `versioning_system` and `dataset_record_id`
- `checksum` must match actual dataset files
- `parent_version_id` must reference existing version (or NULL for initial version)

**State Transitions**:
```
created → verified → active
```

---

## Integration Configuration Entities

### IntegrationConfig (Configuration Entity)

Stores configuration for open-source tool integrations.

**Fields**:
- `id` (UUID, Primary Key): Platform-generated unique identifier
- `integration_type` (String): Integration category ("experiment_tracking", "serving", "orchestration", "registry", "versioning")
- `tool_name` (String): Tool identifier ("mlflow", "kserve", "argo_workflows", "huggingface", "dvc")
- `enabled` (Boolean): Whether integration is enabled
- `environment` (String): Environment ("dev", "stg", "prod")
- `config` (JSONB): Tool-specific configuration (endpoints, credentials, resource limits)
- `feature_flags` (JSONB): Feature flags for gradual rollout
- `created_at` (Timestamp): Record creation time
- `updated_at` (Timestamp): Last update time

**Relationships**:
- None (standalone configuration)

**Validation Rules**:
- `integration_type` must be one of supported types
- `tool_name` must be one of supported tools for the integration type
- `environment` must be one of ("dev", "stg", "prod")
- `config` structure validated per tool

---

## Entity Relationships Diagram

```
TrainingJob ──1:1── ExperimentRun
    │
    └──1:N── WorkflowPipeline (as stage)

ServingEndpoint ──1:1── ServingDeployment

ModelCatalogEntry ──1:N── RegistryModel

DatasetRecord ──1:N── DatasetVersion
    │                    │
    └────────────────────┘ (parent_version_id self-reference)
```

---

## Migration Considerations

### Existing Entities (No Changes)

- `TrainingJob`: No schema changes. Integration metadata stored in `ExperimentRun`.
- `ServingEndpoint`: No schema changes. Framework-specific data in `ServingDeployment`.
- `ModelCatalogEntry`: No schema changes. Registry links in `RegistryModel`.
- `DatasetRecord`: No schema changes. Versioning data in `DatasetVersion`.

### Data Migration

1. **Experiment Tracking**: Existing experiment metrics in `ExperimentMetric` table remain. New experiments create `ExperimentRun` records linked to MLflow.
2. **Serving**: Existing serving endpoints continue working. New deployments create `ServingDeployment` records.
3. **Workflows**: New pipelines use `WorkflowPipeline` entity. Existing job scheduling remains unchanged.
4. **Registry**: Existing catalog entries unchanged. New imports/exports create `RegistryModel` records.
5. **Versioning**: Existing dataset versions remain. New versions use DVC and create `DatasetVersion` records.

### Backward Compatibility

- All existing queries and APIs continue to work
- Integration entities are additive (no breaking changes)
- Feature flags allow gradual migration
- Rollback removes integration entities without affecting core entities

---

## Indexes

**Performance Optimizations**:

```sql
-- ExperimentRun indexes
CREATE INDEX idx_experiment_run_training_job_id ON experiment_runs(training_job_id);
CREATE INDEX idx_experiment_run_tracking_system_run_id ON experiment_runs(tracking_system, tracking_run_id);
CREATE INDEX idx_experiment_run_status ON experiment_runs(status);

-- ServingDeployment indexes
CREATE INDEX idx_serving_deployment_endpoint_id ON serving_deployments(serving_endpoint_id);
CREATE INDEX idx_serving_deployment_framework_resource ON serving_deployments(serving_framework, framework_resource_id, framework_namespace);

-- WorkflowPipeline indexes
CREATE INDEX idx_workflow_pipeline_status ON workflow_pipelines(status);
CREATE INDEX idx_workflow_pipeline_orchestration_workflow ON workflow_pipelines(orchestration_system, workflow_id, workflow_namespace);

-- RegistryModel indexes
CREATE INDEX idx_registry_model_catalog_id ON registry_models(model_catalog_id);
CREATE INDEX idx_registry_model_registry ON registry_models(registry_type, registry_model_id);

-- DatasetVersion indexes
CREATE INDEX idx_dataset_version_record_id ON dataset_versions(dataset_record_id);
CREATE INDEX idx_dataset_version_parent ON dataset_versions(parent_version_id);
CREATE INDEX idx_dataset_version_checksum ON dataset_versions(checksum);
```

---

## Validation and Constraints

### Database Constraints

- Foreign key constraints ensure referential integrity
- Unique constraints on (`tracking_system`, `tracking_run_id`) for `ExperimentRun`
- Unique constraints on (`serving_framework`, `framework_resource_id`, `framework_namespace`) for `ServingDeployment`
- Unique constraints on (`orchestration_system`, `workflow_id`, `workflow_namespace`) for `WorkflowPipeline`
- Unique constraints on (`versioning_system`, `version_id`, `dataset_record_id`) for `DatasetVersion`

### Application-Level Validation

- Tool name validation against supported tools list (configurable)
- Status transition validation (state machine enforcement)
- JSONB schema validation for structured fields (`parameters`, `metrics`, `pipeline_definition`, etc.)
- Resource limit validation (replicas, resource requests/limits)

---

## Notes

- All integration entities use UUID primary keys for global uniqueness
- Timestamps use UTC timezone
- JSONB fields allow flexible schema evolution without migrations
- Soft deletes not implemented (hard deletes with cascade where appropriate)
- Audit logging handled at application level (not in database schema)

