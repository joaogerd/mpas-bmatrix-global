from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

import numpy as np

from .config import load_config
from .nmc import DEFAULT_DIFF_VARIABLES, pair_dir, parse_variables_arg

TIME_FORMAT = "%Y-%m-%d_%H:%M:%S"


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT)


def format_time(value: datetime) -> str:
    return value.strftime(TIME_FORMAT)


def iter_valid_times(start: str, end: str, step_hours: int):
    if step_hours <= 0:
        raise SystemExit("ERRO: --valid-interval-hours deve ser positivo.")
    current = parse_time(start)
    last = parse_time(end)
    step = timedelta(hours=step_hours)
    while current <= last:
        yield format_time(current)
        current += step


def diff_file(config, valid_time: str) -> Path:
    return pair_dir(config, valid_time) / "nmc_diff_f048_minus_f024.nc"


def _as_float_array(var) -> np.ndarray:
    data = np.asarray(var[:], dtype=np.float64)
    if np.ma.isMaskedArray(data):
        data = data.filled(np.nan)
    return data


def _stats_for_array(data: np.ndarray) -> dict[str, float | int]:
    total_count = int(data.size)
    nan_count = int(np.isnan(data).sum())
    inf_count = int(np.isinf(data).sum())
    finite = data[np.isfinite(data)]
    finite_count = int(finite.size)

    if finite_count == 0:
        return {
            "total_count": total_count,
            "finite_count": finite_count,
            "nan_count": nan_count,
            "inf_count": inf_count,
            "min": math.nan,
            "max": math.nan,
            "mean": math.nan,
            "std": math.nan,
            "rms": math.nan,
            "abs_max": math.nan,
        }

    return {
        "total_count": total_count,
        "finite_count": finite_count,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "rms": float(np.sqrt(np.mean(finite * finite))),
        "abs_max": float(np.max(np.abs(finite))),
    }


def collect_perturbation_stats(
    config,
    valid_times: Iterable[str],
    variables: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    try:
        import netCDF4
    except ImportError as exc:
        raise SystemExit("ERRO: o comando bmatrix stats requer o módulo Python netCDF4.") from exc

    requested = list(variables) if variables else list(DEFAULT_DIFF_VARIABLES)
    rows: list[dict[str, object]] = []

    for valid_time in valid_times:
        path = diff_file(config, valid_time)
        if not path.exists():
            raise SystemExit(
                f"ERRO: arquivo de diferença NMC não encontrado para {valid_time}: {path}\n"
                "Gere antes com: mpaswf nmc diff --valid-time <VALID_TIME>"
            )

        with netCDF4.Dataset(path) as ds:
            for name in requested:
                if name not in ds.variables:
                    rows.append(
                        {
                            "valid_time": valid_time,
                            "file": str(path),
                            "variable": name,
                            "status": "missing",
                            "dimensions": "",
                            "total_count": 0,
                            "finite_count": 0,
                            "nan_count": 0,
                            "inf_count": 0,
                            "min": math.nan,
                            "max": math.nan,
                            "mean": math.nan,
                            "std": math.nan,
                            "rms": math.nan,
                            "abs_max": math.nan,
                        }
                    )
                    continue

                var = ds.variables[name]
                stats = _stats_for_array(_as_float_array(var))
                status = "ok"
                if stats["finite_count"] == 0:
                    status = "no_finite_values"
                elif stats["nan_count"] or stats["inf_count"]:
                    status = "has_nan_or_inf"

                rows.append(
                    {
                        "valid_time": valid_time,
                        "file": str(path),
                        "variable": name,
                        "status": status,
                        "dimensions": ",".join(var.dimensions),
                        **stats,
                    }
                )

    return rows


def write_stats_csv(rows: list[dict[str, object]], output: str | Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "valid_time",
        "file",
        "variable",
        "status",
        "dimensions",
        "total_count",
        "finite_count",
        "nan_count",
        "inf_count",
        "min",
        "max",
        "mean",
        "std",
        "rms",
        "abs_max",
    ]
    with output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return output


def print_stats_summary(rows: list[dict[str, object]], max_rows: int = 50):
    print("=== B-matrix NMC perturbation stats ===")
    print(f"Rows: {len(rows)}")

    bad = [r for r in rows if r["status"] != "ok"]
    print(f"Problems: {len(bad)}")
    if bad:
        print("Problem rows:")
        for row in bad[:max_rows]:
            print(
                f"  {row['valid_time']} {row['variable']} status={row['status']} "
                f"nan={row['nan_count']} inf={row['inf_count']} file={row['file']}"
            )
        if len(bad) > max_rows:
            print(f"  ... {len(bad) - max_rows} more problem rows")

    ok_rows = [r for r in rows if r["status"] == "ok"]
    print()
    print("Sample OK rows:")
    for row in ok_rows[:max_rows]:
        print(
            f"  {row['valid_time']} {row['variable']}: "
            f"min={row['min']:.6g} max={row['max']:.6g} "
            f"mean={row['mean']:.6g} std={row['std']:.6g} rms={row['rms']:.6g}"
        )


def stats_command(args) -> int:
    config = load_config(args.config)
    variables = parse_variables_arg(args.variables)
    valid_times = list(
        iter_valid_times(args.start_valid_time, args.end_valid_time, args.valid_interval_hours)
    )
    rows = collect_perturbation_stats(config, valid_times, variables=variables)

    output = args.output
    if output is None:
        output = (
            Path(config["project"]["work_root"])
            / "bmatrix"
            / "stats"
            / f"nmc_perturbation_stats_{args.start_valid_time.replace(':', '.')}_{args.end_valid_time.replace(':', '.')}.csv"
        )

    output = write_stats_csv(rows, output)
    print_stats_summary(rows, max_rows=args.max_print)
    print()
    print(f"CSV={output}")

    bad = [r for r in rows if r["status"] != "ok"]
    return 1 if bad and args.fail_on_problem else 0


def parser():
    p = argparse.ArgumentParser(prog="python -m mpas_workflow.bmatrix")
    sub = p.add_subparsers(dest="cmd", required=True)

    stats = sub.add_parser("stats", help="Calcula estatísticas básicas das perturbações NMC")
    stats.add_argument("--config", default="configs/jaci-x1.10242.yaml")
    stats.add_argument("--start-valid-time", required=True)
    stats.add_argument("--end-valid-time", required=True)
    stats.add_argument("--valid-interval-hours", type=int, default=24)
    stats.add_argument("--variables")
    stats.add_argument("--output")
    stats.add_argument("--max-print", type=int, default=30)
    stats.add_argument("--fail-on-problem", action="store_true")
    stats.set_defaults(func=stats_command)

    return p


def main(argv=None):
    args = parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
