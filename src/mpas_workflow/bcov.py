from __future__ import annotations

import argparse
import csv
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import load_config
from .shell import qsub, require_file, symlink_force, wait_for_pbs_job, write_text


DEFAULT_CONFIG = "configs/jaci-x1.10242.yaml"
TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"
STATE_VARIABLES = [
    "stream_function",
    "velocity_potential",
    "temperature",
    "spechum",
    "surface_pressure",
]


@dataclass(frozen=True)
class Sample:
    valid_time: str
    ptb: Path
    full_f24: Path


def compact_time(value: str) -> str:
    return datetime.strptime(value, TIME_FORMAT).strftime("%Y%m%d%H")


def iso_date(value: str) -> str:
    return datetime.strptime(value, TIME_FORMAT).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_bflow_samples(bflow_workspace: str | Path) -> list[Sample]:
    workspace = Path(bflow_workspace)
    manifest = require_file(workspace / "manifest.tsv", "Bflow manifest.tsv")
    samples: list[Sample] = []
    with manifest.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            vcompact = compact_time(row["valid_time"])
            output = workspace / "output" / vcompact
            ptb = require_file(output / "PTB_f48mf24.nc", f"PTB para {row['valid_time']}")
            full_f24 = require_file(output / "FULL_f24.nc", f"FULL_f24 para {row['valid_time']}")
            samples.append(Sample(row["valid_time"], ptb, full_f24))
    if not samples:
        raise SystemExit("ERRO: nenhum sample Bflow encontrado.")
    return samples


def covariance_root(config) -> Path:
    return Path(config["project"]["work_root"]) / "bmatrix" / "covariance"


def vbal_workspace(config, bflow_workspace: str | Path) -> Path:
    return covariance_root(config) / "vbal" / Path(bflow_workspace).name


def toolbox_exe(config) -> Path:
    path = Path(config["install"]["root"]) / "bin" / "mpasjedi_error_covariance_toolbox.x"
    return require_file(path, "mpasjedi_error_covariance_toolbox.x")


def write_stream_list_control(path: Path) -> None:
    write_text(path, "\n".join(STATE_VARIABLES) + "\n")


def stage_samples(workspace: Path, samples: list[Sample]) -> None:
    samples_dir = workspace / "samples"
    unbalanced = workspace / "samplesUnbalanced"
    samples_dir.mkdir(parents=True, exist_ok=True)
    unbalanced.mkdir(parents=True, exist_ok=True)

    for i, sample in enumerate(samples, start=1):
        member = f"{i:03d}"
        symlink_force(sample.ptb, samples_dir / f"PTB_f48mf24_{member}.nc")


def link_static_files(config, run_dir: Path, bg_file: Path) -> None:
    mesh = config["mesh"]
    static = config["static"]
    tutorial = Path(static["tutorial_physics_files"])

    symlink_force(mesh["graph"], run_dir / Path(mesh["graph"]).name)
    partition = Path(mesh["partitions_dir"]) / f"{Path(mesh['graph']).name}.part.{int(mesh['nproc'])}"
    if partition.exists():
        symlink_force(partition, run_dir / partition.name)

    symlink_force(static["invariant"], run_dir / f"{mesh['name']}.invariant.nc")
    symlink_force(bg_file, run_dir / "bg.nc")
    symlink_force(bg_file, run_dir / "templateFields.nc")

    for filename in ["namelist.atmosphere_240km", "streams.atmosphere_240km"]:
        src = tutorial / filename
        if src.exists():
            symlink_force(src, run_dir / filename)

    for src in tutorial.glob("stream_list.atmosphere.*"):
        symlink_force(src, run_dir / src.name)
    write_stream_list_control(run_dir / "stream_list.atmosphere.control")


def write_vbal_yaml(path: Path, nmembers: int, date: str) -> None:
    variables_yaml = "\n".join(f"  - {name}" for name in STATE_VARIABLES)
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

  iterative ensemble loading: true

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

