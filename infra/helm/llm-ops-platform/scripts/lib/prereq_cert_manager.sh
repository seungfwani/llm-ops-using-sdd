#!/usr/bin/env bash
set -euo pipefail
# expects common.sh loaded

ensure_cert_manager() {
  local cm_ns="cert-manager"

  if kubectl get ns "${cm_ns}" >/dev/null 2>&1; then
    log "cert-manager 네임스페이스가 이미 존재합니다: ${cm_ns}"
  else
    log "cert-manager 네임스페이스 생성: ${cm_ns}"
    kubectl create namespace "${cm_ns}"
  fi

  # cert-manager 설치 여부 감지: deployment 존재로 단순 체크
  if kubectl -n "${cm_ns}" get deploy cert-manager >/dev/null 2>&1; then
    log "cert-manager가 이미 설치되어 있습니다."
    return 0
  fi

  log "cert-manager 설치(Helm)"
  helm repo add jetstack https://charts.jetstack.io >/dev/null 2>&1 || true
  helm repo update >/dev/null 2>&1 || true

  helm upgrade --install cert-manager jetstack/cert-manager \
    --namespace "${cm_ns}" \
    --set installCRDs=true

  log "cert-manager 설치 완료 대기"
  kubectl -n "${cm_ns}" rollout status deploy/cert-manager --timeout=180s
  kubectl -n "${cm_ns}" rollout status deploy/cert-manager-webhook --timeout=180s
}
