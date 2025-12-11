#!/usr/bin/env bash
# KServe CRD 설치 스크립트 (Helm kserve-crd 차트 + 기존 CRD 감지)
#
# 기본 동작:
#   - 클러스터에 이미 KServe CRD가 있으면 Helm 설치를 스킵한다.
#   - KServe CRD가 없으면 kserve-crd Helm 차트(OCI)로 설치한다.
#
# 옵션 (위험!):
#   - FORCE_CRD_REINSTALL=true 로 실행하면,
#     1) 기존 KServe CRD들을 삭제하고
#     2) kserve-crd Helm 차트로 다시 설치한다.
#
# 사용 예시:
#   ./install-kserve-crds.sh
#   KSERVE_VERSION=v0.16.0 ./install-kserve-crds.sh
#   FORCE_CRD_REINSTALL=true ./install-kserve-crds.sh
#
# 환경 변수:
#   KSERVE_VERSION       KServe 버전 (기본: v0.16.0, 'v' 없어도 자동 보정)
#   RELEASE_NAME         kserve-crd Helm 릴리스 이름 (기본: kserve-crd)
#   NAMESPACE            설치 네임스페이스 (기본: kserve-system)
#   DRY_RUN              "true" 이면 실제 설치 대신 helm template만 실행 (기본: false)
#   FORCE_CRD_REINSTALL  "true" 이면 기존 KServe CRD들을 삭제 후 재설치 (기본: false)

set -euo pipefail

# ===== 버전/환경 변수 보정 =====
KSERVE_VERSION_RAW="${KSERVE_VERSION:-v0.16.0}"
if [[ "${KSERVE_VERSION_RAW}" == v* ]]; then
  KSERVE_VERSION="${KSERVE_VERSION_RAW}"
else
  KSERVE_VERSION="v${KSERVE_VERSION_RAW}"
fi

RELEASE_NAME="${RELEASE_NAME:-kserve-crd}"
NAMESPACE="${NAMESPACE:-kserve-system}"
DRY_RUN="${DRY_RUN:-false}"
FORCE_CRD_REINSTALL="${FORCE_CRD_REINSTALL:-false}"

KSERVE_CRD_CHART="${KSERVE_CRD_CHART:-oci://ghcr.io/kserve/charts/kserve-crd}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--help]

KServe CRD를 다음 로직으로 설치합니다.

  1) 클러스터에서 KServe CRD 존재 여부 확인
  2) 이미 있으면:
       - FORCE_CRD_REINSTALL!=true : Helm 설치 스킵
       - FORCE_CRD_REINSTALL=true  : 기존 CRD 삭제 후 Helm으로 재설치
  3) 없으면:
       - Helm kserve-crd 차트로 설치

환경 변수:
  KSERVE_VERSION       KServe 버전 (기본: ${KSERVE_VERSION})
  RELEASE_NAME         Helm 릴리스 이름 (기본: ${RELEASE_NAME})
  NAMESPACE            설치 네임스페이스 (기본: ${NAMESPACE})
  DRY_RUN              "true" 이면 template만 출력 (기본: ${DRY_RUN})
  FORCE_CRD_REINSTALL  "true" 이면 기존 KServe CRD 삭제 후 재설치 (기본: ${FORCE_CRD_REINSTALL})

예시:
  # 기본 값으로 설치 (이미 CRD 있으면 스킵)
  $(basename "$0")

  # 다른 버전 사용
  KSERVE_VERSION=0.16.0 $(basename "$0")

  # 기존 CRD 무시하고 강제로 재설치 (⚠️ InferenceService 등 모두 삭제될 수 있음)
  FORCE_CRD_REINSTALL=true $(basename "$0")
EOF
}

if [[ "${1:-}" =~ ^(-h|--help)$ ]]; then
  usage
  exit 0
fi

# ===== 사전 조건 체크 =====
command -v helm >/dev/null 2>&1 || { echo "❌ helm not found in PATH"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "❌ kubectl not found in PATH"; exit 1; }

echo ">>> KServe CRD install script"
echo "    - Chart           : ${KSERVE_CRD_CHART}"
echo "    - Version         : ${KSERVE_VERSION}"
echo "    - Release         : ${RELEASE_NAME}"
echo "    - Namespace       : ${NAMESPACE}"
echo "    - Dry-run         : ${DRY_RUN}"
echo "    - Force reinstall : ${FORCE_CRD_REINSTALL}"

# ===== 현재 클러스터에 KServe CRD 존재 여부 확인 =====
echo ">>> Checking existing KServe CRDs (group=serving.kserve.io)..."
EXISTING_KSERVE_CRDS="$(kubectl get crd -o name 2>/dev/null | grep 'serving.kserve.io' || true)"

