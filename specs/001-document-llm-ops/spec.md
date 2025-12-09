# Feature Specification: LLM Ops Platform Documentation Alignment

**Feature Branch**: `001-document-llm-ops`  
**Created**: 2025-11-27  
**Status**: Draft  
**Input**: User description: "docs/ 아래 파일을 이용해서, 작성해봐"

## Overview

This specification captures the end-to-end product requirements for the internal
LLM Ops platform described across `docs/PRD.md`, `docs/Constitution.txt`, and
`docs/필수 기능 목록.md`. The platform must unify model, dataset, training,
serving, monitoring, evaluation, governance, and cost management capabilities so
researchers, data engineers, service developers, and operators can collaborate
through a single structured SDD and the `/llm-ops/v1` API surface. The scope
covers the MVP foundation plus expansion hooks for advanced GPU scheduling,
observability, and policy enforcement.

## Assumptions & Dependencies

- Kubernetes clusters with GPU nodes already exist; this project layers the
  orchestration and governance tooling on top of them.
- Vue.js UI, FastAPI backend, and PostgreSQL persistence remain the reference
  stack, but technology specifics stay outside this spec.
- All documentation deliverables must follow the seven-section structure in
  `docs/Constitution.txt`, and every feature change updates the relevant SDD
  section.
- Existing monitoring, alerting, and identity systems (Slack, email, SSO) are
  available for integration without needing custom development here.

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

> Constitution alignment: Tie each user story back to the appropriate SDD
> section (purpose/scope, functional design, or UI) and note any component,
> data-flow, or API contract artifacts that must be updated to keep the feature
> independently testable.

### User Story 1 - Governed Model & Dataset Catalog (Priority: P1)

Researchers and data engineers register models, datasets, and benchmark assets,
attach standardized metadata/model cards, and review lineage through the SDD
sections 1–3 without leaving the platform UI.

**Why this priority**: Catalog governance is prerequisite to every downstream
workflow (training, serving, evaluation) and prevents duplication and compliance
risks called out in the PRD pain points.

**Independent Test**: Seed the catalog with new model and dataset entries,
complete required metadata, and verify reviewers can approve or reject entries
while version history stays auditable.

**Acceptance Scenarios**:

1. **Given** a researcher uploads a new base model, **When** they submit the
   model card and lineage fields, **Then** the catalog stores the entry, assigns
   a version, and reviewers receive an approval task.
2. **Given** a researcher wants to register a model with actual model files,
   **When** they upload model artifacts (weights, configs, tokenizers) through
   the UI or API, **Then** the platform stores files in object storage, records
   the storage URI in the catalog entry, and validates file integrity before
   allowing serving deployment.
3. **Given** a user navigates to the catalog models list page, **When** they
   view the page, **Then** they can see all models in a table format with
   filtering by type, status, and owner team, and click through to detailed
   model views. (See `frontend/src/pages/catalog/ModelList.vue`)
4. **Given** a user views a model detail page, **When** they access a specific
   model, **Then** they can see complete model information including metadata,
   status, and update the model status (draft, pending_review, approved,
   rejected) according to the approval workflow. (See
   `frontend/src/pages/catalog/ModelDetail.vue`)
5. **Given** a user wants to create a new model, **When** they navigate to the
   model creation page, **Then** they can fill out model information including
   name, version, type, owner team, metadata, and lineage dataset IDs, and
   submit to create the catalog entry. (See `frontend/src/pages/catalog/ModelCreate.vue`)
6. **Given** a data engineer revises a dataset, **When** they trigger a new
   version, **Then** the platform compares diffs, runs PII checks, and blocks
   publication until quality gates pass.
7. **Given** a data engineer wants to upload a dataset, **When** they select
   files (CSV, JSONL, or Parquet) through the UI or API, **Then** the platform
   uploads files to object storage, validates file format and structure, stores
   the storage URI in the catalog entry, and triggers validation checks (PII
   scan, quality scoring). (See `frontend/src/pages/catalog/DatasetCreate.vue`)
8. **Given** a user wants to preview a dataset before using it for training,
   **When** they access the dataset preview, **Then** they can see sample rows,
   column schema, basic statistics (row count, file size, format), and navigate
   through paginated results. (See `frontend/src/pages/catalog/DatasetDetail.vue`)
9. **Given** a dataset validation completes, **When** a user views the dataset
   detail page, **Then** they can see PII scan results (status, detected PII
   types, locations), quality score breakdown, validation recommendations, and
   approval status. The dataset cannot be approved if PII scan fails or quality
   score is below the configured threshold.
10. **Given** a user navigates to the dataset list page, **When** they view the
    page, **Then** they can see all datasets in a table format with filtering by
    name, version, owner team, PII status, and quality score, and click through
    to detailed dataset views. (See `frontend/src/pages/catalog/DatasetList.vue`)
11. **Given** a user wants to register an external model (e.g., OpenAI GPT-4,
   Ollama llama2), **When** they select "External" as the model type and
   provide provider-specific configuration (API key, endpoint, model name),
   **Then** the platform creates a catalog entry with the provider information
   stored in metadata, skips file upload requirements, and allows the model to
   be deployed as a serving endpoint without Kubernetes deployment.

---

### User Story 2 - Automated Training & Experiment Tracking (Priority: P1)

ML engineers configure training jobs (fine-tuning, from-scratch, pre-training,
or distributed) that reserve GPU capacity, execute orchestrated pipelines, and
log experiments (parameters, artifacts, metrics) back into the SDD functional
design appendix.

**Why this priority**: Automated training unlocks the promised productivity
gains (faster experiments, reduced manual GPU allocation) and underpins the PRD
goal of experiment-driven development.

**Independent Test**: Submit a job from UI or API, observe GPU scheduling,
monitor logs/metrics, and verify the experiment record captures inputs/outputs
even if the run fails.

**Acceptance Scenarios**:

1. **Given** an engineer submits a fine-tuning job with a base model, **When**
   the job enters the queue, **Then** the scheduler reserves GPUs, loads the
   base model from the catalog, executes the fine-tuning pipeline, and emits
   live status plus retry controls.
2. **Given** an engineer wants to train a model from scratch, **When** they
   submit a from-scratch training job with architecture configuration (no base
   model required), **Then** the platform validates the architecture definition,
   reserves GPUs, initializes the model from scratch, executes the training
   pipeline, and creates a new model entry in the catalog upon completion.
3. **Given** an engineer wants to create a domain-specific base model, **When**
   they submit a pre-training job with a large dataset and architecture
   configuration, **Then** the platform validates the configuration, reserves
   extensive GPU resources, executes pre-training on the large dataset, and
   creates a new base model in the catalog that can be used for subsequent
   fine-tuning.
4. **Given** an engineer submits a distributed training job (fine-tuning,
   from-scratch, or pre-training), **When** the job is configured with multiple
   GPUs/nodes, **Then** the platform distributes the training workload across
   the specified resources, synchronizes gradients, and executes the training
   pipeline with improved efficiency and capacity.
5. **Given** a training failure, **When** operators inspect the experiment
   record, **Then** they see parameters, logs, and root-cause tags needed to
   restart or roll back.
6. **Given** a training job is running, **When** the training pod records
   metrics (loss, accuracy, etc.) during training, **Then** the platform stores
   metrics in the database, displays them in the experiment detail page with
   charts and tables, and training continues even if metric recording fails.
7. **Given** a user views an experiment detail page, **When** they access
   `/experiments/{jobId}`, **Then** they can see all recorded metrics grouped by
   name, displayed as charts showing trends over time and tables with detailed
   values, timestamps, and units.
8. **Given** a training job is submitted, **When** the backend detects local
   development environment (minikube), **Then** it automatically configures
   `API_BASE_URL` environment variable in training pods to use
   `host.minikube.internal:8000` so training pods can call the metrics API.
3. **Given** training jobs are submitted, **When** a user navigates to the
   training jobs list page, **Then** they can view all training jobs in a table
   format with filtering by status (queued, running, succeeded, failed, cancelled)
   and model ID, see job timeline (submitted, started, completed), and click
   through to detailed job views. (See `frontend/src/pages/training/JobList.vue`)
4. **Given** a user views a training job detail page, **When** they access a
   specific job, **Then** they can see complete job information including status,
   job type, model/dataset IDs, timeline visualization, and cancel running or
   queued jobs. The page automatically refreshes status for active jobs. (See
   `frontend/src/pages/training/JobDetail.vue`)
5. **Given** a user submits a training job, **When** the job is successfully
   submitted, **Then** they are automatically redirected to the job detail page
   to monitor the job progress.
6. **Given** a training job completes successfully, **When** an automatic
   evaluation is triggered (or manually executed), **Then** the platform runs
   evaluation against a benchmark dataset, calculates metrics (BLEU, ROUGE, F1,
   etc.), stores results in an EvaluationRun, and links it to the trained model
   version. (See `frontend/src/pages/evaluation/EvaluationRun.vue`)
7. **Given** a user wants to evaluate a model manually, **When** they select a
   model and benchmark dataset through the evaluation UI, **Then** they can
   configure evaluation parameters (metrics to calculate, sample size), execute
   the evaluation, and view results with visualizations and sample outputs.
   (See `frontend/src/pages/evaluation/EvaluationCreate.vue`)
8. **Given** evaluation results are available, **When** a user views the
   evaluation detail page, **Then** they can see automated metrics, human
   review results (if available), LLM Judge scores (if available), sample
   outputs, and comparison with previous evaluations. (See
   `frontend/src/pages/evaluation/EvaluationDetail.vue`)
9. **Given** multiple model versions need comparison, **When** a user selects
   multiple evaluations on the comparison page, **Then** they can see
   side-by-side metric comparisons, performance trends, and recommendations
   for model promotion. (See `frontend/src/pages/evaluation/EvaluationCompare.vue`)
10. **Given** a model requires human review, **When** evaluators are assigned
    evaluation tasks, **Then** they can view sample outputs, rate model
    performance according to rubrics, submit reviews, and the platform
    aggregates results with inter-annotator agreement metrics.

---

### User Story 3 - Standardized Serving & Prompt Operations (Priority: P2)

Service developers and prompt designers deploy vetted model versions to a
high-availability serving tier, manage prompt templates, and run A/B tests while
the `/llm-ops/v1` API contract remains uniform.

