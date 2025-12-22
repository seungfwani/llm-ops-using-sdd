#!/usr/bin/env bash
set -euo pipefail
# expects common.sh loaded

build_docker_image() {
  if [[ "${BUILD_IMAGE}" != "true" ]]; then
    log "BUILD_IMAGE=false: 이미지 빌드를 건너뜁니다."
    return 0
  fi

  require_cmd docker

  log "Docker 이미지 빌드: ${IMAGE}"
  docker build -t "${IMAGE}" -f "${DOCKERFILE_PATH}" "${PROJECT_ROOT}"
  log "Docker 이미지 푸시: ${IMAGE}"
  docker push "${IMAGE}"
}

build_helm_args() {
  HELM_ARGS=(
    "--namespace" "${NAMESPACE}"
    "--create-namespace"
    "-f" "${VALUES_FILE}"
    "--set" "image.repository=${IMAGE%:*}"
    "--set" "image.tag=${IMAGE##*:}"
    # 차트 내부 gpuPlugin은 외부 설치를 전제로 끔 (중복 방지)
    "--set" "gpuPlugin.enabled=false"
    # KServe hook이 잘못된 ns를 바라보지 않도록 강제
    "--set" "kserve.namespaceOverride=${KSERVE_NAMESPACE}"
  )
}

install_llm_ops_platform() {
  build_helm_args

  log "llm-ops-platform Helm 배포: ns=${NAMESPACE}, release=${RELEASE_NAME}"
  (cd "$(dirname "${BASH_SOURCE[0]}")/.." && helm upgrade --install "${RELEASE_NAME}" . "${HELM_ARGS[@]}")
}
