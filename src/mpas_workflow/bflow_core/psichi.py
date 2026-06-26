from __future__ import annotations

import shutil
from pathlib import Path

import netCDF4
import numpy as np

from .external import require_files
from .model import BflowPair, compact_time
from .weights import WEIGHTS_FILENAME

EARTH_RADIUS_M = 6_371_220.0
MPAS_RADIUS_RATIO = 6_371_229.0 / 6_371_220.0


def _require_scipy_fft():
    try:
        from scipy.fft import fft2, ifft2, fftfreq
    except ImportError as exc:
        raise SystemExit(
            "ERRO: o backend Python psi/chi requer scipy. "
            "Instale com `python -m pip install scipy` no ambiente mpaswf."
        ) from exc
    return fft2, ifft2, fftfreq


def load_weights(workspace: Path):
    path = Path(workspace) / "ESMF_weights" / WEIGHTS_FILENAME
    require_files([path], "pesos Python BFLOW")
    return np.load(path, allow_pickle=False)


def apply_sparse_weights(values: np.ndarray, indices: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Apply compact nearest-neighbor weights.

    Parameters
    ----------
    values
        Array with shape ``(nlev, nsource)``.
    indices, weights
        Arrays with shape ``(ntarget, nneighbor)``.
    """
    gathered = values[:, indices]
    return np.einsum("ltk,tk->lt", gathered, weights, optimize=True)


def _gradient_x(field: np.ndarray, dx: float) -> np.ndarray:
    return (np.roll(field, -1, axis=1) - np.roll(field, 1, axis=1)) / (2.0 * dx)


def _gradient_y(field: np.ndarray, dy: float) -> np.ndarray:
    out = np.empty_like(field)
    out[1:-1, :] = (field[2:, :] - field[:-2, :]) / (2.0 * dy)
    out[0, :] = (field[1, :] - field[0, :]) / dy
    out[-1, :] = (field[-1, :] - field[-2, :]) / dy
    return out


def solve_poisson_periodic(rhs: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Solve a 2D Poisson equation on a regular auxiliary grid.

    This is a Python replacement for the previous NCL `uv2sfvpf` path. It uses a
    doubly periodic spectral approximation over the 1-degree auxiliary grid.
    Therefore it is suitable for removing the NCL dependency and for smoke tests,
    but it must be scientifically compared against the previous NCL baseline
    before production use.
    """
    fft2, ifft2, fftfreq = _require_scipy_fft()
    ny, nx = rhs.shape
    rhs0 = rhs - np.nanmean(rhs)
    rhs_hat = fft2(rhs0)
    kx = 2.0 * np.pi * fftfreq(nx, d=dx)
    ky = 2.0 * np.pi * fftfreq(ny, d=dy)
    kx2, ky2 = np.meshgrid(kx * kx, ky * ky)
    k2 = kx2 + ky2
    out_hat = np.zeros_like(rhs_hat)
    mask = k2 > 0.0
    out_hat[mask] = -rhs_hat[mask] / k2[mask]
    return np.real(ifft2(out_hat))


def uv_to_psichi_regular(u_ll: np.ndarray, v_ll: np.ndarray, lats: np.ndarray, lons: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convert regular-grid u/v to streamfunction and velocity potential.

    ``u_ll`` and ``v_ll`` have shape ``(nlev, nlat, nlon)``.
    """
    nlev, _, _ = u_ll.shape
    dlat = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 1.0
    dlon = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 1.0
    dy = EARTH_RADIUS_M * np.deg2rad(dlat)
    # Use an area-representative zonal spacing for the auxiliary global grid.
    dx = EARTH_RADIUS_M * np.deg2rad(dlon) * max(float(np.mean(np.cos(np.deg2rad(lats)))), 1.0e-6)

    psi = np.empty_like(u_ll, dtype="f8")
    chi = np.empty_like(u_ll, dtype="f8")
    for level in range(nlev):
        u = np.asarray(u_ll[level], dtype="f8")
        v = np.asarray(v_ll[level], dtype="f8")
        dudx = _gradient_x(u, dx)
        dudy = _gradient_y(u, dy)
        dvdx = _gradient_x(v, dx)
        dvdy = _gradient_y(v, dy)
        divergence = dudx + dvdy
        vorticity = dvdx - dudy
        psi[level] = solve_poisson_periodic(vorticity, dx, dy)
        chi[level] = solve_poisson_periodic(divergence, dx, dy)
    return psi, chi


def write_full_file(template: Path, output_path: Path, psi_mpas: np.ndarray, chi_mpas: np.ndarray) -> None:
    if output_path.exists():
        output_path.unlink()
    shutil.copy2(template, output_path)
    with netCDF4.Dataset(output_path, "a") as ds:
        for name, data, long_name in [
            ("stream_function", psi_mpas, "stream function"),
            ("velocity_potential", -chi_mpas, "velocity potential"),
        ]:
            if name not in ds.variables:
                raise SystemExit(f"ERRO: variável ausente no template: {name}")
            var = ds.variables[name]
            var[0, :, :] = (data * MPAS_RADIUS_RATIO).T
            var.setncattr("long_name", long_name)
            var.setncattr("units", "m^2 s^(-2)")
            var.setncattr("bflow_python_backend", "spectral_periodic_aux_grid")


def convert_file(input_path: Path, output_path: Path, template: Path, weights) -> None:
    require_files([input_path, template], "psi/chi Python")
    latlon_lats = weights["latlon_lats"]
    latlon_lons = weights["latlon_lons"]
    nlat = len(latlon_lats)
    nlon = len(latlon_lons)

    with netCDF4.Dataset(input_path) as ds:
        for name in ("uReconstructZonal", "uReconstructMeridional"):
            if name not in ds.variables:
                raise SystemExit(f"ERRO: variável ausente em {input_path}: {name}")
        u_cell = np.asarray(ds.variables["uReconstructZonal"][0, :, :], dtype="f8").T
        v_cell = np.asarray(ds.variables["uReconstructMeridional"][0, :, :], dtype="f8").T

    u_ll_flat = apply_sparse_weights(u_cell, weights["mpas_to_latlon_idx"], weights["mpas_to_latlon_w"])
    v_ll_flat = apply_sparse_weights(v_cell, weights["mpas_to_latlon_idx"], weights["mpas_to_latlon_w"])
    u_ll = u_ll_flat.reshape((u_cell.shape[0], nlat, nlon))
    v_ll = v_ll_flat.reshape((v_cell.shape[0], nlat, nlon))

    psi_ll, chi_ll = uv_to_psichi_regular(u_ll, v_ll, latlon_lats, latlon_lons)
    psi_mpas = apply_sparse_weights(
        psi_ll.reshape((psi_ll.shape[0], nlat * nlon)),
        weights["latlon_to_mpas_idx"],
        weights["latlon_to_mpas_w"],
    )
    chi_mpas = apply_sparse_weights(
        chi_ll.reshape((chi_ll.shape[0], nlat * nlon)),
        weights["latlon_to_mpas_idx"],
        weights["latlon_to_mpas_w"],
    )
    write_full_file(template, output_path, psi_mpas, chi_mpas)


def convert_pair(config, workspace: Path, pair: BflowPair) -> None:
    del config
    workspace = Path(workspace).resolve()
    weights = load_weights(workspace)
    template = workspace / "template_PTB.nc"
    require_files([template], "psi/chi Python")

    vcompact = compact_time(pair.valid_time)
    outdir = workspace / "output" / vcompact
    outdir.mkdir(parents=True, exist_ok=True)
    for label, input_path, output_path in [
        ("f48", workspace / "inputs" / vcompact / "f048.nc", outdir / "FULL_f48.nc"),
        ("f24", workspace / "inputs" / vcompact / "f024.nc", outdir / "FULL_f24.nc"),
    ]:
        print(f"Python psi/chi {label} {pair.valid_time}")
        convert_file(input_path, output_path, template, weights)
        require_files([output_path], f"psi/chi Python {label} output")


def convert_uv_to_psichi(config, workspace: Path, pairs: list[BflowPair]) -> None:
    for pair in pairs:
        convert_pair(config, workspace, pair)
