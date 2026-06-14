from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
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
MIN_HDIAG_MEMBERS = 4


@dataclass(frozen=True)
class Sample:
    valid_time: str
    ptb: Path
    full_f24: Path
    template_fields: Path


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
            template_fields = require_file(row["f024"], f"f024 completo para {row['valid_time']}")
            samples.append(Sample(row["valid_time"], ptb, full_f24, template_fields))
    if not samples:
        raise SystemExit("ERRO: nenhum sample Bflow encontrado.")
    return samples


def covariance_root(config) -> Path:
    return Path(config["project"]["work_root"]) / "bmatrix" / "covariance"


def vbal_workspace(config, bflow_workspace: str | Path) -> Path:
    return covariance_root(config) / "vbal" / Path(bflow_workspace).name


def hdiag_workspace(config, vbal_workspace_path: str | Path) -> Path:
    return covariance_root(config) / "hdiag" / Path(vbal_workspace_path).name


def toolbox_exe(config) -> Path:
    path = Path(config["install"]["root"]) / "bin" / "mpasjedi_error_covariance_toolbox.x"
    return require_file(path, "mpasjedi_error_covariance_toolbox.x")


def write_stream_list_control(path: Path) -> None:
    write_text(path, "\n".join(STATE_VARIABLES) + "\n")


def stage_samples(workspace: Path, samples: list[Sample]) -> None:
    samples_dir = workspace / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)

    for i, sample in enumerate(samples, start=1):
        member = f"{i:03d}"
        destination = samples_dir / f"PTB_f48mf24_{member}.nc"
        destination.unlink(missing_ok=True)
        subprocess.run(
            ["nccopy", "-k", "cdf5", str(sample.ptb), str(destination)],
            check=True,
        )


def link_static_files(
    config,
    run_dir: Path,
    bg_file: Path,
    template_fields: Path,
    valid_time: str,
) -> None:
    mesh = config["mesh"]
    static = config["static"]
    tutorial = Path(static["tutorial_physics_files"])

    symlink_force(mesh["graph"], run_dir / Path(mesh["graph"]).name)
    partition = Path(mesh["partitions_dir"]) / f"{Path(mesh['graph']).name}.part.{int(mesh['nproc'])}"
    if partition.exists():
        symlink_force(partition, run_dir / partition.name)

    symlink_force(static["invariant"], run_dir / f"{mesh['name']}.invariant.nc")
    symlink_force(bg_file, run_dir / "bg.nc")
    # The immutable input stream names this file explicitly.
    mesh_id = str(mesh["name"]).removeprefix("x1.")
    symlink_force(template_fields, run_dir / f"templateFields.{mesh_id}.nc")

    namelist = tutorial / "namelist.atmosphere_240km"
    if namelist.exists():
        text = namelist.read_text()
        start_time = datetime.strptime(valid_time, TIME_FORMAT).strftime("%Y-%m-%d_%H:%M:%S")
        text, replacements = re.subn(
            r"(?m)^(\s*config_start_time\s*=\s*)'[^']+'",
            rf"\1'{start_time}'",
            text,
            count=1,
        )
        if replacements != 1:
            raise SystemExit(f"ERRO: config_start_time não encontrado em {namelist}")
        write_text(run_dir / namelist.name, text)

    streams = tutorial / "streams.atmosphere_240km"
    if streams.exists():
        symlink_force(streams, run_dir / streams.name)

    physics_dir = Path(config.get("install", {}).get("atmosphere_share", tutorial))
    for src in physics_dir.iterdir():
        if src.is_file() and src.name[:1].isupper():
            symlink_force(src, run_dir / src.name)

    for key in ["geovars", "keptvars"]:
        if key in static:
            src = require_file(static[key], key)
            symlink_force(src, run_dir / src.name)

    for src in tutorial.glob("stream_list.atmosphere.*"):
        if src.name != "stream_list.atmosphere.control":
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
    link_static_files(
        config,
        run_dir,
        samples[0].full_f24,
        samples[0].template_fields,
        samples[0].valid_time,
    )
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
    log = run_dir / "run_vbal.runlog"
    text = log.read_text(errors="replace") if log.is_file() else ""

    bad_tokens = ["ABORT", "Exception", "Segmentation fault", "CRITICAL"]
    errors = [token for token in bad_tokens if token.lower() in text.lower()]

    global_products = [run_dir / "mpas_sampling.nc", run_dir / "mpas_vbal.nc"]
    sampling_local = sorted(run_dir.glob("mpas_sampling_local_*"))
    vbal_local = sorted(run_dir.glob("mpas_vbal_local_*"))
    legacy_outputs = sorted((root / "samplesUnbalanced").glob("PTB_f48mf24_*.nc"))

    if not log.is_file():
        errors.append("run_vbal.runlog ausente")
    if "Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente no run_vbal.runlog")
    for product in global_products:
        if not product.is_file():
            errors.append(f"produto VBAL ausente: {product.name}")
    errors.extend(_validate_ranked_products(sampling_local, "mpas_sampling_local"))
    errors.extend(_validate_ranked_products(vbal_local, "mpas_vbal_local"))

    print("=== VBAL validation ===")
    print(f"WORKSPACE={root}")
    print(f"RUNLOG={log}")
    print(f"SAMPLING_GLOBAL={(run_dir / 'mpas_sampling.nc').is_file()}")
    print(f"VBAL_GLOBAL={(run_dir / 'mpas_vbal.nc').is_file()}")
    print(f"SAMPLING_LOCAL={len(sampling_local)}")
    print(f"VBAL_LOCAL={len(vbal_local)}")
    print(f"LEGACY_UNBALANCED_SAMPLES={len(legacy_outputs)}")
    if not legacy_outputs:
        print("Este build SABER nao escreve output ensemble no VBAL. Isso e esperado neste fluxo.")
        print(
            "A proxima etapa deve usar os PTBs originais com "
            "BUMP_VerticalBalance em modo read."
        )

    if errors:
        print("Problemas:")
        for err in errors:
            print(f"  - {err}")
        print_vbal_diagnostics(root)
        raise SystemExit("ERRO: VBAL falhou ou ficou incompleto.")

    print("SUCCESS: VBAL validado.")
    return True


