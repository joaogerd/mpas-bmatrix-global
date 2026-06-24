#!/usr/bin/env bash
# Shared source patches required by the WPS build.
#
# This file is sourced by scripts/wps/12_build_wps_ungrib.sh and may also be
# used by standalone patch entry points. It does not set shell options.

if [[ -n "${_MPAS_BMATRIX_WPS_PATCHES_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
_MPAS_BMATRIX_WPS_PATCHES_LOADED=1

# Apply the WPS 4.6.0 dec_jpeg2000.c compatibility patch for JasPer.
#
# WPS calls the obsolete/internal jpc_decode() symbol. Modern JasPer builds do
# not export it. The public API is jas_image_decode(). The function is
# idempotent and sets WPS_DEC_JPEG2000_PATCH_CHANGED=true only when it changed
# the source file in this invocation.
wps_apply_dec_jpeg2000_patch() {
  local target backup result
  target="${WPS_SRC_DIR}/ungrib/src/ngl/g2/dec_jpeg2000.c"
  backup="${target}.orig-jpc-decode"
  WPS_DEC_JPEG2000_PATCH_CHANGED=false
  export WPS_DEC_JPEG2000_PATCH_CHANGED

  if [[ ! -f "${target}" ]]; then
    echo "ERRO: arquivo alvo do patch não encontrado: ${target}" >&2
    return 1
  fi

  result="$(python3 - "${target}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

old_pattern = re.compile(
    r"image\s*=\s*jpc_decode\s*\(\s*jpcstream\s*,\s*opts\s*\)\s*;"
)
new_pattern = re.compile(
    r"image\s*=\s*jas_image_decode\s*\(\s*jpcstream\s*,\s*"
    r"jas_image_strtofmt\s*\(\s*\"jpc\"\s*\)\s*,\s*opts\s*\)\s*;"
)

old_count = len(old_pattern.findall(text))
new_count = len(new_pattern.findall(text))

if old_count == 0 and new_count == 1:
    print("already-applied")
    raise SystemExit(0)

if old_count != 1 or new_count != 0:
    raise SystemExit(
        "ERRO: estado inesperado em dec_jpeg2000.c "
        f"(jpc_decode={old_count}, jas_image_decode={new_count}). "
        "Inspecione o arquivo manualmente antes de continuar."
    )

replacement = 'image=jas_image_decode(jpcstream, jas_image_strtofmt("jpc"), opts);'
path.write_text(old_pattern.sub(replacement, text, count=1))
print("applied")
PY
)" || return 1

  case "${result}" in
    already-applied)
      echo "Patch JasPer já aplicado: ${target}"
      ;;
    applied)
      if [[ ! -e "${backup}" ]]; then
        # The source has already been rewritten by Python above. Reconstructing a
        # pristine backup from the patched file is unsafe, therefore only create
        # backups before an explicit patch invocation. The build remains
        # repeatable without a backup and source control retains the original.
        echo "Patch JasPer aplicado: ${target}"
      else
        echo "Patch JasPer aplicado; backup existente preservado: ${backup}"
      fi
      WPS_DEC_JPEG2000_PATCH_CHANGED=true
      export WPS_DEC_JPEG2000_PATCH_CHANGED
      ;;
    *)
      echo "ERRO: resposta inesperada ao aplicar patch JasPer: ${result}" >&2
      return 1
      ;;
  esac

  cat > "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-patches.env.tmp" <<EOF
WPS_DEC_JPEG2000_PATCH=jas_image_decode
WPS_DEC_JPEG2000_PATCH_TARGET=${target}
EOF
  mv "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-patches.env.tmp" \
    "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-patches.env"
}
