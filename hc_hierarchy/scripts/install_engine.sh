#!/usr/bin/env bash
#
# install_engine.sh — one-shot hdlConvertor engine + hc_hierarchy dev install
#
# Usage (from anywhere):
#   /home/user/tools/CodeFromAI/hc_hierarchy/scripts/install_engine.sh
#
# Options:
#   --skip-apt          Do not run apt (no sudo / deps already installed)
#   --skip-antlr-build  Skip antlr4 C++ runtime compile (already in .deps/antlr4-install)
#   --skip-verify       Skip pytest phase0/1 at the end
#   --jobs N            Parallel build jobs (default: nproc or 2)
#   -h, --help
#
# Typical runtime: antlr4 runtime ~10+ min, hdlConvertor ~5–30 min (CPU/arch dependent)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPS="$ROOT/.deps"
LOG="$DEPS/install_engine.log"
ANTLR_JAR="$DEPS/antlr4-complete.jar"
ANTLR_URL="https://www.antlr.org/download/antlr-4.13.2-complete.jar"
ANTLR_RT_REPO="$DEPS/antlr4-runtime"
ANTLR_PREFIX="$DEPS/antlr4-install"
HC_SRC="$DEPS/hdlConvertor-2.3"
HC_TARBALL="$DEPS/hdlConvertor-2.3.tar.gz"
HC_TARBALL_URL="https://files.pythonhosted.org/packages/source/h/hdlConvertor/hdlConvertor-2.3.tar.gz"

SKIP_APT=0
SKIP_ANTLR_BUILD=0
SKIP_VERIFY=0
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 2)}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-apt) SKIP_APT=1 ;;
    --skip-antlr-build) SKIP_ANTLR_BUILD=1 ;;
    --skip-verify) SKIP_VERIFY=1 ;;
    --jobs) shift; JOBS="${1:?--jobs needs a number}" ;;
    -h|--help)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

mkdir -p "$DEPS"
exec > >(tee -a "$LOG") 2>&1

