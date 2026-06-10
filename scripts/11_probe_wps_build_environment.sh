#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Probe WPS/ungrib build environment on JACI
# =============================================================================
#
# Goal:
#   Check whether the current JACI environment has enough pieces to compile
#   WPS ungrib.exe for GRIB2 input.
#
# Usage:
#
#   source scripts/load_jaci_env.sh
#   scripts/11_probe_wps_build_environment.sh | tee logs/11_probe_wps_build_environment.log
#
# =============================================================================

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
DATA_ROOT=/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global
EXTERNAL_ROOT=${DATA_ROOT}/external
WPS_SRC_DIR=${WPS_SRC_DIR:-${EXTERNAL_ROOT}/WPS/WPS-4.6.0}

mkdir -p "${PROJECT_ROOT}/logs"

echo "=== Runtime context ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "user=${USER}"
echo "pwd=$(pwd)"
echo "WPS_SRC_DIR=${WPS_SRC_DIR}"
echo

echo "=== WPS source check ==="
if [[ -d "${WPS_SRC_DIR}" ]]; then
  echo "FOUND: ${WPS_SRC_DIR}"
  ls -lh "${WPS_SRC_DIR}/configure" "${WPS_SRC_DIR}/compile" "${WPS_SRC_DIR}/link_grib.csh" 2>/dev/null || true
  ls -lh "${WPS_SRC_DIR}/ungrib/Variable_Tables/Vtable.GFS" 2>/dev/null || true
else
  echo "MISSING: ${WPS_SRC_DIR}"
fi

echo

echo "=== Core commands ==="
for cmd in gcc gfortran cc CC ftn mpicc mpifort cmake make gmake perl csh tcsh curl wget tar sed awk grep; do
  printf '%-12s' "${cmd}:"
  command -v "${cmd}" || true
done

echo

echo "=== NetCDF commands and config ==="
for cmd in nc-config nf-config ncdump; do
  printf '%-12s' "${cmd}:"
  command -v "${cmd}" || true
done

echo
if command -v nc-config >/dev/null 2>&1; then
  echo "--- nc-config ---"
  nc-config --prefix || true
  nc-config --libs || true
  nc-config --cflags || true
fi

echo
if command -v nf-config >/dev/null 2>&1; then
  echo "--- nf-config ---"
  nf-config --prefix || true
  nf-config --flibs || true
  nf-config --fflags || true
fi

echo

echo "=== GRIB2 dependency candidates in environment ==="
for var in JASPERLIB JASPERINC PNG_LIB PNG_INC ZLIB_LIB ZLIB_INC NETCDF NETCDFF; do
  printf '%-10s %s\n' "${var}=" "${!var-}"
done

echo

echo "=== Locate jasper/png/zlib libraries under loaded paths ==="
SEARCH_ROOTS=()

if command -v nc-config >/dev/null 2>&1; then
  NC_PREFIX=$(nc-config --prefix 2>/dev/null || true)
  [[ -n "${NC_PREFIX}" ]] && SEARCH_ROOTS+=("$(dirname "${NC_PREFIX}")")
fi

if [[ -n "${STACK_ROOT-}" ]]; then
  SEARCH_ROOTS+=("${STACK_ROOT}")
fi

SEARCH_ROOTS+=(
  /p/projetos/monan_das/joao.gerd/env/spack-stack
  /p/projetos/monan_das/joao.gerd/work/spack-stack-inpe-overlay-20260515T181917Z
)

# Deduplicate search roots.
printf '%s\n' "${SEARCH_ROOTS[@]}" | awk 'NF && !seen[$0]++' | while read -r root; do
  [[ -d "${root}" ]] || continue
  echo
  echo "--- ${root} ---"
  find "${root}" -type f \( \
    -name "libjasper.so" -o -name "libjasper.a" -o \
    -name "libpng.so" -o -name "libpng.a" -o -name "libpng16.so" -o -name "libpng16.a" -o \
    -name "libz.so" -o -name "libz.a" \
  \) 2>/dev/null | sort | sed -n '1,120p'
done

echo

echo "=== Locate headers under loaded paths ==="
printf '%s\n' "${SEARCH_ROOTS[@]}" | awk 'NF && !seen[$0]++' | while read -r root; do
  [[ -d "${root}" ]] || continue
  echo
  echo "--- ${root} ---"
  find "${root}" -type f \( \
    -path "*/include/jasper/jasper.h" -o \
    -path "*/include/png.h" -o \
    -path "*/include/zlib.h" \
  \) 2>/dev/null | sort | sed -n '1,120p'
done

echo

echo "=== WPS configure options preview ==="
if [[ -x "${WPS_SRC_DIR}/configure" ]]; then
  cd "${WPS_SRC_DIR}"
  printf '\n' | ./configure 2>&1 | sed -n '1,180p' || true
else
  echo "Cannot preview: configure not executable."
fi

echo

echo "=== Result hints ==="
echo "If nc-config/nf-config and jasper/png/zlib are found, create JASPERLIB/JASPERINC/PNG_LIB/PNG_INC/ZLIB_LIB/ZLIB_INC and run the WPS configure/compile step."
echo "If jasper is missing, install/load jasper or use a stack environment that provides it."
echo "If configure shows GNU serial options, use one of those for ungrib.exe."
