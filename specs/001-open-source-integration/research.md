# Research Notes - 001-open-source-integration

## Decisions

- **Decision:** GPU 타입 리스트는 백엔드 설정/DB(예: env/ConfigMap, integration config 테이블)에서 관리하며 API로 노출한다.  
  **Rationale:** 프론트 하드코딩 제거, 환경별 차이를 설정으로 분리, 캐싱/검증이 단순함.  
  **Alternatives considered:** (1) 클러스터 노드 라벨 실시간 조회 - 노드 권한·속도 의존도가 높음. (2) 외부 자산 인벤토리 서비스 의존 - 추가 연동 비용과 가용성 리스크가 있음.

## Notes
- 리턴 스키마는 기존 `/llm-ops/v1` `{status,message,data}` 컨벤션을 따른다.
- 환경 파라미터(env/dev/stg/prod)별로 다른 리스트를 반환할 수 있어야 한다.
# Research: Open Source Integration for LLM Ops Platform

**Branch**: `001-open-source-integration`  
**Date**: 2025-01-27  
**Inputs**: `/specs/001-open-source-integration/spec.md`, `/specs/001-document-llm-ops/spec.md`, `/docs/PRD.md`, industry best practices

---

## Decision 1: Experiment Tracking System

- **Decision**: Integrate **MLflow** as the primary experiment tracking system, with adapter interface for potential future alternatives (Weights & Biases, TensorBoard).

- **Rationale**: 
  - MLflow is already mentioned in existing codebase (`backend/pyproject.toml` includes `mlflow = "^2.14.0`)
  - Mature, widely adopted in ML community with strong Python/Kubernetes support
  - Provides experiment tracking UI, metric comparison, artifact management, and model registry capabilities
  - Supports on-premises deployment (MLflow Tracking Server)
  - REST API allows integration without tight coupling
  - Compatible with existing PostgreSQL backend (MLflow can use PostgreSQL as backend store)

- **Alternatives considered**:
  - **Weights & Biases (W&B)**: Excellent UI and collaboration features, but primarily SaaS-focused. Self-hosted option exists but less mature than MLflow for on-premises.
  - **TensorBoard**: Good for visualization but lacks experiment management, artifact tracking, and model registry features needed for full ML lifecycle.
  - **Custom implementation**: Already exists but lacks advanced features (metric comparison, artifact versioning, experiment search) and requires ongoing maintenance.

- **Integration Approach**:
  - Deploy MLflow Tracking Server as Kubernetes service
  - Create adapter interface (`integrations/experiment_tracking/interface.py`) for abstraction
  - Implement MLflow adapter (`mlflow_adapter.py`) that wraps MLflow REST API
  - Training jobs automatically create MLflow runs via adapter
  - Platform UI can embed MLflow UI or link to it, with unified search across platform and MLflow

---

## Decision 2: Model Serving Framework

- **Decision**: Use **KServe** as primary serving framework (already partially integrated per `specs/001-document-llm-ops/quickstart.md`), with **Ray Serve** as secondary option for advanced use cases (distributed inference, custom batching).

- **Rationale**:
  - KServe is already mentioned in existing quickstart documentation and partially implemented
  - Kubernetes-native (InferenceService CRD) aligns with platform's Kubernetes-first architecture
  - Provides automatic scaling, canary deployments, and multi-framework support (vLLM, TGI, custom)
  - Battle-tested in production environments
  - Supports GPU resource management and multi-GPU model parallelism
  - Ray Serve offers advanced features (dynamic batching, distributed inference) for future needs

- **Alternatives considered**:
  - **Raw Kubernetes Deployments**: Current approach but lacks advanced features (autoscaling, canary, batching) and requires custom implementation.
  - **Seldon Core**: Similar to KServe but less mature ecosystem and smaller community.
  - **BentoML**: Good for model packaging but less Kubernetes-native and requires additional abstraction layers.

