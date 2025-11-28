# Data Model: LLM Ops Platform Documentation Alignment

**Branch**: `001-document-llm-ops`  
**Date**: 2025-11-27

---

## Entity Overview

| Entity | Purpose | Key Relationships |
|--------|---------|-------------------|
| `ModelCatalogEntry` | Governs model families/versions, metadata, approvals | links to `DatasetRecord`, `EvaluationRun`, `ServingEndpoint`, `PromptTemplate` |
| `DatasetRecord` | Stores dataset versions, quality/PII checks, approvals | links to `ModelCatalogEntry`, `TrainingJob` |
| `PromptTemplate` | Manages reusable prompt variants and A/B experiments | links to `ModelCatalogEntry`, `ServingEndpoint`, `PromptExperiment` |
| `TrainingJob` | Represents fine-tuning/distributed jobs + experiment lineage | links to `ModelCatalogEntry`, `DatasetRecord`, `ExperimentMetric`, `Artifact` |
| `ServingEndpoint` | Captures deployed inference routes + scaling config | links to `ModelCatalogEntry`, `PromptTemplate`, `ObservabilitySnapshot` |
| `EvaluationRun` | Tracks automated/human evaluation outcomes | links to `ModelCatalogEntry`, `DatasetRecord`, `PromptTemplate` |
| `GovernancePolicy` | Defines RBAC scopes, policy bundles, compliance states | links to `AuditLog`, `CostProfile`, `UserAccount` |
| `CostProfile` | Aggregates GPU/token spend per model/team/time window | links to `ModelCatalogEntry`, `ServingEndpoint`, `TrainingJob` |

---

## ModelCatalogEntry

- **Fields**
  - `id (UUID, pk)`
  - `name (string, unique per organization)`
  - `version (semver string)`
  - `type (enum: base, fine-tuned, external)`
  - `status (enum: draft, under_review, approved, deprecated)`
  - `owner_team (string)`
  - `metadata (JSONB)` – model card content aligned to SDD sections
  - `storage_uri (string, nullable)` – URI to model artifacts in object storage (e.g., `s3://models/{model_id}/{version}/`)
  - `lineage.dataset_ids (UUID[])`
  - `evaluation_summary (JSONB)` – latest metrics references
  - `created_at / updated_at (timestamptz)`
- **Validation Rules**
  - `version` must be unique per `(name, type)`
  - `metadata` must include purpose, scope, contact, licensing
  - `status=approved` requires at least one `EvaluationRun` linked
- **State Transitions**
  1. `draft → under_review` when submitter requests approval.
  2. `under_review → approved` when reviewers sign off + policies satisfied.
  3. `approved → deprecated` when superseded or policy violation detected.

## DatasetRecord

- **Fields**
  - `id (UUID, pk)`
  - `name`
  - `version`
  - `storage_uri`
  - `pii_scan_status (enum: pending, clean, failed)`
  - `quality_score (0-100)`
  - `change_log (text)`
  - `owner_team`
  - `approved_at`
- **Validation**
  - New versions must include diff summary referencing prior version.
  - `pii_scan_status` must be `clean` before `approved_at` can be set.
- **Relationships**
  - Many-to-many with `ModelCatalogEntry`.
  - One-to-many with `TrainingJob` (as inputs).

## PromptTemplate & PromptExperiment

- **PromptTemplate Fields**
  - `id`, `name`, `version`, `language`, `content`, `context_tags (string[])`,
    `status (draft, live, retired)`
- **PromptExperiment Fields**
  - `id`, `template_a_id`, `template_b_id`, `allocation (percent split)`,
    `metric (enum: latency, CSAT, ROUGE, custom)`, `start_at`, `end_at`,
    `winner_template_id`
- **Validation**
  - `content` must pass prohibited token filters before becoming live.
  - Experiments must define stop conditions (time window or min traffic).

## TrainingJob & ExperimentMetric

- **TrainingJob Fields**
  - `id`, `model_entry_id`, `dataset_id`, `job_type (finetune, dist_train)`,
    `resource_profile (GPU count, memory)`, `scheduler_id`, `status
    (queued, running, succeeded, failed, cancelled)`, `retry_policy`,
    `submitted_by`, `submitted_at`, `started_at`, `completed_at`
- **ExperimentMetric Fields**
  - `id`, `training_job_id`, `name`, `value`, `unit`, `timestamp`
- **Validation**
  - Jobs must reference catalog-approved models/datasets.
  - Retry policy must cap at 3 automatic retries unless override approved.

## ServingEndpoint & ObservabilitySnapshot

- **ServingEndpoint Fields**
  - `id`, `model_entry_id`, `environment (DEV/STG/PROD)`, `route`, `min_replicas`,
    `max_replicas`, `autoscale_policy`, `prompt_policy_id`, `status
    (deploying, healthy, degraded, failed)`, `last_health_check`, `rollback_plan`
- **ObservabilitySnapshot Fields**
  - `id`, `serving_endpoint_id`, `time_bucket`, `latency_p50`, `latency_p95`,
    `error_rate`, `token_per_request`, `notes`
- **Validation**
  - PROD endpoints require documented rollback plan + backup.
  - Autoscale policy must include CPU/GPU + latency triggers.

## EvaluationRun

- **Fields**
  - `id`, `model_entry_id`, `dataset_id`, `prompt_template_id`, `type
    (automated, human, llm_judge)`, `metrics (JSONB)`, `status`, `notes`,
    `run_by`, `started_at`, `completed_at`
- **Validation**
  - Must reference immutable benchmark dataset snapshot.
  - Approval requires at least one automated + one human/LLM evaluation.

## GovernancePolicy, AuditLog, CostProfile

- **GovernancePolicy Fields**
  - `id`, `name`, `scope (model, dataset, user)`, `rules (JSONB)`, `status`,
    `last_reviewed_at`
- **AuditLog Fields**
  - `id`, `actor_id`, `action`, `resource_type`, `resource_id`, `result`,
    `metadata`, `timestamp`
- **CostProfile Fields**
  - `id`, `resource_type (training, serving)`, `resource_id`, `time_window`,
    `gpu_hours`, `token_count`, `cost_currency`, `cost_amount`, `budget_variance`
- **Validation**
  - Policies require reassessment every 90 days.
  - Audit logs must be immutable; deletions prohibited.
  - Cost profiles must reconcile with billing feeds before finalization.

---

## Relationships Diagram (Textual)

```text
DatasetRecord <--(many-to-many)--> ModelCatalogEntry <--(one-to-many)--> ServingEndpoint
      ↑                                           ↑                         ↑
      |                                           |                         |
 TrainingJob ------------------------------> EvaluationRun <----------- PromptTemplate
      |                                           |
      └----> ExperimentMetric                     └--> CostProfile (per model/run)

GovernancePolicy --> (enforces) --> {ModelCatalogEntry, DatasetRecord, ServingEndpoint}
AuditLog ----> records actions on all entities
```

This logical model feeds the PostgreSQL schema design and ensures each
requirement from the specification traces to stored data with auditability.

