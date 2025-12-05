# Implementation Plan: Open Source Integration for LLM Ops Platform

**Branch**: `001-open-source-integration` | **Date**: 2025-01-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-open-source-integration/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Migrate custom implementations to proven open-source solutions for experiment tracking, model serving, workflow orchestration, model registry integration, and data versioning. The platform will integrate industry-standard tools (MLflow, KServe/Ray Serve, Argo Workflows, Hugging Face Hub, DVC) while maintaining backward compatibility with existing `/llm-ops/v1` API contracts and user workflows. Integration will be done incrementally with abstraction layers to ensure zero breaking changes.

**Training & Serving Structure Integration**: The platform will enforce the TrainJobSpec and DeploymentSpec structures defined in `docs/training-serving-spec.md`. All training jobs must conform to the standardized schema (job_type, model_family, base_model_ref, dataset_ref, hyperparams, method, resources, output), and all serving deployments must follow the DeploymentSpec structure (model_ref, model_family, job_type, serve_image, resources, runtime constraints, rollout strategy). The platform will convert these structures to open-source tool native formats (MLflow params, KServe InferenceService, Argo Workflow specs) for execution while maintaining the original spec structure for validation and display.

## Technical Context

**Language/Version**: Python 3.11 (backend), TypeScript 5+ (frontend)  
**Primary Dependencies**: FastAPI, Vue 3, PostgreSQL, Kubernetes, MLflow, KServe/Ray Serve, Argo Workflows, Hugging Face Hub, DVC  
**Storage**: PostgreSQL (metadata), MinIO/S3 (artifacts), Redis (caching)  
**Testing**: pytest, pytest-asyncio, schemathesis (contract testing)  
**Target Platform**: Kubernetes clusters (on-premises and cloud) with GPU nodes  
**Project Type**: Web application (backend + frontend)  
**Performance Goals**: Maintain current API response times (within 10% variance), 99.5% serving endpoint availability, 99.9% open-source tool service uptime  
**Constraints**: Zero breaking changes to `/llm-ops/v1` API contracts, on-premises deployment support required, graceful degradation when tools unavailable, strict enforcement of training-serving-spec.md validation rules (model_family whitelist, dataset type compatibility, job_type constraints)  
**Scale/Scope**: Support existing platform scale (10k+ experiments, 100+ serving endpoints, 1000+ datasets), integrate 5 major open-source tool categories, enforce training-serving-spec.md structures for all training jobs and serving deployments

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

1. **Structured SDD Ownership** — ✅ Feature spec includes user scenarios, functional requirements, and success criteria. SDD sections will be updated during implementation to document open-source tool integration architecture, API contracts, and operational procedures.

2. **Architecture Transparency** — ✅ Architecture diagrams will be created in Phase 1 showing:
   - Component diagram: Platform services, open-source tool services, integration adapters
   - Data flow diagram: Request flow through abstraction layers to open-source tools
   - Topology diagram: Kubernetes deployment of platform and tool services

3. **Interface Contract Fidelity** — ✅ All `/llm-ops/v1` endpoints maintain existing contracts. New integration endpoints (if needed) follow the same `{status,message,data}` response format. Open-source tool errors are wrapped in standardized error responses.

4. **Non-Functional Safeguards** — ✅ Success criteria defined: 99.5% availability, <2s query response times, 99.9% tool service uptime. Failure recovery: graceful degradation, retry queues, fallback behaviors. Monitoring: unified observability dashboard integrating tool metrics.

5. **Operations-Ready Delivery** — ✅ Deployment strategy: incremental migration with feature flags, rollback capabilities, environment-specific configurations (dev/stg/prod). Documentation: tool selection rationale, integration guides, troubleshooting procedures, upgrade paths.

**Status**: All gates pass. Phase 0 research completed. Phase 1 design completed.

**Post-Phase 1 Re-check**:
1. ✅ **Structured SDD Ownership**: research.md documents tool selection decisions. data-model.md defines integration entities. API contracts document integration endpoints. quickstart.md provides operational procedures.
2. ✅ **Architecture Transparency**: Project structure section defines integration adapter pattern. Component diagrams will be created during implementation showing platform services, adapters, and open-source tools.
3. ✅ **Interface Contract Fidelity**: All integration APIs follow `/llm-ops/v1` contract with `{status,message,data}` format. Contracts defined in `contracts/` directory for all integration categories.
4. ✅ **Non-Functional Safeguards**: Success criteria defined in spec.md (99.5% availability, <2s query times, 99.9% tool uptime). Failure recovery: graceful degradation, retry queues. Monitoring: unified observability dashboard.
5. ✅ **Operations-Ready Delivery**: quickstart.md provides deployment procedures for all tools. Environment-specific configuration documented. Rollback procedures included.

## Project Structure

### Documentation (this feature)