def _validate_ranked_products(paths: list[Path], prefix: str) -> list[str]:
    if not paths:
        return [f"nenhum arquivo {prefix}_* foi gerado"]

    matches = [re.search(r"_local_(\d{6})-(\d{6})\.nc$", path.name) for path in paths]
    if any(match is None for match in matches):
        return [f"nome inesperado em arquivos {prefix}_*"]

    expected = int(matches[0].group(1))
    ranks = {int(match.group(2)) for match in matches}
    errors = []
    if len(paths) != expected:
        errors.append(f"{prefix}_* incompletos: esperados={expected}, gerados={len(paths)}")
    missing = sorted(set(range(1, expected + 1)) - ranks)
    if missing:
        errors.append(f"{prefix}_* ranks ausentes: {missing[:10]}")
    return errors


def print_vbal_diagnostics(workspace: Path, tail_lines: int = 80) -> None:
    run_dir = workspace / "VBAL"
    print("=== VBAL diagnostics ===")
    for name in ["stdout.log", "stderr.log", "run_vbal.runlog", "log.atmosphere.0000.err"]:
        path = run_dir / name
        print(f"--- {path} (ultimas {tail_lines} linhas) ---")
        if not path.is_file():
            print("[arquivo ausente]")
            continue
        lines = path.read_text(errors="replace").splitlines()
        print("\n".join(lines[-tail_lines:]) or "[arquivo vazio]")

    print(f"--- arquivos gerados em {workspace} ---")
    files = sorted(path for path in workspace.rglob("*") if path.is_file() or path.is_symlink())
    for path in files[:200]:
        kind = "link" if path.is_symlink() else "file"
        print(f"{kind:4} {path.lstat().st_size:12d} {path.relative_to(workspace)}")
    if len(files) > 200:
        print(f"... {len(files) - 200} arquivos adicionais omitidos")


def vbal_date(vbal_root: Path) -> str:
    text = require_file(vbal_root / "VBAL" / "run_vbal.yaml", "run_vbal.yaml").read_text()
    match = re.search(r"(?m)^\s*date:\s*&date\s+'([^']+)'", text)
    if not match:
        raise SystemExit("ERRO: data principal não encontrada no run_vbal.yaml")
    return match.group(1)


def link_hdiag_inputs(vbal_root: Path, workspace: Path, run_dir: Path) -> None:
    vbal_run = vbal_root / "VBAL"
    symlink_force(vbal_root / "samples", workspace / "samples")
    symlink_force(vbal_run, workspace / "vbal")

    required = [
        "bg.nc",
        "namelist.atmosphere_240km",
        "streams.atmosphere_240km",
    ]
    template_fields = sorted(vbal_run.glob("templateFields.*.nc"))
    if len(template_fields) != 1:
        raise SystemExit("ERRO: esperado exatamente um templateFields.*.nc no workspace VBAL.")

    for name in required:
        symlink_force(require_file(vbal_run / name, name), run_dir / name)
    symlink_force(template_fields[0], run_dir / template_fields[0].name)

    for pattern in [
        "*.graph.info",
        "*.graph.info.part.*",
        "*.invariant.nc",
        "stream_list.atmosphere.*",
        "geovars.yaml",
        "keptvars.yaml",
        "[A-Z]*",
    ]:
        for source in vbal_run.glob(pattern):
            if source.name not in required:
                symlink_force(source, run_dir / source.name)


