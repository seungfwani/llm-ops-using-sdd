# Integration API Overview

이 문서는 open-source 통합과 관련된 `/llm-ops/v1` 엔드포인트를 요약합니다.

## Health

- `GET /llm-ops/v1/health/integrations`
  - **설명**: MLflow, KServe, Argo, DVC 등 통합 상태를 통합적으로 조회
  - **Response**: `{ status, message, data: { overall_status, integrations, checked_at } }`

## Experiment Tracking

- `GET /llm-ops/v1/training/jobs/{jobId}/experiment-run`
- `POST /llm-ops/v1/training/jobs/{jobId}/experiment-run`
- `POST /llm-ops/v1/training/jobs/{jobId}/experiment-run/metrics`
- `POST /llm-ops/v1/experiments/search`

## Serving

- `GET /llm-ops/v1/serving/endpoints/{endpointId}/deployment`
- `PATCH /llm-ops/v1/serving/endpoints/{endpointId}/deployment`
- `GET /llm-ops/v1/serving/frameworks`

## Workflows

- `POST /llm-ops/v1/workflows/pipelines`
- `GET /llm-ops/v1/workflows/pipelines/{pipelineId}`
- `DELETE /llm-ops/v1/workflows/pipelines/{pipelineId}`

## Model Registry

- `POST /llm-ops/v1/catalog/models/import`
- `POST /llm-ops/v1/catalog/models/{modelId}/export`
- `GET /llm-ops/v1/catalog/models/{modelId}/registry-links`
- `POST /llm-ops/v1/catalog/models/{modelId}/check-updates`

## Data Versioning

- `POST /llm-ops/v1/catalog/datasets/{datasetId}/versions`
- `GET /llm-ops/v1/catalog/datasets/{datasetId}/versions`
- `GET /llm-ops/v1/catalog/datasets/{datasetId}/versions/{versionId}/diff`
- `POST /llm-ops/v1/catalog/datasets/{datasetId}/versions/{versionId}/restore`

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