```text
specs/001-open-source-integration/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── experiment-tracking.yaml
│   ├── serving-integration.yaml
│   ├── workflow-orchestration.yaml
│   ├── model-registry.yaml
│   └── data-versioning.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── integrations/           # New: Open-source tool integration adapters
│   │   ├── experiment_tracking/
│   │   │   ├── mlflow_adapter.py
│   │   │   └── interface.py
│   │   ├── serving/
│   │   │   ├── kserve_adapter.py
│   │   │   ├── ray_serve_adapter.py
│   │   │   └── interface.py
│   │   ├── orchestration/
│   │   │   ├── argo_adapter.py
│   │   │   └── interface.py
│   │   ├── registry/
│   │   │   ├── huggingface_adapter.py
│   │   │   └── interface.py
│   │   └── versioning/
│   │       ├── dvc_adapter.py
│   │       └── interface.py
│   ├── training/               # Enhanced with TrainJobSpec validation
│   │   ├── validators/         # New: training-serving-spec.md validation
│   │   │   ├── train_job_spec_validator.py
│   │   │   ├── model_family_validator.py
│   │   │   └── dataset_compatibility_validator.py
│   │   ├── converters/         # New: TrainJobSpec to tool format converters
│   │   │   ├── mlflow_converter.py
│   │   │   └── argo_converter.py
│   │   └── services.py         # Updated to use TrainJobSpec structure
│   ├── serving/                # Enhanced with DeploymentSpec validation
│   │   ├── validators/         # New: DeploymentSpec validation
│   │   │   ├── deployment_spec_validator.py
│   │   │   └── job_type_compatibility_validator.py
│   │   ├── converters/         # New: DeploymentSpec to KServe/Ray Serve converters
│   │   │   ├── kserve_converter.py
│   │   │   └── ray_serve_converter.py
│   │   └── serving_service.py  # Updated to use DeploymentSpec structure
│   ├── api/
│   │   └── routes/             # Existing routes, enhanced with integration calls
│   ├── services/              # Existing services, updated to use adapters
│   └── core/
│       ├── settings.py         # Updated with tool configuration
│       └── image_config.py     # New: Container image version management
└── tests/
    ├── integration/
    │   └── test_open_source_integrations.py
    └── unit/
        └── test_integration_adapters.py

frontend/
├── src/
│   ├── components/             # Existing components
│   ├── pages/                  # Existing pages, enhanced with tool UI links
│   └── services/
│       └── integrationClient.ts  # New: Client for integration APIs
└── tests/

infra/
├── k8s/
│   ├── mlflow/                 # New: MLflow deployment manifests
│   ├── argo/                   # New: Argo Workflows deployment
│   └── dvc/                    # New: DVC server deployment (if needed)
└── helm/                       # Helm charts for tool deployments
```

**Structure Decision**: Web application structure maintained. New `integrations/` directory in backend contains adapter pattern implementations for each open-source tool category. Each adapter implements a common interface, allowing tool swapping without changing business logic. 

**Training-Serving Spec Integration**: New `validators/` and `converters/` subdirectories added to `training/` and `serving/` modules. Validators enforce training-serving-spec.md rules (model_family whitelist, dataset type compatibility, job_type constraints). Converters transform TrainJobSpec/DeploymentSpec structures to open-source tool native formats (MLflow params, KServe InferenceService YAML, Argo Workflow specs) for execution. Container image versions are managed through centralized configuration (`core/image_config.py`) loaded from ConfigMap/environment variables.

Frontend remains unchanged except for new integration UI links and optional tool-specific views.

## Training-Serving Spec Integration Architecture

### TrainJobSpec Structure Enforcement

The platform enforces the TrainJobSpec schema from `docs/training-serving-spec.md` for all training job submissions:

**Schema Fields**:
- `job_type`: PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING (enum validation)
- `model_family`: Whitelist validation (llama, mistral, gemma, bert, etc.)
- `base_model_ref`: Required for SFT/RAG_TUNING/RLHF, null for PRETRAIN
- `dataset_ref`: Must include name, version, type, storage_uri
- `hyperparams`: lr (float), batch_size (int), num_epochs (int), max_seq_len (int), precision (fp16|bf16)
- `method`: full, lora, qlora (method constraints per job_type)
- `resources`: gpus (int), gpu_type (string), nodes (int)
- `output`: artifact_name (string), save_format (hf|safetensors)

**Validation Rules**:
- ModelFamily whitelist: Only families defined in training-serving-spec.md allowed
- Dataset type compatibility: PRETRAIN → pretrain_corpus, SFT → sft_pair, RAG_TUNING → rag_qa, RLHF → rlhf_pair
- Base model requirements: PRETRAIN allows null, others require valid base_model_ref
- Method constraints: PRETRAIN defaults to "full", others allow lora/qlora/full
- Max sequence length: SFT max_seq_len must be <= base_model.max_position_embeddings

**Implementation**:
- Validators in `backend/src/training/validators/` enforce rules before job submission
- Converters in `backend/src/training/converters/` transform TrainJobSpec to MLflow params and Argo Workflow specs
- Validation errors return clear messages indicating which rule was violated

