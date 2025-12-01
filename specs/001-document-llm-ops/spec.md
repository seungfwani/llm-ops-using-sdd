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
   rejected). (See `frontend/src/pages/catalog/ModelDetail.vue`)
5. **Given** a user wants to create a new model, **When** they navigate to the
   model creation page, **Then** they can fill out model information including
   name, version, type, owner team, metadata, and lineage dataset IDs, and
   submit to create the catalog entry. (See `frontend/src/pages/catalog/ModelCreate.vue`)
6. **Given** a data engineer revises a dataset, **When** they trigger a new
   version, **Then** the platform compares diffs, runs PII checks, and blocks
   publication until quality gates pass.
7. **Given** a user wants to register an external model (e.g., OpenAI GPT-4,
   Ollama llama2), **When** they select "External" as the model type and
   provide provider-specific configuration (API key, endpoint, model name),
   **Then** the platform creates a catalog entry with the provider information
   stored in metadata, skips file upload requirements, and allows the model to
   be deployed as a serving endpoint without Kubernetes deployment.

---

### User Story 2 - Automated Training & Experiment Tracking (Priority: P1)

ML engineers configure fine-tuning or distributed training jobs that reserve GPU
capacity, execute orchestrated pipelines, and log experiments (parameters,
artifacts, metrics) back into the SDD functional design appendix.

**Why this priority**: Automated training unlocks the promised productivity
gains (faster experiments, reduced manual GPU allocation) and underpins the PRD
goal of experiment-driven development.

**Independent Test**: Submit a job from UI or API, observe GPU scheduling,
monitor logs/metrics, and verify the experiment record captures inputs/outputs
even if the run fails.

**Acceptance Scenarios**:

1. **Given** an engineer submits a fine-tuning job, **When** the job enters the
   queue, **Then** the scheduler reserves GPUs, executes the pipeline, and emits
   live status plus retry controls.
2. **Given** a training failure, **When** operators inspect the experiment
   record, **Then** they see parameters, logs, and root-cause tags needed to
   restart or roll back.

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
- **FR-004**: Training orchestration MUST allow users to configure fine-tuning
  and distributed jobs, reserve GPU capacity, and define retry/on-failure
  behaviors without manual cluster interaction.
- **FR-005**: Every training job MUST emit structured experiment records
  (parameters, logs, metrics, artifacts) that map back to catalog entries and
  remain queryable for comparisons.
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
- **TrainingJob**: Defines submitted fine-tuning or distributed training runs
  with resource requirements, pipeline stages, execution logs, and resulting
  artifacts.
- **ServingEndpoint**: Describes deployed inference routes (environment,
  scaling policy, health status, bound model version, prompt routing rules) tied
  to the `/llm-ops/v1` contract.
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
    KServe is enabled by default (`use_kserve=true`) but can be disabled to use raw
    Kubernetes Deployments for legacy compatibility.
  - **Model Loading from Object Storage**: Internal models are loaded directly
    from object storage (MinIO/S3) using the `storage_uri` stored in the catalog
    entry. No separate container image build process is required for model files.
  - **Model Serving Runtime**: The platform uses a configurable model serving
    runtime (default: `python:3.11-slim` for local testing, `ghcr.io/vllm/vllm:latest`
    for production) that can load models from object storage at container startup.
    The runtime image is configurable via `serving_runtime_image` setting (supports
    vLLM, Text Generation Inference, etc.). The platform MUST handle cases where
    the specified image does not exist (ImagePullBackOff errors) by providing
    clear error messages and alternative image options.
  - **KServe InferenceService**: When KServe is enabled, the platform creates
    `InferenceService` CustomResources instead of raw Deployments. KServe automatically
    manages Deployments, Services, and autoscaling based on the InferenceService spec.
  - **Object Storage Access**: Serving containers receive object storage credentials
    and endpoint configuration via Kubernetes secrets (`llm-ops-object-store-credentials`)
    and ConfigMaps (`llm-ops-object-store-config`). The `MODEL_STORAGE_URI` environment
    variable is set to the catalog entry's `storage_uri` (e.g., `s3://models/{model_id}/{version}/`).
  - **Deployment Validation**: Before deployment, the platform validates that the
    model entry has a `storage_uri` (model files must be uploaded via
    `POST /catalog/models/{model_id}/upload`).
  - **Container Image Registry**: The serving runtime images (vLLM, TGI, etc.)
    are pulled from public container registries (Docker Hub, Hugging Face, etc.)
    or can be configured to use private registries via Kubernetes image pull secrets.
  - **KServe Prerequisites**: KServe must be installed in the Kubernetes cluster
    before deploying models. The platform assumes KServe is installed in the
    `kserve` namespace (configurable via `kserve_namespace` setting).
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
