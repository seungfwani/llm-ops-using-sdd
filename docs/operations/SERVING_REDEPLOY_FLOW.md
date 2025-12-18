# Serving Endpoint 재배포 전체 흐름 분석 문서

## 개요

이 문서는 웹페이지에서 재배포 버튼을 클릭하는 것부터 Kubernetes에 실제로 배포되는 것까지의 전체 흐름을 추적하여 문제점을 파악하기 위해 작성되었습니다.

## 전체 흐름 다이어그램

```
[웹페이지] EndpointDetail.vue
    ↓ 사용자가 "Redeploy Endpoint" 버튼 클릭
    ↓ handleRedeploy() 함수 실행
    ↓
[프론트엔드] servingClient.redeployEndpoint()
    ↓ POST /llm-ops/v1/serving/endpoints/{endpointId}/redeploy
    ↓ Request Body: { deploymentSpec?, useGpu?, ... }
    ↓
[백엔드 API] serving.py:redeploy_endpoint()
    ↓ schemas.RedeployEndpointRequest 검증
    ↓ service.redeploy_endpoint() 호출
    ↓
[서비스 레이어] serving_service.py:redeploy_endpoint()
    ↓ 1. 엔드포인트 조회 및 검증
    ↓ 2. 동시 재배포 방지 (상태 체크)
    ↓ 3. 설정값 백업
    ↓ 4. 상태를 "deploying"으로 변경
    ↓ 5. Kubernetes 리소스 삭제
    ↓ 6. 삭제 완료 확인 (최대 90초 대기)
    ↓ 7. 설정값 결정 (DeploymentSpec 재구성)
    ↓ 8. Kubernetes 배포 (deployer.deploy_endpoint())
    ↓ 9. DB 업데이트 (배포 성공 후)
    ↓ 10. 상태 동기화
    ↓
[배포 레이어] deployer.py:deploy_endpoint()
    ↓ 1. 리소스 존재 확인
    ↓ 2. 존재하면 삭제 및 완료 확인
    ↓ 3. 리소스 생성 (Deployment/InferenceService)
    ↓
[Kubernetes API]
    ↓ Deployment/InferenceService 생성
    ↓ Pods 시작
    ↓ Status 업데이트
```

## 상세 흐름 분석

### 1. 프론트엔드: EndpointDetail.vue

**위치**: `frontend/src/pages/serving/EndpointDetail.vue:733-877`

**함수**: `handleRedeploy()`

**흐름**:
1. 사용자 확인 (`confirm()`)
2. `redeploying.value = true` 설정
3. DeploymentSpec 준비
   - 기존 DeploymentSpec이 없으면 모델 메타데이터에서 재구성
   - `hasRedeployDeploymentSpec` 체크
4. Request 객체 생성
   ```typescript
   {
     deploymentSpec?: DeploymentSpec,
     useGpu?: boolean,
     servingRuntimeImage?: string,
     cpuRequest?: string,
     cpuLimit?: string,
     memoryRequest?: string,
     memoryLimit?: string,
     autoscalePolicy?: {...},
     servingFramework?: string
   }
   ```
5. `servingClient.redeployEndpoint(endpointId, request)` 호출
6. 응답 처리
   - 성공: `alert('Endpoint redeployment started successfully...')`
   - 실패: `alert('Redeploy failed: ${response.message}')`
7. `fetchEndpoint()` 호출하여 상태 갱신

**잠재적 문제점**:
- DeploymentSpec이 불완전할 수 있음
- 에러 메시지가 `alert()`로만 표시됨 (사용자 경험 저하)
- 재배포 중 상태 업데이트가 없음 (로딩 인디케이터만 있음)

### 2. 프론트엔드 API 클라이언트: servingClient.ts

**위치**: `frontend/src/services/servingClient.ts:197-212`

**함수**: `redeployEndpoint()`

**흐름**:
1. URL 구성: `/serving/endpoints/${endpointId}/redeploy`
2. `apiClient.post()` 호출
3. Request Body 전송 (위에서 준비한 request 객체)
4. Response 반환

**잠재적 문제점**:
- Request Body가 빈 객체일 수 있음 (`request || {}`)
- 타임아웃 설정이 없음 (장시간 대기 시 문제)

### 3. 백엔드 API 라우터: serving.py

**위치**: `backend/src/api/routes/serving.py:265-327`

**엔드포인트**: `POST /llm-ops/v1/serving/endpoints/{endpointId}/redeploy`

