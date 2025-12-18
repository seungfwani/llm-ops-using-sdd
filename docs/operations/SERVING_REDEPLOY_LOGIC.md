# Serving Endpoint 재배포 로직 분석 문서

## 개요

이 문서는 기존 서빙 엔드포인트의 재배포(`redeploy_endpoint`) 로직을 분석하고, 잠재적인 문제점을 파악하기 위해 작성되었습니다.

## 재배포 흐름

### 1. 엔드포인트 조회 및 검증

**위치**: `backend/src/serving/serving_service.py:327-358`

**흐름**:
1. 엔드포인트 ID로 엔드포인트 조회
2. 모델 엔트리 조회 및 검증
3. 모델 상태가 "approved"인지 확인
4. External 모델인 경우 즉시 반환 (Kubernetes 배포 불필요)

**문제점**:
- 엔드포인트가 삭제 중인 상태인지 확인하지 않음
- 동시 재배포 요청에 대한 락(lock) 메커니즘이 없음
- DB 트랜잭션 격리 수준에 따라 동시성 문제 발생 가능

### 2. 기존 Kubernetes 리소스 삭제

**위치**: `backend/src/serving/serving_service.py:367-472`

**흐름**:
1. `deployer.delete_endpoint()` 호출
2. 삭제 성공 여부 확인 (`delete_success`)
3. 리소스가 완전히 삭제될 때까지 대기 (최대 60초)
   - KServe: InferenceService 존재 여부 확인
   - 일반 Deployment: Deployment 존재 여부 확인
4. 타임아웃 시 에러 발생

**문제점**:
- `delete_endpoint()`가 `False`를 반환해도 경고만 하고 계속 진행
- 삭제 대기 로직이 `deployer.delete_endpoint()` 내부 로직과 중복됨
- 삭제 실패 시 예외 처리 후 다시 확인하는 로직이 복잡함
- 삭제 완료 확인이 단순히 리소스 존재 여부만 확인 (파드, HPA 등은 확인 안 함)

### 3. DeploymentSpec 결정 로직

**위치**: `backend/src/serving/serving_service.py:481-530`

**우선순위**:
1. 새로 제공된 `deployment_spec` 파라미터
2. 엔드포인트에 저장된 기존 `deployment_spec`
3. 모델 메타데이터에서 재구성

**재구성 로직** (3번째 경우):
```python
# job_type 기반으로 serve_target 결정
if job_type == "RAG_TUNING":
    serve_target = "RAG"
else:
    serve_target = "GENERATION"

# use_gpu 결정: 파라미터 -> 엔드포인트 -> 설정
effective_use_gpu = use_gpu or endpoint.use_gpu or settings.use_gpu

# DeploymentSpec 재구성
effective_deployment_spec = DeploymentSpec(
    model_ref=f"{model_entry.name}-{model_entry.version}",
    model_family=model_family,
    job_type=job_type,
    serve_target=serve_target,
    resources={"gpus": gpus, "gpu_memory_gb": 80 if effective_use_gpu else None},
    runtime={
        "max_concurrent_requests": 256,
        "max_input_tokens": model_entry.model_metadata.get("max_position_embeddings", 4096),
        "max_output_tokens": 1024,
    },
    use_gpu=effective_use_gpu,
)
```

**문제점**:
- 재구성 시 하드코딩된 값들 (gpu_memory_gb=80, max_concurrent_requests=256 등)
- 기존 엔드포인트의 실제 설정값을 반영하지 않음
- `job_type`이 없으면 재구성 실패 (하지만 에러는 발생하지 않음)
- `deployment_spec` 파싱 실패 시 경고만 하고 계속 진행

### 4. 리소스 설정 결정

**위치**: `backend/src/serving/serving_service.py:532-592`

#### 4.1 DeploymentSpec이 있는 경우

**흐름**:
1. DeploymentSpec 검증
2. `image_config.get_serve_image_with_fallback()`로 런타임 이미지 결정
3. `effective_use_gpu = effective_deployment_spec.use_gpu`

