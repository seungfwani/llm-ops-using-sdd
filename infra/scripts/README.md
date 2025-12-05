# LLM Ops Platform 배포 스크립트

이 디렉토리에는 LLM Ops 플랫폼을 배포하고 관리하기 위한 스크립트들이 포함되어 있습니다.

**minikube(로컬 개발)와 프로덕션 Kubernetes 클러스터 모두 지원합니다.**

## 환경 구분

### 로컬 개발 (Minikube)
- 로컬 머신에서 개발 및 테스트
- `minikube start`로 클러스터 시작
- 서비스 접근: `kubectl port-forward` 또는 `minikube service`
- 빠른 개발 사이클

### 프로덕션 (Kubernetes)
- 실제 운영 환경 (GKE, EKS, AKS 등)
- LoadBalancer 또는 Ingress로 외부 접근
- 클러스터 내부 DNS로 서비스 간 통신
- 고가용성 및 확장성

## 빠른 시작

### 최소 사양 배포 (권장 - 개발 환경)

**최소 사양으로 빠르게 시작하려면 `deploy-minimal.sh`를 사용하세요!**

```bash
# 최소 사양으로 배포 (CPU-only 모드)
./deploy-minimal.sh dev
```

`deploy-minimal.sh`는 다음을 자동으로 수행합니다:
1. ✅ Minikube 최소 사양으로 시작 (Memory 8GB, CPU 4코어, Disk 30GB)
2. ✅ 네임스페이스 생성
3. ✅ 의존성 서비스 배포 (최소 리소스: PostgreSQL, Redis, MinIO)
4. ✅ Object Storage Secret/ConfigMap 생성
5. ✅ MinIO 버킷 생성
6. ✅ 리소스 사용량 확인
7. ✅ Port-forward 자동 설정 (선택사항)
8. ✅ 환경 설정 안내

**참고**: 최소 사양 배포는 CPU-only 모드로 구성되며, KServe는 설치하지 않습니다.

### 전체 기능 배포 (프로덕션 또는 고급 개발)

**전체 기능을 사용하려면 `deploy-all.sh`를 사용하세요!**

```bash
# 로컬 개발 (minikube 자동 감지)
./deploy-all.sh dev

# 프로덕션 환경
./deploy-all.sh prod
```

`deploy-all.sh`는 다음을 자동으로 수행합니다:
1. ✅ 네임스페이스 생성
2. ✅ KServe 설치 확인/설치
3. ✅ 의존성 서비스 배포 (PostgreSQL, Redis, MinIO)
4. ✅ Object Storage Secret/ConfigMap 생성
5. ✅ MinIO 버킷 생성
6. ✅ 환경별 접근 방법 안내

## 스크립트 목록

### 1. `deploy-all.sh` - 전체 초기 세팅 및 배포 ⭐ **추천**
**모든 초기 세팅을 한 번에 완료합니다.** 클러스터 타입을 자동 감지하고 필요한 모든 리소스를 배포합니다.

```bash
./deploy-all.sh [environment] [--cluster-type minikube|kubernetes]
```

**기능:**
- 클러스터 타입 자동 감지 (minikube 또는 kubernetes)
- 네임스페이스 생성
- KServe 설치 확인/설치
- 의존성 서비스 배포 (PostgreSQL, Redis, MinIO)
- Object Storage Secret/ConfigMap 생성
- Models 버킷 생성
- 환경별 접근 방법 안내

**예시:**
```bash
# 로컬 개발 (minikube 자동 감지)
./deploy-all.sh dev

# 프로덕션 환경
./deploy-all.sh prod

# 클러스터 타입 강제 지정
./deploy-all.sh dev --cluster-type kubernetes
```

**자동 감지:**
- `minikube status`가 성공하면 → minikube 모드
- kubectl context에 "minikube" 포함 → minikube 모드
- 그 외 → kubernetes 모드

**환경 변수 (선택사항):**
- `KSERVE_VERSION`: KServe 버전 (기본값: v0.11.0)
- `OBJECT_STORE_ACCESS_KEY`: MinIO access key (기본값: llmops)
- `OBJECT_STORE_SECRET_KEY`: MinIO secret key (기본값: llmops-secret)
- `OBJECT_STORE_ENDPOINT`: Object store endpoint URL
- `MINIO_BUCKET_NAME`: MinIO bucket name (기본값: models)

