# Integration Troubleshooting Guide

## 공통 점검 체크리스트

1. `/llm-ops/v1/health/integrations` 엔드포인트로 통합 상태 확인
2. Prometheus / Grafana 대시보드에서 관련 메트릭 확인
3. Kubernetes에서 Pod 상태 및 로그 확인 (`kubectl get pods`, `kubectl logs`)

## MLflow 문제 해결

- 증상: 실험이 생성되지 않음, UI에서 run이 보이지 않음  
- 체크사항:
  - `MLFLOW_TRACKING_URI`, `MLFLOW_BACKEND_STORE_URI` 환경변수 확인
  - `mlflow` 네임스페이스의 Pod/Service 상태 확인
  - 백엔드 로그에서 `MLflowAdapter` 에러 확인

## KServe 문제 해결

- 증상: 배포 상태가 `deploying` 에서 벗어나지 않음  
- 체크사항:
  - `USE_KSERVE=true`, `SERVING_FRAMEWORK_ENABLED=true` 설정 확인
  - InferenceService 리소스 상태 확인: `kubectl describe inferenceservice`
  - Predictor Pod 로그 확인

## Argo Workflows 문제 해결

- 증상: 파이프라인이 생성되지 않음, 상태가 Unknown  
- 체크사항:
  - `ARGO_WORKFLOWS_ENABLED=true` 설정 확인
  - `argo` 네임스페이스의 컨트롤러/서버 Pod 상태 확인
  - Workflow 리소스 조회 및 로그 확인

## DVC 문제 해결

- 증상: 데이터셋 버전 생성 실패, diff 계산 실패  
- 체크사항:
  - `DVC_ENABLED=true`, `DVC_REMOTE_URL` 설정 확인
  - DVC CLI에서 remote 접근 테스트
  - 백엔드 로그에서 `DVCAdapter` 에러 확인

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