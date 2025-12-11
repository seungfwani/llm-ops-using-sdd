#!/usr/bin/env bash
#
# llm-ops-platform 전체 설치 스크립트
#
# 기능:
#   1) cert-manager 설치/검증 (CRD + 컨트롤러)
#   2) KServe CRD 설치/검증 (install-kserve-crds.sh 사용)
#   3) llm-ops-platform Helm dependency 업데이트
#   4) llm-ops-platform Helm upgrade --install
#
# 사용 예시:
#   ./deploy-llm-ops-platform.sh
#
# 환경 변수:
#   ENV / ENVIRONMENT / 첫 번째 인자(dev|stg|prod) 로 네임스페이스/릴리스 접두사 설정
#     - 예: dev → namespace=llm-ops-dev, release=llm-ops-platform-dev
#   RELEASE_NAME            (기본: llm-ops-platform, ENV가 주어지면 접미사 자동 부여)
#   NAMESPACE               (기본: llm-ops, ENV가 주어지면 llm-ops-<env>)
#   INSTALL_CRDS            (기본: true)    false 이면 KServe CRD 설치 스킵
#   KSERVE_VERSION          (기본: v0.16.0)
#   VALUES_FILE             (기본: 빈 값)   추가 values.yaml 지정 시 사용
#
#   INSTALL_CERT_MANAGER    (기본: true)    false 이면 cert-manager 설치 스킵
#   CERT_MANAGER_VERSION    (기본: v1.13.0)
#
#   CRD_SCRIPT              (기본: ./install-kserve-crds.sh)
#   CERT_MANAGER_SCRIPT     (기본: ./install-cert-manager.sh)
#
#   CHART_DIR               (기본: 이 스크립트가 있는 디렉터리)
#

set -euo pipefail

# ===== 기본 설정 =====
USER_SET_RELEASE="${RELEASE_NAME+yes}"
USER_SET_NAMESPACE="${NAMESPACE+yes}"

RELEASE_NAME="${RELEASE_NAME:-llm-ops-platform}"
NAMESPACE="${NAMESPACE:-llm-ops}"
INSTALL_CRDS="${INSTALL_CRDS:-true}"
KSERVE_VERSION="${KSERVE_VERSION:-v0.16.0}"
VALUES_FILE="${VALUES_FILE:-}"

INSTALL_CERT_MANAGER="${INSTALL_CERT_MANAGER:-true}"
CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.13.0}"
OVERRIDE_MINIO_BUCKET_WITH_NAMESPACE="${OVERRIDE_MINIO_BUCKET_WITH_NAMESPACE:-true}"

# 이 스크립트가 있는 디렉터리를 Chart 루트로 간주
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHART_DIR="${CHART_DIR:-${SCRIPT_DIR}}"

CRD_SCRIPT="${CRD_SCRIPT:-${CHART_DIR}/install-kserve-crds.sh}"
CERT_MANAGER_SCRIPT="${CERT_MANAGER_SCRIPT:-${CHART_DIR}/install-cert-manager.sh}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--help]

llm-ops-platform 전체 스택을 설치합니다.

순서:
  1) cert-manager 설치/검증 (선택)
  2) KServe CRD 설치 (선택)
  3) Helm dependency update
  4) Helm upgrade --install (llm-ops-platform)

환경 변수:
  RELEASE_NAME          Helm 릴리스 이름 (기본: ${RELEASE_NAME})
  NAMESPACE             설치 네임스페이스 (기본: ${NAMESPACE})

  INSTALL_CERT_MANAGER  cert-manager 설치 여부 (기본: ${INSTALL_CERT_MANAGER})
  CERT_MANAGER_VERSION  cert-manager 버전 (기본: ${CERT_MANAGER_VERSION})

  INSTALL_CRDS          KServe CRD 설치 여부 (기본: ${INSTALL_CRDS})
  KSERVE_VERSION        KServe 버전 (기본: ${KSERVE_VERSION})

  VALUES_FILE           추가 values.yaml 경로 (옵션)
  CHART_DIR             Chart 디렉터리 (기본: 이 스크립트 디렉터리)