### 2-5. 개별 스크립트들 (고급 사용자용)
> **참고:** 대부분의 경우 `deploy-all.sh`만 사용하면 됩니다. 아래 스크립트들은 특정 작업만 수행하거나 문제 해결 시 사용합니다.

#### `setup-namespaces.sh` - 네임스페이스 생성
LLM Ops 플랫폼에 필요한 Kubernetes 네임스페이스를 생성합니다.

```bash
./setup-namespaces.sh [env1] [env2] ...
```

#### `setup-kserve.sh` - KServe 통합 관리
KServe 설치, 상태 확인, Certificate 수정, 재설치를 모두 지원하는 통합 스크립트입니다.

```bash
# 설치 (기본)
./setup-kserve.sh [namespace]

# 상태 확인
./setup-kserve.sh [namespace] check

# Certificate 수정
./setup-kserve.sh [namespace] fix-cert

# 재설치
./setup-kserve.sh [namespace] reinstall
```

**기능:**
- KServe 설치 및 cert-manager 자동 처리
- 상태 확인 및 문제 진단
- Webhook certificate 수동 생성
- 재설치 지원

#### `setup-object-store.sh` - Object Storage 통합 관리 (MinIO 포함)
Object Storage Secret/ConfigMap 생성 및 MinIO 버킷 생성을 모두 지원하는 통합 스크립트입니다.

```bash
# Secret/ConfigMap 생성 (기본)
./setup-object-store.sh [namespace]

# 버킷 생성
./setup-object-store.sh [namespace] create-bucket

# Secret/ConfigMap + 버킷 생성
./setup-object-store.sh [namespace] setup-all

# 상태 확인
./setup-object-store.sh [namespace] check
```

**기능:**
- Object Storage Secret/ConfigMap 생성
- MinIO 버킷 자동 생성 (여러 방법 시도)
- 상태 확인 및 진단

> **참고:** `deploy-all.sh`가 자동으로 `setup-all` 기능을 호출합니다.

### 6. `check-resources.sh` - 리소스 사용량 확인 ⭐ **최소 사양 모니터링**
리소스 사용량을 확인하는 스크립트입니다.

```bash
./check-resources.sh [environment]
```

**기능:**
- Pod 상태 확인
- Resource requests/limits 확인
- 실제 리소스 사용량 확인 (metrics-server 필요)
- PVC 사용량 확인
- 총 리소스 요구사항 계산

**예시:**
```bash
# 리소스 사용량 확인
./check-resources.sh dev
```

**참고**: Minikube에서 metrics-server를 사용하려면:
```bash
minikube addons enable metrics-server
```

### 7. `detect-cluster.sh` - 클러스터 타입 감지 (유틸리티)
클러스터 타입을 자동으로 감지하는 유틸리티 함수입니다. 다른 스크립트에서 사용됩니다.

### 8. `test-connections.sh` - 연결 테스트
의존성 서비스들의 연결 상태를 테스트합니다.

```bash
./test-connections.sh [environment]
```

**기능:**
- PostgreSQL 연결 테스트
- Redis 연결 테스트
- MinIO 연결 테스트
- Service DNS 해상도 테스트

**예시:**
```bash
./test-connections.sh dev
```

### 9. `port-forward-all.sh` - Port-forward 시작
로컬 개발을 위해 모든 의존성 서비스를 port-forward합니다.

```bash
./port-forward-all.sh [environment]
```

**기능:**
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- MinIO API: localhost:9000
- MinIO Console: localhost:9001

**예시:**
```bash
# 백그라운드로 실행하려면
./port-forward-all.sh dev &

# 또는 포그라운드로 실행 (Ctrl+C로 중지)
./port-forward-all.sh dev
```

### 10. `serving_rollback.sh` - 서빙 엔드포인트 롤백
배포된 서빙 엔드포인트를 롤백합니다. KServe와 raw Deployment 모두 지원합니다.

```bash
./serving_rollback.sh <endpoint_id> [namespace] [--kserve]
```

