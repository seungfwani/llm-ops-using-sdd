# Feature Specification: Open Source Integration for LLM Ops Platform

**Feature Branch**: `001-open-source-integration`  
**Created**: 2025-01-27  
**Status**: Draft  
**Input**: User description: "자 이제 우리는 다시 시작할거야. 현재 spec.md 형태로 구현을 했는데, llm-ops 에 사용되는 오픈소스들이 좋은게 있어. 지금 spec.md 에는 구현을 직접 하는 형태로 했는데, 오픈소스를 잘 적용하는 방식으로 바꿔보고 싶어."

## Overview

This specification defines the migration strategy from custom implementations to proven open-source solutions for the LLM Ops platform. The platform currently implements many features from scratch (as documented in `specs/001-document-llm-ops/spec.md`), but industry-standard open-source tools can provide better maintainability, community support, and feature richness. This spec identifies key areas where open-source integration will replace custom implementations while maintaining the existing `/llm-ops/v1` API contract and user workflows.

## Clarifications

### Session 2025-01-27

- Q: Should the platform apply the full TrainJobSpec structure from training-serving-spec.md (job_type, model_family, base_model_ref, dataset_ref, hyperparams, method, resources, output)? → A: Full application - The platform MUST apply the complete TrainJobSpec schema from training-serving-spec.md, and all training jobs MUST conform to this schema structure.
- Q: Should the platform apply the full DeploymentSpec structure from training-serving-spec.md (serve_image type separation, GENERATION/RAG distinction, runtime constraints, rollout strategy)? → A: Full application - The platform MUST apply the complete DeploymentSpec schema from training-serving-spec.md, and all serving deployments MUST conform to this schema structure.
- Q: How should the platform integrate TrainJobSpec/DeploymentSpec structures with open-source tools (MLflow, KServe, Argo Workflows)? → A: Conversion approach - TrainJobSpec/DeploymentSpec structures MUST be converted to open-source tools' native formats (MLflow run params, KServe InferenceService spec, Argo Workflow spec, etc.), and the platform MUST store the converted formats. The platform MUST maintain mapping logic between training-serving-spec.md structures and open-source tool formats.
- Q: How should the platform manage container image versions defined in training-serving-spec.md for each job_type? → A: Centralized configuration management - Container image mappings from training-serving-spec.md MUST be stored in platform configuration files (ConfigMap/environment variables), and administrators MUST be able to update image versions through configuration. All job_type-specific images MUST be read from configuration.
- Q: When should training-serving-spec.md validation rules be applied, and how should existing training jobs and serving endpoints be handled? → A: Immediate validation with existing data rejection - All newly submitted training jobs and serving deployments MUST be validated immediately against training-serving-spec.md rules. Existing submitted jobs MUST also be re-validated, and jobs that do not satisfy the spec MUST be rejected.
- Q: How should the platform handle local development environments without GPU support? → A: CPU-based image fallback - The platform MUST support both GPU and CPU-based container images for each job_type and serve_target. When GPU is unavailable or `use_gpu=False`, the platform MUST automatically select CPU-based images from configuration. Image configuration MUST support both `gpu` and `cpu` variants for all training and serving images to enable local development without GPU hardware.

### Session 2025-12-10

- Q: How should the training UI obtain available GPU types for job submission? → A: Backend-configured list - The backend must expose GPU type options sourced from configuration/DB (e.g., env/ConfigMap or integration config), and the frontend must fetch and render this list instead of hardcoding values.

## Assumptions & Dependencies

- The existing platform architecture (FastAPI backend, Vue.js frontend, PostgreSQL, Kubernetes) remains the foundation.
- Open-source tools will be integrated as services/components rather than replacing the entire stack.
- The `/llm-ops/v1` API contract must remain stable; open-source tools will be abstracted behind existing endpoints.
- Kubernetes cluster access and GPU nodes are available for deploying open-source tooling (production/staging). Local development environments may not have GPU support, requiring CPU-based image fallback.
- Team has capacity to learn and maintain selected open-source tools.
- Open-source tools selected must support on-premises deployment (not SaaS-only solutions).
- Training job specifications MUST conform to the TrainJobSpec structure defined in `docs/training-serving-spec.md`, including job_type (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING), model_family, base_model_ref, dataset_ref, hyperparams, method, resources, and output fields.
- Container images MUST support both GPU and CPU variants for local development environments without GPU hardware. The platform MUST automatically detect GPU availability and select appropriate images.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Experiment Tracking with Open Source Tools (Priority: P1)

