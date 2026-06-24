#!/usr/bin/env bash
#BOP
# !ROUTINE: 12_build_wps_ungrib.sh
# !DESCRIPTION:
#   Configures and builds WPS/ungrib.exe using the portable installation layout.
#   It applies the required JasPer compatibility patch, prepares a local NetCDF
#   compatibility prefix with symbolic links, resolves GRIB2 dependencies,
#   updates configure.wps and records build provenance.
# !INTERFACE:
#   bash scripts/wps/12_build_wps_ungrib.sh
# !ARGUMENTS:
#   WPS_CONFIGURE_OPTION selects the numeric WPS configure option; FORCE_WPS_REBUILD
#   forces a clean build. NETCDF_COMPAT_DIR, WPS_LOG_DIR and the common layout and
#   GRIB2 dependency variables may override automatic defaults.
# !OUTPUTS:
#   WPS_SRC_DIR/ungrib.exe, build logs, NetCDF compatibility links and provenance files.
# !NOTES:
#   Existing valid executables are preserved unless their source is newer or
#   FORCE_WPS_REBUILD=true.
# !SEE ALSO:
#   _common.sh, _patches.sh, 10_download_wps_assets.sh and
#   14_patch_wps_dec_jpeg2000.sh.
#EOP
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"
# shellcheck source=_patches.sh
source "${SCRIPT_DIR}/_patches.sh"

FORCE_WPS_REBUILD="${FORCE_WPS_REBUILD:-false}"
WPS_CONFIGURE_OPTION="${WPS_CONFIGURE_OPTION:-1}"
NETCDF_COMPAT_DIR="${NETCDF_COMPAT_DIR:-${EXTERNAL_ROOT}/netcdf_compat}"
WPS_LOG_DIR="${WPS_LOG_DIR:-${LOG_ROOT}/wps}"

if [[ ! "${WPS_CONFIGURE_OPTION}" =~ ^[0-9]+$ ]]; then
  echo "ERRO: WPS_CONFIGURE_OPTION deve ser um número do menu ./configure." >&2
  exit 2
fi

if [[ ! -d "${WPS_SRC_DIR}" ]]; then
  echo "ERRO: diretório do WPS não encontrado: ${WPS_SRC_DIR}" >&2
  echo "Execute primeiro: bash scripts/wps/10_download_wps_assets.sh" >&2
  exit 1
fi

if [[ ! -f "${WPS_SRC_DIR}/configure" || ! -f "${WPS_SRC_DIR}/compile" ]]; then
  echo "ERRO: ${WPS_SRC_DIR} não parece ser uma árvore WPS válida." >&2
  exit 1
fi

mkdir -p "${WPS_LOG_DIR}"

# The patch uses Python and must run before deciding whether a pre-existing
# executable can be reused.
wps_require_command python3
wps_apply_dec_jpeg2000_patch
WPS_PATCH_TARGET="${WPS_SRC_DIR}/ungrib/src/ngl/g2/dec_jpeg2000.c"

echo "=== Configuração da compilação WPS/ungrib ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "user=${USER:-unknown}"
wps_show_layout
echo "NETCDF_COMPAT_DIR=${NETCDF_COMPAT_DIR}"
echo "WPS_LOG_DIR=${WPS_LOG_DIR}"
echo "WPS_CONFIGURE_OPTION=${WPS_CONFIGURE_OPTION}"
echo "FORCE_WPS_REBUILD=${FORCE_WPS_REBUILD}"
echo

# When the patch changed the source, or when the patched source is newer than a
# pre-existing executable, recompile automatically instead of silently reusing a
# stale ungrib.exe.
if [[ -x "${WPS_SRC_DIR}/ungrib.exe" ]] \
  && ! wps_is_true "${FORCE_WPS_REBUILD}" \
  && { wps_is_true "${WPS_DEC_JPEG2000_PATCH_CHANGED}" || [[ "${WPS_PATCH_TARGET}" -nt "${WPS_SRC_DIR}/ungrib.exe" ]]; }; then
  echo "O código-fonte WPS foi atualizado após a geração de ungrib.exe; recompilação será feita."
  FORCE_WPS_REBUILD=true
fi

if [[ -x "${WPS_SRC_DIR}/ungrib.exe" ]] && ! wps_is_true "${FORCE_WPS_REBUILD}"; then
  echo "ungrib.exe já existe e está consistente com o código-fonte; nenhuma recompilação foi necessária:"
  ls -lh "${WPS_SRC_DIR}/ungrib.exe"
  echo "Use FORCE_WPS_REBUILD=true para limpar, reconfigurar e recompilar."
  exit 0
fi

wps_require_command nc-config nf-config make perl csh python3 sed awk grep find

