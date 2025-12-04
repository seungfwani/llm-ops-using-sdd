# Topology Diagram: Kubernetes Deployment

## Namespaces

- `llm-ops-dev` : LLM Ops Backend, Frontend, supporting services (PostgreSQL, Redis, MinIO 등)
- `mlflow` : MLflow Tracking Server (`infra/k8s/mlflow/*.yaml`)
- `kserve-system` / `kserve` : KServe 컨트롤러 및 InferenceService 리소스
- `argo` : Argo Workflows 컨트롤러 및 Workflow 리소스
- `monitoring` : Prometheus, Grafana, Alertmanager

## 네트워크

- Ingress / LoadBalancer → LLM Ops API / Frontend 서비스
- LLM Ops Backend ↔ MLflow / KServe / Argo / MinIO / PostgreSQL

## Observability

- 모든 컴포넌트는 Prometheus로 메트릭을 노출하고, Grafana 대시보드에서 시각화됩니다.

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