#!/usr/bin/env bash
set -euo pipefail
# expects common.sh loaded

ensure_kserve_crds() {
  log "KServe CRD 설치/업데이트"
  helm upgrade --install kserve-crd oci://ghcr.io/kserve/charts/kserve-crd \
    --version "${KSERVE_VERSION}" \
    -n "${KSERVE_NAMESPACE}" --create-namespace
}

_kserve_controller_exists() {
  kubectl -n "${KSERVE_NAMESPACE}" get deploy kserve-controller-manager >/dev/null 2>&1 && return 0
  # 일부 배포는 이름이 다를 수 있어 넓게 확인
  kubectl -n "${KSERVE_NAMESPACE}" get deploy | grep -qi kserve && return 0
  return 1
}

ensure_kserve_stack() {
  log "KServe stack 설치/업데이트 (controller/webhook 포함)"
  # KServe stack chart는 ClusterServingRuntime 등 CRD가 선행되어야 함
  ensure_kserve_crds
  # 공식 chart: oci://ghcr.io/kserve/charts/kserve
  helm upgrade --install kserve oci://ghcr.io/kserve/charts/kserve \
    --version "${KSERVE_VERSION}" \
    -n "${KSERVE_NAMESPACE}" --create-namespace

  log "KServe 컨트롤러 준비 대기"
  # 이름이 다를 수 있어 deployment label 기반으로 대기
  kubectl -n "${KSERVE_NAMESPACE}" wait --for=condition=available deploy -l app.kubernetes.io/name=kserve --timeout=300s || true
  kubectl -n "${KSERVE_NAMESPACE}" get deploy
}

ensure_kserve() {
  case "${KSERVE_INSTALL_MODE}" in
    skip)
      log "KSERVE_INSTALL_MODE=skip: KServe 설치를 건너뜁니다."
      return 0
      ;;
    crd-only)
      ensure_kserve_crds
      return 0
      ;;
    stack)
      ensure_kserve_stack
      return 0
      ;;
    detect)
      if _kserve_controller_exists; then
        log "KServe 컨트롤러가 이미 존재합니다. 설치를 건너뜁니다."
        return 0
      fi

      # 컨트롤러가 없으면 stack 시도 -> 실패하면 CRD만이라도 깔아두기
      if ensure_kserve_stack; then
        return 0
      else
        warn "KServe stack 설치에 실패했습니다. CRD-only로 fallback 합니다."
        ensure_kserve_crds
      fi
      ;;
    *)
      die "잘못된 KSERVE_INSTALL_MODE: ${KSERVE_INSTALL_MODE}"
      ;;
  esac
}
