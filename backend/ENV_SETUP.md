# Environment Configuration Guide

이 문서는 LLM Ops Platform의 환경변수 설정 가이드입니다.

## 빠른 시작

1. `env.example` 파일을 `.env`로 복사:
   ```bash
   cd backend
   cp env.example .env
   ```

2. 환경에 맞게 `.env` 파일 수정

3. 애플리케이션 재시작

**참고**: `env.example` 파일은 Git에 커밋되지만, `.env` 파일은 `.gitignore`에 포함되어 있어 커밋되지 않습니다.

## 환경별 설정

### 로컬 개발 환경 (Local Development)

로컬에서 개발할 때는 Kubernetes 서비스에 port-forward를 사용합니다.

```bash
# infra/scripts/port-forward-all.sh 실행
cd infra/scripts
./port-forward-all.sh dev
```

`.env` 설정:
```bash
# Database - localhost로 연결 (port-forward 사용)
DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops

# Redis - localhost로 연결
REDIS_URL=redis://localhost:6379/0

# Object Storage - localhost로 연결
OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false

# Kubernetes - 로컬 kubeconfig 사용
KUBECONFIG_PATH=~/.kube/config

# Serving - CPU-only, 작은 리소스
USE_GPU=false
USE_KSERVE=false
# Note: vllm/vllm:latest may not exist. Use one of:
#   - python:3.11-slim (lightweight, for testing)
#   - ghcr.io/vllm/vllm:latest (GitHub Container Registry)
#   - vllm/vllm-server:latest (if available)
#   - Or build your own custom image
SERVING_RUNTIME_IMAGE=python:3.11-slim

# 작은 리소스 (로컬 환경)
SERVING_CPU_ONLY_CPU_REQUEST=500m
SERVING_CPU_ONLY_CPU_LIMIT=1
SERVING_CPU_ONLY_MEMORY_REQUEST=512Mi
SERVING_CPU_ONLY_MEMORY_LIMIT=1Gi
```

### Kubernetes 클러스터 내부 (In-Cluster)

백엔드가 Kubernetes Pod로 실행될 때:

```bash
# Database - 클러스터 내부 DNS 사용
DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.llm-ops-dev.svc.cluster.local:5432/llmops

# Redis - 클러스터 내부 DNS 사용
REDIS_URL=redis://redis.llm-ops-dev.svc.cluster.local:6379/0

# Object Storage - 클러스터 내부 DNS 사용
OBJECT_STORE_ENDPOINT=http://minio.llm-ops-dev.svc.cluster.local:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false

# Kubernetes - in-cluster config 자동 사용 (비워둠)
KUBECONFIG_PATH=

# Serving - 환경에 맞게 설정
USE_GPU=true  # 또는 false
USE_KSERVE=true  # KServe 설치되어 있으면
# Use official vLLM image or custom built image
# Options: ghcr.io/vllm/vllm:latest, vllm/vllm-server:latest, or custom image
SERVING_RUNTIME_IMAGE=ghcr.io/vllm/vllm:latest

# 프로덕션 리소스
SERVING_CPU_REQUEST=2
SERVING_CPU_LIMIT=4
SERVING_MEMORY_REQUEST=4Gi
SERVING_MEMORY_LIMIT=8Gi
```

### 프로덕션 환경 (Production)

```bash
# Database - 프로덕션 PostgreSQL
DATABASE_URL=postgresql+psycopg://user:password@prod-db.example.com:5432/llmops

# Redis - 프로덕션 Redis
REDIS_URL=redis://prod-redis.example.com:6379/0

# Object Storage - 프로덕션 S3
OBJECT_STORE_ENDPOINT=https://s3.amazonaws.com
OBJECT_STORE_ACCESS_KEY=your-access-key
OBJECT_STORE_SECRET_KEY=your-secret-key
OBJECT_STORE_SECURE=true

# Kubernetes - 프로덕션 클러스터
KUBECONFIG_PATH=/path/to/prod-kubeconfig

# Serving - 프로덕션 설정
USE_GPU=true
USE_KSERVE=true
# Use specific version from official registry
# Options: ghcr.io/vllm/vllm:0.6.0, ghcr.io/vllm/vllm:latest, or custom image
SERVING_RUNTIME_IMAGE=ghcr.io/vllm/vllm:0.6.0  # 특정 버전 사용

# 프로덕션 리소스 (더 큰 값)
SERVING_CPU_REQUEST=4
SERVING_CPU_LIMIT=8
SERVING_MEMORY_REQUEST=8Gi
SERVING_MEMORY_LIMIT=16Gi
```

## 환경변수 설명

### 필수 설정

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 URL | `postgresql+psycopg://user:pass@host:5432/db` |
| `REDIS_URL` | Redis 연결 URL | `redis://host:6379/0` |
| `OBJECT_STORE_ENDPOINT` | Object Storage 엔드포인트 | `http://localhost:9000` |
| `OBJECT_STORE_ACCESS_KEY` | Object Storage 액세스 키 | `llmops` |
| `OBJECT_STORE_SECRET_KEY` | Object Storage 시크릿 키 | `llmops-secret` |

