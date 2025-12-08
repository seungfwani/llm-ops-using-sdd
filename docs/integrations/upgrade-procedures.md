# Open Source Tool Upgrade Procedures

## 공통 원칙

- 모든 툴(MLflow, KServe, Argo Workflows, Hugging Face Hub, DVC)은 **어댑터 패턴**으로 감싸져 있으므로, 가능한 한 어댑터 레이어를 기준으로 호환성을 검증합니다.
- 프로덕션 적용 전 **dev → stg → prod** 순서로 점진적 롤아웃을 수행합니다.
- 업그레이드 과정에서 항상 **feature flag**를 사용하여 빠른 롤백이 가능하도록 합니다.

## MLflow 업그레이드

1. 새 버전의 MLflow 이미지를 staging 클러스터에 배포
2. `MLFLOW_TRACKING_URI`, `MLFLOW_BACKEND_STORE_URI` 호환성 확인
3. 샘플 학습 작업을 실행하여 메트릭/아티팩트 기록 및 UI 동작 확인
4. 문제가 없으면 prod 환경에도 동일 버전 적용

## KServe 업그레이드

1. KServe 릴리스 노트를 검토하여 InferenceService CRD 변경사항 확인
2. staging 클러스터에 새 KServe 매니페스트 적용
3. 테스트 엔드포인트를 배포하고 상태/오토스케일링 동작 확인
4. `KServeAdapter`에서 사용하는 API 버전/필드를 재검토 후 필요 시 어댑터 수정

## Argo Workflows 업그레이드

1. 컨트롤러/서버 이미지를 staging에 먼저 배포
2. 기존 Workflow 정의가 새 버전에서도 그대로 실행되는지 확인
3. 실패/재시도/취소 플로우를 실제로 실행해 보고 상태 매핑이 올바른지 검증

## DVC 업그레이드

1. Python 패키지 버전을 개발 환경에서 먼저 올린 뒤 `DVCAdapter`와 CLI 동작을 확인
2. 원격 스토리지(S3/MinIO)와의 호환성 및 메타데이터 포맷이 유지되는지 확인
3. `create_version`, `calculate_diff`, `restore_version` 플로우를 샘플 데이터셋으로 검증

## 롤백 전략

- 문제가 발생하면 다음 순서로 롤백을 수행합니다.
  1. `.env`에서 통합 feature flag를 비활성화 (`*_ENABLED=false`)
  2. `backend/scripts/rollback_integrations.py` 실행(선택)으로 KServe 리소스 정리
  3. 이전 버전의 도커 이미지/매니페스트를 다시 배포


