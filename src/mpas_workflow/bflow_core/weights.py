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
    return tuple(int(value) for value in np.asarray(ds[name][:]).ravel() if int(value) > 0) if name in ds.variables else ()


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


def _esmf():
    try:
        import esmpy as ESMF
    except ImportError:
        try:
            import ESMF
        except ImportError as exc:
            raise SystemExit("ERRO: instale esmpy com conda-forge para gerar os pesos ESMF.") from exc
    return ESMF


def _grid_coordinates(regrid):
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
    return np.linspace(lower[1], upper[1], nlon), np.linspace(lower[0], upper[0], nlat)


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


def _read_mpas_geometry(mesh_path):
    required = {"latCell", "lonCell", "latVertex", "lonVertex", "verticesOnCell", "nEdgesOnCell"}
    with netCDF4.Dataset(mesh_path) as ds:
        missing = sorted(required.difference(ds.variables))
        if missing:
            raise SystemExit(f"ERRO: malha MPAS sem variáveis requeridas: {', '.join(missing)}")
        face_lat = np.asarray(ds["latCell"][:], dtype="f8")
        face_lon = np.asarray(ds["lonCell"][:], dtype="f8")
        node_lat = np.asarray(ds["latVertex"][:], dtype="f8")
        node_lon = np.asarray(ds["lonVertex"][:], dtype="f8")
        connectivity = np.asarray(ds["verticesOnCell"][:], dtype="i8")
        edge_count = np.asarray(ds["nEdgesOnCell"][:], dtype="i8")
    if connectivity.ndim != 2 or edge_count.shape != (connectivity.shape[0],):
        raise SystemExit(f"ERRO: conectividade MPAS inválida em {mesh_path}")
    if np.any(edge_count < 3) or np.any(edge_count > connectivity.shape[1]):
        raise SystemExit(f"ERRO: nEdgesOnCell inválido em {mesh_path}")
    face_lat, face_lon = _to_degrees(face_lat, face_lon)
    node_lat, node_lon = _to_degrees(node_lat, node_lon)
    return node_lon, node_lat, face_lon, face_lat, connectivity, edge_count


def _lonlat_to_xyz(lon, lat):
    lon_rad = np.deg2rad(lon)
    lat_rad = np.deg2rad(lat)
    return np.cos(lat_rad) * np.cos(lon_rad), np.cos(lat_rad) * np.sin(lon_rad), np.sin(lat_rad)


def _mpas_mesh(mesh_path, ESMF):
    node_lon, node_lat, face_lon, face_lat, connectivity, edge_count = _read_mpas_geometry(mesh_path)
    faces = np.full(connectivity.shape, -1, dtype="i8")
    for face, count in enumerate(edge_count):
        vertices = connectivity[face, :count]
        if np.any(vertices <= 0) or np.any(vertices > node_lon.size):
            raise SystemExit(f"ERRO: verticesOnCell inválido para célula {face} em {mesh_path}")
        faces[face, :count] = vertices - 1

    node_x, node_y, node_z = _lonlat_to_xyz(node_lon, node_lat)
    face_x, face_y, face_z = _lonlat_to_xyz(face_lon, face_lat)
    mesh = ESMF.Mesh(parametric_dim=2, spatial_dim=3)
    node_count = node_lon.size
    mesh.add_nodes(
        node_count,
        np.arange(1, node_count + 1, dtype="i4"),
        np.column_stack((node_x, node_y, node_z)).ravel(),
        np.zeros(node_count, dtype="i4"),
    )

    element_types = edge_count.astype("i4")
    flat_connectivity = np.concatenate(
        [np.asarray(row[:count], dtype="i4") for row, count in zip(faces, edge_count)]
    )
    mesh.add_elements(
        faces.shape[0],
        np.arange(1, faces.shape[0] + 1, dtype="i4"),
        element_types,
        flat_connectivity,
        element_coords=np.column_stack((face_x, face_y, face_z)).ravel(),
    )
    return mesh


