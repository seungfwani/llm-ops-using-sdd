# 의존성 서비스 연결 가이드

## 연결 문제 진단

의존성 서비스 연결이 안 되는 경우, 다음을 확인하세요:

### 1. 서비스 상태 확인

```bash
# Pod 상태 확인
kubectl get pods -n llm-ops-dev

# 서비스 확인
kubectl get svc -n llm-ops-dev

# 연결 테스트
./test-connections.sh dev
```

### 2. 연결 시나리오별 해결 방법

#### 시나리오 A: 백엔드를 로컬에서 실행하는 경우

**문제**: 로컬에서 실행 중인 백엔드는 클러스터 내부 DNS(`postgresql.llm-ops-dev.svc.cluster.local`)에 접근할 수 없습니다.

**해결 방법**: Port-forward 사용

```bash
# 방법 1: 자동 스크립트 사용 (권장)
./port-forward-all.sh dev

# 방법 2: 수동으로 각각 실행
kubectl port-forward -n llm-ops-dev svc/postgresql 5432:5432 &
kubectl port-forward -n llm-ops-dev svc/redis 6379:6379 &
kubectl port-forward -n llm-ops-dev svc/minio 9000:9000 &
kubectl port-forward -n llm-ops-dev svc/minio 9001:9001 &
```

**Backend .env 설정**:
```bash
DATABASE_URL=postgresql+psycopg://llmops:password@localhost:5432/llmops
REDIS_URL=redis://localhost:6379/0
OBJECT_STORE_ENDPOINT=http://localhost:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false
```

#### 시나리오 B: 백엔드를 클러스터 내부에서 실행하는 경우

**문제**: 환경 변수가 `localhost`로 설정되어 있거나 잘못된 네임스페이스를 가리키고 있습니다.

**해결 방법**: 환경 변수를 클러스터 내부 DNS로 설정

**Backend .env 또는 환경 변수**:
```bash
# dev 환경 예시
DATABASE_URL=postgresql+psycopg://llmops:password@postgresql.llm-ops-dev.svc.cluster.local:5432/llmops
REDIS_URL=redis://redis.llm-ops-dev.svc.cluster.local:6379/0
OBJECT_STORE_ENDPOINT=http://minio.llm-ops-dev.svc.cluster.local:9000
OBJECT_STORE_ACCESS_KEY=llmops
OBJECT_STORE_SECRET_KEY=llmops-secret
OBJECT_STORE_SECURE=false
```

### 3. 연결 테스트

#### 로컬에서 테스트 (port-forward 후)

```bash
# PostgreSQL
psql postgresql+psycopg://llmops:password@localhost:5432/llmops -c "SELECT version();"

# Redis
redis-cli -h localhost -p 6379 ping

# MinIO (mc 사용)
mc alias set minio http://localhost:9000 llmops llmops-secret
mc admin info minio
```

#### 클러스터 내부에서 테스트

```bash
# PostgreSQL
kubectl exec -n llm-ops-dev deployment/postgresql -- psql -U llmops -d llmops -c "SELECT version();"

# Redis
kubectl exec -n llm-ops-dev deployment/redis -- redis-cli ping

# MinIO
kubectl exec -n llm-ops-dev deployment/minio -- mc --version
```

### 4. 일반적인 문제 해결

#### 문제: "Connection refused" 또는 "Name or service not known"

**원인**: 
- 로컬에서 실행 중인데 port-forward가 안 되어 있음
- 또는 클러스터 내부에서 실행 중인데 환경 변수가 `localhost`로 설정됨

**해결**:
- 로컬 실행: `./port-forward-all.sh dev` 실행
- 클러스터 내부 실행: 환경 변수를 클러스터 DNS로 변경

#### 문제: "Authentication failed"

**원인**: 잘못된 사용자명/비밀번호

**확인**:
```bash
# Secret 확인
kubectl get secret postgresql-secret -n llm-ops-dev -o yaml
kubectl get secret minio-secret -n llm-ops-dev -o yaml
```

#### 문제: "Network is unreachable"

**원인**: 네임스페이스가 잘못되었거나 서비스가 없음

**확인**:
```bash
# 네임스페이스 확인
kubectl get namespace llm-ops-dev

# 서비스 확인
kubectl get svc -n llm-ops-dev

# Pod 확인
kubectl get pods -n llm-ops-dev
```

### 5. 빠른 진단 체크리스트

- [ ] Pod들이 Running 상태인가? (`kubectl get pods -n llm-ops-dev`)
- [ ] Service들이 생성되어 있는가? (`kubectl get svc -n llm-ops-dev`)
- [ ] 로컬 실행인가? → Port-forward 필요 (`./port-forward-all.sh dev`)
- [ ] 클러스터 내부 실행인가? → 환경 변수가 클러스터 DNS를 가리키는가?
- [ ] 환경 변수가 올바른 네임스페이스를 가리키는가? (`llm-ops-dev`)

### 6. 연결 테스트 스크립트

```bash
# 전체 연결 테스트
./test-connections.sh dev

# Port-forward 시작 (로컬 개발용)
./port-forward-all.sh dev
```