rm -f run_vbal.runlog stdout.log stderr.log
mpiexec -n {nproc} {exe} ./run_vbal.yaml ./run_vbal.runlog > stdout.log 2> stderr.log
"""
    write_text(run_dir / "qsub_vbal.bash", text)


def prepare_vbal(config, bflow_workspace: str | Path, workspace: str | Path | None = None, clean: bool = False) -> Path:
    samples = read_bflow_samples(bflow_workspace)
    out = Path(workspace) if workspace else vbal_workspace(config, bflow_workspace)
    if clean and out.exists():
        shutil.rmtree(out)
    run_dir = out / "VBAL"
    run_dir.mkdir(parents=True, exist_ok=True)

    stage_samples(out, samples)
    link_static_files(config, run_dir, samples[0].full_f24)
    write_vbal_yaml(run_dir / "run_vbal.yaml", nmembers=len(samples), date=iso_date(samples[0].valid_time))
    write_vbal_pbs(config, run_dir)

    write_text(
        out / "README.md",
        f"# VBAL workspace\n\nBflow workspace: `{bflow_workspace}`\nMembers: {len(samples)}\n\nRun dir: `{run_dir}`\n",
    )
    print("=== VBAL workspace ===")
    print(f"WORKSPACE={out}")
    print(f"RUN_DIR={run_dir}")
    print(f"MEMBERS={len(samples)}")
    print(f"PBS={run_dir / 'qsub_vbal.bash'}")
    return out


def submit_vbal(workspace: str | Path, wait: bool = False, poll_seconds: int = 30) -> str:
    run_dir = Path(workspace) / "VBAL"
    require_file(run_dir / "qsub_vbal.bash", "qsub_vbal.bash")
    jobid = qsub("qsub_vbal.bash", run_dir)
    write_text(run_dir / "job_id.txt", jobid + "\n")
    if wait:
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
    return jobid


def validate_vbal(workspace: str | Path) -> bool:
    root = Path(workspace)
    run_dir = root / "VBAL"
    log = require_file(run_dir / "run_vbal.runlog", "run_vbal.runlog")
    text = log.read_text(errors="replace")

    bad_tokens = ["ABORT", "Exception", "Segmentation fault", "CRITICAL"]
    errors = [token for token in bad_tokens if token.lower() in text.lower()]

    outputs = sorted((root / "samplesUnbalanced").glob("PTB_f48mf24_*.nc"))
    if not outputs:
        errors.append("nenhum sample unbalanced foi gerado")

    print("=== VBAL validation ===")
    print(f"WORKSPACE={root}")
    print(f"RUNLOG={log}")
    print(f"UNBALANCED_SAMPLES={len(outputs)}")
    for sample in outputs[:10]:
        print(f"  {sample}")

    if errors:
        print("Problemas:")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit("ERRO: VBAL falhou ou ficou incompleto.")

    print("SUCCESS: VBAL validado.")
    return True


def vbal_prepare_command(args) -> int:
    config = load_config(args.config)
    prepare_vbal(config, args.bflow_workspace, workspace=args.workspace, clean=args.clean)
    return 0


def vbal_submit_command(args) -> int:
    jobid = submit_vbal(args.workspace, wait=args.wait, poll_seconds=args.poll_seconds)
    print(f"JOBID={jobid}")
    return 0


def vbal_validate_command(args) -> int:
    validate_vbal(args.workspace)
    return 0


def vbal_all_command(args) -> int:
    config = load_config(args.config)
    workspace = prepare_vbal(config, args.bflow_workspace, workspace=args.workspace, clean=args.clean)
    jobid = submit_vbal(workspace, wait=True, poll_seconds=args.poll_seconds)
    print(f"JOBID={jobid}")
    validate_vbal(workspace)
    return 0


def parser():
    p = argparse.ArgumentParser(prog="mpasbcov", description="Executa etapas de calibração BUMP/SABER da B-matrix")
    sub = p.add_subparsers(dest="cmd", required=True)

    prep = sub.add_parser("vbal-prepare", help="Prepara workspace VBAL")
    prep.add_argument("--config", default=DEFAULT_CONFIG)
    prep.add_argument("--bflow-workspace", required=True)
    prep.add_argument("--workspace")
    prep.add_argument("--clean", action="store_true")
    prep.set_defaults(func=vbal_prepare_command)

    submit = sub.add_parser("vbal-submit", help="Submete job VBAL")
    submit.add_argument("--workspace", required=True)
    submit.add_argument("--wait", action="store_true")
    submit.add_argument("--poll-seconds", type=int, default=30)
    submit.set_defaults(func=vbal_submit_command)

    validate = sub.add_parser("vbal-validate", help="Valida saída VBAL")
    validate.add_argument("--workspace", required=True)
    validate.set_defaults(func=vbal_validate_command)

    allp = sub.add_parser("vbal-all", help="Prepara, submete, espera e valida VBAL")
    allp.add_argument("--config", default=DEFAULT_CONFIG)
    allp.add_argument("--bflow-workspace", required=True)
    allp.add_argument("--workspace")
    allp.add_argument("--clean", action="store_true")
    allp.add_argument("--poll-seconds", type=int, default=30)
    allp.set_defaults(func=vbal_all_command)

    return p


def main(argv=None):
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
