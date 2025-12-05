# LLM Ops Platform Examples

이 디렉토리에는 LLM Ops 플랫폼을 사용하는 다양한 예제 코드가 포함되어 있습니다.

## 목차

- [서빙 클라이언트 예제](#서빙-클라이언트-예제)
- [사용 방법](#사용-방법)
- [추가 예제](#추가-예제)

## 서빙 클라이언트 예제

### `serving_client.py`

서빙된 모델을 사용하는 Python 클라이언트 예제입니다.

**주요 기능:**
- 서빙 엔드포인트 배포
- 엔드포인트 목록 조회 및 필터링
- 엔드포인트 상태 확인 및 헬스 체크
- 엔드포인트 롤백
- 모델 추론 호출 (구현 예정)

**사용 예제:**

```bash
# 전체 워크플로우 예제 실행
python examples/serving_client.py workflow

# 엔드포인트 배포 및 상태 확인
python examples/serving_client.py deploy

# 엔드포인트 목록 조회
python examples/serving_client.py list

# 엔드포인트 롤백
python examples/serving_client.py rollback
```

**코드에서 직접 사용:**

```python
from examples.serving_client import ServingClient

# 클라이언트 생성
client = ServingClient(
    base_url="https://dev.llm-ops.local/llm-ops/v1",
    user_id="admin",
    user_roles="admin"
)

# 엔드포인트 배포
endpoint = client.deploy_endpoint(
    model_id="your-model-id",
    environment="dev",
    route="/llm-ops/v1/serve/my-model",
    min_replicas=1,
    max_replicas=3
)

# Healthy 상태 대기
client.wait_for_healthy(endpoint["id"])

# 헬스 체크
health = client.check_health("my-model")
print(f"Health: {health['status']}")
```

## 사용 방법

### 1. 환경 설정

예제를 실행하기 전에 필요한 패키지를 설치합니다:

```bash
cd backend
pip install requests  # 또는 poetry install
```

### 2. 환경 변수 설정

API 기본 URL과 인증 정보를 설정합니다:

```bash
export LLM_OPS_API_BASE_URL="https://dev.llm-ops.local/llm-ops/v1"
export LLM_OPS_USER_ID="your-user-id"
export LLM_OPS_USER_ROLES="admin,researcher"
```

또는 코드에서 직접 설정할 수 있습니다:

```python
client = ServingClient(
    base_url="https://dev.llm-ops.local/llm-ops/v1",
    user_id="your-user-id",
    user_roles="admin,researcher"
)
```

### 3. 예제 실행

```bash
# 전체 워크플로우 실행
python examples/serving_client.py workflow

# 특정 예제 실행
python examples/serving_client.py deploy
python examples/serving_client.py list
python examples/serving_client.py rollback
```

## 모델 등록 예제

### `register_base_model.py`

Base 모델을 카탈로그에 등록하고 서빙하는 예제입니다.

**주요 기능:**
- Base 모델 등록
- 모델 상태 업데이트 (draft → approved)
- 모델 등록 후 서빙 엔드포인트 배포
- JSON 파일에서 모델 정보 읽어서 등록

**사용 예제:**
```bash
# Base 모델 등록만 수행
python examples/register_base_model.py register

# 모델 등록 및 서빙 전체 워크플로우
python examples/register_base_model.py workflow

# JSON 파일에서 모델 정보 읽어서 등록
python examples/register_base_model.py json
```

**JSON 예제 파일:**
`model_register_example.json` 파일을 참조하여 모델 등록에 필요한 정보를 확인할 수 있습니다.

**코드에서 직접 사용:**
```python
from examples.register_base_model import CatalogClient, ServingClient

# 카탈로그 클라이언트 생성
catalog_client = CatalogClient(
    base_url="https://dev.llm-ops.local/llm-ops/v1",
    user_id="admin",
    user_roles="admin"
)

# Base 모델 등록
model = catalog_client.create_model(
    name="my-base-model",
    version="1.0",
    model_type="base",
    owner_team="ml-platform",
    metadata={
        "architecture": "transformer",
        "parameters": "7B",
        "framework": "pytorch"
    }
)

# 모델 승인
approved_model = catalog_client.update_model_status(model['id'], "approved")

# 서빙 엔드포인트 배포
serving_client = ServingClient(base_url="https://dev.llm-ops.local/llm-ops/v1")
endpoint = serving_client.deploy_endpoint(
    model_id=approved_model['id'],
    environment="dev",
    route="/llm-ops/v1/serve/my-base-model"
)
```

### `download_and_register_hf_model.py`

Hugging Face에서 모델을 다운로드하고 등록하는 예제입니다.

**주의사항:**
- 현재 시스템은 Hugging Face에서 직접 import하는 기능이 아직 구현되지 않았습니다.
- 모델 파일은 매우 클 수 있으므로(수 GB ~ 수십 GB), 프로덕션 환경에서는 별도의 워크플로우를 사용하는 것을 권장합니다.
- Hugging Face Import 기능은 PRD에 계획되어 있으며 향후 구현 예정입니다.

**사용 방법:**

1. **Hugging Face 라이브러리 설치:**
```bash
pip install huggingface_hub
```

2. **모델 다운로드 및 등록:**
```bash
# Hugging Face에서 모델 다운로드 후 등록
python examples/download_and_register_hf_model.py download
```

3. **이미 업로드된 모델 등록:**
```bash
# storage_uri를 사용하여 이미 S3에 업로드된 모델 등록
python examples/download_and_register_hf_model.py register
```

**코드에서 직접 사용:**
```python
from examples.download_and_register_hf_model import (
    HuggingFaceModelDownloader,
    CatalogClient
)

# Hugging Face 모델 다운로드
downloader = HuggingFaceModelDownloader()
model_path = downloader.download_model("meta-llama/Llama-2-7b-chat-hf")

# 모델 등록
catalog_client = CatalogClient(base_url="https://dev.llm-ops.local/llm-ops/v1")
model = catalog_client.create_model(
    name="llama_2_7b_chat",
    version="1.0",
    model_type="base",
    owner_team="ml-platform",
    metadata={
        "source": "huggingface",
        "huggingface_model_id": "meta-llama/Llama-2-7b-chat-hf",
        "architecture": "llama",
        "parameters": "7B",
        "framework": "pytorch"
    },
    storage_uri="s3://models/llama_2_7b_chat/1.0/"
)
```

**대안 방법:**

Hugging Face에서 직접 import하는 기능이 아직 없으므로, 다음 방법을 사용할 수 있습니다:

1. **수동 다운로드 후 업로드:**
   - Hugging Face에서 모델을 다운로드
   - 모델 파일을 S3/객체 스토리지에 업로드
   - `storage_uri`를 지정하여 모델 등록

2. **storage_uri로 참조:**
   - 이미 S3에 업로드된 모델의 경우 `storage_uri`만 지정하여 등록

3. **API를 통한 파일 업로드:**
   - 모델 등록 후 `/catalog/models/{model_id}/upload` API로 파일 업로드

## Fine-tuning 예제 데이터셋

### `datasets/` 디렉토리

Fine-tuning을 테스트하기 위한 샘플 데이터셋 파일들이 포함되어 있습니다.

**포함된 데이터셋:**
- `customer-support-sample.csv` - Customer support 챗봇 fine-tuning용 (10개 샘플)
- `code-generation-sample.jsonl` - Code generation 모델 fine-tuning용 (10개 샘플)

**사용 방법:**
1. 데이터셋을 카탈로그에 등록
2. 데이터셋 파일 업로드 (`POST /catalog/datasets/{dataset_id}/upload`)
3. Base 모델 선택 후 fine-tuning job 제출

자세한 사용 방법은 [`datasets/README.md`](./datasets/README.md)를 참조하세요.

**예제 워크플로우:**
```bash
# 1. Base 모델 등록
python examples/register_base_model.py register

# 2. 데이터셋 생성 및 업로드 (UI 또는 API 사용)
# 3. Fine-tuning job 제출 (UI: /training/jobs/submit 또는 API)
```

## 전체 워크플로우 예제

### `complete_workflow_example.py`

데이터셋 등록부터 모델 서빙 및 채팅 테스트까지의 전체 과정을 자동으로 실행하는 예제입니다.

**주요 기능:**
- 데이터셋 등록 및 업로드
- Base 모델 등록
- 모델 승인
- (선택) 학습 작업 제출
- 서빙 엔드포인트 배포 (DeploymentSpec 포함)
- 채팅 테스트

**사용 예제:**
```bash
# 전체 워크플로우 자동 실행
python examples/complete_workflow_example.py

# 환경 변수와 함께 실행
LLM_OPS_API_BASE_URL="http://localhost:8000/llm-ops/v1" \
USE_GPU="false" \
python examples/complete_workflow_example.py
```

**코드에서 직접 사용:**
```python
from examples.complete_workflow_example import (
    CatalogClient,
    TrainingClient,
    ServingClient
)

# 클라이언트 생성 (llm-ops-user 역할 필수)
base_url = "http://localhost:8000/llm-ops/v1"
user_roles = "admin,llm-ops-user"  # governance 미들웨어 요구사항
catalog_client = CatalogClient(base_url, user_roles=user_roles)
training_client = TrainingClient(base_url, user_roles=user_roles)
serving_client = ServingClient(base_url, user_roles=user_roles)

# 1. 데이터셋 등록
dataset = catalog_client.create_dataset(
    name="my-dataset",
    version="v1.0"
)

# 2. 모델 등록
model = catalog_client.create_model(
    name="my-model",
    version="1.0",
    model_type="base"
)

# 3. 모델 승인
approved_model = catalog_client.update_model_status(model['id'], "approved")

# 4. 서빙 엔드포인트 배포
endpoint = serving_client.deploy_endpoint(
    model_id=approved_model['id'],
    environment="dev",
    route="/llm-ops/v1/serve/my-model",
    deployment_spec={
        "model_ref": "my-model-1.0",
        "model_family": "llama",
        "job_type": "SFT",
        "serve_target": "GENERATION",
        "resources": {"gpus": 0},
        "runtime": {
            "max_concurrent_requests": 256,
            "max_input_tokens": 4096,
            "max_output_tokens": 1024
        },
        "use_gpu": False
    }
)

# 5. 채팅 테스트
response = serving_client.chat_completion(
    route_name="my-model",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)
```

자세한 내용은 [`COMPLETE_WORKFLOW.md`](./COMPLETE_WORKFLOW.md)를 참조하세요.

## 서빙 컨테이너 이미지 선택

플랫폼은 모델 서빙에 사용할 컨테이너 이미지를 자동으로 선택합니다:

### 이미지 선택 우선순위

1. **DeploymentSpec 제공 시**: `serve_target` (GENERATION 또는 RAG)과 GPU/CPU 여부에 따라 `image_config`에서 적절한 이미지 선택
   - GENERATION: vLLM 또는 TGI 이미지
   - RAG: RAG 전용 이미지
   - GPU/CPU: 환경 변수 `SERVE_IMAGE_{SERVE_TARGET}_{GPU|CPU}` 설정에 따라 선택

2. **모델 메타데이터 확인**: `DeploymentSpec`이 없을 때 모델 메타데이터에서 `huggingface_model_id` 확인
   - HuggingFace 모델 (`huggingface_model_id` 존재): TGI 이미지 사용
   - 기타 모델: vLLM 이미지 사용

3. **설정 기본값**: 위 조건이 모두 없을 때만 `SERVING_RUNTIME_IMAGE` 환경 변수 사용 (기본값: TGI)

### 이미지 설정 예제

```bash
# HuggingFace GENERATION 모델용 GPU 이미지
export SERVE_IMAGE_GENERATION_GPU=ghcr.io/huggingface/text-generation-inference:latest

# HuggingFace GENERATION 모델용 CPU 이미지 (로컬 개발)
export SERVE_IMAGE_GENERATION_CPU=ghcr.io/huggingface/text-generation-inference:latest

# vLLM GENERATION 모델용 GPU 이미지
export SERVE_IMAGE_GENERATION_GPU=ghcr.io/vllm/vllm:latest

# RAG 모델용 이미지
export SERVE_IMAGE_RAG_GPU=registry/llm-serve-rag:vllm-0.5.0-cuda12.1
export SERVE_IMAGE_RAG_CPU=registry/llm-serve-rag:cpu-v0.5.0
```

### 주의사항

- **기본값 `python:3.11-slim`은 사용하지 마세요**: 이는 서빙 런타임이 아닙니다. 플랫폼이 자동으로 감지하여 경고를 출력하고 적절한 이미지로 교체하려고 시도하지만, 명시적으로 적절한 이미지를 설정하는 것이 좋습니다.
- **HuggingFace 모델**: 모델 등록 시 `metadata.huggingface_model_id`를 포함하면 TGI 이미지가 자동으로 선택됩니다.
- **DeploymentSpec 사용 권장**: 명시적으로 `DeploymentSpec`을 제공하면 가장 정확한 이미지 선택이 보장됩니다.

## 추가 예제

더 많은 예제와 사용 사례는 다음 문서를 참조하세요:

- [전체 워크플로우 가이드](./COMPLETE_WORKFLOW.md) - 데이터/모델 등록부터 채팅까지 전체 과정
- [서빙 예제 가이드](../docs/serving-examples.md) - 서빙된 모델을 사용하는 다양한 예제
- [Fine-tuning 데이터셋 가이드](./datasets/README.md) - Fine-tuning용 예제 데이터셋 사용법
- [Quickstart 가이드](../specs/001-document-llm-ops/quickstart.md) - 플랫폼 설정 및 사용 가이드

## 주의 사항

1. **추론 API**: 모델 추론 호출 API (`call_chat_model` 등)는 현재 구현되어 있지 않습니다. PRD에 명시되어 있으나 아직 개발 중입니다.

2. **인증**: 모든 API 요청에는 `X-User-Id`와 `X-User-Roles` 헤더가 필요합니다.

3. **환경**: `dev`, `stg`, `prod` 환경에 따라 API 기본 URL이 달라집니다.

4. **에러 처리**: 모든 API 응답은 `{status, message, data}` 형식의 envelope을 사용합니다.

## 향후 계획

다음 예제들이 추가될 예정입니다:

- [x] Base 모델 등록 예제
- [x] Hugging Face 모델 등록 예제
- [ ] Hugging Face 직접 Import 기능 (PRD에 계획됨)
- [ ] JavaScript/TypeScript 클라이언트 예제
- [ ] 모델 추론 호출 예제 (추론 API 구현 후)
- [ ] 프롬프트 A/B 테스트 예제
- [ ] 배치 추론 예제
- [x] 모델 학습 예제 (Fine-tuning 데이터셋 예제 추가됨)
- [x] 데이터셋 관리 예제 (datasets/README.md에 포함됨)

## 기여하기

새로운 예제를 추가하거나 기존 예제를 개선하고 싶다면:

1. 이 디렉토리에 새로운 예제 파일을 추가하세요
2. 이 README 파일에 예제 설명을 추가하세요
3. 필요한 경우 문서화를 업데이트하세요