**기능:**
- KServe InferenceService 자동 감지 및 롤백
- Raw Deployment 롤백
- 관련 리소스 정리 (HPA, Ingress, Service)

**예시:**
```bash
# 자동 감지 (KServe 또는 Deployment)
./serving_rollback.sh abc123-def456-ghi789 llm-ops-dev

# KServe 강제 사용
./serving_rollback.sh abc123-def456-ghi789 llm-ops-dev --kserve
```

## 배포 워크플로우

### 🚀 빠른 시작 - 최소 사양 (권장 - 개발 환경)

**최소 사양으로 빠르게 시작하려면 `deploy-minimal.sh`를 사용하세요!**

```bash
# 1. 최소 사양으로 배포 (Minikube 자동 시작 포함)
./deploy-minimal.sh dev

# 2. 리소스 사용량 확인
./check-resources.sh dev

# 3. Backend .env 설정 (이미 최소 사양으로 설정됨)
cd ../../backend
cp env.example .env

# 4. Backend 실행
poetry install
poetry run alembic upgrade head
poetry run uvicorn src.api.main:app --reload --port 8000
```

**참고**: `deploy-minimal.sh`는 다음을 자동으로 수행합니다:
- Minikube 최소 사양으로 시작 (Memory 8GB, CPU 4코어, Disk 30GB)
- 의존성 서비스 배포 (최소 리소스)
- Port-forward 자동 설정 (선택사항)

### 🚀 빠른 시작 - 전체 기능 (프로덕션 또는 고급 개발)

**전체 기능을 사용하려면 `deploy-all.sh`를 사용하세요!**

#### 로컬 개발 (Minikube)

```bash
# 1. Minikube 시작
minikube start

# 2. 전체 초기 세팅 및 배포 (자동으로 minikube 감지)
./deploy-all.sh dev

# 3. 서비스 접근 (port-forward)
kubectl port-forward -n llm-ops-dev svc/postgresql 5432:5432
kubectl port-forward -n llm-ops-dev svc/redis 6379:6379
kubectl port-forward -n llm-ops-dev svc/minio 9000:9000
kubectl port-forward -n llm-ops-dev svc/minio 9001:9001

# 4. Backend .env 설정 (deploy-all.sh 출력에서 확인 가능)
DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops
REDIS_URL=redis://localhost:6379/0
OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
```

#### 프로덕션 (Kubernetes)

```bash
# 1. kubectl context 설정 (프로덕션 클러스터)
kubectl config use-context production-cluster

# 2. 전체 초기 세팅 및 배포 (자동으로 kubernetes 감지)
./deploy-all.sh prod

# 3. Backend .env 설정 (deploy-all.sh 출력에서 확인 가능)
DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.llm-ops-prod.svc.cluster.local:5432/llmops
REDIS_URL=redis://redis.llm-ops-prod.svc.cluster.local:6379/0
OBJECT_STORE_ENDPOINT=http://minio.llm-ops-prod.svc.cluster.local:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
```

### 🔧 단계별 배포 (고급 사용자용)

특정 단계만 수행하거나 문제 해결 시 사용:

```bash
# 1. 네임스페이스 생성
./setup-namespaces.sh dev stg prod

# 2. KServe 설치
./setup-kserve.sh

# 3. 의존성 배포
cd ../k8s/dependencies
DEPENDENCIES_NAMESPACE=llm-ops-dev ./deploy.sh

# 4. Object Storage 설정 및 버킷 생성
cd ../../scripts
./setup-object-store.sh llm-ops-dev setup-all
```

## 필수 사전 요구사항

### 공통 요구사항

1. **kubectl 설치**
   ```bash
   kubectl version --client
   ```

2. **Kubernetes 클러스터 접근**
   ```bash
   kubectl cluster-info
   ```

3. **MinIO Client (mc) 설치** (버킷 생성용, 선택사항)
   ```bash
   # macOS
   brew install minio/stable/mc
   
   # Linux
   wget https://dl.min.io/client/mc/release/linux-amd64/mc
   chmod +x mc
   sudo mv mc /usr/local/bin/
   ```

### 로컬 개발 (Minikube)

