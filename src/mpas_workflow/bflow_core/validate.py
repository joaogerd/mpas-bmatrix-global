from __future__ import annotations

from pathlib import Path

import netCDF4

from .model import BflowPair, compact_time

FULL_REQUIRED = ["stream_function", "velocity_potential"]
PTB_REQUIRED = [
    "stream_function",
    "velocity_potential",
    "temperature",
    "spechum",
    "pressure",
    "surface_pressure",
    "uReconstructZonal",
    "uReconstructMeridional",
]


def require_vars(path: Path, names: list[str]) -> None:
    if not path.exists():
        raise SystemExit(f"ERRO: produto ausente: {path}")
    with netCDF4.Dataset(path) as ds:
        for name in names:
            if name not in ds.variables:
                raise SystemExit(f"ERRO: variável ausente em {path}: {name}")
            var = ds.variables[name]
            if name in {"stream_function", "velocity_potential"}:
                expected = ("Time", "nCells", "nVertLevels")
                if tuple(var.dimensions) != expected:
                    raise SystemExit(
                        f"ERRO: dimensões inválidas para {name} em {path}: "
                        f"{var.dimensions}; esperado {expected}"
                    )


def validate_products(workspace: Path, pairs: list[BflowPair], stage: str) -> None:
    if stage not in {"full", "ptb"}:
        raise ValueError(f"stage inválido: {stage}")
    for pair in pairs:
        vdir = workspace / "output" / compact_time(pair.valid_time)
        if stage == "full":
            require_vars(vdir / "FULL_f48.nc", FULL_REQUIRED)
            require_vars(vdir / "FULL_f24.nc", FULL_REQUIRED)
        else:
            require_vars(vdir / "PTB_f48mf24.nc", PTB_REQUIRED)
        print(f"OK {stage}: {pair.valid_time}")
