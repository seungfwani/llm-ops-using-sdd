# Serving Endpoint 재배포 문제 해결 플랜

## 개요

재배포가 전혀 동작하지 않는 문제를 해결하기 위한 단계별 플랜입니다.

## 문제 진단 단계

### Phase 1: 문제 발생 지점 파악

#### 1.1 프론트엔드 확인
**목표**: API 요청이 실제로 전송되는지 확인

**작업**:
- [ ] 브라우저 개발자 도구에서 네트워크 탭 확인
- [ ] `POST /llm-ops/v1/serving/endpoints/{id}/redeploy` 요청 확인
- [ ] 요청 Body 내용 확인
- [ ] 응답 상태 코드 및 메시지 확인
- [ ] 브라우저 콘솔 에러 확인

**예상 결과**:
- 요청이 전송되는지 여부
- 요청 Body가 올바른지 여부
- 응답이 무엇인지 (성공/실패, 에러 메시지)

#### 1.2 백엔드 로그 확인
**목표**: API 엔드포인트가 호출되는지 확인

**작업**:
- [ ] API 라우터 로그 확인 (`serving.py:redeploy_endpoint`)
- [ ] 요청이 도달하는지 확인
- [ ] `RedeployEndpointRequest` 검증 통과 여부 확인
- [ ] `service.redeploy_endpoint()` 호출 여부 확인

**확인할 로그**:
```
- API 요청 수신 로그
- 스키마 검증 로그
- 서비스 메서드 호출 로그
```

#### 1.3 서비스 레이어 로그 확인
**목표**: 재배포 로직이 실행되는지 확인

**작업**:
- [ ] `serving_service.py:redeploy_endpoint()` 로그 확인
- [ ] 각 단계별 로그 확인:
  - 엔드포인트 조회
  - 동시 재배포 방지 체크
  - 설정값 백업
  - Kubernetes 리소스 삭제
  - 삭제 완료 확인
  - 설정값 결정
  - Kubernetes 배포
  - DB 업데이트

**확인할 로그**:
```
- "Starting redeployment for endpoint {id}"
- "Deleted existing Kubernetes resources for endpoint {id}"
- "Verified deletion of {resource_type} {name}"
- "Successfully deployed Kubernetes resources for endpoint {id}"
- "Failed to redeploy endpoint {id}"
```

#### 1.4 배포 레이어 로그 확인
**목표**: Kubernetes API 호출이 실행되는지 확인

**작업**:
- [ ] `deployer.py:delete_endpoint()` 로그 확인
- [ ] `deployer.py:deploy_endpoint()` 로그 확인
- [ ] Kubernetes API 호출 로그 확인:
  - 리소스 존재 확인
  - 삭제 API 호출
  - 삭제 응답
  - 리소스 생성 API 호출
  - 생성 응답

**확인할 로그**:
```
- "Checking if {resource_type} {name} exists"
- "Attempting to delete {resource_type} {name}"
- "Delete API call successful"
- "ApiException when deleting"
```

#### 1.5 Kubernetes 상태 확인
**목표**: 실제 리소스 상태 확인

**작업**:
- [ ] `kubectl get deployment {name} -n {namespace}` 실행
- [ ] `kubectl get inferenceservice {name} -n {namespace}` 실행 (KServe 사용 시)
- [ ] 리소스가 존재하는지 확인
- [ ] 리소스 상태 확인 (Ready, Terminating 등)
- [ ] Pods 상태 확인: `kubectl get pods -n {namespace} -l app={name}`

## 문제 해결 단계

### Phase 2: 로깅 강화

#### 2.1 프론트엔드 로깅 추가
**목표**: 요청 전송 및 응답 처리 과정 추적

**작업**:
- [ ] `handleRedeploy()` 함수에 상세 로깅 추가
- [ ] Request Body 로깅
- [ ] Response 로깅
- [ ] 에러 발생 시 상세 정보 로깅

**수정 파일**: `frontend/src/pages/serving/EndpointDetail.vue`

