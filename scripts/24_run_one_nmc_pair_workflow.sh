#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Run/prep one complete MPAS NMC pair workflow in an idempotent way
# =============================================================================
#
# Pair definition:
#   f048 from OLD_INIT_TIME and f024 from NEW_INIT_TIME, both valid at VALID_TIME.
#
# Default, when no dates are provided:
#   NEW_INIT_TIME = current UTC date at 00 UTC
#   OLD_INIT_TIME = NEW_INIT_TIME - 1 day
#   VALID_TIME    = NEW_INIT_TIME + 1 day
#
# The script is intentionally idempotent. It checks which files already exist,
# runs/prepares only the missing steps, and stops when it needs queued PBS jobs
# to finish. Run the same script again after jobs complete.
#
# Usage:
#   scripts/24_run_one_nmc_pair_workflow.sh
#   SUBMIT=true scripts/24_run_one_nmc_pair_workflow.sh
#
# Example:
#   OLD_INIT_TIME=2026-06-10_00:00:00 \
#   NEW_INIT_TIME=2026-06-11_00:00:00 \
#   VALID_TIME=2026-06-12_00:00:00 \
#   CONFIG_DT=60 \
#   SUBMIT=true \
#   scripts/24_run_one_nmc_pair_workflow.sh
# =============================================================================

PROJECT_ROOT=${PROJECT_ROOT:-/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global}
WORK_ROOT=${WORK_ROOT:-/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global}
DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
MESH_NAME=${MESH_NAME:-x1.10242}
NPROC=${NPROC:-64}
CONFIG_DT=${CONFIG_DT:-60}
SUBMIT=${SUBMIT:-false}

mkdir -p "${PROJECT_ROOT}/logs"
cd "${PROJECT_ROOT}"

# Resolve cycle dates and filename-safe strings.
eval "$(python3 - <<PY
from datetime import datetime, timedelta
import os
fmt = '%Y-%m-%d_%H:%M:%S'
new_s = os.environ.get('NEW_INIT_TIME')
old_s = os.environ.get('OLD_INIT_TIME')
valid_s = os.environ.get('VALID_TIME')
if new_s:
    new = datetime.strptime(new_s, fmt)
elif old_s:
    new = datetime.strptime(old_s, fmt) + timedelta(days=1)
else:
    now = datetime.utcnow()
    new = datetime(now.year, now.month, now.day, 0)
if old_s:
    old = datetime.strptime(old_s, fmt)
else:
    old = new - timedelta(days=1)
if valid_s:
    valid = datetime.strptime(valid_s, fmt)
else:
    valid = new + timedelta(days=1)
for name, dt in [('OLD', old), ('NEW', new), ('VALID', valid)]:
    s = dt.strftime(fmt)
    print(f'{name}_INIT_TIME={s}' if name != 'VALID' else f'VALID_TIME={s}')
    print(f'{name}_SAFE={s.replace(":", ".")}')
    print(f'{name}_GFS_DATE={dt:%Y%m%d}')
    print(f'{name}_GFS_CYCLE={dt:%H}')
PY
)"

OLD_RUN_ID="forecast_${MESH_NAME}_${OLD_SAFE}_f048_dt${CONFIG_DT}_np${NPROC}"
NEW_RUN_ID="forecast_${MESH_NAME}_${NEW_SAFE}_f024_dt${CONFIG_DT}_np${NPROC}"
OLD_FORECAST_DIR="${WORK_ROOT}/runs/${OLD_RUN_ID}"
NEW_FORECAST_DIR="${WORK_ROOT}/runs/${NEW_RUN_ID}"
OLD_F048="${OLD_FORECAST_DIR}/restart.${VALID_SAFE}.nc"
NEW_F024="${NEW_FORECAST_DIR}/restart.${VALID_SAFE}.nc"
OLD_INIT_DIR="${WORK_ROOT}/mpas_init/${MESH_NAME}/${OLD_INIT_TIME}_invariant_np${NPROC}"
NEW_INIT_DIR="${WORK_ROOT}/mpas_init/${MESH_NAME}/${NEW_INIT_TIME}_invariant_np${NPROC}"
OLD_INIT_FILE="${OLD_INIT_DIR}/${MESH_NAME}.init.${OLD_SAFE}.nc"
NEW_INIT_FILE="${NEW_INIT_DIR}/${MESH_NAME}.init.${NEW_SAFE}.nc"
OLD_WPS_DIR="${WORK_ROOT}/wps_ungrib/gfs.${OLD_GFS_DATE}${OLD_GFS_CYCLE}.f000"
NEW_WPS_DIR="${WORK_ROOT}/wps_ungrib/gfs.${NEW_GFS_DATE}${NEW_GFS_CYCLE}.f000"
OLD_WPS_FILE="${OLD_WPS_DIR}/FILE:${OLD_INIT_TIME:0:13}"
NEW_WPS_FILE="${NEW_WPS_DIR}/FILE:${NEW_INIT_TIME:0:13}"

step() { echo; echo "=== $* ==="; }
exists() { [[ -s "$1" ]]; }

submit_pbs_once() {
  local run_dir="$1"
  local pbs_file="$2"
  local tag="$3"
  local job_file="${run_dir}/${tag}.jobid"
  if [[ "${SUBMIT}" != "true" ]]; then
    echo "Prepared only. Submit with:"
    echo "  cd ${run_dir} && qsub ${pbs_file}"
    return 0
  fi
  if [[ -s "${job_file}" ]]; then
    local old_job
    old_job=$(cat "${job_file}" | tail -1)
    if qstat "${old_job}" >/dev/null 2>&1; then
      echo "Job already queued/running for ${tag}: ${old_job}"
      return 0
    fi
  fi
  echo "Submitting ${tag}: ${run_dir}/${pbs_file}"
  (cd "${run_dir}" && qsub "${pbs_file}") | tee "${job_file}"
}

