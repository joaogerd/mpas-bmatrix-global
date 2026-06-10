#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Build WPS ungrib.exe on JACI
# =============================================================================
#
# Goal:
#   Compile only WPS ungrib.exe using the JACI MPAS-JEDI stack.
#
# Notes:
#   The WPS configure script expects a single NETCDF prefix, but this stack has
#   separate netcdf-c and netcdf-fortran prefixes. This script creates a small
#   compatibility prefix with symlinks to both installations and exports NETCDF
#   to that prefix before running WPS configure.
#
# Usage:
#
#   source scripts/load_jaci_env.sh
#   scripts/12_build_wps_ungrib.sh | tee logs/12_build_wps_ungrib.log
#
# Optional:
#
#   WPS_CONFIGURE_OPTION=1 scripts/12_build_wps_ungrib.sh
#   FORCE_WPS_REBUILD=true scripts/12_build_wps_ungrib.sh
#
# =============================================================================

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
EXTERNAL_ROOT=${EXTERNAL_ROOT:-${DATA_ROOT}/external}
WPS_SRC_DIR=${WPS_SRC_DIR:-${EXTERNAL_ROOT}/WPS/WPS-4.6.0}
NETCDF_COMPAT_DIR=${NETCDF_COMPAT_DIR:-${EXTERNAL_ROOT}/netcdf_compat}
FORCE_WPS_REBUILD=${FORCE_WPS_REBUILD:-false}
WPS_CONFIGURE_OPTION=${WPS_CONFIGURE_OPTION:-1}

mkdir -p "${PROJECT_ROOT}/logs"

echo "=== Build WPS ungrib configuration ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "user=${USER}"
echo "PROJECT_ROOT=${PROJECT_ROOT}"
echo "DATA_ROOT=${DATA_ROOT}"
echo "WPS_SRC_DIR=${WPS_SRC_DIR}"
echo "NETCDF_COMPAT_DIR=${NETCDF_COMPAT_DIR}"
echo "WPS_CONFIGURE_OPTION=${WPS_CONFIGURE_OPTION}"
echo "FORCE_WPS_REBUILD=${FORCE_WPS_REBUILD}"
echo

if [[ ! -d "${WPS_SRC_DIR}" ]]; then
  echo "ERRO: WPS source directory not found: ${WPS_SRC_DIR}"
  echo "Run scripts/10_download_wps_assets.sh first."
  exit 1
fi

if [[ -x "${WPS_SRC_DIR}/ungrib.exe" && "${FORCE_WPS_REBUILD}" != "true" ]]; then
  echo "ungrib.exe already exists:"
  ls -lh "${WPS_SRC_DIR}/ungrib.exe"
  echo
  echo "Set FORCE_WPS_REBUILD=true to rebuild."
  exit 0
fi

for cmd in nc-config nf-config make perl csh sed awk grep find; do
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "ERRO: required command not found in PATH: ${cmd}"
    exit 1
  fi
done

NC_PREFIX=$(nc-config --prefix)
NF_PREFIX=$(nf-config --prefix)

if [[ ! -d "${NC_PREFIX}" ]]; then
  echo "ERRO: netcdf-c prefix not found: ${NC_PREFIX}"
  exit 1
fi

if [[ ! -d "${NF_PREFIX}" ]]; then
  echo "ERRO: netcdf-fortran prefix not found: ${NF_PREFIX}"
  exit 1
fi

echo "=== NetCDF prefixes ==="
echo "NC_PREFIX=${NC_PREFIX}"
echo "NF_PREFIX=${NF_PREFIX}"
echo

# Build a compatibility NETCDF prefix expected by WPS.
rm -rf "${NETCDF_COMPAT_DIR}"
mkdir -p "${NETCDF_COMPAT_DIR}/include" "${NETCDF_COMPAT_DIR}/lib"

for inc in "${NC_PREFIX}/include" "${NF_PREFIX}/include"; do
  if [[ -d "${inc}" ]]; then
    find "${inc}" -maxdepth 1 -type f | while read -r f; do
      ln -sfn "${f}" "${NETCDF_COMPAT_DIR}/include/$(basename "$f")"
    done
  fi
done

