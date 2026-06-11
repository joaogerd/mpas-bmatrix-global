#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Download one GFS 0.25 cycle from NOMADS and run WPS ungrib
# =============================================================================
#
# Goal:
#   Create the first WPS intermediate FILE:* file for MPAS init_atmosphere.
#
# Defaults:
#   GFS_DATE: current UTC date, YYYYMMDD
#   GFS_CYCLE: 00
#   GFS_FHOUR: 000
#
# Usage:
#
#   source scripts/load_jaci_env.sh
#   scripts/15_download_gfs_and_run_ungrib.sh
#
#   GFS_DATE=20260611 GFS_CYCLE=00 GFS_FHOUR=000 \
#     scripts/15_download_gfs_and_run_ungrib.sh
#
# Output:
#   work/mpas-bmatrix-global/wps_ungrib/gfs.YYYYMMDDHH.fFFF/FILE:YYYY-MM-DD_HH
#
# =============================================================================

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
WORK_ROOT=${WORK_ROOT:-/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global}

WPS_SRC_DIR=${WPS_SRC_DIR:-${DATA_ROOT}/external/WPS/WPS-4.6.0}
UNGRIB_EXE=${UNGRIB_EXE:-${WPS_SRC_DIR}/ungrib.exe}
LINK_GRIB=${LINK_GRIB:-${WPS_SRC_DIR}/link_grib.csh}
VTABLE_GFS=${VTABLE_GFS:-${WPS_SRC_DIR}/ungrib/Variable_Tables/Vtable.GFS}

GFS_DATE=${GFS_DATE:-$(date -u +%Y%m%d)}
GFS_CYCLE=${GFS_CYCLE:-00}
GFS_FHOUR=${GFS_FHOUR:-000}

RUN_ID="gfs.${GFS_DATE}${GFS_CYCLE}.f${GFS_FHOUR}"
GRIB_DIR=${GRIB_DIR:-${DATA_ROOT}/external/gfs/${GFS_DATE}/${GFS_CYCLE}}
RUN_DIR=${RUN_DIR:-${WORK_ROOT}/wps_ungrib/${RUN_ID}}

GFS_FILE="gfs.t${GFS_CYCLE}z.pgrb2.0p25.f${GFS_FHOUR}"
GFS_URL="https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?dir=%2Fgfs.${GFS_DATE}%2F${GFS_CYCLE}%2Fatmos&file=${GFS_FILE}&all_lev=on&all_var=on"

mkdir -p "${PROJECT_ROOT}/logs" "${GRIB_DIR}" "${RUN_DIR}"

echo "=== GFS/ungrib configuration ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "PROJECT_ROOT=${PROJECT_ROOT}"
echo "DATA_ROOT=${DATA_ROOT}"
echo "WORK_ROOT=${WORK_ROOT}"
echo "WPS_SRC_DIR=${WPS_SRC_DIR}"
echo "UNGRIB_EXE=${UNGRIB_EXE}"
echo "LINK_GRIB=${LINK_GRIB}"
echo "VTABLE_GFS=${VTABLE_GFS}"
echo "GFS_DATE=${GFS_DATE}"
echo "GFS_CYCLE=${GFS_CYCLE}"
echo "GFS_FHOUR=${GFS_FHOUR}"
echo "GRIB_DIR=${GRIB_DIR}"
echo "RUN_DIR=${RUN_DIR}"
echo "GFS_URL=${GFS_URL}"
echo

for f in "${UNGRIB_EXE}" "${LINK_GRIB}" "${VTABLE_GFS}"; do
  if [[ ! -e "${f}" ]]; then
    echo "ERRO: required file not found: ${f}"
    exit 1
  fi
done

if [[ ! -x "${UNGRIB_EXE}" ]]; then
  echo "ERRO: ungrib is not executable: ${UNGRIB_EXE}"
  exit 1
fi

GRIB_PATH="${GRIB_DIR}/${GFS_FILE}"

if [[ -s "${GRIB_PATH}" ]]; then
  echo "Already downloaded: ${GRIB_PATH}"
else
  echo "Downloading GFS GRIB2 file..."
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 5 --retry-delay 10 -o "${GRIB_PATH}.tmp" "${GFS_URL}"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "${GRIB_PATH}.tmp" "${GFS_URL}"
  else
    echo "ERRO: neither curl nor wget found."
    exit 1
  fi
  mv "${GRIB_PATH}.tmp" "${GRIB_PATH}"
fi

ls -lh "${GRIB_PATH}"

echo

echo "=== Prepare WPS ungrib run directory ==="
cd "${RUN_DIR}"
rm -f GRIBFILE.* FILE:* PFILE:* Vtable namelist.wps ungrib.exe link_grib.csh

ln -s "${VTABLE_GFS}" Vtable
ln -s "${UNGRIB_EXE}" ungrib.exe
ln -s "${LINK_GRIB}" link_grib.csh

./link_grib.csh "${GRIB_PATH}"

python3 - <<PY
from datetime import datetime, timedelta
from pathlib import Path

date = "${GFS_DATE}"
cycle = "${GFS_CYCLE}"
fhour = int("${GFS_FHOUR}")
start = datetime.strptime(date + cycle, "%Y%m%d%H") + timedelta(hours=fhour)
end = start

content = f"""&share
 wrf_core = 'ARW',
 max_dom = 1,
 start_date = '{start:%Y-%m-%d_%H}:00:00',
 end_date   = '{end:%Y-%m-%d_%H}:00:00',
 interval_seconds = 21600,
 io_form_geogrid = 2,
/

&ungrib
 out_format = 'WPS',
 prefix = 'FILE',
/

&metgrid
 fg_name = 'FILE',
 io_form_metgrid = 2,
/
"""
Path("namelist.wps").write_text(content)
print(content)
PY

echo

echo "=== Run ungrib ==="
./ungrib.exe 2>&1 | tee "${PROJECT_ROOT}/logs/15_ungrib_${RUN_ID}.log"

echo

echo "=== WPS intermediate result ==="
find "${RUN_DIR}" -maxdepth 1 -type f -name 'FILE:*' -ls | sort || true

if ! find "${RUN_DIR}" -maxdepth 1 -type f -name 'FILE:*' | grep -q .; then
  echo "ERRO: no FILE:* was produced by ungrib."
  exit 1
fi

echo

echo "SUCCESS: WPS intermediate file generated."
echo "RUN_DIR=${RUN_DIR}"