```typescript
async function handleRedeploy() {
  console.log('[Redeploy] Starting redeployment for endpoint:', endpoint.value?.id);
  console.log('[Redeploy] Request payload:', request);
  
  try {
    const response = await servingClient.redeployEndpoint(...);
    console.log('[Redeploy] Response received:', response);
    // ...
  } catch (e) {
    console.error('[Redeploy] Error:', e);
    // ...
  }
}
```

#### 2.2 백엔드 API 로깅 추가
**목표**: API 요청 및 검증 과정 추적

**작업**:
- [ ] 요청 수신 로그 추가
- [ ] Request Body 로깅
- [ ] 스키마 검증 결과 로깅
- [ ] 서비스 메서드 호출 전후 로깅

**수정 파일**: `backend/src/api/routes/serving.py`

```python
@router.post("/endpoints/{endpointId}/redeploy")
def redeploy_endpoint(...):
    logger.info(f"Redeploy request received for endpoint {endpointId}")
    logger.debug(f"Request body: {request.model_dump()}")
    # ...
```

#### 2.3 서비스 레이어 로깅 강화
**목표**: 각 단계별 상세 로깅

**작업**:
- [ ] 각 단계 시작/완료 로깅
- [ ] 예외 발생 시 상세 정보 로깅 (exc_info=True)
- [ ] 중요한 변수 값 로깅
- [ ] 타임아웃 발생 시 로깅

**수정 파일**: `backend/src/serving/serving_service.py`

#### 2.4 배포 레이어 로깅 강화
**목표**: Kubernetes API 호출 상세 추적

**작업**:
- [ ] API 호출 전후 로깅
- [ ] 요청 파라미터 로깅
- [ ] 응답 내용 로깅
- [ ] 예외 발생 시 상세 정보 로깅

**수정 파일**: `backend/src/serving/services/deployer.py`

**이미 추가됨**: 삭제 API 호출 로깅은 이미 강화되어 있음

### Phase 3: 에러 처리 개선

#### 3.1 프론트엔드 에러 처리 개선
**목표**: 사용자에게 명확한 에러 메시지 제공

**작업**:
- [ ] `alert()` 대신 더 나은 UI 컴포넌트 사용
- [ ] 에러 메시지 파싱 및 표시
- [ ] 재시도 옵션 제공
- [ ] 로딩 상태 표시 개선

**수정 파일**: `frontend/src/pages/serving/EndpointDetail.vue`

#### 3.2 백엔드 에러 처리 개선
**목표**: 명확한 에러 메시지 반환

**작업**:
- [ ] 예외 타입별 처리
- [ ] 에러 메시지에 컨텍스트 추가
- [ ] HTTP 상태 코드 적절히 설정
- [ ] 에러 응답에 상세 정보 포함

**수정 파일**: `backend/src/api/routes/serving.py`

```python
except ValueError as e:
    logger.error(f"Validation error for endpoint {endpointId}: {e}")
    return schemas.EnvelopeServingEndpoint(
        status="fail",
        message=f"Invalid request: {str(e)}",
        data=None,
    )
except Exception as e:
    logger.error(f"Unexpected error redeploying endpoint {endpointId}: {e}", exc_info=True)
    return schemas.EnvelopeServingEndpoint(
        status="fail",
        message=f"Failed to redeploy endpoint: {str(e)}",
        data=None,
    )
```

#### 3.3 서비스 레이어 에러 처리 개선
**목표**: 각 단계별 에러 처리 및 롤백

**작업**:
- [ ] 각 단계별 try-except 추가
- [ ] 에러 발생 시 백업 설정값 복원
- [ ] 명확한 에러 메시지 생성
- [ ] 에러 발생 지점 로깅

**수정 파일**: `backend/src/serving/serving_service.py`

### Phase 4: 삭제 로직 수정

#### 4.1 삭제 API 호출 검증
**목표**: 삭제가 실제로 실행되는지 확인

**작업**:
- [ ] 삭제 API 호출 전 리소스 상태 확인
- [ ] 삭제 API 호출 후 응답 확인
- [ ] 삭제 실패 시 재시도 로직 추가
- [ ] 삭제 완료 확인 로직 강화

**수정 파일**: `backend/src/serving/services/deployer.py`

**이미 개선됨**: 상세 로깅이 추가되어 있음

