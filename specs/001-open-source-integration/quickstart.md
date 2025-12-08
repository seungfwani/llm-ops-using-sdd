# Quickstart: Open Source Integration Setup

**Branch**: `001-open-source-integration`  
**Date**: 2025-01-27

---

## 1. Prerequisites

1. Kubernetes cluster with GPU nodes (existing platform requirement)
2. PostgreSQL 14+ database (existing platform requirement)
3. MinIO/S3 object storage (existing platform requirement)
4. Redis cluster (existing platform requirement)
5. Admin access to Kubernetes cluster for deploying open-source tools
6. Python 3.11+ and Poetry for backend development
7. Node.js 18+ and npm for frontend development

---

## 2. Open Source Tool Installation

### 2.1 MLflow Tracking Server

**Purpose**: Experiment tracking for training jobs

**Installation**:

```bash
# Create namespace
kubectl create namespace mlflow

# Deploy MLflow Tracking Server
kubectl apply -f infra/k8s/mlflow/mlflow-server.yaml

# Verify deployment
kubectl get pods -n mlflow
kubectl get svc -n mlflow
```

**Configuration**:

Set environment variables in `backend/.env`:

```bash
# MLflow Configuration
MLFLOW_TRACKING_URI=http://mlflow-service.mlflow.svc.cluster.local:5000
MLFLOW_ENABLED=true
MLFLOW_BACKEND_STORE_URI=postgresql://user:pass@postgres:5432/mlflow
MLFLOW_DEFAULT_ARTIFACT_ROOT=s3://mlflow-artifacts/
```

**Access MLflow UI**:

```bash
# Port-forward to access UI locally
kubectl port-forward -n mlflow svc/mlflow-service 5000:5000

# Open browser: http://localhost:5000
```

---

### 2.2 KServe (Enhanced Integration)

**Purpose**: Model serving framework (already partially integrated)

**Installation** (if not already installed):

```bash
# Install KServe
kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml

# Verify installation
kubectl get pods -n kserve-system
```

**Configuration**:

Update `backend/.env`:

```bash
# KServe Configuration
USE_KSERVE=true
KSERVE_NAMESPACE=kserve
KSERVE_DEFAULT_PREDICTOR=kserve
```

**Note**: KServe integration is already partially implemented. This enhances existing functionality.

---

### 2.3 Argo Workflows

**Purpose**: Workflow orchestration for multi-stage pipelines

**Installation**:

```bash
# Install Argo Workflows
kubectl create namespace argo
kubectl apply -n argo -f https://github.com/argoproj/argo-workflows/releases/download/v3.5.0/install.yaml

# Install Argo CLI (optional, for local development)
# macOS
brew install argoproj/tap/argo-workflows

# Linux
curl -sLO https://github.com/argoproj/argo-workflows/releases/download/v3.5.0/argo-linux-amd64.gz
gunzip argo-linux-amd64.gz
chmod +x argo-linux-amd64
sudo mv argo-linux-amd64 /usr/local/bin/argo
```

**Configuration**:

Set environment variables in `backend/.env`:

```bash
# Argo Workflows Configuration
ARGO_WORKFLOWS_ENABLED=true
ARGO_WORKFLOWS_NAMESPACE=argo
ARGO_WORKFLOWS_CONTROLLER_SERVICE=argo-workflows-server.argo.svc.cluster.local:2746
```

**Access Argo UI**:

```bash
# Port-forward to access UI locally
kubectl port-forward -n argo svc/argo-workflows-server 2746:2746

# Open browser: http://localhost:2746
```

---

### 2.4 Hugging Face Hub Integration

**Purpose**: Model registry integration (no separate deployment needed)

**Installation**:

No separate deployment required. Uses Hugging Face Hub API and Python SDK.

**Configuration**:

Set environment variables in `backend/.env`:

```bash
# Hugging Face Hub Configuration
HUGGINGFACE_HUB_ENABLED=true
HUGGINGFACE_HUB_TOKEN=your_hf_token_here  # Optional, for private repos
HUGGINGFACE_HUB_CACHE_DIR=/tmp/hf_cache
```

**Note**: Existing `huggingface_importer.py` will be enhanced with adapter pattern.

