#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Prepare MPAS init_atmosphere from GFS using an existing x1.10242 invariant file
# =============================================================================
#
# Why:
#   The low-resolution WPS_GEOG compatibility aliases are enough to pass terrain
#   and land-use interpolation, but may segfault in soil-category interpolation
#   when MPAS expects 30s STATSGO data. For a robust pilot, use an already
#   consolidated x1.10242 invariant/static file as the MPAS input stream and skip
#   static interpolation. Then mpas_init_atmosphere only interpolates the GFS
#   meteorological fields from the WPS FILE:* intermediate file.
#
# Usage:
#
#   source scripts/load_jaci_env.sh
#   scripts/19_prepare_mpas_init_from_gfs_invariant.sh
#
# Optional:
#
#   INVARIANT_FILE=/path/to/x1.10242.invariant.nc \
#     scripts/19_prepare_mpas_init_from_gfs_invariant.sh
#
# =============================================================================

PROJECT_ROOT=${PROJECT_ROOT:-/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global}
DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
WORK_ROOT=${WORK_ROOT:-/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global}

MPAS_INSTALL_ROOT=${MPAS_INSTALL_ROOT:-/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas}
MPAS_BIN_DIR=${MPAS_BIN_DIR:-${MPAS_INSTALL_ROOT}/bin}
MPAS_SHARE_DIR=${MPAS_SHARE_DIR:-${MPAS_INSTALL_ROOT}/share/MPAS}
MPAS_INIT_EXE=${MPAS_INIT_EXE:-${MPAS_BIN_DIR}/mpas_init_atmosphere}

MESH_NAME=${MESH_NAME:-x1.10242}
MESH_ROOT=${MESH_ROOT:-/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km}
GRAPH_FILE=${GRAPH_FILE:-${MESH_ROOT}/graph/${MESH_NAME}.graph.info}
PARTITION_DIR=${PARTITION_DIR:-${MESH_ROOT}/partitions}
NPROC=${NPROC:-64}

INVARIANT_FILE=${INVARIANT_FILE:-/p/projetos/monan_das/joao.gerd/data/mpasjedi_tutorial2024_testdata/MPAS_namelist_stream_physics_files/x1.10242.invariant.nc}