- **Integration Approach**:
  - Enhance existing KServe integration (already supports `use_kserve` flag)
  - Create serving adapter interface (`integrations/serving/interface.py`)
  - Implement KServe adapter (`kserve_adapter.py`) for InferenceService CRD management
  - Implement Ray Serve adapter (`ray_serve_adapter.py`) for advanced use cases
  - Platform API routes requests through abstraction layer, maintaining `/llm-ops/v1` contract

---

## Decision 3: Workflow Orchestration

- **Decision**: Integrate **Argo Workflows** for complex multi-stage pipeline orchestration, with adapter interface for potential future alternatives (Kubeflow Pipelines, Prefect).

- **Rationale**:
  - Kubernetes-native (CRD-based) aligns with platform architecture
  - Supports complex DAGs, conditional execution, retry policies, and resource queuing
  - Visual pipeline editor (Argo Workflows UI) for pipeline definition and monitoring
  - Strong community support and active development
  - Supports GPU resource requests and queuing
  - Can integrate with existing Kubernetes job scheduling

- **Alternatives considered**:
  - **Kubeflow Pipelines**: More comprehensive ML platform but heavier weight and more complex setup. Overkill for current needs.
  - **Prefect**: Good workflow engine but less Kubernetes-native, requires additional infrastructure.
  - **Custom job scheduling**: Current approach but lacks visual pipeline editor, dependency management, and advanced retry/error handling.

- **Integration Approach**:
  - Deploy Argo Workflows controller in Kubernetes cluster
  - Create orchestration adapter interface (`integrations/orchestration/interface.py`)
  - Implement Argo adapter (`argo_adapter.py`) that creates Workflow CRDs
  - Platform UI allows pipeline definition through forms, converts to Argo Workflow spec
  - Pipeline status and logs integrated into platform UI with links to Argo UI for detailed views

---

## Decision 4: Model Registry Integration

- **Decision**: Integrate **Hugging Face Hub** as primary model registry, with adapter interface for extensibility to other registries (ModelScope, OpenXLab).

- **Rationale**:
  - Hugging Face Hub is the de facto standard for open-source LLM models
  - Provides standardized model formats, metadata schemas (model cards), and discovery mechanisms
  - Strong Python SDK (`huggingface_hub`) for programmatic access
  - Supports both public and private model repositories
  - Existing codebase already has `huggingface_importer.py` showing integration patterns
  - Large model ecosystem (thousands of pre-trained models)

- **Alternatives considered**:
  - **ModelScope**: Chinese alternative with good model collection but smaller international community.
  - **OpenXLab**: Similar to Hugging Face but less mature ecosystem.
  - **Custom registry only**: Limits model discovery and sharing capabilities, requires maintaining separate registry infrastructure.

- **Integration Approach**:
  - Enhance existing Hugging Face importer (`catalog/services/huggingface_importer.py`)
  - Create registry adapter interface (`integrations/registry/interface.py`)
  - Implement Hugging Face adapter (`huggingface_adapter.py`) wrapping `huggingface_hub` SDK
  - Platform catalog can import models from Hub, export platform models to Hub
  - Unified search interface shows both internal catalog and Hub models (with import option)

---

## Decision 5: Data Versioning

- **Decision**: Integrate **DVC (Data Version Control)** for dataset versioning and lineage tracking, with adapter interface for potential alternatives (LakeFS, Pachyderm).

- **Rationale**:
  - DVC is Git-like versioning for data, providing efficient storage (deduplication, compression)
  - Supports dataset diffs, lineage tracking, and rollback capabilities
  - Can use existing object storage (MinIO/S3) as remote storage
  - Lightweight and easy to integrate with existing data workflows
  - Strong Python SDK for programmatic access
  - Supports large datasets efficiently through content-addressable storage

- **Alternatives considered**:
  - **LakeFS**: More comprehensive data lake management but heavier weight and requires additional infrastructure.
  - **Pachyderm**: Enterprise-grade data versioning but complex setup and overkill for current needs.
  - **Custom versioning**: Current approach but lacks efficient storage (full dataset copies), diff visualization, and lineage tracking.

