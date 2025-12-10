#!/usr/bin/env bash
# KServe CRD 사전 설치 스크립트
# Usage:
#   ./install-kserve-crds.sh             # CRD 다운로드 후 즉시 적용
#   KSERVE_VERSION=0.16.0 ./install-kserve-crds.sh
#   KSERVE_CHART=oci://ghcr.io/kserve/charts/kserve ./install-kserve-crds.sh
#
# 동작:
# - Helm OCI 차트에서 CRD를 추출(helm show crds)해 kubectl apply로 설치합니다.
# - Helm 3.8+ 기준. 더 낮은 버전이면 HELM_EXPERIMENTAL_OCI=1 을 수동 설정하세요.

set -euo pipefail

KSERVE_CHART="${KSERVE_CHART:-oci://ghcr.io/kserve/charts/kserve}"
KSERVE_VERSION="${KSERVE_VERSION:-0.16.0}"

command -v helm >/dev/null 2>&1 || { echo "helm not found in PATH"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found in PATH"; exit 1; }

echo ">>> Installing KServe CRDs from ${KSERVE_CHART} (version: ${KSERVE_VERSION})"

if ! helm show crds "${KSERVE_CHART}" --version "${KSERVE_VERSION}" | kubectl apply -f -; then
  echo "Failed to install CRDs from ${KSERVE_CHART} ${KSERVE_VERSION}"
  exit 1
fi

echo ">>> Done. Verify with: kubectl get crd | grep kserve"

