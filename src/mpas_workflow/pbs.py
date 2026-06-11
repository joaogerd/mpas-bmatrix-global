from __future__ import annotations

from pathlib import Path


def mpas_init_pbs(config, run_dir, nproc):
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    queue = config["pbs"]["queue"]
    walltime = config["pbs"]["walltime_short"]
    return f'''#!/bin/bash
#PBS -N mpas_init_x1.10242
#PBS -q {queue}
#PBS -l select=1:ncpus={nproc}:mpiprocs={nproc}
#PBS -l walltime={walltime}
#PBS -j oe

set -euo pipefail

PROJECT_ROOT={project_root}
RUN_DIR={run_dir}

source "${{PROJECT_ROOT}}/{loader}"

cd "${{RUN_DIR}}"

export OMP_NUM_THREADS=1
export FI_CXI_RX_MATCH_MODE=hybrid
ulimit -s unlimited || true

rm -f log.init_atmosphere.* stdout.log stderr.log

mpiexec -n {nproc} ./mpas_init_atmosphere > stdout.log 2> stderr.log
'''


def mpas_forecast_pbs(config, run_dir, nproc, walltime=None):
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    queue = config["pbs"]["queue"]
    walltime = walltime or config["pbs"]["walltime_long"]
    return f'''#!/bin/bash
#PBS -N mpas_fcst_x1.10242
#PBS -q {queue}
#PBS -l select=1:ncpus={nproc}:mpiprocs={nproc}
#PBS -l walltime={walltime}
#PBS -j oe

set -euo pipefail

PROJECT_ROOT={project_root}
RUN_DIR={run_dir}

source "${{PROJECT_ROOT}}/{loader}"

cd "${{RUN_DIR}}"

export OMP_NUM_THREADS=1
export FI_CXI_RX_MATCH_MODE=hybrid
ulimit -s unlimited || true

mpiexec -n {nproc} ./mpas_atmosphere > stdout.log 2> stderr.log
'''
