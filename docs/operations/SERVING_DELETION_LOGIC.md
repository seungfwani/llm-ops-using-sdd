# Serving Endpoint 삭제 로직 분석 문서

## 개요

이 문서는 Kubernetes에 배포된 서빙 엔드포인트의 삭제 로직을 분석하고, 삭제가 실패하는 원인을 파악하기 위해 작성되었습니다.

## 삭제 흐름

### 1. 재배포 시 삭제 (`redeploy_endpoint`)

**위치**: `backend/src/serving/serving_service.py:367-425`

**흐름**:
1. `delete_endpoint()` 호출
2. 삭제 성공 여부 확인 (`delete_success`)
3. 리소스가 완전히 삭제될 때까지 대기 (최대 60초)
4. 타임아웃 시 에러 발생

**문제점**:
- `delete_endpoint()`가 `False`를 반환해도 경고만 하고 계속 진행
- Foreground propagation을 사용하지만, 실제로는 삭제가 완료되기 전에 재배포 시도 가능
- 삭제 실패 시 명확한 에러 메시지가 있지만, 예외가 catch되어 무시될 수 있음

### 2. 엔드포인트 삭제 (`delete_endpoint` - ServingService)

**위치**: `backend/src/serving/serving_service.py:646-659`

**흐름**:
1. 엔드포인트 조회
2. `deployer.delete_endpoint()` 호출
3. DB에서 엔드포인트 삭제

**문제점**:
- Kubernetes 리소스 삭제 실패 시에도 DB는 삭제됨
- 삭제 순서: K8s 리소스 → DB (원자성이 없음)

### 3. Kubernetes 리소스 삭제 (`delete_endpoint` - ServingDeployer)

**위치**: `backend/src/serving/services/deployer.py:1299-1397`

#### 3.1 KServe 사용 시 (`_delete_kserve`)

**위치**: `backend/src/serving/services/deployer.py:1399-1467`

**삭제 순서**:
1. InferenceService 삭제 (`Background` propagation)
2. 파드 강제 삭제 (라벨 셀렉터로 찾아서 삭제)
3. 이름 패턴으로 파드 찾아서 삭제

**문제점**:
- `Background` propagation 사용 → 삭제가 비동기로 진행됨
- 삭제 완료를 기다리지 않음
- 파드 라벨이 정확하지 않으면 파드를 찾지 못할 수 있음

#### 3.2 일반 Deployment 사용 시

**위치**: `backend/src/serving/services/deployer.py:1306-1397`

**삭제 순서**:
1. Deployment 스케일 다운 (replicas=0)
2. HPA 삭제 (`{endpoint_name}-hpa`)
3. Ingress 삭제 (`{endpoint_name}-ingress`)
4. Service 삭제 (`{endpoint_name}-svc`)
5. Deployment 삭제 (`Foreground` propagation, grace_period_seconds=30)
6. 남은 파드 강제 삭제 (라벨 셀렉터: `app={endpoint_name}`)

**문제점**:
- 각 단계에서 404 에러는 무시하지만, 다른 에러는 경고만 함
- Deployment 삭제 실패 시 예외를 발생시키지만, catch되어 `False` 반환
- `Foreground` propagation을 사용하지만, 실제로는 삭제가 완료되기 전에 반환될 수 있음
- 파드 라벨이 `app={endpoint_name}`이 아닐 수 있음

## 잠재적 문제점

### 1. Propagation Policy 문제

**현재 상태**:
- KServe: `Background` propagation (비동기)
- 일반 Deployment: `Foreground` propagation (동기, 하지만 완전히 기다리지 않음)

**문제**:
- `Foreground` propagation은 finalizer를 사용하여 삭제를 보장하지만, finalizer가 제거되기 전에 재배포를 시도하면 409 Conflict 발생
- `Background` propagation은 즉시 반환되므로, 리소스가 아직 존재할 수 있음

### 2. 리소스 이름 불일치