### DeploymentSpec Structure Enforcement

The platform enforces the DeploymentSpec schema from `docs/training-serving-spec.md` for all serving deployments:

**Schema Fields**:
- `model_ref`: Reference to trained model artifact
- `model_family`: Must match training job's model_family
- `job_type`: Inherited from training job (SFT, RAG_TUNING, RLHF, etc.)
- `serve_image`: Automatically selected based on serve_target type (GENERATION or RAG)
- `resources`: gpus (int), gpu_memory_gb (int)
- `runtime`: max_concurrent_requests (int), max_input_tokens (int), max_output_tokens (int)
- `rollout`: strategy (blue-green|canary), traffic_split (dict with old/new percentages)

**Validation Rules**:
- Job type and serve_target compatibility: RAG_TUNING → RAG, SFT/RLHF → GENERATION
- Model family consistency: Deployment model_family must match training job model_family
- Resource constraints: GPU requests must match model requirements
- Runtime limits: max_input_tokens must be <= model's max_position_embeddings

**Implementation**:
- Validators in `backend/src/serving/validators/` enforce rules before deployment
- Converters in `backend/src/serving/converters/` transform DeploymentSpec to KServe InferenceService YAML or Ray Serve deployment config
- Image selection: Automatically determined from configuration based on serve_target type

### Container Image Version Management

Container images are managed through centralized configuration:

**Configuration Source**: ConfigMap, environment variables, or configuration files
**Image Mappings** (from training-serving-spec.md):
```yaml
train:
  PRETRAIN:
    gpu: "registry/llm-train-pretrain:pytorch2.1-cuda12.1-v1"
    cpu: "registry/llm-train-pretrain:pytorch2.1-cpu-v1"  # CPU-based for local dev
  SFT:
    gpu: "registry/llm-train-sft:pytorch2.1-cuda12.1-v1"
    cpu: "registry/llm-train-sft:pytorch2.1-cpu-v1"
  RAG_TUNING:
    gpu: "registry/llm-train-rag:pytorch2.1-cuda12.1-v1"
    cpu: "registry/llm-train-rag:pytorch2.1-cpu-v1"
  RLHF:
    gpu: "registry/llm-train-rlhf:pytorch2.1-cuda12.1-v1"
    cpu: "registry/llm-train-rlhf:pytorch2.1-cpu-v1"
  EMBEDDING:
    gpu: "registry/llm-train-embedding:pytorch2.1-cuda12.1-v1"
    cpu: "registry/llm-train-embedding:pytorch2.1-cpu-v1"
serve:
  GENERATION:
    gpu: "registry/llm-serve:vllm-0.5.0-cuda12.1"
    cpu: "registry/llm-serve:cpu-v0.5.0"  # CPU-based for local dev
  RAG:
    gpu: "registry/llm-serve-rag:vllm-0.5.0-cuda12.1"
    cpu: "registry/llm-serve-rag:cpu-v0.5.0"
```

**Implementation**:
- `backend/src/core/image_config.py` loads image mappings from configuration
- Environment-specific configurations supported (dev/stg/prod)
- Image selection: Automatically determined at runtime based on:
  - `job_type` or `serve_target` (required)
  - GPU availability or `use_gpu` flag (determines gpu vs cpu variant)
  - Environment (dev/stg/prod) can override default behavior
- User override: NOT allowed - images are enforced based on job_type/serve_target and GPU availability
- CPU fallback: When GPU is not available or `use_gpu=False`, platform automatically selects CPU-based images for local development

### Spec-to-Tool Format Conversion

TrainJobSpec and DeploymentSpec structures are converted to open-source tool native formats:

**TrainJobSpec Conversions**:
- **MLflow**: TrainJobSpec fields → MLflow run parameters (params dict), tags, experiment name
- **Argo Workflows**: TrainJobSpec → Argo Workflow template with container spec, resource requests, environment variables

**DeploymentSpec Conversions**:
- **KServe**: DeploymentSpec → KServe InferenceService YAML with model URI, resource requests, autoscaling config
- **Ray Serve**: DeploymentSpec → Ray Serve deployment config with model path, num_replicas, resource requirements

**Conversion Logic**:
- Bidirectional conversion maintained: Tool native format ↔ TrainJobSpec/DeploymentSpec
- Conversion adapters in `backend/src/training/converters/` and `backend/src/serving/converters/`
- Error handling: Conversion failures return clear error messages with field-level details

### Validation and Error Handling

**Validation Timing**: Immediate validation on job submission and deployment request
**Validation Scope**: All training-serving-spec.md rules enforced (model_family whitelist, dataset compatibility, base_model_ref requirements, method constraints, job_type/serve_target compatibility)
**Existing Data**: Re-validation of existing jobs and deployments; non-compliant items marked and rejected for execution/updates
**Error Messages**: Clear, actionable error messages indicating which rule was violated and how to fix

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All constitution gates pass.
