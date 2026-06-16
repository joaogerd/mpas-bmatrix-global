from __future__ import annotations

from pathlib import Path


def iter_group_variables(group, prefix=''):
    for name, variable in group.variables.items():
        yield prefix, name, variable
    for name, child in group.groups.items():
        child_prefix = f'{prefix}/{name}' if prefix else name
        yield from iter_group_variables(child, child_prefix)


def inspect_vbal_groups(workspace: str | Path) -> list[tuple[str, str, tuple[int, ...]]]:
    import netCDF4

    path = Path(workspace) / 'VBAL' / 'mpas_vbal.nc'
    rows = []
    with netCDF4.Dataset(path) as dataset:
        for group_name, variable_name, variable in iter_group_variables(dataset):
            rows.append((group_name, variable_name, tuple(variable.shape)))
    return rows
