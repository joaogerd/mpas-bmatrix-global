#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
WORK_ROOT=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global

INSTALL_ROOT=/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas
MPAS_EXE=${INSTALL_ROOT}/bin/mpas_atmosphere
ATM_SHARE=${INSTALL_ROOT}/share/MPAS/core_atmosphere

MESH_DIR=/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km
GRID_FILE=${MESH_DIR}/mesh/x1.10242.grid.nc
GRAPH_FILE=${MESH_DIR}/graph/x1.10242.graph.info
GRAPH_PART=${GRAPH_FILE}.part.64

TUTORIAL_ROOT=/p/projetos/monan_das/joao.gerd/data/mpasjedi_tutorial2024_testdata
TUTORIAL_MPAS_FILES=${TUTORIAL_ROOT}/MPAS_namelist_stream_physics_files

INITIAL_STATE=${TUTORIAL_ROOT}/background/2018041418/mpasout.2018-04-14_21.00.00.nc
INVARIANT_FILE=${TUTORIAL_MPAS_FILES}/x1.10242.invariant.nc

RUN_ID=test48h_x1.10242_2018041421_np64
RUN_DIR=${WORK_ROOT}/runs/${RUN_ID}

mkdir -p "${RUN_DIR}"
cd "${RUN_DIR}"

rm -f mpas_atmosphere init.nc x1.10242.grid.nc x1.10242.graph.info \
      x1.10242.graph.info.part.64 x1.10242.invariant.nc \
      namelist.atmosphere streams.atmosphere stream_list.atmosphere.* \
      log.atmosphere.* stdout.log stderr.log \
      history*.nc diagnostics*.nc restart*.nc

ln -sf "${MPAS_EXE}" mpas_atmosphere
ln -sf "${INITIAL_STATE}" init.nc
ln -sf "${GRID_FILE}" x1.10242.grid.nc
ln -sf "${GRAPH_FILE}" x1.10242.graph.info
ln -sf "${GRAPH_PART}" x1.10242.graph.info.part.64
ln -sf "${INVARIANT_FILE}" x1.10242.invariant.nc

find "${ATM_SHARE}" -maxdepth 1 -type f | while read -r f; do
  base=$(basename "$f")
  case "$base" in
    namelist.atmosphere|streams.atmosphere)
      ;;
    *)
      ln -sf "$f" "$base"
      ;;
  esac
done

if [[ -f "${TUTORIAL_MPAS_FILES}/namelist.atmosphere_240km" ]]; then
  cp "${TUTORIAL_MPAS_FILES}/namelist.atmosphere_240km" namelist.atmosphere
else
  cp "${ATM_SHARE}/namelist.atmosphere" namelist.atmosphere
fi

find "${TUTORIAL_MPAS_FILES}" -maxdepth 1 -type f -name "stream_list.atmosphere*" | while read -r f; do
  cp "$f" .
done

find "${ATM_SHARE}" -maxdepth 1 -type f -name "stream_list.atmosphere*" | while read -r f; do
  base=$(basename "$f")
  [[ -f "$base" ]] || ln -sf "$f" "$base"
done

python3 - <<'PY'
from pathlib import Path
import re

p = Path("namelist.atmosphere")
txt = p.read_text()

repls = {
    r"config_start_time\s*=\s*'[^']*'": "config_start_time = '2018-04-14_21:00:00'",
    r"config_run_duration\s*=\s*'[^']*'": "config_run_duration = '2_00:00:00'",
    r"config_do_restart\s*=\s*\.[a-zA-Z]+\." : "config_do_restart = .false.",
    r"config_block_decomp_file_prefix\s*=\s*'[^']*'": "config_block_decomp_file_prefix = 'x1.10242.graph.info.part.'",
}

for pat, rep in repls.items():
    txt = re.sub(pat, rep, txt)

extra_repls = {
    r"config_sst_update\s*=\s*\.[a-zA-Z]+\." : "config_sst_update = .false.",
    r"config_sstdiurn_update\s*=\s*\.[a-zA-Z]+\." : "config_sstdiurn_update = .false.",
    r"config_deepsoiltemp_update\s*=\s*\.[a-zA-Z]+\." : "config_deepsoiltemp_update = .false.",
    r"config_do_DAcycling\s*=\s*\.[a-zA-Z]+\." : "config_do_DAcycling = .false.",
}

for pat, rep in extra_repls.items():
    txt = re.sub(pat, rep, txt)

p.write_text(txt)
PY

cat > streams.atmosphere <<'EOF_STREAMS'
<streams>

<immutable_stream name="invariant"
                  type="input"
                  filename_template="x1.10242.invariant.nc"
                  input_interval="initial_only" />

<immutable_stream name="input"
                  type="input"
                  filename_template="init.nc"
                  input_interval="initial_only" />

<stream name="restart"
        type="output"
        filename_template="restart.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="24:00:00"
        clobber_mode="overwrite" />

<stream name="output"
        type="output"
        filename_template="history.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="24:00:00"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.output" />

<stream name="diagnostics"
        type="output"
        filename_template="diagnostics.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="24:00:00"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.diagnostics" />

</streams>
EOF_STREAMS

echo "Prepared 48h MPAS test:"
echo "${RUN_DIR}"

echo
echo "Namelist:"
grep -nE "config_start_time|config_run_duration|config_do_restart|config_block_decomp_file_prefix|config_dt|config_physics_suite" namelist.atmosphere || true

echo
echo "Streams:"
grep -nE "stream name|immutable_stream name|filename_template|input_interval|output_interval|contents|type=" streams.atmosphere || true
