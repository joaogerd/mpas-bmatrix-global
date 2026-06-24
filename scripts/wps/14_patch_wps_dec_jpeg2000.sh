#!/usr/bin/env bash
set -euo pipefail

# Apply the JasPer compatibility patch required by WPS 4.6.0.
#
# This entry point is normally called automatically by
# scripts/wps/12_build_wps_ungrib.sh. It remains available for inspection or
# an explicit source-only patch operation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"
# shellcheck source=_patches.sh
source "${SCRIPT_DIR}/_patches.sh"

if [[ ! -d "${WPS_SRC_DIR}" ]]; then
  echo "ERRO: diretório do WPS não encontrado: ${WPS_SRC_DIR}" >&2
  echo "Execute primeiro: bash scripts/wps/10_download_wps_assets.sh" >&2
  exit 1
fi

wps_require_command python3 grep

echo "=== Patch JasPer do WPS ==="
wps_show_layout
wps_apply_dec_jpeg2000_patch

target="${WPS_SRC_DIR}/ungrib/src/ngl/g2/dec_jpeg2000.c"
echo
echo "=== Linhas verificadas ==="
grep -nE 'jpc_decode|jas_image_decode|jas_image_strtofmt' "${target}" || true

echo
if wps_is_true "${WPS_DEC_JPEG2000_PATCH_CHANGED}"; then
  echo "O código-fonte foi alterado. Recompile com:"
  echo "  FORCE_WPS_REBUILD=true bash scripts/wps/12_build_wps_ungrib.sh"
else
  echo "Nenhuma alteração foi necessária."
fi