**문제점**:
- DeploymentSpec의 `use_gpu`가 `None`일 수 있음
- 이미지 결정 실패 시 에러 처리 없음

#### 4.2 DeploymentSpec이 없는 경우 (Legacy)

**우선순위**:
- `serving_runtime_image`: 파라미터 -> 엔드포인트 -> 설정
- `use_gpu`: 파라미터 -> 엔드포인트 -> 설정
- `cpu_request/limit`: 파라미터 -> 엔드포인트 -> None (deployer에서 기본값 사용)
- `memory_request/limit`: 파라미터 -> 엔드포인트 -> None (deployer에서 기본값 사용)
- `autoscale_policy`: 파라미터 -> 엔드포인트 -> None

**문제점**:
- `cpu_request` 등이 `None`일 때 deployer의 기본값 사용 (예측 불가능)
- Legacy 로직과 DeploymentSpec 로직이 분리되어 있어 일관성 부족

### 5. 엔드포인트 DB 업데이트

**위치**: `backend/src/serving/serving_service.py:585-596`

**흐름**:
1. 결정된 설정값들을 엔드포인트 엔티티에 저장
2. `deployment_spec`도 저장 (있는 경우)

**문제점**:
- **중요**: Kubernetes 배포 전에 DB를 업데이트함
- 배포 실패 시 DB는 이미 업데이트된 상태 (롤백 필요)
- 트랜잭션 원자성이 없음

### 6. Kubernetes 재배포

**위치**: `backend/src/serving/serving_service.py:598-615`

**흐름**:
1. `deployer.deploy_endpoint()` 호출
2. 반환된 Kubernetes UID 저장
3. 엔드포인트 상태를 "deploying"으로 업데이트

**문제점**:
- 배포 실패 시 예외가 발생하지만, DB는 이미 업데이트됨
- 배포 중인 상태에서 다시 재배포 요청이 오면 충돌 가능
- 배포 실패 시 `endpoint.status = "failed"`로 설정하지만, 설정값은 이미 변경됨

### 7. 상태 동기화

**위치**: `backend/src/serving/serving_service.py:623-637`

**흐름**:
1. Kubernetes에서 실제 상태 조회 (non-blocking)
2. 상태가 있으면 DB 업데이트
3. 조회 실패 시 경고만 하고 "deploying" 상태 유지

**문제점**:
- 배포 직후에는 파드가 아직 시작 중일 수 있어 상태 조회가 실패할 수 있음
- 상태 동기화 실패가 무시됨

## 잠재적 문제점

### 1. 경쟁 조건 (Race Condition)

**시나리오**:
1. 사용자 A가 재배포 요청 (삭제 시작)
2. 사용자 B가 동시에 재배포 요청 (같은 엔드포인트)
3. 두 요청이 동시에 삭제를 시도하거나, 삭제 중에 재배포를 시도

**원인**:
- 동시성 제어 메커니즘 없음
- DB 레벨 락이나 분산 락 없음

### 2. 삭제와 재배포 사이의 타이밍 문제

**시나리오**:
1. 삭제 요청 후 60초 대기
2. 타임아웃 전에 리소스가 삭제됨
3. 재배포 시도
4. 하지만 파드나 HPA가 아직 남아있어 충돌 발생

**원인**:
- 삭제 완료 확인이 메인 리소스(Deployment/InferenceService)만 확인
- 관련 리소스(HPA, Ingress, Service, Pods)는 확인하지 않음

### 3. 설정값 불일치

**시나리오**:
1. 재배포 시 `deployment_spec` 없이 호출
2. 기존 `deployment_spec`도 없음
3. 모델 메타데이터에서 재구성
4. 재구성된 값이 기존 실제 설정과 다름

**원인**:
- 재구성 로직이 하드코딩된 기본값 사용
- 기존 실제 Kubernetes 리소스 설정을 참조하지 않음

