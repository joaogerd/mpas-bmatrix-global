import pytest

from mpas_workflow.bflow_core.weights import weight_paths
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
