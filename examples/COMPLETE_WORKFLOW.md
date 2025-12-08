# LLM Ops Platform 전체 워크플로우 가이드

이 문서는 LLM Ops 플랫폼을 사용하여 데이터셋 등록부터 모델 서빙 및 채팅 테스트까지의 전체 과정을 안내합니다.

## 목차

1. [개요](#개요)
2. [전제 조건](#전제-조건)
3. [워크플로우 단계](#워크플로우-단계)
4. [Python 스크립트 사용](#python-스크립트-사용)
5. [수동 실행 가이드](#수동-실행-가이드)
6. [문제 해결](#문제-해결)

## 개요

전체 워크플로우는 다음과 같은 단계로 구성됩니다:

```
1. 데이터셋 등록 및 업로드
   ↓
2. Base 모델 등록
   ↓
3. 모델 승인
   ↓
4. (선택) 학습 작업 제출
   ↓
5. 서빙 엔드포인트 배포 (DeploymentSpec 포함)
   ↓
6. 채팅 테스트
```

## 전제 조건

### 1. 환경 설정

```bash
# Python 패키지 설치
cd backend
pip install requests

# 또는 poetry 사용
poetry install
```

### 2. 환경 변수 설정 (선택사항)

```bash
export LLM_OPS_API_BASE_URL="http://localhost:8000/llm-ops/v1"
export LLM_OPS_USER_ID="admin"
export LLM_OPS_USER_ROLES="admin,llm-ops-user"  # llm-ops-user 역할 필수 (governance 미들웨어 요구사항)
export USE_GPU="false"  # CPU-only 모드 (개발/테스트용)
```

### 3. 플랫폼 실행 확인

백엔드 서버가 실행 중인지 확인:

```bash
curl http://localhost:8000/llm-ops/v1/health
```

## 워크플로우 단계

### Step 1: 데이터셋 등록 및 업로드

데이터셋을 카탈로그에 등록하고 파일을 업로드합니다.

**API 사용:**

```bash
# 1. 데이터셋 생성
curl -X POST "http://localhost:8000/llm-ops/v1/catalog/datasets" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin,llm-ops-user" \
  -d '{
    "name": "customer-support-dataset",
    "version": "v1.0",
    "owner_team": "ml-platform",
    "type": "sft_pair",
    "storage_uri": "s3://datasets/customer-support-dataset/v1.0/"
  }'

# 2. 데이터셋 파일 업로드
curl -X POST "http://localhost:8000/llm-ops/v1/catalog/datasets/{dataset_id}/upload" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin,llm-ops-user" \
  -F "files=@examples/datasets/customer-support-sample.csv"
```

**UI 사용:**

1. `/catalog/datasets/create` 페이지로 이동
2. 데이터셋 정보 입력 (이름, 버전, 소유 팀)
3. 파일 업로드
4. 생성 완료

### Step 2: Base 모델 등록

Base 모델을 카탈로그에 등록합니다.

**API 사용:**

```bash
curl -X POST "http://localhost:8000/llm-ops/v1/catalog/models" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin,llm-ops-user" \
  -d '{
    "name": "example-base-model",
    "version": "1.0",
    "type": "base",
    "ownerTeam": "ml-platform",
    "metadata": {
      "architecture": "transformer",
      "parameters": "7B",
      "framework": "pytorch",
      "model_family": "llama",
      "description": "Example base model"
    },
    "storageUri": "s3://models/example-base-model/1.0/",
    "status": "draft"
  }'
```

**UI 사용:**

1. `/catalog/models/create` 페이지로 이동
2. 모델 정보 입력
3. 모델 파일 업로드 (선택사항)
4. 생성 완료

### Step 3: 모델 승인

등록된 모델을 승인 상태로 변경합니다.

**API 사용:**

```bash
curl -X PATCH "http://localhost:8000/llm-ops/v1/catalog/models/{model_id}/status" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin,llm-ops-user" \
  -d '{
    "status": "approved"
  }'
```

**UI 사용:**

1. `/catalog/models/{model_id}` 페이지로 이동
2. "Approve" 버튼 클릭

### Step 4: 학습 작업 제출 (선택사항)

Base 모델을 데이터셋으로 fine-tuning합니다.

**API 사용:**

```bash
curl -X POST "http://localhost:8000/llm-ops/v1/training/jobs" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin,llm-ops-user" \
  -d '{
    "modelId": "{model_id}",
    "datasetId": "{dataset_id}",
    "jobType": "finetune",
    "useGpu": false,
    "resourceProfile": {
      "cpuCores": 4,
      "memory": "8Gi",
      "maxDuration": 60
    },
    "trainJobSpec": {
      "model_ref": "example-base-model-1.0",
      "model_family": "llama",
      "job_type": "SFT",
      "dataset_ref": "customer-support-dataset-v1.0",
      "dataset_type": "instruction",
      "resources": {
        "gpus": 0
      },
      "hyperparameters": {
        "learning_rate": 2e-5,
        "batch_size": 4,
        "num_epochs": 1
      },
      "use_gpu": false
    }
  }'
```

**UI 사용:**

1. `/training/jobs/submit` 페이지로 이동
2. Job Type: "SFT" 선택
3. Base Model 선택
4. Dataset 선택
5. Use GPU Resources 체크 해제 (CPU-only)
6. TrainJobSpec 입력
7. Submit Job 클릭

### Step 5: 서빙 엔드포인트 배포

승인된 모델을 서빙 엔드포인트로 배포합니다.

**API 사용:**

```bash
curl -X POST "http://localhost:8000/llm-ops/v1/serving/endpoints" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin,llm-ops-user" \
  -d '{
    "modelId": "{model_id}",
    "environment": "dev",
    "route": "/llm-ops/v1/serve/example-model",
    "minReplicas": 1,
    "maxReplicas": 3,
    "useGpu": false,
    "deploymentSpec": {
      "model_ref": "example-base-model-1.0",
      "model_family": "llama",
      "job_type": "SFT",
      "serve_target": "GENERATION",
      "resources": {
        "gpus": 0,
        "gpu_memory_gb": 80
      },
      "runtime": {
        "max_concurrent_requests": 256,
        "max_input_tokens": 4096,
        "max_output_tokens": 1024
      },
      "use_gpu": false
    }
  }'
```

**UI 사용:**

1. `/serving/endpoints/deploy` 페이지로 이동
2. Model 선택
3. Environment 선택 (dev)
4. Route 입력
5. DeploymentSpec 입력:
   - Model Family: llama
   - Job Type: SFT
   - Serve Target: GENERATION
   - Use GPU Resources: 체크 해제 (CPU-only)
   - Runtime Constraints 설정
6. Deploy Endpoint 클릭

### Step 6: 채팅 테스트

배포된 엔드포인트로 채팅을 테스트합니다.

**API 사용:**

```bash
curl -X POST "http://localhost:8000/llm-ops/v1/serve/example-model/chat" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: admin" \
  -H "X-User-Roles: admin,llm-ops-user" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello! Can you help me?"}
    ],
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

**UI 사용:**

1. `/serving/endpoints/{endpoint_id}` 페이지로 이동
2. "Test Chat" 버튼 클릭 (엔드포인트가 healthy 상태일 때)
3. 메시지 입력 및 전송

## Python 스크립트 사용

전체 워크플로우를 자동으로 실행하는 Python 스크립트를 제공합니다.

### 실행 방법

```bash
# 기본 실행
python examples/complete_workflow_example.py

# 환경 변수와 함께 실행
LLM_OPS_API_BASE_URL="http://localhost:8000/llm-ops/v1" \
USE_GPU="false" \
python examples/complete_workflow_example.py
```

### 스크립트 기능

- 데이터셋 자동 등록 및 업로드
- Base 모델 자동 등록
- 모델 자동 승인
- (선택) 학습 작업 제출
- 서빙 엔드포인트 자동 배포 (DeploymentSpec 포함)
- 엔드포인트 healthy 상태 대기
- 채팅 테스트 자동 실행

## 수동 실행 가이드

각 단계를 수동으로 실행하려면 다음 순서를 따르세요:

1. **데이터셋 등록**
   - UI: `/catalog/datasets/create`
   - API: `POST /catalog/datasets`

2. **모델 등록**
   - UI: `/catalog/models/create`
   - API: `POST /catalog/models`

3. **모델 승인**
   - UI: `/catalog/models/{model_id}` → "Approve"
   - API: `PATCH /catalog/models/{model_id}/status`

4. **서빙 엔드포인트 배포**
   - UI: `/serving/endpoints/deploy`
   - API: `POST /serving/endpoints`

5. **채팅 테스트**
   - UI: `/serving/chat/{endpoint_id}`
   - API: `POST /serve/{route_name}/chat`

## 문제 해결

### 엔드포인트가 healthy 상태가 되지 않는 경우

1. Kubernetes 리소스 확인:
   ```bash
   kubectl get pods -n llm-ops-dev
   kubectl logs -n llm-ops-dev serving-{endpoint_id}
   ```

2. 엔드포인트 상태 확인:
   ```bash
   curl http://localhost:8000/llm-ops/v1/serving/endpoints/{endpoint_id}
   ```

3. 모델 파일 확인:
   - 모델이 `storage_uri`에 올바르게 업로드되었는지 확인
   - 모델 파일 형식이 올바른지 확인

### 채팅 테스트 실패

1. 엔드포인트 상태 확인:
   - 엔드포인트가 "healthy" 상태인지 확인

2. Route 확인:
   - Route 이름이 올바른지 확인
   - Route 형식: `/llm-ops/v1/serve/{route_name}`

3. 모델 서빙 확인:
   - 모델이 실제로 배포되었는지 확인
   - Kubernetes pod가 실행 중인지 확인

### CPU-only 모드 사용

개발/테스트 환경에서 GPU 없이 실행하려면:

1. 환경 변수 설정:
   ```bash
   export USE_GPU="false"
   ```

2. DeploymentSpec에서 `use_gpu: false` 설정

3. 서빙 엔드포인트 배포 시 `useGpu: false` 설정

## 추가 리소스

- [예제 데이터셋](./datasets/README.md)
- [서빙 예제 가이드](../docs/serving-examples.md)
- [Quickstart 가이드](../specs/001-document-llm-ops/quickstart.md)
- [API 문서](../specs/001-document-llm-ops/spec.md)

## 참고사항

1. **GPU vs CPU**: 개발/테스트 환경에서는 CPU-only 모드를 사용할 수 있습니다. 프로덕션 환경에서는 GPU를 사용하는 것을 권장합니다.

2. **모델 파일**: 실제 모델 파일은 매우 클 수 있습니다 (수 GB ~ 수십 GB). 프로덕션 환경에서는 별도의 워크플로우로 업로드하는 것을 권장합니다.

3. **학습 작업**: 학습 작업은 선택사항입니다. Base 모델을 직접 서빙할 수도 있습니다.

4. **DeploymentSpec**: 서빙 엔드포인트 배포 시 DeploymentSpec을 제공하면 training-serving-spec.md에 따라 표준화된 방식으로 배포됩니다.

