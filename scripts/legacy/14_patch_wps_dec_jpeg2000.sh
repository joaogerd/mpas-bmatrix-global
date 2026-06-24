#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"

echo "AVISO: scripts/legacy/14_patch_wps_dec_jpeg2000.sh foi substituído por scripts/wps/14_patch_wps_dec_jpeg2000.sh." >&2
exec bash "${REPO_ROOT}/scripts/wps/14_patch_wps_dec_jpeg2000.sh" "$@"
