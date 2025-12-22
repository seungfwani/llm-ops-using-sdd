#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="${SCRIPT_DIR}/lib"

# shellcheck source=lib/common.sh
source "${LIB_DIR}/common.sh"
# shellcheck source=lib/args.sh
source "${LIB_DIR}/args.sh"
# shellcheck source=lib/prereq_cert_manager.sh
source "${LIB_DIR}/prereq_cert_manager.sh"
# shellcheck source=lib/prereq_kserve.sh
source "${LIB_DIR}/prereq_kserve.sh"
# shellcheck source=lib/prereq_nvidia.sh
source "${LIB_DIR}/prereq_nvidia.sh"
# shellcheck source=lib/app.sh
source "${LIB_DIR}/app.sh"

main() {
  init_defaults
  parse_args "$@"

  require_base_tools

  log "=== prereq: cert-manager ==="
  ensure_cert_manager

  log "=== prereq: kserve (${KSERVE_INSTALL_MODE}) ==="
  ensure_kserve

  log "=== prereq: nvidia-device-plugin (${GPU_INSTALL_MODE}) ==="
  ensure_nvidia_device_plugin

  log "=== app: build image ==="
  build_docker_image

  log "=== app: helm install/upgrade ==="
  install_llm_ops_platform

  log "배포 완료"
}

main "$@"