ML engineers submit training jobs and automatically track experiments (parameters, metrics, artifacts) using an integrated open-source experiment tracking system, replacing custom experiment logging implementations.

**Why this priority**: Experiment tracking is foundational for ML workflows and open-source tools provide mature features (UI dashboards, metric comparison, artifact management) that reduce maintenance burden compared to custom implementations.

**Independent Test**: Submit a training job, verify experiment metadata (parameters, metrics, logs) is automatically captured in the open-source tracking system, and confirm users can view experiment history and compare runs through the integrated UI.

**Acceptance Scenarios**:

1. **Given** an engineer submits a training job, **When** the job starts execution, **Then** the platform automatically creates an experiment run in the open-source tracking system with job metadata (model ID, dataset ID, hyperparameters) and links it to the training job record.
2. **Given** a training job records metrics during execution, **When** metrics are logged, **Then** the platform forwards metrics to the open-source tracking system in real-time, and users can view metric charts and trends in the tracking UI.
3. **Given** a training job completes, **When** artifacts (model checkpoints, logs) are generated, **Then** the platform uploads artifacts to object storage and registers artifact URIs in the open-source tracking system for versioned artifact management.
4. **Given** a user wants to compare multiple training runs, **When** they access the experiment comparison interface, **Then** they can view side-by-side metric comparisons, parameter differences, and artifact versions from the open-source tracking system.
5. **Given** a user searches for past experiments, **When** they query by model, dataset, or date range, **Then** the platform searches the open-source tracking system and returns matching experiment runs with metadata and links to detailed views.

---

### User Story 2 - Model Serving with Open Source Serving Frameworks (Priority: P1)

Service developers deploy models using industry-standard open-source serving frameworks that provide automatic scaling, health checks, and optimized inference performance, replacing custom Kubernetes deployment logic.

**Why this priority**: Serving infrastructure is critical for production workloads and open-source frameworks provide battle-tested features (autoscaling, batching, multi-GPU support) that are difficult to implement and maintain from scratch.

**Independent Test**: Deploy a model through the platform UI, verify it uses the open-source serving framework, confirm automatic scaling works under load, and validate inference requests are routed correctly.

**Acceptance Scenarios**:

1. **Given** a developer deploys a model as a serving endpoint, **When** the deployment is initiated, **Then** the platform creates a serving deployment using the open-source framework (e.g., KServe InferenceService, Ray Serve deployment) instead of raw Kubernetes resources, and the endpoint becomes available through the standard `/llm-ops/v1` API.
2. **Given** a serving endpoint receives high traffic, **When** request rate exceeds configured thresholds, **Then** the open-source serving framework automatically scales replicas based on CPU/memory/GPU utilization or request queue depth, and the platform reflects updated replica counts in endpoint status.
3. **Given** a serving endpoint is deployed, **When** users send inference requests, **Then** requests are routed to the open-source serving framework which handles batching, model loading, and inference execution, returning responses through the standard API contract.
4. **Given** a model requires GPU resources, **When** the serving framework schedules pods, **Then** it properly requests GPU resources, handles multi-GPU model parallelism if configured, and reports GPU utilization metrics to the platform.
5. **Given** a serving endpoint needs to be updated, **When** a new model version is deployed, **Then** the open-source serving framework supports canary deployments or blue-green rollouts, allowing gradual traffic migration and automatic rollback on health check failures.

---

### User Story 3 - Workflow Orchestration with Open Source Pipelines (Priority: P2)

Data engineers and ML engineers define and execute complex training and evaluation pipelines using open-source workflow orchestration tools, replacing custom job scheduling logic.

