from __future__ import annotations

from pathlib import Path

from ..shell import write_text
from ..vbal_core.model import toolbox_exe
from .model import NICAS_DIRAC_POINTS, NICAS_VARIABLES


def write_nicas_yaml(path: Path, variable: str, date: str, nvertlevels: int) -> None:
    level = 1 if variable == "surface_pressure" else max(1, nvertlevels - 20 + 1)
    dirac_yaml = "\n".join(
        f"""      - longitude: {longitude}
        latitude: {latitude}
        level: {level}
        variable: {variable}"""
        for longitude, latitude in NICAS_DIRAC_POINTS
    )
    text = f"""geometry:
  nml_file: "./namelist.atmosphere_240km"
  streams_file: "./streams.atmosphere_240km"
  deallocate non-da fields: true
  bump vunit: "avgheight"
background:
  state variables:
  - {variable}
  filename: "./bg.nc"
  date: &date '{date}'
  stream name: control
  transform model to analysis: false

background error:
  covariance model: SABER

  saber central block:
    saber block name: BUMP_NICAS
    calibration:
      io:
        files prefix: mpas
      drivers:
        multivariate strategy: univariate
        compute nicas: true
        write local nicas: true
        write global nicas: true
        write nicas grids: true
        internal dirac test: true
      nicas:
        resolution: 8
        max horizontal grid size: 15000
      dirac:
{dirac_yaml}
      input model files:
      - parameter: rh
        file:
          filename: ../mpas.cor_rh.nc
          date: *date
          stream name: control
      - parameter: rv
        file:
          filename: ../mpas.cor_rv.nc
          date: *date
          stream name: control
      output model files:
      - parameter: nicas_norm
        file:
          filename: ./mpas.nicas_norm.nc
          date: *date
          stream name: control
      - parameter: dirac_nicas
        file:
          filename: ./mpas.dirac_nicas.nc
          date: *date
          stream name: control
"""
    write_text(path, text)


def write_nicas_pbs(config, run_dir: Path, variable: str) -> None:
    nproc = int(config["mesh"].get("nproc", config["pbs"].get("nproc", 64)))
    queue = config["pbs"].get("queues", {}).get("bmatrix", config["pbs"].get("queue", "pesqmini"))
    walltime = config["pbs"].get("walltime", {}).get("bmatrix", config["pbs"].get("walltime_short", "00:10:00"))
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    exe = toolbox_exe(config)
    text = f"""#!/bin/bash
#PBS -N NICAS_{variable}
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

rm -f run_nicas.runlog stdout.log stderr.log
mpiexec -n {nproc} {exe} ./run_nicas.yaml ./run_nicas.runlog > stdout.log 2> stderr.log
"""
    write_text(run_dir / "qsub_nicas.bash", text)


def write_nicas_merge_files(config, workspace: Path) -> None:
    merge_dir = workspace / "merge"
    merge_dir.mkdir(parents=True, exist_ok=True)
    nproc = int(config["mesh"].get("nproc", config["pbs"].get("nproc", 64)))
    padded = f"{nproc:06d}"

    for rank in range(1, nproc + 1):
        rank_padded = f"{rank:06d}"
        local_name = f"mpas_nicas_local_{padded}-{rank_padded}.nc"
        grids_name = f"mpas_nicas_grids_local_{padded}-{rank_padded}.nc"
        commands = ["#!/bin/bash", "set -euo pipefail", f"rm -f {local_name} {grids_name}"]
        for variable in NICAS_VARIABLES:
            commands.extend(
                [
                    f"ncks -A ../{variable}/{local_name} {local_name}",
                    f"ncatted -O -a eulaVlliF_,global,d,, {local_name}",
                    f"ncks -A ../{variable}/{grids_name} {grids_name}",
                    f"ncatted -O -a eulaVlliF_,global,d,, {grids_name}",
                ]
            )
        write_text(merge_dir / f"merge_nicas_{rank_padded}.bash", "\n".join(commands) + "\n")

    global_commands = ["#!/bin/bash", "set -euo pipefail", "rm -f mpas_nicas.nc"]
    for variable in NICAS_VARIABLES:
        global_commands.extend(
            [
                f"ncks -A ../{variable}/mpas_nicas.nc mpas_nicas.nc",
                "ncatted -O -a eulaVlliF_,global,d,, mpas_nicas.nc",
            ]
        )
    write_text(merge_dir / "merge_nicas_global.bash", "\n".join(global_commands) + "\n")

    queue = config["pbs"].get("queues", {}).get("bmatrix", config["pbs"].get("queue", "pesqmini"))
    walltime = config["pbs"].get("walltime", {}).get("bmatrix", config["pbs"].get("walltime_short", "00:10:00"))
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    variables = " ".join(NICAS_VARIABLES)
    text = f"""#!/bin/bash
#PBS -N NICASmerge
#PBS -q {queue}
#PBS -l select=1:ncpus={nproc}
#PBS -l walltime={walltime}
#PBS -j oe

set -euo pipefail
source "{project_root}/{loader}"
module load nco 2>/dev/null || true
command -v ncks >/dev/null
command -v ncatted >/dev/null
cd "{merge_dir}"

rm -f stdout.log stderr.log merge.done mpas.nicas_norm.nc mpas.dirac_nicas.nc
for script in merge_nicas_[0-9][0-9][0-9][0-9][0-9][0-9].bash; do
  chmod +x "$script"
  ./"$script" &
done
wait
chmod +x merge_nicas_global.bash
./merge_nicas_global.bash
for variable in {variables}; do
  ncks -A -v "$variable" "../$variable/mpas.nicas_norm.nc" mpas.nicas_norm.nc
  ncks -A -v "$variable" "../$variable/mpas.dirac_nicas.nc" mpas.dirac_nicas.nc
done
touch merge.done
"""
    write_text(merge_dir / "qsub_nicas_merge.bash", text)
