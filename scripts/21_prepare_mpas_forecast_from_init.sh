#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=${PROJECT_ROOT:-/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global}
WORK_ROOT=${WORK_ROOT:-/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global}
INSTALL_ROOT=${INSTALL_ROOT:-/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas}

MESH_NAME=${MESH_NAME:-x1.10242}
MESH_ROOT=${MESH_ROOT:-/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km}
TUTORIAL_ROOT=${TUTORIAL_ROOT:-/p/projetos/monan_das/joao.gerd/data/mpasjedi_tutorial2024_testdata}
TUTORIAL_MPAS_FILES=${TUTORIAL_MPAS_FILES:-${TUTORIAL_ROOT}/MPAS_namelist_stream_physics_files}

NPROC=${NPROC:-64}
INIT_TIME=${INIT_TIME:-2026-06-11_00:00:00}
INIT_TIME_SAFE=${INIT_TIME//:/.}
RUN_DURATION=${RUN_DURATION:-0_06:00:00}
OUTPUT_INTERVAL=${OUTPUT_INTERVAL:-06:00:00}

MPAS_EXE=${MPAS_EXE:-${INSTALL_ROOT}/bin/mpas_atmosphere}
ATM_SHARE=${ATM_SHARE:-${INSTALL_ROOT}/share/MPAS/core_atmosphere}
INVARIANT_FILE=${INVARIANT_FILE:-${TUTORIAL_MPAS_FILES}/${MESH_NAME}.invariant.nc}
INIT_RUN_DIR=${INIT_RUN_DIR:-${WORK_ROOT}/mpas_init/${MESH_NAME}/${INIT_TIME}_invariant_np${NPROC}}
INITIAL_STATE=${INITIAL_STATE:-${INIT_RUN_DIR}/${MESH_NAME}.init.${INIT_TIME_SAFE}.nc}
RUN_ID=${RUN_ID:-forecast_${MESH_NAME}_${INIT_TIME_SAFE}_f006_np${NPROC}}
RUN_DIR=${RUN_DIR:-${WORK_ROOT}/runs/${RUN_ID}}

mkdir -p "${PROJECT_ROOT}/logs" "${RUN_DIR}"

for f in \
  "${MPAS_EXE}" \
  "${ATM_SHARE}/namelist.atmosphere" \
  "${MESH_ROOT}/mesh/${MESH_NAME}.grid.nc" \
  "${MESH_ROOT}/graph/${MESH_NAME}.graph.info" \
  "${MESH_ROOT}/partitions/${MESH_NAME}.graph.info.part.${NPROC}" \
  "${INVARIANT_FILE}" \
  "${INITIAL_STATE}"; do
  if [[ ! -e "${f}" ]]; then
    echo "ERRO: required file not found: ${f}"
    exit 1
  fi
done

cd "${RUN_DIR}"

find . -maxdepth 1 -type l -delete
rm -f namelist.atmosphere streams.atmosphere stream_list.atmosphere.* stdout.log stderr.log
rm -f log.atmosphere.* history*.nc diagnostics*.nc restart*.nc

ln -sfn "${MPAS_EXE}" mpas_atmosphere
ln -sfn "${INITIAL_STATE}" init.nc
ln -sfn "${MESH_ROOT}/mesh/${MESH_NAME}.grid.nc" "${MESH_NAME}.grid.nc"
ln -sfn "${MESH_ROOT}/graph/${MESH_NAME}.graph.info" "${MESH_NAME}.graph.info"
ln -sfn "${MESH_ROOT}/partitions/${MESH_NAME}.graph.info.part.${NPROC}" "${MESH_NAME}.graph.info.part.${NPROC}"
ln -sfn "${INVARIANT_FILE}" "${MESH_NAME}.invariant.nc"

find "${ATM_SHARE}" -maxdepth 1 -type f | while read -r f; do
  base=$(basename "$f")
  case "$base" in
    namelist.atmosphere|streams.atmosphere) ;;
    *) ln -sfn "$f" "$base" ;;
  esac
done

if [[ -f "${TUTORIAL_MPAS_FILES}/namelist.atmosphere_240km" ]]; then
  cp "${TUTORIAL_MPAS_FILES}/namelist.atmosphere_240km" namelist.atmosphere
else
  cp "${ATM_SHARE}/namelist.atmosphere" namelist.atmosphere
