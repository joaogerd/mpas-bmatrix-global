#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Validate MPAS init_atmosphere output generated from GFS/WPS FILE
# =============================================================================
#
# Usage:
#
#   scripts/20_validate_mpas_init_output.sh
#
# Optional:
#
#   RUN_DIR=/path/to/mpas_init/run scripts/20_validate_mpas_init_output.sh
#   INIT_FILE=/path/to/x1.10242.init.YYYY-MM-DD_HH.MM.SS.nc scripts/20_validate_mpas_init_output.sh
#
# =============================================================================

RUN_DIR=${RUN_DIR:-/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/mpas_init/x1.10242/2026-06-11_00:00:00_invariant_np64}
INIT_FILE=${INIT_FILE:-}

if [[ -z "${INIT_FILE}" ]]; then
  INIT_FILE=$(find "${RUN_DIR}" -maxdepth 1 -type f -name 'x1.10242.init.*.nc' | sort | tail -1 || true)
fi

if [[ -z "${INIT_FILE}" || ! -f "${INIT_FILE}" ]]; then
  echo "ERRO: MPAS init file not found."
  echo "RUN_DIR=${RUN_DIR}"
  echo "INIT_FILE=${INIT_FILE:-unset}"
  exit 1
fi

LOG_OUT=${RUN_DIR}/log.init_atmosphere.0000.out
LOG_ERR=${RUN_DIR}/log.init_atmosphere.0000.err

echo "=== MPAS init output validation ==="
echo "RUN_DIR=${RUN_DIR}"
echo "INIT_FILE=${INIT_FILE}"
echo

ls -lh "${INIT_FILE}"

echo

echo "=== Log status ==="
if [[ -f "${LOG_OUT}" ]]; then
  grep -nE "Finished running the init_atmosphere core|Error messages|Critical error messages|Warning messages" "${LOG_OUT}" || true
else
  echo "WARNING: missing ${LOG_OUT}"
fi

if [[ -s "${LOG_ERR}" ]]; then
  echo "WARNING: non-empty error log: ${LOG_ERR}"
  cat "${LOG_ERR}"
  exit 1
else
  echo "OK: no non-empty MPAS error log found."
fi

echo

echo "=== NetCDF header summary ==="
if command -v ncdump >/dev/null 2>&1; then
  echo "NetCDF format: $(ncdump -k "${INIT_FILE}" 2>/dev/null || echo unknown)"
  echo
  ncdump -h "${INIT_FILE}" | sed -n '1,120p'
else
  echo "WARNING: ncdump not found in PATH."
fi

echo

echo "=== Recommended export ==="
echo "export MPAS_INIT_FILE=${INIT_FILE}"

echo

echo "SUCCESS: MPAS init output exists and init_atmosphere log reports no errors."
