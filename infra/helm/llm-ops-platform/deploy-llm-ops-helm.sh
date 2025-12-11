#!/usr/bin/env bash
#
# llm-ops-platform + KServe + NVIDIA Device Plugin (time-slicing) 일괄 배포 스크립트
#

set -euo pipefail

# ===== 환경 설정 =====
ENVIRONMENT="${1:-dev}"                 # dev | stg | prod ...
KSERVE_VERSION="${KSERVE_VERSION:-v0.16.0}"

# KServe deployment mode: RawDeployment | Serverless
KSERVE_DEPLOYMENT_MODE="${KSERVE_DEPLOYMENT_MODE:-RawDeployment}"
# KServe ingress TLS on/off (default: off to avoid HTTPS mismatch)
KSERVE_TLS_ENABLED="${KSERVE_TLS_ENABLED:-false}"

# cert-manager 설치 여부
INSTALL_CERT_MANAGER="${INSTALL_CERT_MANAGER:-true}"
CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.13.0}"

# llm-ops-platform 네임스페이스 / 릴리스명
NAMESPACE="${NAMESPACE:-llm-ops-${ENVIRONMENT}}"
RELEASE_NAME="${RELEASE_NAME:-llm-ops-platform-${ENVIRONMENT}}"

# NVIDIA Device Plugin 설정 (setup-nvidia-device-plugin.sh 로직 기반)
NVDP_REPLICAS="${NVDP_REPLICAS:-4}"                     # 1 physical GPU -> 4 time-slices
NVDP_NAMESPACE="${NVDP_NAMESPACE:-kube-system}"
NVDP_RELEASE_NAME="${NVDP_RELEASE_NAME:-nvidia-device-plugin}"
NVDP_CHART_VERSION="${NVDP_CHART_VERSION:-0.15.0}"
NVDP_CONFIGMAP_NAME="${NVDP_CONFIGMAP_NAME:-nvidia-device-plugin-config}"

# 스크립트 / 차트 경로
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${SCRIPT_DIR}/Chart.yaml" ]]; then
  CHART_DIR="${SCRIPT_DIR}"
elif [[ -f "${SCRIPT_DIR}/../chart/Chart.yaml" ]]; then
  CHART_DIR="${SCRIPT_DIR}/../chart"
else
  echo "❌ Chart.yaml 을 찾지 못했습니다."
  exit 1
fi

echo
echo ">>> ENVIRONMENT            : ${ENVIRONMENT}"
echo ">>> NAMESPACE              : ${NAMESPACE}"
echo ">>> RELEASE_NAME           : ${RELEASE_NAME}"
echo ">>> CHART_DIR              : ${CHART_DIR}"
echo ">>> KSERVE_VERSION         : ${KSERVE_VERSION}"
echo ">>> KSERVE_DEPLOYMENT_MODE : ${KSERVE_DEPLOYMENT_MODE}"
echo ">>> INSTALL_CERT_MANAGER   : ${INSTALL_CERT_MANAGER}"
echo ">>> NVDP_NAMESPACE         : ${NVDP_NAMESPACE}"
echo ">>> NVDP_REPLICAS          : ${NVDP_REPLICAS}"
echo ">>> NVDP_CHART_VERSION     : ${NVDP_CHART_VERSION}"
echo

# ===== 전제 조건 체크 =====
if ! command -v kubectl >/dev/null 2>&1; then
  echo "❌ kubectl 이 필요합니다."
  exit 1
fi

if ! command -v helm >/dev/null 2>&1; then
  echo "❌ helm 이 필요합니다."
  exit 1
fi

# ===== 네임스페이스 생성 (llm-ops용) =====
if ! kubectl get ns "${NAMESPACE}" >/dev/null 2>&1; then
  echo ">>> Creating namespace: ${NAMESPACE}"
  kubectl create namespace "${NAMESPACE}"
else
  echo ">>> Namespace already exists: ${NAMESPACE}"
fi

# ===== cert-manager 설치/검증 =====
ensure_cert_manager() {
  if [[ "${INSTALL_CERT_MANAGER}" != "true" ]]; then
    echo ">>> Skipping cert-manager install"
    return 0
  fi

  echo ">>> Ensuring cert-manager ..."

  if kubectl get crd | grep -q "cert-manager.io"; then
    echo "   - cert-manager CRDs already exist."
  else
    local yaml_url="https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
    echo "   - Installing cert-manager: ${yaml_url}"
    kubectl apply -f "${yaml_url}"
  fi

  echo ">>> Waiting for cert-manager deployments to be available..."
  for deploy in cert-manager cert-manager-webhook cert-manager-cainjector; do
    kubectl wait --for=condition=available "deployment/${deploy}" \
      -n cert-manager --timeout=180s || true
  done
}

