#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Prepare MPAS atmosphere smoke test
# =============================================================================
#
# Goal:
#   Test whether mpas_atmosphere can run on JACI using an existing MPAS-JEDI
#   tutorial state as initial condition.
#
# This test uses:
#   - x1.10242.invariant.nc
#   - mpasout.2018-04-14_21.00.00.nc linked as init.nc
#   - a minimal streams.atmosphere written by this script
#
# =============================================================================

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

RUN_ID=smoke_x1.10242_2018041421_6h_np64
RUN_DIR=${WORK_ROOT}/runs/${RUN_ID}

mkdir -p "${RUN_DIR}"
mkdir -p "${PROJECT_ROOT}/logs"

echo "Preparing MPAS smoke test:"
echo "  RUN_DIR=${RUN_DIR}"
echo "  MPAS_EXE=${MPAS_EXE}"
echo "  INITIAL_STATE=${INITIAL_STATE}"
echo "  INVARIANT_FILE=${INVARIANT_FILE}"
echo "  GRAPH_PART=${GRAPH_PART}"

for f in \
  "${MPAS_EXE}" \
  "${INITIAL_STATE}" \
  "${INVARIANT_FILE}" \
  "${GRID_FILE}" \
  "${GRAPH_FILE}" \
  "${GRAPH_PART}"
do
  if [[ ! -e "${f}" ]]; then
    echo "ERRO: arquivo obrigatório não encontrado:"
    echo "  ${f}"
    exit 1
  fi
done

cd "${RUN_DIR}"

# Clean generated links/files from previous preparations.
rm -f mpas_atmosphere
rm -f init.nc
rm -f x1.10242.grid.nc
rm -f x1.10242.graph.info
rm -f x1.10242.graph.info.part.64
rm -f x1.10242.invariant.nc
rm -f namelist.atmosphere
rm -f streams.atmosphere
rm -f stream_list.atmosphere.*
rm -f log.atmosphere.*
rm -f stdout.log stderr.log
rm -f output*.nc history*.nc restart*.nc diagnostics*.nc

# Executable and core inputs.
ln -sf "${MPAS_EXE}" mpas_atmosphere

# Smoke-test initial state.
# If MPAS later rejects this file because it lacks prognostic fields,
# then we will move to generating a true init.nc with mpas_init_atmosphere.
ln -sf "${INITIAL_STATE}" init.nc

ln -sf "${GRID_FILE}" x1.10242.grid.nc
ln -sf "${GRAPH_FILE}" x1.10242.graph.info
ln -sf "${GRAPH_PART}" x1.10242.graph.info.part.64
ln -sf "${INVARIANT_FILE}" x1.10242.invariant.nc

# Link atmosphere physics/support files, except namelist/streams.
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

# Prefer tutorial 240-km namelist when available.
if [[ -f "${TUTORIAL_MPAS_FILES}/namelist.atmosphere_240km" ]]; then
  cp "${TUTORIAL_MPAS_FILES}/namelist.atmosphere_240km" namelist.atmosphere
else
  cp "${ATM_SHARE}/namelist.atmosphere" namelist.atmosphere
fi

# Stream lists.
# Prefer tutorial stream lists, then fall back to MPAS share.
find "${TUTORIAL_MPAS_FILES}" -maxdepth 1 -type f -name "stream_list.atmosphere*" | while read -r f; do
  cp "$f" .
done

find "${ATM_SHARE}" -maxdepth 1 -type f -name "stream_list.atmosphere*" | while read -r f; do
  base=$(basename "$f")
  [[ -f "$base" ]] || ln -sf "$f" "$base"
done

# If stream_list.atmosphere.output does not exist, create a small one.
# This avoids dependence on the tutorial stream configuration.
if [[ ! -f stream_list.atmosphere.output ]]; then
  cat > stream_list.atmosphere.output <<'EOS'
latCell
lonCell
zgrid
theta
rho
u
qv
pressure
surface_pressure
EOS
fi

if [[ ! -f stream_list.atmosphere.diagnostics ]]; then
  cat > stream_list.atmosphere.diagnostics <<'EOS'
latCell
lonCell
theta
rho
u
qv
pressure
surface_pressure
EOS
fi

# Patch namelist for the smoke test.
python3 - <<'PY'
from pathlib import Path
import re

p = Path("namelist.atmosphere")
txt = p.read_text()

repls = {
    r"config_start_time\s*=\s*'[^']*'": "config_start_time = '2018-04-14_21:00:00'",
    r"config_run_duration\s*=\s*'[^']*'": "config_run_duration = '0_06:00:00'",
    r"config_do_restart\s*=\s*\.[a-zA-Z]+\." : "config_do_restart = .false.",
    r"config_block_decomp_file_prefix\s*=\s*'[^']*'": "config_block_decomp_file_prefix = 'x1.10242.graph.info.part.'",
}

for pat, rep in repls.items():
    if re.search(pat, txt):
        txt = re.sub(pat, rep, txt)
    else:
        print(f"WARNING: pattern not found in namelist: {pat}")

# Disable options that may require extra external files in a smoke test.
extra_repls = {
    r"config_sst_update\s*=\s*\.[a-zA-Z]+\." : "config_sst_update = .false.",
    r"config_sstdiurn_update\s*=\s*\.[a-zA-Z]+\." : "config_sstdiurn_update = .false.",
    r"config_deepsoiltemp_update\s*=\s*\.[a-zA-Z]+\." : "config_deepsoiltemp_update = .false.",
    r"config_do_DAcycling\s*=\s*\.[a-zA-Z]+\." : "config_do_DAcycling = .false.",
    r"config_do_restart\s*=\s*\.[a-zA-Z]+\." : "config_do_restart = .false.",
}

for pat, rep in extra_repls.items():
    txt = re.sub(pat, rep, txt)

p.write_text(txt)
PY

# Write a minimal, explicit streams.atmosphere for this smoke test.
# The critical part is:
#   input -> init.nc
# not templateFields.10242.nc.
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
        output_interval="6:00:00"
        clobber_mode="overwrite" />

<stream name="output"
        type="output"
        filename_template="history.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="6:00:00"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.output" />

<stream name="diagnostics"
        type="output"
        filename_template="diagnostics.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="6:00:00"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.diagnostics" />

</streams>
EOF_STREAMS

echo
echo "=== Prepared run directory ==="
pwd
ls -lh

echo
echo "=== Key namelist settings ==="
grep -nE "config_start_time|config_run_duration|config_do_restart|config_block_decomp_file_prefix|config_dt|config_physics_suite|config_sst_update|config_do_DAcycling" namelist.atmosphere || true

echo
echo "=== Streams summary ==="
grep -nE "stream name|immutable_stream name|filename_template|input_interval|output_interval|contents|type=" streams.atmosphere || true

echo
echo "=== Initial-state variables check ==="
if command -v ncdump >/dev/null 2>&1; then
  ncdump -h init.nc | grep -E "Time|nCells|nVertLevels|theta|rho|u|qv|pressure|surface_pressure|air_temperature|water_vapor|air_pressure_at_surface|dry_air_density" | head -160 || true
else
  echo "ncdump not available in current environment."
fi

echo
echo "Smoke test directory ready:"
echo "${RUN_DIR}"