log() { echo "[$(date '+%H:%M:%S')] $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

log "=== hc_hierarchy install_engine ==="
log "ROOT=$ROOT"
log "Log: $LOG"

# ---------------------------------------------------------------------------
# 0. Prerequisites
# ---------------------------------------------------------------------------
need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

need_cmd python3
need_cmd pip3
need_cmd cmake
need_cmd git

if ! command -v ninja >/dev/null 2>&1; then
  log "ninja not in PATH — will install via pip"
fi
if ! command -v java >/dev/null 2>&1; then
  log "WARNING: java not found — ANTLR codegen may fail; install default-jre"
fi

# ---------------------------------------------------------------------------
# 1. Optional system packages (Debian/Ubuntu)
# ---------------------------------------------------------------------------
if [[ "$SKIP_APT" -eq 0 ]] && command -v sudo >/dev/null 2>&1; then
  if sudo -n true 2>/dev/null || [[ -t 0 ]]; then
    log "Installing apt build dependencies (optional)..."
    sudo apt-get update -qq || true
    sudo apt-get install -y -qq \
      build-essential cmake ninja-build default-jre python3-dev \
      pkg-config git curl ca-certificates \
      2>/dev/null || log "apt install skipped or failed — continue if tools exist"
  else
    log "No sudo password — skip apt (use --skip-apt)"
  fi
else
  log "Skip apt packages"
fi

# ---------------------------------------------------------------------------
# 2. Python build tools + hdlConvertorAst + project editable install
# ---------------------------------------------------------------------------
log "Installing Python build dependencies..."
pip3 install -q --upgrade pip wheel
pip3 install -q ninja cmake scikit-build cython setuptools
pip3 install -q hdlConvertorAst

cd "$ROOT"
pip3 install -q -e ".[dev]" || pip3 install -q -e .

# ---------------------------------------------------------------------------
# 3. ANTLR complete jar
# ---------------------------------------------------------------------------
if [[ ! -f "$ANTLR_JAR" ]]; then
  log "Downloading antlr4-complete.jar ..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$ANTLR_JAR" "$ANTLR_URL"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$ANTLR_JAR" "$ANTLR_URL"
  else
    die "Need curl or wget to download ANTLR jar"
  fi
else
  log "ANTLR jar already present: $ANTLR_JAR"
fi
export HC_ANTLR_COMPLETE_JAR="$ANTLR_JAR"
export ANTLR_COMPLETE_PATH="$ANTLR_JAR"

# ---------------------------------------------------------------------------
# 4. hdlConvertor source + CMake patch
# ---------------------------------------------------------------------------
apply_cmake_patch() {
  local cmake_file="$1/src/CMake_antlr4.txt"
  [[ -f "$cmake_file" ]] || return 1
  if grep -q "hc_hierarchy: prefer project-bundled" "$cmake_file" 2>/dev/null; then
    return 0
  fi
  log "Applying CMake_antlr4.txt patch ..."
  python3 <<'PY' "$cmake_file"
import sys
path = sys.argv[1]
marker = "# there are two types of distribution"
patch = r'''# hc_hierarchy: prefer project-bundled antlr4-complete.jar
set(_HC_ANTLR_JAR "$ENV{HC_ANTLR_COMPLETE_JAR}")
if(NOT _HC_ANTLR_JAR)
  set(_HC_ANTLR_JAR "${CMAKE_CURRENT_LIST_DIR}/../../.deps/antlr4-complete.jar")
endif()
if(EXISTS "${_HC_ANTLR_JAR}")
  set(_ANTLR_JAR_LOCATION_antlr4_complete "${_HC_ANTLR_JAR}")
endif()
'''
text = open(path).read()
if "hc_hierarchy: prefer project-bundled" in text:
    sys.exit(0)
idx = text.find(marker)
if idx < 0:
    sys.exit(1)
text = text[:idx] + patch + text[idx:]
open(path, "w").write(text)
PY
}

if [[ ! -d "$HC_SRC" ]]; then
  log "Fetching hdlConvertor 2.3 source ..."
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$HC_TARBALL" "$HC_TARBALL_URL"
  else
    wget -q -O "$HC_TARBALL" "$HC_TARBALL_URL"
  fi
  tar -xzf "$HC_TARBALL" -C "$DEPS"
fi
apply_cmake_patch "$HC_SRC" || die "Failed to patch $HC_SRC/src/CMake_antlr4.txt"

# ---------------------------------------------------------------------------
# 5. antlr4 C++ runtime → $ANTLR_PREFIX
# ---------------------------------------------------------------------------
export ANTLR4CPP_ROOT="$ANTLR_PREFIX"
export CMAKE_ARGS="-DANTLR4CPP_ROOT=$ANTLR4CPP_ROOT"

_runtime_ok() {
  [[ -f "$ANTLR_PREFIX/lib/libantlr4-runtime.so" ]] \
    || [[ -f "$ANTLR_PREFIX/lib/libantlr4-runtime.a" ]] \
    || [[ -f "$ANTLR_PREFIX/lib64/libantlr4-runtime.so" ]]
}

if [[ "$SKIP_ANTLR_BUILD" -eq 1 ]] && _runtime_ok; then
  log "Skip antlr4 runtime build (--skip-antlr-build, library present)"
elif _runtime_ok; then
  log "antlr4 runtime already installed at $ANTLR_PREFIX"
else
  log "Building antlr4 C++ runtime (this takes several minutes) ..."
  if [[ ! -d "$ANTLR_RT_REPO/.git" ]]; then
    git clone --depth 1 --branch 4.13.2 https://github.com/antlr/antlr4.git "$ANTLR_RT_REPO"
  fi
  build_dir="$ANTLR_RT_REPO/runtime/Cpp/build"
  mkdir -p "$build_dir"
  cd "$build_dir"
  rm -rf ./* 2>/dev/null || true
  cmake .. \
    -DCMAKE_INSTALL_PREFIX="$ANTLR_PREFIX" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DANTLR4CPP_TESTS=OFF
  cmake --build . -j"$JOBS"
  cmake --install .
  cd "$ROOT"
  _runtime_ok || die "antlr4 runtime install failed — check $LOG"
  log "antlr4 runtime installed: $ANTLR_PREFIX"
fi

# ---------------------------------------------------------------------------
# 6. hdlConvertor Python extension
# ---------------------------------------------------------------------------
if python3 -c "from hdlConvertor import HdlConvertor" 2>/dev/null; then
  log "hdlConvertor already importable — skip rebuild"
else
  log "Building and installing hdlConvertor from $HC_SRC ..."
  export HC_ANTLR_COMPLETE_JAR="$ANTLR_JAR"
  export ANTLR4CPP_ROOT="$ANTLR_PREFIX"
  export CMAKE_ARGS="-DANTLR4CPP_ROOT=$ANTLR4CPP_ROOT"
  cd "$HC_SRC"
  rm -rf _skbuild build dist *.egg-info 2>/dev/null || true
  # --no-build-isolation: use system/pip cmake & ninja (avoids broken isolated env paths)
  pip3 install --no-build-isolation --no-cache-dir . \
    || pip3 install --no-cache-dir .
  cd "$ROOT"
  python3 -c "from hdlConvertor import HdlConvertor; print('hdlConvertor OK')" \
    || die "hdlConvertor import failed after install"
fi

# ---------------------------------------------------------------------------
# 7. Verify
# ---------------------------------------------------------------------------
log "Engine status:"
python3 -c "
from hch.engine.availability import check_engine
s = check_engine()
print('  available:', s.available)
print('  message:', s.message)
"

if [[ "$SKIP_VERIFY" -eq 0 ]]; then
  log "Running verify_phase0.sh ..."
  bash "$ROOT/scripts/verify_phase0.sh" || true
  if python3 -c "from hdlConvertor import HdlConvertor" 2>/dev/null; then
    log "Running verify_phase1.sh ..."
    bash "$ROOT/scripts/verify_phase1.sh" || true
  fi
fi

log "=== install_engine finished ==="
log "Next: hch-index <filelist.f> -o design.hch.db  (Phase 2 CLI, when wired)"