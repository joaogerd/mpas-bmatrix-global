#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/p/projetos/monan_das/joao.gerd}"

echo "=== MPAS executáveis ==="
find "$ROOT" -type f \( \
  -name "atmosphere_model" -o \
  -name "init_atmosphere_model" \
\) 2>/dev/null | sort || true

echo
echo "=== MPAS-JEDI toolbox ==="
find "$ROOT" -type f -name "mpasjedi_error_covariance_toolbox.x" 2>/dev/null | sort || true

echo
echo "=== WPS / ungrib ==="
find "$ROOT" -type f \( \
  -name "ungrib.exe" -o \
  -name "link_grib.csh" \
\) 2>/dev/null | sort || true

echo
echo "=== malhas globais MPAS ==="
find "$ROOT" -type f \( \
  -name "x1.*.grid.nc" -o \
  -name "*.graph.info" \
\) 2>/dev/null | sort || true

echo
echo "=== namelists e streams ==="
find "$ROOT" -type f \( \
  -name "namelist.atmosphere*" -o \
  -name "streams.atmosphere*" -o \
  -name "namelist.init_atmosphere*" -o \
  -name "streams.init_atmosphere*" \
\) 2>/dev/null | sort || true
