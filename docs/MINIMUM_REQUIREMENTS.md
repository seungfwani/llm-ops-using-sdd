# LLM Ops Platform 최소 사양 (Minimum Requirements)

**작성일**: 2025-01-27  
**대상**: 개발 및 테스트 환경

---

## 개요

이 문서는 LLM Ops Platform을 **개발 및 테스트** 목적으로 실행하기 위한 최소 하드웨어 및 소프트웨어 요구사항을 정의합니다.

**참고**: 프로덕션 환경의 경우 더 높은 사양이 필요하며, 별도의 프로덕션 배포 가이드를 참조하세요.

---

## 1. 하드웨어 최소 사양

### 1.1 개발 환경 (Development)

#### 최소 사양 (Minimum)
- **CPU**: 4코어 이상 (Apple Silicon M1/M2 또는 Intel i5 이상)
- **메모리**: 16GB RAM
- **디스크**: 50GB 이상 여유 공간
- **GPU**: 선택사항 (CPU-only 모드 지원)

#### 권장 사양 (Recommended)
- **CPU**: 8코어 이상 (Apple Silicon M2 Pro/Max 또는 Intel i7 이상)
- **메모리**: 32GB RAM
- **디스크**: 100GB 이상 여유 공간 (모델 저장 공간 포함)
- **GPU**: 선택사항 (GPU 모드 테스트 시 필요)

### 1.2 리소스 할당 가이드

#### Minikube 리소스 할당

**최소 구성 (CPU-only 모드)**:
```bash
minikube start \
  --memory=8192 \
  --cpus=4 \
  --disk-size=30g \
  --driver=docker
```

**권장 구성 (GPU 테스트 포함)**:
```bash
minikube start \
  --memory=16384 \
  --cpus=6 \
  --disk-size=50g \
  --driver=docker \
  --gpus=1  # GPU 지원 시
```

**Mac M2 Pro 기준 권장 설정**:
```bash
# 전체 시스템 리소스 고려
# - 시스템: 4GB
# - Minikube: 12GB
# - 개발 도구: 4GB
# - 여유 공간: 4GB
# 총 24GB 이상 권장

minikube start \
  --memory=12288 \
  --cpus=6 \
  --disk-size=50g \
  --driver=docker
```

### 1.3 디스크 공간 세부사항

| 용도 | 예상 공간 |
|------|----------|
| Minikube VM | 20GB |
| Docker 이미지 | 10GB |
| 모델 파일 (소형 모델) | 5-10GB |
| 데이터셋 | 5GB |
| 로그 및 임시 파일 | 5GB |
| **총합 (최소)** | **50GB** |
| **총합 (권장)** | **100GB** |

---

## 2. 소프트웨어 요구사항

### 2.1 운영체제

#### 지원 OS
- **macOS**: 12.0 (Monterey) 이상 (Apple Silicon M1/M2 권장)
- **Linux**: Ubuntu 20.04 LTS 이상
- **Windows**: WSL2 (Ubuntu 20.04 이상)

### 2.2 필수 소프트웨어

#### 컨테이너 및 Kubernetes
- **Docker Desktop**: 20.10 이상
  - 또는 **Docker Engine**: 20.10 이상
- **Minikube**: 1.30.0 이상
- **kubectl**: 1.28.0 이상

#### 개발 도구
- **Python**: 3.11 이상
- **Poetry**: 1.6.0 이상 (Python 패키지 관리)
- **Node.js**: 18.0 이상
- **npm**: 9.0 이상

#### 선택적 도구
- **MinIO Client (mc)**: 버킷 관리용
- **PostgreSQL Client**: 데이터베이스 접근용
- **Redis CLI**: Redis 접근용

### 2.3 설치 가이드

#### macOS (Homebrew)
```bash
# Docker Desktop
brew install --cask docker

# Minikube
brew install minikube

# kubectl
brew install kubectl

# Python & Poetry
brew install python@3.11
pip install poetry

# Node.js
brew install node@18

# MinIO Client (선택사항)
brew install minio/stable/mc
```

#### Linux (Ubuntu/Debian)
```bash
# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Python & Poetry
sudo apt update
sudo apt install python3.11 python3-pip
pip3 install poetry

# Node.js
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

---

## 3. Minikube 설정 가이드

### 3.1 빠른 시작 (최소 사양) ⭐ **권장**

**최소 사양으로 개발 환경 구성을 위한 빠른 시작 가이드:**

#### 방법 1: 자동 배포 스크립트 사용 (권장)

```bash
# 1. 최소 사양으로 자동 배포 (Minikube 자동 시작 포함)
cd infra/scripts
./deploy-minimal.sh dev

