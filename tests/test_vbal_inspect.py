import netCDF4

from mpas_workflow.vbal_inspect import inspect, validate_relations


def test_inspect_detects_configured_relation_products(tmp_path):
    path = tmp_path / "mpas.vbal.nc"
    group_name = "air_horizontal_streamfunction-air_temperature"
    with netCDF4.Dataset(path, "w") as dataset:
        dataset.createDimension("n", 1)
        group = dataset.createGroup(group_name)
        group.createVariable("explained_var", "f8", ("n",))[:] = [0.0]
        group.createVariable("reg_matrix", "f8", ("n",))[:] = [0.0]

    products_by_group, lines = inspect(path)

    assert products_by_group[group_name] == {"explained", "reg"}
    assert not validate_relations(products_by_group, {group_name})
    assert any(group_name in line for line in lines)
