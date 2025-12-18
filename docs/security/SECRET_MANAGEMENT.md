# Secret 관리 가이드

이 문서는 LLM Ops Platform의 Kubernetes Secret 관리 방법과 보안 모범 사례를 설명합니다.

## 목차

1. [개요](#개요)
2. [Secret 생성 및 관리](#secret-생성-및-관리)
3. [각 Secret 상세](#각-secret-상세)
4. [보안 모범 사례](#보안-모범-사례)
5. [문제 해결](#문제-해결)

---

## 개요

LLM Ops Platform은 Kubernetes Secret을 사용하여 민감한 정보(데이터베이스 비밀번호, 객체 스토리지 인증 정보 등)를 안전하게 관리합니다.

### Secret 관리 원칙

- **일관성**: 모든 Secret은 동일한 네이밍 컨벤션과 구조를 따릅니다
- **보안**: Secret 값은 평문으로 노출되지 않으며, `secretKeyRef`를 통해 환경 변수로 주입됩니다
- **조건부 생성**: 각 Secret은 해당 의존성이 활성화된 경우에만 생성됩니다

---

## Secret 생성 및 관리

### 네이밍 컨벤션

모든 Secret은 다음 네이밍 패턴을 따릅니다:
- `{service-name}-secret`

예시:
- `postgresql-secret`
- `minio-secret`
- `redis-secret` (선택사항)

### Secret 구조

모든 Secret은 다음 구조를 따릅니다:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {service-name}-secret
  labels:
    {{- include "llmops.labels" . | nindent 4 }}
type: Opaque
stringData:
  KEY_NAME: {{ .Values.dependencies.{service}.secret.{key} | quote }}
```

### 생성 조건

각 Secret은 해당 의존성이 활성화된 경우에만 생성됩니다:

```yaml
{{- if .Values.dependencies.{service}.enabled }}
# Secret 생성 코드
{{- end }}
```

---

## 각 Secret 상세

### 1. PostgreSQL Secret

**Secret 이름**: `postgresql-secret`

**생성 위치**: `infra/helm/llm-ops-platform/templates/postgresql.yaml`

**포함 키**:
- `POSTGRES_USER`: 데이터베이스 사용자 이름
- `POSTGRES_PASSWORD`: 데이터베이스 비밀번호
- `POSTGRES_DB`: 데이터베이스 이름

**생성 조건**: `.Values.dependencies.postgresql.enabled == true`

**사용 위치**:

1. **PostgreSQL Deployment** (`postgresql.yaml`)
   ```yaml
   env:
     - name: POSTGRES_USER
       valueFrom:
         secretKeyRef:
           name: postgresql-secret
           key: POSTGRES_USER
     - name: POSTGRES_PASSWORD
       valueFrom:
         secretKeyRef:
           name: postgresql-secret
           key: POSTGRES_PASSWORD
     - name: POSTGRES_DB
       valueFrom:
         secretKeyRef:
           name: postgresql-secret
           key: POSTGRES_DB
   ```

2. **App Deployment** (`deployment.yaml`)
   ```yaml
   env:
     - name: DB_USER
       valueFrom:
         secretKeyRef:
           name: postgresql-secret
           key: POSTGRES_USER
     - name: DB_PASSWORD
       valueFrom:
         secretKeyRef:
           name: postgresql-secret
           key: POSTGRES_PASSWORD
     - name: DB_NAME
       valueFrom:
         secretKeyRef:
           name: postgresql-secret
           key: POSTGRES_DB
     - name: DB_HOST
       value: postgresql
     - name: DB_PORT
       value: "5432"
   ```

**백엔드 처리**: `backend/src/core/settings.py`에서 개별 환경 변수(`DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`)를 읽어 `DATABASE_URL`을 자동으로 조합합니다.

**설정 위치**: `infra/helm/llm-ops-platform/values.yaml`
```yaml
dependencies:
  postgresql:
    enabled: true
    secret:
      user: llmops
      password: password  # 프로덕션에서는 반드시 변경
      db: llmops
```

---

### 2. MinIO Secret

**Secret 이름**: `minio-secret`

**생성 위치**: `infra/helm/llm-ops-platform/templates/minio.yaml`

**포함 키**:
- `MINIO_ROOT_USER`: MinIO 루트 사용자 이름
- `MINIO_ROOT_PASSWORD`: MinIO 루트 비밀번호

**생성 조건**: `.Values.dependencies.minio.enabled == true`

**사용 위치**:

1. **MinIO Deployment** (`minio.yaml`)
   ```yaml
   env:
     - name: MINIO_ROOT_USER
       valueFrom:
         secretKeyRef:
           name: minio-secret
           key: MINIO_ROOT_USER
     - name: MINIO_ROOT_PASSWORD
       valueFrom:
         secretKeyRef:
           name: minio-secret
           key: MINIO_ROOT_PASSWORD
   ```

2. **App Deployment** (`deployment.yaml`)
   ```yaml
   env:
     - name: OBJECT_STORE_ACCESS_KEY
       valueFrom:
         secretKeyRef:
           name: minio-secret
           key: MINIO_ROOT_USER
     - name: OBJECT_STORE_SECRET_KEY
       valueFrom:
         secretKeyRef:
           name: minio-secret
           key: MINIO_ROOT_PASSWORD
   ```

3. **MinIO Bucket Job** (`minio-bucket-job.yaml`)
   ```yaml
   env:
     - name: MINIO_ROOT_USER
       valueFrom:
         secretKeyRef:
           name: minio-secret
           key: MINIO_ROOT_USER
     - name: MINIO_ROOT_PASSWORD
       valueFrom:
         secretKeyRef:
           name: minio-secret
           key: MINIO_ROOT_PASSWORD
   ```

**설정 위치**: `infra/helm/llm-ops-platform/values.yaml`
```yaml
dependencies:
  minio:
    enabled: true
    secret:
      accessKey: llmops
      secretKey: llmops-secret  # 프로덕션에서는 반드시 변경
```

---

### 3. Redis Secret (선택사항)

**Secret 이름**: `redis-secret`

**생성 위치**: `infra/helm/llm-ops-platform/templates/redis.yaml`

**포함 키**:
- `REDIS_PASSWORD`: Redis 비밀번호

**생성 조건**: `.Values.dependencies.redis.enabled == true` AND `.Values.dependencies.redis.secret.enabled == true`

**사용 위치**:

1. **Redis Deployment** (`redis.yaml`)
   ```yaml
   env:
     - name: REDIS_PASSWORD
       valueFrom:
         secretKeyRef:
           name: redis-secret
           key: REDIS_PASSWORD
   command:
     - /bin/sh
     - -c
     - |
       redis-server --appendonly yes --requirepass "$REDIS_PASSWORD"
   ```

2. **App Deployment** (`deployment.yaml`)
   ```yaml
   env:
     - name: REDIS_HOST
       value: redis
     - name: REDIS_PORT
       value: "6379"
     - name: REDIS_DATABASE
       value: "0"
     - name: REDIS_PASSWORD
       valueFrom:
         secretKeyRef:
           name: redis-secret
           key: REDIS_PASSWORD
   ```

**백엔드 처리**: `backend/src/core/settings.py`에서 개별 환경 변수(`REDIS_HOST`, `REDIS_PORT`, `REDIS_DATABASE`, `REDIS_PASSWORD`)를 읽어 `REDIS_URL`을 자동으로 조합합니다.

**설정 위치**: `infra/helm/llm-ops-platform/values.yaml`
```yaml
dependencies:
  redis:
    enabled: true
    secret:
      enabled: false  # Set to true to enable Redis password authentication
      password: ""  # Redis password (required if enabled is true)
```

**사용 시나리오**:
- 개발 환경: `secret.enabled: false` (기본 동작, 인증 없음)
- 프로덕션 환경: `secret.enabled: true` 및 강력한 비밀번호 설정

---

## 보안 모범 사례

### 1. Secret 값 관리

#### ❌ 피해야 할 것

- `values.yaml`에 평문 비밀번호 저장 (개발 환경 제외)
- 환경 변수에 직접 비밀번호 포함
- Secret 값을 로그에 출력

#### ✅ 권장 사항

- 프로덕션 환경에서는 Helm values를 외부에서 주입 (예: `--set` 옵션 또는 별도 values 파일)
- Secret은 `secretKeyRef`를 통해서만 접근
- 비밀번호는 강력하고 고유하게 설정
- 정기적인 비밀번호 로테이션

### 2. 프로덕션 배포 시 Secret 설정

#### 방법 1: Helm values 파일 사용 (권장)

```bash
# secrets-values.yaml (Git에 커밋하지 않음)
dependencies:
  postgresql:
    secret:
      user: production_user
      password: <strong-password>
      db: llmops_prod
  minio:
    secret:
      accessKey: production_access_key
      secretKey: <strong-secret-key>

# 배포
helm install llm-ops-platform ./infra/helm/llm-ops-platform \
  -f secrets-values.yaml
```

#### 방법 2: Helm set 옵션 사용

```bash
helm install llm-ops-platform ./infra/helm/llm-ops-platform \
  --set dependencies.postgresql.secret.password=<password> \
  --set dependencies.minio.secret.secretKey=<secret-key>
```

#### 방법 3: 외부 Secret 관리 도구 사용

- **HashiCorp Vault**: Kubernetes Secret Store CSI Driver와 연동
- **Sealed Secrets**: Git에 암호화된 Secret 저장
- **External Secrets Operator**: 외부 Secret 관리 시스템과 동기화

### 3. Secret 접근 제어

- RBAC을 통해 Secret 접근 권한 제한
- ServiceAccount는 필요한 Secret만 접근 가능하도록 설정
- 네트워크 정책으로 Secret 접근 제한 (선택사항)

### 4. Secret 암호화

Kubernetes Secret은 기본적으로 base64 인코딩만 되어 있습니다. 프로덕션 환경에서는 다음을 고려하세요:

- **etcd 암호화**: Kubernetes etcd 데이터 암호화 활성화
- **Secret 암호화 제공자**: KMS, Vault 등과 연동

---

## 문제 해결

### Secret이 생성되지 않는 경우

1. **의존성 활성화 확인**
   ```bash
   helm get values llm-ops-platform
   ```
   `dependencies.{service}.enabled`가 `true`인지 확인

2. **Secret 존재 확인**
   ```bash
   kubectl get secrets -n <namespace>
   ```

3. **Secret 내용 확인** (디버깅용)
   ```bash
   kubectl get secret postgresql-secret -n <namespace> -o yaml
   ```

### Pod에서 Secret을 읽을 수 없는 경우

1. **Secret 존재 확인**
   ```bash
   kubectl get secret <secret-name> -n <namespace>
   ```

2. **Pod 환경 변수 확인**
   ```bash
   kubectl exec <pod-name> -n <namespace> -- env | grep DB_
   ```

3. **Pod 로그 확인**
   ```bash
   kubectl logs <pod-name> -n <namespace>
   ```

### Secret 값 변경 후 적용

1. **Helm upgrade 실행**
   ```bash
   helm upgrade llm-ops-platform ./infra/helm/llm-ops-platform \
     -f secrets-values.yaml
   ```

2. **Pod 재시작** (Secret 변경은 자동으로 반영되지 않을 수 있음)
   ```bash
   kubectl rollout restart deployment/<deployment-name> -n <namespace>
   ```

### 백엔드에서 DATABASE_URL 조합 오류

1. **환경 변수 확인**
   ```bash
   kubectl exec <pod-name> -n <namespace> -- env | grep -E "DB_|DATABASE_URL"
   ```

2. **백엔드 로그 확인**
   ```bash
   kubectl logs <pod-name> -n <namespace> | grep -i database
   ```

3. **settings.py 확인**: `backend/src/core/settings.py`의 `get_settings()` 함수가 올바르게 DATABASE_URL을 조합하는지 확인

---

## 참고 자료

- [Kubernetes Secrets 공식 문서](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Helm Values 파일 가이드](https://helm.sh/docs/chart_best_practices/values/)
- [Pydantic Settings 문서](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

---

## 변경 이력

- **2024-01-XX**: PostgreSQL Secret 사용 개선 (secretKeyRef 사용)
- **2024-01-XX**: Redis Secret 옵션 추가 (선택사항)
- **2024-01-XX**: Secret 관리 문서 초기 작성

