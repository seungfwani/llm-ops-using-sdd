# Research: LLM Ops Platform Documentation Alignment

**Branch**: `001-document-llm-ops`  
**Date**: 2025-11-27  
**Inputs**: `/docs/PRD.md`, `/docs/Constitution.txt`, `/docs/필수 기능 목록.md`, internal architecture notes

---

## Decision 1: Platform Stack & Service Boundaries

- **Decision**: Keep FastAPI (Python 3.11) for backend services, Vue 3 + TypeScript for UI, PostgreSQL for metadata, MinIO/S3 for artifacts, Redis for prompt caches, and Kubernetes (with GPU nodes + HPA) as the deployment substrate.
- **Rationale**: Matches PRD assumptions, existing team expertise, and constitution requirement for structured SDD alignment without retooling. Each component already has operational playbooks and observability tooling in place.
- **Alternatives considered**:
  - **Django/GraphQL backend**: Adds ORM conveniences but diverges from FastAPI contract-first workflow and existing `/llm-ops/v1` toolchain.
  - **Next.js frontend**: Strong for SSR but unnecessary for internal admin UI; increases learning curve against established Vue design system.

## Decision 2: Catalog & Dataset Governance Model

- **Decision**: Represent models, datasets, prompts, and benchmarks as first-class catalog entries with versioned metadata, lineage pointers, and approval workflows stored in PostgreSQL schemas aligned to SDD Sections 1–3.
- **Rationale**: Constitution demands every change update SDD overview/system sections; having a rich catalog schema ensures documentation stays synchronized and audit-friendly.
- **Alternatives considered**:
  - **Flat document storage (e.g., MongoDB)**: Easier to iterate but weakens relational integrity between models/datasets and undermines diffing/version comparisons mandated in the PRD.
  - **External tooling (e.g., Model Registry SaaS)**: Adds integration overhead and complicates policy enforcement + `/llm-ops` contract alignment.

## Decision 3: Training Orchestration & Experiment Tracking

- **Decision**: Use Kubernetes-native jobs (e.g., Volcano or Argo-style controllers) triggered through FastAPI endpoints, with experiment metadata persisted via an MLflow-compatible store and artifacts in object storage.
- **Rationale**: Meets requirement for automated GPU scheduling, retry controls, and experiment lineage. Aligns with existing infrastructure and avoids bespoke schedulers.
- **Alternatives considered**:
  - **Managed cloud training (SageMaker)**: Not viable for on-prem GPU constraints and governance policies.
  - **Bare-metal scheduling scripts**: Lack multi-tenant fairness and would violate observability expectations.

## Decision 4: Serving & Prompt Operations

- **Decision**: Deploy approved model versions behind a unified inference gateway that enforces the `/llm-ops/v1` envelope, uses HPA for autoscale, and integrates prompt templates/A/B routing rules stored in catalog tables.
- **Rationale**: Guarantees interface contract fidelity and simplifies prompt experimentation plus rollback; also aligns success metric of 99.5% availability and <1s latency.
- **Alternatives considered**:
  - **Direct deployment per team**: Reintroduces inconsistency and drifts from constitution’s governance.
  - **Serverless-only hosting**: Harder to guarantee GPU availability and inline policy enforcement.

## Decision 5: Observability, Governance, and Cost Controls

- **Decision**: Standardize on Prometheus/Grafana for latency/error/tokens, integrate audit logs into PostgreSQL + long term storage, run RBAC/policy engine (OPA-style) as middleware, and compute cost profiles via scheduled jobs aggregating GPU + token usage.
- **Rationale**: Provides measurable safeguards (alerting within 5 minutes, 20% idle GPU reduction) and satisfies non-functional guardrails in the constitution.
- **Alternatives considered**:
  - **Custom metrics stack**: Slower to implement and duplicates existing monitoring investments.
  - **Manual cost tracking**: Fails success criteria and cannot trigger automated alerts.

## Decision 6: Documentation & Delivery Workflow

- **Decision**: Enforce the seven-section SDD template for every feature, link catalog entries to doc sections, and distribute quickstart/deployment appendices alongside this plan so operations proof is available before Phase 2.
- **Rationale**: Direct response to constitution gate #1 and #5; reduces review friction and ensures tasks/agents reference consistent documentation.
- **Alternatives considered**:
  - **Lightweight wiki updates**: Risk of drift; reviewers can’t trace compliance.
  - **Ad-hoc per-team docs**: Violates structured SDD ownership and complicates audits.

## Decision 7: Load Testing & Performance Validation

- **Decision**: Use k6 for load testing serving and training endpoints, with thresholds targeting 95th percentile latency <2s for serving and <5s for training, error rate <5%, and staged ramp-up to 100 concurrent users for serving and 50 for training.
- **Rationale**: Validates non-functional requirements (99.5% availability, <1s median latency) and identifies bottlenecks before production deployment. k6 integrates with CI/CD and provides detailed metrics.
- **Load Test Scripts**:
  - `backend/tests/load/k6_serving_test.js`: Tests serving endpoint list and deployment operations
    - Stages: 10 → 50 → 100 concurrent users over 11 minutes
    - Thresholds: p95 latency <2s, error rate <5%
  - `backend/tests/load/k6_training_test.js`: Tests training job list and submission operations
    - Stages: 5 → 20 → 50 concurrent users over 11 minutes
    - Thresholds: p95 latency <5s, error rate <5%
- **Execution**:
  ```bash
  k6 run --env BASE_URL=http://localhost:8000/llm-ops/v1 \
         --env MODEL_ID=<model-id> \
         --env DATASET_ID=<dataset-id> \
         backend/tests/load/k6_serving_test.js
  ```
- **Metrics Recorded**:
  - Request duration (p50, p95, p99)
  - Error rate
  - Request rate (RPS)
  - Custom metrics: serving_latency, training_latency
- **Alternatives considered**:
  - **Apache Bench (ab)**: Limited metrics and no support for complex scenarios
  - **JMeter**: Heavier weight, requires GUI for complex test design
  - **Locust**: Python-based but k6's JavaScript syntax is more familiar to team

