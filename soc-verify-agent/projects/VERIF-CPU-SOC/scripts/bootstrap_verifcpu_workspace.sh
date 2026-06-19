#!/usr/bin/env bash
# Bind VerifCPU RTL (RTL_ROOT) and update cache.yaml clone.path
#
# Priority:
#   1. --dest /path/to/verif_cpu_verilog  (existing RTL tree)
#   2. discovered.yaml local_clone_path   (default: ~/tools/__CFI)
#   3. git clone → projects/VERIF-CPU-SOC/workspace/{tag}
#
# Usage:
#   ./bootstrap_verifcpu_workspace.sh
#   ./bootstrap_verifcpu_workspace.sh --tag v1.2.0
#   ./bootstrap_verifcpu_workspace.sh --dest ~/tools/__CFI/VerifCPU/verif_cpu_verilog
#
set -euo pipefail
source "$(dirname "$0")/_common.sh"

TAG_ARG=""
DEST_OVERRIDE=""

while (( $# > 0 )); do
  case "$1" in
    --tag) TAG_ARG="${2:-}"; shift 2 ;;
    --dest) DEST_OVERRIDE="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) die "unknown arg: $1" ;;
  esac
done

EFFECTIVE_TAG="${TAG_ARG:-${TAG}}"
DISCOVERED="${PROJECT_DIR}/discovered.yaml"
CACHE="${PROJECT_DIR}/cache.yaml"

read_discovered() {
  python3 - <<'PY' "${DISCOVERED}"
import sys, yaml
from pathlib import Path
d = yaml.safe_load(Path(sys.argv[1]).read_text()) or {}
print(d.get("git_url") or "")
print(d.get("rtl_subdir") or "VerifCPU/verif_cpu_verilog")
print(d.get("local_clone_path") or "")
PY
}

mapfile -t DISC < <(read_discovered)
GIT_URL="${DISC[0]:-}"
RTL_SUBDIR="${DISC[1]:-VerifCPU/verif_cpu_verilog}"
LOCAL_CLONE_PATH="${DISC[2]:-}"

clone_root_from_rtl() {
  local rtl_root="$1"
  python3 - <<'PY' "$rtl_root" "$RTL_SUBDIR"
import sys
from pathlib import Path
rtl = Path(sys.argv[1]).resolve()
sub = sys.argv[2].strip("/")
if sub and str(rtl).endswith(sub):
    print(str(rtl)[: -len(sub)].rstrip("/"))
else:
    print(str(rtl.parent))
PY
}

resolve_local_clone() {
  local candidate
  for candidate in "${LOCAL_CLONE_PATH}" "${HOME}/tools/__CFI"; do
    [[ -n "$candidate" ]] || continue
    candidate="$(python3 -c "from pathlib import Path; print(Path('${candidate}').expanduser())")"
    if [[ -f "${candidate}/${RTL_SUBDIR}/example.sh" ]]; then
      echo "${candidate}/${RTL_SUBDIR}"
      return 0
    fi
  done
  return 1
}

if [[ -z "$DEST_OVERRIDE" ]]; then
  if DEST_OVERRIDE="$(resolve_local_clone)"; then
    log "using local CFI RTL: ${DEST_OVERRIDE}"
  fi
fi

if [[ -n "$DEST_OVERRIDE" ]]; then
  RTL_ROOT="$(cd "$(python3 -c "from pathlib import Path; print(Path('${DEST_OVERRIDE}').expanduser())")" && pwd)"
  [[ -f "${RTL_ROOT}/example.sh" ]] || die "not a VerifCPU root (no example.sh): ${RTL_ROOT}"
  CLONE_ROOT="$(clone_root_from_rtl "${RTL_ROOT}")"
  log "using existing RTL_ROOT=${RTL_ROOT} (clone.path=${CLONE_ROOT})"
else
  CLONE_ROOT="${PROJECT_DIR}/workspace/${EFFECTIVE_TAG}"
  RTL_ROOT="${CLONE_ROOT}/${RTL_SUBDIR}"
  if [[ -f "${RTL_ROOT}/example.sh" ]]; then
    log "VerifCPU already present: ${RTL_ROOT}"
  else
    mkdir -p "${CLONE_ROOT}"
    HTTPS_URL="${GIT_URL}"
    if [[ "$GIT_URL" == git@github.com:* ]]; then
      HTTPS_URL="https://github.com/${GIT_URL#git@github.com:}"
    fi
    [[ -n "$HTTPS_URL" ]] || die "discovered.yaml missing git_url (or set local_clone_path / --dest)"
    if [[ -d "${CLONE_ROOT}/.git" ]]; then
      log "pull ${CLONE_ROOT}"
      git -C "${CLONE_ROOT}" pull --ff-only
    else
      log "clone ${HTTPS_URL} -> ${CLONE_ROOT}"
      git clone --depth 1 "${HTTPS_URL}" "${CLONE_ROOT}"
    fi
    [[ -f "${RTL_ROOT}/example.sh" ]] || die "clone ok but VerifCPU missing: ${RTL_ROOT}"
  fi
fi

python3 - <<'PY' "${CACHE}" "${CLONE_ROOT}" "${EFFECTIVE_TAG}"
import sys, yaml
from pathlib import Path
from datetime import datetime, timezone

cache_path, clone_root, tag = sys.argv[1:4]
data = yaml.safe_load(Path(cache_path).read_text()) or {}
data.setdefault("tag", {})["value"] = tag
data.setdefault("clone", {})["path"] = clone_root
data["clone"]["valid_for_tag"] = tag
data["clone"]["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
Path(cache_path).write_text(yaml.dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
print(f"[bootstrap] cache.yaml clone.path={clone_root}")
PY

log "RTL_ROOT=${RTL_ROOT}"
log "next: cd \"${RTL_ROOT}\" && ./example.sh gen"