**Why this priority**: Consistent serving and prompt workflows directly impact
consumer teams and revenue-facing SLAs, so they must work independently of
training operations.

**Independent Test**: Promote a cataloged model to production, confirm the API
endpoint responds with the standardized payload, and validate prompt variants
can be rolled back without affecting other teams.

**Acceptance Scenarios**:

1. **Given** a model version passes evaluation, **When** a developer promotes it
   through the deployment wizard, **Then** the platform provisions serving pods,
   registers the `/llm-ops/v1` route, and emits audit logs.
2. **Given** two prompt templates, **When** a product owner runs an A/B test,
   **Then** the platform routes traffic per allocation, tracks performance, and
   recommends the winning template.
3. **Given** serving endpoints are deployed, **When** a user navigates to the
   serving endpoints list page, **Then** they can view all deployed models with
   their status, route, environment, and model information, and click through to
   detailed endpoint views.
4. **Given** a developer wants to programmatically manage serving endpoints,
   **When** they use the provided Python client or API examples, **Then** they
   can deploy, query, monitor, and rollback endpoints without manual UI
   interaction. (See `examples/serving_client.py` and `docs/serving-examples.md`)
5. **Given** a serving endpoint is deployed and healthy, **When** a user navigates
   to the chat test page, **Then** they can select the endpoint, send messages,
   and interact with the model through a web-based chat interface to verify
   inference functionality. (See `frontend/src/pages/serving/ChatTest.vue`)
6. **Given** an external model (e.g., OpenAI GPT-4) is registered in the
   catalog and approved, **When** a developer deploys it as a serving endpoint,
   **Then** the platform creates the endpoint without Kubernetes deployment,
   routes inference requests to the external API client, and returns responses
   through the same standardized API interface as internal models.
7. **Given** a serving endpoint uses an external model, **When** a user sends
   a chat completion request, **Then** the platform automatically routes the
   request to the appropriate external provider (OpenAI, Ollama, etc.) based on
   the model's metadata, handles API responses and errors consistently, and
   tracks token usage for cost management.
8. **Given** a developer deploys a serving endpoint with a specific runtime image
   (e.g., vLLM or TGI), **When** the platform detects the runtime type from the
   image name, **Then** it automatically configures runtime-specific arguments,
   environment variables, and health probes for optimal model serving.
9. **Given** a model is registered with Hugging Face model ID in metadata, **When**
   a developer deploys it using TGI runtime, **Then** the platform uses the
   Hugging Face model ID for direct download, avoiding S3 download and init
   container overhead.
10. **Given** a serving endpoint is deployed without GPU resources (CPU-only mode),
    **When** the platform configures the deployment, **Then** it automatically
    adjusts resource limits, sets CPU-specific environment variables, and configures
    runtime arguments for CPU mode (e.g., `--device cpu` for vLLM).
11. **Given** a serving endpoint deployment fails due to pod scheduling issues,
    **When** a user checks the endpoint status, **Then** the platform reports
    "deploying" status with details about scheduling failures (e.g., insufficient
    resources, node selector mismatches).
12. **Given** KServe is enabled in the platform configuration, **When** a developer
    deploys a serving endpoint, **Then** the platform creates a KServe InferenceService
    CRD instead of raw Kubernetes Deployment, and inference requests are routed through
    KServe's predictor service.

---

### User Story 4 - Operations, Governance & Cost Insights (Priority: P3)

Operators and admins monitor GPU health, token/cost usage, policy compliance,
and audit trails, raising alerts or enforcing RBAC without blocking other user
stories.

**Why this priority**: Governance and cost controls ensure sustainable platform
operation but can ship after catalog/training/serving slices are functional.

**Independent Test**: Simulate abnormal GPU usage or policy violations and
verify dashboards, alerts, and policy engines respond, while RBAC prevents
unauthorized access.

**Acceptance Scenarios**:

1. **Given** GPU utilization spikes, **When** thresholds breach, **Then** the
   system surfaces the cluster heatmap, issues alerts, and suggests scaling or
   job rebalancing.
2. **Given** a user attempts to access a restricted dataset, **When** RBAC
   policies evaluate the request, **Then** access is denied, logged, and
   security admins see the event in the audit console.

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

- Catalog entries missing mandatory metadata must be rejected with actionable
  validation feedback before they reach reviewers.
- Training jobs submitted without available GPU quota are queued with SLA
  countdowns; users can reprioritize or cancel without orphaning artifacts.
- Serving endpoints must continue returning `{status,message,data}` responses
  even when downstream model runtimes throw exceptions; failures populate
  `status=fail` and descriptive messages.
- DEV/STG/PROD environment drifts (e.g., different inference runtimes) trigger
  deployment blockers until configuration parity is documented.
- Cost dashboards must gracefully handle delayed billing feeds by backfilling
  once data arrives, without double-counting usage.

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: The platform MUST maintain a governed catalog for models,
  datasets, prompts, and benchmarks with required metadata, lineage links, and
  approval workflows per SDD Sections 1–3.
- **FR-001a**: The platform MUST support model file uploads (weights, configs,
  tokenizers, safetensors) to object storage, store the storage URI in catalog
  entries, and validate file integrity before allowing serving deployment.
- **FR-001b**: Users MUST be able to list and view all catalog models with
  filtering by type, status, and owner team, access detailed model information
  including metadata and status, and update model status through the catalog
  UI pages. (See `frontend/src/pages/catalog/ModelList.vue` and
  `frontend/src/pages/catalog/ModelDetail.vue`)
- **FR-001c**: The platform MUST support external model providers (e.g., OpenAI,
  Ollama) by allowing users to register external models in the catalog with
  provider-specific configuration (API keys, endpoints, model names) stored in
  metadata. External models MUST be accessible through the same serving API
  interface as internal models, with automatic routing to the appropriate
  external API client. External models MUST NOT require file uploads and MUST
  skip Kubernetes deployment while still being deployable as serving endpoints.
  (See `backend/src/serving/external_models.py` and `frontend/src/pages/catalog/ModelCreate.vue`)
- **FR-002**: Users MUST be able to create, compare, and publish model and
  dataset versions, including visual diffs, audit logs, and rollback controls.
- **FR-003**: Dataset ingestion MUST run automated quality, PII, and compliance
  checks before assets become available to training jobs.
- **FR-003a**: The platform MUST support dataset file uploads (CSV, JSONL, Parquet)
  to object storage, store the storage URI in catalog entries, and validate file
  format and structure before allowing training job usage. The platform MUST:
  - Provide a `POST /llm-ops/v1/catalog/datasets/{dataset_id}/upload` API endpoint
    that accepts multipart/form-data with dataset files
  - Support multiple file formats (CSV, JSONL, Parquet) with format validation
  - Store files in object storage (MinIO/S3) under `datasets/{dataset_id}/{version}/`
  - Update catalog entry with storage URI after successful upload
  - Validate file structure (schema, encoding, required columns) before acceptance
  - Provide upload progress tracking for large files
- **FR-003b**: Users MUST be able to preview dataset contents before using them
  for training. The platform MUST:
  - Provide a `GET /llm-ops/v1/catalog/datasets/{dataset_id}/preview` API endpoint
    that returns sample data (first N rows, configurable limit)
  - Display dataset schema/column information (column names, types, nullability)
  - Show basic statistics (total rows, column count, file size, format)
  - Support pagination for large datasets
  - Display preview in dataset detail UI pages
- **FR-003c**: Dataset validation MUST provide detailed quality and compliance
  reports. The platform MUST:
  - Run PII detection using configurable rules (regex patterns, NER models) and
    report detected PII types and locations
  - Calculate quality scores (0-100) based on:
    - Missing value percentage
    - Duplicate record percentage
    - Data distribution anomalies
    - Schema compliance
    - Format validation
  - Generate validation reports with:
    - PII scan results (status: pending, clean, failed) with detailed findings
    - Quality score breakdown by metric
    - Recommendations for data improvement
    - Block dataset approval if PII scan fails or quality score below threshold
- **FR-003d**: Users MUST be able to manage datasets through dedicated UI pages.
  The platform MUST:
  - Provide dataset list page with filtering by name, version, owner team, PII
    status, and quality score
  - Provide dataset detail page showing complete information, preview, validation
    results, and version history
  - Provide dataset creation/upload page with file upload, metadata input, and
    validation trigger
  - Display dataset status badges (PII status, quality score, approval status)
  - Support dataset version comparison with visual diffs
  - Enable dataset approval workflow (draft → under_review → approved/rejected)
- **FR-004**: Training orchestration MUST allow users to configure fine-tuning
  and distributed jobs, reserve GPU capacity, and define retry/on-failure
  behaviors without manual cluster interaction.
- **FR-004a**: Users MUST be able to list and view all training jobs with
  filtering by status (queued, running, succeeded, failed, cancelled) and model
  ID, access detailed job information including timeline (submitted, started,
  completed), and cancel queued or running jobs through the training UI pages.
  (See `frontend/src/pages/training/JobList.vue` and
  `frontend/src/pages/training/JobDetail.vue`)
- **FR-004b**: The platform MUST support multiple training job types to accommodate
  different learning approaches. The platform MUST:
  - Support **fine-tuning** (`jobType: "finetune"`): Requires a base model from
    the catalog, adapts the model to a specific task using a smaller dataset,
    typically faster and requires fewer resources than from-scratch training.
  - Support **from-scratch training** (`jobType: "from_scratch"`): Does not
    require a base model, trains a new model architecture from initialization,
    requires more GPU resources and training time, suitable for custom
    architectures or domain-specific models.
  - Support **pre-training** (`jobType: "pretrain"`): Trains a base model on
    large-scale data, typically produces a base model that can be used for
    subsequent fine-tuning, requires extensive GPU resources and long training
    duration.
  - Support **distributed training** (`jobType: "distributed"`): Can be applied
    to any training type (fine-tuning, from-scratch, pre-training), distributes
    training across multiple GPUs/nodes for faster training and larger model
    capacity.
  - Validate job type requirements (e.g., fine-tuning requires base model,
    from-scratch requires architecture definition, pre-training requires large
    dataset).
  - Allow users to specify training job type in job submission API and UI.
