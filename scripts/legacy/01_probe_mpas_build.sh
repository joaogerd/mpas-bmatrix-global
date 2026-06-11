#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT=/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas
SOURCE_ROOT=/p/projetos/monan_das/joao.gerd/projects/MONAN-JEDI
BUILD_DIR=/p/projetos/monan_das/joao.gerd/work/MONAN-JEDI/build

BIN=${INSTALL_ROOT}/bin
SHARE=${INSTALL_ROOT}/share/MPAS

MPAS_ATM=${BIN}/mpas_atmosphere
MPAS_INIT=${BIN}/mpas_init_atmosphere
MPAS_TABLES=${BIN}/mpas_atmosphere_build_tables
TOOLBOX=${BIN}/mpasjedi_error_covariance_toolbox.x

GRID=/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/mesh/x1.10242.grid.nc
GRAPH=/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/graph/x1.10242.graph.info

echo "=== Ambiente ==="
echo "HOSTNAME=$(hostname)"
echo "USER=${USER}"
echo "PWD=$(pwd)"
echo "PATH=${PATH}"
echo
echo "which ncdump:"
which ncdump || true
echo
echo "which gpmetis:"
which gpmetis || true
echo
echo "which mpiexec:"
which mpiexec || true
echo
echo "which mpirun:"
which mpirun || true

echo
echo "=== MONAN-JEDI source ==="
echo "${SOURCE_ROOT}"
if [[ -d "${SOURCE_ROOT}/.git" ]]; then
  git -C "${SOURCE_ROOT}" rev-parse --show-toplevel
  git -C "${SOURCE_ROOT}" status --short
  echo "branch: $(git -C "${SOURCE_ROOT}" branch --show-current || true)"
  echo "commit: $(git -C "${SOURCE_ROOT}" rev-parse HEAD || true)"
fi

echo
echo "=== CMakeCache MPAS_DOUBLE_PRECISION ==="
if [[ -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  grep -H "MPAS_DOUBLE_PRECISION" "${BUILD_DIR}/CMakeCache.txt" || true
else
  echo "CMakeCache não encontrado em: ${BUILD_DIR}"
fi

echo
echo "=== MPAS/JEDI executáveis ==="
for f in "$MPAS_INIT" "$MPAS_ATM" "$MPAS_TABLES" "$TOOLBOX"; do
  echo
  echo "$f"
  if [[ -x "$f" ]]; then
    ls -lh "$f"
    file "$f" || true
  else
    echo "ERRO: executável não encontrado ou sem permissão: $f"
  fi
done

echo
echo "=== Bibliotecas dinâmicas principais: mpas_atmosphere ==="
ldd "$MPAS_ATM" | grep -Ei "not found|netcdf|pnetcdf|mpi|hdf5|eckit|fckit|oops|mpas|gsl|blas|lapack|fabric" || true

echo
echo "=== Bibliotecas dinâmicas principais: mpas_init_atmosphere ==="
ldd "$MPAS_INIT" | grep -Ei "not found|netcdf|pnetcdf|mpi|hdf5|eckit|fckit|oops|mpas|gsl|blas|lapack|fabric" || true

echo
echo "=== Share MPAS ==="
if [[ -d "$SHARE" ]]; then
  find "$SHARE" -maxdepth 3 -type f | sort | sed -n '1,220p'
else
  echo "ERRO: share MPAS não encontrado: $SHARE"
fi

echo
echo "=== Malha piloto ==="
ls -lh "$GRID"
ls -lh "$GRAPH"

echo
echo "=== Partições disponíveis da malha piloto ==="
ls -lh "${GRAPH}".part.* 2>/dev/null || echo "Nenhuma partição encontrada ainda."

echo
echo "=== ncdump da malha ==="
ncdump -h "$GRID" | sed -n '1,120p'

echo
echo "=== Resultado ==="
echo "Probe concluído."