**Why this priority**: Workflow orchestration enables complex multi-stage pipelines (data preparation → training → evaluation → deployment) and open-source tools provide visual pipeline editors, dependency management, and retry/error handling that reduce operational overhead.

**Independent Test**: Define a training pipeline with multiple stages (data validation, training, evaluation), submit it through the platform, verify stages execute in correct order with dependency resolution, and confirm pipeline status is visible in both the platform UI and orchestration tool UI.

**Acceptance Scenarios**:

1. **Given** an engineer defines a training pipeline with multiple stages, **When** they submit the pipeline, **Then** the platform creates a workflow in the open-source orchestration system with defined stages, dependencies, and resource requirements, and execution begins automatically.
2. **Given** a pipeline stage fails, **When** the failure is detected, **Then** the open-source orchestration system retries the stage according to configured retry policies, and the platform updates pipeline status and notifies users of retry attempts.
3. **Given** a pipeline requires conditional execution, **When** a stage completes with specific outcomes, **Then** the open-source orchestration system evaluates conditions and branches to appropriate next stages, and the platform reflects the execution path in pipeline visualization.
4. **Given** multiple pipelines are submitted, **When** they compete for GPU resources, **Then** the open-source orchestration system queues pipelines based on priority and resource availability, and the platform shows queue position and estimated start time.
5. **Given** a user wants to monitor pipeline execution, **When** they access the pipeline detail page, **Then** they can view real-time execution status, stage logs, and resource usage from the open-source orchestration system integrated into the platform UI.

---

### User Story 4 - Model Registry Integration with Open Source Hubs (Priority: P2)

Researchers register and discover models through integration with open-source model registries and hubs, enabling model sharing, versioning, and metadata management beyond the platform's internal catalog.

**Why this priority**: Model registries provide standardized model formats, metadata schemas, and discovery mechanisms that enhance collaboration and reduce duplicate model storage. Integration enables importing models from public registries and exporting platform models for external use.

**Independent Test**: Import a model from an open-source model registry (e.g., Hugging Face Hub) into the platform catalog, verify metadata and files are correctly transferred, and confirm the model can be deployed as a serving endpoint.

**Acceptance Scenarios**:

1. **Given** a researcher wants to import a model from an open-source registry, **When** they provide the model identifier (e.g., Hugging Face model ID), **Then** the platform fetches model metadata, downloads model files, validates compatibility, and creates a catalog entry with imported metadata and storage URI.
2. **Given** a model is registered in the platform catalog, **When** a user exports it to an open-source registry, **Then** the platform uploads model files, publishes metadata in the registry's format, and creates a public or private registry entry with version tags.
3. **Given** a model in the catalog references an open-source registry model, **When** users view the model detail page, **Then** they can see registry metadata (model card, license, usage examples) and links to the original registry entry.
4. **Given** an open-source registry model is updated, **When** a user checks for updates, **Then** the platform queries the registry for new versions, notifies users of available updates, and allows one-click import of new versions.
5. **Given** models are stored in both platform catalog and open-source registry, **When** users search for models, **Then** search results include both internal catalog models and registry models (with import option), unified through a single search interface.

---

### User Story 5 - Data Versioning with Open Source Tools (Priority: P3)

Data engineers version datasets and track dataset lineage using open-source data version control tools, replacing custom dataset versioning implementations.

**Why this priority**: Data versioning is critical for reproducibility and open-source tools provide efficient storage (deduplication, compression), diff visualization, and lineage tracking that are complex to implement correctly.

**Independent Test**: Create a dataset version, modify the dataset, create a new version, verify the tool tracks changes efficiently (not storing duplicate data), and confirm users can view diffs and rollback to previous versions.

**Acceptance Scenarios**:

