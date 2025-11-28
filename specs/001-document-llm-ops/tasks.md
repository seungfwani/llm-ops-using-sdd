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

**Checkpoint**: Catalog slice independently functional and documented; constitutes MVP. Model file upload capability enables full model registration workflow.

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

**Checkpoint**: Training orchestration independently deployable with experiment lineage.

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

**Checkpoint**: Serving/prompt subsystem independently testable with rollback support.

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

**Checkpoint**: Ops/governance slice independently enforces policies and surfaces costs.

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
- **US2 (training)**: depends on catalog entities for lineage references; uses US1 read-only.  
- **US3 (serving/prompt)**: relies on approved catalog entries and evaluation outputs; can begin after US1 + Foundational.  
- **US3 Enhancement (endpoints list/view)**: extends US3; requires existing serving endpoints to be deployed (can run after T030-T036 complete).  
- **US3 Enhancement (client examples)**: extends US3; requires serving API endpoints to be functional; can run in parallel with other US3 enhancements after core serving functionality (T030-T036) is complete.  
- **US4 (ops/governance)**: consumes metrics and policy hooks from earlier stories but most work (UI/dashboards) can proceed in parallel once observability is ready.

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
- US2: T023, T026, T027 parallel after T022.  
- US3: T030 vs T033; T031 vs T034.  
- US3 Enhancement (endpoints list/view): T049, T051, T053, T055 can run in parallel after T050.  
- US3 Enhancement (client examples): T059, T061, T062, T063, T064 can run in parallel; T065 after documentation tasks complete.  
- US4: T038, T039, T042 in parallel.

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

---

## Implementation Strategy

### MVP First (US1)
1. Finish Setup + Foundational.
2. Deliver US1 catalog slice and validate acceptance tests.
3. Pause for review before moving to training.

### Incremental Delivery
1. US1 → US2 → US3 → US3 Enhancement (endpoints list/view) → US3 Enhancement (client examples) → US4; each deployable independently.  
2. After each story, update SDD + quickstart, run regression tests, and confirm metrics.
3. US3 Enhancements (endpoints list/view and client examples) can be delivered after core US3 serving functionality is complete.

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

