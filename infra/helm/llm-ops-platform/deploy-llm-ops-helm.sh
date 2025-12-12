#!/usr/bin/env bash
#
# llm-ops-platform + KServe + NVIDIA Device Plugin (time-slicing) 일괄 배포 스크립트
#

set -euo pipefail

# ===== 스크립트 경로 설정 (먼저 설정해야 함) =====
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ===== 기본값 설정 =====
ENVIRONMENT="dev"
KSERVE_VERSION="v0.16.0"
KSERVE_DEPLOYMENT_MODE="RawDeployment"
KSERVE_TLS_ENABLED="false"
INSTALL_CERT_MANAGER="true"
CERT_MANAGER_VERSION="v1.13.0"
NAMESPACE=""
RELEASE_NAME=""
BUILD_IMAGE="false"
PUSH_IMAGE="false"
IMAGE_REGISTRY=""
IMAGE_NAME="llm-ops-platform"
IMAGE_TAG=""
DOCKERFILE_PATH="${SCRIPT_DIR}/../../Dockerfile"
PROJECT_ROOT="${SCRIPT_DIR}/../.."
NVDP_REPLICAS="4"
NVDP_NAMESPACE="kube-system"
NVDP_RELEASE_NAME="nvidia-device-plugin"
NVDP_CHART_VERSION="0.15.0"
NVDP_CONFIGMAP_NAME="nvidia-device-plugin-config"

# ===== Help 함수 =====
show_help() {
  cat <<EOF
사용법: $0 [옵션]

llm-ops-platform + KServe + NVIDIA Device Plugin (time-slicing) 일괄 배포 스크립트

옵션:
  -h, --help                          이 도움말 표시

  환경 설정:
  -e, --environment ENV              환경 이름 (dev, stg, prod 등) [기본값: dev]
  -n, --namespace NAMESPACE           Kubernetes 네임스페이스 [기본값: llm-ops-\${ENVIRONMENT}]
  -r, --release-name NAME             Helm 릴리스 이름 [기본값: llm-ops-platform-\${ENVIRONMENT}]

  KServe 설정:
  --kserve-version VERSION           KServe 버전 [기본값: v0.16.0]
  --kserve-deployment-mode MODE      KServe 배포 모드 (RawDeployment|Serverless) [기본값: RawDeployment]
  --kserve-tls-enabled BOOL           KServe TLS 활성화 (true|false) [기본값: false]

  cert-manager 설정:
  --install-cert-manager BOOL         cert-manager 설치 여부 (true|false) [기본값: true]
  --cert-manager-version VERSION      cert-manager 버전 [기본값: v1.13.0]

  Docker 이미지 설정:
  --build-image BOOL                  Docker 이미지 빌드 여부 (true|false) [기본값: false]
  --push-image BOOL                   Docker 이미지 푸시 여부 (true|false) [기본값: false]
  --image-registry REGISTRY           이미지 레지스트리 (예: docker.io/username)
  --image-name NAME                   이미지 이름 [기본값: llm-ops-platform]
  --image-tag TAG                     이미지 태그 [기본값: \${ENVIRONMENT}-\${TIMESTAMP}]

  NVIDIA Device Plugin 설정:
  --nvdp-replicas NUM                 GPU time-slicing replicas 수 [기본값: 4]
  --nvdp-namespace NAMESPACE          NVIDIA Device Plugin 네임스페이스 [기본값: kube-system]
  --nvdp-release-name NAME            NVIDIA Device Plugin Helm 릴리스 이름 [기본값: nvidia-device-plugin]
  --nvdp-chart-version VERSION        NVIDIA Device Plugin 차트 버전 [기본값: 0.15.0]

예제:
  # 기본 설정으로 dev 환경 배포
  $0 --environment dev

  # 이미지 빌드 및 푸시 포함
  $0 --environment prod --build-image true --push-image true --image-registry docker.io/username

  # 커스텀 네임스페이스 및 릴리스 이름
  $0 --environment stg --namespace my-namespace --release-name my-release

  # GPU time-slicing replicas 변경
  $0 --environment dev --nvdp-replicas 8

환경 변수:
  모든 옵션은 환경 변수로도 설정할 수 있습니다. 환경 변수는 명령줄 옵션보다 우선순위가 낮습니다.
  예: ENVIRONMENT=prod KSERVE_VERSION=v0.17.0 $0

EOF
}