- **FR-004c**: For from-scratch and pre-training jobs, the platform MUST support
  architecture definition and initialization. The platform MUST:
  - Allow users to specify model architecture configuration (e.g., transformer
    config, layer counts, hidden dimensions) via hyperparameters or metadata.
  - Support initialization strategies (random, pretrained embeddings, custom
    weights) for from-scratch training.
  - Store architecture definitions in training job metadata for reproducibility.
  - Validate architecture configuration before job submission.
- **FR-004d**: The training subsystem MUST support CPU-only training when GPU
  resources are unavailable or not requested. The platform MUST:
  - Allow users to specify `useGpu` parameter (optional boolean, default: `true`)
    in training job submission API and UI
  - Support CPU-only resource allocation when `useGpu=false` is specified
  - Automatically adjust CPU and memory resource requests when GPU is not
    requested (e.g., increase CPU cores, allocate more memory for CPU-based
    training)
  - Queue training jobs when GPU quota is unavailable, but allow immediate
    execution with CPU-only configuration if `useGpu=false` is specified
  - Prevent training job failures due to insufficient GPU resources by allowing
    graceful fallback to CPU-only training
  - Support CPU-only training for development, testing, and small-scale
    fine-tuning scenarios
  - Provide environment variables for CPU-only training resource limits:
    `TRAINING_CPU_ONLY_CPU_REQUEST`, `TRAINING_CPU_ONLY_CPU_LIMIT`,
    `TRAINING_CPU_ONLY_MEMORY_REQUEST`, `TRAINING_CPU_ONLY_MEMORY_LIMIT`
- **FR-005**: Every training job MUST emit structured experiment records
  (parameters, logs, metrics, artifacts) that map back to catalog entries and
  remain queryable for comparisons.
- **FR-005f**: Training pods MUST be able to record experiment metrics during
  training execution. The platform MUST:
  - Provide `API_BASE_URL` environment variable to training pods when submitting
    jobs, allowing pods to call the metrics API endpoint
  - Support automatic detection of local development environment (minikube) and
    configure appropriate API URL (e.g., `host.minikube.internal:8000`)
  - Provide `POST /llm-ops/v1/training/jobs/{jobId}/metrics` API endpoint that
    accepts metric name, value, and optional unit from training pods
  - Store metrics in `ExperimentMetric` entities linked to training jobs
  - Continue training execution even if metric recording fails (non-blocking)
  - Support optional `apiBaseUrl` parameter in training job submission request
    to override default API URL configuration
  - Log metric recording attempts and failures for debugging
  - Provide `GET /llm-ops/v1/training/experiments/{jobId}` endpoint to retrieve
    all metrics for a training job
  - Display metrics in experiment detail UI pages with charts and tables
- **FR-005a**: The platform MUST support model evaluation execution and management
  after training completion. The platform MUST:
  - Provide a `POST /llm-ops/v1/evaluation/runs` API endpoint to execute model
    evaluation against benchmark datasets
  - Support automatic evaluation trigger after training job completion (optional)
  - Support manual evaluation execution through UI or API
  - Store evaluation results in `EvaluationRun` entities linked to model entries
  - Support evaluation scheduling for continuous evaluation (CI/CD style)
  - Link evaluation runs to training jobs for traceability
- **FR-005b**: The platform MUST support automated evaluation metrics calculation.
  The platform MUST:
  - Calculate standard NLP metrics: BLEU, ROUGE (ROUGE-1, ROUGE-2, ROUGE-L),
    F1 score, Exact Match (EM), Perplexity
  - Support task-specific metrics (e.g., accuracy for classification, F1 for
    NER, BLEU/ROUGE for generation)
  - Execute evaluation against benchmark datasets stored in the catalog
  - Generate evaluation reports with metric breakdowns and sample outputs
  - Store metrics in `EvaluationRun.metrics` (JSONB) for querying and comparison
  - Support batch evaluation (evaluate multiple models against same dataset)
- **FR-005c**: The platform MUST support human review workflow for model
  evaluation. The platform MUST:
  - Provide a `POST /llm-ops/v1/evaluation/runs/{runId}/human-review` API endpoint
    to submit human evaluation results
  - Assign evaluation tasks to human reviewers (role-based assignment)
  - Support evaluation criteria and rubrics definition
  - Collect human ratings (e.g., 1-5 scale, pass/fail, quality scores)
  - Aggregate multiple human reviews with inter-annotator agreement metrics
  - Store human review results in `EvaluationRun` with `run_type: "human"`
  - Support evaluation task management (assign, track progress, collect results)
- **FR-005d**: The platform MUST support LLM-based automatic evaluation (LLM Judge).
  The platform MUST:
  - Provide a `POST /llm-ops/v1/evaluation/runs/{runId}/llm-judge` API endpoint
    to execute LLM Judge evaluation
  - Support configurable evaluation criteria and prompts for LLM Judge
  - Use LLM models (from catalog) to evaluate model outputs
  - Calculate evaluation scores and confidence metrics
  - Store LLM Judge results in `EvaluationRun` with `run_type: "llm_judge"`
  - Support multiple LLM Judge models for consensus evaluation
- **FR-005e**: Users MUST be able to manage evaluations through dedicated UI pages
  and APIs. The platform MUST:
  - Provide evaluation list page with filtering by model, dataset, run type,
    status, and date range
  - Provide evaluation detail page showing metrics, sample outputs, comparison
    with previous evaluations, and approval status
  - Provide evaluation execution page for manual evaluation trigger with
    benchmark dataset selection and evaluation configuration
  - Provide evaluation comparison page to compare multiple models/versions
    against the same benchmark dataset
  - Display evaluation results with visualizations (charts, tables, sample
    outputs)
  - Support evaluation result export (CSV, JSON) for reporting
  - Link evaluations to training jobs and model versions for traceability
- **FR-006**: The serving subsystem MUST deploy approved model versions into
  scalable inference endpoints with health probes, traffic policies, and defined
  rollback paths. For internal models, this MUST include Kubernetes deployment
  with Deployment, Service, HPA (Horizontal Pod Autoscaler), and Ingress
  resources. The deployment MUST support:
  - Automatic scaling based on CPU/memory utilization or custom metrics
  - Health checks via `/health` and `/ready` endpoints
  - Traffic routing through Ingress with proper path configuration
  - Resource limits and requests for GPU/CPU/memory allocation
  - Rollback capability to previous deployment versions
  - Kubernetes namespace mapping: The deployment environment (dev/stg/prod) MUST
    be mapped to Kubernetes namespaces with the `llm-ops-` prefix for resource
    isolation. All Kubernetes resources (Deployment, Service, HPA, Ingress) MUST
    be created in the namespace `llm-ops-{environment}` (e.g., `llm-ops-dev`,
    `llm-ops-stg`, `llm-ops-prod`).
- **FR-006a**: Users MUST be able to list and view all serving endpoints with
  filtering by environment, model, and status, and access detailed endpoint
  information including route, health status, scaling configuration, and bound
  model metadata.
- **FR-006b**: The platform MUST provide programmatic client libraries and
  examples (Python, JavaScript/TypeScript) for deploying, managing, and
  monitoring serving endpoints, documented in `examples/` and `docs/serving-examples.md`.
- **FR-006c**: Users MUST be able to interactively test serving endpoints through
  a web-based chat interface, allowing them to send messages, configure inference
  parameters (temperature, max tokens), and view model responses in real-time.
- **FR-006d**: The serving subsystem MUST support both internal models (deployed
  to Kubernetes) and external models (accessed via API) through a unified
  inference interface. External model requests MUST be routed to the appropriate
  provider client (OpenAI, Ollama, etc.) based on model metadata, with error
  handling and token usage tracking consistent across all model types.
- **FR-006e**: The serving subsystem MUST support CPU-only deployment when GPU
  resources are unavailable or not requested. The platform MUST:
  - Allow users to specify `useGpu` parameter (optional boolean) in deployment
    requests via the serving API (`POST /llm-ops/v1/serving/endpoints`)
  - Provide a global configuration setting `use_gpu` (default: `true`) that can
    be overridden per deployment request
  - Automatically adjust CPU and memory resource requests when GPU is not
    requested (e.g., increase CPU from 2 to 4 cores, memory limits remain
    configurable)
  - Support both KServe InferenceService and raw Kubernetes Deployment modes
    with CPU-only resource allocation
  - Prevent deployment failures due to insufficient GPU resources by allowing
    graceful fallback to CPU-only deployment
- **FR-006f**: The serving subsystem MUST support configurable resource limits
  (CPU, memory) for serving deployments. The platform MUST:
  - Provide environment variables for GPU-enabled resource limits:
    `SERVING_CPU_REQUEST`, `SERVING_CPU_LIMIT`, `SERVING_MEMORY_REQUEST`,
    `SERVING_MEMORY_LIMIT`
  - Provide environment variables for CPU-only resource limits:
    `SERVING_CPU_ONLY_CPU_REQUEST`, `SERVING_CPU_ONLY_CPU_LIMIT`,
    `SERVING_CPU_ONLY_MEMORY_REQUEST`, `SERVING_CPU_ONLY_MEMORY_LIMIT`
  - Allow different resource configurations for local development (smaller
    values) and production (larger values)
  - Default to reasonable values suitable for local development (CPU: 1/2,
    Memory: 1Gi/2Gi for CPU-only, CPU: 1/2, Memory: 2Gi/4Gi for GPU-enabled)
- **FR-006g**: The serving API contract MUST capture rollout safety and model traceability:
  - `POST /llm-ops/v1/serving/endpoints` request MUST include `version` (model version string) and `rollbackPlan` (human-readable plan or runbook link) in addition to existing fields.
  - Serving endpoint responses MUST return `version`, `promptPolicyId`, `lastHealthCheck`, and `rollbackPlan` so that clients can audit deployed versions and rollback readiness.
  - `PATCH /llm-ops/v1/serving/endpoints/{endpointId}` MUST allow updating `autoscalePolicy`, `promptPolicyId`, and `status` while preserving existing rollback metadata.
