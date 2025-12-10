#!/bin/bash
# NVIDIA Device Plugin 설치 및 time-slicing 설정 스크립트
# Usage:
#   ./setup-nvidia-device-plugin.sh [replicas]
#   REPLICAS=<int> NAMESPACE=<ns> CHART_VERSION=<ver> ./setup-nvidia-device-plugin.sh
#
# 기본값:
#   replicas: 4          # 1개의 물리 GPU를 4개의 time-slice로 노출
#   namespace: kube-system
#   chart version: 0.15.0 (time-slicing 지원 버전 권장)

set -euo pipefail

REPLICAS="${1:-${REPLICAS:-4}}"
NAMESPACE="${NAMESPACE:-kube-system}"
RELEASE_NAME="${RELEASE_NAME:-nvidia-device-plugin}"
CHART_VERSION="${CHART_VERSION:-0.15.0}"
CONFIGMAP_NAME="${CONFIGMAP_NAME:-nvidia-device-plugin-config}"

echo "🚀 NVIDIA Device Plugin time-slicing 설정"
echo "   Namespace      : ${NAMESPACE}"
echo "   Replicas (slice): ${REPLICAS}"
echo "   Helm release   : ${RELEASE_NAME}"
echo "   Chart version  : ${CHART_VERSION}"
echo ""

# -----------------------------------------------------------------------------
# Prerequisites
# -----------------------------------------------------------------------------
if ! command -v kubectl >/dev/null 2>&1; then
    echo "❌ kubectl 이 필요합니다."
    exit 1
fi

if ! command -v helm >/dev/null 2>&1; then
    echo "❌ helm 이 필요합니다."
    exit 1
fi

if ! [[ "${REPLICAS}" =~ ^[0-9]+$ ]] || [ "${REPLICAS}" -lt 1 ]; then
    echo "❌ replicas 값은 1 이상의 정수여야 합니다."
    exit 1
fi

# -----------------------------------------------------------------------------
# Helm repo 준비
# -----------------------------------------------------------------------------
if ! helm repo list | grep -q "^nvidia[[:space:]]"; then
    echo "📦 Helm repo 추가: nvidia"
    helm repo add nvidia https://nvidia.github.io/k8s-device-plugin >/dev/null
fi
echo "🔄 Helm repo 업데이트"
helm repo update nvidia >/dev/null || helm repo update >/dev/null

# -----------------------------------------------------------------------------
# values 파일 생성 (ConfigMap + time-slicing)
# -----------------------------------------------------------------------------
VALUES_FILE="$(mktemp)"
cat > "${VALUES_FILE}" <<EOF
args:
  - --fail-on-init-error=false
  - --config-file=/config/config.yaml
config:
  map:
    name: ${CONFIGMAP_NAME}
    data:
      config.yaml: |
        version: v1
        sharing:
          timeSlicing:
            resources:
              - name: nvidia.com/gpu
                replicas: ${REPLICAS}
EOF

echo "🛠️  Helm upgrade --install 실행 중..."
helm upgrade --install "${RELEASE_NAME}" nvidia/nvidia-device-plugin \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --version "${CHART_VERSION}" \
  -f "${VALUES_FILE}"

rm -f "${VALUES_FILE}"

echo ""
echo "⏳ DaemonSet 준비 상태 확인..."
kubectl rollout status daemonset/nvidia-device-plugin-daemonset \
  -n "${NAMESPACE}" --timeout=180s || true

echo ""
echo "🔍 할당 가능한 GPU 슬라이스 수 확인:"
kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu 2>/dev/null || true
echo ""
echo "✅ 완료! 파드는 'nvidia.com/gpu: 1' 요청으로 time-slice를 할당받습니다."

