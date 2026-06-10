#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=/p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
RUN_DIR=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/runs/test48h_x1.10242_2018041421_np64

cd "${PROJECT_ROOT}"

source scripts/load_jaci_env.sh

./scripts/02_make_graph_partition.sh 64
./scripts/06_prepare_mpas_48h_test.sh

cp templates/pbs/run_mpas_48h_test.pbs "${RUN_DIR}/run_mpas_48h_test.pbs"

cd "${RUN_DIR}"
qsub run_mpas_48h_test.pbs