1. **Minikube 설치 및 시작**
   ```bash
   # macOS
   brew install minikube
   
   # Linux
   curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
   sudo install minikube-linux-amd64 /usr/local/bin/minikube
   
   # 시작
   minikube start
   ```

2. **Minikube 드라이버 설정** (선택사항)
   ```bash
   # Docker 사용
   minikube start --driver=docker
   
   # 또는 VirtualBox 사용
   minikube start --driver=virtualbox
   ```

### 프로덕션 (Kubernetes)

1. **클러스터 접근 설정**
   ```bash
   # GKE
   gcloud container clusters get-credentials CLUSTER_NAME --zone ZONE
   
   # EKS
   aws eks update-kubeconfig --name CLUSTER_NAME --region REGION
   
   # AKS
   az aks get-credentials --resource-group RESOURCE_GROUP --name CLUSTER_NAME
   ```

2. **클러스터 권한 확인**
   ```bash
   kubectl auth can-i create namespaces
   kubectl auth can-i create deployments
   ```

## 문제 해결

### KServe 설치 실패

#### cert-manager 관련 에러
KServe 설치 시 다음과 같은 에러가 발생할 수 있습니다:
```
resource mapping not found for name: "serving-cert" namespace: "kserve" 
from "https://github.com/kserve/kserve/releases/download/v0.11.0/kserve.yaml": 
no matches for kind "Certificate" in version "cert-manager.io/v1"
```

**해결 방법:**
- 이 에러는 **무시해도 됩니다**. cert-manager는 선택적이고, KServe의 핵심 기능은 cert-manager 없이도 작동합니다.
- cert-manager를 설치하려면:
  ```bash
  kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml
  ```

#### 일반적인 KServe 문제
```bash
# KServe 상태 확인 및 진단
./setup-kserve.sh kserve check

# Certificate 문제 해결
./setup-kserve.sh kserve fix-cert

# 재설치
./setup-kserve.sh kserve reinstall

# 또는 수동으로 확인
kubectl get pods -n kserve
kubectl logs -n kserve -l control-plane=kserve-controller-manager
kubectl get crd | grep kserve
```

### 네임스페이스가 생성되지 않음
```bash
# 권한 확인
kubectl auth can-i create namespaces

# 수동 생성
kubectl create namespace llm-ops-dev
```

### MinIO 버킷 생성 실패
```bash
# 버킷 생성 스크립트 직접 실행
./setup-object-store.sh llm-ops-dev create-bucket

# 또는 상태 확인
./setup-object-store.sh llm-ops-dev check

# 또는 MinIO Console 사용 (권장)
kubectl port-forward -n llm-ops-dev svc/minio 9001:9001
# 브라우저에서 http://localhost:9001 열기
# 로그인: llmops / llmops-secret
# 버킷 생성: "Create Bucket" 버튼 클릭

# 또는 mc client 사용
kubectl port-forward -n llm-ops-dev svc/minio 9000:9000
# 다른 터미널에서:
mc alias set minio http://localhost:9000 llmops llmops-secret
mc mb minio/models
```

### KServe Webhook 연결 실패
```bash
# 에러: "failed calling webhook" 또는 "connection refused"
# 원인: KServe가 Knative Serving/Istio에 의존하는데 설치되지 않음

# 빠른 해결: Raw Kubernetes Deployment 사용
# backend/.env 파일에 추가:
USE_KSERVE=false

# 또는 backend/src/core/settings.py에서 기본값 변경:
# use_kserve: bool = False

# 자세한 해결 방법은 README-KSERVE-ISSUES.md 참조
```

### Object Storage Secret 생성 실패
```bash
# 상태 확인
./setup-object-store.sh llm-ops-dev check

# Secret/ConfigMap 재생성
./setup-object-store.sh llm-ops-dev setup

# 또는 전체 재설정
./setup-object-store.sh llm-ops-dev setup-all

# 수동 생성
kubectl create secret generic llm-ops-object-store-credentials \
  --from-literal=access-key-id=llmops \
  --from-literal=secret-access-key=llmops-secret \
  -n llm-ops-dev
```

## 참고 자료

- [KServe 공식 문서](https://kserve.github.io/website/)
- [Kubernetes 네임스페이스](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
- [MinIO 문서](https://min.io/docs/)