### 4. 에러 처리 및 롤백 부족

**시나리오**:
1. DB 업데이트 성공
2. Kubernetes 배포 실패
3. 엔드포인트 상태는 "failed"이지만 설정값은 이미 변경됨
4. 이전 설정값으로 롤백 불가능

**원인**:
- 트랜잭션 원자성 부족
- 롤백 메커니즘 없음

### 5. DeploymentSpec 재구성의 불완전성

**문제점**:
- `job_type`이 없으면 재구성 실패하지만 에러 없이 계속 진행
- 하드코딩된 값들:
  - `gpu_memory_gb: 80` (모든 GPU에 동일)
  - `max_concurrent_requests: 256`
  - `max_output_tokens: 1024`
- 기존 엔드포인트의 실제 설정값을 반영하지 않음

### 6. 리소스 설정 우선순위의 복잡성

**문제점**:
- DeploymentSpec이 있을 때와 없을 때 로직이 완전히 다름
- Legacy 로직에서 `None` 값이 deployer의 기본값으로 전달됨
- 예측 불가능한 동작

## 삭제 실패 시나리오

### 시나리오 1: 삭제 타임아웃 후 재배포

1. `delete_endpoint()` 호출
2. 60초 대기 후 타임아웃
3. 에러 발생하지만 예외 처리 후 계속 진행
4. 리소스가 아직 존재하는 상태에서 재배포 시도
5. 409 Conflict 발생

**원인**: 삭제 완료 확인이 부족함

### 시나리오 2: Finalizer로 인한 삭제 지연

1. Deployment/InferenceService에 finalizer 존재
2. 삭제 요청 후 리소스가 Terminating 상태로 남음
3. 60초 대기 후 타임아웃
4. 재배포 시도 → 409 Conflict

**원인**: Finalizer 제거 로직이 `delete_endpoint()` 내부에만 있음

### 시나리오 3: 관련 리소스가 남아있음

1. Deployment 삭제 완료
2. 하지만 HPA나 파드가 아직 남아있음
3. 재배포 시도
4. 리소스 이름 충돌 발생

**원인**: 관련 리소스 삭제 확인 부족

## 권장 해결 방법

### 1. 동시성 제어 추가

```python
# 분산 락 또는 DB 레벨 락 사용
@with_lock(endpoint_id)
def redeploy_endpoint(...):
    # 재배포 로직
```

### 2. 삭제 완료 확인 강화

```python
# 모든 관련 리소스 확인
def wait_for_complete_deletion(endpoint_name, namespace):
    # Deployment/InferenceService 확인
    # HPA 확인
    # Ingress 확인
    # Service 확인
    # Pods 확인
    # 모두 삭제될 때까지 대기
```

### 3. 설정값 백업 및 롤백

```python
# 재배포 전 기존 설정값 백업
backup_config = {
    "runtime_image": endpoint.runtime_image,
    "use_gpu": endpoint.use_gpu,
    "deployment_spec": endpoint.deployment_spec,
    # ...
}

try:
    # 재배포 시도
    ...
except Exception:
    # 롤백
    restore_config(endpoint, backup_config)
```

### 4. 트랜잭션 원자성 보장

```python
# DB 업데이트와 Kubernetes 배포를 하나의 트랜잭션으로
# 또는 배포 성공 후에만 DB 업데이트
```

### 5. DeploymentSpec 재구성 개선

```python
# 기존 Kubernetes 리소스에서 실제 설정값 읽기
# 또는 기존 엔드포인트의 모든 설정값을 보존
```

### 6. 삭제 로직 통합

```python
# redeploy_endpoint에서 별도로 삭제 대기하지 않고
# delete_endpoint()가 완료를 보장하도록 수정
# 또는 delete_endpoint()의 반환값을 신뢰하고 대기 로직 제거
```

## 디버깅 체크리스트

재배포가 실패할 때 확인할 사항:

