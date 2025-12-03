# Tasks: LLM Ops Platform Documentation Alignment

**Input**: Design documents from `/specs/001-document-llm-ops/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Added only where required for contract validation or acceptance evidence.  
**Organization**: Tasks grouped by user story to keep work independently deliverable/testable.

## Format: `[ID] [P?] [Story] Description`

- `[P]` means task can run in parallel (different files, no blocking dependency).  
- `[USX]` labels tasks for specific user stories.  
- All descriptions include concrete file paths per constitution.

## Path Conventions

- Backend: `backend/src/...`, `backend/workers/...`, `backend/tests/...`
- Frontend: `frontend/src/...`, `frontend/tests/...`
- Contracts/tests: `specs/001-document-llm-ops/contracts/`, `backend/tests/contract/`
- Docs: `docs/`, `specs/001-document-llm-ops/*.md`

> Constitution alignment: Include explicit tasks for updating SDD sections, refreshing diagrams/data flows, validating `/llm-ops/v1` contracts, and documenting deployment/backups when touched.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Ensure repo structure, tooling, secrets, and documentation match the plan.

- [x] T001 Verify repo structure matches plan (`backend/`, `frontend/`, `infra/`) and log deviations in `specs/001-document-llm-ops/plan.md`.
- [x] T002 Install/lock backend dependencies (`backend/poetry.lock`) and frontend packages (`frontend/package-lock.json`) per Technical Context.
- [x] T003 Configure shared env templates (`backend/.env.example`, `frontend/.env.example`) with PostgreSQL, Redis, object storage, and telemetry placeholders.
- [x] T004 [P] Enable pre-commit + lint tooling in `.pre-commit-config.yaml`, `backend/pyproject.toml`, and `frontend/package.json`.
- [x] T005 [P] Update setup guidance in `specs/001-document-llm-ops/quickstart.md` reflecting dependency/bootstrap steps.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish shared schema, auth/policy, observability, and CI guardrails required by every story.

- [x] T006 Generate initial DB migrations for catalog/dataset/prompt/governance tables in `backend/src/catalog/migrations/`.
- [x] T007 Implement shared ORM models/repositories for core entities in `backend/src/catalog/models.py` and `backend/src/catalog/repositories.py`.
- [x] T008 Create FastAPI root app + router wiring for `/llm-ops/v1` in `backend/src/api/app.py` and `backend/src/api/routes/__init__.py`.
- [x] T009 [P] Add RBAC/policy middleware referencing governance policies in `backend/src/governance/middleware.py`.
- [x] T010 Configure observability hooks (structured logs, Prometheus metrics) in `backend/src/core/observability.py`.
- [x] T011 Wire Redis + object storage clients in `backend/src/core/clients/redis_client.py` and `backend/src/core/clients/object_store.py`.
- [x] T012 [P] Add CI workflow `.github/workflows/contracts.yml` running schemathesis against `specs/001-document-llm-ops/contracts/*.yaml`.
- [ ] T013 [P] Update SDD overview/system sections in `docs/Constitution.txt` referencing foundational changes.

**Checkpoint**: Backend skeleton, schema, auth/policy, and observability present; CI enforcing contracts.

---

## Phase 3: User Story 1 – Governed Model & Dataset Catalog (Priority: P1) 🎯 MVP

**Goal**: Provide catalog CRUD, lineage, approvals, and dataset quality gates.

**Independent Test**: Create model + dataset entries via UI/API, run PII/quality checks, and complete approval workflow without other systems.

### Implementation

- [x] T014 [P] [US1] Implement catalog services (CRUD, lineage, approvals) in `backend/src/catalog/services/catalog.py`.
- [x] T015 [P] [US1] Build dataset ingestion + PII scan pipeline in `backend/src/catalog/services/datasets.py`.
- [x] T016 [US1] Add catalog routers (`GET/POST /catalog/models`, approvals) in `backend/src/api/routes/catalog.py`.
- [x] T017 [US1] Create catalog Vue pages (list/detail/version diff) in `frontend/src/pages/catalog/`.
- [x] T018 [P] [US1] Implement catalog API client wrappers in `frontend/src/services/catalogClient.ts`.
- [x] T019 [US1] Add Playwright smoke tests for catalog workflows in `frontend/tests/catalog.spec.ts`.
- [x] T020 [US1] Write contract tests for catalog endpoints in `backend/tests/contract/test_catalog.py`.
- [x] T021 [US1] Update SDD Sections 1–3 in `docs/Constitution.txt` and `specs/001-document-llm-ops/plan.md` reflecting catalog/governance flow.

### Catalog UI Enhancement (FR-001b)

- [x] T071 [P] [US1] Enhance ModelList.vue with table-based listing, filtering (type, status, owner team), and status badges in `frontend/src/pages/catalog/ModelList.vue`.
- [x] T072 [P] [US1] Enhance ModelDetail.vue with complete model information display, status update dropdown, and metadata JSON viewer in `frontend/src/pages/catalog/ModelDetail.vue`.
- [x] T073 [P] [US1] Create ModelCreate.vue with form-based model creation, JSON metadata editor, and lineage dataset IDs input in `frontend/src/pages/catalog/ModelCreate.vue`.
- [x] T074 [P] [US1] Add updateModelStatus method to catalogClient in `frontend/src/services/catalogClient.ts`.
- [x] T075 [US1] Add router configuration for `/catalog/models/new` route in `frontend/src/router/index.ts`.

### Model File Upload (FR-001a)

- [x] T076 [US1] Create database migration to add `storage_uri` column to `model_catalog_entries` table in `backend/alembic/versions/`.
- [x] T077 [P] [US1] Update ModelCatalogEntry model with `storage_uri` field in `backend/src/catalog/models.py`.
- [x] T078 [P] [US1] Update ModelCatalogResponse schema to include `storage_uri` field in `backend/src/catalog/schemas.py`.
- [x] T079 [US1] Implement file upload service method in CatalogService to handle multipart uploads and object storage integration in `backend/src/catalog/services/catalog.py`.
- [x] T080 [US1] Add file validation logic (file types, sizes, required files) in `backend/src/catalog/services/catalog.py`.
- [x] T081 [US1] Implement POST /catalog/models/{model_id}/upload endpoint in `backend/src/api/routes/catalog.py`.
- [x] T082 [P] [US1] Add file upload UI component with drag-and-drop support to ModelCreate.vue in `frontend/src/pages/catalog/ModelCreate.vue`.
- [x] T083 [P] [US1] Add file upload UI component with progress tracking to ModelDetail.vue in `frontend/src/pages/catalog/ModelDetail.vue`.
- [x] T084 [P] [US1] Add uploadModelFiles method to catalogClient in `frontend/src/services/catalogClient.ts`.
- [x] T085 [P] [US1] Write contract test for upload endpoint in `backend/tests/contract/test_catalog.py`.
- [x] T086 [US1] Add E2E test for file upload workflow in `frontend/tests/catalog.spec.ts`.
- [x] T087 [US1] Update quickstart.md with object storage bucket setup and file upload workflow in `specs/001-document-llm-ops/quickstart.md`.

### External Model Support (FR-001c)

- [x] T088 [P] [US1] Extend ModelCatalogEntry model to support `type: "external"` in `backend/src/catalog/models.py`.
- [x] T089 [P] [US1] Update model creation schema to accept external model provider configuration (OpenAI, Ollama) in metadata in `backend/src/catalog/schemas.py`.
- [x] T090 [US1] Update catalog service to handle external model creation without file upload requirement in `backend/src/catalog/services/catalog.py`.
- [x] T091 [P] [US1] Update ModelCreate.vue to show provider-specific configuration fields when "External" type is selected in `frontend/src/pages/catalog/ModelCreate.vue`.
- [x] T092 [US1] Add validation logic for external model provider configuration (required fields per provider) in `backend/src/catalog/services/catalog.py`.
- [x] T093 [P] [US1] Update contract tests to cover external model creation in `backend/tests/contract/test_catalog.py`.
- [x] T094 [US1] Update spec.md with external model support documentation (FR-001c) in `specs/001-document-llm-ops/spec.md`.

### Model Status Update & Deletion (FR-001d)

- [x] T095 [P] [US1] Implement PATCH /catalog/models/{modelId}/status endpoint for status updates in `backend/src/api/routes/catalog.py`.
- [x] T096 [P] [US1] Implement DELETE /catalog/models/{modelId} endpoint with dependency checking in `backend/src/api/routes/catalog.py`.
- [x] T097 [US1] Add dependency checking logic to prevent deletion of models referenced by serving endpoints or training jobs in `backend/src/catalog/services/catalog.py`.
- [x] T098 [P] [US1] Add model deletion UI action to ModelDetail.vue with confirmation dialog in `frontend/src/pages/catalog/ModelDetail.vue`.
- [x] T099 [P] [US1] Add deleteModel method to catalogClient in `frontend/src/services/catalogClient.ts`.
- [x] T100 [P] [US1] Add contract tests for model status update and deletion endpoints in `backend/tests/contract/test_catalog.py`.
- [x] T101 [US1] Update spec.md with model status update and deletion requirements (FR-001d) in `specs/001-document-llm-ops/spec.md`.

### Dataset Management (FR-003a-d)

- [x] T167 [P] [US1] Implement POST /catalog/datasets/{dataset_id}/upload endpoint for dataset file uploads (CSV, JSONL, Parquet) in `backend/src/api/routes/catalog.py`.
- [x] T168 [US1] Add dataset file validation logic (format validation, structure validation, required columns) in `backend/src/catalog/services/datasets.py`.
- [x] T169 [US1] Implement dataset file storage in object storage under `datasets/{dataset_id}/{version}/` in `backend/src/catalog/services/datasets.py`.
- [x] T170 [US1] Add automatic validation trigger (PII scan, quality scoring) after dataset upload in `backend/src/catalog/services/datasets.py`.
- [x] T171 [P] [US1] Implement GET /catalog/datasets/{dataset_id}/preview endpoint with sample rows, schema, and statistics in `backend/src/api/routes/catalog.py`.
- [x] T172 [P] [US1] Implement GET /catalog/datasets/{dataset_id}/validation endpoint for PII scan and quality score results in `backend/src/api/routes/catalog.py`.
- [x] T173 [US1] Implement PII detection using configurable rules (regex patterns, NER models) in `backend/src/catalog/services/datasets.py`.
- [x] T174 [US1] Implement quality score calculation (missing values, duplicates, distribution, schema compliance) in `backend/src/catalog/services/datasets.py`.
- [x] T175 [P] [US1] Implement GET /catalog/datasets/{dataset_id}/versions/{version1}/compare/{version2} endpoint for version comparison in `backend/src/api/routes/catalog.py`.
- [x] T176 [P] [US1] Create DatasetList.vue page with table listing, filtering (name, version, owner team, PII status, quality score), and status badges in `frontend/src/pages/catalog/DatasetList.vue`.
- [x] T177 [P] [US1] Create DatasetDetail.vue page with dataset information, preview section, validation results, and version history in `frontend/src/pages/catalog/DatasetDetail.vue`.
- [x] T178 [P] [US1] Create DatasetCreate.vue page with form-based creation, file upload (CSV, JSONL, Parquet), drag-and-drop, and upload progress tracking in `frontend/src/pages/catalog/DatasetCreate.vue`.
- [x] T179 [P] [US1] Add dataset API client methods (listDatasets, getDataset, createDataset, uploadDatasetFiles, previewDataset, getDatasetValidation) to catalogClient in `frontend/src/services/catalogClient.ts`.
- [x] T180 [US1] Add router configuration for dataset routes (/catalog/datasets, /catalog/datasets/new, /catalog/datasets/:id) in `frontend/src/router/index.ts`.
- [x] T181 [P] [US1] Add contract tests for dataset endpoints (upload, preview, validation, version comparison) in `backend/tests/contract/test_catalog.py`.
- [x] T182 [US1] Add E2E tests for dataset management workflow (create, upload, preview, validate) in `frontend/tests/catalog.spec.ts`.
- [x] T183 [US1] Update spec.md with dataset management requirements (FR-003a-d) in `specs/001-document-llm-ops/spec.md`.

**Checkpoint**: Catalog slice independently functional and documented; constitutes MVP. Model file upload capability enables full model registration workflow. External model support enables hybrid deployment. Model lifecycle management (status update, deletion) complete. Dataset management with file upload, preview, validation, and version comparison complete.

---

## Phase 4: User Story 2 – Automated Training & Experiment Tracking (Priority: P1)

**Goal**: Submit GPU training jobs, reserve resources, log experiments, and handle retries.

**Independent Test**: Launch a job via UI/API, watch scheduling/logging, view experiment record, and recover from failure without other stories.

### Implementation

- [x] T022 [US2] Implement training job repositories in `backend/src/training/repositories.py` (models already exist in catalog/models.py).
- [x] T023 [P] [US2] Integrate Kubernetes scheduler client in `backend/src/training/scheduler.py`.
- [x] T024 [US2] Expose `/training/jobs` REST endpoints in `backend/src/api/routes/training.py`.
- [x] T025 [P] [US2] Implement experiment logging worker (`backend/workers/trainers/experiment_logger.py`) writing to MLflow-compatible store.
- [x] T026 [US2] Build training job submission/status UI in `frontend/src/pages/training/`.
- [x] T027 [US2] Create contract tests for training endpoints in `backend/tests/contract/test_training.py`.
- [x] T028 [US2] Add integration test simulating failure/retry in `backend/tests/integration/test_training_retries.py`.
- [x] T029 [US2] Document training workflow diagrams in `specs/001-document-llm-ops/plan.md` + update SDD functional section.

### Training Job Types & UI Enhancement (FR-004a-c)

- [x] T184 [P] [US2] Update training job submission schema to support jobType field (finetune, from_scratch, pretrain, distributed) in `backend/src/training/schemas.py`.
- [x] T185 [US2] Add job type validation logic (fine-tuning requires base model, from-scratch requires architecture) in `backend/src/api/routes/training.py`.
- [x] T186 [US2] Update training service to handle architecture configuration for from-scratch and pre-training jobs in `backend/src/training/services.py`.
- [x] T187 [US2] Update Kubernetes scheduler to support distributed training configuration (multiple GPUs/nodes) in `backend/src/training/scheduler.py`.
- [x] T188 [P] [US2] Enhance JobList.vue with filtering by status and model ID, auto-refresh for active jobs, and timeline display in `frontend/src/pages/training/JobList.vue`.
- [x] T189 [P] [US2] Enhance JobDetail.vue with timeline visualization, cancel functionality for queued/running jobs, and auto-refresh in `frontend/src/pages/training/JobDetail.vue`.
- [x] T190 [P] [US2] Create JobSubmit.vue with job type selection (finetune, from_scratch, pretrain, distributed), conditional fields based on job type, and GPU configuration in `frontend/src/pages/training/JobSubmit.vue`.
- [x] T191 [US2] Add conditional form fields in JobSubmit.vue (base model required for fine-tuning, architecture required for from-scratch, etc.) in `frontend/src/pages/training/JobSubmit.vue`.
- [x] T192 [P] [US2] Add job type-specific validation in frontend (e.g., fine-tuning requires base model selection) in `frontend/src/pages/training/JobSubmit.vue`.
- [x] T193 [P] [US2] Update trainingClient to support job type parameter in job submission in `frontend/src/services/trainingClient.ts`.
- [x] T194 [US2] Add router configuration for /training/jobs/new route in `frontend/src/router/index.ts`.
- [x] T195 [P] [US2] Update contract tests for training job submission with job types in `backend/tests/contract/test_training.py`.
- [x] T196 [US2] Add E2E tests for training job submission with different job types in `frontend/tests/training.spec.ts`.
- [x] T197 [US2] Update spec.md with training job types requirements (FR-004a-c) in `specs/001-document-llm-ops/spec.md`.

### CPU-Only Training Fallback (FR-004d)

- [x] T220 [P] [US2] Add useGpu parameter to training job submission schema in `backend/src/training/schemas.py`.
- [x] T221 [US2] Update training service to support CPU-only resource allocation when useGpu=false in `backend/src/training/services.py`.
- [x] T222 [P] [US2] Add CPU-only resource limit environment variables (TRAINING_CPU_ONLY_*) to settings in `backend/src/core/settings.py`.
- [x] T223 [US2] Update Kubernetes scheduler to support CPU-only training jobs without GPU requirements in `backend/src/training/scheduler.py`.
- [x] T224 [P] [US2] Add useGpu toggle option to JobSubmit.vue in `frontend/src/pages/training/JobSubmit.vue`.
- [x] T225 [P] [US2] Update trainingClient to support useGpu parameter in job submission in `frontend/src/services/trainingClient.ts`.
- [x] T226 [US2] Update contract tests for CPU-only training job submission in `backend/tests/contract/test_training.py`.
- [x] T227 [US2] Update spec.md with CPU-only training requirements (FR-004d) in `specs/001-document-llm-ops/spec.md`.

### Training Pod Metric Recording (FR-005f)

- [x] T228 [P] [US2] Add API_BASE_URL environment variable to training job pods in `backend/src/training/services.py`.
- [x] T229 [US2] Implement POST /training/jobs/{jobId}/metrics endpoint for metric recording from training pods in `backend/src/api/routes/training.py`.
- [x] T230 [US2] Implement GET /training/experiments/{jobId} endpoint to retrieve experiment metrics in `backend/src/api/routes/training.py`.
- [x] T231 [US2] Add apiBaseUrl optional parameter to TrainingJobRequest schema in `backend/src/training/schemas.py`.
- [x] T232 [US2] Implement local development environment detection (minikube) for automatic API URL configuration in `backend/src/training/services.py`.
- [x] T233 [US2] Add metric recording logic in training pod scripts with error handling and non-blocking behavior in `backend/src/training/services.py`.
- [x] T234 [US2] Update ExperimentDetail.vue to display metrics with charts and tables in `frontend/src/pages/training/ExperimentDetail.vue`.
- [x] T235 [US2] Add experiment link to JobDetail.vue in `frontend/src/pages/training/JobDetail.vue`.
- [x] T236 [US2] Update training contract tests to cover metric recording endpoints in `backend/tests/contract/test_training.py`.
- [x] T237 [US2] Update spec.md with metric recording requirements (FR-005f) in `specs/001-document-llm-ops/spec.md`.
- [x] T238 [US2] Update training.yaml contract with metric recording endpoints and schemas in `specs/001-document-llm-ops/contracts/training.yaml`.

**Checkpoint**: Training orchestration independently deployable with experiment lineage. Multiple training job types (finetune, from_scratch, pretrain, distributed) supported with appropriate validation and UI. CPU-only training fallback enables training on GPU-less servers for development and testing scenarios. Training pods can record experiment metrics during execution, with automatic local development environment detection for seamless metric recording in development setups.

---

## Phase 4.5: User Story 2.5 – Model Evaluation System (Priority: P1) 🎯 MVP Extension

**Goal**: Provide comprehensive model evaluation capabilities including automated metrics, human review workflow, LLM Judge, and evaluation comparison.

**Independent Test**: Execute evaluation against a benchmark dataset, view metrics and sample outputs, submit human review, run LLM Judge, and compare multiple evaluations without other systems.

### Evaluation APIs (FR-005a-e)

- [ ] T198 [P] [US2.5] Create EvaluationRun model in `backend/src/evaluation/models.py` (or extend existing model if present).
- [ ] T199 [P] [US2.5] Implement evaluation service with automated metrics calculation (BLEU, ROUGE, F1, EM, Perplexity) in `backend/src/evaluation/services.py`.
- [ ] T200 [US2.5] Implement POST /evaluation/runs endpoint for evaluation execution (automated, human, llm_judge, combined) in `backend/src/api/routes/evaluation.py`.
- [ ] T201 [US2.5] Add automated evaluation metrics calculation logic (BLEU, ROUGE, F1, EM, Perplexity) in `backend/src/evaluation/services.py`.
- [ ] T202 [US2.5] Implement human review workflow (task assignment, rubric collection, aggregation) in `backend/src/evaluation/services.py`.
- [ ] T203 [US2.5] Implement POST /evaluation/runs/{runId}/human-review endpoint for human review submission in `backend/src/api/routes/evaluation.py`.
- [ ] T204 [US2.5] Implement LLM Judge evaluation using LLM models from catalog in `backend/src/evaluation/services.py`.
- [ ] T205 [US2.5] Implement POST /evaluation/runs/{runId}/llm-judge endpoint for LLM Judge execution in `backend/src/api/routes/evaluation.py`.
- [ ] T206 [P] [US2.5] Implement GET /evaluation/runs endpoint with filtering (model, dataset, run type, status, date range) in `backend/src/api/routes/evaluation.py`.
- [ ] T207 [P] [US2.5] Implement GET /evaluation/runs/{runId} endpoint with detailed metrics, sample outputs, timeline in `backend/src/api/routes/evaluation.py`.
- [ ] T208 [P] [US2.5] Implement GET /evaluation/runs/compare endpoint for comparing multiple evaluations in `backend/src/api/routes/evaluation.py`.
- [ ] T209 [P] [US2.5] Implement GET /evaluation/runs/{runId}/export endpoint for exporting results (CSV, JSON) in `backend/src/api/routes/evaluation.py`.
- [ ] T210 [P] [US2.5] Create evaluation schemas (EvaluationRunRequest, EvaluationRunResponse, HumanReviewRequest, LLMJudgeRequest) in `backend/src/evaluation/schemas.py`.
- [ ] T211 [P] [US2.5] Create EvaluationList.vue page with table listing, filtering (model, dataset, run type, status, date range), and status badges in `frontend/src/pages/evaluation/EvaluationList.vue`.
- [ ] T212 [P] [US2.5] Create EvaluationDetail.vue page with metrics visualization, sample outputs, comparison with previous evaluations, and export functionality in `frontend/src/pages/evaluation/EvaluationDetail.vue`.
- [ ] T213 [P] [US2.5] Create EvaluationCreate.vue page with model/dataset selection, evaluation type configuration (automated, human, llm_judge), and evaluation parameters in `frontend/src/pages/evaluation/EvaluationCreate.vue`.
- [ ] T214 [P] [US2.5] Create EvaluationCompare.vue page with side-by-side comparison, metric comparison tables/charts, and model promotion recommendations in `frontend/src/pages/evaluation/EvaluationCompare.vue`.
- [ ] T215 [P] [US2.5] Create evaluationClient with methods (listEvaluations, getEvaluation, createEvaluation, submitHumanReview, executeLLMJudge, compareEvaluations, exportEvaluation) in `frontend/src/services/evaluationClient.ts`.
- [ ] T216 [US2.5] Add router configuration for evaluation routes (/evaluation, /evaluation/new, /evaluation/:id, /evaluation/compare) in `frontend/src/router/index.ts`.
- [ ] T217 [P] [US2.5] Add contract tests for evaluation endpoints in `backend/tests/contract/test_evaluation.py`.
- [ ] T218 [US2.5] Add E2E tests for evaluation workflow (create, view, compare, export) in `frontend/tests/evaluation.spec.ts`.
- [ ] T219 [US2.5] Create evaluation contract file (contracts/evaluation.yaml) with all evaluation endpoints in `specs/001-document-llm-ops/contracts/evaluation.yaml`.
- [ ] T220 [US2.5] Update spec.md with evaluation system requirements (FR-005a-e) in `specs/001-document-llm-ops/spec.md`.

**Checkpoint**: Model evaluation system independently functional with automated metrics, human review workflow, LLM Judge, and comparison capabilities. Evaluation UI pages complete.

---

## Phase 5: User Story 3 – Standardized Serving & Prompt Operations (Priority: P2)

**Goal**: Deploy approved models to `/llm-ops/v1` endpoints, manage prompt templates, and run A/B tests with rollback guarantees.

**Independent Test**: Promote a model to DEV/STG/PROD, confirm envelope compliance, and run prompt experiment that can roll back safely.

### Implementation

- [x] T030 [US3] Implement serving deployment controller in `backend/src/serving/services/deployer.py`.
- [x] T031 [P] [US3] Add `/serving/endpoints` routes enforcing `{status,message,data}` in `backend/src/api/routes/serving.py`.
- [x] T032 [US3] Build prompt template/A-B UI flows in `frontend/src/pages/prompts/`.
- [x] T033 [P] [US3] Implement prompt routing + experiment logic in `backend/src/serving/prompt_router.py`.
- [x] T034 [US3] Add contract tests for serving/prompts in `backend/tests/contract/test_serving.py`.
- [x] T035 [US3] Create deployment rollback automation script `infra/scripts/serving_rollback.sh`.
- [x] T036 [US3] Update quickstart deployment instructions for serving/prompt flows in `specs/001-document-llm-ops/quickstart.md`.

### Environment Variable Configuration (FR-006g)

- [x] T102 [P] [US3] Create env.example template file with all configuration options in `backend/env.example`.
- [x] T103 [P] [US3] Implement Pydantic Settings class with environment variable loading in `backend/src/core/settings.py`.
- [x] T104 [US3] Add support for boolean parsing (lowercase true/false) and empty string to None conversion in `backend/src/core/settings.py`.
- [x] T105 [P] [US3] Create ENV_SETUP.md documentation with environment-specific examples in `backend/ENV_SETUP.md`.
- [x] T106 [US3] Update quickstart.md with environment configuration instructions in `specs/001-document-llm-ops/quickstart.md`.

### CPU-Only Deployment Fallback (FR-006e)

- [x] T107 [P] [US3] Add useGpu parameter to serving deployment API endpoint in `backend/src/api/routes/serving.py`.
- [x] T108 [US3] Update deployer to support CPU-only resource allocation when useGpu=false in `backend/src/serving/services/deployer.py`.
- [x] T109 [P] [US3] Add CPU-only resource limit environment variables (SERVING_CPU_ONLY_*) to settings in `backend/src/core/settings.py`.
- [x] T110 [P] [US3] Update EndpointDeploy.vue to include useGpu toggle option in `frontend/src/pages/serving/EndpointDeploy.vue`.
- [x] T111 [US3] Update serving schemas to include useGpu field in `backend/src/serving/schemas.py`.
- [x] T112 [US3] Update spec.md with CPU-only deployment requirements (FR-006e) in `specs/001-document-llm-ops/spec.md`.

### Configurable Resource Limits (FR-006f)

- [x] T113 [P] [US3] Add environment variables for GPU-enabled resource limits (SERVING_CPU_REQUEST, SERVING_CPU_LIMIT, etc.) in `backend/src/core/settings.py`.
- [x] T114 [P] [US3] Add environment variables for CPU-only resource limits (SERVING_CPU_ONLY_*) in `backend/src/core/settings.py`.
- [x] T115 [US3] Update deployer to use configurable resource limits from settings in `backend/src/serving/services/deployer.py`.
- [x] T116 [US3] Update ENV_SETUP.md with resource limit configuration examples in `backend/ENV_SETUP.md`.
- [x] T117 [US3] Update spec.md with resource limits requirements (FR-006f) in `specs/001-document-llm-ops/spec.md`.

### Runtime Image Override (FR-006h)

- [x] T118 [P] [US3] Add servingRuntimeImage field to serving deployment schemas in `backend/src/serving/schemas.py`.
- [x] T119 [US3] Update deployer to support per-endpoint runtime image override in `backend/src/serving/services/deployer.py`.
- [x] T120 [P] [US3] Update EndpointDeploy.vue to include runtime image selection dropdown in `frontend/src/pages/serving/EndpointDeploy.vue`.
- [x] T121 [US3] Add runtime image validation and error handling for ImagePullBackOff errors in `backend/src/serving/services/deployer.py`.
- [x] T122 [P] [US3] Update serving endpoint responses to include runtimeImage field in `backend/src/serving/schemas.py`.
- [x] T123 [US3] Update spec.md with runtime image override requirements (FR-006h) in `specs/001-document-llm-ops/spec.md`.

### Runtime Image Tracking (FR-006k)

- [x] T124 [P] [US3] Create database migration to add runtime_image column to serving_endpoints table in `backend/alembic/versions/`.
- [x] T125 [P] [US3] Update ServingEndpoint model with runtime_image field in `backend/src/serving/models.py`.
- [x] T126 [US3] Update serving service to store runtime_image on deployment in `backend/src/serving/serving_service.py`.
- [x] T127 [US3] Update serving schemas to return runtimeImage in endpoint responses in `backend/src/serving/schemas.py`.
- [x] T128 [US3] Update spec.md with runtime image tracking requirements (FR-006k) in `specs/001-document-llm-ops/spec.md`.

### Endpoint Rollback & Redeployment (FR-006j)

- [x] T129 [US3] Implement POST /serving/endpoints/{endpointId}/rollback endpoint in `backend/src/api/routes/serving.py`.
- [x] T130 [US3] Implement POST /serving/endpoints/{endpointId}/redeploy endpoint with optional useGpu and servingRuntimeImage parameters in `backend/src/api/routes/serving.py`.
- [x] T131 [US3] Add deployment history tracking to enable rollback operations in `backend/src/serving/serving_service.py`.
- [x] T132 [P] [US3] Add rollback and redeploy UI actions to EndpointDetail.vue in `frontend/src/pages/serving/EndpointDetail.vue`.
- [x] T133 [P] [US3] Add rollbackEndpoint and redeployEndpoint methods to servingClient in `frontend/src/services/servingClient.ts`.
- [x] T134 [P] [US3] Add contract tests for rollback and redeploy endpoints in `backend/tests/contract/test_serving.py`.
- [x] T135 [US3] Update spec.md with rollback and redeploy requirements (FR-006j) in `specs/001-document-llm-ops/spec.md`.

### Endpoint Deletion with Dependency Awareness (FR-006i)

- [x] T136 [US3] Implement DELETE /serving/endpoints/{endpointId} endpoint with Kubernetes resource cleanup in `backend/src/api/routes/serving.py`.
- [x] T137 [US3] Add logic to delete both database record and Kubernetes resources (Deployment/Service/HPA/Ingress or KServe InferenceService) in `backend/src/serving/services/deployer.py`.
- [x] T138 [US3] Add graceful handling of partial failures (e.g., if Kubernetes resources already deleted) in `backend/src/serving/services/deployer.py`.
- [x] T139 [P] [US3] Add delete endpoint UI action to EndpointDetail.vue with confirmation dialog in `frontend/src/pages/serving/EndpointDetail.vue`.
- [x] T140 [P] [US3] Add deleteEndpoint method to servingClient in `frontend/src/services/servingClient.ts`.
- [x] T141 [US3] Add audit logging for endpoint deletion operations in `backend/src/governance/services/policies.py`.
- [x] T142 [US3] Update spec.md with endpoint deletion requirements (FR-006i) in `specs/001-document-llm-ops/spec.md`.

### External Model Serving Support (FR-006d)

- [x] T143 [P] [US3] Implement OpenAI client for external model inference in `backend/src/serving/external_models.py`.
- [x] T144 [P] [US3] Implement Ollama client for external model inference in `backend/src/serving/external_models.py`.
- [x] T145 [US3] Create factory function to get appropriate external model client based on model metadata in `backend/src/serving/external_models.py`.
- [x] T146 [US3] Update serving service to handle external model deployment without Kubernetes resources in `backend/src/serving/serving_service.py`.
- [x] T147 [US3] Update serving schemas to support external model endpoints in `backend/src/serving/schemas.py`.
- [x] T148 [US3] Update spec.md with external model serving requirements (FR-006d) in `specs/001-document-llm-ops/spec.md`.

### Unified Inference API (FR-006l)

- [x] T149 [US3] Implement POST /serve/{route_name}/chat endpoint for unified chat completions in `backend/src/api/routes/inference.py`.
- [x] T150 [US3] Add automatic routing logic to detect model type and route to appropriate backend (Kubernetes pod or external API client) in `backend/src/api/routes/inference.py`.
- [x] T151 [US3] Implement prompt template application if configured for endpoint in `backend/src/api/routes/inference.py`.
- [x] T152 [US3] Add support for inference parameters (temperature, max_tokens) in chat completion requests in `backend/src/api/routes/inference.py`.
- [x] T153 [US3] Implement standardized response format with message choices, token usage, and finish reasons in `backend/src/api/routes/inference.py`.
- [x] T154 [P] [US3] Add contract tests for unified inference API in `backend/tests/contract/test_serving.py`.
- [x] T155 [US3] Update spec.md with unified inference API requirements (FR-006l) in `specs/001-document-llm-ops/spec.md`.

### Chat Test UI (FR-006c)

- [x] T156 [P] [US3] Create ChatTest.vue page with endpoint selection, message history, and inference parameter controls in `frontend/src/pages/serving/ChatTest.vue`.
- [x] T157 [P] [US3] Add chat completion API client method to servingClient in `frontend/src/services/servingClient.ts`.
- [x] T158 [US3] Add routes for /serving/chat and /serving/chat/:endpointId in `frontend/src/router/index.ts`.
- [x] T159 [P] [US3] Add E2E tests for chat test page in `frontend/tests/serving.spec.ts`.
- [x] T160 [US3] Update spec.md with chat test UI requirements (FR-006c) in `specs/001-document-llm-ops/spec.md`.

**Checkpoint**: Serving/prompt subsystem independently testable with rollback support. Comprehensive serving features including CPU-only fallback, resource limits, runtime image override, rollback/redeploy, external model support, unified inference API, and chat test UI complete.

---

## Phase 6: User Story 4 – Operations, Governance & Cost Insights (Priority: P3)

**Goal**: Provide policy enforcement, auditability, dashboards, and cost attribution.

**Independent Test**: Trigger policy violation + cost anomaly and observe RBAC blocks, alerts, and dashboards without touching other stories.

### Implementation

- [x] T037 [US4] Implement governance policy CRUD/evaluation service in `backend/src/governance/services/policies.py`.
- [x] T038 [US4] Build observability/cost APIs (`/governance/policies`, `/observability/cost-profiles`, `/audit/logs`) in `backend/src/api/routes/governance.py`.
- [x] T039 [P] [US4] Create Grafana dashboards + alert rules in `infra/k8s/monitoring/`.
- [x] T040 [US4] Add governance dashboards/audit log UI in `frontend/src/pages/governance/`.
- [x] T041 [US4] Write contract tests for governance/observability endpoints in `backend/tests/contract/test_governance.py`.
- [x] T042 [US4] Implement scheduled cost aggregation worker in `backend/workers/evaluators/cost_aggregator.py`.
- [x] T043 [US4] Update documentation for governance & cost workflows in `docs/Constitution.txt` and `specs/001-document-llm-ops/plan.md`.

### Additional Governance APIs (FR-010a)

- [x] T161 [P] [US4] Implement GET /governance/policies/{policyId} endpoint to retrieve specific policy by ID in `backend/src/api/routes/governance.py`.
- [x] T162 [US4] Implement GET /governance/observability/cost-aggregate endpoint with filtering by resource_type, start_date, end_date in `backend/src/api/routes/governance.py`.
- [x] T163 [US4] Add cost aggregation service method to aggregate GPU hours, tokens, and cost across resources in `backend/src/governance/services/cost.py`.
- [x] T164 [P] [US4] Update governance schemas to include cost aggregate response schema in `backend/src/governance/schemas.py`.
- [x] T165 [P] [US4] Add contract tests for additional governance APIs in `backend/tests/contract/test_governance.py`.
- [x] T166 [US4] Update spec.md with additional governance API requirements (FR-010a) in `specs/001-document-llm-ops/spec.md`.

**Checkpoint**: Ops/governance slice independently enforces policies and surfaces costs. Additional governance APIs for policy retrieval and cost aggregation complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, performance, documentation sweep, and release readiness.

- [x] T044 [P] Improve global error handling/logging in `backend/src/api/middleware/error_handler.py`.
- [x] T045 [P] Run k6 load tests for serving/training endpoints and record metrics in `specs/001-document-llm-ops/research.md`.
- [x] T046 Validate quickstart instructions against actual deployment runs and update `specs/001-document-llm-ops/quickstart.md`.
- [x] T047 Audit documentation cross-links (PRD, constitution, plan) ensuring all sections updated.
- [x] T048 Conduct security/RBAC regression tests and log outcomes in `specs/001-document-llm-ops/plan.md`.

---

## Dependencies & Execution Order

### Phase Dependencies
- Setup → Foundational → User Stories → Polish.
- User stories align with priority order (US1, US2, US3, US4) but can overlap once Foundational is done and shared contracts in place.

### User Story Dependencies
- **US1 (catalog)**: baseline for other stories; no dependencies beyond Foundational (MVP).  
- **US1 Enhancement (catalog UI pages)**: extends US1; requires existing catalog API endpoints (T014-T016); can run in parallel with other US1 work.  
- **US1 Enhancement (model file upload)**: extends US1; requires database migration (T076) before service/API implementation; frontend UI (T082-T084) can run after backend API (T081) is complete.  
- **US1 Enhancement (external model support)**: extends US1; requires catalog API endpoints (T014-T016); can run in parallel with other US1 enhancements.  
- **US1 Enhancement (model status update & deletion)**: extends US1; requires catalog API endpoints (T014-T016); can run in parallel with other US1 enhancements.  
- **US1 Enhancement (dataset management)**: extends US1; requires catalog API endpoints (T014-T016) and dataset service (T015); can run in parallel with other US1 enhancements after T015.
- **US2 (training)**: depends on catalog entities for lineage references; uses US1 read-only.
- **US2 Enhancement (training job types & UI)**: extends US2; requires training API endpoints (T024); can run in parallel with other US2 work.
- **US2.5 (evaluation system)**: depends on catalog entities (models, datasets) and training jobs; can begin after US1 + US2 foundational work.  
- **US3 (serving/prompt)**: relies on approved catalog entries and evaluation outputs; can begin after US1 + Foundational.  
- **US3 Enhancement (endpoints list/view)**: extends US3; requires existing serving endpoints to be deployed (can run after T030-T036 complete).  
- **US3 Enhancement (client examples)**: extends US3; requires serving API endpoints to be functional; can run in parallel with other US3 enhancements after core serving functionality (T030-T036) is complete.  
- **US3 Enhancement (environment configuration)**: extends US3; foundational for all serving features; should complete early (T102-T106).  
- **US3 Enhancement (CPU-only deployment)**: extends US3; requires environment configuration (T102-T106) and deployer (T030); can run in parallel with resource limits (T113-T117).  
- **US3 Enhancement (resource limits)**: extends US3; requires environment configuration (T102-T106); can run in parallel with CPU-only deployment (T107-T112).  
- **US3 Enhancement (runtime image override)**: extends US3; requires runtime image tracking (T124-T128) and deployer (T030); can run in parallel with other enhancements.  
- **US3 Enhancement (runtime image tracking)**: extends US3; requires database migration (T124) before other runtime image features; should complete before runtime image override (T118-T123).  
- **US3 Enhancement (rollback/redeploy)**: extends US3; requires serving endpoints to be deployed (T030-T036); can run in parallel with deletion (T136-T142).  
- **US3 Enhancement (endpoint deletion)**: extends US3; requires serving endpoints to be deployed (T030-T036); can run in parallel with rollback/redeploy (T129-T135).  
- **US3 Enhancement (external model serving)**: extends US3; requires external model catalog support (T088-T094) and serving service (T030); enables unified inference API (T149-T155).  
- **US3 Enhancement (unified inference API)**: extends US3; requires external model serving (T143-T148) and serving endpoints (T030-T036); enables chat test UI (T156-T160).  
- **US3 Enhancement (chat test UI)**: extends US3; requires unified inference API (T149-T155); can run after inference API is complete.  
- **US4 (ops/governance)**: consumes metrics and policy hooks from earlier stories but most work (UI/dashboards) can proceed in parallel once observability is ready.  
- **US4 Enhancement (additional governance APIs)**: extends US4; requires governance service (T037); can run in parallel with other governance work.

### Within Each User Story
- Contract tests precede implementation when included.  
- Order: data models → services → API → UI → validation/logging → documentation.  
- Each story finishes with SDD/quickstart updates before moving on.

### Parallel Opportunities
- Setup tasks T003–T005.  
- Foundational tasks T007, T009, T011, T012, T013 operate on distinct files.  
- US1: T014, T015, T018 run concurrently.  
- US1 Enhancement (catalog UI pages): T071, T072, T073, T074, T075 can run in parallel after T016-T018 complete.  
- US1 Enhancement (model file upload): T077, T078 can run in parallel after T076; T082, T083, T084, T085 can run in parallel after T081; T086, T087 can run after T081-T084 complete.  
- US1 Enhancement (external model support): T088, T089, T091 can run in parallel after T014-T016; T092, T093 can run in parallel after T090.  
- US1 Enhancement (model status update & deletion): T095, T096, T098, T099, T100 can run in parallel after T014-T016; T097, T101 can run after T095-T096.
- US1 Enhancement (dataset management): T167, T171, T172, T175, T176, T177, T178, T179 can run in parallel after T015; T168, T169, T170, T173, T174 after T167; T180, T181, T182, T183 after dataset APIs complete.
- US2: T023, T026, T027 parallel after T022.
- US2 Enhancement (training job types & UI): T184, T188, T189, T190, T193 can run in parallel after T024; T185, T186, T187, T191, T192 after T184; T194, T195, T196, T197 after job type implementation complete.
- US2.5 (evaluation system): T198, T199, T206, T207, T208, T209, T210, T211, T212, T213, T214, T215 can run in parallel after US1+US2 foundational; T200, T201, T202, T203, T204, T205 after T198-T199; T216, T217, T218, T219, T220 after evaluation APIs complete.  
- US3: T030 vs T033; T031 vs T034.  
- US3 Enhancement (endpoints list/view): T049, T051, T053, T055 can run in parallel after T050.  
- US3 Enhancement (client examples): T059, T061, T062, T063, T064 can run in parallel; T065 after documentation tasks complete.  
- US3 Enhancement (environment configuration): T102, T103, T105 can run in parallel; T104, T106 after T103 complete.  
- US3 Enhancement (CPU-only deployment): T107, T109, T110, T111 can run in parallel after T030; T108, T112 after T107-T111.  
- US3 Enhancement (resource limits): T113, T114, T116 can run in parallel after T102-T106; T115, T117 after T113-T114.  
- US3 Enhancement (runtime image override): T118, T120, T122 can run in parallel after T124-T128; T119, T121, T123 after T118-T122.  
- US3 Enhancement (runtime image tracking): T125, T127 can run in parallel after T124; T126, T128 after T125-T127.  
- US3 Enhancement (rollback/redeploy): T129, T132, T133, T134 can run in parallel after T030-T036; T130, T131, T135 after T129-T134.  
- US3 Enhancement (endpoint deletion): T136, T139, T140 can run in parallel after T030-T036; T137, T138, T141, T142 after T136-T140.  
- US3 Enhancement (external model serving): T143, T144, T147 can run in parallel after T088-T094; T145, T146, T148 after T143-T147.  
- US3 Enhancement (unified inference API): T149, T150, T152, T154 can run in parallel after T143-T148; T151, T153, T155 after T149-T154.  
- US3 Enhancement (chat test UI): T156, T157, T159 can run in parallel after T149-T155; T158, T160 after T156-T159.  
- US4: T038, T039, T042 in parallel.  
- US4 Enhancement (additional governance APIs): T161, T164, T165 can run in parallel after T037; T162, T163, T166 after T161-T165.

---

## Parallel Example: User Story 2

```bash
Task T023 → backend/src/training/scheduler.py      # Scheduler integration
Task T026 → frontend/src/pages/training/           # UI for job submission/status
Task T027 → backend/tests/contract/test_training.py # Contract tests
```

## Parallel Example: User Story 3 Enhancement (Endpoints List/View)

```bash
Task T049 → backend/src/serving/schemas.py         # List response schema
Task T051 → frontend/src/services/servingClient.ts  # listEndpoints client method
Task T053 → frontend/src/pages/serving/EndpointDetail.vue # Detail page
Task T055 → backend/tests/contract/test_serving.py # Contract tests
```

## Parallel Example: User Story 3 Enhancement (Client Examples)

```bash
Task T059 → examples/serving_client.py             # Python client library
Task T061 → docs/serving-examples.md               # Comprehensive examples guide
Task T062 → examples/README.md                     # Examples README
Task T063 → specs/001-document-llm-ops/quickstart.md # Quickstart Section 7
Task T064 → specs/001-document-llm-ops/spec.md     # Spec updates
```

## Parallel Example: User Story 1 Enhancement (External Model Support)

```bash
Task T088 → backend/src/catalog/models.py         # Model type extension
Task T089 → backend/src/catalog/schemas.py         # Schema updates
Task T091 → frontend/src/pages/catalog/ModelCreate.vue # UI updates
Task T093 → backend/tests/contract/test_catalog.py # Contract tests
```

## Parallel Example: User Story 3 Enhancement (CPU-Only & Resource Limits)

```bash
Task T107 → backend/src/api/routes/serving.py      # useGpu parameter
Task T109 → backend/src/core/settings.py           # CPU-only env vars
Task T110 → frontend/src/pages/serving/EndpointDeploy.vue # UI toggle
Task T111 → backend/src/serving/schemas.py         # Schema updates
Task T113 → backend/src/core/settings.py           # Resource limit env vars
Task T114 → backend/src/core/settings.py           # CPU-only resource env vars
```

## Parallel Example: User Story 1 Enhancement (Dataset Management)

```bash
Task T167 → backend/src/api/routes/catalog.py         # Dataset upload endpoint
Task T171 → backend/src/api/routes/catalog.py         # Dataset preview endpoint
Task T172 → backend/src/api/routes/catalog.py         # Dataset validation endpoint
Task T175 → backend/src/api/routes/catalog.py         # Dataset version comparison endpoint
Task T176 → frontend/src/pages/catalog/DatasetList.vue # Dataset list page
Task T177 → frontend/src/pages/catalog/DatasetDetail.vue # Dataset detail page
Task T178 → frontend/src/pages/catalog/DatasetCreate.vue # Dataset create page
Task T179 → frontend/src/services/catalogClient.ts   # Dataset client methods
```

## Parallel Example: User Story 2 Enhancement (Training Job Types)

```bash
Task T184 → backend/src/training/schemas.py           # Job type schema
Task T188 → frontend/src/pages/training/JobList.vue  # Enhanced job list
Task T189 → frontend/src/pages/training/JobDetail.vue # Enhanced job detail
Task T190 → frontend/src/pages/training/JobSubmit.vue # Job submit page
Task T193 → frontend/src/services/trainingClient.ts  # Updated client
```

## Parallel Example: User Story 2.5 (Evaluation System)

```bash
Task T198 → backend/src/evaluation/models.py         # Evaluation model
Task T199 → backend/src/evaluation/services.py      # Evaluation service
Task T206 → backend/src/api/routes/evaluation.py     # List endpoint
Task T207 → backend/src/api/routes/evaluation.py     # Detail endpoint
Task T208 → backend/src/api/routes/evaluation.py     # Compare endpoint
Task T209 → backend/src/api/routes/evaluation.py     # Export endpoint
Task T210 → backend/src/evaluation/schemas.py        # Evaluation schemas
Task T211 → frontend/src/pages/evaluation/EvaluationList.vue # List page
Task T212 → frontend/src/pages/evaluation/EvaluationDetail.vue # Detail page
Task T213 → frontend/src/pages/evaluation/EvaluationCreate.vue # Create page
Task T214 → frontend/src/pages/evaluation/EvaluationCompare.vue # Compare page
Task T215 → frontend/src/services/evaluationClient.ts # Evaluation client
```

## Parallel Example: User Story 3 Enhancement (Runtime Image & Rollback)

```bash
Task T118 → backend/src/serving/schemas.py         # Runtime image schema
Task T120 → frontend/src/pages/serving/EndpointDeploy.vue # Image selector
Task T122 → backend/src/serving/schemas.py         # Response schema
Task T125 → backend/src/serving/models.py          # Model field
Task T127 → backend/src/serving/schemas.py         # Response schema
Task T132 → frontend/src/pages/serving/EndpointDetail.vue # Rollback UI
Task T133 → frontend/src/services/servingClient.ts  # Client methods
Task T134 → backend/tests/contract/test_serving.py  # Contract tests
```

## Parallel Example: User Story 3 Enhancement (Inference & Chat UI)

```bash
Task T149 → backend/src/api/routes/inference.py    # Chat endpoint
Task T150 → backend/src/api/routes/inference.py    # Routing logic
Task T152 → backend/src/api/routes/inference.py    # Inference params
Task T154 → backend/tests/contract/test_serving.py # Contract tests
Task T156 → frontend/src/pages/serving/ChatTest.vue # Chat UI
Task T157 → frontend/src/services/servingClient.ts  # Client method
Task T159 → frontend/tests/serving.spec.ts          # E2E tests
```

---

## Implementation Strategy

### MVP First (US1)
1. Finish Setup + Foundational.
2. Deliver US1 catalog slice and validate acceptance tests.
3. Pause for review before moving to training.

### Incremental Delivery
1. US1 → US2 → US3 → US3 Enhancements → US4; each deployable independently.  
2. After each story, update SDD + quickstart, run regression tests, and confirm metrics.
3. US3 Enhancements can be delivered incrementally:
   - Environment configuration (T102-T106) should complete early as foundation
   - Endpoints list/view (T049-T058) can be delivered after core serving
   - Client examples (T059-T065) can be delivered after serving APIs are stable
   - CPU-only deployment (T107-T112) and resource limits (T113-T117) can be delivered together
   - Runtime image tracking (T124-T128) should complete before runtime image override (T118-T123)
   - Rollback/redeploy (T129-T135) and deletion (T136-T142) can be delivered together
   - External model serving (T143-T148) enables unified inference API (T149-T155)
   - Chat test UI (T156-T160) can be delivered after unified inference API
4. US1 Enhancements can be delivered incrementally:
   - Catalog UI pages (T071-T075) can be delivered early
   - Model file upload (T076-T087) can be delivered after catalog APIs
   - External model support (T088-T094) enables external model serving
   - Model status update & deletion (T095-T101) completes catalog lifecycle management

### Parallel Team Strategy
- Team A: Backend catalog/training.  
- Team B: Frontend experiences + prompt tooling.  
- Team C: Infra/observability/governance.  
- Sync via contracts, data model docs, and constitution gates after each checkpoint.

---

## Phase 8: User Story 3 Enhancement – Serving Endpoints List & View (Priority: P2)

**Goal**: Enable users to list and view all serving endpoints with filtering capabilities (FR-006a, US3 Acceptance Scenario 3).

**Independent Test**: Navigate to serving endpoints list page, filter by environment/model/status, view endpoint details including route, health status, scaling configuration, and bound model metadata without requiring other systems.

### Implementation

- [x] T049 [P] [US3] Add `EnvelopeServingEndpointList` schema for list response in `backend/src/serving/schemas.py`.
- [x] T050 [US3] Implement `GET /serving/endpoints` route with query parameter filters (environment, modelId, status) in `backend/src/api/routes/serving.py`.
- [x] T051 [P] [US3] Add `listEndpoints` method with filter parameters to `frontend/src/services/servingClient.ts`.
- [x] T052 [US3] Create `EndpointList.vue` page with table display, filtering controls (environment, model, status), and navigation to detail page in `frontend/src/pages/serving/EndpointList.vue`.
- [x] T053 [P] [US3] Create `EndpointDetail.vue` page displaying route, health status, scaling configuration (min/max replicas, autoscale policy), bound model metadata, and environment in `frontend/src/pages/serving/EndpointDetail.vue`.
- [x] T054 [US3] Add routes for `/serving/endpoints` (list) and `/serving/endpoints/:id` (detail) in `frontend/src/router/index.ts`.
- [x] T055 [P] [US3] Add contract test for `GET /serving/endpoints` with filters in `backend/tests/contract/test_serving.py`.
- [x] T056 [US3] Add frontend tests for EndpointList and EndpointDetail pages in `frontend/tests/serving.spec.ts`.
- [x] T057 [US3] Update quickstart.md with list endpoints examples in `specs/001-document-llm-ops/quickstart.md`.
- [x] T058 [US3] Update SDD functional design section documenting endpoint list/view flows in `docs/Constitution.txt`.

**Checkpoint**: Users can browse and filter serving endpoints, view detailed endpoint information, and navigate between list and detail views independently of other features.

---

## Phase 9: User Story 3 Enhancement – Serving Client Examples & Documentation (Priority: P2)

**Goal**: Provide programmatic client libraries and examples for deploying, managing, and monitoring serving endpoints, enabling developers to integrate serving operations into their workflows without manual UI interaction (FR-006b, US3 Acceptance Scenario 4).

**Independent Test**: Use Python client library to deploy an endpoint, query its status, wait for healthy status, and perform rollback operations without accessing the UI. Verify examples guide provides complete documentation for all operations.

**Status**: ✅ **COMPLETED** - All example files and documentation have been created.

### Implementation

- [x] T059 [P] [US3] Create reusable Python `ServingClient` class with methods for deploy, list, get, wait_for_healthy, check_health, and rollback in `examples/serving_client.py`.
- [x] T060 [P] [US3] Add example functions (deploy_and_check, list_endpoints, rollback, full_workflow) with command-line interface in `examples/serving_client.py`.
- [x] T061 [P] [US3] Create comprehensive examples guide with cURL, Python, and JavaScript/TypeScript examples covering all serving operations in `docs/serving-examples.md`.
- [x] T062 [P] [US3] Create examples README with usage guide, environment setup, and execution instructions in `examples/README.md`.
- [x] T063 [US3] Add Section 7 "Serving Examples & Client Usage" to quickstart guide with Python client examples, workflow examples, and JavaScript/TypeScript examples in `specs/001-document-llm-ops/quickstart.md`.
- [x] T064 [US3] Update spec.md with FR-006b functional requirement, User Story 3 Acceptance Scenario 4, and "Examples & Reference Materials" section in `specs/001-document-llm-ops/spec.md`.
- [x] T065 [US3] Create implementation plan documenting serving examples implementation status and future work in `specs/001-document-llm-ops/plan-serving-examples.md`.

**Checkpoint**: Developers can programmatically manage serving endpoints using Python client library, and comprehensive examples documentation is available for all operations.

### Future Work (Pending Model Inference API Implementation)

- [ ] T066 [US3] Implement `call_chat_model()` method in `ServingClient` class once inference API is available in `examples/serving_client.py`.
- [ ] T067 [P] [US3] Update model inference examples with working API calls in `docs/serving-examples.md`.
- [ ] T068 [US3] Update Section 7.5 in quickstart guide with working inference examples in `specs/001-document-llm-ops/quickstart.md`.

**Note**: Tasks T066-T068 are blocked until `POST /inference/{model_name}` API is implemented. See `specs/001-document-llm-ops/plan-serving-examples.md` for details.

---

## Notes

- Task IDs remain sequential; `[P]` indicates safe parallelization.  
- MVP equals completion of US1.  
- Every story ends with documentation compliance per constitution.  
- Ensure `/llm-ops/v1` envelope verified in each API router before closing story.
- Phase 8 tasks (T049-T058) extend User Story 3 with serving endpoints list/view capability per FR-006a.
- Phase 9 tasks (T059-T065) implement serving client examples and documentation per FR-006b and US3 Acceptance Scenario 4. All Phase 9 tasks are completed. Tasks T066-T068 are future work pending Model Inference API implementation.
- Catalog UI Enhancement tasks (T071-T075) extend User Story 1 with improved frontend pages per FR-001b. All tasks are completed.
- Model File Upload tasks (T076-T087) implement model file upload capability per FR-001a. Tasks T076-T081 are backend implementation; T082-T084 are frontend UI; T085-T087 are tests and documentation.
- External Model Support tasks (T088-T094) implement external model registration and serving per FR-001c and FR-006d. All tasks are completed.
- Model Status Update & Deletion tasks (T095-T101) implement model lifecycle management per FR-001d. All tasks are completed.
- Environment Variable Configuration tasks (T102-T106) implement comprehensive configuration system per FR-006g. All tasks are completed.
- CPU-Only Deployment Fallback tasks (T107-T112) implement CPU-only deployment option per FR-006e. All tasks are completed.
- Configurable Resource Limits tasks (T113-T117) implement resource limit configuration per FR-006f. All tasks are completed.
- Runtime Image Override tasks (T118-T123) implement per-endpoint runtime image selection per FR-006h. All tasks are completed.
- Runtime Image Tracking tasks (T124-T128) implement runtime image storage and retrieval per FR-006k. All tasks are completed.
- Endpoint Rollback & Redeployment tasks (T129-T135) implement endpoint lifecycle management per FR-006j. All tasks are completed.
- Endpoint Deletion tasks (T136-T142) implement endpoint deletion with dependency awareness per FR-006i. All tasks are completed.
- External Model Serving Support tasks (T143-T148) implement external model inference routing per FR-006d. All tasks are completed.
- Unified Inference API tasks (T149-T155) implement unified chat completion API per FR-006l. All tasks are completed.
- Chat Test UI tasks (T156-T160) implement interactive chat interface per FR-006c. All tasks are completed.
- Additional Governance APIs tasks (T161-T166) implement policy retrieval and cost aggregation per FR-010a. All tasks are completed.