NC_PREFIX="$(nc-config --prefix)"
NF_PREFIX="$(nf-config --prefix)"

if [[ ! -d "${NC_PREFIX}" || ! -d "${NF_PREFIX}" ]]; then
  echo "ERRO: nc-config/nf-config retornaram prefixos inválidos." >&2
  echo "NC_PREFIX=${NC_PREFIX}" >&2
  echo "NF_PREFIX=${NF_PREFIX}" >&2
  exit 1
fi

link_directory_entries() {
  local source_dir="$1"
  local destination_dir="$2"
  shift 2

  [[ -d "${source_dir}" ]] || return 0
  local pattern file
  for pattern in "$@"; do
    while IFS= read -r -d '' file; do
      ln -sfn "${file}" "${destination_dir}/$(basename "${file}")"
    done < <(find "${source_dir}" -maxdepth 1 \( -type f -o -type l \) -name "${pattern}" -print0)
  done
}

refresh_netcdf_compat() {
  mkdir -p "${NETCDF_COMPAT_DIR}/include" "${NETCDF_COMPAT_DIR}/lib"

  # Remove only symlinks created by a previous run; regular files are preserved.
  find "${NETCDF_COMPAT_DIR}/include" -maxdepth 1 -type l -delete
  find "${NETCDF_COMPAT_DIR}/lib" -maxdepth 1 -type l -delete

  local include_dir library_dir file
  for include_dir in "${NC_PREFIX}/include" "${NF_PREFIX}/include"; do
    [[ -d "${include_dir}" ]] || continue
    while IFS= read -r -d '' file; do
      ln -sfn "${file}" "${NETCDF_COMPAT_DIR}/include/$(basename "${file}")"
    done < <(find "${include_dir}" -maxdepth 1 \( -type f -o -type l \) -print0)
  done

  for library_dir in "${NC_PREFIX}/lib" "${NC_PREFIX}/lib64" "${NF_PREFIX}/lib" "${NF_PREFIX}/lib64"; do
    link_directory_entries "${library_dir}" "${NETCDF_COMPAT_DIR}/lib" \
      'libnetcdf*' 'libhdf5*' 'libcurl*' 'libsz*' 'libz*'
  done

  cat > "${NETCDF_COMPAT_DIR}/.mpas-bmatrix-global-wps-netcdf-compat.env.tmp" <<EOF
NETCDF_C_PREFIX=${NC_PREFIX}
NETCDF_FORTRAN_PREFIX=${NF_PREFIX}
EOF
  mv "${NETCDF_COMPAT_DIR}/.mpas-bmatrix-global-wps-netcdf-compat.env.tmp" \
    "${NETCDF_COMPAT_DIR}/.mpas-bmatrix-global-wps-netcdf-compat.env"
}

echo "=== Prefixos NetCDF ==="
echo "NC_PREFIX=${NC_PREFIX}"
echo "NF_PREFIX=${NF_PREFIX}"
refresh_netcdf_compat
export NETCDF="${NETCDF_COMPAT_DIR}"
export NETCDFF="${NF_PREFIX}"
echo "NETCDF=${NETCDF}"
echo "NETCDFF=${NETCDFF}"
echo

wps_collect_search_roots "${NC_PREFIX}" "${NF_PREFIX}"

JASPERINC="${JASPERINC:-$(wps_find_include_root 'include/jasper/jasper.h')}"
JASPERLIB="${JASPERLIB:-$(wps_find_library_dir 'libjasper.so*' 'libjasper.a')}"
PNG_INC="${PNG_INC:-$(wps_find_include_root 'include/png.h')}"
PNG_LIB="${PNG_LIB:-$(wps_find_library_dir 'libpng.so*' 'libpng.a' 'libpng16.so*' 'libpng16.a')}"
ZLIB_INC="${ZLIB_INC:-$(wps_find_include_root 'include/zlib.h')}"
ZLIB_LIB="${ZLIB_LIB:-$(wps_find_library_dir 'libz.so*' 'libz.a')}"

export JASPERINC JASPERLIB PNG_INC PNG_LIB ZLIB_INC ZLIB_LIB

echo "=== Dependências GRIB2 ==="
missing_dependencies=false
for variable_name in JASPERINC JASPERLIB PNG_INC PNG_LIB ZLIB_INC ZLIB_LIB; do
  value="${!variable_name:-}"
  echo "${variable_name}=${value}"
  if [[ -z "${value}" || ! -d "${value}" ]]; then
    missing_dependencies=true
  fi
done

if "${missing_dependencies}"; then
  echo "ERRO: não foi possível localizar todas as dependências GRIB2." >&2
  echo "Defina WPS_DEP_SEARCH_ROOTS ou informe explicitamente JASPERINC/JASPERLIB/PNG_INC/PNG_LIB/ZLIB_INC/ZLIB_LIB." >&2
  exit 1