**흐름**:
1. `schemas.RedeployEndpointRequest` 검증
2. `service.redeploy_endpoint()` 호출
   ```python
   endpoint = service.redeploy_endpoint(
       endpointId,
       use_gpu=request.useGpu,
       serving_runtime_image=request.servingRuntimeImage,
       cpu_request=request.cpuRequest,
       cpu_limit=request.cpuLimit,
       memory_request=request.memoryRequest,
       memory_limit=request.memoryLimit,
       autoscale_policy=request.autoscalePolicy,
       serving_framework=request.servingFramework,
       deployment_spec=request.deploymentSpec,
   )
   ```
3. 응답 생성 및 반환

**잠재적 문제점**:
- `RedeployEndpointRequest` 스키마 확인 필요
- 예외 처리가 `ValueError`와 일반 `Exception`만 구분
- 에러 메시지가 상세하지 않을 수 있음

### 4. 서비스 레이어: serving_service.py

**위치**: `backend/src/serving/serving_service.py:327-644`

**함수**: `redeploy_endpoint()`

**주요 단계**:

#### 4.1 엔드포인트 조회 및 검증 (341-366)
- 엔드포인트 존재 확인
- 모델 엔트리 조회 및 검증
- 모델 상태가 "approved"인지 확인
- External 모델인 경우 즉시 반환

**잠재적 문제점**:
- 동시 재배포 방지 로직이 있지만, DB 레벨 락은 없음

#### 4.2 설정값 백업 (381-392)
- 현재 모든 설정값 백업
- 롤백을 위한 준비

#### 4.3 상태 업데이트 (395-398)
- `endpoint.status = "deploying"` 설정
- DB 업데이트

#### 4.4 Kubernetes 리소스 삭제 (400-505)
- `deployer.delete_endpoint()` 호출
- 삭제 완료 확인 (최대 90초 대기)
- Terminating 상태 감지 및 대기
- 리소스가 존재하지만 Terminating이 아닌 경우 재삭제 시도

**잠재적 문제점**:
- 삭제가 완료되지 않으면 타임아웃 에러 발생
- 삭제 실패 시 재배포 진행 불가

#### 4.5 DeploymentSpec 결정 (445-530)
- 우선순위: 새 spec → 기존 spec → 재구성
- 재구성 시 기존 설정값 보존

**잠재적 문제점**:
- 재구성 로직이 복잡함
- `job_type`이 없으면 재구성 실패 가능

#### 4.6 Kubernetes 배포 (598-615)
- `deployer.deploy_endpoint()` 호출
- 배포 실패 시 백업 설정값 복원

**잠재적 문제점**:
- 배포 실패 시 롤백은 하지만, 에러는 여전히 발생

#### 4.7 DB 업데이트 (617-620)
- 배포 성공 후에만 DB 업데이트
- 새 설정값 저장

#### 4.8 상태 동기화 (623-637)
- Kubernetes에서 실제 상태 조회
- DB 상태 업데이트

### 5. 배포 레이어: deployer.py

**위치**: `backend/src/serving/services/deployer.py:71-...`

**함수**: `deploy_endpoint()`

**주요 단계**:

#### 5.1 리소스 존재 확인 (110-186)
- 리소스가 이미 존재하는지 확인
- 존재하면 삭제 및 완료 확인

**잠재적 문제점**:
- 삭제 확인 로직이 `redeploy_endpoint()`와 중복될 수 있음

#### 5.2 리소스 생성
- KServe 또는 일반 Deployment 생성
- HPA, Ingress, Service 생성

**잠재적 문제점**:
- 리소스 생성 실패 시 에러 발생
- 409 Conflict 발생 가능 (삭제가 완료되지 않은 경우)

## 문제점 분석

### 1. 삭제가 전혀 동작하지 않는 문제

**가능한 원인**:
1. **Kubernetes API 호출 실패**
   - 네트워크 문제
   - 인증/권한 문제
   - Kubernetes 클러스터 연결 문제

2. **삭제 API 호출이 실행되지 않음**
   - `delete_endpoint()`가 호출되지 않음
   - 예외가 발생했지만 처리되지 않음
   - 리소스 존재 확인 실패

3. **삭제 완료 확인 실패**
   - 리소스가 삭제되었지만 확인 로직이 실패
   - 타임아웃이 너무 짧음
   - 리소스 상태 확인 로직 오류

### 2. 재배포가 전혀 동작하지 않는 문제

**가능한 원인**:
1. **프론트엔드 요청 실패**
   - API 호출이 전송되지 않음
   - 네트워크 오류
   - CORS 문제

2. **백엔드 API 검증 실패**
   - `RedeployEndpointRequest` 스키마 검증 실패
   - 필수 필드 누락

3. **서비스 레이어 예외**
   - 엔드포인트 조회 실패
   - 모델 엔트리 조회 실패
   - 동시 재배포 방지 로직에서 에러

