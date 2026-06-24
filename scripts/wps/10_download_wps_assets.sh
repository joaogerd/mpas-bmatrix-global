#!/usr/bin/env bash
#BOP
# !ROUTINE: 10_download_wps_assets.sh
# !DESCRIPTION:
#   Downloads and validates the WPS source archive and the selected WPS
#   geographical static-data package, then extracts them into the portable
#   installation layout. Existing valid archives and extracted content are
#   preserved by default, making normal re-execution safe.
# !INTERFACE:
#   bash scripts/wps/10_download_wps_assets.sh
# !ARGUMENTS:
#   No positional arguments are accepted. WPS_GEOG_PACKAGE selects the
#   geographical dataset (low or high). DATA_ROOT, EXTERNAL_ROOT,
#   DOWNLOAD_ROOT, WPS_SRC_DIR and WPS_VERSION customize paths and version.
#   FORCE_WPS_SOURCE_REFRESH=true or FORCE_WPS_GEOG_REFRESH=true explicitly
#   permit replacement of the respective extracted directories.
# !OUTPUTS:
#   Stores validated archives under DOWNLOAD_ROOT, extracts the WPS source at
#   WPS_SRC_DIR, extracts static geographical data below EXTERNAL_ROOT/WPS_GEOG
#   and writes .mpas-bmatrix-global-wps-assets.env in WPS_SRC_DIR.
# !NOTES:
#   curl is preferred and wget is used as a fallback. The script rejects an
#   invalid archive before it can replace a valid download. Refresh flags are
#   intentionally required before destructive replacement is performed.
# !REVISION HISTORY:
#   24 Jun 2026 - Documentation added for the portable WPS asset stage.
# !SEE ALSO:
#   _common.sh, 11_probe_wps_build_environment.sh and 12_build_wps_ungrib.sh.
#EOP
set -euo pipefail

# Download WPS source and the optional WPS geographical static-data package.
#
# The script derives all default paths from this checkout:
#   * <repo>/data/... for a generic clone
#   * <workspace>/data/<repo-name>/... when the checkout is under
#     <workspace>/projects/<repo-name>
#
# Override any location with DATA_ROOT, EXTERNAL_ROOT, DOWNLOAD_ROOT or WPS_SRC_DIR.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

WPS_GEOG_PACKAGE="${WPS_GEOG_PACKAGE:-low}"
FORCE_WPS_SOURCE_REFRESH="${FORCE_WPS_SOURCE_REFRESH:-false}"
FORCE_WPS_GEOG_REFRESH="${FORCE_WPS_GEOG_REFRESH:-false}"

WPS_TARBALL="WPS-${WPS_VERSION}.tar.gz"
WPS_URL="https://github.com/wrf-model/WPS/archive/refs/tags/${WPS_VERSION}.tar.gz"
WPS_SRC_PARENT="$(dirname "${WPS_SRC_DIR}")"

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
    echo "ERRO: WPS_GEOG_PACKAGE deve ser 'low' ou 'high'; recebido: ${WPS_GEOG_PACKAGE}" >&2
    exit 2
    ;;
esac

archive_is_valid() {
  tar -tzf "$1" >/dev/null 2>&1
}

fetch_archive() {
  local url="$1"
  local destination="$2"
  local temporary="${destination}.part"

  if [[ -f "${destination}" ]] && archive_is_valid "${destination}"; then
    echo "Arquivo já disponível e válido: ${destination}"
    return 0
  fi

  rm -f "${destination}" "${temporary}"
  echo "Baixando: ${url}"
  echo "      para: ${destination}"

  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --retry 5 --retry-delay 10 --output "${temporary}" "${url}"
  elif command -v wget >/dev/null 2>&1; then
    wget --output-document="${temporary}" "${url}"
  else
    echo "ERRO: é necessário ter curl ou wget no PATH." >&2
    exit 1
  fi

  if ! archive_is_valid "${temporary}"; then
    rm -f "${temporary}"
    echo "ERRO: download inválido ou incompleto: ${url}" >&2
    exit 1
  fi

  mv "${temporary}" "${destination}"
}