1. ✅ 엔드포인트가 이미 삭제 중인 상태인가?
2. ✅ 동시에 다른 재배포 요청이 있는가?
3. ✅ 기존 리소스가 완전히 삭제되었는가? (Deployment, HPA, Ingress, Service, Pods)
4. ✅ Finalizer가 있는가?
5. ✅ DeploymentSpec 재구성이 올바른가?
6. ✅ 리소스 설정값이 예상과 일치하는가?
7. ✅ DB 상태와 Kubernetes 상태가 일치하는가?
8. ✅ 네임스페이스가 올바른가?
9. ✅ Kubernetes API 권한이 충분한가?

## 로그 확인 포인트

재배포 실패 시 다음 로그를 확인:

1. `Redeploying endpoint {endpoint_id}...` - 재배포 시작
2. `Deleted existing Kubernetes resources for endpoint {endpoint_id}` - 삭제 완료
3. `Waiting for {resource_type} {endpoint_name} to be deleted...` - 삭제 대기 중
4. `Timeout waiting for {resource_type} {endpoint_name} to be deleted` - 삭제 타임아웃
5. `Using existing deployment_spec from endpoint {endpoint_id}` - 기존 spec 사용
6. `Reconstructed deployment_spec from model metadata` - 재구성
7. `Redeployed serving endpoint {endpoint_id}` - 재배포 완료
8. `Failed to redeploy endpoint {endpoint_id}` - 재배포 실패

## 개선 사항 (2024년 적용)

### 1. 동시 재배포 방지
- ✅ 재배포 시작 시 엔드포인트 상태를 "deploying"으로 설정하여 동시 재배포 방지
- ✅ 이미 "deploying" 상태인 경우 에러 발생

### 2. 삭제 완료 확인 강화
- ✅ `deployer.delete_endpoint()` 호출 후 항상 리소스 존재 여부 확인
- ✅ 리소스가 완전히 삭제될 때까지 최대 90초 대기
- ✅ Terminating 상태 감지 및 대기
- ✅ 리소스가 존재하지만 Terminating이 아닌 경우 재삭제 시도
- ✅ 삭제 완료 확인 후에만 재배포 진행 (409 Conflict 방지)

### 7. deploy_endpoint() 내부에서 리소스 존재 확인 및 삭제
- ✅ `deploy_endpoint()` 시작 시 리소스 존재 여부 확인
- ✅ 리소스가 존재하면 자동으로 삭제 후 생성 (idempotency 보장)
- ✅ 재배포 로직과 이중 안전장치로 409 Conflict 완전 방지

### 3. 설정값 백업 및 롤백
- ✅ 재배포 전 모든 설정값 백업
- ✅ Kubernetes 배포 실패 시 자동으로 백업 설정값 복원
- ✅ 예외 발생 시에도 백업 설정값 복원 시도

### 4. 트랜잭션 원자성 보장
- ✅ **중요**: DB 업데이트를 Kubernetes 배포 성공 후로 이동
- ✅ 배포 실패 시 DB는 변경되지 않음
- ✅ 배포 성공 후에만 DB에 새 설정값 저장

### 5. DeploymentSpec 재구성 개선
- ✅ 기존 `deployment_spec`의 `runtime` 및 `resources` 설정 보존
- ✅ 재구성 시 기존 설정값 우선 사용, 없을 때만 기본값 사용
- ✅ `use_gpu`가 `None`인 경우 폴백 로직 개선

### 6. 에러 처리 개선
- ✅ 배포 실패 시 명확한 에러 메시지
- ✅ 백업 설정값 복원 실패 시에도 로그 기록
- ✅ 예외 타입별 처리 (ValueError는 그대로 전파)

## 개선된 재배포 흐름

1. **엔드포인트 조회 및 검증**
   - 엔드포인트 존재 확인
   - 동시 재배포 방지 (상태 체크)
   - 모델 엔트리 검증

2. **설정값 백업**
   - 현재 모든 설정값 백업