for libdir in "${NC_PREFIX}/lib" "${NC_PREFIX}/lib64" "${NF_PREFIX}/lib" "${NF_PREFIX}/lib64"; do
  if [[ -d "${libdir}" ]]; then
    find "${libdir}" -maxdepth 1 -type f \( -name "libnetcdf*" -o -name "libhdf5*" -o -name "libcurl*" -o -name "libsz*" -o -name "libz*" \) | while read -r f; do
      ln -sfn "${f}" "${NETCDF_COMPAT_DIR}/lib/$(basename "$f")"
    done
    find "${libdir}" -maxdepth 1 -type l \( -name "libnetcdf*" -o -name "libhdf5*" -o -name "libcurl*" -o -name "libsz*" -o -name "libz*" \) | while read -r f; do
      target=$(readlink -f "${f}" || true)
      [[ -n "${target}" ]] && ln -sfn "${target}" "${NETCDF_COMPAT_DIR}/lib/$(basename "$f")"
    done
  fi
done

export NETCDF="${NETCDF_COMPAT_DIR}"
export NETCDFF="${NF_PREFIX}"

echo "=== NETCDF compatibility prefix ==="
echo "NETCDF=${NETCDF}"
echo "NETCDFF=${NETCDFF}"
ls -lh "${NETCDF_COMPAT_DIR}/include" | sed -n '1,80p'
ls -lh "${NETCDF_COMPAT_DIR}/lib" | sed -n '1,120p'
echo

# Detect GRIB2 dependencies. WPS uses JASPERINC/JASPERLIB plus PNG/ZLIB vars.
STACK_INSTALL_ROOT="/p/projetos/monan_das/joao.gerd/env/spack-stack/spack-stack-inpe-overlay-20260515T181917Z/install/gcc/12.3.0"

find_first_dir_with_file() {
  local root="$1"
  local pattern="$2"
  local file
  file=$(find "${root}" -type f -path "${pattern}" 2>/dev/null | head -1 || true)

  if [[ -z "${file}" ]]; then
    return 0
  fi

  # Special case: if the match is include/jasper/jasper.h,
  # WPS expects JASPERINC to be the include root, not include/jasper.
  if [[ "${file}" == */include/jasper/jasper.h ]]; then
    dirname "$(dirname "${file}")"
  else
    dirname "${file}"
  fi
}

find_first_lib_dir() {
  local root="$1"
  shift
  find "${root}" -type f \( "$@" \) 2>/dev/null | head -1 | xargs -r dirname
}

JASPERINC=${JASPERINC:-$(find_first_dir_with_file "${STACK_INSTALL_ROOT}" "*/include/jasper/jasper.h")}
PNG_INC=${PNG_INC:-$(find_first_dir_with_file "${STACK_INSTALL_ROOT}" "*/include/png.h")}
ZLIB_INC=${ZLIB_INC:-$(find_first_dir_with_file "${STACK_INSTALL_ROOT}" "*/include/zlib.h")}

# Search broader than libjasper.so/a because some installs may use versioned names.
JASPERLIB=${JASPERLIB:-$(find "${STACK_INSTALL_ROOT}" -type f \( -name "libjasper.so*" -o -name "libjasper.a" \) 2>/dev/null | head -1 | xargs -r dirname)}
PNG_LIB=${PNG_LIB:-$(find "${STACK_INSTALL_ROOT}" -type f \( -name "libpng.so*" -o -name "libpng.a" -o -name "libpng16.so*" -o -name "libpng16.a" \) 2>/dev/null | head -1 | xargs -r dirname)}
ZLIB_LIB=${ZLIB_LIB:-$(find "${STACK_INSTALL_ROOT}" -type f \( -name "libz.so*" -o -name "libz.a" \) 2>/dev/null | head -1 | xargs -r dirname)}

export JASPERINC JASPERLIB PNG_INC PNG_LIB ZLIB_INC ZLIB_LIB

echo "=== GRIB2 dependencies ==="
echo "JASPERINC=${JASPERINC}"
echo "JASPERLIB=${JASPERLIB}"
echo "PNG_INC=${PNG_INC}"
echo "PNG_LIB=${PNG_LIB}"
echo "ZLIB_INC=${ZLIB_INC}"
echo "ZLIB_LIB=${ZLIB_LIB}"
echo

missing=false
for var in JASPERINC JASPERLIB PNG_INC PNG_LIB ZLIB_INC ZLIB_LIB; do
  val="${!var}"
  if [[ -z "${val}" || ! -d "${val}" ]]; then
    echo "MISSING: ${var}=${val}"
    missing=true
  fi
done

if [[ "${missing}" == "true" ]]; then
  echo
  echo "ERRO: one or more GRIB2 dependency paths were not found."
  echo "Try loading/installing jasper/libpng/zlib, or pass explicit paths, e.g.:"
  echo "  JASPERINC=/path/include JASPERLIB=/path/lib PNG_INC=/path/include PNG_LIB=/path/lib ZLIB_INC=/path/include ZLIB_LIB=/path/lib scripts/12_build_wps_ungrib.sh"
  exit 1