# ===== 옵션 파싱 =====
parse_args() {
  # 환경 변수에서 기본값 로드 (명령줄 인자가 없을 때 사용)
  ENVIRONMENT="${ENVIRONMENT:-dev}"
  KSERVE_VERSION="${KSERVE_VERSION:-v0.16.0}"
  KSERVE_DEPLOYMENT_MODE="${KSERVE_DEPLOYMENT_MODE:-RawDeployment}"
  KSERVE_TLS_ENABLED="${KSERVE_TLS_ENABLED:-false}"
  INSTALL_CERT_MANAGER="${INSTALL_CERT_MANAGER:-true}"
  CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.13.0}"
  NAMESPACE="${NAMESPACE:-}"
  RELEASE_NAME="${RELEASE_NAME:-}"
  BUILD_IMAGE="${BUILD_IMAGE:-false}"
  PUSH_IMAGE="${PUSH_IMAGE:-false}"
  IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
  IMAGE_NAME="${IMAGE_NAME:-llm-ops-platform}"
  IMAGE_TAG="${IMAGE_TAG:-}"
  NVDP_REPLICAS="${NVDP_REPLICAS:-4}"
  NVDP_NAMESPACE="${NVDP_NAMESPACE:-kube-system}"
  NVDP_RELEASE_NAME="${NVDP_RELEASE_NAME:-nvidia-device-plugin}"
  NVDP_CHART_VERSION="${NVDP_CHART_VERSION:-0.15.0}"

  while [[ $# -gt 0 ]]; do
    case $1 in
      -h|--help)
        show_help
        exit 0
        ;;
      -e|--environment)
        ENVIRONMENT="$2"
        shift 2
        ;;
      -n|--namespace)
        NAMESPACE="$2"
        shift 2
        ;;
      -r|--release-name)
        RELEASE_NAME="$2"
        shift 2
        ;;
      --kserve-version)
        KSERVE_VERSION="$2"
        shift 2
        ;;
      --kserve-deployment-mode)
        KSERVE_DEPLOYMENT_MODE="$2"
        shift 2
        ;;
      --kserve-tls-enabled)
        KSERVE_TLS_ENABLED="$2"
        shift 2
        ;;
      --install-cert-manager)
        INSTALL_CERT_MANAGER="$2"
        shift 2
        ;;
      --cert-manager-version)
        CERT_MANAGER_VERSION="$2"
        shift 2
        ;;
      --build-image)
        BUILD_IMAGE="$2"
        shift 2
        ;;
      --push-image)
        PUSH_IMAGE="$2"
        shift 2
        ;;
      --image-registry)
        IMAGE_REGISTRY="$2"
        shift 2
        ;;
      --image-name)
        IMAGE_NAME="$2"
        shift 2
        ;;
      --image-tag)
        IMAGE_TAG="$2"
        shift 2
        ;;
      --nvdp-replicas)
        NVDP_REPLICAS="$2"
        shift 2
        ;;
      --nvdp-namespace)
        NVDP_NAMESPACE="$2"
        shift 2
        ;;
      --nvdp-release-name)
        NVDP_RELEASE_NAME="$2"
        shift 2
        ;;
      --nvdp-chart-version)
        NVDP_CHART_VERSION="$2"
        shift 2
        ;;
      *)
        echo "❌ 알 수 없는 옵션: $1"
        echo "   '$0 --help'를 실행하여 사용법을 확인하세요."
        exit 1
        ;;
    esac
  done

  # 네임스페이스와 릴리스 이름 기본값 설정 (명시적으로 설정되지 않은 경우)
  if [[ -z "${NAMESPACE}" ]]; then
    NAMESPACE="llm-ops-${ENVIRONMENT}"
  fi
  if [[ -z "${RELEASE_NAME}" ]]; then
    RELEASE_NAME="llm-ops-platform-${ENVIRONMENT}"
  fi
  
  # 이미지 태그 기본값 설정 (명시적으로 설정되지 않은 경우)
  if [[ -z "${IMAGE_TAG}" ]]; then
    IMAGE_TAG="${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
  fi
}

# ===== 인자 파싱 실행 =====
parse_args "$@"

# 스크립트 / 차트 경로

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
echo ">>> BUILD_IMAGE            : ${BUILD_IMAGE}"
echo ">>> PUSH_IMAGE             : ${PUSH_IMAGE}"
if [[ "${BUILD_IMAGE}" == "true" ]]; then
  echo ">>> IMAGE_REGISTRY         : ${IMAGE_REGISTRY}"
  echo ">>> IMAGE_NAME             : ${IMAGE_NAME}"
  echo ">>> IMAGE_TAG              : ${IMAGE_TAG}"
fi
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

if [[ "${BUILD_IMAGE}" == "true" ]] && ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker 이미지를 빌드하려면 docker 가 필요합니다."
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

