#!/usr/bin/env bash
# Manual SSOT snapshot — run before risky edits to ~/tools/__CFA.
set -euo pipefail

CFA_ROOT="${CFA_ROOT:-$HOME/tools/__CFA}"
BACKUP_ROOT="${CFA_BACKUP_ROOT:-$HOME/tools/__CFA-backups}"
LABEL="${1:-manual}"
STAMP="${CFA_BACKUP_STAMP:-$(date -u +%Y%m%dT%H%M%SZ)}"

[[ -d "$CFA_ROOT/VerifCPU" ]] || { echo "[FAIL] missing CFA tree: $CFA_ROOT" >&2; exit 1; }
mkdir -p "$BACKUP_ROOT"
DEST="$BACKUP_ROOT/cfa-${LABEL}-${STAMP}.tar.gz"

tar -czf "$DEST" \
  --exclude='VerifCPU/verif_cpu_verilog/sim_build' \
  --exclude='VerifCPU/verif_cpu_verilog/firmware/campaign/build' \
  --exclude='**/__pycache__' \
  --exclude='**/*.pyc' \
  -C "$(dirname "$CFA_ROOT")" "$(basename "$CFA_ROOT")"

echo "$DEST" | tee "$BACKUP_ROOT/LATEST_MANUAL_BACKUP.txt"
echo "[OK] CFA snapshot: $DEST"