3. **상태 업데이트 (deploying)**
   - 동시 재배포 방지를 위해 먼저 상태 업데이트

4. **Kubernetes 리소스 삭제 및 완료 확인**
   - `deployer.delete_endpoint()` 호출
   - 리소스가 완전히 삭제될 때까지 최대 90초 대기
   - Terminating 상태 감지 및 대기
   - 리소스가 존재하지만 Terminating이 아닌 경우 재삭제 시도
   - 삭제 완료 확인 후에만 다음 단계 진행 (409 Conflict 방지)

5. **설정값 결정**
   - DeploymentSpec 우선순위: 새 spec -> 기존 spec -> 재구성
   - 재구성 시 기존 설정값 보존

6. **Kubernetes 배포**
   - `deploy_endpoint()` 호출 (내부에서 리소스 존재 확인 및 삭제)
   - 배포 성공 후에만 다음 단계 진행
   - 배포 실패 시 백업 설정값 복원 및 에러 발생

7. **DB 업데이트**
   - 배포 성공 후에만 DB 업데이트
   - 새 설정값 저장

8. **상태 동기화**
   - Kubernetes에서 실제 상태 조회
   - DB 상태 업데이트

## 개선 사항 (2024년 12월 적용)

### 1. 로깅 강화
- ✅ 프론트엔드: 재배포 시작/완료, 요청 페이로드, 응답, 에러 상세 로깅 추가
- ✅ 백엔드 API: 요청 수신, 요청 body, 서비스 메서드 호출 전후 로깅 추가
- ✅ 서비스 레이어: 각 단계별 상세 로깅 (삭제 시작/완료, 배포 시작, 설정값 결정 등)
- ✅ 에러 발생 시 `exc_info=True`로 상세 스택 트레이스 로깅

### 2. 에러 처리 개선
- ✅ 백엔드 API: `ValueError`와 일반 `Exception` 구분하여 처리
- ✅ 명확한 에러 메시지 제공 (검증 에러 vs 예상치 못한 에러)
- ✅ 프론트엔드: 에러 메시지 파싱 및 표시 개선

### 3. 409 Conflict 처리 강화
- ✅ 리소스 생성 전 최종 확인 로직 추가 (60초 대기)
- ✅ 409 Conflict 발생 시 자동 재시도 로직 추가
- ✅ 재시도 시 삭제 완료 확인 후 재생성 (최대 120초 대기)
- ✅ 모든 리소스 생성 경로에 409 처리 적용 (Deployment, KServe InferenceService, Service, HPA, Ingress)

### 4. 코드 정리 및 리팩토링
- ✅ 공통 헬퍼 메서드 추가:
  - `_check_resource_exists()`: 리소스 존재 및 Terminating 상태 확인
  - `_ensure_resource_deleted()`: 리소스 완전 삭제 확인 (대기 포함)
  - `_handle_409_conflict()`: 409 Conflict 발생 시 삭제 후 재시도
- ✅ 중복 코드 제거 (약 500줄 이상 감소)
- ✅ 코드 가독성 및 유지보수성 향상

### 5. 삭제 로직 개선
- ✅ `delete_endpoint()` 함수가 KServe 설정과 무관하게 실제 존재하는 리소스 모두 삭제
- ✅ KServe InferenceService와 Deployment 모두 확인 및 삭제
- ✅ 관련 리소스 삭제 로직 통합 (`_delete_related_resources()` 메서드)
- ✅ HPA, Ingress, Service, Pods 모두 삭제 보장

## 다음 단계

1. 실제 재배포 실패 로그 확인
2. Kubernetes 리소스 상태 확인 (`kubectl get all -n {namespace}`)
3. DB 상태 확인 (엔드포인트 설정값)
4. 동시성 테스트 수행
5. 배포 실패 시 롤백 동작 검증
6. 409 Conflict 재시도 로직 검증
7. 삭제 로직 완전성 검증

