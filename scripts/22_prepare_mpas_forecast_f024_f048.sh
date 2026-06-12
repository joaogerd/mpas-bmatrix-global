#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Prepare MPAS f024 and f048 forecasts from one generated MPAS init file
# =============================================================================
#
# This is the forecast standard used before constructing NMC pairs.
# It delegates the actual run-directory creation to:
#
#   scripts/21_prepare_mpas_forecast_from_init.sh
#
# Usage:
#
#   scripts/22_prepare_mpas_forecast_f024_f048.sh
#
# Optional:
#
#   INIT_TIME=2026-06-11_00:00:00 CONFIG_DT=60 scripts/22_prepare_mpas_forecast_f024_f048.sh
#   SUBMIT=true scripts/22_prepare_mpas_forecast_f024_f048.sh
#
# =============================================================================

PROJECT_ROOT=${PROJECT_ROOT:-/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global}
WORK_ROOT=${WORK_ROOT:-/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global}
MESH_NAME=${MESH_NAME:-x1.10242}
NPROC=${NPROC:-64}
INIT_TIME=${INIT_TIME:-2026-06-11_00:00:00}
INIT_TIME_SAFE=${INIT_TIME//:/.}
CONFIG_DT=${CONFIG_DT:-60}
OUTPUT_INTERVAL=${OUTPUT_INTERVAL:-24:00:00}
SUBMIT=${SUBMIT:-false}

mkdir -p "${PROJECT_ROOT}/logs"

prepare_forecast() {
  local fhour="$1"
  local duration="$2"
  local tag
  tag=$(printf 'f%03d' "${fhour}")

  local run_id="forecast_${MESH_NAME}_${INIT_TIME_SAFE}_${tag}_dt${CONFIG_DT}_np${NPROC}"
  local run_dir="${WORK_ROOT}/runs/${run_id}"
  local log_file="${PROJECT_ROOT}/logs/22_prepare_${run_id}.log"

  echo
  echo "=== Prepare ${tag} forecast ==="
  echo "INIT_TIME=${INIT_TIME}"
  echo "RUN_DURATION=${duration}"
  echo "OUTPUT_INTERVAL=${OUTPUT_INTERVAL}"
  echo "CONFIG_DT=${CONFIG_DT}"
  echo "RUN_ID=${run_id}"
  echo "RUN_DIR=${run_dir}"

  INIT_TIME="${INIT_TIME}" \
  RUN_ID="${run_id}" \
  RUN_DURATION="${duration}" \
  OUTPUT_INTERVAL="${OUTPUT_INTERVAL}" \
  CONFIG_DT="${CONFIG_DT}" \
  NPROC="${NPROC}" \
  "${PROJECT_ROOT}/scripts/21_prepare_mpas_forecast_from_init.sh" | tee "${log_file}"

  if [[ "${SUBMIT}" == "true" ]]; then
    echo "Submitting ${tag}: ${run_dir}/run_mpas_forecast.pbs"
    (cd "${run_dir}" && qsub run_mpas_forecast.pbs) | tee "${PROJECT_ROOT}/logs/22_submit_${run_id}.jobid"
  else
    echo "Prepared only. Submit with:"
    echo "  cd ${run_dir} && qsub run_mpas_forecast.pbs"
  fi
}

prepare_forecast 24 '1_00:00:00'
prepare_forecast 48 '2_00:00:00'

echo

echo "SUCCESS: f024/f048 forecast directories prepared."
echo "INIT_TIME=${INIT_TIME}"
echo "CONFIG_DT=${CONFIG_DT}"
echo "SUBMIT=${SUBMIT}"