**문제**:
- HPA 이름: `{endpoint_name}-hpa`
- Ingress 이름: `{endpoint_name}-ingress`
- Service 이름: `{endpoint_name}-svc`
- 실제 배포 시 이 이름들이 다를 수 있음

### 3. 파드 라벨 불일치

**문제**:
- 파드 라벨: `app={endpoint_name}`
- 실제 배포 시 다른 라벨을 사용할 수 있음
- KServe의 경우 라벨이 다를 수 있음

### 4. Finalizer 문제

**문제**:
- Deployment나 InferenceService에 finalizer가 있으면 삭제가 블록될 수 있음
- Finalizer를 제거하지 않으면 리소스가 삭제되지 않음

### 5. 네임스페이스 문제

**문제**:
- 네임스페이스가 존재하지 않으면 삭제 실패
- 네임스페이스가 다르면 리소스를 찾을 수 없음

## 삭제 실패 시나리오

### 시나리오 1: Foreground Propagation이 완료되지 않음

1. `delete_namespaced_deployment()` 호출 (Foreground propagation)
2. API는 즉시 반환 (삭제는 백그라운드에서 진행)
3. 재배포 시도
4. Deployment가 아직 존재 → 409 Conflict

**원인**: Foreground propagation이 실제로 완료를 기다리지 않음

### 시나리오 2: Finalizer가 있는 경우

1. Deployment에 finalizer가 있음
2. 삭제 요청 시 finalizer가 제거되지 않음
3. Deployment가 `Terminating` 상태로 남음
4. 재배포 시도 → 409 Conflict

**원인**: Finalizer를 명시적으로 제거하지 않음

### 시나리오 3: 리소스 이름 불일치

1. 실제 HPA 이름이 `{endpoint_name}-hpa`가 아님
2. HPA 삭제 실패 (404 무시)
3. HPA가 남아있어서 Deployment 삭제가 블록됨
4. 재배포 시도 → 409 Conflict

**원인**: 리소스 이름이 예상과 다름

### 시나리오 4: 파드가 Terminating 상태로 남음

1. Deployment 삭제 요청
2. 파드가 정상 종료되지 않음
3. 파드가 `Terminating` 상태로 남음
4. Deployment가 삭제되지 않음
5. 재배포 시도 → 409 Conflict

**원인**: 파드 강제 삭제가 실패하거나, 파드를 찾지 못함

## 권장 해결 방법

### 1. 삭제 완료 확인 로직 개선

```python
# 삭제 후 실제로 리소스가 사라졌는지 확인
def wait_for_deletion(endpoint_name, namespace, max_wait=60):
    waited = 0
    while waited < max_wait:
        try:
            # 리소스 존재 확인
            if resource_exists(endpoint_name, namespace):
                time.sleep(2)
                waited += 2
            else:
                return True  # 삭제 완료
        except ApiException as e:
            if e.status == 404:
                return True  # 삭제 완료
            raise
    return False  # 타임아웃
```

### 2. Finalizer 명시적 제거

```python
# Deployment의 finalizer 제거
deployment = apps_api.read_namespaced_deployment(name, namespace)
if deployment.metadata.finalizers:
    deployment.metadata.finalizers = []
    apps_api.patch_namespaced_deployment(name, namespace, deployment)
```

### 3. Graceful Deletion 강제

```python
# Grace period를 0으로 설정하여 즉시 삭제
body = client.V1DeleteOptions(
    propagation_policy="Foreground",
    grace_period_seconds=0  # 즉시 삭제
)
```

### 4. 리소스 이름 동적 확인

```python
# 실제 리소스 이름 확인
deployments = apps_api.list_namespaced_deployment(namespace)
for dep in deployments.items:
    if endpoint_name in dep.metadata.name:
        # 실제 이름으로 삭제
        delete_resource(dep.metadata.name)
```

### 5. 삭제 전 리소스 상태 확인

