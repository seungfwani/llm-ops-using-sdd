# Legacy Implementation Cleanup Plan

이 문서는 오픈소스 통합 도입 이후 제거 대상이 되는 기존 커스텀 구현을 식별하기 위한 참고용 문서입니다.

## 대상 영역

- Experiment Tracking
  - 기존 DB 기반 메트릭 저장(`ExperimentMetric` 등)은 유지하되, 신규 플로우는 MLflow 중심으로 전환
  - 중복되는 커스텀 실험 조회 로직은 `ExperimentRun` + MLflow 검색 기반으로 단계적 정리

- Serving
  - 직접 Deployment/Service/HPA를 구성하는 커스텀 서빙 로직은 KServe/Ray Serve 어댑터로 대체
  - 롤백/그레이스풀 디그레이션용 최소한의 경로만 남기고, 중복 배포 코드 제거

- Workflows
  - 기존 단순 Job 기반 스케줄링 로직은 Argo Workflows 파이프라인으로 마이그레이션
  - 단일 스텝 Job만 필요한 경우에 한해 레거시 경로 유지

- Model Registry / Data Versioning
  - 내부 전용 모델/데이터 버전 관리 코드 중 Hugging Face Hub / DVC로 완전히 대체 가능한 부분 정리
  - 사용자 워크플로우에 영향을 주지 않는 범위에서 점진적 제거

## 진행 원칙

1. `/llm-ops/v1` API 계약을 깨지 않는다.
2. feature flag를 통해 언제든지 기존 경로로 롤백 가능하도록 유지한다.
3. 각 영역별로 레거시 구현을 제거하기 전에, 통합 테스트 및 운영 지표를 통해 안정성을 검증한다.