INIT_TIME=${INIT_TIME:-2026-06-11_00:00:00}
INIT_TIME_SAFE=${INIT_TIME//:/.}
WPS_RUN_DIR=${WPS_RUN_DIR:-${WORK_ROOT}/wps_ungrib/gfs.2026061100.f000}
WPS_FILE=${WPS_FILE:-${WPS_RUN_DIR}/FILE:2026-06-11_00}
RUN_DIR=${RUN_DIR:-${WORK_ROOT}/mpas_init/${MESH_NAME}/${INIT_TIME}_invariant_np${NPROC}}

mkdir -p "${PROJECT_ROOT}/logs" "${RUN_DIR}"

echo "=== MPAS init preparation from invariant configuration ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "PROJECT_ROOT=${PROJECT_ROOT}"
echo "DATA_ROOT=${DATA_ROOT}"
echo "WORK_ROOT=${WORK_ROOT}"
echo "MPAS_INIT_EXE=${MPAS_INIT_EXE}"
echo "MPAS_SHARE_DIR=${MPAS_SHARE_DIR}"
echo "MESH_NAME=${MESH_NAME}"
echo "INVARIANT_FILE=${INVARIANT_FILE}"
echo "GRAPH_FILE=${GRAPH_FILE}"
echo "PARTITION_DIR=${PARTITION_DIR}"
echo "NPROC=${NPROC}"
echo "INIT_TIME=${INIT_TIME}"
echo "INIT_TIME_SAFE=${INIT_TIME_SAFE}"
echo "WPS_RUN_DIR=${WPS_RUN_DIR}"
echo "WPS_FILE=${WPS_FILE}"
echo "RUN_DIR=${RUN_DIR}"
echo

required=(
  "${MPAS_INIT_EXE}"
  "${MPAS_SHARE_DIR}/core_init_atmosphere/namelist.init_atmosphere"
  "${MPAS_SHARE_DIR}/core_init_atmosphere/streams.init_atmosphere"
  "${INVARIANT_FILE}"
  "${GRAPH_FILE}"
  "${PARTITION_DIR}/${MESH_NAME}.graph.info.part.${NPROC}"
  "${WPS_FILE}"
)

for item in "${required[@]}"; do
  if [[ ! -e "${item}" ]]; then
    echo "ERRO: required input not found: ${item}"
    exit 1
  fi
done

cd "${RUN_DIR}"

echo "=== Link/copy inputs ==="
ln -sfn "${MPAS_INIT_EXE}" mpas_init_atmosphere

# Keep the stream filename as x1.10242.grid.nc for compatibility with existing
# PBS/templates, but point it to the invariant/static file.
ln -sfn "${INVARIANT_FILE}" "${MESH_NAME}.grid.nc"

ln -sfn "${GRAPH_FILE}" "${MESH_NAME}.graph.info"
ln -sfn "${PARTITION_DIR}/${MESH_NAME}.graph.info.part.${NPROC}" "${MESH_NAME}.graph.info.part.${NPROC}"
ln -sfn "${WPS_FILE}" "$(basename "${WPS_FILE}")"

cp "${MPAS_SHARE_DIR}/core_init_atmosphere/namelist.init_atmosphere" namelist.init_atmosphere
cp "${MPAS_SHARE_DIR}/core_init_atmosphere/streams.init_atmosphere" streams.init_atmosphere

echo "Linked inputs:"
ls -lh mpas_init_atmosphere "${MESH_NAME}.grid.nc" "${MESH_NAME}.graph.info" "${MESH_NAME}.graph.info.part.${NPROC}" "$(basename "${WPS_FILE}")"
echo

echo "=== Patch namelist.init_atmosphere ==="
python3 - <<PY
from pathlib import Path
import re

p = Path("namelist.init_atmosphere")
txt = p.read_text()

replacements = {
    "config_init_case": "7",
    "config_start_time": "'${INIT_TIME}'",
    "config_stop_time": "'${INIT_TIME}'",
    "config_nvertlevels": "55",
    "config_met_prefix": "'FILE'",
    "config_sfc_prefix": "'FILE'",
    "config_fg_interval": "21600",
    "config_use_spechumd": ".false.",

    # Critical difference from scripts/16_prepare_mpas_init_from_gfs.sh:
    # use existing static/invariant fields instead of recomputing WPS_GEOG static fields.
    "config_static_interp": ".false.",
    "config_native_gwd_static": ".false.",
    "config_native_gwd_gsl_static": ".false.",
    "config_vertical_grid": ".true.",
    "config_met_interp": ".true.",
    "config_block_decomp_file_prefix": "'${MESH_NAME}.graph.info.part.'",
}

for key, value in replacements.items():
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*).*$", re.MULTILINE)
    if pattern.search(txt):
        txt = pattern.sub(rf"\g<1>{value}", txt)
    else:
        txt = txt.replace("/\n", f"    {key} = {value}\n/\n", 1)

p.write_text(txt)
PY

grep -nE "config_(init_case|start_time|stop_time|nvertlevels|met_prefix|sfc_prefix|fg_interval|use_spechumd|static_interp|native_gwd_static|native_gwd_gsl_static|vertical_grid|met_interp|block_decomp_file_prefix)" namelist.init_atmosphere || true

echo

echo "=== Patch streams.init_atmosphere ==="
python3 - <<PY
from pathlib import Path
import re

p = Path("streams.init_atmosphere")
txt = p.read_text()

outname = "${MESH_NAME}.init.${INIT_TIME_SAFE}.nc"

txt = txt.replace("x1.40962", "${MESH_NAME}")
txt = txt.replace("${MESH_NAME}.init.nc", outname)
txt = re.sub(r"${MESH_NAME}\.init\.[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9:.]+\.nc", outname, txt)
txt = re.sub(r"${MESH_NAME}\.init\.nc", outname, txt)

p.write_text(txt)
PY

grep -nE "${MESH_NAME}|filename_template|input|output|immutable|static|surface|lbc" streams.init_atmosphere | sed -n '1,160p' || true

echo

echo "=== Prepared run directory ==="
find "${RUN_DIR}" -maxdepth 1 -type f -o -type l | sort -V | xargs -r ls -lh

echo

echo "SUCCESS: MPAS init run directory prepared from invariant/static file."
echo "RUN_DIR=${RUN_DIR}"
echo "Expected output candidate: ${RUN_DIR}/${MESH_NAME}.init.${INIT_TIME_SAFE}.nc"