```python
# 삭제 전 리소스 상태 확인
deployment = apps_api.read_namespaced_deployment(name, namespace)
if deployment.metadata.deletion_timestamp:
    # 이미 삭제 중이면 대기
    wait_for_deletion(name, namespace)
```

## 디버깅 체크리스트

삭제가 실패할 때 확인할 사항:

1. ✅ Deployment/InferenceService가 실제로 존재하는가?
2. ✅ 리소스 이름이 예상과 일치하는가?
3. ✅ Finalizer가 있는가?
4. ✅ 리소스가 `Terminating` 상태인가?
5. ✅ 파드가 정상 종료되고 있는가?
6. ✅ 네임스페이스가 올바른가?
7. ✅ Kubernetes API 권한이 충분한가?
8. ✅ 삭제 후 실제로 리소스가 사라졌는가?

## 로그 확인 포인트

삭제 실패 시 다음 로그를 확인:

1. `Deleted Deployment {endpoint_name} with Foreground propagation` - 삭제 요청 성공
2. `Waiting for Deployment {endpoint_name} to be deleted...` - 삭제 대기 중
3. `Deployment {endpoint_name} successfully deleted` - 삭제 완료 확인
4. `Failed to delete Deployment {endpoint_name}: {e}` - 삭제 실패
5. `Timeout waiting for Deployment {endpoint_name} to be deleted` - 타임아웃

## 개선 사항 (2024년 12월 적용)

### 1. `delete_endpoint()` 함수 개선
- ✅ KServe 설정과 무관하게 실제 존재하는 리소스를 모두 삭제하도록 변경
- ✅ KServe InferenceService 존재 시 삭제 시도
- ✅ Deployment 존재 시 삭제 시도
- ✅ 두 리소스 모두 존재하는 경우 모두 삭제

### 2. 관련 리소스 삭제 로직 통합
- ✅ `_delete_related_resources()` 메서드 추가
- ✅ HPA, Ingress, Service, Pods 삭제 로직 통합
- ✅ 동적 검색으로 이름이 다른 리소스도 삭제
- ✅ 모든 관련 리소스 삭제 보장

### 3. 코드 구조 개선
- ✅ `_delete_deployment()` 메서드 분리
- ✅ 관련 리소스 삭제는 `delete_endpoint()`에서 한 번만 수행
- ✅ 중복 코드 제거 및 가독성 향상

### 4. 에러 처리 개선
- ✅ 각 리소스 삭제 시도 시 예외 처리 강화
- ✅ 삭제 실패해도 다른 리소스 삭제 계속 진행
- ✅ 상세 로깅으로 삭제 과정 추적 가능

## 개선된 삭제 흐름

1. **KServe InferenceService 확인 및 삭제**
   - 리소스 존재 확인 (`_check_resource_exists()`)
   - 존재하면 `_delete_kserve()` 호출
   - 삭제 실패해도 계속 진행

2. **Deployment 확인 및 삭제**
   - 리소스 존재 확인 (`_check_resource_exists()`)
   - 존재하면 `_delete_deployment()` 호출
   - 삭제 실패해도 계속 진행

3. **관련 리소스 삭제**
   - `_delete_related_resources()` 호출
   - HPA, Ingress, Service, Pods 모두 삭제
   - 동적 검색으로 이름이 다른 리소스도 삭제

4. **결과 반환**
   - KServe 또는 Deployment 중 하나라도 삭제 성공하면 `True` 반환
   - 둘 다 없으면 `True` 반환 (이미 삭제됨)

## 다음 단계

1. 실제 삭제 실패 로그 확인
2. Kubernetes 리소스 상태 확인 (`kubectl get deployment -n {namespace}`)
3. Finalizer 확인 (`kubectl get deployment {name} -o yaml | grep finalizers`)
4. 파드 상태 확인 (`kubectl get pods -n {namespace} -l app={endpoint_name}`)
5. 위의 권장 해결 방법 적용
6. KServe와 Deployment 동시 삭제 시나리오 검증
7. 관련 리소스 완전 삭제 검증

