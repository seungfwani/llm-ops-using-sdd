#!/usr/bin/env bash
# cert-manager 설치 스크립트
#
# - 공식 cert-manager YAML(manifest)로 설치
# - CRD 포함
# - 기본 버전: v1.13.0 (필요시 환경변수로 override)
#
# 사용 예:
#   ./install-cert-manager.sh
#   CERT_MANAGER_VERSION=v1.14.0 ./install-cert-manager.sh

set -euo pipefail

CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.13.0}"
NAMESPACE="${NAMESPACE:-cert-manager}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--help]

cert-manager CRD + 컨트롤러를 설치합니다.
(공식 GitHub 릴리스의 cert-manager.yaml 사용)

환경 변수:
  CERT_MANAGER_VERSION   기본: ${CERT_MANAGER_VERSION}
  NAMESPACE              기본: ${NAMESPACE}

예시:
  $(basename "$0")
  CERT_MANAGER_VERSION=v1.14.0 $(basename "$0")
EOF
}

if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
  usage
  exit 0
fi

command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found in PATH"; exit 1; }

echo ">>> Installing cert-manager"
echo "    - Version   : ${CERT_MANAGER_VERSION}"
echo "    - Namespace : ${NAMESPACE}"

# 네임스페이스 생성
if ! kubectl get ns "${NAMESPACE}" >/dev/null 2>&1; then
  echo ">>> Creating namespace ${NAMESPACE}..."
  kubectl create namespace "${NAMESPACE}" >/dev/null 2>&1 || true
fi

# 이미 CRD가 있으면 스킵할지 말지 간단히 보여주기
EXISTING_CM_CRDS="$(kubectl get crd -o name 2>/dev/null | grep 'cert-manager.io' || true)"
if [[ -n "${EXISTING_CM_CRDS}" ]]; then
  echo ">>> Detected existing cert-manager CRDs:"
  echo "${EXISTING_CM_CRDS}" | sed 's/^/      - /'
  echo ">>> cert-manager를 다시 적용합니다 (기존 CRD와 리소스는 유지)."
fi

YAML_URL="https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"

echo ">>> Applying ${YAML_URL} ..."
kubectl apply -f "${YAML_URL}"

echo ">>> Waiting for cert-manager deployments to be available..."

for deploy in cert-manager cert-manager-webhook cert-manager-cainjector; do
  echo "   - Waiting for deployment/${deploy} in ${NAMESPACE} ..."
  kubectl wait --for=condition=available "deploy/${deploy}" -n "${NAMESPACE}" --timeout=180s >/dev/null 2>&1 || \
    echo "     ⚠️  Failed waiting for ${deploy} (check manually: kubectl get deploy -n ${NAMESPACE})"
done

echo
echo "✅ cert-manager installation done."
echo "   - Check CRDs  : kubectl get crd | grep cert-manager.io"
echo "   - Check pods  : kubectl get pods -n ${NAMESPACE}"