# 외부 Kubernetes 클러스터 연동 가이드

## 개요

본 노드에서 backend/frontend만 실행하고, 외부 노드의 Kubernetes 클러스터(minikube 포함)와 연동하는 방법을 설명합니다.

## ✅ 연동 가능 여부

**모든 기능이 외부 클러스터와 연동 가능합니다:**

1. ✅ **Kubernetes API 연동**: kubeconfig를 통한 외부 클러스터 접근
2. ✅ **Database (PostgreSQL)**: 외부 접근 가능한 주소로 연결
3. ✅ **Object Storage (MinIO/S3)**: 외부 접근 가능한 주소로 연결
4. ✅ **Redis**: 외부 접근 가능한 주소로 연결
5. ✅ **서빙 엔드포인트**: Kubernetes API를 통한 배포 및 관리
6. ✅ **트레이닝 작업**: Kubernetes API를 통한 작업 관리

## 아키텍처

```
┌─────────────────────────────────┐
│  본 노드 (Backend/Frontend)      │
│                                  │
│  - Backend API                   │
│  - Frontend UI                   │
│  - kubeconfig (외부 클러스터)    │
└──────────────┬──────────────────┘
               │
               │ Kubernetes API
               │ (kubeconfig)
               │
               │ Database/Redis/MinIO
               │ (외부 접근 주소)
               │
┌──────────────▼──────────────────┐
│  외부 노드 (Kubernetes Cluster)  │
│                                  │
│  - PostgreSQL                    │
│  - Redis                         │
│  - MinIO                         │
│  - 서빙 엔드포인트                │
│  - 트레이닝 작업                  │
└─────────────────────────────────┘
```

## 설정 방법

### 1. Kubernetes 클러스터 연결 설정

#### 1.1 외부 클러스터 kubeconfig 준비

외부 노드에서 kubeconfig 파일을 가져옵니다:

```bash
# 외부 노드에서
kubectl config view --flatten > /path/to/external-kubeconfig.yaml

# 또는 특정 컨텍스트만
kubectl config view --flatten --context=minikube > /path/to/external-kubeconfig.yaml
```

#### 1.2 Backend .env 설정

```bash
# backend/.env

# 외부 클러스터 kubeconfig 경로 지정
KUBECONFIG_PATH=/path/to/external-kubeconfig.yaml

# 또는 기본 kubeconfig 사용 (kubectl context 설정 후)
# KUBECONFIG_PATH=  # 비워두면 ~/.kube/config 사용
```

### 2. Database (PostgreSQL) 연결 설정

외부 클러스터의 PostgreSQL에 접근하는 방법:

#### 방법 A: NodePort 또는 LoadBalancer 사용

```bash
# 외부 노드에서 PostgreSQL Service를 NodePort로 변경
kubectl patch svc postgresql -n llm-ops-dev -p '{"spec":{"type":"NodePort","ports":[{"port":5432,"targetPort":5432,"nodePort":30432}]}}'

# 또는 LoadBalancer 사용 (클라우드 환경)
kubectl patch svc postgresql -n llm-ops-dev -p '{"spec":{"type":"LoadBalancer"}}'
```

```bash
# backend/.env
# 외부 노드의 IP 주소 또는 LoadBalancer IP 사용
DATABASE_URL=postgresql+psycopg://llmops:password@<외부노드IP>:30432/llmops
# 또는
DATABASE_URL=postgresql+psycopg://llmops:password@<LoadBalancerIP>:5432/llmops
```

#### 방법 B: Port-forward 사용 (개발 환경)

```bash
# 외부 노드에서 port-forward 실행 (백그라운드)
kubectl port-forward -n llm-ops-dev svc/postgresql 5432:5432 &
```

```bash
# backend/.env
# 외부 노드의 localhost로 접근 (SSH 터널링 또는 동일 노드)
DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops
```

#### 방법 C: Ingress 사용 (프로덕션)

PostgreSQL을 Ingress로 노출 (보안 주의):

```bash
# backend/.env
DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.example.com:5432/llmops
```

### 3. Redis 연결 설정

PostgreSQL과 동일한 방식으로 설정:

```bash
# 외부 노드에서 NodePort 설정
kubectl patch svc redis -n llm-ops-dev -p '{"spec":{"type":"NodePort","ports":[{"port":6379,"targetPort":6379,"nodePort":30679}]}}'
```

```bash
# backend/.env
REDIS_URL=redis://<외부노드IP>:30679/0
```

### 4. Object Storage (MinIO) 연결 설정

```bash
# 외부 노드에서 NodePort 설정
kubectl patch svc minio -n llm-ops-dev -p '{"spec":{"type":"NodePort","ports":[{"port":9000,"targetPort":9000,"nodePort":30900}]}}'
```

```bash
# backend/.env
OBJECT_STORE_ENDPOINT=http://<외부노드IP>:30900
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false
```

### 5. 서빙 엔드포인트 접근 설정

서빙 엔드포인트는 Kubernetes API를 통해 배포되며, 접근은 Ingress를 통해 가능합니다.

#### 5.1 Ingress Controller 확인

외부 클러스터에 Ingress Controller가 설치되어 있는지 확인:

```bash
kubectl get ingressclass
kubectl get pods -n ingress-nginx  # nginx ingress 예시
```

#### 5.2 서빙 엔드포인트 접근

서빙 엔드포인트는 자동으로 Ingress가 생성됩니다:

