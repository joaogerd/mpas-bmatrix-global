#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global

cd "${PROJECT_ROOT}"

source scripts/load_jaci_env.sh

./scripts/02_make_graph_partition.sh 64
./scripts/04_prepare_mpas_smoke_test.sh

RUN_DIR=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/runs/smoke_x1.10242_2018041421_6h_np64

cp templates/pbs/run_mpas_smoke_test.pbs "${RUN_DIR}/run_mpas_smoke_test.pbs"

echo
echo "Submitting:"
echo "${RUN_DIR}/run_mpas_smoke_test.pbs"
echo

cd "${RUN_DIR}"
qsub run_mpas_smoke_test.pbs
