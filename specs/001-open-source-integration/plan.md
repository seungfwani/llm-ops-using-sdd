# Implementation Plan: Open Source Integration - GPU 타입 동적 제공

**Branch**: `001-open-source-integration` | **Date**: 2025-12-10 | **Spec**: `specs/001-open-source-integration/spec.md`
**Input**: Feature specification from `/specs/001-open-source-integration/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Training Job 제출 시 GPU 타입 셀렉트가 프론트에 하드코딩되어 있었던 문제를 해소한다. 환경별 설정/DB에 관리된 GPU 타입 리스트를 백엔드 API로 노출하고, 프론트는 이를 조회해 옵션을 구성한다. 제출 시 `gpu_type`는 백엔드에서 환경별 enabled 리스트로 검증한다. 응답 스키마는 기존 `{status,message,data}` 규약을 따른다.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11 (FastAPI), Node/Vue 3 (frontend)  
**Primary Dependencies**: FastAPI, SQLAlchemy, PostgreSQL, Vue 3, Vite, Kubernetes (KServe already used)  
**Storage**: PostgreSQL (integration/config table), ConfigMap/env for GPU 타입 소스; no new DB tables required if config table reused  
**Testing**: pytest, frontend unit/E2E (vitest/cypress)  
**Target Platform**: Kubernetes (DEV/STG/PROD), browser frontend  
**Project Type**: Web (backend + frontend)  
**Performance Goals**: GET gpu-types p95 < 300ms intra-cluster; validation adds < 5ms per submission  
**Constraints**: Must preserve `/llm-ops/v1` `{status,message,data}` schema; env별 리스트 분리; no cluster-role expansion  
**Scale/Scope**: Scope limited to Training Job submit UI/API; reuse existing integration config infrastructure

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. **Structured SDD Ownership** — Provide or update the feature SDD covering
   purpose, scope, references, functional inventory, scenarios, and UI flows per
   `docs/Constitution.txt`.
2. **Architecture Transparency** — Attach current component, topology, and data
   flow diagrams that match the feature boundaries and dependencies.
3. **Interface Contract Fidelity** — Document every touched API under
   `/llm-ops/v1`, including the canonical `{status,message,data}` response body,
   200-only success contract, and mapped 4xx/5xx errors.
4. **Non-Functional Safeguards** — Capture measurable performance, security,
   failure-recovery, and logging/monitoring commitments for the change.
5. **Operations-Ready Delivery** — Show deployment diagram deltas, environment
   configs (DEV/STG/PROD), backup/scaling adjustments, and maintenance impacts.

Any unmet gate must be logged in *Complexity Tracking* with an explicit plan to
restore compliance before implementation proceeds.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/           # FastAPI routes
│   ├── serving/       # serving logic (unchanged)
│   ├── training/      # training job submission/validation
│   └── integrations/  # integration config access
└── tests/

frontend/
├── src/
│   ├── pages/training/    # JobSubmit.vue, JobDetail.vue
│   ├── components/        # shared UI components
│   └── services/          # API clients
└── tests/
```

**Structure Decision**: Web application with backend + frontend as above; feature touches training submit UI and backend API.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

None.