예시:
  # 기본 값으로 설치
  $(basename "$0")

  # prod values 사용
  VALUES_FILE=./values-prod.yaml $(basename "$0")

  # cert-manager는 이미 있으니 스킵, KServe CRD도 스킵
  INSTALL_CERT_MANAGER=false INSTALL_CRDS=false $(basename "$0")
EOF
}

if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
  usage
  exit 0
fi

# ===== ENV로 namespace/release 자동 설정 =====
ENV_INPUT="${ENVIRONMENT:-${ENV:-${1:-}}}"
if [[ -n "${ENV_INPUT}" ]]; then
  env_norm="$(echo "${ENV_INPUT}" | tr '[:upper:]' '[:lower:]')"
  case "${env_norm}" in
    dev|development) env_norm="dev" ;;
    stg|stage|staging) env_norm="stg" ;;
    prod|production) env_norm="prod" ;;
    *) echo "⚠️  Unknown ENV '${ENV_INPUT}', using literal suffix";;
  esac
  if [[ "${USER_SET_NAMESPACE}" != "yes" ]]; then
    NAMESPACE="llm-ops-${env_norm}"
  fi
  if [[ "${USER_SET_RELEASE}" != "yes" ]]; then
    RELEASE_NAME="llm-ops-platform-${env_norm}"
  fi
fi

# ===== 사전 체크 =====
command -v helm >/dev/null 2>&1 || { echo "❌ helm not found in PATH"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found in PATH"; exit 1; }

echo ">>> Chart directory        : ${CHART_DIR}"
echo ">>> Release name           : ${RELEASE_NAME}"
echo ">>> Namespace              : ${NAMESPACE}"
echo ">>> Install cert-manager   : ${INSTALL_CERT_MANAGER} (version: ${CERT_MANAGER_VERSION})"
echo ">>> Install KServe CRDs    : ${INSTALL_CRDS} (version: ${KSERVE_VERSION})"
if [[ -n "${VALUES_FILE}" ]]; then
  echo ">>> Extra values file      : ${VALUES_FILE}"
fi

# ===== cert-manager 보장 =====
ensure_cert_manager() {
  if [[ "${INSTALL_CERT_MANAGER}" != "true" ]]; then
    echo ">>> Skipping cert-manager install (INSTALL_CERT_MANAGER=${INSTALL_CERT_MANAGER})"
    return 0
  fi

  echo ">>> Ensuring cert-manager is installed (force apply ${CERT_MANAGER_VERSION})..."

  # 1) 우선 스크립트가 있으면 스크립트로 설치/업그레이드
  if [[ -x "${CERT_MANAGER_SCRIPT}" ]]; then
    echo ">>> Using cert-manager script: ${CERT_MANAGER_SCRIPT}"
    CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION}" NAMESPACE="cert-manager" "${CERT_MANAGER_SCRIPT}"
  else
    # 2) 스크립트가 없으면 공식 manifest 직접 apply
    echo ">>> ${CERT_MANAGER_SCRIPT} not found; applying official cert-manager manifest directly"
    local cm_ns="cert-manager"
    kubectl get ns "${cm_ns}" >/dev/null 2>&1 || kubectl create namespace "${cm_ns}" >/dev/null 2>&1 || true

    local yaml_url="https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
    echo ">>> Applying ${yaml_url} ..."
    kubectl apply -f "${yaml_url}"

    echo ">>> Waiting for cert-manager deployments to be available..."
    for deploy in cert-manager cert-manager-webhook cert-manager-cainjector; do
      echo "   - Waiting for deployment/${deploy} in ${cm_ns} ..."
      kubectl wait --for=condition=available "deploy/${deploy}" -n "${cm_ns}" --timeout=180s >/dev/null 2>&1 || \
        echo "     ⚠️  Failed waiting for ${deploy} (check manually: kubectl get deploy -n ${cm_ns})"
    done
  fi

  # 3) v1 CRD들이 실제로 있는지 확인 (Certificate, Issuer)
  echo ">>> Verifying cert-manager CRDs (certificates.cert-manager.io, issuers.cert-manager.io)..."

  local missing=false

  if ! kubectl get crd certificates.cert-manager.io >/dev/null 2>&1; then
    echo "   ❌ CRD certificates.cert-manager.io not found"
    missing=true
  fi

  if ! kubectl get crd issuers.cert-manager.io >/dev/null 2>&1; then
    echo "   ❌ CRD issuers.cert-manager.io not found"
    missing=true
  fi

  if [[ "${missing}" == "true" ]]; then
    echo "   ❌ Required cert-manager CRDs are missing."
    echo "      - llm-ops-platform 차트 설치 전에 cert-manager 상태를 먼저 확인해주세요."
    echo "      - 예: kubectl get crd | grep cert-manager.io"
    exit 1
  fi

  echo "   ✅ cert-manager CRDs detected."
}

