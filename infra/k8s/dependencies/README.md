# LLM Ops Dependencies

이 디렉토리에는 LLM Ops 플랫폼의 의존성 서비스들이 포함되어 있습니다.
**minikube(로컬 개발)와 프로덕션 Kubernetes 클러스터 모두 지원합니다.**

## 배포된 서비스

- **PostgreSQL**: 데이터베이스
- **Redis**: 캐시 및 메타데이터 저장
- **MinIO**: Object Storage (S3 호환)

## 배포 방법

```bash
cd infra/k8s/dependencies
./deploy.sh
```

또는 직접 kubectl로:

```bash
kubectl apply -k infra/k8s/dependencies
```

## 서비스 연결 정보

### Kubernetes 클러스터 내부에서 접근

애플리케이션이 같은 클러스터에서 실행되는 경우 (환경별 네임스페이스 사용):

- **PostgreSQL**: `postgresql.llm-ops-{env}.svc.cluster.local:5432`
  - 예: `postgresql.llm-ops-dev.svc.cluster.local:5432`
  - Database: `llmops`
  - User: `llmops`
  - Password: `password`

- **Redis**: `redis.llm-ops-{env}.svc.cluster.local:6379`
  - 예: `redis.llm-ops-dev.svc.cluster.local:6379`

- **MinIO API**: `minio.llm-ops-{env}.svc.cluster.local:9000`
  - 예: `minio.llm-ops-dev.svc.cluster.local:9000`
  - Access Key: `llmops`
  - Secret Key: `llmops-secret`

- **MinIO Console**: `minio.llm-ops-{env}.svc.cluster.local:9001`
  - 예: `minio.llm-ops-dev.svc.cluster.local:9001`

### 로컬에서 접근 (Port Forward)

로컬 개발 환경에서 접근하려면 port-forward를 사용하세요 (환경별 네임스페이스 사용):

```bash
# dev 환경 예시
NAMESPACE="llm-ops-dev"

# PostgreSQL
kubectl port-forward -n ${NAMESPACE} svc/postgresql 5432:5432

# Redis
kubectl port-forward -n ${NAMESPACE} svc/redis 6379:6379

# MinIO API
kubectl port-forward -n ${NAMESPACE} svc/minio 9000:9000

# MinIO Console
kubectl port-forward -n ${NAMESPACE} svc/minio 9001:9001
```

포트 포워드 후:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001` (로그인: llmops / llmops-secret)

## 환경 변수 설정

백엔드 애플리케이션에서 사용할 환경 변수:

### 클러스터 내부에서 실행하는 경우 (환경별 네임스페이스)

```bash
# dev 환경 예시
ENV="dev"
DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.llm-ops-${ENV}.svc.cluster.local:5432/llmops
REDIS_URL=redis://redis.llm-ops-${ENV}.svc.cluster.local:6379/0
OBJECT_STORE_ENDPOINT=http://minio.llm-ops-${ENV}.svc.cluster.local:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false
```

### 로컬에서 실행하는 경우 (port-forward 필요)

```bash
# port-forward를 먼저 실행한 후
DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops
REDIS_URL=redis://localhost:6379/0
OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false
```

## 상태 확인

```bash
# 환경별 네임스페이스 사용 (예: dev)
NAMESPACE="llm-ops-dev"

# Pod 상태 확인
kubectl get pods -n ${NAMESPACE}

# 서비스 확인
kubectl get svc -n ${NAMESPACE}

# PVC 확인
kubectl get pvc -n ${NAMESPACE}

# 로그 확인
kubectl logs -n ${NAMESPACE} deployment/postgresql
kubectl logs -n ${NAMESPACE} deployment/redis
kubectl logs -n ${NAMESPACE} deployment/minio
```

## 삭제

```bash
# 환경별 네임스페이스 삭제
kubectl delete namespace llm-ops-dev

# 또는 kustomize로 삭제
kubectl delete -k infra/k8s/dependencies
```

## 주의사항

- 이 설정은 개발 환경용입니다. 프로덕션 환경에서는 보안 강화가 필요합니다.
- 비밀번호는 기본값을 사용하고 있으므로, 프로덕션에서는 반드시 변경하세요.
- MinIO는 초기 버킷이 생성되지 않았으므로, 애플리케이션에서 필요시 생성해야 합니다.

