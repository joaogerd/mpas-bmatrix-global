#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
SOURCE_ROOT=/p/projetos/monan_das/joao.gerd/projects/MONAN-JEDI
BUILD_DIR=/p/projetos/monan_das/joao.gerd/work/MONAN-JEDI/build
INSTALL_ROOT=/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas

STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUTDIR="${PROJECT_ROOT}/logs/build_metadata_${STAMP}"

mkdir -p "${OUTDIR}"

{
  echo "timestamp_utc=${STAMP}"
  echo "hostname=$(hostname)"
  echo "user=${USER}"
  echo "source_root=${SOURCE_ROOT}"
  echo "build_dir=${BUILD_DIR}"
  echo "install_root=${INSTALL_ROOT}"
} > "${OUTDIR}/metadata.txt"

if [[ -d "${SOURCE_ROOT}/.git" ]]; then
  git -C "${SOURCE_ROOT}" rev-parse HEAD > "${OUTDIR}/git_head.txt" || true
  git -C "${SOURCE_ROOT}" branch --show-current > "${OUTDIR}/git_branch.txt" || true
  git -C "${SOURCE_ROOT}" status --short > "${OUTDIR}/git_status_short.txt" || true
  git -C "${SOURCE_ROOT}" submodule status --recursive > "${OUTDIR}/git_submodules.txt" || true
fi

if [[ -f "${BUILD_DIR}/CMakeCache.txt" ]]; then
  cp "${BUILD_DIR}/CMakeCache.txt" "${OUTDIR}/CMakeCache.txt"
  grep "MPAS_DOUBLE_PRECISION" "${BUILD_DIR}/CMakeCache.txt" > "${OUTDIR}/mpas_double_precision.txt" || true
fi

for exe in \
  "${INSTALL_ROOT}/bin/mpas_init_atmosphere" \
  "${INSTALL_ROOT}/bin/mpas_atmosphere" \
  "${INSTALL_ROOT}/bin/mpas_atmosphere_build_tables" \
  "${INSTALL_ROOT}/bin/mpasjedi_error_covariance_toolbox.x"
do
  base=$(basename "$exe")
  if [[ -x "$exe" ]]; then
    {
      echo "path=${exe}"
      ls -lh "$exe"
      file "$exe"
      echo
      echo "ldd:"
      ldd "$exe"
    } > "${OUTDIR}/${base}.txt" || true
  fi
done

module list > "${OUTDIR}/module_list.txt" 2>&1 || true
env | sort > "${OUTDIR}/env.txt"

echo "Build metadata saved in:"
echo "${OUTDIR}"
