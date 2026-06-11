#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Patch WPS dec_jpeg2000.c to avoid the obsolete jpc_decode symbol
# =============================================================================
#
# WPS 4.6.0 ungrib/src/ngl/g2/dec_jpeg2000.c calls the old/internal JasPer
# symbol jpc_decode(). Modern JasPer does not export it, and the local legacy
# JasPer 1.900.1 build on JACI did not export it either.
#
# Replace:
#
#   image = jpc_decode(jpcstream, opts);
#
# with the public JasPer API:
#
#   image = jas_image_decode(jpcstream, jas_image_strtofmt("jpc"), opts);
#
# Usage:
#
#   scripts/14_patch_wps_dec_jpeg2000.sh
#
# Then rebuild ungrib:
#
#   FORCE_WPS_REBUILD=true scripts/12_build_wps_ungrib.sh
#
# =============================================================================

DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
EXTERNAL_ROOT=${EXTERNAL_ROOT:-${DATA_ROOT}/external}
WPS_SRC_DIR=${WPS_SRC_DIR:-${EXTERNAL_ROOT}/WPS/WPS-4.6.0}
TARGET=${WPS_SRC_DIR}/ungrib/src/ngl/g2/dec_jpeg2000.c
BACKUP=${TARGET}.orig-jpc-decode

if [[ ! -f "${TARGET}" ]]; then
  echo "ERRO: target file not found: ${TARGET}"
  exit 1
fi

if [[ ! -f "${BACKUP}" ]]; then
  cp "${TARGET}" "${BACKUP}"
  echo "Backup created: ${BACKUP}"
else
  echo "Backup already exists: ${BACKUP}"
fi

python3 - <<PY
from pathlib import Path

p = Path("${TARGET}")
txt = p.read_text()

old = "image=jpc_decode(jpcstream,opts);"
new = "image=jas_image_decode(jpcstream, jas_image_strtofmt(\"jpc\"), opts);"

if new in txt:
    print("Patch already applied.")
elif old in txt:
    txt = txt.replace(old, new)
    p.write_text(txt)
    print("Patched dec_jpeg2000.c: jpc_decode -> jas_image_decode")
else:
    raise SystemExit("Expected jpc_decode call not found; inspect file manually: ${TARGET}")
PY

echo

echo "=== Patched lines ==="
grep -nE "jpc_decode|jas_image_decode|jas_image_strtofmt" "${TARGET}" || true