def write_hdiag_yaml(path: Path, nmembers: int, date: str) -> None:
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
  bump vunit: "avgheight"
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

  saber central block:
    saber block name: BUMP_NICAS
    calibration:
      io:
        files prefix: mpas
      drivers:
        compute covariance: true
        compute correlation: true
        multivariate strategy: univariate
        write global sampling: true
        compute variance: true
        compute moments: true
        write diagnostics: true
      sampling:
        computation grid size: 12000
        diagnostic grid size: 1000
        distance classes: 10
        distance class width: 1000.0e3
        reduced levels: 10
        local diagnostic: true
        averaging length-scale: 3000.0e3
      variance:
        objective filtering: true
        filtering iterations: 1
        initial length-scale:
        - variables: *vars
          value: 3000.0e3
      fit:
        horizontal filtering length-scale: 3000.0e3
      output model files:
      - parameter: stddev
        file:
          filename: ./mpas.stddev.nc
          date: *date
          stream name: control
      - parameter: cor_rh
        file:
          filename: ./mpas.cor_rh.nc
          date: *date
          stream name: control
      - parameter: cor_rv
        file:
          filename: ./mpas.cor_rv.nc
          date: *date
          stream name: control

  saber outer blocks:
  - saber block name: BUMP_VerticalBalance
    read:
      io:
        data directory: ../vbal
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
"""
    write_text(path, text)


def write_hdiag_pbs(config, run_dir: Path) -> None:
    nproc = int(config["mesh"].get("nproc", config["pbs"].get("nproc", 64)))
    queue = config["pbs"].get("queues", {}).get("bmatrix", config["pbs"].get("queue", "pesqmini"))
    walltime = config["pbs"].get("walltime", {}).get("bmatrix", config["pbs"].get("walltime_short", "00:10:00"))
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    exe = toolbox_exe(config)

    text = f"""#!/bin/bash
#PBS -N mpasjediBTrainingHDIAG
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

