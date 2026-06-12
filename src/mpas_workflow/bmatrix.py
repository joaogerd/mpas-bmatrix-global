from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np

from .shell import qsub, require_file, symlink_force, write_text


TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"
DEFAULT_VARIABLES = ["u", "w", "rho", "theta", "qv", "surface_pressure"]
TOOLBOX_EXE = "mpasjedi_error_covariance_toolbox.x"


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def bmatrix_root(config) -> Path:
    return Path(config["project"]["work_root"]) / "bmatrix"


def toolbox_executable(config) -> Path:
    configured = config.get("install", {}).get("mpasjedi_error_covariance_toolbox")
    if configured:
        return Path(configured)
    return Path(config["install"]["root"]) / "bin" / TOOLBOX_EXE


def toolbox_run_dir(config, name: str) -> Path:
    return bmatrix_root(config) / "toolbox" / name


def _valid_time_from_pair_dir(path: Path) -> Optional[str]:
    marker = "_valid_"
    if marker not in path.name:
        return None
    value = path.name.split(marker, 1)[1]
    if len(value) != 19:
        return value
    return value.replace(".", ":")


def find_nmc_diff_files(config, start_valid_time: Optional[str] = None, end_valid_time: Optional[str] = None):
    nmc_root = Path(config["project"]["work_root"]) / "nmc_pairs"
    if not nmc_root.exists():
        return []

    start = parse_time(start_valid_time) if start_valid_time else None
    end = parse_time(end_valid_time) if end_valid_time else None
    found = []

    for pair_dir in sorted(nmc_root.glob("nmc_*_valid_*")):
        valid_time = _valid_time_from_pair_dir(pair_dir)
        if not valid_time:
            continue
        try:
            vt = parse_time(valid_time)
        except ValueError:
            continue
        if start and vt < start:
            continue
        if end and vt > end:
            continue
        diff_file = pair_dir / "nmc_diff_f048_minus_f024.nc"
        if diff_file.exists():
            found.append((valid_time, diff_file))

    return found


def collect_samples(config, start_valid_time: Optional[str] = None, end_valid_time: Optional[str] = None) -> Path:
    samples = find_nmc_diff_files(config, start_valid_time, end_valid_time)
    if not samples:
        raise SystemExit("ERRO: nenhuma diferença NMC encontrada para o intervalo solicitado.")

    out_dir = bmatrix_root(config) / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "manifest.csv"

    with manifest.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sample", "valid_time", "path"])
        for idx, (valid_time, src) in enumerate(samples, start=1):
            link = out_dir / f"sample_{idx:05d}.nc"
            symlink_force(src, link)
            writer.writerow([link.name, valid_time, str(src.resolve())])

    print("=== B-matrix sample collection ===")
    print(f"SAMPLES={len(samples)}")
    print(f"MANIFEST={manifest}")
    return manifest


def _read_manifest(path: Path) -> List[Path]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return [Path(row["path"]) for row in reader]


def _copy_dimensions(src, dst):
    for name, dim in src.dimensions.items():
        dst.createDimension(name, None if dim.isunlimited() else len(dim))


