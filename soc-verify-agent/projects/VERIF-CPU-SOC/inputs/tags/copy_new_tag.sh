#!/usr/bin/env bash
# Scaffold a new inputs/tags/{TAG}/ folder — copies MD/YAML SSOT that gen does NOT create.
#
# Usage:
#   ./copy_new_tag.sh my_chip_v1              # empty intake template (gates block LLM)
#   ./copy_new_tag.sh my_chip_v1 --example    # filled dry-run example (reference only)
#   ./copy_new_tag.sh my_chip_v1 --from main  # copy live intake from another tag
#
# See: templates/obsidian/agent/vcpu-soc-integration/12-EXAMPLE-SCAFFOLD.md

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD="${ROOT}/_scaffold"
SOC_ROOT="$(cd "${ROOT}/../../../.." && pwd)"
TEMPLATE="${SOC_ROOT}/templates/obsidian/agent/vcpu-soc-integration/intake/customer_soc_intake.template.yaml"
FROM_TAG=""
USE_EXAMPLE=false

usage() {
  sed -n '2,8p' "$0"
  exit 1
}

TAG="${1:-}"
shift || true
while (( $# > 0 )); do
  case "$1" in
    --from) FROM_TAG="${2:-}"; shift 2 ;;
    --example) USE_EXAMPLE=true; shift ;;
    -h|--help) usage ;;
    *) echo "unknown arg: $1" >&2; usage ;;
  esac
done

[[ -n "$TAG" ]] || usage
[[ -d "$SCAFFOLD" ]] || { echo "missing scaffold: $SCAFFOLD" >&2; exit 1; }

DEST="${ROOT}/${TAG}"
if [[ -e "$DEST" ]]; then
  echo "refusing to overwrite existing: $DEST" >&2
  exit 1
fi

echo "[scaffold] creating ${DEST}"

mkdir -p "${DEST}/weekly_release" "${DEST}/sfr" "${DEST}/overrides"
touch "${DEST}/weekly_release/.gitkeep" "${DEST}/sfr/.gitkeep" "${DEST}/overrides/.gitkeep"

sed "s/{TAG}/${TAG}/g" "${SCAFFOLD}/README.md" > "${DEST}/README.md"
sed "s/{TAG}/${TAG}/g" "${SCAFFOLD}/manifest.yaml" > "${DEST}/manifest.yaml"

mkdir -p "${DEST}/deployment"
sed "s/{TAG}/${TAG}/g" "${SCAFFOLD}/deployment/README.md" > "${DEST}/deployment/README.md"
sed "s/{TAG}/${TAG}/g" "${SCAFFOLD}/deployment/integration_notes.md" > "${DEST}/deployment/integration_notes.md"
sed "s/{TAG}/${TAG}/g" "${SCAFFOLD}/deployment/questions_pending.md" > "${DEST}/deployment/questions_pending.md"

INTAKE_DST="${DEST}/deployment/customer_soc_intake.yaml"
if [[ -n "$FROM_TAG" && -f "${ROOT}/${FROM_TAG}/deployment/customer_soc_intake.yaml" ]]; then
  cp -a "${ROOT}/${FROM_TAG}/deployment/customer_soc_intake.yaml" "$INTAKE_DST"
  echo "[scaffold] intake from ${FROM_TAG}/deployment/customer_soc_intake.yaml"
elif [[ "$USE_EXAMPLE" == true && -f "${ROOT}/main/deployment/customer_soc_intake.example.yaml" ]]; then
  cp -a "${ROOT}/main/deployment/customer_soc_intake.example.yaml" "$INTAKE_DST"
  echo "[scaffold] WARN: example intake (dry-run) — use only for reference/testing"
elif [[ -f "$TEMPLATE" ]]; then
  cp -a "$TEMPLATE" "$INTAKE_DST"
  echo "[scaffold] intake from template (user_provided/user_documented=false)"
else
  echo "[scaffold] WARN: no template — fill deployment/customer_soc_intake.yaml manually"
fi

echo "[scaffold] done: ${DEST}"
echo "[scaffold] next: bootstrap RTL (~/tools/__CFI), edit intake, integration_notes.md; ./scripts/bootstrap_verifcpu_workspace.sh"