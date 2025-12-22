#!/usr/bin/env bash
set -euo pipefail
# expects common.sh loaded

_detect_existing_nvidia_stack() {
  # GPU Operator나 기존 device-plugin이 있으면 true
  kubectl get ds -A 2>/dev/null | grep -qiE 'nvidia|gpu-operator' && return 0
  return 1
}

_install_nvidia_device_plugin() {
  log "NVIDIA device plugin 설치/업데이트"
  helm repo add nvidia https://nvidia.github.io/k8s-device-plugin >/dev/null 2>&1 || true
  helm repo update >/dev/null 2>&1 || true

  # time-slicing configmap (chart가 config.name을 참조)
  local ts_yaml
  ts_yaml=$(cat <<EOF
version: v1
flags:
  migStrategy: none
sharing:
  timeSlicing:
    resources:
    - name: nvidia.com/gpu
      replicas: ${NVDP_REPLICAS}
EOF
)

  kubectl -n "${NVDP_NAMESPACE}" create configmap "${NVDP_CONFIGMAP_NAME}" \
    --from-literal=config.yaml="${ts_yaml}" \
    --dry-run=client -o yaml | kubectl apply -f -

  helm upgrade --install "${NVDP_RELEASE_NAME}" nvidia/nvidia-device-plugin \
    --namespace "${NVDP_NAMESPACE}" \
    --version "${NVDP_CHART_VERSION}" \
    --set config.name="${NVDP_CONFIGMAP_NAME}"
}

_verify_gpu_allocatable() {
  # allocatable 확인 (0이면 실패)
  local cnt
  cnt=$(kubectl get nodes -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' 2>/dev/null | grep -vc '^$' || true)
  # cnt는 라인 수일 뿐; 실제 값이 0만이면 실패 처리
  local vals
  vals=$(kubectl get nodes -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' 2>/dev/null || true)
  if echo "${vals}" | grep -qE '^[1-9]'; then
    log "노드에 nvidia.com/gpu allocatable이 확인됩니다."
    return 0
  fi
  return 1
}

ensure_nvidia_device_plugin() {
  case "${GPU_INSTALL_MODE}" in
    skip)
      log "GPU_INSTALL_MODE=skip: NVIDIA device plugin 설치를 건너뜁니다."
      return 0
      ;;
    detect)
      if _detect_existing_nvidia_stack; then
        log "기존 NVIDIA/GPU 스택이 감지되어 설치를 건너뜁니다."
      else
        _install_nvidia_device_plugin
      fi
      ;;
    install)
      _install_nvidia_device_plugin
      ;;
    *)
      die "잘못된 GPU_INSTALL_MODE: ${GPU_INSTALL_MODE}"
      ;;
  esac

  if [[ "${FAIL_FAST}" == "true" ]]; then
    if ! _verify_gpu_allocatable; then
      die "GPU allocatable(nvidia.com/gpu)이 확인되지 않습니다. (FAIL_FAST=true)"
    fi
  else
    if ! _verify_gpu_allocatable; then
      warn "GPU allocatable(nvidia.com/gpu)이 확인되지 않습니다."
    fi
  fi
}
