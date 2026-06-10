#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Inventory sources needed to generate MPAS global initial conditions
# =============================================================================
#
# Goal:
#   Locate the local ingredients required by mpas_init_atmosphere:
#
#   1. MPAS init executable and templates
#   2. MPAS mesh/static/invariant candidates
#   3. WPS/ungrib tools
#   4. Vtables
#   5. WPS geographic data
#   6. GRIB files or WPS intermediate FILE:* files
#
# Usage:
#
#   source scripts/load_jaci_env.sh
#   scripts/09_inventory_initial_condition_sources.sh | tee logs/09_inventory_initial_condition_sources.log
#
# =============================================================================

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
MONAN_JEDI_SOURCE=/p/projetos/monan_das/joao.gerd/projects/MONAN-JEDI
INSTALL_ROOT=/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas
DATA_ROOT=/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global
USER_ROOT=/p/projetos/monan_das/joao.gerd

mkdir -p "${PROJECT_ROOT}/logs"

echo "=== Runtime context ==="
echo "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "hostname=$(hostname)"
echo "user=${USER}"
echo "pwd=$(pwd)"
echo

echo "=== Commands available in current environment ==="
for cmd in mpiexec mpirun ncdump ncks ncrename ncatted gpmetis ungrib.exe link_grib.csh; do
  printf '%-18s' "${cmd}:"
  command -v "${cmd}" || true
done

echo

echo "=== MPAS init executable ==="
for f in \
  "${INSTALL_ROOT}/bin/mpas_init_atmosphere" \
  "${INSTALL_ROOT}/bin/mpas_atmosphere" \
  "${INSTALL_ROOT}/bin/mpas_atmosphere_build_tables"; do
  echo
  echo "${f}"
  if [[ -x "${f}" ]]; then
    ls -lh "${f}"
  else
    echo "MISSING"
  fi
done

echo

echo "=== MPAS init templates from installed share ==="
INIT_SHARE=${INSTALL_ROOT}/share/MPAS/core_init_atmosphere
if [[ -d "${INIT_SHARE}" ]]; then
  find "${INIT_SHARE}" -maxdepth 2 -type f | sort
  echo
  echo "--- namelist.init_atmosphere key lines ---"
  grep -nE "config_|&|/" "${INIT_SHARE}/namelist.init_atmosphere" | sed -n '1,220p' || true
  echo
  echo "--- streams.init_atmosphere summary ---"
  grep -nE "stream|filename_template|input_interval|output_interval|contents|type=" "${INIT_SHARE}/streams.init_atmosphere" | sed -n '1,220p' || true
else
  echo "MISSING: ${INIT_SHARE}"
fi

echo

echo "=== Existing MPAS static/invariant/init candidates ==="
find "${USER_ROOT}" -type f \( \
  -name "static.nc" -o \
  -name "*static*.nc" -o \
  -name "*invariant*.nc" -o \
  -name "*.init.*.nc" -o \
  -name "init.nc" -o \
  -name "x1.*.init*.nc" \
\) 2>/dev/null | sort | sed -n '1,300p'

echo

echo "=== MPAS mesh candidates ==="
find "${USER_ROOT}" -type f \( \
  -name "x1.*.grid.nc" -o \
  -name "*.graph.info" -o \
  -name "*.graph.info.part.*" \
\) 2>/dev/null | sort | sed -n '1,300p'

echo

echo "=== WPS/ungrib candidates ==="
find "${USER_ROOT}" -type f \( \
  -name "ungrib.exe" -o \
  -name "link_grib.csh" -o \
  -name "geogrid.exe" -o \
  -name "metgrid.exe" \
\) 2>/dev/null | sort | sed -n '1,300p'

echo

echo "=== Vtable candidates ==="
find "${USER_ROOT}" -type f \( \
  -iname "Vtable*" -o \
  -iname "*Vtable*" \
\) 2>/dev/null | sort | sed -n '1,300p'

echo

echo "=== Geographic data directory candidates ==="
find "${USER_ROOT}" -type d \( \
  -iname "*geog*" -o \
  -iname "*wps_geog*" -o \
  -iname "*WPS_GEOG*" -o \
  -iname "*geog_data*" \
\) 2>/dev/null | sort | sed -n '1,300p'

echo

echo "=== GRIB candidates under user project/data areas ==="
find "${USER_ROOT}" -type f \( \
  -iname "*.grib" -o \
  -iname "*.grb" -o \
  -iname "*.grib2" -o \
  -iname "*.grb2" \
\) 2>/dev/null | sort | sed -n '1,300p'

echo

echo "=== WPS intermediate FILE:* candidates ==="
find "${USER_ROOT}" -type f -name "FILE:*" 2>/dev/null | sort | sed -n '1,300p'

echo

echo "=== Existing mpas_init_atmosphere examples in MONAN-JEDI tree ==="
if [[ -d "${MONAN_JEDI_SOURCE}" ]]; then
  grep -RIl "mpas_init_atmosphere\|init_atmosphere" "${MONAN_JEDI_SOURCE}" 2>/dev/null | sed -n '1,200p'
else
  echo "MISSING: ${MONAN_JEDI_SOURCE}"
fi

echo

echo "=== Summary hints ==="
echo "If WPS/ungrib and WPS geog data are missing, the next step is to choose/download a supported global analysis source."
echo "If an x1.10242 static/invariant file already exists, we can reuse it for the first IC-generation test."
echo "If FILE:* intermediate files exist for a cycle, we can test mpas_init_atmosphere without downloading GRIB first."
