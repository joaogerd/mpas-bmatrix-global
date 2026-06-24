#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"

echo "AVISO: scripts/legacy/10_download_wps_assets.sh foi substituído por scripts/wps/10_download_wps_assets.sh." >&2
exec bash "${REPO_ROOT}/scripts/wps/10_download_wps_assets.sh" "$@"