# 2. 리소스 사용량 확인
./check-resources.sh dev

# 3. Backend .env 설정 (이미 최소 사양으로 설정됨)
cd ../../backend
cp env.example .env

# 4. 데이터베이스 마이그레이션
poetry install
poetry run alembic upgrade head

# 5. Backend 실행
poetry run uvicorn src.api.main:app --reload --port 8000

# 6. Frontend 실행 (다른 터미널)
cd ../frontend
npm install
npm run dev
```

**참고**: `deploy-minimal.sh`는 다음을 자동으로 수행합니다:
- Minikube 최소 사양으로 시작 (Memory 8GB, CPU 4코어, Disk 30GB)
- 의존성 서비스 배포 (최소 리소스)
- Port-forward 자동 설정 (선택사항)
- 환경 설정 안내

#### 방법 2: 수동 배포

```bash
# 1. Minikube 시작 (최소 사양 - CPU-only 모드)
minikube start \
  --memory=8192 \
  --cpus=4 \
  --disk-size=30g \
  --driver=docker

# 2. 상태 확인
minikube status
kubectl cluster-info

# 3. 의존성 서비스 배포
cd infra/scripts
./deploy-all.sh dev

# 4. Port-forward 설정 (로컬 개발용)
./port-forward-all.sh dev

# 5. Backend .env 설정
cd ../../backend
cp env.example .env
# .env 파일은 이미 최소 사양(CPU-only)으로 설정되어 있습니다

# 6. Frontend 실행
cd ../frontend
npm install
npm run dev

# 7. Backend 실행
cd ../backend
poetry install
poetry run alembic upgrade head
poetry run uvicorn src.api.main:app --reload --port 8000
```

**참고**: 
- 기본 설정은 **CPU-only 모드**로 구성되어 있습니다 (`USE_GPU=false`, `USE_KSERVE=false`)
- Serving 리소스는 최소 사양으로 설정되어 있습니다 (CPU: 500m-1, Memory: 512Mi-1Gi)
- 의존성 서비스(PostgreSQL, Redis, MinIO)도 최소 리소스로 설정되어 있습니다

### 3.2 초기 설정 (상세)

```bash
# Minikube 시작 (최소 사양)
minikube start \
  --memory=8192 \
  --cpus=4 \
  --disk-size=30g \
  --driver=docker

# Minikube 시작 (권장 사양)
minikube start \
  --memory=12288 \
  --cpus=6 \
  --disk-size=50g \
  --driver=docker

# 상태 확인
minikube status
kubectl cluster-info
```

### 3.2 리소스 모니터링

```bash
# Minikube 리소스 사용량 확인
minikube ssh -- df -h
minikube ssh -- free -h

# Kubernetes 리소스 사용량 확인
kubectl top nodes
kubectl top pods --all-namespaces
```

### 3.3 리소스 부족 시 대응

#### 메모리 부족
```bash
# Minikube 중지 후 메모리 증가
minikube stop
minikube start --memory=16384 --cpus=6
```

#### 디스크 공간 부족
```bash
# 불필요한 이미지 정리
minikube ssh -- docker system prune -a

# Minikube 디스크 확장 (재시작 필요)
minikube stop
minikube start --disk-size=100g
```

---

## 4. 환경별 구성

### 4.1 CPU-only 모드 (최소 리소스)

GPU 없이 개발 및 테스트를 수행하는 경우:

```bash
# Minikube 시작 (CPU-only)
minikube start \
  --memory=8192 \
  --cpus=4 \
  --disk-size=30g \
  --driver=docker

# Backend .env 설정
USE_GPU=false
USE_KSERVE=false
SERVING_RUNTIME_IMAGE=python:3.11-slim

# 리소스 제한 설정
SERVING_CPU_ONLY_CPU_REQUEST=500m
SERVING_CPU_ONLY_CPU_LIMIT=1
SERVING_CPU_ONLY_MEMORY_REQUEST=512Mi
SERVING_CPU_ONLY_MEMORY_LIMIT=1Gi
```

**제한사항**:
- 실제 모델 학습은 불가능 (CPU-only)
- 소형 모델 Serving만 가능
- 성능 테스트 제한적

### 4.2 GPU 모드 (권장 사양)

GPU를 사용한 개발 및 테스트:

```bash
# Minikube 시작 (GPU 지원)
minikube start \
  --memory=16384 \
  --cpus=6 \
  --disk-size=50g \
  --driver=docker \
  --gpus=1