fi

if command -v ftn >/dev/null 2>&1; then
  WPS_FORTRAN_COMPILER="ftn"
else
  WPS_FORTRAN_COMPILER="${FC:-gfortran}"
fi
if command -v cc >/dev/null 2>&1; then
  WPS_C_COMPILER="cc"
else
  WPS_C_COMPILER="${CC:-gcc}"
fi
export WPS_FORTRAN_COMPILER WPS_C_COMPILER

cd "${WPS_SRC_DIR}"

echo
echo "=== Limpeza e configuração do WPS ==="
./clean -a >/dev/null 2>&1 || true
rm -f configure.wps configure.wps.original ungrib.exe ungrib/src/ungrib.exe

printf '%s\n' "${WPS_CONFIGURE_OPTION}" | ./configure --nowrf \
  2>&1 | tee "${WPS_LOG_DIR}/configure.log"

if [[ ! -f configure.wps ]]; then
  echo "ERRO: ./configure não gerou configure.wps." >&2
  exit 1
fi

cp configure.wps configure.wps.original

python3 - <<'PY'
from __future__ import annotations

import os
import re
from pathlib import Path

path = Path("configure.wps")
text = path.read_text()

def set_assignment(name: str, value: str, append_when_missing: bool = True) -> None:
    global text
    pattern = rf"^{re.escape(name)}\s*=.*$"
    replacement = f"{name:<16}=       {value}"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    elif append_when_missing:
        text += f"\n{replacement}\n"

for variable in ("SFC", "DM_FC", "FC", "LD"):
    set_assignment(variable, os.environ["WPS_FORTRAN_COMPILER"], append_when_missing=False)
for variable in ("SCC", "SCC_NOMPI", "DM_CC", "CC"):
    set_assignment(variable, os.environ["WPS_C_COMPILER"], append_when_missing=False)

compression_inc = " ".join(
    f"-I{os.environ[name]}" for name in ("JASPERINC", "PNG_INC", "ZLIB_INC")
)
compression_libs = " ".join(
    (
        f"-L{os.environ['JASPERLIB']}",
        "-ljasper",
        f"-L{os.environ['PNG_LIB']}",
        "-lpng",
        f"-L{os.environ['ZLIB_LIB']}",
        "-lz",
    )
)
set_assignment("COMPRESSION_INC", compression_inc)
set_assignment("COMPRESSION_LIBS", compression_libs)

path.write_text(text)
PY

echo "--- Linhas relevantes de configure.wps ---"
grep -nE '^(SFC|SCC|SCC_NOMPI|DM_FC|DM_CC|CC|FC|LD|COMPRESSION_INC|COMPRESSION_LIBS|NETCDF)[[:space:]]*=' \
  configure.wps || true

echo
echo "=== Compilação do ungrib ==="
./compile ungrib 2>&1 | tee "${WPS_LOG_DIR}/compile-ungrib.log"

if [[ ! -x "${WPS_SRC_DIR}/ungrib.exe" ]]; then
  echo "ERRO: ungrib.exe não foi criado." >&2
  echo "Últimas linhas do log:" >&2
  tail -120 "${WPS_LOG_DIR}/compile-ungrib.log" >&2 || true
  exit 1
fi

cat > "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-build.env.tmp" <<EOF
WPS_VERSION=${WPS_VERSION}
NETCDF_C_PREFIX=${NC_PREFIX}
NETCDF_FORTRAN_PREFIX=${NF_PREFIX}
JASPERINC=${JASPERINC}
JASPERLIB=${JASPERLIB}
PNG_INC=${PNG_INC}
PNG_LIB=${PNG_LIB}
ZLIB_INC=${ZLIB_INC}
ZLIB_LIB=${ZLIB_LIB}
WPS_CONFIGURE_OPTION=${WPS_CONFIGURE_OPTION}
WPS_DEC_JPEG2000_PATCH=jas_image_decode
EOF
mv "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-build.env.tmp" \
  "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-build.env"

echo
echo "=== Resultado ==="
ls -lh "${WPS_SRC_DIR}/ungrib.exe"
command -v file >/dev/null 2>&1 && file "${WPS_SRC_DIR}/ungrib.exe" || true
if command -v ldd >/dev/null 2>&1; then
  if ldd "${WPS_SRC_DIR}/ungrib.exe" | grep -q 'not found'; then
    echo "ERRO: há bibliotecas dinâmicas ausentes na saída de ldd." >&2
    ldd "${WPS_SRC_DIR}/ungrib.exe" >&2 || true
    exit 1
  fi
fi
echo "SUCESSO: ungrib.exe compilado em ${WPS_SRC_DIR}/ungrib.exe"
