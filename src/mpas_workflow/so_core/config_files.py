from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..shell import write_text
from .model import so_artifacts, variational_exe


def write_so_yaml(path: Path, date: str, nicas_dir: Path, stddev_file: Path, vbal_dir: Path, variant: str = "default") -> None:
    so_artifacts(variant)
    analysis_date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    window_begin = (analysis_date - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    epoch = analysis_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    observers = []
    if variant in ("default", "t-only"):
        observers.append(
            f"""    - obs space:
        name: SO_T
        simulated variables: [airTemperature]
        obsdatain:
          engine:
            type: GenList
            lats: [30.3061]
            lons: [130.085]
            vert coord type: pressure
            vert coords: [78775.95]
            dateTimes: [0]
            epoch: "seconds since {epoch}"
            obs errors: [0.8]
            obs values: [284.5912]
        obsdataout:
          engine:
            type: H5File
            obsfile: ./obsout_SO_T.h5
      obs operator:
        name: VertInterp
        vertical coordinate: air_pressure
        interpolation method: log-linear"""
        )
    if variant in ("default", "u-only"):
        observers.append(
            f"""    - obs space:
        name: SO_U
        simulated variables: [windEastward]
        obsdatain:
          engine:
            type: GenList
            lats: [57.7699]
            lons: [357.713]
            vert coord type: pressure
            vert coords: [77693.09]
            dateTimes: [0]
            epoch: "seconds since {epoch}"
            obs errors: [1.0]
            obs values: [0.7250047]
        obsdataout:
          engine:
            type: H5File
            obsfile: ./obsout_SO_U.h5
      obs operator:
        name: VertInterp
        vertical coordinate: air_pressure
        interpolation method: log-linear"""
        )
    text = f"""output:
  filename: ./an.$Y-$M-$D_$h.$m.$s.nc
  stream name: analysis

variational:
  minimizer:
    algorithm: DRPCG
  iterations:
  - geometry:
      nml_file: "./namelist.atmosphere_240km"
      streams_file: "./streams.atmosphere_240km"
    gradient norm reduction: 1e-3
    diagnostics:
      departures: ombg
    ninner: 10

final:
  diagnostics:
    departures: oman

cost function:
  cost type: 3D-Var
  time window:
    begin: '{window_begin}'
    length: PT6H
  jb evaluation: false
  geometry:
    nml_file: "./namelist.atmosphere_240km"
    streams_file: "./streams.atmosphere_240km"
    deallocate non-da fields: true
  analysis variables: &incvars
  - spechum
  - surface_pressure
  - temperature
  - uReconstructMeridional
  - uReconstructZonal
  background:
    state variables:
    - spechum
    - surface_pressure
    - temperature
    - uReconstructMeridional
    - uReconstructZonal
    - air_temperature
    - air_pressure
    - air_pressure_at_surface
    - eastward_wind
    - northward_wind
    - theta
    - rho
    - u
    - qv
    - pressure
    - pressure_p
    filename: ./bg_so.nc
    date: &analysisDate '{date}'
    transform model to analysis: false
  background error:
    covariance model: SABER
    saber central block:
      saber block name: BUMP_NICAS
      active variables: &ctlvars
      - stream_function
      - velocity_potential
      - temperature
      - spechum
      - surface_pressure
      read:
        io:
          data directory: {nicas_dir}
          files prefix: mpas
        drivers:
          multivariate strategy: univariate
          read local nicas: true
        grids:
        - model:
            variables:
            - stream_function
            - velocity_potential
            - temperature
            - spechum
        - model:
            variables:
            - surface_pressure
    saber outer blocks:
    - saber block name: StdDev
      read:
        model file:
          filename: {stddev_file}
          date: *analysisDate
          stream name: control
    - saber block name: BUMP_VerticalBalance
      read:
        io:
          data directory: {vbal_dir}
          files prefix: mpas
        drivers:
          read local sampling: true
          read vertical balance: true
        vertical balance:
          vbal:
          - balanced variable: velocity_potential
            unbalanced variable: stream_function
            diagonal regression: true
          - balanced variable: temperature
            unbalanced variable: stream_function
          - balanced variable: surface_pressure
            unbalanced variable: stream_function
    linear variable change:
      linear variable change name: Control2Analysis
      input variables: *ctlvars
      output variables: *incvars

  observations:
    observers:
{chr(10).join(observers)}
"""
    write_text(path, text)


def write_so_pbs(config, run_dir: Path, variant: str = "default") -> None:
    artifacts = so_artifacts(variant)
    nproc = int(config["mesh"].get("nproc", config["pbs"].get("nproc", 64)))
    queue = config["pbs"].get("queues", {}).get("bmatrix", config["pbs"].get("queue", "pesqmini"))
    walltime = config["pbs"].get("walltime", {}).get("bmatrix", config["pbs"].get("walltime_short", "00:10:00"))
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    exe = variational_exe(config)
    text = f"""#!/bin/bash
#PBS -N SOTest
#PBS -q {queue}
#PBS -l select=1:ncpus={nproc}:mpiprocs={nproc}
#PBS -l walltime={walltime}
#PBS -j oe

set -euo pipefail
source "{project_root}/{loader}"
cd "{run_dir}"
export OMP_NUM_THREADS=1
export GFORTRAN_CONVERT_UNIT=big_endian:101-200
export FI_CXI_RX_MATCH_MODE=hybrid
ulimit -s unlimited || true

rm -f {artifacts['runlog']} {artifacts['stdout']} {artifacts['stderr']}
mpiexec -n {nproc} {exe} ./{artifacts['yaml']} ./{artifacts['runlog']} > {artifacts['stdout']} 2> {artifacts['stderr']}
"""
    write_text(run_dir / artifacts["pbs"], text)


def write_so_t_only_diagnostic_pbs(config, run_dir: Path) -> None:
    # Kept intentionally lightweight. Detailed debugger scripts can be added in a
    # dedicated diagnostic module later.
    write_text(run_dir / "qsub_so_t_only_debug.bash", "#!/bin/bash\necho 'SO t-only debug placeholder'\n")
