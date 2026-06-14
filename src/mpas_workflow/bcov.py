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
NICAS_VARIABLES = STATE_VARIABLES
NICAS_DIRAC_POINTS = [
    (-45.0, 0.0),
    (-135.0, 0.0),
    (45.0, 0.0),
    (135.0, 0.0),
    (-135.0, 45.0),
    (-45.0, 45.0),
    (45.0, 45.0),
    (135.0, 45.0),
    (-135.0, -45.0),
    (-45.0, -45.0),
    (45.0, -45.0),
    (135.0, -45.0),
]


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


def nicas_workspace(config, hdiag_workspace_path: str | Path) -> Path:
    return covariance_root(config) / "nicas" / Path(hdiag_workspace_path).name


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


def hdiag_date(hdiag_root: Path) -> str:
    text = require_file(hdiag_root / "HDIAG" / "run_hdiag.yaml", "run_hdiag.yaml").read_text()
    match = re.search(r"(?m)^\s*date:\s*&date\s+'([^']+)'", text)
    if not match:
        raise SystemExit("ERRO: data principal não encontrada no run_hdiag.yaml")
    return match.group(1)


def link_nicas_support(hdiag_run: Path, run_dir: Path) -> None:
    required = ["bg.nc", "namelist.atmosphere_240km", "streams.atmosphere_240km"]
    for name in required:
        symlink_force(require_file(hdiag_run / name, name), run_dir / name)

    for pattern in [
        "templateFields.*.nc",
        "*.graph.info",
        "*.graph.info.part.*",
        "*.invariant.nc",
        "stream_list.atmosphere.*",
        "geovars.yaml",
        "keptvars.yaml",
        "[A-Z]*",
    ]:
        for source in hdiag_run.glob(pattern):
            symlink_force(source, run_dir / source.name)


def write_nicas_yaml(
    path: Path,
    variable: str,
    date: str,
    nvertlevels: int,
) -> None:
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


def prepare_nicas(
    config,
    hdiag_workspace_path: str | Path,
    workspace: str | Path | None = None,
    clean: bool = False,
) -> Path:
    hdiag_root = Path(hdiag_workspace_path)
    validate_hdiag(hdiag_root)
    hdiag_run = hdiag_root / "HDIAG"
    date = hdiag_date(hdiag_root)
    out = Path(workspace) if workspace else nicas_workspace(config, hdiag_root)
    if clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    symlink_force(require_file(hdiag_run / "mpas.cor_rh.nc"), out / "mpas.cor_rh.nc")
    symlink_force(require_file(hdiag_run / "mpas.cor_rv.nc"), out / "mpas.cor_rv.nc")
    symlink_force(require_file(hdiag_run / "mpas.stddev.nc"), out / "mpas.stddev.nc")

    for variable in NICAS_VARIABLES:
        run_dir = out / variable
        run_dir.mkdir(parents=True, exist_ok=True)
        link_nicas_support(hdiag_run, run_dir)
        write_nicas_yaml(
            run_dir / "run_nicas.yaml",
            variable,
            date,
            int(config["mesh"].get("nvertlevels", 55)),
        )
        write_nicas_pbs(config, run_dir, variable)

    write_nicas_merge_files(config, out)
    write_text(
        out / "README.md",
        f"# NICAS split/merge workspace\n\nHDIAG workspace: `{hdiag_root}`\n",
    )
    print("=== NICAS split/merge workspace ===")
    print(f"WORKSPACE={out}")
    print(f"VARIABLES={','.join(NICAS_VARIABLES)}")
    print(f"MERGE_DIR={out / 'merge'}")
    return out


def _qsub_afterok(pbs_file: str, cwd: Path, jobids: list[str]) -> str:
    dependency = ":".join(jobids)
    cmd = ["qsub", "-W", f"depend=afterok:{dependency}", pbs_file]
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip())
    if proc.returncode != 0:
        raise SystemExit(f"ERRO: qsub do merge NICAS falhou com código {proc.returncode}")
    return proc.stdout.strip().split()[0]


