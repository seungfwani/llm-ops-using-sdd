#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
사용법:
  ./deploy.sh [options]

필수/주요 옵션:
  --namespace <ns>                 앱 배포 네임스페이스 (기본: llm-ops-dev)
  --release-name <name>            Helm 릴리스 이름 (기본: llm-ops-platform)
  --values <path>                  Helm values 파일 (기본: values.yaml)

빌드 옵션:
  --build-image                    Docker 이미지 빌드+푸시 수행
  --image <repo/name:tag>          사용할 이미지 (기본: ghcr.io/your-org/llm-ops:latest)
  --dockerfile <path>              Dockerfile 경로

KServe 옵션:
  --kserve-install-mode <detect|stack|crd-only|skip>  KServe 설치 모드 (기본: detect)
  --kserve-namespace <ns>                              KServe 네임스페이스 (기본: kserve-system)
  --kserve-version <ver>                               KServe chart 버전(기본: 0.15.1)

GPU 옵션:
  --gpu-install-mode <detect|install|skip>             NVIDIA device plugin 설치 모드 (기본: detect)
  --nvidia-device-plugin-replicas <n>                  time-slicing replica 수 (기본: 4)

동작 옵션:
  --fail-fast <true|false>                             사전조건 실패 시 즉시 중단 (기본: true)
  -h, --help                                           도움말

EOF
}

# ===== defaults (export to make libs see them) =====
init_defaults() {
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  CHART_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

  PROJECT_ROOT_DEFAULT="$(cd "${CHART_DIR}/../../.." && pwd)"
  DOCKERFILE_PATH_DEFAULT="${PROJECT_ROOT_DEFAULT}/Dockerfile"

  # App
  export NAMESPACE="${NAMESPACE:-llm-ops-dev}"
  export RELEASE_NAME="${RELEASE_NAME:-llm-ops-platform}"
  export VALUES_FILE="${VALUES_FILE:-${CHART_DIR}/values.yaml}"
  export IMAGE="${IMAGE:-ghcr.io/your-org/llm-ops:latest}"
  export BUILD_IMAGE="${BUILD_IMAGE:-false}"

  export PROJECT_ROOT="${PROJECT_ROOT:-${PROJECT_ROOT_DEFAULT}}"
  export DOCKERFILE_PATH="${DOCKERFILE_PATH:-${DOCKERFILE_PATH_DEFAULT}}"

  # KServe
  export KSERVE_VERSION="${KSERVE_VERSION:-0.15.1}"
  export KSERVE_NAMESPACE="${KSERVE_NAMESPACE:-kserve-system}"
  export KSERVE_INSTALL_MODE="${KSERVE_INSTALL_MODE:-detect}"

  # NVIDIA device plugin
  export GPU_INSTALL_MODE="${GPU_INSTALL_MODE:-detect}"
  export NVDP_REPLICAS="${NVDP_REPLICAS:-4}"
  export NVDP_NAMESPACE="${NVDP_NAMESPACE:-kube-system}"
  export NVDP_RELEASE_NAME="${NVDP_RELEASE_NAME:-nvidia-device-plugin}"
  export NVDP_CHART_VERSION="${NVDP_CHART_VERSION:-0.15.0}"
  export NVDP_CONFIGMAP_NAME="${NVDP_CONFIGMAP_NAME:-nvidia-device-plugin-config}"

  # Behavior
  export FAIL_FAST="${FAIL_FAST:-true}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --namespace) NAMESPACE="$2"; shift 2 ;;
      --release-name) RELEASE_NAME="$2"; shift 2 ;;
      --values) VALUES_FILE="$2"; shift 2 ;;
      --image) IMAGE="$2"; shift 2 ;;
      --build-image) BUILD_IMAGE=true; shift ;;
      --dockerfile) DOCKERFILE_PATH="$2"; shift 2 ;;

      --kserve-install-mode) KSERVE_INSTALL_MODE="$2"; shift 2 ;;
      --kserve-namespace) KSERVE_NAMESPACE="$2"; shift 2 ;;
      --kserve-version) KSERVE_VERSION="$2"; shift 2 ;;

      --gpu-install-mode) GPU_INSTALL_MODE="$2"; shift 2 ;;
      --nvidia-device-plugin-replicas) NVDP_REPLICAS="$2"; shift 2 ;;

      --fail-fast) FAIL_FAST="$2"; shift 2 ;;

      -h|--help) show_help; exit 0 ;;
      *) echo "알 수 없는 옵션: $1"; show_help; exit 1 ;;
    esac
  done

  export NAMESPACE RELEASE_NAME VALUES_FILE IMAGE BUILD_IMAGE DOCKERFILE_PATH
  export KSERVE_INSTALL_MODE KSERVE_NAMESPACE KSERVE_VERSION
  export GPU_INSTALL_MODE NVDP_REPLICAS
  export FAIL_FAST
}
