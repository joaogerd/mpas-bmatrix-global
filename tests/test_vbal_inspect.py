import netCDF4

from mpas_workflow.vbal_inspect import inspect


def test_inspect_detects_unbalanced_group(tmp_path):
    path = tmp_path / "mpas.vbal.nc"
    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension("n", 1)
        group = dataset.createGroup("unbalanced")
        group.createVariable("air_temperature", "f8", ("n",))[:] = [0.0]

    has_unbalanced, lines = inspect(path)

    assert has_unbalanced
    assert any("/unbalanced" in line for line in lines)
