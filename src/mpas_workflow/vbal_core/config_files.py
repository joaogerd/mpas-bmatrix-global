from __future__ import annotations

from pathlib import Path

from ..shell import write_text
from .model import STATE_VARIABLES, process_perts_exe, toolbox_exe


def _variables_yaml(indent: str = "  - ") -> str:
    return "\n".join(f"{indent}{name}" for name in STATE_VARIABLES)


def _vertical_balance_yaml(indent: str = "        ") -> str:
    return f"""{indent}vbal:
{indent}- balanced variable: velocity_potential
{indent}  unbalanced variable: stream_function
{indent}  diagonal regression: true
{indent}- balanced variable: temperature
{indent}  unbalanced variable: stream_function
{indent}- balanced variable: surface_pressure
{indent}  unbalanced variable: stream_function"""


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
      vertical balance:
{_vertical_balance_yaml('        ')}
        pseudo inverse: true
        dominant mode: 20
"""
    write_text(path, text)


def write_processperts_yaml(path: Path, nmembers: int, date: str) -> None:
    """Write a ProcessPerts YAML that materializes K2^-1(PTB) samples.

    The output files keep the same MPAS/JEDI variable names as the control
    variables. Semantically, after the right-inverse VBAL block, the fields
    velocity_potential, temperature and surface_pressure contain their
    unbalanced components.
    """
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
input variables: *vars
ensemble:
  members from template:
    template:
      <<: *memberConfig
      filename: ../samples/PTB_f48mf24_%mem%.nc
    pattern: '%mem%'
    nmembers: {nmembers}
    zero padding: 3
bands:
- band:
    filter:
    - saber block name: BUMP_VerticalBalance
      right inverse: true
      read:
        io:
          data directory: ../vbal
          files prefix: mpas
        drivers:
          read local sampling: true
          read vertical balance: true
        vertical balance:
{_vertical_balance_yaml('          ')}
  output:
    model write:
      stream name: control
      filename: ../samples_unbalanced/PTB_unbalanced_%mem%.nc
      member pattern: '%mem%'
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

rm -f run_vbal.runlog stdout.log stderr.log
mpiexec -n {nproc} {exe} ./run_vbal.yaml ./run_vbal.runlog > stdout.log 2> stderr.log
"""
    write_text(run_dir / "qsub_vbal.bash", text)


def write_processperts_pbs(config, run_dir: Path) -> None:
    nproc = int(config["mesh"].get("nproc", config["pbs"].get("nproc", 64)))
    queue = config["pbs"].get("queues", {}).get("bmatrix", config["pbs"].get("queue", "pesqmini"))
    walltime = config["pbs"].get("walltime", {}).get("bmatrix", config["pbs"].get("walltime_short", "00:10:00"))
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    exe = process_perts_exe(config)

    text = f"""#!/bin/bash
#PBS -N mpasjediBTrainingUnbal
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

mkdir -p ../samples_unbalanced
rm -f process_perts.runlog stdout.log stderr.log
mpiexec -n {nproc} {exe} ./process_unbalanced.yaml ./process_perts.runlog > stdout.log 2> stderr.log
"""
    write_text(run_dir / "qsub_process_unbalanced.bash", text)
