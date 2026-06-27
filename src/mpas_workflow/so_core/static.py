from __future__ import annotations

import shutil
from pathlib import Path

from ..nicas_core.static import link_nicas_support
from ..shell import require_file, symlink_force
from .model import SO_BACKGROUND_VARIABLES


def link_so_support(hdiag_run: Path, run_dir: Path) -> Path:
    link_nicas_support(hdiag_run, run_dir)
    (run_dir / "bg.nc").unlink(missing_ok=True)
    templates = sorted(hdiag_run.glob("templateFields.*.nc"))
    if len(templates) != 1:
        raise SystemExit("ERRO: esperado exatamente um templateFields.*.nc no workspace HDIAG")
    return templates[0]


def validate_so_background(path: Path) -> bool:
    try:
        import netCDF4
    except ImportError as exc:
        raise SystemExit("ERRO: so-prepare requer o módulo Python netCDF4.") from exc

    with netCDF4.Dataset(path) as dataset:
        missing = [name for name in SO_BACKGROUND_VARIABLES if name not in dataset.variables]
    if missing:
        raise SystemExit(
            f"ERRO: background SO incompleto em {path}; variáveis ausentes: " + ", ".join(missing)
        )
    return True


def _copy_attrs(src_var, dst_var) -> None:
    for attr in src_var.ncattrs():
        if attr == "_FillValue":
            continue
        try:
            dst_var.setncattr(attr, src_var.getncattr(attr))
        except Exception:
            pass


def _create_or_replace(dataset, name: str, template, values, long_name: str, units: str) -> None:
    if name in dataset.variables:
        del dataset.variables[name]
    variable = dataset.createVariable(name, template.dtype, template.dimensions)
    _copy_attrs(template, variable)
    variable[:] = values.astype(template.dtype, copy=False)
    variable.setncattr("long_name", long_name)
    variable.setncattr("units", units)


def create_so_background(source: Path, output: Path) -> None:
    try:
        import netCDF4
    except ImportError as exc:
        raise SystemExit("ERRO: so-prepare requer o módulo Python netCDF4.") from exc

    source = require_file(source.resolve(), "template MPAS completo")
    output.unlink(missing_ok=True)
    shutil.copy2(source, output)

    with netCDF4.Dataset(output, "a") as dataset:
        native = ["pressure_base", "pressure_p", "theta", "qv"]
        missing = [name for name in native if name not in dataset.variables]
        if missing:
            raise SystemExit(
                f"ERRO: template MPAS sem variáveis nativas para o SO: {', '.join(missing)}"
            )

        pressure_p = dataset.variables["pressure_p"]
        pressure = dataset.variables["pressure_base"][:] + pressure_p[:]
        theta = dataset.variables["theta"]
        qv = dataset.variables["qv"]
        derived = {
            "pressure": (pressure_p, pressure, "pressure", "Pa"),
            "air_pressure": (pressure_p, pressure, "air pressure", "Pa"),
            "air_pressure_at_surface": (
                dataset.variables["surface_pressure"],
                dataset.variables["surface_pressure"][:],
                "air pressure at surface",
                "Pa",
            ),
            "temperature": (
                theta,
                theta[:] * (pressure / 100000.0) ** (2.0 / 7.0),
                "temperature",
                "K",
            ),
            "air_temperature": (
                theta,
                theta[:] * (pressure / 100000.0) ** (2.0 / 7.0),
                "air temperature",
                "K",
            ),
            "spechum": (qv, qv[:] / (1.0 + qv[:]), "specific humidity", "kg kg-1"),
            "eastward_wind": (
                dataset.variables["uReconstructZonal"],
                dataset.variables["uReconstructZonal"][:],
                "eastward wind",
                "m s-1",
            ),
            "northward_wind": (
                dataset.variables["uReconstructMeridional"],
                dataset.variables["uReconstructMeridional"][:],
                "northward wind",
                "m s-1",
            ),
        }
        for name, (template, values, long_name, units) in derived.items():
            if name in dataset.variables:
                continue
            variable = dataset.createVariable(name, template.dtype, template.dimensions)
            variable[:] = values.astype(template.dtype, copy=False)
            variable.setncattr("long_name", long_name)
            variable.setncattr("units", units)

    validate_so_background(output)
