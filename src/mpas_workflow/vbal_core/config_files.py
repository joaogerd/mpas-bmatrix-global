from __future__ import annotations

from pathlib import Path

from ..shell import write_text
from .model import STATE_VARIABLES, toolbox_exe


def _variables_yaml(indent: str = "  - ") -> str:
    return "\n".join(f"{indent}{name}" for name in STATE_VARIABLES)


def write_vbal_yaml(path: Path, nmembers: int, date: str) -> None:
    variables_yaml = _variables_yaml()
    text = f"""_member config: &memberConfig
  state variables: &vars
{variables_yaml}
  date: &date '{date}'
  stream name: control
  transform model to analysis: false
geometry:
  nml_file: "./namelist.atmosphere_240km"
  streams_file: "./streams.atmosphere_240km"
background:
  state variables: *vars
  filename: "./bg.nc"
  date: *date
  stream name: control
  transform model to analysis: false

background error:
  covariance model: SABER

  iterative ensemble loading: false

  ensemble:
    members from template:
      template:
        <<: *memberConfig
        filename: ../samples/PTB_f48mf24_%mem%.nc
      pattern: '%mem%'
      nmembers: {nmembers}
      zero padding: 3

  output ensemble:
    filename: ../samplesUnbalanced/PTB_f48mf24_%{{member}}%.nc
    date: *date
    stream name: control

  saber central block:
    saber block name: ID

  saber outer blocks:
  - saber block name: BUMP_VerticalBalance
    calibration:
      io:
        files prefix: mpas
      drivers:
        write local sampling: true
        write global sampling: true
        compute vertical covariance: true
        compute vertical balance: true
        write vertical balance: true
      sampling:
        computation grid size: 12000
        diagnostic grid size: 200
        reduced levels: 55
        averaging latitude width: 10.0
      diagnostics:
        target ensemble size: {nmembers}
      vertical balance:
        vbal:
        - balanced variable: velocity_potential
          unbalanced variable: stream_function
          diagonal regression: true
        - balanced variable: temperature
          unbalanced variable: stream_function
        - balanced variable: surface_pressure
          unbalanced variable: stream_function
        pseudo inverse: true
        dominant mode: 20
"""
    write_text(path, text)


def write_vbal_pbs(config, run_dir: Path) -> None:
    nproc = int(config["mesh"].get("nproc", config["pbs"].get("nproc", 64)))
    queue = config["pbs"].get("queues", {}).get("bmatrix", config["pbs"].get("queue", "pesqmini"))
    walltime = config["pbs"].get("walltime", {}).get("bmatrix", config["pbs"].get("walltime_short", "00:10:00"))
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    exe = toolbox_exe(config)

    text = f"""#!/bin/bash
#PBS -N mpasjediBTrainingVBAL
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
export GFORTRAN_CONVERT_UNIT=big_endian:101-200
export FI_CXI_RX_MATCH_MODE=hybrid
ulimit -s unlimited || true

mkdir -p ../samplesUnbalanced
rm -f run_vbal.runlog stdout.log stderr.log
mpiexec -n {nproc} {exe} ./run_vbal.yaml ./run_vbal.runlog > stdout.log 2> stderr.log
"""
    write_text(run_dir / "qsub_vbal.bash", text)