4. **Kubernetes 배포 실패**
   - 리소스 생성 실패
   - 409 Conflict (리소스가 아직 존재)
   - 권한 문제

## 디버깅 체크리스트

### 프론트엔드 확인
- [ ] 브라우저 콘솔에 에러가 있는가?
- [ ] 네트워크 탭에서 API 요청이 전송되는가?
- [ ] 요청 Body가 올바른가?
- [ ] 응답이 무엇인가? (status, message)

### 백엔드 API 확인
- [ ] API 엔드포인트가 호출되는가?
- [ ] `RedeployEndpointRequest` 검증이 통과하는가?
- [ ] `service.redeploy_endpoint()`가 호출되는가?
- [ ] 예외가 발생하는가? (어떤 예외인가?)

### 서비스 레이어 확인
- [ ] 엔드포인트가 조회되는가?
- [ ] 동시 재배포 방지 로직이 작동하는가?
- [ ] `deployer.delete_endpoint()`가 호출되는가?
- [ ] 삭제가 완료되는가?
- [ ] `deployer.deploy_endpoint()`가 호출되는가?
- [ ] 배포가 성공하는가?

### 배포 레이어 확인
- [ ] 리소스 존재 확인이 작동하는가?
- [ ] 삭제 API 호출이 실행되는가?
- [ ] 삭제 응답이 무엇인가?
- [ ] 리소스 생성 API 호출이 실행되는가?
- [ ] 생성 응답이 무엇인가?

### Kubernetes 확인
- [ ] 리소스가 실제로 존재하는가?
- [ ] 리소스가 삭제되고 있는가?
- [ ] 리소스가 생성되고 있는가?
- [ ] Pods가 시작되는가?

## 로그 확인 포인트

### 프론트엔드 로그
```
[브라우저 콘솔]
- "Redeploying endpoint..."
- "Redeploy failed: ..."
- Network request details
```

### 백엔드 로그
```
[API 레이어]
- "Redeploy endpoint request received"
- "RedeployEndpointRequest validation"

[서비스 레이어]
- "Starting redeployment for endpoint {id}"
- "Deleted existing Kubernetes resources for endpoint {id}"
- "Verified deletion of {resource_type} {name}"
- "Successfully deployed Kubernetes resources for endpoint {id}"
- "Redeployed serving endpoint {id}"
- "Failed to redeploy endpoint {id}"

[배포 레이어]
- "Checking if {resource_type} {name} exists"
- "Attempting to delete {resource_type} {name}"
- "Delete API call successful"
- "ApiException when deleting"
```

## 개선 사항 (2024년 12월 적용)

### 1. 로깅 강화 ✅
- ✅ 프론트엔드: 재배포 시작/완료, 요청 페이로드, 응답, 에러 상세 로깅
- ✅ 백엔드 API: 요청 수신, 요청 body, 서비스 메서드 호출 전후 로깅
- ✅ 서비스 레이어: 각 단계별 상세 로깅 (삭제 시작/완료, 배포 시작, 설정값 결정 등)
- ✅ 배포 레이어: 리소스 생성 전후 로깅, 409 Conflict 처리 로깅

### 2. 에러 처리 개선 ✅
- ✅ 백엔드 API: `ValueError`와 일반 `Exception` 구분하여 처리
- ✅ 명확한 에러 메시지 제공
- ✅ 프론트엔드: 에러 메시지 파싱 및 표시 개선

### 3. 409 Conflict 처리 강화 ✅
- ✅ 리소스 생성 전 최종 확인 로직 추가
- ✅ 409 Conflict 발생 시 자동 재시도 로직 추가
- ✅ 재시도 시 삭제 완료 확인 후 재생성
- ✅ 모든 리소스 생성 경로에 409 처리 적용

### 4. 코드 정리 및 리팩토링 ✅
- ✅ 공통 헬퍼 메서드 추가 (`_check_resource_exists`, `_ensure_resource_deleted`, `_handle_409_conflict`)
- ✅ 중복 코드 제거 (약 500줄 이상 감소)
- ✅ 코드 가독성 및 유지보수성 향상

### 5. 삭제 로직 개선 ✅
- ✅ `delete_endpoint()` 함수가 KServe 설정과 무관하게 모든 리소스 삭제
- ✅ 관련 리소스 삭제 로직 통합

## 다음 단계

1. 실제 로그 확인하여 어느 단계에서 실패하는지 파악
2. 각 단계별로 상세 로깅 추가 (완료)
3. 에러 처리 개선 (완료)
4. 사용자 피드백 개선 (프론트엔드) (완료)
5. 409 Conflict 재시도 로직 검증
6. 삭제 로직 완전성 검증

