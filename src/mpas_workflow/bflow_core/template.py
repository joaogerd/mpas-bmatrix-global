from __future__ import annotations

from pathlib import Path

import netCDF4

from .netcdf_utils import copy_attrs


def generate_template_ptb(first_ref: Path, workspace: Path) -> Path:
    first_ref = Path(first_ref)
    out = Path(workspace) / "template_PTB.nc"
    if not first_ref.exists():
        raise SystemExit(f"ERRO: arquivo não encontrado: {first_ref}")
    if out.exists():
        out.unlink()

    with netCDF4.Dataset(first_ref) as src, netCDF4.Dataset(out, "w") as dst:
        theta = src.variables["theta"]
        for dim_name in theta.dimensions:
            dim = src.dimensions[dim_name]
            dst.createDimension(dim_name, None if dim.isunlimited() else len(dim))
        copy_attrs(src, dst)
        for name, long_name in [
            ("stream_function", "stream function"),
            ("velocity_potential", "velocity potential"),
        ]:
            kwargs = {}
            fill_value = getattr(theta, "_FillValue", None)
            if fill_value is not None:
                kwargs["fill_value"] = fill_value
            var = dst.createVariable(name, theta.dtype, theta.dimensions, **kwargs)
            var[:] = theta[:] * 0.0
            var.setncattr("long_name", long_name)
            var.setncattr("units", "m^2 s^(-2)")
    print(f"template PTB: {out}")
    return out