#### 4.2 삭제 완료 확인 로직 개선
**목표**: 리소스가 완전히 삭제되었는지 확실히 확인

**작업**:
- [ ] 여러 방법으로 리소스 존재 확인
- [ ] 관련 리소스도 확인 (HPA, Ingress, Service, Pods)
- [ ] 타임아웃 증가 (현재 90초 → 120초)
- [ ] Finalizer 제거 강화

**수정 파일**: `backend/src/serving/services/deployer.py`

#### 4.3 삭제 실패 시 처리 개선
**목표**: 삭제 실패 시에도 재배포 가능하도록

**작업**:
- [ ] 삭제 실패 시 리소스 강제 삭제 시도
- [ ] Finalizer 제거 후 재삭제 시도
- [ ] 모든 방법 실패 시 명확한 에러 메시지

**수정 파일**: `backend/src/serving/services/deployer.py`

### Phase 5: 배포 로직 수정

#### 5.1 리소스 존재 확인 강화
**목표**: 배포 전 리소스가 완전히 삭제되었는지 확인

**작업**:
- [ ] `deploy_endpoint()` 시작 시 리소스 존재 확인
- [ ] 존재하면 삭제 및 완료 확인
- [ ] 삭제 완료 후에만 생성 진행

**수정 파일**: `backend/src/serving/services/deployer.py`

**이미 개선됨**: 리소스 존재 확인 로직이 추가되어 있음

#### 5.2 409 Conflict 방지
**목표**: 리소스가 아직 존재하는 상태에서 생성 시도 방지

**작업**:
- [ ] 생성 전 최종 확인
- [ ] 409 Conflict 발생 시 재삭제 시도
- [ ] 재시도 후에도 실패 시 명확한 에러

**수정 파일**: `backend/src/serving/services/deployer.py`

### Phase 6: 동시성 제어 개선

#### 6.1 DB 레벨 락 추가
**목표**: 동시 재배포 완전 방지

**작업**:
- [ ] SELECT FOR UPDATE 사용
- [ ] 트랜잭션 격리 수준 설정
- [ ] 락 타임아웃 설정

**수정 파일**: `backend/src/serving/serving_service.py`

```python
# 엔드포인트 조회 시 락 획득
endpoint = (
    self.session.query(catalog_models.ServingEndpoint)
    .filter(catalog_models.ServingEndpoint.id == endpoint_id)
    .with_for_update()
    .first()
)
```

#### 6.2 상태 체크 강화
**목표**: 이미 재배포 중인 엔드포인트 재배포 방지

**작업**:
- [ ] 상태 체크 로직 개선
- [ ] "deploying" 상태일 때 명확한 에러 메시지
- [ ] 상태 업데이트 원자성 보장

**수정 파일**: `backend/src/serving/serving_service.py`

### Phase 7: 테스트 및 검증

#### 7.1 단위 테스트
**작업**:
- [ ] 각 단계별 단위 테스트 작성
- [ ] 에러 케이스 테스트
- [ ] 동시성 테스트

#### 7.2 통합 테스트
**작업**:
- [ ] 전체 재배포 흐름 테스트
- [ ] 삭제 실패 시나리오 테스트
- [ ] 배포 실패 시나리오 테스트

#### 7.3 수동 테스트
**작업**:
- [ ] 실제 환경에서 재배포 테스트
- [ ] 로그 확인
- [ ] Kubernetes 리소스 상태 확인

## 우선순위별 작업 순서

### 즉시 실행 (High Priority)

1. **로그 확인** (Phase 1)
   - 실제 로그를 확인하여 문제 발생 지점 파악
   - 가장 중요한 단계

2. **로깅 강화** (Phase 2)
   - 문제 파악을 위해 상세 로깅 추가
   - 특히 삭제 및 배포 단계

3. **에러 처리 개선** (Phase 3)
   - 명확한 에러 메시지로 문제 파악 용이

### 중기 작업 (Medium Priority)

4. **삭제 로직 수정** (Phase 4)
   - 삭제가 제대로 동작하도록 수정

5. **배포 로직 수정** (Phase 5)
   - 409 Conflict 방지

### 장기 작업 (Low Priority)

6. **동시성 제어 개선** (Phase 6)
   - DB 레벨 락 추가