fi

cd "${WPS_SRC_DIR}"

echo "=== Clean previous WPS build ==="
./clean -a >/dev/null 2>&1 || true
rm -f configure.wps ungrib.exe ungrib/src/ungrib.exe

echo

echo "=== Run WPS configure with --nowrf ==="
echo "Selecting WPS configure option: ${WPS_CONFIGURE_OPTION}"
printf '%s\n' "${WPS_CONFIGURE_OPTION}" | ./configure --nowrf 2>&1 | tee "${PROJECT_ROOT}/logs/12_wps_configure.log"

if [[ ! -f configure.wps ]]; then
  echo "ERRO: configure.wps was not generated."
  exit 1
fi

echo

echo "=== Patch configure.wps for JACI compiler wrappers ==="
cp configure.wps configure.wps.original

# Prefer Cray compiler wrappers when available. They use the loaded PrgEnv.
SFC_VALUE=$(command -v ftn >/dev/null 2>&1 && echo ftn || echo gfortran)
SCC_VALUE=$(command -v cc  >/dev/null 2>&1 && echo cc  || echo gcc)
SCC_NOMP_VALUE="${SCC_VALUE}"

python3 - <<PY
from pathlib import Path
import re

p = Path("configure.wps")
txt = p.read_text()

repls = {
    r"^SFC\s*=.*$": "SFC             =       ${SFC_VALUE}",
    r"^SCC\s*=.*$": "SCC             =       ${SCC_VALUE}",
    r"^DM_FC\s*=.*$": "DM_FC           =       ${SFC_VALUE}",
    r"^DM_CC\s*=.*$": "DM_CC           =       ${SCC_VALUE}",
    r"^CC\s*=.*$": "CC              =       ${SCC_VALUE}",
    r"^FC\s*=.*$": "FC              =       ${SFC_VALUE}",
    r"^LD\s*=.*$": "LD              =       ${SFC_VALUE}",
}

for pat, rep in repls.items():
    txt = re.sub(pat, rep, txt, flags=re.MULTILINE)

# Ensure include/lib flags know about explicitly detected GRIB2 dependencies.
# Keep the original configure choices and append include/lib flags via COMPRESSION_*.
extra_inc = f" -I${JASPERINC} -I${PNG_INC} -I${ZLIB_INC}"
extra_lib = f" -L${JASPERLIB} -L${PNG_LIB} -L${ZLIB_LIB}"

if "COMPRESSION_INC" in txt:
    txt = re.sub(r"^COMPRESSION_INC\s*=\s*(.*)$", lambda m: m.group(0) + extra_inc if extra_inc not in m.group(0) else m.group(0), txt, flags=re.MULTILINE)
else:
    txt += f"\nCOMPRESSION_INC = {extra_inc}\n"

if "COMPRESSION_LIBS" in txt:
    txt = re.sub(r"^COMPRESSION_LIBS\s*=\s*(.*)$", lambda m: m.group(0) + extra_lib if extra_lib not in m.group(0) else m.group(0), txt, flags=re.MULTILINE)
else:
    txt += f"\nCOMPRESSION_LIBS = {extra_lib} -ljasper -lpng -lz\n"

p.write_text(txt)
PY

echo "--- configure.wps compiler lines ---"
grep -nE "^(SFC|SCC|DM_FC|DM_CC|CC|FC|LD|COMPRESSION_INC|COMPRESSION_LIBS|NETCDF)\s*=" configure.wps || true

echo

echo "=== Compile ungrib ==="
./compile ungrib 2>&1 | tee "${PROJECT_ROOT}/logs/12_wps_compile_ungrib.log"

echo

echo "=== Build result ==="
if [[ -x "${WPS_SRC_DIR}/ungrib.exe" ]]; then
  ls -lh "${WPS_SRC_DIR}/ungrib.exe"
  file "${WPS_SRC_DIR}/ungrib.exe" || true
  ldd "${WPS_SRC_DIR}/ungrib.exe" | grep -Ei "not found|netcdf|jasper|png|zlib|hdf5|curl|gcc|gfortran|mpi|fabric" || true
  echo
  echo "SUCCESS: ungrib.exe built."
else
  echo "ERRO: ungrib.exe was not created."
  echo
  echo "Last lines from compile log:"
  tail -120 "${PROJECT_ROOT}/logs/12_wps_compile_ungrib.log" || true
  exit 1
fi
