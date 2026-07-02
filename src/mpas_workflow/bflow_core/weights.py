from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import netCDF4
import numpy as np


@dataclass(frozen=True)
class EsmfSparseWeights:
    path: Path
    row: np.ndarray
    col: np.ndarray
    weights: np.ndarray
    src_size: int
    dst_size: int
    src_grid_dims: tuple[int, ...]
    dst_grid_dims: tuple[int, ...]


def _dims(ds, name):
    return tuple(int(v) for v in np.asarray(ds[name][:]).ravel() if int(v) > 0) if name in ds.variables else ()


def _check(path):
    if not Path(path).exists():
        raise SystemExit(f"ERRO: pesos ESMF ausentes: {path}")
    with netCDF4.Dataset(path) as ds:
        missing = [name for name in ("row", "col", "S") if name not in ds.variables]
        sizes = {ds[name].size for name in ("row", "col", "S") if name in ds.variables}
        if missing or not sizes or 0 in sizes or len(sizes) != 1:
            raise SystemExit(f"ERRO: pesos ESMF inválidos: {path}")


def load_esmf_sparse_weights(path):
    path = Path(path)
    _check(path)
    with netCDF4.Dataset(path) as ds:
        row = np.asarray(ds["row"][:], dtype="i8").ravel() - 1
        col = np.asarray(ds["col"][:], dtype="i8").ravel() - 1
        coeff = np.asarray(ds["S"][:], dtype="f8").ravel()
        src_dims, dst_dims = _dims(ds, "src_grid_dims"), _dims(ds, "dst_grid_dims")
    if row.min() < 0 or col.min() < 0:
        raise SystemExit(f"ERRO: índices ESMF inválidos: {path}")
    return EsmfSparseWeights(
        path,
        row,
        col,
        coeff,
        int(np.prod(src_dims)) if src_dims else int(col.max()) + 1,
        int(np.prod(dst_dims)) if dst_dims else int(row.max()) + 1,
        src_dims,
        dst_dims,
    )


def apply_esmf_weights(values, weights):
    values = np.asarray(values)
    if values.ndim != 2 or values.shape[1] < weights.src_size:
        raise SystemExit(f"ERRO: shape incompatível para {weights.path}: {values.shape}")
    output = np.zeros((values.shape[0], weights.dst_size), dtype="f8")
    for level in range(values.shape[0]):
        np.add.at(output[level], weights.row, values[level, weights.col] * weights.weights)
    return output


def latlon_shape_from_weights(weights):
    dims = weights.dst_grid_dims or weights.src_grid_dims
    if len(dims) < 2:
        raise SystemExit(f"ERRO: dimensões lat/lon ausentes: {weights.path}")
    return int(dims[1]), int(dims[0])


def _regrid(config):
    value = config.get("bflow", {}).get("regridding")
    if not isinstance(value, dict):
        raise SystemExit("ERRO: bloco bflow.regridding ausente.")
    return value


def _name(config, regrid, key):
    value = regrid.get(key)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"ERRO: bflow.regridding.{key} ausente.")
    return value.format(mesh_name=config["mesh"]["name"])


def weight_paths(config, workspace):
    regrid = _regrid(config)
    directory = Path(regrid.get("weights_directory", "ESMF_weights").format(mesh_name=config["mesh"]["name"]))
    if not directory.is_absolute():
        directory = Path(workspace) / directory
    return (
        directory / _name(config, regrid, "weight_mpas_to_latlon"),
        directory / _name(config, regrid, "weight_latlon_to_mpas"),
    )


def ensure_esmf_weights(config, workspace):
    paths = weight_paths(config, workspace)
    for path in paths:
        _check(path)
    return paths


def _stack():
    try:
        import xarray as xr
        import xesmf as xe
    except ImportError as exc:
        raise SystemExit("ERRO: instale xarray, xesmf e esmpy com conda-forge.") from exc
    return xr, xe


def _grid(regrid, xr):
    lower, upper = regrid.get("lower_left"), regrid.get("upper_right")
    text = str(regrid.get("scrip_resolution")).lower().replace("deg", "")
    try:
        parts = [float(value) for value in text.split("x")]
        dlat, dlon = parts[0], parts[-1]
        nlat = round((upper[0] - lower[0]) / dlat) + 1
        nlon = round((upper[1] - lower[1]) / dlon) + 1
    except (TypeError, ValueError, IndexError) as exc:
        raise SystemExit("ERRO: grade auxiliar inválida.") from exc
    if dlat <= 0.0 or dlon <= 0.0 or nlat < 2 or nlon < 2:
        raise SystemExit("ERRO: grade auxiliar inválida.")
    if not np.isclose(lower[0] + (nlat - 1) * dlat, upper[0]) or not np.isclose(
        lower[1] + (nlon - 1) * dlon, upper[1]
    ):
        raise SystemExit("ERRO: limites e resolução não definem uma grade regular inteira.")
    return xr.Dataset(
        coords={
            "lat": ("lat", np.linspace(lower[0], upper[0], nlat)),
            "lon": ("lon", np.linspace(lower[1], upper[1], nlon)),
        }
    )


def _mesh_path(config, regrid, workspace):
    value = regrid.get("mesh_file")
    if value is None:
        value = config.get("mesh", {}).get("grid") or config.get("static", {}).get("invariant")
    if not isinstance(value, str) or not value:
        raise SystemExit("ERRO: informe bflow.regridding.mesh_file, mesh.grid ou static.invariant.")
    path = Path(value.format(mesh_name=config["mesh"]["name"]))
    return path if path.is_absolute() else Path(workspace) / path


