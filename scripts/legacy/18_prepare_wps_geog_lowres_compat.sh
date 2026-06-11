#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Prepare a low-resolution WPS_GEOG compatibility tree for MPAS init_atmosphere
# =============================================================================
#
# Problem:
#   MPAS init_atmosphere with config_topo_data='GMTED2010' looks for directories
#   such as topo_gmted2010_30s. The WPS low-resolution mandatory package provides
#   topo_gmted2010_5m instead. For a pilot/smoke test, create a compatibility
#   tree that aliases the available low-resolution directories to the higher-
#   resolution names expected by MPAS.
#
# Important:
#   This is suitable for a first functional test. For production-quality static
#   fields, use the full/high-resolution WPS_GEOG package.
#
# Usage:
#
#   scripts/18_prepare_wps_geog_lowres_compat.sh
#
# Then rerun prepare with:
#
#   WPS_GEOG_DIR=/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS_GEOG/mpas_lowres_compat \
#     scripts/16_prepare_mpas_init_from_gfs.sh
#
# =============================================================================

DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
SRC_DIR=${SRC_DIR:-${DATA_ROOT}/external/WPS_GEOG/low_res_mandatory/WPS_GEOG_LOW_RES}
COMPAT_DIR=${COMPAT_DIR:-${DATA_ROOT}/external/WPS_GEOG/mpas_lowres_compat}

mkdir -p "${COMPAT_DIR}"

echo "=== WPS_GEOG low-res compatibility tree ==="
echo "SRC_DIR=${SRC_DIR}"
echo "COMPAT_DIR=${COMPAT_DIR}"
echo

if [[ ! -d "${SRC_DIR}" ]]; then
  echo "ERRO: source WPS_GEOG low-res directory not found: ${SRC_DIR}"
  exit 1
fi

# Link all original low-res directories first.
find "${SRC_DIR}" -mindepth 1 -maxdepth 1 -type d | sort | while read -r d; do
  name=$(basename "${d}")
  ln -sfn "${d}" "${COMPAT_DIR}/${name}"
done

# Compatibility aliases for MPAS init_atmosphere defaults.
declare -A aliases=(
  [topo_gmted2010_30s]=topo_gmted2010_5m
  [soiltype_top_30s]=soiltype_top_5m
  [soiltype_bot_30s]=soiltype_bot_5m
  [modis_landuse_20class_30s]=modis_landuse_20class_5m_with_lakes
  [modis_landuse_20class_30s_with_lakes]=modis_landuse_20class_5m_with_lakes
  [greenfrac_fpar_modis_30s]=greenfrac_fpar_modis_5m
)

for dst in "${!aliases[@]}"; do
  src="${aliases[$dst]}"
  if [[ -d "${SRC_DIR}/${src}" ]]; then
    ln -sfn "${SRC_DIR}/${src}" "${COMPAT_DIR}/${dst}"
    echo "alias: ${dst} -> ${src}"
  else
    echo "warning: cannot create alias ${dst}; missing source ${SRC_DIR}/${src}"
  fi
done

echo

echo "=== Verify index files ==="
missing=false
for name in \
  topo_gmted2010_30s \
  soiltype_top_30s \
  soiltype_bot_30s \
  modis_landuse_20class_30s \
  modis_landuse_20class_30s_with_lakes \
  greenfrac_fpar_modis_30s; do
  if [[ -f "${COMPAT_DIR}/${name}/index" ]]; then
    echo "OK: ${name}/index"
  else
    echo "MISSING: ${name}/index"
    missing=true
  fi
done

echo

echo "Compatibility directory contents:"
find "${COMPAT_DIR}" -maxdepth 1 -type l -o -type d | sort | xargs -r ls -ld

if [[ "${missing}" == "true" ]]; then
  echo
  echo "WARNING: one or more expected compatibility aliases are missing."
  echo "The next MPAS init run may expose the next missing geog dataset."
else
  echo
  echo "SUCCESS: low-res compatibility tree prepared."
fi

echo "WPS_GEOG_DIR=${COMPAT_DIR}"