1. **Given** a data engineer uploads a dataset, **When** they create a new dataset version, **Then** the platform uses the open-source data versioning tool to store the dataset efficiently (deduplication, compression), track version metadata, and link versions in the catalog.
2. **Given** a dataset is modified, **When** a new version is created, **Then** the open-source tool calculates and stores only differences from previous versions, and the platform displays change summaries (added/removed rows, schema changes) in the dataset detail page.
3. **Given** a user wants to compare dataset versions, **When** they select two versions, **Then** the platform queries the open-source tool for diffs and displays visual comparisons (row-level changes, schema evolution) in the UI.
4. **Given** a training job references a dataset version, **When** users view job details, **Then** they can see the exact dataset version used (with checksum/hash) and access the dataset through the versioning tool for reproducibility.
5. **Given** a dataset version needs to be restored, **When** a user requests rollback, **Then** the platform uses the open-source tool to restore the dataset files and metadata to the specified version, and updates the catalog entry accordingly.

---

### User Story 6 - Navigation Menu Reorganization with Dropdown Groups (Priority: P2)

Users navigate the platform through a reorganized top navigation menu that groups related features into dropdown menus, improving discoverability and reducing visual clutter while maintaining quick access to all functionality.

**Why this priority**: Navigation organization directly impacts user experience and productivity. Grouping related features (Catalog, ML Operations, Governance) makes the platform more intuitive and scalable as new features are added. This is a UX improvement that can be implemented independently without affecting backend functionality.

**Independent Test**: Access the platform UI, verify the top navigation displays grouped dropdown menus (Catalog, ML Operations, Governance, Admin), confirm all existing routes remain accessible through the dropdowns, and validate that the active route is properly highlighted in the navigation.

**Acceptance Scenarios**:

1. **Given** a user accesses the platform, **When** they view the top navigation bar, **Then** they see grouped dropdown menus: "Catalog" (containing Models, Datasets), "ML Operations" (containing Training, Experiments, Serving), "Governance" (containing Policies, Audit, Costs), "Admin" (containing Integrations), and "Getting Started" as a standalone link.
2. **Given** a user hovers over or clicks a dropdown menu (e.g., "Catalog"), **When** the dropdown opens, **Then** they see all submenu items (Models, Datasets) with clear labels and can click to navigate to the respective pages.
3. **Given** a user navigates to a page (e.g., "/catalog/models"), **When** they view the navigation, **Then** the parent dropdown menu ("Catalog") and the active submenu item ("Models") are visually highlighted to indicate the current location.
4. **Given** a user is on a page within a dropdown group (e.g., Training under ML Operations), **When** they navigate to another page in the same group (e.g., Experiments), **Then** the navigation maintains the dropdown state and highlights the new active item without requiring the user to reopen the dropdown.
5. **Given** a user accesses the platform on a mobile or narrow screen, **When** the viewport is too small for horizontal navigation, **Then** the navigation adapts to a mobile-friendly format (e.g., hamburger menu) that preserves the dropdown grouping structure.

---

### Edge Cases

