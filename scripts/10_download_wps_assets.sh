#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Download WPS source and WPS geographical static data
# =============================================================================
#
# Default behavior:
#   - download WPS v4.6.0 source from the official wrf-model/WPS GitHub repo
#   - download the WPS V4 low-resolution mandatory geographical static data
#
# The low-resolution package is intended for the first MPAS init-atmosphere pilot.
# For production, use:
#
#   WPS_GEOG_PACKAGE=high scripts/10_download_wps_assets.sh
#
# WARNING:
#   The high-resolution mandatory package is much larger. The UCAR page reports
#   about 2.6 GB compressed and about 29 GB uncompressed.
#
# Usage:
#
#   scripts/10_download_wps_assets.sh
#   WPS_VERSION=v4.6.0 WPS_GEOG_PACKAGE=low scripts/10_download_wps_assets.sh
#   WPS_GEOG_PACKAGE=high scripts/10_download_wps_assets.sh
#
# Outputs:
#
#   /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-v4.6.0
#   /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS_GEOG/low_res_mandatory
#
# =============================================================================

DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
EXTERNAL_ROOT=${EXTERNAL_ROOT:-${DATA_ROOT}/external}
DOWNLOAD_ROOT=${DOWNLOAD_ROOT:-${EXTERNAL_ROOT}/downloads}

WPS_VERSION=${WPS_VERSION:-v4.6.0}
WPS_GEOG_PACKAGE=${WPS_GEOG_PACKAGE:-low}

WPS_TARBALL="WPS-${WPS_VERSION}.tar.gz"
WPS_URL="https://github.com/wrf-model/WPS/archive/refs/tags/${WPS_VERSION}.tar.gz"

case "${WPS_GEOG_PACKAGE}" in
  low)
    GEOG_URL="https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_low_res_mandatory.tar.gz"
    GEOG_TARBALL="geog_low_res_mandatory.tar.gz"
    GEOG_DIR="${EXTERNAL_ROOT}/WPS_GEOG/low_res_mandatory"
    ;;
  high)
    GEOG_URL="https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_high_res_mandatory.tar.gz"
    GEOG_TARBALL="geog_high_res_mandatory.tar.gz"
    GEOG_DIR="${EXTERNAL_ROOT}/WPS_GEOG/high_res_mandatory"
    ;;
  *)
    echo "ERRO: WPS_GEOG_PACKAGE deve ser 'low' ou 'high'. Valor recebido: ${WPS_GEOG_PACKAGE}"
    exit 1
    ;;
esac

WPS_SRC_PARENT="${EXTERNAL_ROOT}/WPS"
WPS_SRC_DIR="${WPS_SRC_PARENT}/WPS-${WPS_VERSION#v}"

mkdir -p "${DOWNLOAD_ROOT}" "${WPS_SRC_PARENT}" "${GEOG_DIR}"

fetch_file() {
  local url="$1"
  local out="$2"

  if [[ -s "${out}" ]]; then
    echo "Already downloaded: ${out}"
    return 0
  fi

  echo "Downloading: ${url}"
  echo "        to: ${out}"

  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 5 --retry-delay 10 -o "${out}.tmp" "${url}"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "${out}.tmp" "${url}"
  else
    echo "ERRO: nem curl nem wget encontrados no PATH."
    exit 1
  fi

  mv "${out}.tmp" "${out}"
}

echo "=== Download configuration ==="
echo "DATA_ROOT=${DATA_ROOT}"
echo "EXTERNAL_ROOT=${EXTERNAL_ROOT}"
echo "DOWNLOAD_ROOT=${DOWNLOAD_ROOT}"
echo "WPS_VERSION=${WPS_VERSION}"
echo "WPS_GEOG_PACKAGE=${WPS_GEOG_PACKAGE}"
echo "WPS_URL=${WPS_URL}"
echo "GEOG_URL=${GEOG_URL}"
echo

fetch_file "${WPS_URL}" "${DOWNLOAD_ROOT}/${WPS_TARBALL}"
fetch_file "${GEOG_URL}" "${DOWNLOAD_ROOT}/${GEOG_TARBALL}"

echo

echo "=== Extract WPS source ==="
if [[ -d "${WPS_SRC_DIR}" ]]; then
  echo "WPS source already extracted: ${WPS_SRC_DIR}"
else
  tar -xzf "${DOWNLOAD_ROOT}/${WPS_TARBALL}" -C "${WPS_SRC_PARENT}"
fi

# GitHub source archives extract as WPS-4.6.0 for tag v4.6.0.
if [[ ! -d "${WPS_SRC_DIR}" ]]; then
  echo "ERRO: diretório esperado do WPS não encontrado: ${WPS_SRC_DIR}"
  echo "Conteúdo de ${WPS_SRC_PARENT}:"
  find "${WPS_SRC_PARENT}" -maxdepth 2 -type d | sort
  exit 1
fi

echo

echo "=== Extract WPS geog data ==="
if find "${GEOG_DIR}" -mindepth 1 -maxdepth 1 | grep -q .; then
  echo "WPS geog directory already has content: ${GEOG_DIR}"
else
  tar -xzf "${DOWNLOAD_ROOT}/${GEOG_TARBALL}" -C "${GEOG_DIR}"
fi

echo

echo "=== Result ==="
echo "WPS_SRC_DIR=${WPS_SRC_DIR}"
echo "WPS_GEOG_DIR=${GEOG_DIR}"
echo

echo "Useful files:"
ls -lh "${WPS_SRC_DIR}/link_grib.csh" || true
ls -lh "${WPS_SRC_DIR}/ungrib/Variable_Tables/Vtable.GFS" || true

echo

echo "Geog top-level contents:"
find "${GEOG_DIR}" -mindepth 1 -maxdepth 2 -type d | sort | sed -n '1,120p'