rm -f run_hdiag.runlog stdout.log stderr.log
mpiexec -n {nproc} {exe} ./run_hdiag.yaml ./run_hdiag.runlog > stdout.log 2> stderr.log
"""
    write_text(run_dir / "qsub_hdiag.bash", text)


def require_hdiag_members(samples: list[Path]) -> None:
    if len(samples) < MIN_HDIAG_MEMBERS:
        raise SystemExit(
            "ERRO: HDIAG/NICAS requer pelo menos "
            f"{MIN_HDIAG_MEMBERS} membros; encontrados={len(samples)}. "
            "O BUMP exige ens_ne/ens_nsub > 3."
        )


def prepare_hdiag(
    config,
    vbal_workspace_path: str | Path,
    workspace: str | Path | None = None,
    clean: bool = False,
) -> Path:
    vbal_root = Path(vbal_workspace_path)
    validate_vbal(vbal_root)
    samples = sorted((vbal_root / "samples").glob("PTB_f48mf24_*.nc"))
    if not samples:
        raise SystemExit("ERRO: nenhum PTB original encontrado no workspace VBAL.")
    require_hdiag_members(samples)

    out = Path(workspace) if workspace else hdiag_workspace(config, vbal_root)
    if clean and out.exists():
        shutil.rmtree(out)
    run_dir = out / "HDIAG"
    run_dir.mkdir(parents=True, exist_ok=True)

    link_hdiag_inputs(vbal_root, out, run_dir)
    write_hdiag_yaml(run_dir / "run_hdiag.yaml", len(samples), vbal_date(vbal_root))
    write_hdiag_pbs(config, run_dir)
    write_text(
        out / "README.md",
        f"# HDIAG/NICAS workspace\n\nVBAL workspace: `{vbal_root}`\nMembers: {len(samples)}\n",
    )

    print("=== HDIAG/NICAS workspace ===")
    print(f"WORKSPACE={out}")
    print(f"RUN_DIR={run_dir}")
    print(f"MEMBERS={len(samples)}")
    print(f"YAML={run_dir / 'run_hdiag.yaml'}")
    print(f"PBS={run_dir / 'qsub_hdiag.bash'}")
    return out


def submit_hdiag(workspace: str | Path, wait: bool = False, poll_seconds: int = 30) -> str:
    run_dir = Path(workspace) / "HDIAG"
    require_file(run_dir / "qsub_hdiag.bash", "qsub_hdiag.bash")
    jobid = qsub("qsub_hdiag.bash", run_dir)
    write_text(run_dir / "job_id.txt", jobid + "\n")
    if wait:
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)
    return jobid


def validate_hdiag(workspace: str | Path) -> bool:
    root = Path(workspace)
    run_dir = root / "HDIAG"
    log = run_dir / "run_hdiag.runlog"
    text = log.read_text(errors="replace") if log.is_file() else ""
    errors = []
    if not log.is_file():
        errors.append("run_hdiag.runlog ausente")
    if "Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente no run_hdiag.runlog")
    for name in ["mpas.stddev.nc", "mpas.cor_rh.nc", "mpas.cor_rv.nc"]:
        if not (run_dir / name).is_file():
            errors.append(f"produto HDIAG ausente: {name}")

    print("=== HDIAG validation ===")
    print(f"WORKSPACE={root}")
    if errors:
        for error in errors:
            print(f"  - {error}")
        print_hdiag_diagnostics(root)
        raise SystemExit("ERRO: HDIAG falhou ou ficou incompleto.")
    print("SUCCESS: HDIAG validado.")
    return True


def print_hdiag_diagnostics(workspace: Path, tail_lines: int = 80) -> None:
    run_dir = workspace / "HDIAG"
    print("=== HDIAG diagnostics ===")
    for name in ["stdout.log", "stderr.log", "run_hdiag.runlog", "log.atmosphere.0000.err"]:
        path = run_dir / name
        print(f"--- {path} (ultimas {tail_lines} linhas) ---")
        if not path.is_file():
            print("[arquivo ausente]")
            continue
        lines = path.read_text(errors="replace").splitlines()
        print("\n".join(lines[-tail_lines:]) or "[arquivo vazio]")

    stdout = run_dir / "stdout.log"
    if stdout.is_file() and "ens_ne/ens_nsub should be larger than 3" in stdout.read_text(
        errors="replace"
    ):
        print(
            "CAUSA IDENTIFICADA: BUMP_NICAS requer pelo menos 4 membros "
            "por sub-ensemble."
        )


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


def hdiag_prepare_command(args) -> int:
    config = load_config(args.config)
    prepare_hdiag(config, args.vbal_workspace, workspace=args.workspace, clean=args.clean)
    return 0


def hdiag_submit_command(args) -> int:
    jobid = submit_hdiag(args.workspace, wait=args.wait, poll_seconds=args.poll_seconds)
    print(f"JOBID={jobid}")
    return 0


def hdiag_validate_command(args) -> int:
    validate_hdiag(args.workspace)
    return 0


def hdiag_all_command(args) -> int:
    config = load_config(args.config)
    workspace = prepare_hdiag(
        config,
        args.vbal_workspace,
        workspace=args.workspace,
        clean=args.clean,
    )
    jobid = submit_hdiag(workspace, wait=True, poll_seconds=args.poll_seconds)
    print(f"JOBID={jobid}")
    validate_hdiag(workspace)
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

    hprep = sub.add_parser("hdiag-prepare", help="Prepara calibração HDIAG/NICAS")
    hprep.add_argument("--config", default=DEFAULT_CONFIG)
    hprep.add_argument("--vbal-workspace", required=True)
    hprep.add_argument("--workspace")
    hprep.add_argument("--clean", action="store_true")
    hprep.set_defaults(func=hdiag_prepare_command)

    hsubmit = sub.add_parser("hdiag-submit", help="Submete job HDIAG/NICAS")
    hsubmit.add_argument("--workspace", required=True)
    hsubmit.add_argument("--wait", action="store_true")
    hsubmit.add_argument("--poll-seconds", type=int, default=30)
    hsubmit.set_defaults(func=hdiag_submit_command)

    hvalidate = sub.add_parser("hdiag-validate", help="Valida saída HDIAG/NICAS")
    hvalidate.add_argument("--workspace", required=True)
    hvalidate.set_defaults(func=hdiag_validate_command)

    hall = sub.add_parser("hdiag-all", help="Prepara, submete, espera e valida HDIAG/NICAS")
    hall.add_argument("--config", default=DEFAULT_CONFIG)
    hall.add_argument("--vbal-workspace", required=True)
    hall.add_argument("--workspace")
    hall.add_argument("--clean", action="store_true")
    hall.add_argument("--poll-seconds", type=int, default=30)
    hall.set_defaults(func=hdiag_all_command)

    return p


def main(argv=None):
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