fi

find "${TUTORIAL_MPAS_FILES}" -maxdepth 1 -type f -name 'stream_list.atmosphere*' -exec cp {} . \;
find "${ATM_SHARE}" -maxdepth 1 -type f -name 'stream_list.atmosphere*' | while read -r f; do
  base=$(basename "$f")
  [[ -f "$base" ]] || ln -sfn "$f" "$base"
done

python3 - <<PY
from pathlib import Path
import re
p = Path('namelist.atmosphere')
txt = p.read_text()
for pat, rep in {
    r"config_start_time\s*=\s*'[^']*'": "config_start_time = '${INIT_TIME}'",
    r"config_run_duration\s*=\s*'[^']*'": "config_run_duration = '${RUN_DURATION}'",
    r"config_do_restart\s*=\s*\.[a-zA-Z]+\.": "config_do_restart = .false.",
    r"config_block_decomp_file_prefix\s*=\s*'[^']*'": "config_block_decomp_file_prefix = '${MESH_NAME}.graph.info.part.'",
    r"config_sst_update\s*=\s*\.[a-zA-Z]+\.": "config_sst_update = .false.",
    r"config_sstdiurn_update\s*=\s*\.[a-zA-Z]+\.": "config_sstdiurn_update = .false.",
    r"config_deepsoiltemp_update\s*=\s*\.[a-zA-Z]+\.": "config_deepsoiltemp_update = .false.",
    r"config_do_DAcycling\s*=\s*\.[a-zA-Z]+\.": "config_do_DAcycling = .false.",
}.items():
    txt = re.sub(pat, rep, txt)
p.write_text(txt)
PY

cat > streams.atmosphere <<EOF_STREAMS
<streams>
<immutable_stream name="invariant" type="input" filename_template="${MESH_NAME}.invariant.nc" input_interval="initial_only" />
<immutable_stream name="input" type="input" filename_template="init.nc" input_interval="initial_only" />
<stream name="restart" type="output" filename_template="restart.\$Y-\$M-\$D_\$h.\$m.\$s.nc" filename_interval="output_interval" output_interval="${OUTPUT_INTERVAL}" clobber_mode="overwrite" />
<stream name="output" type="output" filename_template="history.\$Y-\$M-\$D_\$h.\$m.\$s.nc" filename_interval="output_interval" output_interval="${OUTPUT_INTERVAL}" clobber_mode="overwrite" contents="stream_list.atmosphere.output" />
<stream name="diagnostics" type="output" filename_template="diagnostics.\$Y-\$M-\$D_\$h.\$m.\$s.nc" filename_interval="output_interval" output_interval="${OUTPUT_INTERVAL}" clobber_mode="overwrite" contents="stream_list.atmosphere.diagnostics" />
</streams>
EOF_STREAMS

cat > run_mpas_forecast.pbs <<EOF_PBS
#!/bin/bash
#PBS -N mpas_f006_x1.10242
#PBS -q pesqmini
#PBS -l select=1:ncpus=${NPROC}:mpiprocs=${NPROC}
#PBS -l walltime=00:30:00
#PBS -j oe

set -euo pipefail
PROJECT_ROOT=${PROJECT_ROOT}
RUN_DIR=${RUN_DIR}
NPROC=${NPROC}

source "\${PROJECT_ROOT}/scripts/load_jaci_env.sh"
cd "\${RUN_DIR}"
export OMP_NUM_THREADS=1
export FI_CXI_RX_MATCH_MODE=hybrid
ulimit -s unlimited || true

module list || true
mpiexec -n "\${NPROC}" ./mpas_atmosphere > stdout.log 2> stderr.log
ls -lh *.nc || true
tail -160 log.atmosphere.0000.out || true
cat log.atmosphere.0000.err || true
tail -120 stderr.log || true
EOF_PBS

echo "SUCCESS: MPAS forecast run directory prepared."
echo "RUN_DIR=${RUN_DIR}"
echo

echo "Namelist summary:"
grep -nE 'config_start_time|config_run_duration|config_do_restart|config_block_decomp_file_prefix|config_dt|config_physics_suite' namelist.atmosphere || true
echo

echo "Submit with:"
echo "  cd ${RUN_DIR} && qsub run_mpas_forecast.pbs"