print_config() {
  step "NMC workflow configuration"
  cat <<EOF
OLD_INIT_TIME=${OLD_INIT_TIME}
NEW_INIT_TIME=${NEW_INIT_TIME}
VALID_TIME=${VALID_TIME}
CONFIG_DT=${CONFIG_DT}
SUBMIT=${SUBMIT}
OLD_INIT_FILE=${OLD_INIT_FILE}
NEW_INIT_FILE=${NEW_INIT_FILE}
OLD_F048=${OLD_F048}
NEW_F024=${NEW_F024}
EOF
}

ensure_ungrib() {
  local label="$1" gfs_date="$2" gfs_cycle="$3" wps_file="$4"
  if exists "${wps_file}"; then
    echo "OK: ${label} WPS file exists: ${wps_file}"
    return 0
  fi
  step "Run GFS download and ungrib for ${label}"
  GFS_DATE="${gfs_date}" GFS_CYCLE="${gfs_cycle}" GFS_FHOUR=000 \
    scripts/15_download_gfs_and_run_ungrib.sh \
    | tee "logs/24_ungrib_${label}_${gfs_date}${gfs_cycle}.log"
}

ensure_init() {
  local label="$1" init_time="$2" init_file="$3" wps_dir="$4" wps_file="$5" init_dir="$6"
  if exists "${init_file}"; then
    echo "OK: ${label} init exists: ${init_file}"
    return 0
  fi
  step "Prepare MPAS init for ${label}"
  INIT_TIME="${init_time}" WPS_RUN_DIR="${wps_dir}" WPS_FILE="${wps_file}" \
    scripts/19_prepare_mpas_init_from_gfs_invariant.sh \
    | tee "logs/24_prepare_init_${label}_${init_time//[:]/}.log"
  RUN_DIR="${init_dir}" scripts/17_submit_mpas_init_from_gfs.sh \
    | tee "logs/24_submit_init_${label}_${init_time//[:]/}.log"
  echo "MPAS init submitted/prepared for ${label}. Run this script again after it finishes."
}

ensure_forecast() {
  local label="$1" init_time="$2" run_id="$3" duration="$4" expected_restart="$5" run_dir="$6"
  if exists "${expected_restart}"; then
    echo "OK: ${label} forecast exists: ${expected_restart}"
    return 0
  fi
  step "Prepare forecast ${label}"
  INIT_TIME="${init_time}" RUN_ID="${run_id}" RUN_DURATION="${duration}" \
    OUTPUT_INTERVAL="24:00:00" CONFIG_DT="${CONFIG_DT}" NPROC="${NPROC}" \
    scripts/21_prepare_mpas_forecast_from_init.sh \
    | tee "logs/24_prepare_forecast_${run_id}.log"
  submit_pbs_once "${run_dir}" run_mpas_forecast.pbs "forecast_${label}"
  echo "Forecast ${label} submitted/prepared. Run this script again after it finishes."
}

stage_pair() {
  step "Stage NMC pair"
  OLD_INIT_TIME="${OLD_INIT_TIME}" NEW_INIT_TIME="${NEW_INIT_TIME}" \
    VALID_TIME="${VALID_TIME}" CONFIG_DT="${CONFIG_DT}" NPROC="${NPROC}" \
    scripts/23_prepare_nmc_pair_from_forecasts.sh \
    | tee "logs/24_stage_nmc_pair_valid_${VALID_SAFE}.log"
}

print_config

ensure_ungrib OLD "${OLD_GFS_DATE}" "${OLD_GFS_CYCLE}" "${OLD_WPS_FILE}"
ensure_ungrib NEW "${NEW_GFS_DATE}" "${NEW_GFS_CYCLE}" "${NEW_WPS_FILE}"

ensure_init OLD "${OLD_INIT_TIME}" "${OLD_INIT_FILE}" "${OLD_WPS_DIR}" "${OLD_WPS_FILE}" "${OLD_INIT_DIR}"
ensure_init NEW "${NEW_INIT_TIME}" "${NEW_INIT_FILE}" "${NEW_WPS_DIR}" "${NEW_WPS_FILE}" "${NEW_INIT_DIR}"

if ! exists "${OLD_INIT_FILE}" || ! exists "${NEW_INIT_FILE}"; then
  echo
  echo "Waiting for missing init files. Re-run this script after MPAS init jobs finish."
  exit 0
fi

ensure_forecast OLD_f048 "${OLD_INIT_TIME}" "${OLD_RUN_ID}" '2_00:00:00' "${OLD_F048}" "${OLD_FORECAST_DIR}"
ensure_forecast NEW_f024 "${NEW_INIT_TIME}" "${NEW_RUN_ID}" '1_00:00:00' "${NEW_F024}" "${NEW_FORECAST_DIR}"

if ! exists "${OLD_F048}" || ! exists "${NEW_F024}"; then
  echo
  echo "Waiting for missing forecast restarts. Re-run this script after forecast jobs finish."
  exit 0
fi

stage_pair

echo
echo "SUCCESS: one NMC pair workflow is complete."
echo "OLD_F048=${OLD_F048}"
echo "NEW_F024=${NEW_F024}"
echo "VALID_TIME=${VALID_TIME}"
