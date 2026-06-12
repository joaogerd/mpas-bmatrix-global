from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

import numpy as np

from .nmc import parse_variables_arg
from .shell import symlink_force


TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"
DEFAULT_VARIABLES = ["u", "w", "rho", "theta", "qv", "surface_pressure"]


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def bmatrix_root(config) -> Path:
    return Path(config["project"]["work_root"]) / "bmatrix"


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
