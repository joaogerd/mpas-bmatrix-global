from __future__ import annotations

from pathlib import Path

import netCDF4
import numpy as np

from .model import BflowPair, compact_time
from .netcdf_utils import copy_attrs


def diff_file(f48: Path, f24: Path, out: Path, valid_time: str) -> None:
    if out.exists():
        out.unlink()
    with netCDF4.Dataset(f48) as ds48, netCDF4.Dataset(f24) as ds24, netCDF4.Dataset(out, "w") as dst:
        for name, dim in ds48.dimensions.items():
            dst.createDimension(name, None if dim.isunlimited() else len(dim))

        copy_attrs(ds48, dst)
        dst.setncattr("nmc_difference", "f048_minus_f024")
        dst.setncattr("valid_time", valid_time)
        dst.setncattr("source_f048", str(f48))
        dst.setncattr("source_f024", str(f24))

        common = [name for name in ds48.variables if name in ds24.variables]
        for name in common:
            v48 = ds48.variables[name]
            v24 = ds24.variables[name]
            if v48.dimensions != v24.dimensions:
                continue
            if not np.issubdtype(v48.dtype, np.number):
                continue
            kwargs = {}
            fill_value = getattr(v48, "_FillValue", None)
            if fill_value is not None:
                kwargs["fill_value"] = fill_value
            outvar = dst.createVariable(name, v48.dtype, v48.dimensions, **kwargs)
            copy_attrs(v48, outvar)
            outvar.setncattr("nmc_operation", "f048_minus_f024")
            outvar[:] = v48[:] - v24[:]


def diff_pairs(workspace: Path, pairs: list[BflowPair]) -> None:
    for pair in pairs:
        vdir = workspace / "output" / compact_time(pair.valid_time)
        out = vdir / "PTB_f48mf24.nc"
        print(f"ncdiff {pair.valid_time}: {out}")
        diff_file(vdir / "FULL_f48.nc", vdir / "FULL_f24.nc", out, pair.valid_time)