- What happens when an open-source tool service is unavailable? The platform must gracefully degrade (e.g., fall back to basic logging if experiment tracking is down) and queue operations for retry when the service recovers.
- How does the system handle version compatibility between platform and open-source tools? The platform must support multiple tool versions during migration and provide upgrade paths without breaking existing workflows.
- How is the `{status,message,data}` contract honored when open-source tool APIs return errors? The platform must wrap open-source tool errors in standardized error responses and provide actionable error messages to users.
- What happens when open-source tool configurations differ between DEV/STG/PROD environments? The platform must support environment-specific tool configurations and validate consistency during deployment.
- How does the system handle data migration from custom implementations to open-source tools? Migration scripts must preserve existing data, support rollback, and provide progress tracking for large datasets.
- What happens when a training job or serving deployment is submitted in a local development environment without GPU support? The platform must automatically detect GPU unavailability, select CPU-based images from configuration, and adjust resource requests accordingly (CPU/memory instead of GPU). Training jobs submitted with `use_gpu=False` must use CPU images regardless of GPU availability.
- How does the platform handle GPU detection failures or ambiguous GPU availability states? The platform must default to CPU-based images when GPU detection fails or is ambiguous, ensuring local development environments can function without GPU hardware. Administrators must be able to explicitly configure GPU/CPU preference through environment variables or configuration.
- What happens when a user navigates directly to a deep route (e.g., via bookmark or direct URL)? The navigation menu must correctly identify and highlight the active page and parent dropdown group, even when the page is accessed without going through the navigation menu.
- How does the navigation handle dynamic routes (e.g., `/catalog/models/:id`)? The navigation must recognize dynamic route patterns and highlight the appropriate parent menu item (e.g., "Models" under "Catalog") when viewing model detail pages.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST integrate an open-source experiment tracking system for training job metadata, metrics, and artifacts. The system MUST automatically create experiment runs when training jobs start, forward metrics in real-time, and store artifact references. Users MUST be able to view experiment history, compare runs, and search experiments through the integrated UI.
- **FR-002**: The platform MUST use an open-source model serving framework for deploying inference endpoints. The framework MUST support automatic scaling, health checks, GPU resource management, and canary deployments. All serving endpoints MUST remain accessible through the existing `/llm-ops/v1` API contract regardless of the underlying serving framework.
- **FR-003**: The platform MUST integrate an open-source workflow orchestration tool for complex multi-stage pipelines (training, evaluation, deployment). The tool MUST support dependency management, conditional execution, retry policies, and resource queuing. Pipeline definitions MUST be manageable through the platform UI and API.
- **FR-004**: The platform MUST integrate with open-source model registries for model import/export. Users MUST be able to import models from registries (with metadata and files), export platform models to registries, and view registry metadata in catalog entries. The platform MUST support at least one major model registry (e.g., Hugging Face Hub) with extensibility for additional registries.
- **FR-005**: The platform MUST use an open-source data versioning tool for dataset storage and versioning. The tool MUST support efficient storage (deduplication, compression), version diffs, and lineage tracking. Dataset versions MUST be linked to training jobs for reproducibility.
- **FR-006**: All open-source tool integrations MUST maintain backward compatibility with existing `/llm-ops/v1` API endpoints. Users MUST not experience breaking changes to API contracts, request/response formats, or authentication mechanisms.
- **FR-007**: The platform MUST provide configuration management for open-source tools. Administrators MUST be able to configure tool endpoints, credentials, resource limits, and feature flags through environment variables or configuration files. Configuration MUST support environment-specific settings (dev/stg/prod).
- **FR-008**: The platform MUST handle open-source tool service failures gracefully. When a tool service is unavailable, the platform MUST queue operations for retry, provide fallback behavior where possible, and surface clear error messages to users. Critical operations (e.g., training job submission) MUST not be blocked by tool unavailability.
- **FR-009**: The platform MUST support migration from custom implementations to open-source tools. Migration scripts MUST preserve existing data, support incremental migration, provide rollback capabilities, and include progress tracking and validation steps.
- **FR-010**: The platform MUST provide unified observability across open-source tools and custom components. Metrics, logs, and traces from open-source tools MUST be integrated into the platform's monitoring dashboard, and alerts MUST be configurable for tool-specific events (e.g., experiment tracking service down, serving framework scaling failures).
- **FR-011**: Users MUST be able to access open-source tool UIs directly when needed (e.g., advanced experiment visualization, detailed pipeline graphs) while maintaining the platform UI as the primary interface for common workflows. Tool UIs MUST be accessible through authenticated links from the platform UI.
- **FR-012**: The platform MUST document open-source tool selection rationale, integration architecture, and operational procedures. Documentation MUST include tool-specific configuration guides, troubleshooting steps, and upgrade procedures for platform maintainers.
- **FR-013**: For any capability that is fully covered by an integrated open-source tool, the platform MUST NOT maintain a parallel custom implementation. Legacy code paths that duplicate open-source functionality MUST be either removed or clearly deprecated behind feature flags, ensuring there is no long-term duplication of behavior between in-house code and open-source integrations.
- **FR-014**: The platform MUST reorganize the top navigation menu into grouped dropdown menus. Navigation MUST group related features: "Catalog" (Models, Datasets), "ML Operations" (Training, Experiments, Serving), "Governance" (Policies, Audit, Costs), "Admin" (Integrations), with "Getting Started" as a standalone link. All existing routes MUST remain accessible through the new navigation structure.
- **FR-015**: The navigation dropdown menus MUST clearly indicate the active page by highlighting both the parent dropdown group and the active submenu item. Navigation MUST maintain dropdown state when navigating between pages within the same group to reduce user interaction overhead.
- **FR-016**: The navigation MUST be responsive and adapt to mobile/narrow screen sizes. On small viewports, the navigation MUST transform to a mobile-friendly format (e.g., hamburger menu or collapsible sidebar) that preserves the dropdown grouping structure and maintains access to all features.
- **FR-017**: The platform MUST enforce the TrainJobSpec schema structure from `docs/training-serving-spec.md` for all training job submissions. Training jobs MUST include: job_type (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING), model_family (from whitelist: llama, mistral, gemma, bert, etc.), base_model_ref (null for PRETRAIN, required for others), dataset_ref (with type matching job_type requirements), hyperparams (lr, batch_size, num_epochs, max_seq_len, precision), method (full, lora, qlora), resources (gpus, gpu_type, nodes), and output (artifact_name, save_format). The platform MUST reject training jobs that do not conform to this schema.
- **FR-018**: The platform MUST enforce model_family whitelist validation. Only model families defined in the training-serving-spec.md (llama, mistral, gemma, bert, etc.) MUST be allowed for training and serving. Training jobs or serving deployments referencing unsupported model families MUST be rejected with clear error messages.
- **FR-019**: The platform MUST automatically select training container images based on job_type according to the training-serving-spec.md mapping (PRETRAIN → pretrain image, SFT → sft image, RAG_TUNING → rag image, RLHF → rlhf image, EMBEDDING → embedding image). The platform MUST support both GPU and CPU variants for each job_type. Image selection MUST consider GPU availability and `use_gpu` flag: when GPU is unavailable or `use_gpu=False`, the platform MUST automatically select CPU-based images. Users MUST NOT override train_image selection; the platform MUST enforce image selection based on job_type and GPU availability.
- **FR-020**: The platform MUST validate dataset_ref.type compatibility with job_type. For example, PRETRAIN jobs MUST use datasets with type "pretrain_corpus", SFT jobs MUST use "sft_pair", RAG_TUNING jobs MUST use "rag_qa", and RLHF jobs MUST use "rlhf_pair". Incompatible dataset types MUST be rejected during job submission validation.
- **FR-021**: The platform MUST enforce the DeploymentSpec schema structure from `docs/training-serving-spec.md` for all serving deployments. Serving deployments MUST include: model_ref, model_family, job_type (from training job), serve_image (GENERATION or RAG based on job_type and model purpose), resources (gpus, gpu_memory_gb), runtime constraints (max_concurrent_requests, max_input_tokens, max_output_tokens), and rollout strategy (blue-green or canary with traffic_split). The platform MUST reject serving deployments that do not conform to this schema.
- **FR-022**: The platform MUST automatically select serving container images based on serve_target type according to the training-serving-spec.md mapping. GENERATION type models MUST use images.serve.GENERATION, RAG type models MUST use images.serve.RAG. The platform MUST support both GPU and CPU variants for each serve_target type. Image selection MUST consider GPU availability: when GPU is unavailable, the platform MUST automatically select CPU-based images. The platform MUST enforce image selection based on the model's intended serving purpose (generation vs. RAG) and GPU availability, and users MUST NOT override serve_image selection.
- **FR-023**: The platform MUST validate model_family and job_type compatibility for serving deployments. For example, RAG_TUNING job outputs MUST be deployed with serve_target type "RAG", while SFT and RLHF outputs typically use "GENERATION". The platform MUST reject incompatible job_type and serve_target combinations during deployment validation.
- **FR-024**: The platform MUST convert TrainJobSpec structures to open-source tool native formats for storage and execution. TrainJobSpec fields MUST be mapped to MLflow run parameters, Argo Workflow step definitions, and other tool-specific formats. The platform MUST maintain bidirectional conversion logic (TrainJobSpec ↔ tool native format) to ensure data consistency and tool interoperability.
- **FR-025**: The platform MUST convert DeploymentSpec structures to open-source serving framework native formats (e.g., KServe InferenceService YAML, Ray Serve deployment config). DeploymentSpec fields MUST be mapped to framework-specific configuration, and the platform MUST store the converted formats while maintaining the ability to reconstruct the original DeploymentSpec for validation and display.
- **FR-026**: The platform MUST provide conversion adapters for each open-source tool integration. Adapters MUST handle mapping between training-serving-spec.md structures and tool-specific formats, validate conversions, and provide error messages when conversion fails due to incompatible specifications or missing required fields.
- **FR-027**: The platform MUST manage container image versions through centralized configuration (ConfigMap, environment variables, or configuration files). Image mappings from training-serving-spec.md (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING training images, and GENERATION, RAG serving images) MUST be stored in configuration with both `gpu` and `cpu` variants for each image type. Administrators MUST be able to update image versions without code changes. The platform MUST support environment-specific image configurations (dev/stg/prod), and MUST support CPU-based images for local development environments without GPU hardware.
- **FR-028**: The platform MUST read container image assignments from configuration at runtime. When a training job is submitted, the platform MUST look up the appropriate training image based on job_type and GPU availability (or `use_gpu` flag) from configuration, selecting GPU or CPU variant accordingly. When a serving deployment is created, the platform MUST look up the appropriate serving image based on serve_target type and GPU availability from configuration. The platform MUST implement GPU availability detection logic to automatically determine whether to use GPU or CPU images. Users MUST NOT be able to override image selection; images MUST be determined automatically from configuration based on job_type or serve_target and GPU availability.
- **FR-029**: The platform MUST validate all training job submissions immediately against training-serving-spec.md rules (model_family whitelist, dataset type compatibility, base_model_ref requirements, method constraints, etc.). Jobs that fail validation MUST be rejected with clear error messages indicating which rule was violated. Validation MUST occur before job submission is accepted.
- **FR-030**: The platform MUST validate all serving deployment requests immediately against training-serving-spec.md DeploymentSpec rules (model_family compatibility, job_type and serve_target compatibility, resource constraints, etc.). Deployments that fail validation MUST be rejected with clear error messages.
- **FR-031**: The platform MUST re-validate existing training jobs and serving endpoints against training-serving-spec.md rules. Jobs or deployments that do not satisfy the spec MUST be marked as non-compliant and MUST be rejected for execution or updates. The platform MUST provide migration guidance or tools to help users update non-compliant jobs to meet the spec requirements.
- **FR-032**: Training job submission UI MUST obtain selectable GPU types from a backend API that sources its list from configuration/DB (e.g., env/ConfigMap or integration config). Hardcoded GPU type options in the frontend are prohibited. The backend MUST validate requested gpu_type against the configured list per environment.
- **FR-033**: The platform MUST provide a Helm-based deployment package that installs core dependencies (PostgreSQL, Redis, MinIO), NVIDIA device plugin, and KServe using the official KServe Helm chart. Namespace creation MUST be handled via Helm CLI `--namespace --create-namespace` (no namespace manifests). Default service ports MUST match the existing scripts (PostgreSQL 5432, Redis 6379, MinIO API 9000, MinIO Console 9001).
- **FR-034**: The Helm package MUST configure GPU time-slicing by default with NVIDIA device plugin (kube-system) exposing 10 slices per GPU via timeSlicing. It MUST include post-install/upgrade hooks that (a) create or reuse a self-signed webhook certificate for KServe if cert-manager is absent, (b) patch KServe webhooks with the CA bundle, and (c) set `inferenceservice-config` `defaultDeploymentMode=Standard` (RawDeployment) in the KServe namespace.