# ===== Docker 이미지 빌드 =====
build_docker_image() {
  if [[ "${BUILD_IMAGE}" != "true" ]]; then
    echo ">>> Skipping Docker image build"
    return 0
  fi

  echo ">>> Building Docker image..."
  
  # 이미지 이름 구성
  if [[ -n "${IMAGE_REGISTRY}" ]]; then
    FULL_IMAGE_NAME="${IMAGE_REGISTRY}/${IMAGE_NAME}:${IMAGE_TAG}"
  else
    FULL_IMAGE_NAME="${IMAGE_NAME}:${IMAGE_TAG}"
  fi

  echo "   - Image: ${FULL_IMAGE_NAME}"
  echo "   - Dockerfile: ${DOCKERFILE_PATH}"
  echo "   - Context: ${PROJECT_ROOT}"

  # Dockerfile 존재 확인
  if [[ ! -f "${DOCKERFILE_PATH}" ]]; then
    echo "❌ Dockerfile을 찾을 수 없습니다: ${DOCKERFILE_PATH}"
    exit 1
  fi

  # Docker 빌드
  docker build \
    -f "${DOCKERFILE_PATH}" \
    -t "${FULL_IMAGE_NAME}" \
    "${PROJECT_ROOT}"

  echo "✅ Docker 이미지 빌드 완료: ${FULL_IMAGE_NAME}"

  # 이미지 푸시
  if [[ "${PUSH_IMAGE}" == "true" ]]; then
    echo ">>> Pushing Docker image to registry..."
    docker push "${FULL_IMAGE_NAME}"
    echo "✅ Docker 이미지 푸시 완료: ${FULL_IMAGE_NAME}"
  fi

  # 환경 변수에 이미지 이름 저장 (Helm 설치 시 사용)
  export DEPLOY_IMAGE_NAME="${FULL_IMAGE_NAME}"
}

# ===== llm-ops-platform (Helm) 설치 =====
install_llm_ops_platform() {
  echo ">>> Updating Helm dependencies..."
  helm dependency update "${CHART_DIR}"

  # Helm 설치 명령어 구성
  local helm_args=(
    "upgrade" "--install" "${RELEASE_NAME}" "${CHART_DIR}"
    "-n" "${NAMESPACE}"
    "--create-namespace"
    "-f" "${CHART_DIR}/values.yaml"
    "--set" "kserve.enabled=true"
    "--set" "gpuPlugin.enabled=false"
    "--set" "kserve.controller.deploymentMode=${KSERVE_DEPLOYMENT_MODE}"
    "--set" "kserve.ingressGateway.tls.enabled=${KSERVE_TLS_ENABLED}"
    "--set" "kserve.ingressGateway.certManager.enabled=${KSERVE_TLS_ENABLED}"
  )

  # 이미지가 빌드된 경우 이미지 이름 설정
  if [[ -n "${DEPLOY_IMAGE_NAME:-}" ]]; then
    # 이미지 이름에서 repository와 tag 분리 (마지막 : 기준)
    local image_repo="${DEPLOY_IMAGE_NAME%:*}"
    local image_tag="${DEPLOY_IMAGE_NAME##*:}"
    helm_args+=(
      "--set" "app.enabled=true"
      "--set" "app.image.repository=${image_repo}"
      "--set" "app.image.tag=${image_tag}"
    )
    echo ">>> Using Docker image: ${DEPLOY_IMAGE_NAME}"
    echo "   - Repository: ${image_repo}"
    echo "   - Tag: ${image_tag}"
  fi

  echo ">>> Installing llm-ops-platform..."
  helm "${helm_args[@]}"
}

# ===== 실행 순서 =====
build_docker_image
ensure_cert_manager
ensure_kserve_crds
install_nvidia_device_plugin
install_llm_ops_platform

echo
echo "✅ llm-ops-platform + KServe + NVIDIA Device Plugin (time-slicing) 배포 완료"
echo "   - NVIDIA DP Pod:    kubectl get pods -n ${NVDP_NAMESPACE} | grep nvidia"
echo "   - GPU 노드 리소스:  kubectl describe node <NODE> | grep -A3 nvidia"
echo "   - KServe 컨트롤러:  kubectl get pods -n ${NAMESPACE} | grep kserve"
if [[ "${BUILD_IMAGE}" == "true" ]] && [[ -n "${DEPLOY_IMAGE_NAME:-}" ]]; then
  echo "   - App Pod:         kubectl get pods -n ${NAMESPACE} | grep app"
  echo "   - App Service:     kubectl get svc -n ${NAMESPACE} | grep app"
  echo "   - 배포된 이미지:    ${DEPLOY_IMAGE_NAME}"
fi