- **Integration Approach**:
  - Deploy DVC remote storage configuration pointing to existing MinIO/S3
  - Create versioning adapter interface (`integrations/versioning/interface.py`)
  - Implement DVC adapter (`dvc_adapter.py`) wrapping DVC Python API
  - Dataset uploads trigger DVC version creation
  - Platform UI displays version diffs and lineage from DVC metadata
  - Training jobs reference DVC dataset versions for reproducibility

---

## Decision 6: Integration Architecture Pattern

- **Decision**: Use **Adapter Pattern** with common interfaces for all open-source tool integrations, allowing tool swapping without changing business logic.

- **Rationale**:
  - Maintains flexibility to switch tools if better alternatives emerge
  - Enables gradual migration (feature flags can switch between custom and open-source implementations)
  - Simplifies testing (mock adapters for unit tests)
  - Clear separation of concerns (business logic vs. tool integration)
  - Supports multiple tools per category (e.g., KServe + Ray Serve) with selection logic

- **Alternatives considered**:
  - **Direct integration**: Simpler initially but creates tight coupling, makes tool switching difficult, and complicates testing.
  - **Service mesh**: Overkill for current scale, adds complexity without clear benefits.

- **Implementation Pattern**:
  - Each tool category has interface definition (`interface.py`) with abstract methods
  - Concrete adapters implement interface (`{tool}_adapter.py`)
  - Factory pattern selects adapter based on configuration
  - Business services call adapter interface, not tool APIs directly
  - Error handling wraps tool-specific errors in platform error format

---

## Decision 7: Migration Strategy

- **Decision**: **Incremental migration with feature flags**, allowing gradual rollout and easy rollback.

- **Rationale**:
  - Minimizes risk by allowing testing in production with limited users
  - Enables A/B testing between custom and open-source implementations
  - Provides rollback path if issues arise
  - Allows team to learn tools gradually without disrupting operations
  - Supports environment-specific enablement (dev/stg/prod)

- **Migration Phases**:
  1. **Phase 1 (Weeks 1-4)**: Deploy open-source tools, implement adapters, enable for dev environment only
  2. **Phase 2 (Weeks 5-8)**: Enable for staging, validate functionality, performance testing
  3. **Phase 3 (Weeks 9-12)**: Gradual production rollout with feature flags, monitor metrics, full migration

- **Rollback Plan**:
  - Feature flags allow instant rollback to custom implementations
  - Data migration scripts support bidirectional data sync during transition
  - Monitoring alerts trigger automatic rollback on critical errors
  - Documentation includes rollback procedures for each tool

---

## Decision 8: Observability Integration

- **Decision**: **Unified observability dashboard** integrating metrics, logs, and traces from both platform and open-source tools.

- **Rationale**:
  - Single pane of glass for operations reduces cognitive load
  - Enables correlation between platform events and tool events
  - Maintains existing Prometheus/Grafana stack (no new tooling needed)
  - Tool-specific metrics exported to Prometheus format
  - Centralized logging via existing log aggregation

- **Integration Approach**:
  - MLflow metrics exported to Prometheus (via MLflow Prometheus plugin or custom exporter)
  - KServe metrics already available via Prometheus (Kubernetes metrics)
  - Argo Workflows metrics via Prometheus operator
  - Platform Grafana dashboards include tool-specific panels
  - Log aggregation collects tool logs alongside platform logs
  - Alerts configured for tool service health and integration failures

---

## Open Questions Resolved

1. **Q: Should we replace all custom implementations immediately?**  
   **A**: No. Incremental migration with feature flags allows gradual transition and validation.

2. **Q: What if an open-source tool doesn't meet requirements?**  
   **A**: Adapter pattern allows switching tools without code changes. Multiple adapters can coexist.

3. **Q: How do we handle tool service failures?**  
   **A**: Graceful degradation with fallback to basic functionality, retry queues, and clear error messages.

4. **Q: What about tool version compatibility?**  
   **A**: Support multiple tool versions during migration, document upgrade paths, test compatibility.

5. **Q: How do users access tool UIs?**  
   **A**: Authenticated links from platform UI, with platform UI as primary interface for common workflows.

