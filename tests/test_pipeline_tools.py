import numpy as np
import pytest

from mpas_workflow.bflow_core.weights import _mpas_ugrid, weight_paths
from mpas_workflow.dirac_summary import summarize_dirac_file


def test_dirac_summary_reports_nonzero_numeric_variables(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    path = tmp_path / "mpas.dirac.nc"
    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension("nCells", 3)
        variable = dataset.createVariable("temperature", "f4", ("nCells",))
        variable[:] = [0.0, 2.0, -2.0]

    rows = summarize_dirac_file(path)

    row = next(item for item in rows if item["variable"] == "temperature")
    assert row["shape"] == (3,)
    assert row["min"] == pytest.approx(-2.0)
    assert row["max"] == pytest.approx(2.0)
    assert row["absmax"] == pytest.approx(2.0)


def test_bflow_weight_paths_follow_the_regridding_contract(tmp_path):
    config = {
        "mesh": {"name": "x1.test"},
        "bflow": {
            "regridding": {
                "weights_directory": "weights/{mesh_name}",
                "weight_mpas_to_latlon": "mpas_{mesh_name}_to_regular.nc",
                "weight_latlon_to_mpas": "regular_to_mpas_{mesh_name}.nc",
            }
        },
    }

    mpas_to_latlon, latlon_to_mpas = weight_paths(config, tmp_path)

    assert mpas_to_latlon == tmp_path / "weights/x1.test/mpas_x1.test_to_regular.nc"
    assert latlon_to_mpas == tmp_path / "weights/x1.test/regular_to_mpas_x1.test.nc"


def test_mpas_ugrid_converts_mpas_indices_and_radians(tmp_path):
    netCDF4 = pytest.importorskip("netCDF4")
    xr = pytest.importorskip("xarray")
    path = tmp_path / "mesh.nc"
    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension("nCells", 2)
        dataset.createDimension("nVertices", 4)
        dataset.createDimension("maxEdges", 4)
        for name, values, dimensions in (
            ("latCell", [0.0, np.pi / 6], ("nCells",)),
            ("lonCell", [0.0, np.pi / 3], ("nCells",)),
            ("latVertex", [0.0, 0.0, np.pi / 6, np.pi / 6], ("nVertices",)),
            ("lonVertex", [0.0, np.pi / 6, np.pi / 6, 0.0], ("nVertices",)),
            ("nEdgesOnCell", [3, 4], ("nCells",)),
        ):
            variable = dataset.createVariable(name, "f8" if name != "nEdgesOnCell" else "i4", dimensions)
            variable[:] = values
        vertices = dataset.createVariable("verticesOnCell", "i4", ("nCells", "maxEdges"))
        vertices[:] = [[1, 2, 3, 0], [1, 3, 4, 2]]

    mesh = _mpas_ugrid(path, xr)

    assert mesh["face_node_connectivity"].values.tolist() == [[0, 1, 2, -1], [0, 2, 3, 1]]
    assert mesh["face_node_connectivity"].attrs["start_index"] == 0
    assert mesh["face_node_connectivity"].attrs["_FillValue"] == -1
    assert mesh["node_lon"].values[1] == pytest.approx(30.0)
    assert mesh["face_lat"].values[1] == pytest.approx(30.0)
    assert mesh["mesh"].attrs["cf_role"] == "mesh_topology"
