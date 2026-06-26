from __future__ import annotations

from pathlib import Path

import netCDF4
import numpy as np


WEIGHTS_FILENAME = "bflow_regridding_weights.npz"
DEFAULT_LAT_RESOLUTION_DEG = 1.0
DEFAULT_LON_RESOLUTION_DEG = 1.0
DEFAULT_NEIGHBORS = 4
DEFAULT_POWER = 2.0


def _require_scipy_spatial():
    try:
        from scipy.spatial import cKDTree
    except ImportError as exc:
        raise SystemExit(
            "ERRO: o backend Python de pesos BFLOW requer scipy. "
            "Instale com `python -m pip install scipy` no ambiente mpaswf."
        ) from exc
    return cKDTree


def _lon_to_180(lon_deg: np.ndarray) -> np.ndarray:
    return ((lon_deg + 180.0) % 360.0) - 180.0


def _lonlat_to_unit_xyz(lon_deg: np.ndarray, lat_deg: np.ndarray) -> np.ndarray:
    lon = np.deg2rad(lon_deg)
    lat = np.deg2rad(lat_deg)
    coslat = np.cos(lat)
    return np.column_stack((coslat * np.cos(lon), coslat * np.sin(lon), np.sin(lat)))


def regular_latlon_grid(
    lat_resolution_deg: float = DEFAULT_LAT_RESOLUTION_DEG,
    lon_resolution_deg: float = DEFAULT_LON_RESOLUTION_DEG,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return center-point 1D and flattened 2D regular lat/lon coordinates.

    The default grid matches the previous NCL setup: centers at -89.5..89.5 and
    -179.5..179.5 for a 1 degree grid.
    """
    lats = np.arange(-90.0 + lat_resolution_deg / 2.0, 90.0, lat_resolution_deg)
    lons = np.arange(-180.0 + lon_resolution_deg / 2.0, 180.0, lon_resolution_deg)
    lon2d, lat2d = np.meshgrid(lons, lats)
    return lats, lons, lat2d.ravel(), lon2d.ravel()


def inverse_distance_weights(
    src_lon_deg: np.ndarray,
    src_lat_deg: np.ndarray,
    dst_lon_deg: np.ndarray,
    dst_lat_deg: np.ndarray,
    *,
    neighbors: int = DEFAULT_NEIGHBORS,
    power: float = DEFAULT_POWER,
) -> tuple[np.ndarray, np.ndarray]:
    """Build spherical nearest-neighbor inverse-distance interpolation weights.

    This replaces the NCL/ESMF weight generation used previously. It is fully
    Python and deterministic, but it is not bitwise equivalent to ESMF bilinear
    weights on the MPAS unstructured mesh. The resulting BFLOW products must be
    validated against the old NCL baseline before being used operationally.
    """
    cKDTree = _require_scipy_spatial()
    src_xyz = _lonlat_to_unit_xyz(src_lon_deg, src_lat_deg)
    dst_xyz = _lonlat_to_unit_xyz(dst_lon_deg, dst_lat_deg)
    k = min(int(neighbors), len(src_lon_deg))
    distances, indices = cKDTree(src_xyz).query(dst_xyz, k=k)

    if k == 1:
        distances = distances[:, None]
        indices = indices[:, None]

    weights = np.empty_like(distances, dtype="f8")
    exact = distances <= 1.0e-14
    rows_with_exact = exact.any(axis=1)

    weights[~rows_with_exact] = 1.0 / np.maximum(distances[~rows_with_exact], 1.0e-14) ** power
    weights[~rows_with_exact] /= weights[~rows_with_exact].sum(axis=1, keepdims=True)

    weights[rows_with_exact] = 0.0
    if rows_with_exact.any():
        exact_cols = exact[rows_with_exact].argmax(axis=1)
        weights[np.where(rows_with_exact)[0], exact_cols] = 1.0

    return indices.astype("i8"), weights.astype("f8")


def read_mpas_cell_centers(invariant_path: Path) -> tuple[np.ndarray, np.ndarray]:
    invariant_path = Path(invariant_path)
    if not invariant_path.exists():
        raise SystemExit(f"ERRO: static.invariant não encontrado: {invariant_path}")
    with netCDF4.Dataset(invariant_path) as ds:
        for name in ("lonCell", "latCell"):
            if name not in ds.variables:
                raise SystemExit(f"ERRO: variável ausente em invariant MPAS: {name}")
        lon = _lon_to_180(np.rad2deg(ds.variables["lonCell"][:]).astype("f8"))
        lat = np.rad2deg(ds.variables["latCell"][:]).astype("f8")
    return lon, lat


def generate_python_weights(config, workspace: Path) -> Path:
    mesh_name = config["mesh"]["name"]
    invariant = Path(config["static"]["invariant"])
    weight_dir = Path(workspace) / "ESMF_weights"
    weight_dir.mkdir(parents=True, exist_ok=True)
    out = weight_dir / WEIGHTS_FILENAME

    mpas_lon, mpas_lat = read_mpas_cell_centers(invariant)
    lats, lons, latlon_lat_flat, latlon_lon_flat = regular_latlon_grid()

    print("Generating Python BFLOW regridding weights")
    print(f"mesh={mesh_name}")
    print(f"nCells={mpas_lon.size}")
    print(f"latlon_grid={lats.size}x{lons.size}")

    mpas_to_latlon_idx, mpas_to_latlon_w = inverse_distance_weights(
        mpas_lon,
        mpas_lat,
        latlon_lon_flat,
        latlon_lat_flat,
    )
    latlon_to_mpas_idx, latlon_to_mpas_w = inverse_distance_weights(
        latlon_lon_flat,
        latlon_lat_flat,
        mpas_lon,
        mpas_lat,
    )

    np.savez_compressed(
        out,
        backend="python_idw_spherical",
        mesh_name=mesh_name,
        invariant=str(invariant),
        neighbors=np.array(DEFAULT_NEIGHBORS, dtype="i4"),
        power=np.array(DEFAULT_POWER, dtype="f8"),
        lat_resolution_deg=np.array(DEFAULT_LAT_RESOLUTION_DEG, dtype="f8"),
        lon_resolution_deg=np.array(DEFAULT_LON_RESOLUTION_DEG, dtype="f8"),
        mpas_lon=mpas_lon.astype("f8"),
        mpas_lat=mpas_lat.astype("f8"),
        latlon_lats=lats.astype("f8"),
        latlon_lons=lons.astype("f8"),
        mpas_to_latlon_idx=mpas_to_latlon_idx,
        mpas_to_latlon_w=mpas_to_latlon_w,
        latlon_to_mpas_idx=latlon_to_mpas_idx,
        latlon_to_mpas_w=latlon_to_mpas_w,
    )
    print(f"weights: {out}")
    return out


def generate_esmf_weights(config, workspace: Path) -> None:
    """Generate BFLOW interpolation weights with a pure Python backend.

    The function name is kept for compatibility with the existing runner. The
    produced file is not an ESMF weight file; it is a NumPy archive consumed by
    :mod:`mpas_workflow.bflow_core.psichi`.
    """
    generate_python_weights(config, workspace)