def _to_degrees(lat, lon):
    if np.nanmax(np.abs(lon)) <= 2 * np.pi + 1e-6:
        return np.rad2deg(lat), np.rad2deg(lon)
    return lat, lon


def _cells(mesh_path, xr):
    with xr.open_dataset(mesh_path, decode_cf=False) as ds:
        if "latCell" not in ds or "lonCell" not in ds:
            raise SystemExit(f"ERRO: malha MPAS sem latCell/lonCell: {mesh_path}")
        lat, lon = np.asarray(ds["latCell"]), np.asarray(ds["lonCell"])
    lat, lon = _to_degrees(lat, lon)
    return xr.Dataset({"lat": ("nCells", lat), "lon": ("nCells", lon)})


def _mpas_ugrid(mesh_path, xr):
    """Return the MPAS cell mesh as the native xarray/UGRID contract for xESMF."""
    required = {"latCell", "lonCell", "latVertex", "lonVertex", "verticesOnCell", "nEdgesOnCell"}
    with xr.open_dataset(mesh_path, decode_cf=False) as source:
        missing = sorted(required.difference(source.variables))
        if missing:
            raise SystemExit(f"ERRO: malha MPAS sem variáveis UGRID requeridas: {', '.join(missing)}")
        face_lat = np.asarray(source["latCell"].values, dtype="f8")
        face_lon = np.asarray(source["lonCell"].values, dtype="f8")
        node_lat = np.asarray(source["latVertex"].values, dtype="f8")
        node_lon = np.asarray(source["lonVertex"].values, dtype="f8")
        connectivity = np.asarray(source["verticesOnCell"].values, dtype="i8")
        edge_count = np.asarray(source["nEdgesOnCell"].values, dtype="i8")

    if connectivity.ndim != 2 or edge_count.shape != (connectivity.shape[0],):
        raise SystemExit(f"ERRO: conectividade MPAS inválida em {mesh_path}")
    if np.any(edge_count < 3) or np.any(edge_count > connectivity.shape[1]):
        raise SystemExit(f"ERRO: nEdgesOnCell inválido em {mesh_path}")

    face_lat, face_lon = _to_degrees(face_lat, face_lon)
    node_lat, node_lon = _to_degrees(node_lat, node_lon)
    faces = np.full(connectivity.shape, -1, dtype="i8")
    for face, count in enumerate(edge_count):
        vertices = connectivity[face, :count]
        if np.any(vertices <= 0) or np.any(vertices > node_lon.size):
            raise SystemExit(f"ERRO: verticesOnCell inválido para célula {face} em {mesh_path}")
        faces[face, :count] = vertices - 1

    mesh = xr.Dataset(
        data_vars={
            "node_lon": ("n_node", node_lon),
            "node_lat": ("n_node", node_lat),
            "face_lon": ("n_face", face_lon),
            "face_lat": ("n_face", face_lat),
            "face_node_connectivity": (("n_face", "n_max_face_nodes"), faces),
        }
    )
    mesh["mesh"] = xr.DataArray(
        np.int8(0),
        attrs={
            "cf_role": "mesh_topology",
            "topology_dimension": 2,
            "node_coordinates": "node_lon node_lat",
            "face_coordinates": "face_lon face_lat",
            "face_node_connectivity": "face_node_connectivity",
        },
    )
    mesh["node_lon"].attrs.update({"standard_name": "longitude", "units": "degrees_east"})
    mesh["node_lat"].attrs.update({"standard_name": "latitude", "units": "degrees_north"})
    mesh["face_lon"].attrs.update({"standard_name": "longitude", "units": "degrees_east"})
    mesh["face_lat"].attrs.update({"standard_name": "latitude", "units": "degrees_north"})
    mesh["face_node_connectivity"].attrs.update(
        {"cf_role": "face_node_connectivity", "start_index": 0, "_FillValue": -1}
    )
    return mesh


def _write(path, create):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    regridder = create(str(path))
    del regridder
    _check(path)


def generate_esmf_weights(config, workspace):
    workspace = Path(workspace)
    mpas_to_latlon, latlon_to_mpas = weight_paths(config, workspace)
    missing = [path for path in (mpas_to_latlon, latlon_to_mpas) if not path.exists()]
    if not missing:
        print("Reusing existing ESMF weights")
        return ensure_esmf_weights(config, workspace)

    xr, xe = _stack()
    regrid = _regrid(config)
    mesh_path = _mesh_path(config, regrid, workspace)
    if not mesh_path.exists():
        raise SystemExit(f"ERRO: malha MPAS não encontrada: {mesh_path}")
    method = regrid.get("interpolation_method", "bilinear")
    if method not in {"bilinear", "patch", "nearest_s2d", "nearest_d2s"}:
        raise SystemExit("ERRO: método não suportado para MPAS/lat-lon.")

    latlon = _grid(regrid, xr)
    print("Generating missing ESMF weights with Python xESMF and explicit MPAS UGRID")
    if mpas_to_latlon in missing:
        mesh = _mpas_ugrid(mesh_path, xr)
        _write(
            mpas_to_latlon,
            lambda filename: xe.Regridder(
                mesh,
                latlon,
                method,
                mesh_in=True,
                filename=filename,
                reuse_weights=False,
            ),
        )
    if latlon_to_mpas in missing:
        cells = _cells(mesh_path, xr)
        _write(
            latlon_to_mpas,
            lambda filename: xe.Regridder(
                latlon,
                cells,
                method,
                locstream_out=True,
                periodic=bool(regrid.get("periodic", True)),
                filename=filename,
                reuse_weights=False,
            ),
        )
    return ensure_esmf_weights(config, workspace)
