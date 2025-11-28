# LLM Ops Dependencies on Minikube

이 디렉토리에는 minikube에서 실행할 수 있는 LLM Ops 플랫폼의 의존성 서비스들이 포함되어 있습니다.

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

애플리케이션이 같은 클러스터에서 실행되는 경우:

- **PostgreSQL**: `postgresql.llm-ops.svc.cluster.local:5432`
  - Database: `llmops`
  - User: `llmops`
  - Password: `password`

- **Redis**: `redis.llm-ops.svc.cluster.local:6379`

- **MinIO API**: `minio.llm-ops.svc.cluster.local:9000`
  - Access Key: `llmops`
  - Secret Key: `llmops-secret`

- **MinIO Console**: `minio.llm-ops.svc.cluster.local:9001`

### 로컬에서 접근 (Port Forward)

로컬 개발 환경에서 접근하려면 port-forward를 사용하세요:

```bash
# PostgreSQL
kubectl port-forward -n llm-ops svc/postgresql 5432:5432

# Redis
kubectl port-forward -n llm-ops svc/redis 6379:6379

# MinIO API
kubectl port-forward -n llm-ops svc/minio 9000:9000

# MinIO Console
kubectl port-forward -n llm-ops svc/minio 9001:9001
```

포트 포워드 후:
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001` (로그인: llmops / llmops-secret)

## 환경 변수 설정

백엔드 애플리케이션에서 사용할 환경 변수:

```bash
# .env 파일 또는 환경 변수
DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.llm-ops.svc.cluster.local:5432/llmops
REDIS_URL=redis://redis.llm-ops.svc.cluster.local:6379/0
OBJECT_STORE_ENDPOINT=http://minio.llm-ops.svc.cluster.local:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false
```

로컬에서 port-forward를 사용하는 경우:

```bash
DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops
REDIS_URL=redis://localhost:6379/0
OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false
```

## 상태 확인

```bash
# Pod 상태 확인
kubectl get pods -n llm-ops

# 서비스 확인
kubectl get svc -n llm-ops

# PVC 확인
kubectl get pvc -n llm-ops

# 로그 확인
kubectl logs -n llm-ops deployment/postgresql
kubectl logs -n llm-ops deployment/redis
kubectl logs -n llm-ops deployment/minio
```

## 삭제

```bash
kubectl delete -k infra/k8s/dependencies
# 또는
kubectl delete namespace llm-ops
```

## 주의사항

- 이 설정은 개발 환경용입니다. 프로덕션 환경에서는 보안 강화가 필요합니다.
- 비밀번호는 기본값을 사용하고 있으므로, 프로덕션에서는 반드시 변경하세요.
- MinIO는 초기 버킷이 생성되지 않았으므로, 애플리케이션에서 필요시 생성해야 합니다.

