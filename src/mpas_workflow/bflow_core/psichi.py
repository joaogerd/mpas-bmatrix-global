from __future__ import annotations

import shutil
from pathlib import Path

import netCDF4
import numpy as np

from .external import require_files
from .model import BflowPair, compact_time
from .weights import (
    apply_esmf_weights,
    latlon_shape_from_weights,
    load_esmf_sparse_weights,
    weight_paths,
)

MPAS_RADIUS_RATIO = 6_371_229.0 / 6_371_220.0


def _require_windspharm():
    try:
        from windspharm.standard import VectorWind
    except ImportError as exc:
        raise SystemExit(
            "ERRO: o backend Python psi/chi requer windspharm. "
            "Recomendado instalar via conda-forge, pois a dependência pyspharm é compilada:\n"
            "  conda install -c conda-forge windspharm pyspharm"
        ) from exc
    return VectorWind


def _latitudes_for_regular_grid(nlat: int) -> np.ndarray:
    return np.linspace(-90.0 + 90.0 / nlat, 90.0 - 90.0 / nlat, nlat)


def _flat_to_latlon(values: np.ndarray, nlat: int, nlon: int) -> np.ndarray:
    """Reshape ESMF flattened output to `(nlev, nlat, nlon)`.

    The previous NCL workflow used a 1-degree regular auxiliary grid with output
    shaped as `(nlev, nlat, nlon)`. ESMF weight files usually store regular grid
    dimensions as `(nlon, nlat)`, so this reshape keeps the Python path aligned
    with that convention. This still must be validated against one old NCL case.
    """
    return values.reshape((values.shape[0], nlat, nlon))


def _latlon_to_flat(values: np.ndarray) -> np.ndarray:
    return values.reshape((values.shape[0], values.shape[1] * values.shape[2]))


def uv_to_psichi_windspharm(u_ll: np.ndarray, v_ll: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert regular-grid wind to streamfunction and velocity potential.

    `windspharm` expects the latitude axis to be north-to-south. The BFLOW
    auxiliary grid is represented south-to-north here, matching the old NCL
    1-degree grid. Therefore we reverse latitude before and after calling
    `VectorWind.sfvp()`.
    """
    VectorWind = _require_windspharm()
    if u_ll.shape != v_ll.shape:
        raise ValueError(f"u/v com shapes diferentes: {u_ll.shape} != {v_ll.shape}")
    if u_ll.ndim != 3:
        raise ValueError(f"u_ll/v_ll devem ter shape (nlev, nlat, nlon); recebido {u_ll.shape}")

    # windspharm.standard expects dimensions as (nlat, nlon, nfields) for 3-D data.
    u_for_wind = np.transpose(u_ll[:, ::-1, :], (1, 2, 0))
    v_for_wind = np.transpose(v_ll[:, ::-1, :], (1, 2, 0))
    wind = VectorWind(u_for_wind, v_for_wind, gridtype="regular")
    psi, chi = wind.sfvp()
    psi = np.transpose(np.asarray(psi), (2, 0, 1))[:, ::-1, :]
    chi = np.transpose(np.asarray(chi), (2, 0, 1))[:, ::-1, :]
    return psi, chi


def write_full_file(template: Path, output_path: Path, psi_mpas: np.ndarray, chi_mpas: np.ndarray) -> None:
    if output_path.exists():
        output_path.unlink()
    shutil.copy2(template, output_path)
    with netCDF4.Dataset(output_path, "a") as ds:
        for name, data, long_name, scale in [
            ("stream_function", psi_mpas, "stream function", 1.0),
            ("velocity_potential", chi_mpas, "velocity potential", -1.0),
        ]:
            if name not in ds.variables:
                raise SystemExit(f"ERRO: variável ausente no template: {name}")
            var = ds.variables[name]
            var[0, :, :] = (data * scale * MPAS_RADIUS_RATIO).T
            var.setncattr("long_name", long_name)
            var.setncattr("units", "m^2 s^(-2)")
            var.setncattr("bflow_python_backend", "windspharm_esmf_sparse_weights")


def convert_file(
    input_path: Path,
    output_path: Path,
    template: Path,
    mpas_to_latlon_weights,
    latlon_to_mpas_weights,
) -> None:
    require_files([input_path, template], "psi/chi windspharm")
    nlat, nlon = latlon_shape_from_weights(mpas_to_latlon_weights)

    with netCDF4.Dataset(input_path) as ds:
        for name in ("uReconstructZonal", "uReconstructMeridional"):
            if name not in ds.variables:
                raise SystemExit(f"ERRO: variável ausente em {input_path}: {name}")
        # MPAS files store wind as (Time, nCells, nVertLevels).  The sparse
        # weight application expects (nlev, nCells), same convention as the old
        # NCL script after transpose().
        u_cell = np.asarray(ds.variables["uReconstructZonal"][0, :, :], dtype="f8").T
        v_cell = np.asarray(ds.variables["uReconstructMeridional"][0, :, :], dtype="f8").T

    u_ll = _flat_to_latlon(apply_esmf_weights(u_cell, mpas_to_latlon_weights), nlat, nlon)
    v_ll = _flat_to_latlon(apply_esmf_weights(v_cell, mpas_to_latlon_weights), nlat, nlon)

    psi_ll, chi_ll = uv_to_psichi_windspharm(u_ll, v_ll)

    psi_mpas = apply_esmf_weights(_latlon_to_flat(psi_ll), latlon_to_mpas_weights)
    chi_mpas = apply_esmf_weights(_latlon_to_flat(chi_ll), latlon_to_mpas_weights)
    write_full_file(template, output_path, psi_mpas, chi_mpas)


def convert_pair(config, workspace: Path, pair: BflowPair) -> None:
    workspace = Path(workspace).resolve()
    mpas_to_latlon_path, latlon_to_mpas_path = weight_paths(config, workspace)
    mpas_to_latlon_weights = load_esmf_sparse_weights(mpas_to_latlon_path)
    latlon_to_mpas_weights = load_esmf_sparse_weights(latlon_to_mpas_path)
    template = workspace / "template_PTB.nc"
    require_files([template], "psi/chi windspharm")

    vcompact = compact_time(pair.valid_time)
    outdir = workspace / "output" / vcompact
    outdir.mkdir(parents=True, exist_ok=True)
    for label, input_path, output_path in [
        ("f48", workspace / "inputs" / vcompact / "f048.nc", outdir / "FULL_f48.nc"),
        ("f24", workspace / "inputs" / vcompact / "f024.nc", outdir / "FULL_f24.nc"),
    ]:
        print(f"windspharm psi/chi {label} {pair.valid_time}")
        convert_file(
            input_path,
            output_path,
            template,
            mpas_to_latlon_weights,
            latlon_to_mpas_weights,
        )
        require_files([output_path], f"psi/chi windspharm {label} output")


def convert_uv_to_psichi(config, workspace: Path, pairs: list[BflowPair]) -> None:
    for pair in pairs:
        convert_pair(config, workspace, pair)
