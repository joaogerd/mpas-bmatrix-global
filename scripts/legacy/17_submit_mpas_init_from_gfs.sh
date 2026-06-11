#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Submit MPAS init_atmosphere run prepared from GFS/WPS FILE
# =============================================================================
#
# Usage:
#
#   scripts/17_submit_mpas_init_from_gfs.sh
#
# Optional:
#
#   RUN_DIR=/path/to/run NPROC=64 scripts/17_submit_mpas_init_from_gfs.sh
#
# =============================================================================

PROJECT_ROOT=${PROJECT_ROOT:-/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global}
RUN_DIR=${RUN_DIR:-/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/mpas_init/x1.10242/2026-06-11_00:00:00_np64}
NPROC=${NPROC:-64}
PBS_TEMPLATE=${PBS_TEMPLATE:-${PROJECT_ROOT}/templates/pbs/run_mpas_init_from_gfs.pbs}
PBS_FILE=${PBS_FILE:-${RUN_DIR}/run_mpas_init_from_gfs.pbs}

mkdir -p "${PROJECT_ROOT}/logs" "${RUN_DIR}"

if [[ ! -f "${PBS_TEMPLATE}" ]]; then
  echo "ERRO: PBS template not found: ${PBS_TEMPLATE}"
  exit 1
fi

for f in \
  "${RUN_DIR}/mpas_init_atmosphere" \
  "${RUN_DIR}/namelist.init_atmosphere" \
  "${RUN_DIR}/streams.init_atmosphere" \
  "${RUN_DIR}/x1.10242.grid.nc" \
  "${RUN_DIR}/x1.10242.graph.info" \
  "${RUN_DIR}/x1.10242.graph.info.part.${NPROC}"; do
  if [[ ! -e "${f}" ]]; then
    echo "ERRO: required run file not found: ${f}"
    echo "Run scripts/16_prepare_mpas_init_from_gfs.sh or scripts/19_prepare_mpas_init_from_gfs_invariant.sh first."
    exit 1
  fi
done

if ! compgen -G "${RUN_DIR}/FILE:*" >/dev/null; then
  echo "ERRO: no FILE:* found in ${RUN_DIR}"
  echo "Run scripts/15_download_gfs_and_run_ungrib.sh first."
  exit 1
fi

cp "${PBS_TEMPLATE}" "${PBS_FILE}"

# Make the submitted PBS file explicit/reproducible. Do not depend on qsub
# inheriting shell variables, because some PBS configurations do not export them
# unless -V or -v is used.
python3 - <<PY
from pathlib import Path
import re

p = Path("${PBS_FILE}")
txt = p.read_text()

txt = re.sub(r"^PROJECT_ROOT=.*$", "PROJECT_ROOT=${PROJECT_ROOT}", txt, flags=re.MULTILINE)
txt = re.sub(r"^RUN_DIR=.*$", "RUN_DIR=${RUN_DIR}", txt, flags=re.MULTILINE)
txt = re.sub(r"^NPROC=.*$", "NPROC=${NPROC}", txt, flags=re.MULTILINE)

p.write_text(txt)
PY

echo "=== Submit MPAS init_atmosphere ==="
echo "PROJECT_ROOT=${PROJECT_ROOT}"
echo "RUN_DIR=${RUN_DIR}"
echo "NPROC=${NPROC}"
echo "PBS_FILE=${PBS_FILE}"
echo

echo "PBS fixed assignments:"
grep -nE "^(PROJECT_ROOT|RUN_DIR|NPROC)=" "${PBS_FILE}"
echo

cd "${RUN_DIR}"
JOBID=$(qsub "${PBS_FILE}")
echo "Submitted job: ${JOBID}"
echo "${JOBID}" | tee "${PROJECT_ROOT}/logs/17_mpas_init_jobid.txt" > /dev/null

echo

echo "Check status with:"
echo "  qstat -u ${USER}"
echo

echo "After it finishes, inspect:"
echo "  ls -lh ${RUN_DIR}/*.nc"
echo "  tail -160 ${RUN_DIR}/log.init_atmosphere.0000.out"
echo "  cat ${RUN_DIR}/log.init_atmosphere.0000.err"
