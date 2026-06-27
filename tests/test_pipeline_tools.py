import pytest

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