---

### 2.5 DVC (Data Version Control)

**Purpose**: Dataset versioning and lineage tracking

**Installation**:

DVC runs as a Python library, no separate Kubernetes deployment needed. Configure remote storage:

```bash
# Install DVC Python package (already in requirements)
poetry add dvc[s3]  # For S3/MinIO support

# Configure DVC remote (pointing to existing MinIO/S3)
dvc remote add -d minio s3://datasets-dvc
dvc remote modify minio endpointurl http://minio-service.minio.svc.cluster.local:9000
dvc remote modify minio access_key_id $MINIO_ACCESS_KEY
dvc remote modify minio secret_access_key $MINIO_SECRET_KEY
```

**Configuration**:

Set environment variables in `backend/.env`:

```bash
# DVC Configuration
DVC_ENABLED=true
DVC_REMOTE_NAME=minio
DVC_REMOTE_URL=s3://datasets-dvc
DVC_CACHE_DIR=/tmp/dvc-cache
```

---

## 3. Platform Configuration

### 3.1 Backend Configuration

Update `backend/.env` with all integration settings:

```bash
# Integration Feature Flags
EXPERIMENT_TRACKING_ENABLED=true
EXPERIMENT_TRACKING_SYSTEM=mlflow
SERVING_FRAMEWORK_ENABLED=true
SERVING_FRAMEWORK_DEFAULT=kserve
WORKFLOW_ORCHESTRATION_ENABLED=true
WORKFLOW_ORCHESTRATION_SYSTEM=argo_workflows
MODEL_REGISTRY_ENABLED=true
MODEL_REGISTRY_DEFAULT=huggingface
DATA_VERSIONING_ENABLED=true
DATA_VERSIONING_SYSTEM=dvc

# Environment-specific settings
ENVIRONMENT=dev  # dev, stg, prod
```

### 3.2 Database Migrations

Run Alembic migrations to create integration tables:

```bash
cd backend
poetry run alembic upgrade head
```

This creates:
- `experiment_runs` table
- `serving_deployments` table
- `workflow_pipelines` table
- `registry_models` table
- `dataset_versions` table
- `integration_configs` table

### 3.3 Install Python Dependencies

```bash
cd backend
poetry add mlflow
poetry add kubernetes  # Already installed
poetry add dvc[s3]
poetry add huggingface-hub
poetry add argo-workflows  # If using Argo Python SDK
```

---

## 4. Training-Serving Spec Integration

### 4.1 TrainJobSpec Structure

플랫폼은 `docs/training-serving-spec.md`에 정의된 **TrainJobSpec** 구조를 사용합니다:

```yaml
TrainJobSpec:
  job_type: PRETRAIN | SFT | RAG_TUNING | RLHF | EMBEDDING
  model_family: llama | mistral | gemma | bert ...  # Whitelist 검증
  base_model_ref: null (PRETRAIN) | "model-ref" (SFT/RAG_TUNING/RLHF)
  dataset_ref:
    name: string
    version: string
    type: pretrain_corpus | sft_pair | rag_qa | rlhf_pair  # job_type과 호환성 검증
    storage_uri: string
  hyperparams:
    lr: float
    batch_size: int
    num_epochs: int
    max_seq_len: int  # base_model.max_position_embeddings 이하여야 함
    precision: fp16 | bf16
  method: full | lora | qlora  # PRETRAIN은 full만 허용
  resources:
    gpus: int
    gpu_type: string
    nodes: int
  output:
    artifact_name: string
    save_format: hf | safetensors
  use_gpu: bool  # GPU 없으면 자동으로 CPU 이미지로 fallback
```

**검증 규칙**:
- ModelFamily whitelist: 지원되는 model_family만 허용
- Dataset type 호환성: PRETRAIN → pretrain_corpus, SFT → sft_pair 등
- Base model 요구사항: PRETRAIN은 null, 다른 타입은 필수
- Method 제약: PRETRAIN은 full만, 다른 타입은 lora/qlora/full 허용
- Container image: job_type에 따라 자동 선택 (GPU/CPU 자동 fallback)

### 4.2 DeploymentSpec Structure