if [[ -n "${EXISTING_KSERVE_CRDS}" ]]; then
  echo "    Detected existing KServe CRDs:"
  echo "${EXISTING_KSERVE_CRDS}" | sed 's/^/      - /'

  if [[ "${FORCE_CRD_REINSTALL}" != "true" ]]; then
    echo
    echo ">>> KServe CRDs already exist. Not installing via Helm to avoid ownership conflict."
    echo "    - 이 상태에서는 CRD들이 Helm 릴리스에 소속되어 있지 않습니다."
    echo "    - 만약 Helm 릴리스로 재관리하고 싶다면:"
    echo "        FORCE_CRD_REINSTALL=true $(basename "$0")"
    echo "      로 실행해 CRD를 삭제 후 재설치할 수 있습니다. (⚠️ 주의!)"
    exit 0
  fi

  echo
  echo "⚠️  FORCE_CRD_REINSTALL=true 설정됨: 기존 KServe CRD들을 삭제하고 재설치합니다."
  echo "    이 작업은 해당 CRD에 속한 모든 커스텀 리소스(InferenceService 등)를 삭제할 수 있습니다."
  echo "    5초 후 계속 진행합니다. 중단하려면 Ctrl+C 를 누르세요..."
  sleep 5

  echo ">>> Deleting existing KServe CRDs..."
  # 안전하게 한 줄씩 삭제
  while read -r crd; do
    [[ -z "${crd}" ]] && continue
    echo "    Deleting ${crd}..."
    kubectl delete "${crd}" || true
  done <<< "${EXISTING_KSERVE_CRDS}"

  echo ">>> Waiting a bit for CRD deletions to propagate..."
  sleep 5
else
  echo "    No existing KServe CRDs found."
fi

# ===== Helm 버전 간단 체크 (OCI 지원 경고 용도) =====
HELM_MAJOR_MINOR="$(helm version --short 2>/dev/null | sed -E 's/^v([0-9]+\.[0-9]+).*/\1/')"
HELM_MAJOR="${HELM_MAJOR_MINOR%%.*}"
HELM_MINOR="${HELM_MAJOR_MINOR#*.}"

if [[ -n "${HELM_MAJOR_MINOR}" ]]; then
  if (( HELM_MAJOR < 3 )) || (( HELM_MAJOR == 3 && HELM_MINOR < 8 )); then
    echo "⚠️  Helm ${HELM_MAJOR_MINOR} detected. OCI 기반 차트 사용을 위해 Helm 3.8+ 권장."
  fi
fi

# 네임스페이스 생성 (없으면)
if ! kubectl get ns "${NAMESPACE}" >/dev/null 2>&1; then
  echo ">>> Creating namespace ${NAMESPACE}..."
  kubectl create namespace "${NAMESPACE}" >/dev/null 2>&1 || true
fi

# ===== DRY-RUN 모드 =====
if [[ "${DRY_RUN}" == "true" ]]; then
  echo ">>> DRY_RUN=true: Helm template 출력만 수행합니다. 실제 설치는 하지 않습니다."
  helm template "${RELEASE_NAME}" "${KSERVE_CRD_CHART}" \
    --version "${KSERVE_VERSION}" \
    -n "${NAMESPACE}"
  exit 0
fi

# ===== Helm 설치/업그레이드 =====
echo ">>> Installing KServe CRDs with Helm..."
echo "    helm upgrade --install ${RELEASE_NAME} ${KSERVE_CRD_CHART} --version ${KSERVE_VERSION} -n ${NAMESPACE} --create-namespace"

helm upgrade --install "${RELEASE_NAME}" "${KSERVE_CRD_CHART}" \
  --version "${KSERVE_VERSION}" \
  -n "${NAMESPACE}" \
  --create-namespace

echo ">>> Waiting for InferenceService CRD to be ready..."

SUCCESS=false
for i in $(seq 1 30); do
  if kubectl get crd inferenceservices.serving.kserve.io >/dev/null 2>&1; then
    SUCCESS=true
    break
  fi
  sleep 2
done

if [[ "${SUCCESS}" == "true" ]]; then
  echo "   ✅ CRD inferenceservices.serving.kserve.io detected."

  echo ">>> Checking api-resources for serving.kserve.io group..."
  if kubectl api-resources --api-group=serving.kserve.io >/dev/null 2>&1; then
    echo "   ✅ API group serving.kserve.io is available."
  else
    echo "   ⚠️  API group serving.kserve.io 가 아직 api-resources에 안 보입니다."
    echo "      (apiserver 캐시 반영까지 약간 딜레이가 있을 수 있음)"
  fi
else
  echo "   ⚠️  inferenceservices.serving.kserve.io CRD를 아직 찾지 못했습니다."
  echo "      'kubectl get crd | grep kserve' 로 수동 확인해보세요."
fi

echo
echo "✅ Done."
echo "   - Helm release : helm status ${RELEASE_NAME} -n ${NAMESPACE}"
echo "   - CRDs         : kubectl get crd | grep kserve"
echo "   - API group    : kubectl api-resources --api-group=serving.kserve.io"