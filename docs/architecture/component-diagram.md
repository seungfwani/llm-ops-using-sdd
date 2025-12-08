# Component Diagram: Open Source Integrations

플랫폼 컴포넌트와 외부 오픈소스 도구 간의 관계를 개략적으로 나타냅니다.

## 주요 컴포넌트

- **Backend Core**
  - `api` (FastAPI 라우트)
  - `services` (도메인 서비스)
  - `catalog`, `training`, `serving`, `workflows` 모듈
- **Integrations**
  - `integrations/experiment_tracking` → MLflow Tracking Server
  - `integrations/serving` → KServe / Ray Serve
  - `integrations/orchestration` → Argo Workflows
  - `integrations/registry` → Hugging Face Hub
  - `integrations/versioning` → DVC
- **Observability**
  - Prometheus ↔ `core/observability.py`, `integrations/observability.py`
  - Grafana 대시보드 (`infra/k8s/monitoring/grafana-dashboards.yaml`)

실제 다이어그램은 별도 도구(draw.io, Excalidraw 등)에서 관리하고, 이 문서는 구조와 책임을 텍스트로 정리합니다.

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