- **FR-006h**: The serving subsystem MUST support per-endpoint override of the
  serving runtime image. The platform MUST:
  - Provide an optional `servingRuntimeImage` field on serving deployment and
    redeployment APIs (e.g., `POST /llm-ops/v1/serving/endpoints`,
    `POST /llm-ops/v1/serving/endpoints/{endpointId}/redeploy`) that, when set,
    overrides the global `serving_runtime_image` setting for that endpoint.
  - Allow users to select a serving runtime image from a curated list
    (e.g., vLLM, Text Generation Inference, custom images) via the serving
    endpoint deployment UI (`EndpointDeploy.vue`) and to specify a fully
    qualified custom image string.
  - Preserve the chosen runtime image on the endpoint entity so that subsequent
    redeploy operations reuse the same image unless explicitly overridden.
  - Clearly surface image-related deployment failures (e.g., ImagePullBackOff)
    in the UI and API responses with actionable error messages and remediation
    hints (such as trying an alternative image).
- **FR-006g**: The platform MUST provide comprehensive environment variable
  configuration support. The platform MUST:
  - Load configuration from `.env` file in the backend directory
  - Provide `env.example` template file with all available configuration options
  - Support environment-specific configurations (local development, cluster
    deployment, production)
  - Parse boolean values as lowercase `true`/`false` strings
  - Convert empty strings for optional fields to `None` automatically
  - Document all environment variables in `ENV_SETUP.md` with examples for each
    environment type
  - Support case-insensitive environment variable names
  - Ignore empty environment variables when loading configuration