```bash
# Ingress 확인
kubectl get ingress -n llm-ops-dev

# Ingress 주소 확인
kubectl get ingress <endpoint-name>-ingress -n llm-ops-dev
```

#### 5.3 로컬 개발용 Port-forward (선택사항)

```bash
# backend/.env
# Port-forward를 사용하는 경우
SERVING_LOCAL_BASE_URL=http://localhost:8001
```

### 6. 트레이닝 작업 연동

트레이닝 작업은 Kubernetes API를 통해 자동으로 관리됩니다. 추가 설정이 필요 없습니다.

#### 6.1 트레이닝 API URL 설정 (선택사항)

트레이닝 Pod에서 Backend API로 메트릭을 전송하는 경우:

```bash
# backend/.env
# 외부 노드에서 접근 가능한 Backend API 주소
TRAINING_API_BASE_URL=http://<본노드IP>:8000/llm-ops/v1
```

## 전체 설정 예시

### backend/.env (외부 클러스터 연동)

```bash
# =========================================================================
# Kubernetes Configuration
# =========================================================================
KUBECONFIG_PATH=/path/to/external-kubeconfig.yaml
TRAINING_NAMESPACE=llm-ops-dev

# =========================================================================
# Database Configuration
# =========================================================================
# 방법 1: NodePort 사용
DATABASE_URL=postgresql+psycopg://llmops:password@<외부노드IP>:30432/llmops

# 방법 2: LoadBalancer 사용
# DATABASE_URL=postgresql+psycopg://llmops:password@<LoadBalancerIP>:5432/llmops

# =========================================================================
# Redis Configuration
# =========================================================================
REDIS_URL=redis://<외부노드IP>:30679/0

# =========================================================================
# Object Storage Configuration
# =========================================================================
OBJECT_STORE_ENDPOINT=http://<외부노드IP>:30900
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false
OBJECT_STORE_BUCKET=llm-ops-dev

# =========================================================================
# Serving Configuration
# =========================================================================
USE_GPU=false
USE_KSERVE=false

# =========================================================================
# Training Configuration
# =========================================================================
# 트레이닝 Pod에서 Backend API로 메트릭 전송 (선택사항)
TRAINING_API_BASE_URL=http://<본노드IP>:8000/llm-ops/v1
```

## 네트워크 연결 확인

### 1. Kubernetes API 연결 확인

```bash
# kubeconfig가 올바르게 설정되었는지 확인
kubectl --kubeconfig=/path/to/external-kubeconfig.yaml get nodes

# 또는 환경 변수로 설정
export KUBECONFIG=/path/to/external-kubeconfig.yaml
kubectl get nodes
```

### 2. Database 연결 확인

```bash
# PostgreSQL 연결 테스트
psql "postgresql+psycopg://llmops:password@<외부노드IP>:30432/llmops" -c "SELECT version();"
```

### 3. Redis 연결 확인

```bash
# Redis 연결 테스트
redis-cli -h <외부노드IP> -p 30679 ping
```

### 4. MinIO 연결 확인

```bash
# MinIO 연결 테스트
curl http://<외부노드IP>:30900/minio/health/live
```

## 보안 고려사항

### 1. 네트워크 보안

- **프로덕션 환경**: VPN, Private Network, 또는 Firewall 규칙 사용
- **개발 환경**: SSH 터널링 또는 Port-forward 사용

### 2. 인증 정보 관리

- kubeconfig 파일 권한 설정:
  ```bash
  chmod 600 /path/to/external-kubeconfig.yaml
  ```

- 환경 변수 파일 보호:
  ```bash
  chmod 600 backend/.env
  ```

### 3. TLS/SSL 사용

프로덕션 환경에서는 TLS/SSL을 사용하는 것을 권장합니다:

```bash
# Database
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db?sslmode=require

# Object Storage
OBJECT_STORE_ENDPOINT=https://minio.example.com
OBJECT_STORE_SECURE=true
```

## 문제 해결

### 문제 1: Kubernetes API 연결 실패

**증상**: `Could not initialize Kubernetes client`

**해결**:
1. kubeconfig 파일 경로 확인
2. kubeconfig 파일 권한 확인
3. 외부 클러스터 접근 가능 여부 확인
4. 네트워크 방화벽 규칙 확인

```bash
# 연결 테스트
kubectl --kubeconfig=/path/to/external-kubeconfig.yaml cluster-info
```

### 문제 2: Database 연결 실패

**증상**: `Connection refused` 또는 `Name or service not known`

**해결**:
1. NodePort/LoadBalancer 설정 확인
2. 외부 노드 IP 주소 확인
3. 네트워크 방화벽 규칙 확인
4. Service 상태 확인

```bash
# Service 확인
kubectl get svc postgresql -n llm-ops-dev
```

### 문제 3: 서빙 엔드포인트 접근 불가

**증상**: 서빙 엔드포인트에 접근할 수 없음

**해결**:
1. Ingress Controller 설치 확인
2. Ingress 리소스 확인
3. Ingress 주소 확인

```bash
# Ingress 확인
kubectl get ingress -n llm-ops-dev
kubectl describe ingress <endpoint-name>-ingress -n llm-ops-dev
```

## 참고 자료

- [Kubernetes kubeconfig 문서](https://kubernetes.io/docs/concepts/configuration/organize-cluster-access-kubeconfig/)
- [PostgreSQL 외부 접근 설정](https://www.postgresql.org/docs/current/runtime-config-connection.html)
- [MinIO 외부 접근 설정](https://min.io/docs/minio/kubernetes/kubernetes-deployment.html)