### Key Entities *(include if feature involves data)*

- **ExperimentRun**: Represents a training job execution tracked in the open-source experiment tracking system. Links to TrainingJob, stores parameters, metrics, and artifact URIs. May include tracking system-specific metadata (run ID, experiment name, tags).
- **ServingDeployment**: Represents a model serving endpoint deployed through an open-source serving framework. Links to ServingEndpoint, stores framework-specific configuration (replica counts, autoscaling policies, resource requests). May include framework-specific status and metrics.
- **WorkflowPipeline**: Represents a multi-stage pipeline definition and execution in the open-source orchestration tool. Links to TrainingJob or EvaluationRun, stores stage definitions, dependencies, and execution history. May include pipeline-specific metadata (workflow ID, DAG definition).
- **RegistryModel**: Represents a model imported from or exported to an open-source model registry. Links to ModelCatalogEntry, stores registry-specific metadata (registry ID, version tags, registry URL). May include registry-specific fields (model card, license, usage examples).
- **DatasetVersion**: Represents a dataset version managed by the open-source data versioning tool. Links to DatasetRecord, stores version metadata (checksum, diff summary, parent version). May include versioning tool-specific references (commit hash, branch name).
- **TrainJobSpec**: Represents a training job specification conforming to the structure defined in training-serving-spec.md. Includes job_type (PRETRAIN, SFT, RAG_TUNING, RLHF, EMBEDDING), model_family (from whitelist), base_model_ref (reference to base model for fine-tuning jobs), dataset_ref (with name, version, type, storage_uri), hyperparams (lr, batch_size, num_epochs, max_seq_len, precision), method (full, lora, qlora), resources (gpus, gpu_type, nodes), and output (artifact_name, save_format). Links to TrainingJob entity.
- **ModelFamily**: Represents a supported model architecture family (llama, mistral, gemma, bert, etc.) from the whitelist defined in training-serving-spec.md. Each ModelFamily has associated HuggingFace architecture identifier, minimum version requirements, and usage constraints (e.g., EMBEDDING-only families).
- **DeploymentSpec**: Represents a deployment specification for serving trained models. Includes model_ref, model_family, job_type, serve_image (GENERATION or RAG), resources (gpus, gpu_memory_gb), runtime constraints (max_concurrent_requests, max_input_tokens, max_output_tokens), and rollout strategy (blue-green, canary). Links to ServingEndpoint and TrainingJob.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of new training jobs automatically create experiment runs in the open-source tracking system within 30 seconds of job start, and 95% of experiment metadata queries return results in under 2 seconds.
- **SC-002**: Serving endpoints deployed through open-source frameworks achieve 99.5% availability (same as current target), and autoscaling responds to traffic spikes within 60 seconds (improvement over custom implementation).
- **SC-003**: Complex multi-stage pipelines (3+ stages) execute with correct dependency resolution 99% of the time, and pipeline definition time reduces from 30 minutes to under 10 minutes using visual pipeline editors.
- **SC-004**: Model import from open-source registries completes successfully for 95% of standard model formats, and import time for models under 10GB is under 5 minutes including metadata transfer.
- **SC-005**: Dataset versioning operations (create version, diff, rollback) complete in under 30 seconds for datasets under 100GB, and storage efficiency improves by at least 30% compared to full dataset copies through deduplication.
- **SC-006**: Platform API response times remain within 10% of current performance after open-source tool integration, and no breaking changes to `/llm-ops/v1` API contracts occur during migration.
- **SC-007**: Open-source tool service availability (experiment tracking, serving framework, orchestration) maintains 99.9% uptime, and service failures are detected and reported within 1 minute.
- **SC-008**: Migration from custom implementations to open-source tools completes for all critical components (experiment tracking, serving, workflows) within 3 months, with zero data loss and rollback capability maintained throughout the process.
- **SC-009**: Navigation menu reorganization completes with 100% of existing routes accessible through the new dropdown structure, and users can navigate to any page within 2 clicks from the home page. Navigation highlighting correctly identifies the active page 100% of the time.
- **SC-010**: Responsive navigation adapts correctly to screen widths from 320px (mobile) to 2560px (desktop), and mobile navigation maintains full feature access with no functionality loss compared to desktop navigation.