def nicas_home_failure_files(run_dir: Path) -> list[Path]:
    failures = []
    for pattern in ["*.o*", "*.e*"]:
        for path in run_dir.glob(pattern):
            if path.is_file() and "Could not chdir to home directory" in path.read_text(
                errors="replace"
            ):
                failures.append(path)
    return sorted(set(failures))


def nicas_variable_errors(run_dir: Path) -> list[str]:
    runlog = run_dir / "run_nicas.runlog"
    text = runlog.read_text(errors="replace") if runlog.is_file() else ""
    errors = []
    if "Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0" not in text:
        errors.append("status final de sucesso ausente")
    for name in ["mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"]:
        if not (run_dir / name).is_file():
            errors.append(f"produto ausente: {name}")
    errors.extend(
        _validate_ranked_products(
            sorted(run_dir.glob("mpas_nicas_local_*")), "mpas_nicas_local"
        )
    )
    errors.extend(
        _validate_ranked_products(
            sorted(run_dir.glob("mpas_nicas_grids_local_*")), "mpas_nicas_grids_local"
        )
    )
    return errors


def clean_nicas_variable_outputs(run_dir: Path) -> None:
    for name in [
        "run_nicas.runlog",
        "stdout.log",
        "stderr.log",
        "mpas_nicas.nc",
        "mpas.nicas_norm.nc",
        "mpas.dirac_nicas.nc",
    ]:
        (run_dir / name).unlink(missing_ok=True)
    for pattern in ["mpas_nicas_local_*", "mpas_nicas_grids_local_*"]:
        for path in run_dir.glob(pattern):
            path.unlink()


def submit_nicas_variable(
    variable: str,
    run_dir: Path,
    retries: int,
    poll_seconds: int,
) -> str:
    for attempt in range(retries + 1):
        clean_nicas_variable_outputs(run_dir)
        for path in nicas_home_failure_files(run_dir):
            path.unlink()
        jobid = qsub("qsub_nicas.bash", run_dir)
        write_text(run_dir / "job_id.txt", jobid + "\n")
        wait_for_pbs_job(jobid, poll_seconds=poll_seconds)

        if nicas_home_failure_files(run_dir):
            if attempt < retries:
                print(f"Falha PBS/HOME na JACI, ressubmetendo variável {variable}.")
                continue
            raise SystemExit(
                f"ERRO: falha PBS/HOME persistiu para {variable} "
                f"após {retries} retries."
            )

        errors = nicas_variable_errors(run_dir)
        if not errors:
            print(f"SUCCESS: NICAS validado para {variable}.")
            return jobid

        raise SystemExit(
            f"ERRO: NICAS falhou para {variable}: " + "; ".join(errors)
        )
    raise AssertionError("loop de retry NICAS terminou inesperadamente")


def submit_nicas(
    workspace: str | Path,
    wait: bool = False,
    poll_seconds: int = 30,
    parallel: bool = False,
    retries: int = 2,
) -> str:
    root = Path(workspace)
    merge_dir = root / "merge"
    retries = max(0, retries)

    if parallel:
        jobids = []
        for variable in NICAS_VARIABLES:
            run_dir = root / variable
            jobid = qsub("qsub_nicas.bash", run_dir)
            write_text(run_dir / "job_id.txt", jobid + "\n")
            jobids.append(jobid)
        merge_jobid = _qsub_afterok("qsub_nicas_merge.bash", merge_dir, jobids)
    else:
        for variable in NICAS_VARIABLES:
            submit_nicas_variable(
                variable,
                root / variable,
                retries=retries,
                poll_seconds=poll_seconds,
            )
        merge_jobid = qsub("qsub_nicas_merge.bash", merge_dir)

    write_text(merge_dir / "job_id.txt", merge_jobid + "\n")
    if wait:
        wait_for_pbs_job(merge_jobid, poll_seconds=poll_seconds)
        validate_nicas(root)
    return merge_jobid


