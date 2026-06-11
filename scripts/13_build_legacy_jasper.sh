#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Build legacy JasPer 1.900.1 for WPS/ungrib
# =============================================================================
#
# WPS 4.6.0 ungrib can fail to link against modern JasPer 4.x because older WPS
# GRIB2 code expects legacy symbols such as jpc_decode. This script builds a
# local JasPer 1.900.1 installation and verifies that the expected symbol exists.
#
# Usage:
#
#   source scripts/load_jaci_env.sh
#   scripts/13_build_legacy_jasper.sh | tee logs/13_build_legacy_jasper.log
#
# Output:
#
#   /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/jasper-legacy/jasper-1.900.1-install
#
# =============================================================================

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
DATA_ROOT=${DATA_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global}
LEGACY_ROOT=${LEGACY_ROOT:-${DATA_ROOT}/external/jasper-legacy}
JASPER_VERSION=${JASPER_VERSION:-version-1.900.1}
JASPER_TARBALL=${JASPER_TARBALL:-jasper-${JASPER_VERSION}.tar.gz}
JASPER_URL=${JASPER_URL:-https://github.com/jasper-software/jasper/archive/refs/tags/${JASPER_VERSION}.tar.gz}
JASPER_SRC_DIR=${JASPER_SRC_DIR:-${LEGACY_ROOT}/jasper-${JASPER_VERSION}}
JASPER_PREFIX=${JASPER_PREFIX:-${LEGACY_ROOT}/jasper-1.900.1-install}
FORCE_JASPER_REBUILD=${FORCE_JASPER_REBUILD:-false}

mkdir -p "${PROJECT_ROOT}/logs" "${LEGACY_ROOT}"

echo "=== Build legacy JasPer configuration ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "LEGACY_ROOT=${LEGACY_ROOT}"
echo "JASPER_VERSION=${JASPER_VERSION}"
echo "JASPER_URL=${JASPER_URL}"
echo "JASPER_SRC_DIR=${JASPER_SRC_DIR}"
echo "JASPER_PREFIX=${JASPER_PREFIX}"
echo "FORCE_JASPER_REBUILD=${FORCE_JASPER_REBUILD}"
echo

if [[ -f "${JASPER_PREFIX}/include/jasper/jasper.h" ]] && \
   find "${JASPER_PREFIX}" -type f \( -name "libjasper.so*" -o -name "libjasper.a" \) | grep -q . && \
   [[ "${FORCE_JASPER_REBUILD}" != "true" ]]; then
  echo "Legacy JasPer already installed: ${JASPER_PREFIX}"
else
  if [[ ! -s "${LEGACY_ROOT}/${JASPER_TARBALL}" ]]; then
    echo "Downloading ${JASPER_URL}"
    if command -v curl >/dev/null 2>&1; then
      curl -L --fail --retry 5 -o "${LEGACY_ROOT}/${JASPER_TARBALL}.tmp" "${JASPER_URL}"
    elif command -v wget >/dev/null 2>&1; then
      wget -O "${LEGACY_ROOT}/${JASPER_TARBALL}.tmp" "${JASPER_URL}"
    else
      echo "ERRO: neither curl nor wget found."
      exit 1
    fi
    mv "${LEGACY_ROOT}/${JASPER_TARBALL}.tmp" "${LEGACY_ROOT}/${JASPER_TARBALL}"
  else
    echo "Already downloaded: ${LEGACY_ROOT}/${JASPER_TARBALL}"
  fi

  rm -rf "${JASPER_SRC_DIR}"
  tar -xzf "${LEGACY_ROOT}/${JASPER_TARBALL}" -C "${LEGACY_ROOT}"

  if [[ ! -d "${JASPER_SRC_DIR}" ]]; then
    echo "ERRO: expected source directory not found: ${JASPER_SRC_DIR}"
    echo "Contents under ${LEGACY_ROOT}:"
    find "${LEGACY_ROOT}" -maxdepth 2 -type d | sort
    exit 1
  fi

  cd "${JASPER_SRC_DIR}"

  echo
  echo "=== Source tree check ==="
  ls -lh | sed -n '1,120p'

  # The GitHub tag archive for JasPer 1.900.1 is autotools-based and does not
  # have a top-level CMakeLists.txt. Prefer an existing configure script; if the
  # archive does not contain it, try autoreconf.
  if [[ ! -x ./configure ]]; then
    if [[ -f configure.ac || -f configure.in ]]; then
      echo
      echo "No executable ./configure found; trying autoreconf -fi"
      if ! command -v autoreconf >/dev/null 2>&1; then
        echo "ERRO: autoreconf not found and ./configure is missing."
        echo "Install/load autoconf automake libtool or use a release tarball that includes ./configure."
        exit 1
      fi
      autoreconf -fi
    else
      echo "ERRO: no ./configure and no configure.ac/configure.in found."
      exit 1
    fi
  fi

  echo
  echo "=== Configure legacy JasPer ==="
  CC_VALUE=${CC:-/opt/cray/pe/craype/2.7.33/bin/cc}
  CFLAGS_VALUE=${CFLAGS:-"-O2 -fPIC"}

  ./configure \
    --prefix="${JASPER_PREFIX}" \
    --disable-opengl \
    --disable-libjpeg \
    CC="${CC_VALUE}" \
    CFLAGS="${CFLAGS_VALUE}" \
    2>&1 | tee "${PROJECT_ROOT}/logs/13_jasper_configure.log"

  echo
  echo "=== Build legacy JasPer ==="
  make -j 4 2>&1 | tee "${PROJECT_ROOT}/logs/13_jasper_make.log"

  echo
  echo "=== Install legacy JasPer ==="
  rm -rf "${JASPER_PREFIX}"
  make install 2>&1 | tee "${PROJECT_ROOT}/logs/13_jasper_install.log"
fi

echo

echo "=== Legacy JasPer result ==="
find "${JASPER_PREFIX}" -maxdepth 3 -type f \( \
  -path "*/include/jasper/jasper.h" -o \
  -name "libjasper.so*" -o \
  -name "libjasper.a" \
\) -print | sort

echo

echo "=== Check for jpc_decode symbol ==="
JASPER_SYMBOL_FOUND=false

while read -r lib; do
  [[ -n "${lib}" ]] || continue
  echo "Checking ${lib}"
  if nm -D "${lib}" 2>/dev/null | grep -q "jpc_decode"; then
    nm -D "${lib}" 2>/dev/null | grep "jpc_decode"
    JASPER_SYMBOL_FOUND=true
  elif nm "${lib}" 2>/dev/null | grep -q "jpc_decode"; then
    nm "${lib}" 2>/dev/null | grep "jpc_decode"
    JASPER_SYMBOL_FOUND=true
  fi
done < <(find "${JASPER_PREFIX}" -type f \( -name "libjasper.so*" -o -name "libjasper.a" \) | sort)

if [[ "${JASPER_SYMBOL_FOUND}" != "true" ]]; then
  echo "ERRO: jpc_decode was not found in the installed legacy JasPer library."
  exit 1
fi

echo

echo "SUCCESS: legacy JasPer is available for WPS/ungrib."
echo "Use these paths when rebuilding WPS:"
echo "export JASPERINC=${JASPER_PREFIX}/include"
if [[ -d "${JASPER_PREFIX}/lib64" ]]; then
  echo "export JASPERLIB=${JASPER_PREFIX}/lib64"
else
  echo "export JASPERLIB=${JASPER_PREFIX}/lib"
fi
