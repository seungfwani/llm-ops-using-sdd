#!/usr/bin/env bash
set -euo pipefail

log()  { echo -e "[INFO] $*"; }
warn() { echo -e "[WARN] $*" >&2; }
err()  { echo -e "[ERROR] $*" >&2; }
die()  { err "$*"; exit 1; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }
require_cmd() { have_cmd "$1" || die "필수 커맨드가 없습니다: $1"; }

# kubectl/helm은 대부분 단계에서 필요
require_base_tools() {
  require_cmd kubectl
  require_cmd helm
}