# ===== KServe CRD 설치 =====
ensure_kserve_crds() {
  echo ">>> Ensuring KServe CRDs ..."

  if kubectl get crd inferenceservices.serving.kserve.io >/dev/null 2>&1; then
    echo "   - KServe CRDs already exist."
    return 0
  fi

  echo "   - Installing kserve-crd via Helm ..."
  helm upgrade --install kserve-crd oci://ghcr.io/kserve/charts/kserve-crd \
    --version "${KSERVE_VERSION}" \
    -n kserve-system \
    --create-namespace

  kubectl get crd inferenceservices.serving.kserve.io
}

# ===== NVIDIA Device Plugin 설치 (time-slicing 포함) =====
install_nvidia_device_plugin() {
  echo "🚀 NVIDIA Device Plugin time-slicing 설정"
  echo "   Namespace       : ${NVDP_NAMESPACE}"
  echo "   Replicas(slice) : ${NVDP_REPLICAS}"
  echo "   Helm release    : ${NVDP_RELEASE_NAME}"
  echo "   Chart version   : ${NVDP_CHART_VERSION}"
  echo

  # replicas 유효성 체크
  if ! [[ "${NVDP_REPLICAS}" =~ ^[0-9]+$ ]] || [ "${NVDP_REPLICAS}" -lt 1 ]; then
    echo "❌ NVDP_REPLICAS 값은 1 이상의 정수여야 합니다. (현재: ${NVDP_REPLICAS})"
    exit 1
  fi

  # Helm repo 준비
  if ! helm repo list | grep -q "^nvidia[[:space:]]"; then
    echo "📦 Helm repo 추가: nvidia"
    helm repo add nvidia https://nvidia.github.io/k8s-device-plugin >/dev/null
  fi
  echo "🔄 Helm repo 업데이트"
  helm repo update nvidia >/dev/null || helm repo update >/dev/null

  # values 파일 생성 (config.map + default)
  echo "📝 values 파일 생성 (time-slicing 설정 포함)"
  local values_file
  values_file="$(mktemp)"
  cat > "${values_file}" <<EOF
config:
  map:
    default: |-
      version: v1
      flags:
        migStrategy: none
      sharing:
        timeSlicing:
          renameByDefault: false
          failRequestsGreaterThanOne: false
          resources:
            - name: nvidia.com/gpu
              replicas: ${NVDP_REPLICAS}
  default: "default"
EOF

  echo "🛠️  Helm upgrade --install (NVIDIA Device Plugin) 실행 중..."
  helm upgrade --install "${NVDP_RELEASE_NAME}" nvidia/nvidia-device-plugin \
    --namespace "${NVDP_NAMESPACE}" \
    --create-namespace \
    --version "${NVDP_CHART_VERSION}" \
    -f "${values_file}"

  rm -f "${values_file}"

  echo
  echo "⏳ DaemonSet 준비 상태 확인..."
  kubectl rollout status daemonset/nvidia-device-plugin-daemonset \
    -n "${NVDP_NAMESPACE}" --timeout=180s || true

  echo
  echo "🔍 할당 가능한 GPU 슬라이스 수 확인:"
  kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu 2>/dev/null || true
  echo

  # GPU 리소스 없을 때 안내
  if ! kubectl get nodes -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' 2>/dev/null | grep -q '[0-9]'; then
    echo "⚠️  클러스터 노드에서 nvidia.com/gpu 리소스를 찾지 못했습니다."
    echo "    - 실제 GPU 없는 환경(minikube 등)이면 정상일 수 있습니다."
    echo "    - GPU 노드라면 호스트에서 nvidia-smi / 드라이버 / nvidia-container-toolkit 설정을 확인하세요."
  else
    echo "✅ 완료! 파드는 'nvidia.com/gpu: 1' 요청으로 time-slice를 할당받게 됩니다."
  fi
}

# ===== llm-ops-platform (Helm) 설치 =====
install_llm_ops_platform() {
  echo ">>> Updating Helm dependencies..."
  helm dependency update "${CHART_DIR}"

  echo ">>> Installing llm-ops-platform..."
  helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}" \
    -n "${NAMESPACE}" \
    --create-namespace \
    -f "${CHART_DIR}/values.yaml" \
    --set kserve.enabled=true \
    --set gpuPlugin.enabled=false \
    --set "kserve.controller.deploymentMode=${KSERVE_DEPLOYMENT_MODE}" \
    --set "kserve.ingressGateway.tls.enabled=${KSERVE_TLS_ENABLED}" \
    --set "kserve.ingressGateway.certManager.enabled=${KSERVE_TLS_ENABLED}"
}

# ===== 실행 순서 =====
ensure_cert_manager
ensure_kserve_crds
install_nvidia_device_plugin
install_llm_ops_platform

echo
echo "✅ llm-ops-platform + KServe + NVIDIA Device Plugin (time-slicing) 배포 완료"
echo "   - NVIDIA DP Pod:    kubectl get pods -n ${NVDP_NAMESPACE} | grep nvidia"
echo "   - GPU 노드 리소스:  kubectl describe node <NODE> | grep -A3 nvidia"
echo "   - KServe 컨트롤러:  kubectl get pods -n ${NAMESPACE} | grep kserve"