def compute_stats(config, manifest: Optional[str | Path], variables: Optional[Iterable[str]], output: Optional[str | Path]) -> Path:
    try:
        import netCDF4
    except ImportError as exc:
        raise SystemExit("ERRO: bmatrix stats requer o módulo Python netCDF4.") from exc

    manifest_path = Path(manifest) if manifest else bmatrix_root(config) / "samples" / "manifest.csv"
    if not manifest_path.exists():
        raise SystemExit(f"ERRO: manifest não encontrado: {manifest_path}")

    sample_files = _read_manifest(manifest_path)
    if not sample_files:
        raise SystemExit("ERRO: manifest não contém amostras.")

    requested = list(variables) if variables else list(DEFAULT_VARIABLES)
    output_path = Path(output) if output else bmatrix_root(config) / "stats" / "bmatrix_nmc_stats.nc"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with netCDF4.Dataset(sample_files[0]) as first, netCDF4.Dataset(output_path, "w") as dst:
        _copy_dimensions(first, dst)
        dst.setncattr("source_manifest", str(manifest_path.resolve()))
        dst.setncattr("sample_count", len(sample_files))
        dst.setncattr("operation", "NMC sample mean, rms and stddev")

        available = [v for v in requested if v in first.variables]
        if not available:
            raise SystemExit("ERRO: nenhuma variável solicitada existe no primeiro arquivo de amostra.")

        for name in available:
            ref = first.variables[name]
            dims = ref.dimensions
            total = np.zeros(ref.shape, dtype=np.float64)
            total2 = np.zeros(ref.shape, dtype=np.float64)
            count = np.zeros(ref.shape, dtype=np.int64)

            for sample in sample_files:
                with netCDF4.Dataset(sample) as ds:
                    if name not in ds.variables:
                        print(f"WARNING: variável ausente em {sample}: {name}")
                        continue
                    var = ds.variables[name]
                    if var.dimensions != dims:
                        print(f"WARNING: dimensões incompatíveis em {sample}: {name}")
                        continue
                    arr = var[:]
                    if hasattr(arr, "filled"):
                        arr = arr.filled(np.nan)
                    arr = np.asarray(arr, dtype=np.float64)
                    mask = np.isfinite(arr)
                    total[mask] += arr[mask]
                    total2[mask] += arr[mask] * arr[mask]
                    count[mask] += 1

            with np.errstate(invalid="ignore", divide="ignore"):
                mean = total / count
                rms = np.sqrt(total2 / count)
                variance = (total2 / count) - mean * mean
                variance = np.where(variance < 0.0, 0.0, variance)
                stddev = np.sqrt(variance)

            mean = np.where(count > 0, mean, np.nan)
            rms = np.where(count > 0, rms, np.nan)
            stddev = np.where(count > 0, stddev, np.nan)

            for suffix, data in [("mean", mean), ("rms", rms), ("stddev", stddev)]:
                out = dst.createVariable(f"{name}_{suffix}", "f8", dims)
                out[:] = data
                out.setncattr("source_variable", name)
                out.setncattr("sample_count", int(count.max()))

            print(f"OK: estatísticas calculadas para {name}")

    print("=== B-matrix NMC statistics ===")
    print(f"OUTPUT={output_path}")
    return output_path


def _toolbox_pbs(config, run_dir: Path, yaml_file: Path, nproc: int) -> str:
    project_root = config["project"]["project_root"]
    loader = config["environment"]["loader"]
    queue = config["pbs"]["queue"]
    walltime = config["pbs"].get("walltime_long", "04:00:00")
    return f'''#!/bin/bash
#PBS -N mpasjedi_bmatrix
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

mpiexec -n {nproc} ./{TOOLBOX_EXE} {yaml_file.name} > stdout.log 2> stderr.log
'''


def prepare_toolbox(config, yaml_file: str | Path, name: str = "default", nproc: Optional[int] = None) -> Path:
    src_yaml = require_file(yaml_file, "YAML do mpasjedi_error_covariance_toolbox")
    exe = require_file(toolbox_executable(config), TOOLBOX_EXE)
    nproc = int(nproc or config["pbs"].get("nproc") or config["mesh"]["nproc"])

    run_dir = toolbox_run_dir(config, name)
    run_dir.mkdir(parents=True, exist_ok=True)

    symlink_force(exe, run_dir / TOOLBOX_EXE)
    symlink_force(src_yaml, run_dir / src_yaml.name)
    write_text(run_dir / "run_mpasjedi_error_covariance_toolbox.pbs", _toolbox_pbs(config, run_dir, src_yaml, nproc))

    readme = (
        "# MPAS-JEDI error covariance toolbox\n\n"
        f"- executable: `{exe}`\n"
        f"- yaml: `{src_yaml}`\n"
        f"- nproc: `{nproc}`\n\n"
        "Submit with:\n\n"
        "```bash\n"
        "qsub run_mpasjedi_error_covariance_toolbox.pbs\n"
        "```\n"
    )
    write_text(run_dir / "README.md", readme)

    print("=== MPAS-JEDI error covariance toolbox ===")
    print(f"RUN_DIR={run_dir}")
    print(f"YAML={run_dir / src_yaml.name}")
    print(f"PBS={run_dir / 'run_mpasjedi_error_covariance_toolbox.pbs'}")
    return run_dir


def submit_toolbox(config, name: str = "default"):
    run_dir = toolbox_run_dir(config, name)
    pbs = require_file(run_dir / "run_mpasjedi_error_covariance_toolbox.pbs", "PBS do toolbox")
    qsub(pbs.name, run_dir)
