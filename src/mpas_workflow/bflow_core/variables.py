from __future__ import annotations

from pathlib import Path

import netCDF4

from .model import BflowPair, compact_time
from .netcdf_utils import ensure_dims, upsert_var

COPY_VARIABLES = [
    "surface_pressure",
    "uReconstructZonal",
    "uReconstructMeridional",
    "qv", "qc", "qr", "qi", "qs", "qg",
    "pressure_p", "pressure_base",
]


def add_variables(input_path: Path, full_path: Path) -> None:
    if not full_path.exists():
        raise SystemExit(f"ERRO: FULL file não existe; rode primeiro uv_to_psichi: {full_path}")
    with netCDF4.Dataset(input_path) as src, netCDF4.Dataset(full_path, "a") as dst:
        theta = src.variables["theta"]
        ensure_dims(src, dst, theta)

        pressure = src.variables["pressure_p"][:] + src.variables["pressure_base"][:]
        temperature = src.variables["theta"][:] * ((pressure / 100000.0) ** (2.0 / 7.0))
        spechum = src.variables["qv"][:] / (1.0 + src.variables["qv"][:])

        for name in COPY_VARIABLES:
            if name not in src.variables:
                print(f"AVISO: variável ausente em {input_path}: {name}")
                continue
            var = src.variables[name]
            ensure_dims(src, dst, var)
            upsert_var(dst, var, name)

        pvar = src.variables["pressure_p"]
        out = upsert_var(dst, pvar, "pressure", pressure.astype(pvar.dtype, copy=False))
        out.setncattr("long_name", "pressure")
        out.setncattr("units", "Pa")

        tvar = upsert_var(dst, theta, "temperature", temperature.astype(theta.dtype, copy=False))
        tvar.setncattr("long_name", "temperature")
        tvar.setncattr("units", "K")

        qv = src.variables["qv"]
        svar = upsert_var(dst, qv, "spechum", spechum.astype(qv.dtype, copy=False))
        svar.setncattr("long_name", "specific humidity")
        svar.setncattr("units", "kg kg^{-1}")


def add_variables_for_pairs(workspace: Path, pairs: list[BflowPair]) -> None:
    for pair in pairs:
        vdir = workspace / "output" / compact_time(pair.valid_time)
        print(f"add variables {pair.valid_time} f48")
        add_variables(pair.f048, vdir / "FULL_f48.nc")
        print(f"add variables {pair.valid_time} f24")
        add_variables(pair.f024, vdir / "FULL_f24.nc")
