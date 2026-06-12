from __future__ import annotations


def _pbs_queue(config, task: str) -> str:
    pbs = config["pbs"]
    task_queues = pbs.get("queues", {})
    return task_queues.get(task, pbs["queue"])


def _pbs_walltime(config, task: str, lead_hours: int | None = None) -> str:
    pbs = config["pbs"]
    walltime = pbs.get("walltime", {})

    if task == "init":
        return walltime.get("init", pbs.get("walltime_short", "00:10:00"))

    if task == "forecast":
        forecast = walltime.get("forecast", {})
        if lead_hours is not None:
            key = f"f{int(lead_hours):03d}"
            if key in forecast:
                return forecast[key]
        return forecast.get("default", pbs.get("walltime_long", "00:30:00"))

    return pbs.get("walltime_short", "00:10:00")


def mpas_init_pbs(config, run_dir, nproc):
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    queue = _pbs_queue(config, "init")
    walltime = _pbs_walltime(config, "init")
    mesh_name = config["mesh"]["name"]
    return f'''#!/bin/bash
#PBS -N mpas_init_{mesh_name}
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


def mpas_forecast_pbs(config, run_dir, nproc, lead_hours=None, walltime=None):
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    queue = _pbs_queue(config, "forecast")
    walltime = walltime or _pbs_walltime(config, "forecast", lead_hours=lead_hours)
    mesh_name = config["mesh"]["name"]
    lead = f"f{int(lead_hours):03d}" if lead_hours is not None else "fcst"
    return f'''#!/bin/bash
#PBS -N mpas_{lead}_{mesh_name}
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

rm -f log.atmosphere.* stdout.log stderr.log

mpiexec -n {nproc} ./mpas_atmosphere > stdout.log 2> stderr.log
'''