wps_source_is_valid() {
  [[ -f "${WPS_SRC_DIR}/configure" ]] \
    && [[ -f "${WPS_SRC_DIR}/compile" ]] \
    && [[ -f "${WPS_SRC_DIR}/link_grib.csh" ]] \
    && [[ -f "${WPS_SRC_DIR}/ungrib/Variable_Tables/Vtable.GFS" ]]
}

directory_has_content() {
  [[ -d "$1" ]] && find "$1" -mindepth 1 -maxdepth 1 -print -quit | grep -q .
}

mkdir -p "${DOWNLOAD_ROOT}" "${WPS_SRC_PARENT}"

echo "=== Configuração do download do WPS ==="
wps_show_layout
echo "WPS_GEOG_PACKAGE=${WPS_GEOG_PACKAGE}"
echo "WPS_GEOG_DIR=${GEOG_DIR}"
echo

fetch_archive "${WPS_URL}" "${DOWNLOAD_ROOT}/${WPS_TARBALL}"
fetch_archive "${GEOG_URL}" "${DOWNLOAD_ROOT}/${GEOG_TARBALL}"

echo
echo "=== Código-fonte do WPS ==="
if wps_source_is_valid && ! wps_is_true "${FORCE_WPS_SOURCE_REFRESH}"; then
  echo "Código-fonte já extraído e validado: ${WPS_SRC_DIR}"
else
  if [[ -e "${WPS_SRC_DIR}" ]]; then
    if ! wps_is_true "${FORCE_WPS_SOURCE_REFRESH}"; then
      echo "ERRO: ${WPS_SRC_DIR} existe, mas não contém uma árvore WPS válida." >&2
      echo "Use FORCE_WPS_SOURCE_REFRESH=true somente se puder substituir esse diretório." >&2
      exit 1
    fi
    rm -rf "${WPS_SRC_DIR}"
  fi

  tar -xzf "${DOWNLOAD_ROOT}/${WPS_TARBALL}" -C "${WPS_SRC_PARENT}"
  if ! wps_source_is_valid; then
    echo "ERRO: o arquivo foi extraído, mas a árvore WPS esperada não foi encontrada: ${WPS_SRC_DIR}" >&2
    exit 1
  fi
  echo "Código-fonte extraído: ${WPS_SRC_DIR}"
fi

echo
echo "=== Dados geográficos do WPS ==="
if directory_has_content "${GEOG_DIR}" && ! wps_is_true "${FORCE_WPS_GEOG_REFRESH}"; then
  echo "Dados geográficos já disponíveis: ${GEOG_DIR}"
else
  if [[ -e "${GEOG_DIR}" ]] && wps_is_true "${FORCE_WPS_GEOG_REFRESH}"; then
    rm -rf "${GEOG_DIR}"
  fi
  mkdir -p "${GEOG_DIR}"
  tar -xzf "${DOWNLOAD_ROOT}/${GEOG_TARBALL}" -C "${GEOG_DIR}"
  if ! directory_has_content "${GEOG_DIR}"; then
    echo "ERRO: a extração dos dados geográficos não produziu arquivos em ${GEOG_DIR}" >&2
    exit 1
  fi
  echo "Dados geográficos extraídos: ${GEOG_DIR}"
fi

cat > "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-assets.env.tmp" <<EOF
WPS_VERSION=${WPS_VERSION}
WPS_SOURCE_ARCHIVE=${DOWNLOAD_ROOT}/${WPS_TARBALL}
WPS_GEOG_PACKAGE=${WPS_GEOG_PACKAGE}
WPS_GEOG_DIR=${GEOG_DIR}
EOF
mv "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-assets.env.tmp" \
  "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-assets.env"

echo
echo "=== Resultado ==="
echo "WPS_SRC_DIR=${WPS_SRC_DIR}"
echo "WPS_GEOG_DIR=${GEOG_DIR}"
echo "Próximo passo: source scripts/load_jaci_env.sh && bash scripts/wps/11_probe_wps_build_environment.sh"