### 선택적 설정

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `SQLALCHEMY_ECHO` | `false` | SQL 쿼리 로깅 활성화 |
| `OBJECT_STORE_SECURE` | `false` | HTTPS 사용 여부 |
| `KUBECONFIG_PATH` | `None` | kubeconfig 파일 경로 (비워두면 자동 감지) |
| `USE_KSERVE` | `false` | KServe 사용 여부 |
| `USE_GPU` | `true` | GPU 리소스 요청 여부 |
| `SERVING_RUNTIME_IMAGE` | `vllm/vllm:latest` | 서빙 런타임 이미지 |
| `EXPERIMENT_TRACKING_ENABLED` | `false` | 실험 추적 통합(MLflow 등) 활성화 여부 |
| `EXPERIMENT_TRACKING_SYSTEM` | `mlflow` | 실험 추적 시스템 식별자 |
| `SERVING_FRAMEWORK_ENABLED` | `false` | KServe/Ray Serve 등 서빙 프레임워크 통합 활성화 여부 |
| `SERVING_FRAMEWORK_DEFAULT` | `kserve` | 기본 서빙 프레임워크 |
| `WORKFLOW_ORCHESTRATION_ENABLED` | `false` | Argo Workflows 등 오케스트레이션 활성화 여부 |
| `WORKFLOW_ORCHESTRATION_SYSTEM` | `argo_workflows` | 오케스트레이션 시스템 식별자 |
| `MODEL_REGISTRY_ENABLED` | `false` | Hugging Face Hub 등 모델 레지스트리 통합 활성화 여부 |
| `MODEL_REGISTRY_DEFAULT` | `huggingface` | 기본 모델 레지스트리 |
| `DATA_VERSIONING_ENABLED` | `false` | DVC 등 데이터 버저닝 통합 활성화 여부 |
| `DATA_VERSIONING_SYSTEM` | `dvc` | 데이터 버저닝 시스템 식별자 |
| `MLFLOW_TRACKING_URI` | - | MLflow Tracking Server URL |
| `MLFLOW_ENABLED` | `false` | MLflow 기능 활성화 여부 |
| `MLFLOW_BACKEND_STORE_URI` | - | MLflow 백엔드 스토어(PostgreSQL 등) URI |
| `MLFLOW_DEFAULT_ARTIFACT_ROOT` | - | MLflow 아티팩트 저장소(S3/MinIO) URI |
| `ARGO_WORKFLOWS_ENABLED` | `false` | Argo Workflows 활성화 여부 |
| `ARGO_WORKFLOWS_NAMESPACE` | `argo` | Argo Workflows 네임스페이스 |
| `ARGO_WORKFLOWS_CONTROLLER_SERVICE` | `argo-workflows-server.argo.svc.cluster.local:2746` | Argo 컨트롤러 서비스 엔드포인트 |
| `HUGGINGFACE_HUB_ENABLED` | `false` | Hugging Face Hub 통합 활성화 여부 |
| `HUGGINGFACE_HUB_TOKEN` | - | Hugging Face 토큰(프라이빗 리포지토리용) |
| `HUGGINGFACE_HUB_CACHE_DIR` | `/tmp/hf_cache` | Hugging Face 캐시 디렉터리 |
| `DVC_ENABLED` | `false` | DVC 통합 활성화 여부 |
| `DVC_REMOTE_NAME` | `minio` | DVC remote 이름 |
| `DVC_REMOTE_URL` | - | DVC remote URL (예: `s3://datasets-dvc`) |
| `DVC_CACHE_DIR` | `/tmp/dvc-cache` | DVC 캐시 디렉터리 경로 |

### 리소스 설정

#### GPU 사용 시
- `SERVING_CPU_REQUEST`: CPU 요청량 (예: "1", "500m")
- `SERVING_CPU_LIMIT`: CPU 제한 (예: "2", "1")
- `SERVING_MEMORY_REQUEST`: 메모리 요청량 (예: "2Gi", "512Mi")
- `SERVING_MEMORY_LIMIT`: 메모리 제한 (예: "4Gi", "1Gi")

#### CPU-only 사용 시
- `SERVING_CPU_ONLY_CPU_REQUEST`: CPU 요청량
- `SERVING_CPU_ONLY_CPU_LIMIT`: CPU 제한
- `SERVING_CPU_ONLY_MEMORY_REQUEST`: 메모리 요청량
- `SERVING_CPU_ONLY_MEMORY_LIMIT`: 메모리 제한

## 리소스 권장값

### 로컬 개발 (CPU-only)
```bash
SERVING_CPU_ONLY_CPU_REQUEST=500m
SERVING_CPU_ONLY_CPU_LIMIT=1
SERVING_CPU_ONLY_MEMORY_REQUEST=512Mi
SERVING_CPU_ONLY_MEMORY_LIMIT=1Gi
```

### 개발/스테이징 (GPU)
```bash
SERVING_CPU_REQUEST=1
SERVING_CPU_LIMIT=2
SERVING_MEMORY_REQUEST=2Gi
SERVING_MEMORY_LIMIT=4Gi
```

### 프로덕션 (GPU)
```bash
SERVING_CPU_REQUEST=4
SERVING_CPU_LIMIT=8
SERVING_MEMORY_REQUEST=8Gi
SERVING_MEMORY_LIMIT=16Gi
```

## 문제 해결

### 연결 오류
- 로컬에서 실행 중이면 port-forward 확인
- 클러스터 내부에서 실행 중이면 DNS 이름 확인
- Secret/ConfigMap 존재 확인

### 리소스 부족 오류
- Pod가 Pending 상태면 리소스 요청량 줄이기
- `kubectl describe pod`로 원인 확인
- `USE_GPU=false`로 CPU-only 모드 사용

### 이미지 Pull 오류
- `SERVING_RUNTIME_IMAGE` 확인
- 이미지 태그가 올바른지 확인
- 프라이빗 레지스트리면 imagePullSecrets 설정

## 보안 주의사항

⚠️ **중요**: `.env` 파일은 절대 Git에 커밋하지 마세요!

- `.env`는 `.gitignore`에 포함되어 있습니다
- 프로덕션에서는 Kubernetes Secret 사용 권장
- 민감한 정보(비밀번호, API 키)는 환경변수로 직접 설정하지 말고 Secret 사용

