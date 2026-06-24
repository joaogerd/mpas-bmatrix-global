#!/usr/bin/env bash
#BOP
# !ROUTINE: _common.sh
# !DESCRIPTION:
#   Defines the shared helpers and portable directory layout used by the WPS
#   installation scripts. This file is a library: it must be sourced, not run
#   directly. It derives paths from the repository checkout and provides
#   deterministic helper functions for boolean parsing, prerequisite checks and
#   GRIB2 dependency discovery.
# !INTERFACE:
#   source scripts/wps/_common.sh
# !ARGUMENTS:
#   No positional arguments are consumed. The optional environment variables
#   REPO_ROOT, DATA_ROOT, EXTERNAL_ROOT, DOWNLOAD_ROOT, LOG_ROOT, WPS_VERSION,
#   WPS_SRC_DIR, WPS_DEP_SEARCH_ROOTS, STACK_ROOT, SPACK_ROOT and
#   SPACK_INSTALL_ROOT customize the resolved layout and dependency search.
# !OUTPUTS:
#   Exports REPO_ROOT, DATA_ROOT, EXTERNAL_ROOT, DOWNLOAD_ROOT, LOG_ROOT,
#   WPS_VERSION and WPS_SRC_DIR. It also exposes the WPS_SEARCH_ROOTS array
#   after wps_collect_search_roots is called.
# !NOTES:
#   The source guard makes repeated sourcing safe. The file intentionally does
#   not change shell options because the calling script owns that policy.
# !REVISION HISTORY:
#   24 Jun 2026 - Documentation added for the portable WPS installation API.
# !SEE ALSO:
#   1_download_wps_assets.sh, 2_probe_wps_build_environment.sh and
#   3_build_wps_ungrib.sh.
#EOP
# Shared helpers for the portable WPS scripts.
#
# This file is intentionally sourced by the numbered scripts. It does not alter
# shell options because the caller owns its execution policy.

if [[ -n "${_MPAS_BMATRIX_WPS_COMMON_LOADED:-}" ]]; then
  return 0 2>/dev/null || exit 0
fi
_MPAS_BMATRIX_WPS_COMMON_LOADED=1

WPS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="${REPO_ROOT:-$(cd "${WPS_SCRIPT_DIR}/../.." && pwd -P)}"

if [[ ! -f "${REPO_ROOT}/pyproject.toml" ]]; then
  echo "ERRO: não foi possível identificar a raiz do repositório." >&2
  echo "Defina REPO_ROOT=/caminho/para/mpas-bmatrix-global." >&2
  return 1 2>/dev/null || exit 1
fi

wps_default_data_root() {
  local parent workspace
  parent="$(dirname "${REPO_ROOT}")"
  if [[ "$(basename "${parent}")" == "projects" ]]; then
    workspace="$(dirname "${parent}")"
    printf '%s/data/%s\n' "${workspace}" "$(basename "${REPO_ROOT}")"
  else
    printf '%s/data\n' "${REPO_ROOT}"
  fi
}

DATA_ROOT="${DATA_ROOT:-$(wps_default_data_root)}"
EXTERNAL_ROOT="${EXTERNAL_ROOT:-${DATA_ROOT}/external}"
DOWNLOAD_ROOT="${DOWNLOAD_ROOT:-${EXTERNAL_ROOT}/downloads}"
LOG_ROOT="${LOG_ROOT:-${REPO_ROOT}/logs}"

WPS_VERSION="${WPS_VERSION:-v4.6.0}"
WPS_SRC_DIR="${WPS_SRC_DIR:-${EXTERNAL_ROOT}/WPS/WPS-${WPS_VERSION#v}}"

export REPO_ROOT DATA_ROOT EXTERNAL_ROOT DOWNLOAD_ROOT LOG_ROOT WPS_VERSION WPS_SRC_DIR

wps_is_true() {
  case "${1:-false}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

wps_require_command() {
  local command_name
  for command_name in "$@"; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
      echo "ERRO: comando obrigatório não encontrado no PATH: ${command_name}" >&2
      return 1
    fi
  done
}

wps_add_search_root() {
  local candidate="${1:-}"
  [[ -n "${candidate}" && -d "${candidate}" ]] || return 0

  local root
  for root in "${WPS_SEARCH_ROOTS[@]:-}"; do
    [[ "${root}" == "${candidate}" ]] && return 0
  done
  WPS_SEARCH_ROOTS+=("${candidate}")
}

# Populate WPS_SEARCH_ROOTS without assuming a particular user, account or Spack
# installation path. Explicit WPS_DEP_SEARCH_ROOTS takes precedence in the search
# order and accepts a colon-separated list.
wps_collect_search_roots() {
  WPS_SEARCH_ROOTS=()

  local root prefix parent
  if [[ -n "${WPS_DEP_SEARCH_ROOTS:-}" ]]; then
    local -a explicit_roots=()
    IFS=':' read -r -a explicit_roots <<< "${WPS_DEP_SEARCH_ROOTS}"
    for root in "${explicit_roots[@]}"; do
      wps_add_search_root "${root}"
    done
  fi

  for root in "${STACK_ROOT:-}" "${SPACK_ROOT:-}" "${SPACK_INSTALL_ROOT:-}"; do
    wps_add_search_root "${root}"
  done

  for prefix in "$@"; do
    [[ -n "${prefix:-}" && -d "${prefix}" ]] || continue
    wps_add_search_root "${prefix}"
    parent="$(dirname "${prefix}")"
    wps_add_search_root "${parent}"
    parent="$(dirname "${parent}")"
    wps_add_search_root "${parent}"
    parent="$(dirname "${parent}")"
    wps_add_search_root "${parent}"
  done
}

wps_find_include_root() {
  local header_path="$1"
  local root found
  for root in "${WPS_SEARCH_ROOTS[@]:-}"; do
    found="$(find "${root}" -type f -path "*/${header_path}" -print -quit 2>/dev/null || true)"
    [[ -n "${found}" ]] || continue

    if [[ "${header_path}" == "include/jasper/jasper.h" ]]; then
      dirname "$(dirname "${found}")"
    else
      dirname "${found}"
    fi
    return 0
  done
  return 0
}

wps_find_library_dir() {
  local root pattern found
  for root in "${WPS_SEARCH_ROOTS[@]:-}"; do
    for pattern in "${@:1}"; do
      found="$(find "${root}" \( -type f -o -type l \) -name "${pattern}" -print -quit 2>/dev/null || true)"
      [[ -n "${found}" ]] || continue
      dirname "${found}"
      return 0
    done
  done
  return 0
}

wps_show_layout() {
  echo "REPO_ROOT=${REPO_ROOT}"
  echo "DATA_ROOT=${DATA_ROOT}"
  echo "EXTERNAL_ROOT=${EXTERNAL_ROOT}"
  echo "DOWNLOAD_ROOT=${DOWNLOAD_ROOT}"
  echo "LOG_ROOT=${LOG_ROOT}"
  echo "WPS_VERSION=${WPS_VERSION}"
  echo "WPS_SRC_DIR=${WPS_SRC_DIR}"
}
