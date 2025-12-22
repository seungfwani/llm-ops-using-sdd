#!/usr/bin/env bash
set -euo pipefail
# expects common.sh loaded


: "${GPU_ALLOC_WAIT_SECONDS:=90}"
: "${GPU_ALLOC_WAIT_INTERVAL:=5}"


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

  # NOTE: function boundary.
}

_get_nvd_ds_name() {
  # Try to find daemonset name for this helm release
  kubectl -n "${NVDP_NAMESPACE}" get ds \
    -l "app.kubernetes.io/instance=${NVDP_RELEASE_NAME}" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true
}

_wait_nvidia_device_plugin_ready() {
  local ds
  ds="$(_get_nvd_ds_name)"
  if [[ -z "${ds}" ]]; then
    warn "NVIDIA device plugin DaemonSet을 찾지 못했습니다. (namespace=${NVDP_NAMESPACE}, release=${NVDP_RELEASE_NAME})"
    return 1
  fi
  log "NVIDIA device plugin DaemonSet 준비 대기: ${ds}"
  # rollout status가 실패해도 바로 종료하지 않고 후속 진단을 위해 return code를 전달
  kubectl -n "${NVDP_NAMESPACE}" rollout status "ds/${ds}" --timeout=120s
}

_wait_gpu_allocatable() {
  local deadline=$((SECONDS + GPU_ALLOC_WAIT_SECONDS))
  while (( SECONDS < deadline )); do
    if _verify_gpu_allocatable; then
      return 0
    fi
    sleep "${GPU_ALLOC_WAIT_INTERVAL}"
  done
  return 1
}

_dump_nvidia_diagnostics() {
  warn "=== NVIDIA 진단 정보 ==="
  warn "[nodes allocatable]"
  kubectl get nodes -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\\.com/gpu 2>/dev/null || true

  warn "[daemonsets in kube-system (nvidia 관련)]"
  kubectl -n "${NVDP_NAMESPACE}" get ds 2>/dev/null | grep -i nvidia || true

  local ds pod
  ds="$(_get_nvd_ds_name)"
  if [[ -n "${ds}" ]]; then
    warn "[daemonset describe: ${ds}]"
    kubectl -n "${NVDP_NAMESPACE}" describe "ds/${ds}" 2>/dev/null || true
    pod=$(kubectl -n "${NVDP_NAMESPACE}" get pods -l "app.kubernetes.io/instance=${NVDP_RELEASE_NAME}" \
      -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
    if [[ -n "${pod}" ]]; then
      warn "[device-plugin pod logs (tail 200): ${pod}]"
      kubectl -n "${NVDP_NAMESPACE}" logs "${pod}" --tail=200 2>/dev/null || true
    fi
  fi
  warn "=== NVIDIA 진단 정보 끝 ==="
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
        log "기존 NVIDIA/GPU 스택이 감지되었습니다."
        if ! _verify_gpu_allocatable; then
          warn "기존 NVIDIA 스택이 있지만 GPU allocatable(nvidia.com/gpu)이 확인되지 않습니다. device-plugin 설치/업데이트를 시도합니다."
          _install_nvidia_device_plugin
        else
          log "GPU allocatable이 확인되어 설치를 건너뜁니다."
        fi
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

  # 설치/업데이트를 시도했다면 DaemonSet이 실제로 스케줄링/기동될 시간을 준다.
  # (스킵 케이스에서도 이미 존재하는 DS가 rollout 중일 수 있어 항상 호출해도 무방)
  _wait_nvidia_device_plugin_ready || true

  # device-plugin 적용 직후 allocatable 반영까지 약간의 지연이 있을 수 있어 대기 후 확인
  if [[ "${FAIL_FAST}" == "true" ]]; then
    if ! _wait_gpu_allocatable; then
      _dump_nvidia_diagnostics
      die "GPU allocatable(nvidia.com/gpu)이 확인되지 않습니다. (FAIL_FAST=true)"
    fi
  else
    if ! _wait_gpu_allocatable; then
      _dump_nvidia_diagnostics
      warn "GPU allocatable(nvidia.com/gpu)이 확인되지 않습니다."
    fi
  fi
}