7. **테스트 및 검증** (Phase 7)
   - 자동화된 테스트 추가

## 예상 문제 시나리오 및 해결책

### 시나리오 1: 삭제 API 호출이 실행되지 않음

**증상**: 로그에 "Attempting to delete" 메시지가 없음

**원인**:
- `delete_endpoint()`가 호출되지 않음
- 예외가 발생했지만 처리되지 않음

**해결책**:
- 로깅 추가하여 호출 여부 확인
- 예외 처리 개선

### 시나리오 2: 삭제 API 호출은 되지만 리소스가 삭제되지 않음

**증상**: 로그에 "Delete API call successful"이 있지만 리소스가 여전히 존재

**원인**:
- Kubernetes API 권한 문제
- Finalizer 문제
- 리소스가 Terminating 상태로 멈춤

**해결책**:
- Finalizer 제거 강화
- 강제 삭제 로직 추가
- 권한 확인

### 시나리오 3: 삭제는 되지만 재배포가 실패

**증상**: 삭제는 성공하지만 배포 시 409 Conflict 발생

**원인**:
- 삭제 완료 확인이 부족
- 리소스가 아직 Terminating 상태

**해결책**:
- 삭제 완료 확인 강화
- 배포 전 최종 확인 추가

### 시나리오 4: 프론트엔드에서 요청이 전송되지 않음

**증상**: 네트워크 탭에 요청이 없음

**원인**:
- JavaScript 에러
- 요청 전송 전 예외 발생

**해결책**:
- 프론트엔드 에러 처리 개선
- 로깅 추가

## 체크리스트

### 진단 단계
- [ ] 프론트엔드 네트워크 요청 확인
- [ ] 백엔드 API 로그 확인
- [ ] 서비스 레이어 로그 확인
- [ ] 배포 레이어 로그 확인
- [ ] Kubernetes 리소스 상태 확인

### 해결 단계
- [ ] 로깅 강화 완료
- [ ] 에러 처리 개선 완료
- [ ] 삭제 로직 수정 완료
- [ ] 배포 로직 수정 완료
- [ ] 동시성 제어 개선 완료
- [ ] 테스트 완료

## 구현 완료 사항 (2024년 12월)

### Phase 2: 로깅 강화 ✅
- ✅ 프론트엔드 로깅 추가 (`EndpointDetail.vue`)
- ✅ 백엔드 API 로깅 추가 (`serving.py`)
- ✅ 서비스 레이어 로깅 강화 (`serving_service.py`)
- ✅ 배포 레이어 로깅 강화 (`deployer.py`)

### Phase 3: 에러 처리 개선 ✅
- ✅ 프론트엔드 에러 처리 개선
- ✅ 백엔드 에러 처리 개선 (ValueError vs Exception 구분)
- ✅ 서비스 레이어 에러 처리 개선

### Phase 4: 삭제 로직 수정 ✅
- ✅ 삭제 API 호출 검증 강화
- ✅ 삭제 완료 확인 로직 개선 (120초 대기, Terminating 상태 감지)
- ✅ 삭제 실패 시 처리 개선 (강제 삭제 시도)

### Phase 5: 배포 로직 수정 ✅
- ✅ 리소스 존재 확인 강화 (최종 확인 추가)
- ✅ 409 Conflict 방지 (자동 재시도 로직 추가)
- ✅ 모든 리소스 생성 경로에 409 처리 적용

### Phase 6: 코드 정리 ✅
- ✅ 공통 헬퍼 메서드 추출
- ✅ 중복 코드 제거 (약 500줄 이상 감소)
- ✅ 코드 가독성 및 유지보수성 향상

### Phase 7: 삭제 로직 개선 ✅
- ✅ `delete_endpoint()` 함수가 KServe 설정과 무관하게 모든 리소스 삭제
- ✅ 관련 리소스 삭제 로직 통합

## 다음 단계

1. **즉시**: 실제 로그 확인 및 검증 (Phase 1)
2. **단기**: 동시성 제어 개선 (Phase 6 - DB 레벨 락 추가)
3. **중기**: 테스트 및 검증 (Phase 7)
4. **장기**: 성능 최적화 및 모니터링 강화

