#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"

echo "AVISO: scripts/legacy/11_probe_wps_build_environment.sh foi substituído por scripts/wps/11_probe_wps_build_environment.sh." >&2
exec bash "${REPO_ROOT}/scripts/wps/11_probe_wps_build_environment.sh" "$@"
