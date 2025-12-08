# Data Flow Diagram: Integration Requests

## 1. Experiment Tracking 플로우

1. 클라이언트 → `/llm-ops/v1/training/jobs` (학습 작업 제출)
2. `TrainingJobService`가 작업 레코드 생성
3. 작업 실행 중, 컨테이너가 `/llm-ops/v1/training/jobs/{id}/experiment-run/...` 로 메트릭 전송
4. `ExperimentTrackingService` → `MLflowAdapter` → MLflow Tracking Server
5. UI에서는 ExperimentDetail/ExperimentSearch를 통해 MLflow run으로 링크

## 2. Serving 플로우 (KServe)

1. 클라이언트 → `/llm-ops/v1/serving/endpoints` (배포 요청)
2. `ServingService` → `ServingDeploymentService` → `KServeAdapter.deploy`
3. Kubernetes 상에 InferenceService 생성
4. 상태 조회 시 `/llm-ops/v1/serving/endpoints/{id}/deployment` → `KServeAdapter.get_deployment_status`

## 3. Workflow / Registry / Data Versioning

각각 `ArgoWorkflowsAdapter`, `HuggingFaceAdapter`, `DVCAdapter`를 통해 요청이 외부 시스템으로 위임되며,\n결과 메타데이터는 `workflow_pipelines`, `registry_models`, `dataset_versions` 테이블에 저장됩니다.

{
  "cells": [],
  "metadata": {
    "language_info": {
      "name": "python"
    }
  },
  "nbformat": 4,
  "nbformat_minor": 2
}