플랫폼은 **DeploymentSpec** 구조를 사용합니다:

```yaml
DeploymentSpec:
  model_ref: string  # 학습된 모델 artifact 참조
  model_family: string  # Training job의 model_family와 일치해야 함
  job_type: SFT | RAG_TUNING | RLHF | PRETRAIN | EMBEDDING
  serve_target: GENERATION | RAG  # job_type과 호환성 검증
  resources:
    gpus: int
    gpu_memory_gb: int
  runtime:
    max_concurrent_requests: int
    max_input_tokens: int  # model.max_position_embeddings 이하여야 함
    max_output_tokens: int
  rollout:
    strategy: blue-green | canary
    traffic_split: {old: int, new: int}  # canary 시 필수
  use_gpu: bool  # GPU 없으면 자동으로 CPU 이미지로 fallback
```

**검증 규칙**:
- Job type과 serve_target 호환성: RAG_TUNING → RAG, SFT/RLHF → GENERATION
- Model family 일치: Deployment의 model_family는 training job과 일치해야 함
- Container image: serve_target에 따라 자동 선택 (GENERATION/RAG, GPU/CPU 자동 fallback)

---

## 5. Verify Integration

### 5.1 Test Experiment Tracking with TrainJobSpec

```bash
# Submit a training job with TrainJobSpec structure
curl -X POST http://localhost:8000/llm-ops/v1/training/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "modelId": "...",
    "datasetId": "...",
    "jobType": "finetune",
    "trainJobSpec": {
      "job_type": "SFT",
      "model_family": "llama",
      "base_model_ref": "llama-3-8b-pretrain-v1",
      "dataset_ref": {
        "name": "enterprise-instruction",
        "version": "v1",
        "type": "sft_pair",
        "storage_uri": "s3://llm-datasets/enterprise-instruction/v1"
      },
      "hyperparams": {
        "lr": 0.0001,
        "batch_size": 4,
        "num_epochs": 3,
        "max_seq_len": 4096,
        "precision": "bf16"
      },
      "method": "lora",
      "resources": {
        "gpus": 2,
        "gpu_type": "A100",
        "nodes": 1
      },
      "output": {
        "artifact_name": "llama-3-8b-sft-v1",
        "save_format": "hf"
      },
      "use_gpu": true
    }
  }'

# Check experiment run was created
curl http://localhost:8000/llm-ops/v1/training/jobs/{jobId}/experiment-run

# Verify in MLflow UI
# Open http://localhost:5000 and check for new experiment run
# TrainJobSpec fields are automatically converted to MLflow parameters
```

### 5.2 Test Serving Integration with DeploymentSpec

```bash
# Deploy a model with DeploymentSpec structure (uses KServe if enabled)
curl -X POST http://localhost:8000/llm-ops/v1/serving/endpoints \
  -H "Content-Type: application/json" \
  -d '{
    "modelId": "...",
    "route": "/test-model",
    "environment": "dev",
    "deploymentSpec": {
      "model_ref": "llama-3-8b-sft-v1",
      "model_family": "llama",
      "job_type": "SFT",
      "serve_target": "GENERATION",
      "resources": {
        "gpus": 2,
        "gpu_memory_gb": 80
      },
      "runtime": {
        "max_concurrent_requests": 256,
        "max_input_tokens": 4096,
        "max_output_tokens": 1024
      },
      "rollout": {
        "strategy": "canary",
        "traffic_split": {
          "old": 90,
          "new": 10
        }
      },
      "use_gpu": true
    }
  }'

# Check deployment details
curl http://localhost:8000/llm-ops/v1/serving/endpoints/{endpointId}/deployment

# Verify KServe InferenceService was created from DeploymentSpec
kubectl get inferenceservice -n llm-ops-dev
kubectl describe inferenceservice {endpoint-name} -n llm-ops-dev
```

### 5.3 Test Model Registry

```bash
# Import model from Hugging Face Hub
curl -X POST http://localhost:8000/llm-ops/v1/catalog/models/import \
  -H "Content-Type: application/json" \
  -d '{
    "registry_type": "huggingface",
    "registry_model_id": "microsoft/DialoGPT-medium"
  }'

# Check registry links
curl http://localhost:8000/llm-ops/v1/catalog/models/{modelId}/registry-links
```