# Backend .env 설정
USE_GPU=true
USE_KSERVE=true
SERVING_RUNTIME_IMAGE=ghcr.io/vllm/vllm:latest

# 리소스 설정
SERVING_CPU_REQUEST=2
SERVING_CPU_LIMIT=4
SERVING_MEMORY_REQUEST=4Gi
SERVING_MEMORY_LIMIT=8Gi
```

**참고**: Minikube에서 GPU 지원은 제한적입니다. 실제 GPU 테스트는 프로덕션 클러스터 또는 로컬 Kubernetes 클러스터를 권장합니다.

---

## 5. 의존성 서비스 리소스 요구사항

### 5.1 필수 서비스

플랫폼 실행을 위한 최소 리소스:

| 서비스 | CPU 요청 | 메모리 요청 | CPU 제한 | 메모리 제한 |
|--------|---------|------------|---------|------------|
| PostgreSQL | 250m | 256Mi | 500m | 512Mi |
| Redis | 100m | 128Mi | 200m | 256Mi |
| MinIO | 250m | 512Mi | 500m | 1Gi |
| **합계 (최소)** | **600m** | **896Mi** | **1.2** | **1.75Gi** |

### 5.2 추가 서비스 (선택사항)

| 서비스 | CPU 요청 | 메모리 요청 | CPU 제한 | 메모리 제한 |
|--------|---------|------------|---------|------------|
| MLflow | 200m | 256Mi | 500m | 512Mi |
| KServe Controller | 100m | 128Mi | 200m | 256Mi |
| Argo Workflows | 100m | 128Mi | 200m | 256Mi |

### 5.3 총 리소스 요구사항

**최소 구성 (CPU-only)**:
- CPU: 1 core (600m 요청 + 여유 공간)
- 메모리: 2GB (896Mi 요청 + 여유 공간)
- 디스크: 30GB

**권장 구성 (GPU 포함)**:
- CPU: 2 cores (1.2 요청 + 여유 공간)
- 메모리: 4GB (1.75Gi 요청 + 여유 공간)
- 디스크: 50GB
- GPU: 1개 (선택사항)

---

## 6. 성능 최적화 팁

### 6.1 리소스 효율적 사용

```bash
# 불필요한 Pod 정리
kubectl delete pods --field-selector=status.phase=Succeeded --all-namespaces

# 이미지 캐시 정리
minikube ssh -- docker system prune -a --volumes

# 로그 파일 정리
kubectl logs --tail=100 <pod-name> > /dev/null
```

### 6.2 개발 시 리소스 절약

1. **CPU-only 모드 사용**: GPU가 필요 없는 기능 테스트 시
2. **단일 Replica**: Serving Pod를 1개만 실행
3. **리소스 제한**: 개발 환경에서는 낮은 리소스 제한 사용
4. **선택적 서비스**: 필요한 서비스만 배포

### 6.3 모니터링

```bash
# 리소스 사용량 모니터링
watch kubectl top nodes
watch kubectl top pods --all-namespaces

# 디스크 사용량 확인
minikube ssh -- df -h
```

---

## 7. 문제 해결

### 7.1 메모리 부족 (OOM)

**증상**:
- Pod가 `OOMKilled` 상태
- Minikube가 느려짐

**해결**:
```bash
# Minikube 메모리 증가
minikube stop
minikube start --memory=16384

# Pod 리소스 제한 감소
# backend/.env에서 메모리 제한 값 감소
```

### 7.2 디스크 공간 부족

**증상**:
- Pod가 `Pending` 상태
- 이미지 Pull 실패

**해결**:
```bash
# 불필요한 이미지 정리
minikube ssh -- docker system prune -a

# Minikube 디스크 확장
minikube stop
minikube start --disk-size=100g
```

### 7.3 CPU 부족

**증상**:
- Pod 스케줄링 지연
- 응답 속도 저하

**해결**:
```bash
# Minikube CPU 증가
minikube stop
minikube start --cpus=6

