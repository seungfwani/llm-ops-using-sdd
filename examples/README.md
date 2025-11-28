# LLM Ops Platform Examples

이 디렉토리에는 LLM Ops 플랫폼을 사용하는 다양한 예제 코드가 포함되어 있습니다.

## 목차

- [서빙 클라이언트 예제](#서빙-클라이언트-예제)
- [사용 방법](#사용-방법)
- [추가 예제](#추가-예제)

## 서빙 클라이언트 예제

### `serving_client.py`

서빙된 모델을 사용하는 Python 클라이언트 예제입니다.

**주요 기능:**
- 서빙 엔드포인트 배포
- 엔드포인트 목록 조회 및 필터링
- 엔드포인트 상태 확인 및 헬스 체크
- 엔드포인트 롤백
- 모델 추론 호출 (구현 예정)

**사용 예제:**

```bash
# 전체 워크플로우 예제 실행
python examples/serving_client.py workflow

# 엔드포인트 배포 및 상태 확인
python examples/serving_client.py deploy

# 엔드포인트 목록 조회
python examples/serving_client.py list

# 엔드포인트 롤백
python examples/serving_client.py rollback
```

**코드에서 직접 사용:**

```python
from examples.serving_client import ServingClient

# 클라이언트 생성
client = ServingClient(
    base_url="https://dev.llm-ops.local/llm-ops/v1",
    user_id="admin",
    user_roles="admin"
)

# 엔드포인트 배포
endpoint = client.deploy_endpoint(
    model_id="your-model-id",
    environment="dev",
    route="/llm-ops/v1/serve/my-model",
    min_replicas=1,
    max_replicas=3
)

# Healthy 상태 대기
client.wait_for_healthy(endpoint["id"])

# 헬스 체크
health = client.check_health("my-model")
print(f"Health: {health['status']}")
```

## 사용 방법

### 1. 환경 설정

예제를 실행하기 전에 필요한 패키지를 설치합니다:

```bash
cd backend
pip install requests  # 또는 poetry install
```

### 2. 환경 변수 설정

API 기본 URL과 인증 정보를 설정합니다:

```bash
export LLM_OPS_API_BASE_URL="https://dev.llm-ops.local/llm-ops/v1"
export LLM_OPS_USER_ID="your-user-id"
export LLM_OPS_USER_ROLES="admin,researcher"
```

또는 코드에서 직접 설정할 수 있습니다:

```python
client = ServingClient(
    base_url="https://dev.llm-ops.local/llm-ops/v1",
    user_id="your-user-id",
    user_roles="admin,researcher"
)
```

### 3. 예제 실행

```bash
# 전체 워크플로우 실행
python examples/serving_client.py workflow

# 특정 예제 실행
python examples/serving_client.py deploy
python examples/serving_client.py list
python examples/serving_client.py rollback
```

## 추가 예제

더 많은 예제와 사용 사례는 다음 문서를 참조하세요:

- [서빙 예제 가이드](../docs/serving-examples.md) - 서빙된 모델을 사용하는 다양한 예제
- [Quickstart 가이드](../specs/001-document-llm-ops/quickstart.md) - 플랫폼 설정 및 사용 가이드

## 주의 사항

1. **추론 API**: 모델 추론 호출 API (`call_chat_model` 등)는 현재 구현되어 있지 않습니다. PRD에 명시되어 있으나 아직 개발 중입니다.

2. **인증**: 모든 API 요청에는 `X-User-Id`와 `X-User-Roles` 헤더가 필요합니다.

3. **환경**: `dev`, `stg`, `prod` 환경에 따라 API 기본 URL이 달라집니다.

4. **에러 처리**: 모든 API 응답은 `{status, message, data}` 형식의 envelope을 사용합니다.

## 향후 계획

다음 예제들이 추가될 예정입니다:

- [ ] JavaScript/TypeScript 클라이언트 예제
- [ ] 모델 추론 호출 예제 (추론 API 구현 후)
- [ ] 프롬프트 A/B 테스트 예제
- [ ] 배치 추론 예제
- [ ] 모델 학습 예제
- [ ] 데이터셋 관리 예제

## 기여하기

새로운 예제를 추가하거나 기존 예제를 개선하고 싶다면:

1. 이 디렉토리에 새로운 예제 파일을 추가하세요
2. 이 README 파일에 예제 설명을 추가하세요
3. 필요한 경우 문서화를 업데이트하세요