def validate_nicas(workspace: str | Path) -> bool:
    root = Path(workspace)
    errors = []
    for variable in NICAS_VARIABLES:
        run_dir = root / variable
        if nicas_home_failure_files(run_dir):
            errors.append(
                f"{variable}: falha PBS/HOME: Could not chdir to home directory"
            )
        errors.extend(f"{variable}: {error}" for error in nicas_variable_errors(run_dir))

    merge_dir = root / "merge"
    if nicas_home_failure_files(merge_dir):
        errors.append("merge: falha PBS/HOME: Could not chdir to home directory")
    for name in ["merge.done", "mpas_nicas.nc", "mpas.nicas_norm.nc", "mpas.dirac_nicas.nc"]:
        if not (merge_dir / name).is_file():
            errors.append(f"merge: produto ausente: {name}")
    errors.extend(
        f"merge: {error}"
        for error in _validate_ranked_products(
            sorted(merge_dir.glob("mpas_nicas_local_*")), "mpas_nicas_local"
        )
    )
    errors.extend(
        f"merge: {error}"
        for error in _validate_ranked_products(
            sorted(merge_dir.glob("mpas_nicas_grids_local_*")), "mpas_nicas_grids_local"
        )
    )

    print("=== NICAS validation ===")
    print(f"WORKSPACE={root}")
    if errors:
        for error in errors:
            print(f"  - {error}")
        raise SystemExit("ERRO: NICAS falhou ou ficou incompleto.")
    print("SUCCESS: NICAS split/merge validado.")
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


def nicas_prepare_command(args) -> int:
    config = load_config(args.config)
    prepare_nicas(config, args.hdiag_workspace, workspace=args.workspace, clean=args.clean)
    return 0


def nicas_submit_command(args) -> int:
    jobid = submit_nicas(
        args.workspace,
        wait=args.wait,
        poll_seconds=args.poll_seconds,
        parallel=args.parallel,
        retries=args.retries,
    )
    print(f"MERGE_JOBID={jobid}")
    return 0


def nicas_validate_command(args) -> int:
    validate_nicas(args.workspace)
    return 0


def nicas_all_command(args) -> int:
    config = load_config(args.config)
    workspace = prepare_nicas(
        config,
        args.hdiag_workspace,
        workspace=args.workspace,
        clean=args.clean,
    )
    jobid = submit_nicas(
        workspace,
        wait=True,
        poll_seconds=args.poll_seconds,
        parallel=args.parallel,
        retries=args.retries,
    )
    print(f"MERGE_JOBID={jobid}")
    validate_nicas(workspace)
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

    nprep = sub.add_parser("nicas-prepare", help="Prepara calibração NICAS split/merge")
    nprep.add_argument("--config", default=DEFAULT_CONFIG)
    nprep.add_argument("--hdiag-workspace", required=True)
    nprep.add_argument("--workspace")
    nprep.add_argument("--clean", action="store_true")
    nprep.set_defaults(func=nicas_prepare_command)

    nsubmit = sub.add_parser("nicas-submit", help="Submete jobs NICAS e merge dependente")
    nsubmit.add_argument("--workspace", required=True)
    nsubmit.add_argument("--wait", action="store_true", help="Aguarda e valida também o merge")
    nsubmit.add_argument("--poll-seconds", type=int, default=30)
    nsubmit.add_argument("--parallel", action="store_true", help="Usa submissão paralela legada")
    nsubmit.add_argument("--retries", type=int, default=2, help="Retries para falha PBS/HOME")
    nsubmit.set_defaults(func=nicas_submit_command)

    nvalidate = sub.add_parser("nicas-validate", help="Valida saída NICAS split/merge")
    nvalidate.add_argument("--workspace", required=True)
    nvalidate.set_defaults(func=nicas_validate_command)

    nall = sub.add_parser("nicas-all", help="Prepara, submete, espera e valida NICAS")
    nall.add_argument("--config", default=DEFAULT_CONFIG)
    nall.add_argument("--hdiag-workspace", required=True)
    nall.add_argument("--workspace")
    nall.add_argument("--clean", action="store_true")
    nall.add_argument("--poll-seconds", type=int, default=30)
    nall.add_argument("--parallel", action="store_true")
    nall.add_argument("--retries", type=int, default=2)
    nall.set_defaults(func=nicas_all_command)

    return p


def main(argv=None):
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