- **FR-006i**: The serving subsystem MUST provide a safe endpoint deletion and
  model deletion flow with dependency awareness. The platform MUST:
  - Prevent deletion of a model catalog entry if it is referenced by active
    serving endpoints or training jobs, returning a clear error message
    indicating which resources block deletion.
  - Expose a model deletion API and UI action that, when allowed, deletes the
    catalog entry and performs best-effort cleanup of associated model files
    in object storage (e.g., deleting all objects under the model's `storage_uri`).
  - Expose a serving endpoint deletion API and UI action that deletes both the
    database record and associated Kubernetes resources (Deployment/Service/HPA/
    Ingress or KServe InferenceService), handling partial failures gracefully
    and surfacing status to the user.
  - Log all delete operations (model and endpoint) to the audit log with actor,
    resource identifiers, and result for governance traceability.
- **FR-006j**: The serving subsystem MUST support endpoint rollback and redeployment
  operations. The platform MUST:
  - Provide a `POST /llm-ops/v1/serving/endpoints/{endpointId}/rollback` API
    endpoint that reverts an endpoint to its previous deployment version.
  - Provide a `POST /llm-ops/v1/serving/endpoints/{endpointId}/redeploy` API
    endpoint that redeploys an endpoint with the same or updated configuration
    (e.g., GPU settings, runtime image).
  - Support optional parameters on redeploy for `useGpu` and `servingRuntimeImage`
    to allow configuration updates without full endpoint recreation.
  - Maintain deployment history to enable rollback operations.
- **FR-006k**: The serving subsystem MUST store the runtime image used for each
  endpoint deployment. The platform MUST:
  - Store the `runtime_image` field on the `ServingEndpoint` entity to track
    which container image is used for each endpoint.
  - Return the `runtimeImage` in serving endpoint responses for visibility and
    debugging purposes.
  - Preserve the runtime image across redeployments unless explicitly overridden.
- **FR-001d**: The catalog subsystem MUST support model status updates and deletion.
  The platform MUST:
  - Provide a `PATCH /llm-ops/v1/catalog/models/{modelId}/status` API endpoint
    that allows updating a model's status (draft, under_review, approved, deprecated).
  - Provide a `DELETE /llm-ops/v1/catalog/models/{modelId}` API endpoint that
    deletes a model catalog entry with dependency checking (prevents deletion if
    referenced by serving endpoints or training jobs).
  - Return clear error messages when deletion is blocked due to dependencies.
- **FR-010a**: The governance subsystem MUST provide additional policy and cost
  management APIs. The platform MUST:
  - Provide a `GET /llm-ops/v1/governance/policies/{policyId}` API endpoint that
    retrieves a specific governance policy by ID.
  - Provide a `GET /llm-ops/v1/governance/observability/cost-aggregate` API endpoint
    that returns aggregated cost summaries across resources, time windows, and
    resource types (training, serving).
  - Support filtering cost aggregates by resource type, start date, and end date.
- **FR-006l**: The platform MUST provide a unified inference API for chat completions.
  The platform MUST:
  - Provide a `POST /llm-ops/v1/serve/{route_name}/chat` API endpoint that accepts
    chat completion requests and routes them to the appropriate serving endpoint
    (internal or external models).
  - Support both internal models (deployed to Kubernetes) and external models
    (OpenAI, Ollama, etc.) through the same API interface.
  - Automatically detect the model type and route requests to the appropriate
    backend (Kubernetes pod or external API client).
  - Return standardized chat completion responses with message choices, token usage,
    and finish reasons.
  - Support inference parameters (temperature, max_tokens) in the request.
  - Apply prompt templates if configured for the endpoint.
- **FR-006m**: The serving subsystem MUST support automatic runtime detection and
  configuration for different serving runtimes (vLLM, Text Generation Inference).
  The platform MUST:
  - Automatically detect the serving runtime type from the container image name
    (e.g., "vllm" in image name indicates vLLM runtime, "text-generation" or "tgi"
    indicates TGI runtime).
  - Configure runtime-specific command arguments:
    - **vLLM**: `--model`, `--host`, `--port`, `--served-model-name` arguments.
      For CPU mode, `--device cpu` MUST be specified BEFORE `--model` to prevent
      device type inference failures.
    - **TGI**: `--model-id` (for Hugging Face model ID), `--hostname`, `--port`
      arguments. TGI prefers Hugging Face model IDs over S3 URIs.
  - Extract Hugging Face model ID from model metadata (`huggingface_model_id` field)
    when available, especially for TGI deployments.
  - Support fallback mechanisms when Hugging Face model ID is not available
    (e.g., init container for S3 download, local path configuration).
- **FR-006n**: The serving subsystem MUST configure runtime-specific environment
  variables for optimal model serving. The platform MUST:
  - **For TGI (Text Generation Inference)**:
    - Set `HF_HUB_DOWNLOAD_TIMEOUT` (default: 1800 seconds) for large model downloads
    - Configure `HF_HOME` to use ephemeral storage (`/tmp/hf_cache`) to prevent OOM
    - Disable progress bars (`HF_HUB_DISABLE_PROGRESS_BARS=1`) to reduce memory usage
    - Enable hf-transfer (`HF_HUB_ENABLE_HF_TRANSFER=1`) for faster downloads
    - Disable telemetry (`HF_HUB_DISABLE_TELEMETRY=1`)
    - Configure PyTorch CUDA allocation (`PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512`)
    - For CPU mode: Disable Triton (`DISABLE_TRITON=1`, `MAMBA_DISABLE_TRITON=1`)
      and disable torch compile (`TORCH_COMPILE_DISABLE=1`) to prevent driver errors
  - **For vLLM**:
    - Set `VLLM_LOGGING_LEVEL=DEBUG` for debugging device type issues
    - For CPU mode: Set `VLLM_USE_CPU=1`, `CUDA_VISIBLE_DEVICES=""`,
      `NVIDIA_VISIBLE_DEVICES=""`, and `VLLM_CPU_KVCACHE_SPACE=4` (GB)
  - **Common environment variables**:
    - `MODEL_STORAGE_URI`: S3 URI to model files
    - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`: From Kubernetes secrets
    - `AWS_ENDPOINT_URL`: From Kubernetes ConfigMap
    - `AWS_DEFAULT_REGION`: Default region for S3 access
- **FR-006o**: The serving subsystem MUST support init containers for model download
  when required. The platform MUST:
  - Use init containers for TGI deployments when Hugging Face model ID is not available
    in model metadata, downloading model files from S3 to a shared volume before
    the main container starts.
  - Configure init containers with:
    - AWS CLI image (`amazon/aws-cli:latest`) for S3 access
    - Object storage credentials from Kubernetes secrets
    - Separate resource limits (memory: 2Gi/4Gi, CPU: 1/2) to prevent OOM during
      download
    - EmptyDir volume (size limit: 100Gi, configurable) for sharing files with
      main container
  - Log warnings when TGI is deployed without Hugging Face model ID, recommending
    Hugging Face import to get `huggingface_model_id` in metadata.
  - Skip init container when Hugging Face model ID is available (TGI downloads
    directly from Hugging Face Hub).
- **FR-006p**: The serving subsystem MUST configure health probes appropriately for
  different runtimes. The platform MUST:
  - Configure liveness and readiness probes on `/health` and `/ready` endpoints
    (port 8000) for all serving containers.
  - **For TGI deployments**:
    - Set longer initial delay (300 seconds) to allow model download and loading
    - Increase failure thresholds (5 for liveness, 10 for readiness) to tolerate
      long download times
    - Use longer period (10 seconds) for readiness checks during download
  - **For vLLM deployments**:
    - Set shorter initial delay (120 seconds for liveness, 60 seconds for readiness)
    - Use standard failure thresholds (3) and periods (5-10 seconds)
  - Ensure probes do not interfere with model loading and allow sufficient time
    for large model downloads.
- **FR-006q**: The serving subsystem MUST normalize route paths for consistent
  Ingress configuration. The platform MUST:
  - Strip leading and trailing whitespace from route paths
  - Ensure routes start with `/` (absolute paths)
  - Remove trailing slashes (except for root path `/`)
  - Normalize routes before creating Ingress resources to prevent routing issues
- **FR-006r**: The serving subsystem MUST provide accurate endpoint status by checking
  actual pod status. The platform MUST:
  - Check pod phases (Pending, Running, Failed, Error) to determine endpoint health
  - Detect scheduling issues (Unschedulable, Insufficient resources) and report
    as "deploying" status
  - Count ready pods vs. total pods to determine "healthy", "degraded", or "failed"
    status
  - Support both KServe InferenceService pods (labeled with
    `serving.kserve.io/inferenceservice={endpoint_name}`) and raw Deployment pods
    (labeled with `app={endpoint_name}`)
  - Fall back to KServe condition status or Deployment status if pod status is
    unavailable
  - Map pod status to endpoint status: "healthy" (all pods running and ready),
    "degraded" (some pods ready), "failed" (any pod failed), "deploying" (pods
    pending or creating)
- **FR-006s**: The serving subsystem MUST configure image pull policy appropriately.
  The platform MUST:
  - Set `imagePullPolicy: IfNotPresent` for serving containers to avoid pulling
    latest from remote registry when local image exists, reducing ImagePullBackOff
    errors during frequent redeployments
  - Allow users to override image pull policy if needed for specific deployments
- **FR-006t**: The serving subsystem MUST pass model metadata to deployment functions.
  The platform MUST:
  - Extract model metadata from catalog entries and pass to deployment functions
  - Use metadata fields such as `huggingface_model_id` for runtime configuration
  - Support additional metadata fields for future runtime-specific configurations
  - Preserve metadata integrity during deployment and redeployment operations
- **FR-007**: Prompt management MUST support versioned templates, A/B testing,
  and quick rollback while capturing experiment outcomes and reviewer approvals.
- **FR-008**: Every `/llm-ops/v1` endpoint MUST reply with HTTP 200 +
  `{status,message,data}` on success, map client issues to 4xx, infrastructure
  issues to 5xx, and serialize errors into the same envelope.
- **FR-009**: Observability dashboards MUST surface latency, error rate, token
  usage, GPU utilization, and anomaly alerts with drill-down filters by user,
  team, model, and environment.
- **FR-010**: Governance controls MUST enforce RBAC, policy-driven model/data
  access, audit logging for every administrative action, and policy violation
  alerts within five minutes.
- **FR-011**: Cost management MUST attribute GPU and token spend to models,
  teams, and projects, offering budgeting targets and recommendations drawn from
  utilization trends.
- **FR-012**: Deployment workflows MUST capture DEV/STG/PROD topology deltas,
  backup plans, and maintenance procedures so reviewers can trace operational
  impacts before approval.

*Example of marking unclear requirements:*

- **FR-006**: System MUST authenticate users via [NEEDS CLARIFICATION: auth method not specified - email/password, SSO, OAuth?]
- **FR-007**: System MUST retain user data for [NEEDS CLARIFICATION: retention period not specified]

### Key Entities *(include if feature involves data)*

- **ModelCatalogEntry**: Represents a specific model family/version with model
  card metadata, lineage pointers to datasets, evaluation scores, deployment
  eligibility state, and storage URI pointing to model artifacts in object
  storage (e.g., `s3://models/{model_id}/{version}/`).
- **DatasetRecord**: Captures dataset versions, quality checks, PII scan
  outcomes, ownership, and approval/audit history.
- **TrainingJob**: Defines submitted training runs (fine-tuning, from-scratch,
  pre-training, or distributed) with resource requirements, pipeline stages,
  execution logs, and resulting artifacts. Includes job type, base model
  reference (if applicable for fine-tuning), architecture configuration (for
  from-scratch/pre-training), and training hyperparameters.
- **ServingEndpoint**: Describes deployed inference routes (environment,
  scaling policy, health status, bound model version, prompt routing rules) tied
  to the `/llm-ops/v1` contract. Includes `runtime_image` field to track the
  container image used for serving.
- **EvaluationRun**: Stores automated and human review results, benchmark
  datasets used, scoring metrics, and promotion/blocker decisions.
- **CostProfile**: Aggregates GPU, token, and storage consumption per model,
  team, or time window with budgeting thresholds and alert settings.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: 95% of new models and datasets complete catalog approval (metadata
  + compliance checks) within two business days.
- **SC-002**: Training job setup-to-launch time drops below 15 minutes and 90%
  of jobs automatically log experiment metadata without manual edits.
- **SC-003**: Serving deployments maintain 99.5% availability while median API
  response stays under 1 second for standard prompts.
- **SC-004**: Prompt experiments deliver statistically significant results within
  one week and reduce manual prompt rollback incidents by 50%.
- **SC-005**: Cost dashboard adoption leads to at least 20% reduction in idle
  GPU time and 15% reduction in unexpected token spend quarter-over-quarter.
- **SC-006**: Policy violations (unauthorized access, PII exposure) are detected
  and alerted within five minutes with 100% audit log coverage.

## Examples & Reference Materials

### Serving Client Examples

Comprehensive examples for using the serving APIs are provided:

- **Python Client Library**: [`examples/serving_client.py`](../../examples/serving_client.py)
  - Reusable `ServingClient` class for programmatic endpoint management
  - Full workflow examples (deploy, wait, health check, rollback)
  - Usage examples: `python examples/serving_client.py workflow`

- **Detailed Examples Guide**: [`docs/serving-examples.md`](../../docs/serving-examples.md)
  - Complete API usage examples (cURL, Python, JavaScript/TypeScript)
  - Endpoint deployment, querying, health checks, rollback procedures
  - Model inference examples (pending implementation)

- **Quickstart Integration**: See [Section 7 of quickstart.md](./quickstart.md#7-serving-examples--client-usage)
  - Getting started with the Python client
  - Common workflows and use cases

- **Frontend Chat Test Page**: [`frontend/src/pages/serving/ChatTest.vue`](../../frontend/src/pages/serving/ChatTest.vue)
  - Interactive web-based chat interface for testing serving endpoints
  - Endpoint selection, message history, and inference parameter controls
  - Real-time model interaction for verification and testing
  - Accessible via `/serving/chat` or `/serving/chat/:endpointId` routes

These examples support **FR-006b** and **FR-006c**, enabling developers to integrate serving
operations into their workflows without manual UI interaction and providing an interactive
interface for testing model inference.

### Catalog UI Pages

The platform provides comprehensive catalog management through dedicated frontend pages:

- **Model List Page**: [`frontend/src/pages/catalog/ModelList.vue`](../../frontend/src/pages/catalog/ModelList.vue)
  - Table-based model listing with columns for name, version, type, status, and owner team
  - Filtering capabilities by type (base, fine-tuned, external), status (draft, pending_review, approved, rejected), and owner team
  - Status and type badges with color coding for visual identification
  - "Create New Model" button linking to model creation page
  - Click-through navigation to model detail pages
  - Refresh functionality to reload model list

- **Model Detail Page**: [`frontend/src/pages/catalog/ModelDetail.vue`](../../frontend/src/pages/catalog/ModelDetail.vue)
  - Complete model information display including ID, name, version, type, status, owner team
  - Formatted metadata display (JSON viewer)
  - Model status update functionality with dropdown selector
  - Status transition support (draft → pending_review → approved/rejected)
  - "Back to List" navigation
  - Refresh functionality to reload model details

- **Model Create Page**: [`frontend/src/pages/catalog/ModelCreate.vue`](../../frontend/src/pages/catalog/ModelCreate.vue)
  - Form-based model creation with validation
  - Fields for name, version, type, owner team, metadata (JSON), and lineage dataset IDs
  - JSON metadata editor with validation
  - Lineage dataset ID input (comma-separated)
  - Success/error message display
  - Automatic redirect to model detail page after successful creation
  - Cancel button to return to list

- **Catalog Client**: [`frontend/src/services/catalogClient.ts`](../../frontend/src/services/catalogClient.ts)
  - `listModels()` - Retrieve all catalog models
  - `getModel(modelId)` - Get specific model details
  - `createModel(payload)` - Create new model entry
  - `updateModelStatus(modelId, status)` - Update model status

These pages support **FR-001b**, providing a complete UI for catalog management, model
registration, status tracking, and metadata management through the platform interface.

### Dataset UI Pages

The platform provides comprehensive dataset management through dedicated frontend pages:

- **Dataset List Page**: [`frontend/src/pages/catalog/DatasetList.vue`](../../frontend/src/pages/catalog/DatasetList.vue)
  - Table-based dataset listing with columns for name, version, owner team, PII status, quality score, and approval status
  - Filtering capabilities by name, version, owner team, PII status (pending, clean, failed), and quality score range
  - Status badges with color coding for visual identification (PII status, quality score ranges)
  - "Create New Dataset" button linking to dataset creation page
  - Click-through navigation to dataset detail pages
  - Refresh functionality to reload dataset list

- **Dataset Detail Page**: [`frontend/src/pages/catalog/DatasetDetail.vue`](../../frontend/src/pages/catalog/DatasetDetail.vue)
  - Complete dataset information display including ID, name, version, owner team, storage URI
  - Dataset preview section showing sample rows (first N rows, configurable limit)
  - Schema/column information display (column names, types, nullability)
  - Basic statistics (total rows, column count, file size, format)
  - Validation results section:
    - PII scan results (status, detected PII types, locations, recommendations)
    - Quality score breakdown by metric (missing values, duplicates, distribution, schema compliance)
    - Overall quality score (0-100) with visual indicator
  - Version history and comparison with visual diffs
  - Dataset approval workflow (draft → under_review → approved/rejected)
  - "Back to List" navigation
  - Refresh functionality to reload dataset details

- **Dataset Create Page**: [`frontend/src/pages/catalog/DatasetCreate.vue`](../../frontend/src/pages/catalog/DatasetCreate.vue)
  - Form-based dataset creation with validation
  - Fields for name, version, owner team, change log, and metadata (JSON)
  - File upload interface supporting CSV, JSONL, and Parquet formats
  - Drag-and-drop or file picker for dataset files
  - Upload progress tracking for large files
  - File format validation before upload
  - Automatic validation trigger after upload (PII scan, quality scoring)
  - Success/error message display
  - Automatic redirect to dataset detail page after successful creation
  - Cancel button to return to list

- **Dataset Client**: [`frontend/src/services/catalogClient.ts`](../../frontend/src/services/catalogClient.ts)
  - `listDatasets(filters?)` - Retrieve all datasets with optional filtering
  - `getDataset(datasetId)` - Get specific dataset details
  - `createDataset(payload)` - Create new dataset entry
  - `uploadDatasetFiles(datasetId, files)` - Upload dataset files
  - `previewDataset(datasetId, limit?)` - Get dataset preview (sample rows)
  - `getDatasetValidation(datasetId)` - Get validation results (PII scan, quality score)
  - `updateDatasetStatus(datasetId, status)` - Update dataset approval status

These pages support **FR-003a**, **FR-003b**, **FR-003c**, and **FR-003d**, providing a complete
UI for dataset management, file upload, preview, validation, and version control through the
platform interface.

### Training UI Pages

The platform provides comprehensive training job management through dedicated frontend pages:

- **Job List Page**: [`frontend/src/pages/training/JobList.vue`](../../frontend/src/pages/training/JobList.vue)
  - Table-based job listing with columns for ID, model ID, dataset ID, job type, status, and timeline (submitted, started, completed)
  - Filtering capabilities by status (queued, running, succeeded, failed, cancelled) and model ID
  - Status badges with color coding for visual identification (queued: yellow, running: blue, succeeded: green, failed: red, cancelled: gray)
  - "Submit New Job" button linking to job submission page
  - Click-through navigation to job detail pages
  - Cancel job functionality for queued or running jobs
  - Auto-refresh every 10 seconds for active jobs (queued or running)
  - Refresh button for manual updates

- **Job Detail Page**: [`frontend/src/pages/training/JobDetail.vue`](../../frontend/src/pages/training/JobDetail.vue)
  - Complete job information display including ID, model ID, dataset ID, job type, and status
  - Timeline visualization showing job progress (submitted → started → completed)
  - Status badges and job type indicators
  - Cancel job button (available for queued or running jobs)
  - Experiment URL link to view experiment details
  - Auto-refresh every 5 seconds for active jobs (queued or running)
  - Manual refresh button
  - "Back to Jobs" navigation link

- **Job Submit Page**: [`frontend/src/pages/training/JobSubmit.vue`](../../frontend/src/pages/training/JobSubmit.vue)
  - Form-based job submission with validation
  - Fields for job type selection (finetune, from_scratch, pretrain, distributed)
  - Conditional fields based on job type:
    - Fine-tuning: Base model selection (required), dataset selection (required)
    - From-scratch: Architecture configuration (required), dataset selection (required), base model selection (optional/disabled)
    - Pre-training: Architecture configuration (required), large dataset selection (required), base model selection (optional/disabled)
    - Distributed: Can be combined with any training type, additional GPU/node configuration
  - **CPU-only training option**: `useGpu` toggle (default: enabled) to allow CPU-only training for development/testing
  - GPU configuration (count, type, max duration) - shown when `useGpu=true`
  - CPU configuration (cores, memory) - shown when `useGpu=false`
  - Hyperparameters input (JSON editor) for architecture definition and training parameters
  - Model and dataset dropdowns populated from catalog
  - Job type-specific validation (e.g., fine-tuning requires base model, from-scratch requires architecture)
  - Success/error message display
  - Automatic redirect to job detail page after successful submission
  - Cancel button to return to list

- **Training Client**: [`frontend/src/services/trainingClient.ts`](../../frontend/src/services/trainingClient.ts)
  - `listJobs(filters?)` - Retrieve training jobs with optional filters (status, modelId)
  - `submitJob(request)` - Submit a new training job
  - `getJob(jobId)` - Get specific job details
  - `cancelJob(jobId)` - Cancel a queued or running job

These pages support **FR-004a**, providing a complete UI for training job management, submission,
monitoring, and cancellation through the platform interface.

### Evaluation UI Pages

The platform provides comprehensive model evaluation management through dedicated frontend pages:

- **Evaluation List Page**: [`frontend/src/pages/evaluation/EvaluationList.vue`](../../frontend/src/pages/evaluation/EvaluationList.vue)
  - Table-based evaluation listing with columns for ID, model ID, dataset ID, run type (automated, human, llm_judge), status, metrics summary, and date
  - Filtering capabilities by model, dataset, run type, status, and date range
  - Status badges with color coding for visual identification
  - "Create New Evaluation" button linking to evaluation execution page
  - Click-through navigation to evaluation detail pages
  - Refresh functionality to reload evaluation list

- **Evaluation Detail Page**: [`frontend/src/pages/evaluation/EvaluationDetail.vue`](../../frontend/src/pages/evaluation/EvaluationDetail.vue)
  - Complete evaluation information display including ID, model ID, dataset ID, run type, status, and execution timeline
  - Metrics visualization (charts, tables) showing BLEU, ROUGE, F1, Exact Match, and other calculated metrics
  - Sample outputs display (input, expected output, actual output, scores)
  - Comparison with previous evaluations (metric trends, performance changes)
  - Human review results section (if available): reviewer ratings, comments, inter-annotator agreement
  - LLM Judge results section (if available): LLM evaluation scores, confidence metrics, consensus results
  - Evaluation report export (CSV, JSON)
  - Link to training job that produced the evaluated model
  - "Back to List" navigation
  - Refresh functionality to reload evaluation details

- **Evaluation Create Page**: [`frontend/src/pages/evaluation/EvaluationCreate.vue`](../../frontend/src/pages/evaluation/EvaluationCreate.vue)
  - Form-based evaluation execution with validation
  - Fields for model selection (from catalog), benchmark dataset selection, evaluation type (automated, human, llm_judge, or combined)
  - Evaluation configuration:
    - Metrics to calculate (BLEU, ROUGE, F1, EM, etc.)
    - Sample size (for quick evaluation)
    - Evaluation criteria and rubrics (for human review)
    - LLM Judge model selection and prompts (for LLM Judge)
  - Automatic evaluation trigger option (after training completion)
  - Success/error message display
  - Automatic redirect to evaluation detail page after successful execution
  - Cancel button to return to list

- **Evaluation Compare Page**: [`frontend/src/pages/evaluation/EvaluationCompare.vue`](../../frontend/src/pages/evaluation/EvaluationCompare.vue)
  - Side-by-side comparison of multiple evaluations (different models or versions)
  - Metric comparison tables and charts
  - Performance trend visualization
  - Sample output comparison
  - Model promotion recommendations based on evaluation results
  - Export comparison reports

- **Evaluation Client**: [`frontend/src/services/evaluationClient.ts`](../../frontend/src/services/evaluationClient.ts)
  - `listEvaluations(filters?)` - Retrieve evaluations with optional filtering
  - `getEvaluation(evaluationId)` - Get specific evaluation details
  - `createEvaluation(request)` - Execute new evaluation
  - `submitHumanReview(evaluationId, review)` - Submit human review results
  - `executeLLMJudge(evaluationId, config)` - Execute LLM Judge evaluation
  - `compareEvaluations(evaluationIds)` - Compare multiple evaluations
  - `exportEvaluation(evaluationId, format)` - Export evaluation results

These pages support **FR-005a**, **FR-005b**, **FR-005c**, **FR-005d**, and **FR-005e**, providing a complete
UI for model evaluation execution, result viewing, human review workflow, LLM Judge evaluation,
and evaluation comparison through the platform interface.

### Model File Upload

The platform supports uploading actual model files (weights, configs, tokenizers) when
registering models in the catalog:

- **API Endpoint**: `POST /catalog/models/{model_id}/upload`
  - Accepts multipart/form-data with model files
  - Validates file types and sizes
  - Stores files in object storage (MinIO/S3) under `models/{model_id}/{version}/`
  - Updates catalog entry with storage URI
  - Returns upload status and storage location

- **Frontend Integration**: Model creation and detail pages support file upload
  - Drag-and-drop or file picker interface
  - Progress indicators for large file uploads
  - Support for multiple files (weights, config, tokenizer, etc.)
  - File validation before upload

- **Storage Structure**: Model files are organized in object storage as:
  ```
  models/
    {model_id}/
      {version}/
        weights.bin (or .safetensors)
        config.json
        tokenizer.json
        tokenizer_config.json
        ...
  ```

- **Validation**: Before allowing serving deployment, the platform validates:
  - File integrity (checksums)
  - Required files present (config, weights)
  - File format compatibility
  - Storage URI accessible

This functionality supports **FR-001a**, ensuring models can be registered with their
actual artifacts and deployed to serving endpoints.

### External Model Support

The platform supports external model providers (OpenAI, Ollama, etc.) through
a unified catalog and serving interface:

- **Model Registration**: External models can be registered in the catalog with
  type "external" and provider-specific configuration stored in metadata:
  - **OpenAI**: Requires `provider: "openai"`, `model_name` (e.g., "gpt-4",
    "gpt-3.5-turbo"), `api_key`, and optional `base_url`
  - **Ollama**: Requires `provider: "ollama"`, `model_name` (e.g., "llama2",
    "mistral"), and `endpoint` (e.g., "http://localhost:11434")

- **Frontend Integration**: The model creation UI (`ModelCreate.vue`) provides
  provider-specific configuration forms when "External" type is selected:
  - Provider selection dropdown (OpenAI/Ollama)
  - Provider-specific fields (API key, endpoint, model name)
  - File upload section is hidden for external models
  - Provider configuration is automatically added to metadata

- **Serving Integration**: External models are deployed as serving endpoints
  without Kubernetes deployment:
  - Endpoint status is immediately set to "healthy"
  - No container image or pod deployment required
  - Inference requests are routed to external API clients
  - Same standardized API interface as internal models

- **API Clients**: External model clients are implemented in
  `backend/src/serving/external_models.py`:
  - `OpenAIClient`: Handles OpenAI API requests with proper error handling
  - `OllamaClient`: Handles Ollama API requests, including streaming response
    parsing
  - `get_external_model_client()`: Factory function to create appropriate
    client based on model metadata

- **Inference Routing**: The inference API (`backend/src/api/routes/inference.py`)
  automatically detects external models and routes requests to the appropriate
  client, maintaining consistent response format and error handling.

This functionality supports **FR-001c** and **FR-006d**, enabling hybrid
deployment of internal and external models through a unified interface, as
specified in the PRD's "Hybrid Router" requirement.

### Additional Catalog Management APIs

The platform provides additional catalog management capabilities beyond the core
CRUD operations:

- **Model Status Update**: `PATCH /llm-ops/v1/catalog/models/{modelId}/status`
  - Allows updating model status (draft, under_review, approved, deprecated)
  - Supports status transitions for approval workflows
  - Returns updated model information

- **Model Deletion**: `DELETE /llm-ops/v1/catalog/models/{modelId}`
  - Deletes a model catalog entry with dependency checking
  - Prevents deletion if model is referenced by active serving endpoints or
    training jobs
  - Returns clear error messages when deletion is blocked
  - Performs best-effort cleanup of associated model files in object storage

These APIs support **FR-001d**, providing complete lifecycle management for
catalog entries.

### Dataset Management APIs

The platform provides comprehensive dataset management capabilities:

- **Dataset List**: `GET /llm-ops/v1/catalog/datasets`
  - Lists all datasets with optional filtering
  - Returns dataset ID, name, version, owner team, PII status, quality score, approval status
  - Supports query parameters for filtering

- **Dataset Creation**: `POST /llm-ops/v1/catalog/datasets`
  - Creates a new dataset catalog entry
  - Accepts name, version, owner team, change log, metadata
  - Returns dataset ID and initial status

- **Dataset File Upload**: `POST /llm-ops/v1/catalog/datasets/{dataset_id}/upload`
  - Accepts multipart/form-data with dataset files (CSV, JSONL, Parquet)
  - Validates file format and structure before acceptance
  - Stores files in object storage under `datasets/{dataset_id}/{version}/`
  - Updates catalog entry with storage URI
  - Triggers automatic validation (PII scan, quality scoring)
  - Returns upload status and storage location
  - Supports upload progress tracking

- **Dataset Preview**: `GET /llm-ops/v1/catalog/datasets/{dataset_id}/preview`
  - Returns sample data (first N rows, configurable via `limit` query parameter)
  - Includes schema/column information (column names, types, nullability)
  - Returns basic statistics (total rows, column count, file size, format)
  - Supports pagination for large datasets

- **Dataset Validation Results**: `GET /llm-ops/v1/catalog/datasets/{dataset_id}/validation`
  - Returns PII scan results (status, detected PII types, locations, recommendations)
  - Returns quality score breakdown by metric (missing values, duplicates, distribution, schema compliance)
  - Returns overall quality score (0-100)
  - Returns validation recommendations

- **Dataset Details**: `GET /llm-ops/v1/catalog/datasets/{dataset_id}`
  - Retrieves complete dataset information
  - Includes storage URI, PII status, quality score, approval status, version history

- **Dataset Status Update**: `PATCH /llm-ops/v1/catalog/datasets/{dataset_id}/status`
  - Updates dataset approval status (draft, under_review, approved, rejected)
  - Validates PII scan status and quality score before allowing approval
  - Returns updated dataset information

- **Dataset Version Comparison**: `GET /llm-ops/v1/catalog/datasets/{dataset_id}/versions/{version1}/compare/{version2}`
  - Compares two dataset versions
  - Returns visual diff summary (added/removed/modified rows, schema changes)
  - Highlights changes in data distribution

These APIs support **FR-003a**, **FR-003b**, **FR-003c**, and **FR-003d**, providing complete
dataset lifecycle management including file upload, preview, validation, and version control.

### Serving Endpoint Management APIs

The platform provides comprehensive serving endpoint management beyond basic
deployment:

- **Endpoint Rollback**: `POST /llm-ops/v1/serving/endpoints/{endpointId}/rollback`
  - Reverts an endpoint to its previous deployment version
  - For KServe InferenceServices: Scales down replicas to 0 (minReplicas=0, maxReplicas=0)
  - For raw Deployments: Scales down replicas to 0
  - Updates endpoint status and Kubernetes resources accordingly
  - Maintains deployment history for rollback operations

- **Endpoint Redeployment**: `POST /llm-ops/v1/serving/endpoints/{endpointId}/redeploy`
  - Redeploys an endpoint with the same or updated configuration
  - Supports optional query parameters:
    - `useGpu` (boolean): Override GPU setting
    - `servingRuntimeImage` (string): Override runtime image
    - `cpuRequest`, `cpuLimit`, `memoryRequest`, `memoryLimit` (string): Override resource limits
  - Allows configuration updates without full endpoint recreation
  - Preserves existing configuration unless explicitly overridden
  - Works with both KServe InferenceServices and raw Deployments

- **Endpoint Deletion**: `DELETE /llm-ops/v1/serving/endpoints/{endpointId}`
  - Deletes both the database record and associated Kubernetes resources
  - For KServe InferenceServices: Deletes InferenceService CRD (automatically cleans up resources)
  - For raw Deployments: Deletes Deployment, Service, HPA, and Ingress resources
  - Handles partial failures gracefully (e.g., if Kubernetes resources are
    already deleted)
  - Logs deletion operations to the audit log

- **Endpoint Status**: `GET /llm-ops/v1/serving/endpoints/{endpointId}`
  - Retrieves endpoint status by checking actual pod status for accuracy
  - For KServe: Checks InferenceService status and pod phases
  - For raw Deployments: Checks Deployment status and pod phases
  - Returns status: "healthy", "degraded", "failed", or "deploying"
  - Includes replica counts (total, ready, available)

- **Runtime Image Tracking**: Serving endpoints store and return the `runtimeImage`
  field to track which container image is used for each deployment. This supports
  debugging, version tracking, and ensures consistent redeployments.

- **KServe Support**: When `use_kserve=true` is configured, endpoints are deployed
  as KServe InferenceService CRDs instead of raw Kubernetes Deployments. The
  platform automatically:
  - Creates InferenceService with proper predictor configuration
  - Configures autoscaling (minReplicas, maxReplicas)
  - Sets route annotation for ingress routing
  - Handles KServe-specific status checking and rollback operations

These APIs support **FR-006j**, **FR-006k**, **FR-006m**, **FR-006n**, **FR-006p**,
and **FR-006r**, providing complete endpoint lifecycle management with support for
both KServe and raw Kubernetes deployments.

### Training API

The platform provides comprehensive training job management APIs:

- **Job List**: `GET /llm-ops/v1/training/jobs`
  - Lists all training jobs with optional filtering
  - Supports query parameters: `modelId` (filter by model ID), `status` (filter by status: queued, running, succeeded, failed, cancelled)
  - Returns list of jobs with ID, model ID, dataset ID, job type, status, and timeline (submitted, started, completed)
  - Jobs are ordered by submission time (most recent first)

- **Job Submission**: `POST /llm-ops/v1/training/jobs`
  - Submits a new training job (fine-tuning, from-scratch, pre-training, or distributed)
  - Accepts `jobType` parameter: `"finetune"`, `"from_scratch"`, `"pretrain"`, or `"distributed"`
  - Accepts optional `useGpu` parameter (boolean, default: `true`) to enable CPU-only training
  - Accepts optional `apiBaseUrl` parameter (string) to specify API base URL for metric recording
    - If not provided, uses `TRAINING_API_BASE_URL` setting from backend configuration
    - For local development with minikube, automatically detects and uses `host.minikube.internal:8000`
    - Format: `http://{host}:{port}/llm-ops/v1` (e.g., `http://host.minikube.internal:8000/llm-ops/v1`)
  - Validates job type-specific requirements:
    - Fine-tuning: Requires base model ID (must be approved in catalog)
    - From-scratch: Requires architecture configuration in hyperparameters, base model optional
    - Pre-training: Requires architecture configuration and large dataset, base model optional
    - Distributed: Can be combined with any training type
  - Validates dataset is approved before submission
  - Validates architecture configuration for from-scratch and pre-training jobs
  - When `useGpu=true` (default): Reserves GPU capacity based on job type and resource profile
  - When `useGpu=false`: Allocates CPU-only resources (no GPU requirements), suitable for development/testing
  - Sets `API_BASE_URL` environment variable in Kubernetes job pods to enable metric recording
  - Submits to Kubernetes scheduler with appropriate training pipeline and resource configuration
  - Returns job ID and initial status

- **Job Details**: `GET /llm-ops/v1/training/jobs/{jobId}`
  - Retrieves detailed information for a specific training job
  - Returns job status, timeline, model/dataset IDs, job type, and experiment URL
  - Supports real-time status monitoring

- **Job Cancellation**: `DELETE /llm-ops/v1/training/jobs/{jobId}`
  - Cancels a queued or running training job
  - Deletes associated Kubernetes job resources
  - Updates job status to "cancelled"
  - Only allows cancellation of queued or running jobs

- **Metric Recording**: `POST /llm-ops/v1/training/jobs/{jobId}/metrics`
  - Records experiment metrics from training pods during training execution
  - Accepts metric name, value, and optional unit
  - Stores metrics in `ExperimentMetric` entities linked to training jobs
  - Returns success/failure status with error details if recording fails
  - Training pods call this endpoint using `API_BASE_URL` environment variable
  - Metric recording failures do not stop training execution (non-blocking)

- **Experiment Metrics**: `GET /llm-ops/v1/training/experiments/{jobId}`
  - Retrieves all experiment metrics for a training job
  - Returns list of metrics with name, value, unit, and recorded timestamp
  - Metrics are ordered by recording time (ascending)
  - Used by experiment detail UI pages to display training progress

These APIs support **FR-004**, **FR-004a**, and **FR-005f**, providing complete training job lifecycle management
and experiment tracking through both API and UI interfaces.

### Evaluation API

The platform provides comprehensive model evaluation capabilities:

- **Evaluation List**: `GET /llm-ops/v1/evaluation/runs`
  - Lists all evaluation runs with optional filtering
  - Supports query parameters: `modelId` (filter by model), `datasetId` (filter by benchmark dataset),
    `runType` (filter by type: automated, human, llm_judge), `status` (filter by status),
    `startDate`, `endDate` (filter by date range)
  - Returns list of evaluations with ID, model ID, dataset ID, run type, status, metrics summary,
    and execution timeline
  - Evaluations are ordered by execution time (most recent first)

- **Evaluation Execution**: `POST /llm-ops/v1/evaluation/runs`
  - Executes model evaluation against a benchmark dataset
  - Accepts model ID, dataset ID, evaluation type (automated, human, llm_judge, or combined),
    evaluation configuration (metrics to calculate, sample size, criteria)
  - Validates model and dataset are approved before evaluation
  - For automated evaluation: Calculates metrics (BLEU, ROUGE, F1, EM, etc.) automatically
  - For human review: Creates evaluation tasks for human reviewers
  - For LLM Judge: Executes LLM-based evaluation with configurable prompts
  - Supports automatic evaluation trigger after training job completion (via webhook or polling)
  - Returns evaluation run ID and initial status

- **Evaluation Details**: `GET /llm-ops/v1/evaluation/runs/{runId}`
  - Retrieves detailed information for a specific evaluation run
  - Returns evaluation status, metrics (detailed breakdown), sample outputs, execution timeline,
    linked training job ID, and evaluation type
  - Includes human review results if available (ratings, comments, inter-annotator agreement)
  - Includes LLM Judge results if available (scores, confidence metrics, consensus)

- **Human Review Submission**: `POST /llm-ops/v1/evaluation/runs/{runId}/human-review`
  - Submits human evaluation results for an evaluation run
  - Accepts reviewer ID, ratings (per sample or overall), comments, and evaluation criteria scores
  - Aggregates multiple human reviews with inter-annotator agreement calculation
  - Updates evaluation run status and metrics with human review results

- **LLM Judge Execution**: `POST /llm-ops/v1/evaluation/runs/{runId}/llm-judge`
  - Executes LLM-based evaluation for an evaluation run
  - Accepts LLM Judge model ID (from catalog), evaluation prompts, and criteria
  - Uses LLM to evaluate model outputs and calculate scores
  - Supports multiple LLM Judge models for consensus evaluation
  - Updates evaluation run with LLM Judge results

- **Evaluation Comparison**: `GET /llm-ops/v1/evaluation/runs/compare`
  - Compares multiple evaluation runs (different models or versions)
  - Accepts query parameter `runIds` (comma-separated evaluation run IDs)
  - Returns side-by-side metric comparison, performance trends, and recommendations
  - Validates all evaluations use the same benchmark dataset for fair comparison

- **Evaluation Export**: `GET /llm-ops/v1/evaluation/runs/{runId}/export`
  - Exports evaluation results in specified format (CSV, JSON)
  - Includes metrics, sample outputs, and metadata
  - Supports filtering and formatting options

These APIs support **FR-005a**, **FR-005b**, **FR-005c**, **FR-005d**, and **FR-005e**, providing complete
model evaluation lifecycle management including automated metrics, human review workflow, LLM Judge
evaluation, and evaluation comparison through both API and UI interfaces.

### Inference API

The platform provides a unified inference API for chat completions:

- **Chat Completion Endpoint**: `POST /llm-ops/v1/serve/{route_name}/chat`
  - Accepts chat completion requests with message history
  - Supports inference parameters: `temperature` (0.0-2.0), `max_tokens` (1-4000)
  - Automatically routes requests to the appropriate backend:
    - **Internal models (KServe)**: Routes to KServe InferenceService predictor
      service (`{endpoint-name}-predictor-default.{namespace}.svc.cluster.local`)
      using OpenAI-compatible API at `/v1/chat/completions`
    - **Internal models (raw Deployment)**: Routes to Kubernetes Service
      (`{endpoint-name}-svc.{namespace}.svc.cluster.local:8000`) using
      OpenAI-compatible API at `/v1/chat/completions`
    - **External models**: Routes to external API clients (OpenAI, Ollama, etc.)
  - Supports local development override via `serving_local_base_url` setting
    (e.g., port-forwarded service at `http://localhost:8001`)
  - Applies prompt templates if configured for the endpoint
  - Returns standardized responses with:
    - Message choices (role, content, finish_reason)
    - Token usage (prompt_tokens, completion_tokens, total_tokens)
    - Standardized error handling with `{status, message, data}` envelope

- **Route Resolution**: The API automatically resolves route names to serving
  endpoints by searching across all environments (dev, stg, prod), preferring
  healthy endpoints. Routes are normalized (leading/trailing whitespace removed,
  absolute path ensured) before matching.

- **KServe Inference**: When KServe is enabled, inference requests are routed
  to KServe InferenceService predictor pods. KServe automatically handles:
  - Load balancing across predictor replicas
  - Autoscaling based on traffic
  - Canary deployments and traffic splitting (future)
  - Standardized inference API endpoints

- **Raw Deployment Inference**: When KServe is disabled, inference requests are
  routed directly to Kubernetes Service endpoints. The platform assumes:
  - Serving runtime exposes OpenAI-compatible API at `/v1/chat/completions`
  - Service is accessible via cluster DNS
  - Health probes are configured for endpoint availability

- **External Model Support**: External models are automatically detected based
  on model metadata and routed to the appropriate provider client, maintaining
  consistent response format and error handling.

This functionality supports **FR-006l**, **FR-006m**, and **FR-006q**, providing
a unified interface for model inference regardless of deployment type (KServe,
raw Kubernetes, or external API).

### Additional Governance APIs

The platform provides additional governance and observability capabilities:

- **Policy Retrieval**: `GET /llm-ops/v1/governance/policies/{policyId}`
  - Retrieves a specific governance policy by ID
  - Returns complete policy information including rules, scope, and status
  - Supports policy inspection and management workflows

- **Cost Aggregation**: `GET /llm-ops/v1/governance/observability/cost-aggregate`
  - Returns aggregated cost summaries across resources
  - Supports filtering by:
    - `resource_type` (training, serving)
    - `start_date` and `end_date` (datetime)
  - Returns aggregated metrics:
    - Total GPU hours
    - Total tokens
    - Total cost (with currency)
    - Resource count
  - Enables cost analysis and budgeting workflows

These APIs support **FR-010a**, providing comprehensive governance and cost
management capabilities.

## Assumptions & Open Issues

- The organization agrees on the initial taxonomy for models, datasets, and
  prompts; any changes are governed through the constitution amendment process.
- External model providers (e.g., OpenAI, Ollama) expose billing and usage hooks
  needed for unified cost reporting. External model support is implemented with
  provider-specific API clients that handle authentication, request formatting,
  and response parsing.
- Model inference API (`POST /llm-ops/v1/serve/{route_name}/chat`) supports
  both internal and external models through a unified interface. External models
  are automatically routed to the appropriate provider client based on model
  metadata.
- External model configuration (API keys, endpoints) is stored in model
  metadata. Security best practices should be followed for sensitive
  credentials (e.g., encryption at rest, secret management integration).
- **Kubernetes Deployment for Internal Models**: Internal models MUST be deployed
  to Kubernetes clusters as specified in FR-006. The platform uses the following
  approach:
  - **KServe Integration**: The platform uses KServe (Kubernetes-native model serving
    framework) for deploying internal models. KServe provides standardized inference
    APIs, automatic scaling, canary deployments, and traffic splitting capabilities.
    KServe is disabled by default (`use_kserve=false`) but can be enabled to use
    KServe InferenceService CRDs instead of raw Kubernetes Deployments. When KServe
    is disabled, the platform falls back to raw Kubernetes Deployments for legacy
    compatibility.
  - **KServe InferenceService CRD**: When KServe is enabled, the platform creates
    `InferenceService` CustomResources (API version `serving.kserve.io/v1beta1`)
    instead of raw Deployments. KServe automatically manages Deployments, Services,
    and autoscaling based on the InferenceService spec. The InferenceService includes:
    - Predictor container configuration (image, args, env, resources)
    - Min/max replicas for autoscaling
    - Route annotation (`serving.kserve.io/route`) for ingress routing
    - Resource requests and limits (CPU, memory, GPU)
  - **KServe Status Checking**: The platform checks KServe InferenceService status
    by querying the CustomResource status field, including:
    - Ready condition status
    - Component replicas (predictor readyReplicas, availableReplicas)
    - Pod status for accurate health reporting
  - **KServe Route Annotation**: Routes are stored in InferenceService annotations
    (`serving.kserve.io/route`) and normalized before storage (leading/trailing
    whitespace removed, absolute path ensured).
  - **Model Loading from Object Storage**: Internal models are loaded directly
    from object storage (MinIO/S3) using the `storage_uri` stored in the catalog
    entry. No separate container image build process is required for model files.
  - **Model Serving Runtime**: The platform uses a configurable model serving
    runtime (default: `ghcr.io/huggingface/text-generation-inference:latest` for
    TGI) that can load models from object storage at container startup. The runtime
    image is configurable via `serving_runtime_image` setting (supports vLLM, Text
    Generation Inference, etc.). The platform MUST handle cases where the specified
    image does not exist (ImagePullBackOff errors) by providing clear error messages
    and alternative image options.
  - **Object Storage Access**: Serving containers receive object storage credentials
    and endpoint configuration via Kubernetes secrets (`llm-ops-object-store-credentials`)
    and ConfigMaps (`llm-ops-object-store-config`). The `MODEL_STORAGE_URI` environment
    variable is set to the catalog entry's `storage_uri` (e.g., `s3://models/{model_id}/{version}/`).
  - **Deployment Validation**: Before deployment, the platform validates that the
    model entry has a `storage_uri` (model files must be uploaded via
    `POST /catalog/models/{model_id}/upload`).
  - **Container Image Registry**: The serving runtime images (vLLM, TGI, etc.)
    are pulled from public container registries (Docker Hub, Hugging Face, GitHub
    Container Registry, etc.) or can be configured to use private registries via
    Kubernetes image pull secrets.
  - **KServe Prerequisites**: KServe must be installed in the Kubernetes cluster
    before deploying models with `use_kserve=true`. The platform assumes KServe is
    installed in the `kserve` namespace (configurable via `kserve_namespace` setting).
    KServe requires Knative Serving and Istio for full functionality, but the platform
    can work with minimal KServe installation (InferenceService CRD only).
  - **KServe Rollback**: When rolling back KServe InferenceServices, the platform
    scales down replicas to 0 (minReplicas=0, maxReplicas=0) instead of deleting
    the resource, allowing for quick restoration if needed.
  - **KServe Deletion**: When deleting KServe InferenceServices, the platform uses
    the CustomObjectsApi to delete the InferenceService CRD, which automatically
    cleans up associated Kubernetes resources (Deployments, Services, etc.).
  - **Environment Configuration**: The platform uses environment variables for
    configuration, loaded from a `.env` file in the backend directory. A template
    file `env.example` is provided with all available configuration options. The
    platform MUST support:
    - Database connection URL configuration (PostgreSQL)
    - Redis connection URL configuration
    - Object storage (MinIO/S3) endpoint and credentials
    - Kubernetes configuration (kubeconfig path or in-cluster detection)
    - Serving runtime image configuration (vLLM, TGI, etc.)
    - Resource limits configuration (CPU, memory, GPU) for serving deployments
    - GPU fallback configuration (`use_gpu` setting to enable CPU-only deployment)
    - Environment-specific settings (local development vs. cluster deployment)
    - All boolean values MUST be parsed as lowercase `true`/`false` strings
    - Empty strings for optional fields MUST be converted to `None` automatically
    - Configuration MUST be documented in `ENV_SETUP.md` with environment-specific
      examples (local, cluster, production)
