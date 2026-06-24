#!/usr/bin/env bash
#BOP
# !ROUTINE: 11_probe_wps_build_environment.sh
# !DESCRIPTION:
#   Performs a read-only readiness check for building WPS/ungrib.exe. It
#   validates the WPS source tree, required commands, NetCDF prefixes and the
#   JasPer, libpng and zlib directories needed for GRIB2 support. It never runs
#   WPS configure and does not modify the source tree or dependency installs.
# !INTERFACE:
#   bash scripts/wps/11_probe_wps_build_environment.sh
# !ARGUMENTS:
#   No positional arguments are accepted. Path variables from _common.sh apply.
#   WPS_DEP_SEARCH_ROOTS supplies additional colon-separated dependency roots;
#   JASPERINC, JASPERLIB, PNG_INC, PNG_LIB, ZLIB_INC and ZLIB_LIB override
#   automatic discovery. Set STRICT_WPS_PROBE=true to return a non-zero status
#   whenever a prerequisite is missing.
# !OUTPUTS:
#   Writes a diagnostic report to standard output. By default, missing
#   prerequisites are reported without causing failure; strict mode exits with
#   status 1. The script does not create or overwrite files.
# !NOTES:
#   Run this after loading the target compiler and NetCDF environment. Its
#   output can be used directly to select explicit dependency paths for the
#   build stage.
# !REVISION HISTORY:
#   24 Jun 2026 - Documentation added for the non-destructive WPS probe.
# !SEE ALSO:
#   _common.sh, 10_download_wps_assets.sh and 12_build_wps_ungrib.sh.
#EOP
set -euo pipefail

# Non-destructive probe of the environment required to compile WPS/ungrib.
# It never runs WPS configure and therefore can be safely executed repeatedly.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

STRICT_WPS_PROBE="${STRICT_WPS_PROBE:-false}"

echo "=== Contexto da verificação ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "user=${USER:-unknown}"
wps_show_layout
echo

echo "=== Código-fonte do WPS ==="
source_ok=true
for required_file in configure compile link_grib.csh ungrib/Variable_Tables/Vtable.GFS; do
  if [[ -e "${WPS_SRC_DIR}/${required_file}" ]]; then
    echo "OK: ${WPS_SRC_DIR}/${required_file}"
  else
    echo "AUSENTE: ${WPS_SRC_DIR}/${required_file}"
    source_ok=false
  fi
done
echo

echo "=== Comandos necessários ==="
commands_ok=true
for command_name in nc-config nf-config make perl csh python3 sed awk grep find; do
  if path="$(command -v "${command_name}" 2>/dev/null)"; then
    printf 'OK:      %-12s %s\n' "${command_name}" "${path}"
  else
    printf 'AUSENTE: %-12s\n' "${command_name}"
    commands_ok=false
  fi
done
echo

NC_PREFIX=""
NF_PREFIX=""
if command -v nc-config >/dev/null 2>&1; then
  NC_PREFIX="$(nc-config --prefix 2>/dev/null || true)"
fi
if command -v nf-config >/dev/null 2>&1; then
  NF_PREFIX="$(nf-config --prefix 2>/dev/null || true)"
fi

echo "=== NetCDF ==="
echo "NETCDF-C prefix=${NC_PREFIX:-AUSENTE}"
echo "NETCDF-Fortran prefix=${NF_PREFIX:-AUSENTE}"
if command -v nc-config >/dev/null 2>&1; then
  echo "--- nc-config --libs ---"
  nc-config --libs || true
fi
if command -v nf-config >/dev/null 2>&1; then
  echo "--- nf-config --flibs ---"
  nf-config --flibs || true
fi
echo

wps_collect_search_roots "${NC_PREFIX}" "${NF_PREFIX}"

echo "=== Raízes de busca de dependências GRIB2 ==="
if ((${#WPS_SEARCH_ROOTS[@]} == 0)); then
  echo "Nenhuma raiz local foi detectada."
  echo "Defina WPS_DEP_SEARCH_ROOTS=/caminho/para/install[:/outro/caminho] e execute novamente."
else
  printf '%s\n' "${WPS_SEARCH_ROOTS[@]}"
fi
echo

JASPERINC="${JASPERINC:-$(wps_find_include_root 'include/jasper/jasper.h')}"
JASPERLIB="${JASPERLIB:-$(wps_find_library_dir 'libjasper.so*' 'libjasper.a')}"
PNG_INC="${PNG_INC:-$(wps_find_include_root 'include/png.h')}"
PNG_LIB="${PNG_LIB:-$(wps_find_library_dir 'libpng.so*' 'libpng.a' 'libpng16.so*' 'libpng16.a')}"
ZLIB_INC="${ZLIB_INC:-$(wps_find_include_root 'include/zlib.h')}"
ZLIB_LIB="${ZLIB_LIB:-$(wps_find_library_dir 'libz.so*' 'libz.a')}"

echo "=== Dependências GRIB2 ==="
dependencies_ok=true
for variable_name in JASPERINC JASPERLIB PNG_INC PNG_LIB ZLIB_INC ZLIB_LIB; do
  value="${!variable_name:-}"
  if [[ -n "${value}" && -d "${value}" ]]; then
    printf 'OK:      %-10s %s\n' "${variable_name}" "${value}"
  else
    printf 'AUSENTE: %-10s %s\n' "${variable_name}" "${value:-}"
    dependencies_ok=false
  fi
done
echo

echo "=== Diagnóstico ==="
if "${source_ok}" && "${commands_ok}" && "${dependencies_ok}"; then
  echo "Ambiente aparentemente pronto para a compilação."
  echo "Execute: bash scripts/wps/12_build_wps_ungrib.sh"
else
  echo "O ambiente ainda não está completo para compilar o ungrib.exe."
  echo "Os caminhos JASPERINC, JASPERLIB, PNG_INC, PNG_LIB, ZLIB_INC e ZLIB_LIB podem ser informados explicitamente."
  echo "Para uma instalação Spack fora das raízes detectadas, informe WPS_DEP_SEARCH_ROOTS."
fi

if wps_is_true "${STRICT_WPS_PROBE}" && (! "${source_ok}" || ! "${commands_ok}" || ! "${dependencies_ok}"); then
  exit 1
fi