# ===== KServe CRD 설치 =====
install_crds() {
  if [[ "${INSTALL_CRDS}" != "true" ]]; then
    echo ">>> Skipping KServe CRD install (INSTALL_CRDS=${INSTALL_CRDS})"
    return 0
  fi

  echo ">>> Installing KServe CRDs (version: ${KSERVE_VERSION})..."

  if [[ -x "${CRD_SCRIPT}" ]]; then
    echo ">>> Using CRD script: ${CRD_SCRIPT}"
    KSERVE_VERSION="${KSERVE_VERSION}" "${CRD_SCRIPT}"
    return 0
  fi

  echo ">>> ${CRD_SCRIPT} not found; falling back to kserve-crd Helm chart"
  kubectl get ns kserve-system >/dev/null 2>&1 || kubectl create namespace kserve-system >/dev/null 2>&1 || true

  helm upgrade --install kserve-crd \
    oci://ghcr.io/kserve/charts/kserve-crd \
    --version "${KSERVE_VERSION}" \
    -n kserve-system --create-namespace

  echo ">>> Waiting for InferenceService CRD to be available..."
  for i in $(seq 1 20); do
    if kubectl get crd inferenceservices.serving.kserve.io >/dev/null 2>&1; then
      echo "   ✅ inferenceservices.serving.kserve.io CRD detected"
      return 0
    fi
    sleep 2
  done

  echo "⚠️  CRD not detected yet. Proceeding anyway, but Helm install may fail if CRDs are not ready."
}

# ===== Helm dependency 업데이트 =====
update_deps() {
  echo ">>> Updating Helm dependencies in ${CHART_DIR}..."
  helm dependency update "${CHART_DIR}"
}

# ===== llm-ops-platform 설치/업그레이드 =====
install_llm_ops_platform() {
  echo ">>> Installing/Upgrading Helm release ${RELEASE_NAME} in namespace ${NAMESPACE}..."

  kubectl get ns "${NAMESPACE}" >/dev/null 2>&1 || kubectl create namespace "${NAMESPACE}" >/dev/null 2>&1 || true

  # 이전 실패한 버킷 Job이 남아 있으면 훅이 재실행되지 않을 수 있으므로 삭제
  kubectl delete job minio-create-bucket -n "${NAMESPACE}" --ignore-not-found >/dev/null 2>&1 || true

  # 기본적으로 kserve.enabled / gpuPlugin.enabled 켜줌
  HELM_CMD=(
    helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}"
    -n "${NAMESPACE}"
    --create-namespace
    --set kserve.enabled=true
    --set gpuPlugin.enabled=true
  )

  if [[ "${OVERRIDE_MINIO_BUCKET_WITH_NAMESPACE}" == "true" ]]; then
    HELM_CMD+=( --set objectStore.bucket="${NAMESPACE}" )
  fi

  if [[ -n "${VALUES_FILE}" ]]; then
    HELM_CMD+=( -f "${VALUES_FILE}" )
  fi

  echo ">>> Running: ${HELM_CMD[*]}"
  "${HELM_CMD[@]}"

  echo "✅ Helm release ${RELEASE_NAME} deployed."
}

# ===== 실행 순서 =====
ensure_cert_manager
install_crds
update_deps
install_llm_ops_platform

echo
echo "✅ All done."
echo "   - Check release : helm status ${RELEASE_NAME} -n ${NAMESPACE}"
echo "   - Check CRDs    : kubectl get crd | grep -E 'kserve|cert-manager'"
echo "   - Check pods    : kubectl get pods -n ${NAMESPACE}"