def _latlon_grid(regrid, ESMF, *, periodic):
    lon_1d, lat_1d = _grid_coordinates(regrid)
    lon, lat = np.meshgrid(lon_1d, lat_1d, indexing="ij")
    lon = np.asfortranarray(lon)
    lat = np.asfortranarray(lat)
    grid = ESMF.Grid(
        np.asarray(lon.shape, dtype="i4"),
        staggerloc=ESMF.StaggerLoc.CENTER,
        coord_sys=ESMF.CoordSys.SPH_DEG,
        num_peri_dims=1 if periodic else None,
    )
    grid.get_coords(coord_dim=0, staggerloc=ESMF.StaggerLoc.CENTER)[...] = lon
    grid.get_coords(coord_dim=1, staggerloc=ESMF.StaggerLoc.CENTER)[...] = lat
    return grid


def _method(method, ESMF):
    values = {
        "bilinear": ESMF.RegridMethod.BILINEAR,
        "patch": ESMF.RegridMethod.PATCH,
        "nearest_s2d": ESMF.RegridMethod.NEAREST_STOD,
        "nearest_d2s": ESMF.RegridMethod.NEAREST_DTOS,
    }
    try:
        return values[method]
    except KeyError as exc:
        raise SystemExit("ERRO: método não suportado para MPAS/lat-lon.") from exc


def _destroy(value):
    if value is not None:
        try:
            value.destroy()
        except Exception:
            pass


def _field(grid, *, is_mesh, ESMF):
    if is_mesh:
        return ESMF.Field(grid, meshloc=ESMF.MeshLoc.ELEMENT)
    return ESMF.Field(grid)


def _write_weights(path, source, destination, *, source_mesh, destination_mesh, method, ESMF):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    source_field = destination_field = regrid = None
    try:
        source_field = _field(source, is_mesh=source_mesh, ESMF=ESMF)
        destination_field = _field(destination, is_mesh=destination_mesh, ESMF=ESMF)
        regrid = ESMF.Regrid(
            source_field,
            destination_field,
            filename=str(path),
            regrid_method=_method(method, ESMF),
            unmapped_action=ESMF.UnmappedAction.IGNORE,
            ignore_degenerate=False,
            norm_type=ESMF.NormType.DSTAREA,
        )
    except Exception as exc:
        raise SystemExit(f"ERRO: ESMF não conseguiu gerar pesos em {path}: {exc}") from exc
    finally:
        _destroy(regrid)
        _destroy(source_field)
        _destroy(destination_field)
        _destroy(source)
        _destroy(destination)
    _check(path)


def generate_esmf_weights(config, workspace):
    workspace = Path(workspace)
    mpas_to_latlon, latlon_to_mpas = weight_paths(config, workspace)
    missing = [path for path in (mpas_to_latlon, latlon_to_mpas) if not path.exists()]
    if not missing:
        print("Reusing existing ESMF weights")
        return ensure_esmf_weights(config, workspace)

    ESMF = _esmf()
    regrid = _regrid(config)
    mesh_path = _mesh_path(config, regrid, workspace)
    if not mesh_path.exists():
        raise SystemExit(f"ERRO: malha MPAS não encontrada: {mesh_path}")
    method = regrid.get("interpolation_method", "bilinear")
    _method(method, ESMF)
    print("Generating missing ESMF weights directly with ESMPy")

    if mpas_to_latlon in missing:
        _write_weights(
            mpas_to_latlon,
            _mpas_mesh(mesh_path, ESMF),
            _latlon_grid(regrid, ESMF, periodic=False),
            source_mesh=True,
            destination_mesh=False,
            method=method,
            ESMF=ESMF,
        )
    if latlon_to_mpas in missing:
        _write_weights(
            latlon_to_mpas,
            _latlon_grid(regrid, ESMF, periodic=bool(regrid.get("periodic", True))),
            _mpas_mesh(mesh_path, ESMF),
            source_mesh=False,
            destination_mesh=True,
            method=method,
            ESMF=ESMF,
        )
    return ensure_esmf_weights(config, workspace)