### 5.4 Test Data Versioning

```bash
# Create dataset version
curl -X POST http://localhost:8000/llm-ops/v1/catalog/datasets/{datasetId}/versions \
  -H "Content-Type: application/json" \
  -d '{
    "version_tag": "v1.0.0"
  }'

# List versions
curl http://localhost:8000/llm-ops/v1/catalog/datasets/{datasetId}/versions

# Compare versions
curl http://localhost:8000/llm-ops/v1/catalog/datasets/{datasetId}/versions/{versionId}/diff?baseVersionId={baseId}
```

---

## 6. Troubleshooting

### 6.1 MLflow Connection Issues

```bash
# Check MLflow pod status
kubectl get pods -n mlflow

# Check MLflow logs
kubectl logs -n mlflow deployment/mlflow-server

# Verify database connection
kubectl exec -n mlflow deployment/mlflow-server -- \
  psql $MLFLOW_BACKEND_STORE_URI -c "SELECT 1"
```

### 6.2 KServe Deployment Issues

```bash
# Check KServe controller status
kubectl get pods -n kserve-system

# Check InferenceService status
kubectl describe inferenceservice -n llm-ops-dev {endpoint-name}

# Check predictor pods
kubectl get pods -n llm-ops-dev -l serving.kserve.io/inferenceservice={endpoint-name}
```

### 6.3 Argo Workflows Issues

```bash
# Check Argo Workflows controller
kubectl get pods -n argo

# Check workflow status
kubectl get workflows -n argo

# View workflow logs
argo logs -n argo {workflow-name}
```

### 6.4 DVC Storage Issues

```bash
# Test DVC remote connection
dvc remote list

# Verify S3/MinIO access
aws s3 ls s3://datasets-dvc --endpoint-url http://minio-service.minio.svc.cluster.local:9000
```

---

### 6.5 TrainJobSpec/DeploymentSpec Validation Issues

```bash
# Re-validate existing training jobs
cd backend
python scripts/validate_existing_training_jobs.py

# Re-validate existing serving endpoints
python scripts/validate_existing_serving_endpoints.py

# Validate specific job/endpoint
python scripts/validate_existing_training_jobs.py --job-id {job-id}
python scripts/validate_existing_serving_endpoints.py --endpoint-id {endpoint-id}
```

**일반적인 검증 오류**:
- `Model family 'xxx' is not supported`: 지원되지 않는 model_family 사용
- `Dataset type 'xxx' is not compatible with job_type 'yyy'`: Dataset type과 job_type 불일치
- `SFT max_seq_len must be <= base_model.max_position_embeddings`: Sequence length 초과
- `Serve target 'xxx' is not compatible with job_type 'yyy'`: Serve target과 job_type 불일치

---

## 7. Next Steps

1. **Enable integrations gradually**: Start with dev environment, then staging, then production
2. **Monitor metrics**: Set up alerts for tool service health and integration failures
3. **Train team**: Provide documentation and training on using integrated tools
4. **Iterate**: Gather feedback and refine integration based on usage patterns

---

## 8. Rollback Procedure

If issues arise, disable integrations via feature flags:

```bash
# Disable all integrations
EXPERIMENT_TRACKING_ENABLED=false
SERVING_FRAMEWORK_ENABLED=false
WORKFLOW_ORCHESTRATION_ENABLED=false
MODEL_REGISTRY_ENABLED=false
DATA_VERSIONING_ENABLED=false

# Restart backend services
kubectl rollout restart deployment/llm-ops-backend -n llm-ops-dev
```

Platform will fall back to custom implementations automatically.

또한 필요 시 다음 스크립트를 활용할 수 있습니다.

- `backend/scripts/migrate_experiments_to_mlflow.py` : 기존 학습 작업 실험 메타데이터를 MLflow로 마이그레이션
- `backend/scripts/migrate_serving_to_kserve.py` : 기존 서빙 엔드포인트를 KServe InferenceService로 마이그레이션
- `backend/scripts/rollback_integrations.py` : feature flag 비활성화 및 KServe 리소스 정리 보조