# 불필요한 Pod 정리
kubectl delete pods --field-selector=status.phase=Succeeded --all-namespaces
```

---

## 8. 체크리스트

### 8.1 사전 확인

- [ ] 하드웨어 사양 확인 (CPU, 메모리, 디스크)
- [ ] Docker Desktop 설치 및 실행
- [ ] Minikube 설치 확인
- [ ] kubectl 설치 확인
- [ ] Python 3.11+ 설치 확인
- [ ] Node.js 18+ 설치 확인

### 8.2 초기 설정

- [ ] Minikube 시작 (적절한 리소스 할당)
- [ ] Kubernetes 클러스터 접근 확인
- [ ] 의존성 서비스 배포 (PostgreSQL, Redis, MinIO)
- [ ] Backend .env 설정
- [ ] Frontend .env 설정

### 8.3 기능 테스트

- [ ] Backend API 접근 확인
- [ ] Frontend UI 접근 확인
- [ ] 데이터베이스 연결 확인
- [ ] Object Storage 연결 확인
- [ ] 모델 등록 테스트
- [ ] Serving 배포 테스트 (CPU-only)

---

## 9. 배포 스크립트

### 9.1 최소 사양 배포 스크립트

최소 사양으로 배포하는 전용 스크립트가 제공됩니다:

```bash
# 최소 사양으로 배포
cd infra/scripts
./deploy-minimal.sh dev
```

**주요 기능:**
- Minikube 최소 사양으로 자동 시작
- 의존성 서비스 최소 리소스로 배포
- 리소스 사용량 자동 확인
- Port-forward 자동 설정 (선택사항)
- 환경 설정 안내

**자세한 내용**: [배포 스크립트 README](../infra/scripts/README.md)

### 9.2 리소스 확인 스크립트

리소스 사용량을 확인하는 스크립트:

```bash
# 리소스 사용량 확인
cd infra/scripts
./check-resources.sh dev
```

**주요 기능:**
- Pod 상태 확인
- Resource requests/limits 확인
- 실제 리소스 사용량 확인 (metrics-server 필요)
- 총 리소스 요구사항 계산

---

## 10. 참고 자료

- [Minikube 공식 문서](https://minikube.sigs.k8s.io/docs/)
- [Kubernetes 리소스 관리](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Docker Desktop 리소스 설정](https://docs.docker.com/desktop/settings/mac/#resources)
- [프로젝트 README](../README.md)
- [환경 설정 가이드](./ENV_SETUP.md)
- [배포 스크립트 README](../infra/scripts/README.md)

---

## 11. 요약

### 최소 사양 (CPU-only 모드) - 기본 설정
- **CPU**: 4코어
- **메모리**: 16GB (시스템) + 8GB (Minikube)
- **디스크**: 50GB
- **GPU**: 불필요
- **기본 구성**: CPU-only 모드 (`USE_GPU=false`, `USE_KSERVE=false`)

### 권장 사양 (GPU 모드)
- **CPU**: 8코어
- **메모리**: 32GB (시스템) + 16GB (Minikube)
- **디스크**: 100GB
- **GPU**: 1개 (선택사항)

### Mac M2 Pro 기준 권장 설정
```bash
minikube start \
  --memory=12288 \
  --cpus=6 \
  --disk-size=50g \
  --driver=docker
```

### 최소 사양 구성 변경 사항

플랫폼이 **최소 사양으로 개발 환경을 구성할 수 있도록** 다음이 기본값으로 설정되었습니다:

1. **Backend 설정** (`backend/env.example`, `backend/src/core/settings.py`):
   - `USE_GPU=false` (CPU-only 모드)
   - `USE_KSERVE=false` (Raw Kubernetes Deployment 사용)
   - Serving 리소스: CPU 500m-1, Memory 512Mi-1Gi

2. **의존성 서비스 리소스 최소화**:
   - PostgreSQL: CPU 100m-250m, Memory 128Mi-256Mi, Storage 5Gi
   - Redis: CPU 100m-200m, Memory 128Mi-256Mi (변경 없음)
   - MinIO: CPU 100m-250m, Memory 256Mi-512Mi, Storage 10Gi

3. **총 리소스 요구사항 (최소)**:
   - CPU: 약 600m 요청 (0.6 core)
   - 메모리: 약 1GB 요청
   - 디스크: 약 15GB (PostgreSQL 5Gi + MinIO 10Gi)

이 설정으로 개발 및 테스트가 가능하며, 필요에 따라 리소스를 조정할 수 있습니다.

