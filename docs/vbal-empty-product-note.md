# VBAL product finding

The smoke-test VBAL product is a NetCDF-4 file that stores the useful vertical-balance fields inside NetCDF groups.

This is important because a simple Python check such as:

```python
list(ds.variables.keys())
```

only inspects the root group and may incorrectly suggest that `mpas_vbal.nc` has no variables.

Observed file:

```text
VBAL/mpas_vbal.nc
```

The root dimensions are:

```text
nc2: 200
nl0_1: 55
nl0_2: 55
```

The useful fields are inside groups such as:

```text
stream_function-velocity_potential
stream_function-temperature
stream_function-surface_pressure
```

These groups include variables such as:

```text
reg_c2
cov_c2
explained_var_c2
```

The companion sampling file:

```text
VBAL/mpas_sampling.nc
```

provides the diagnostic grid coordinates and masks, including `lon_c2`, `lat_c2`, `vert_coord_c2` and `smask_c2`.

Therefore, tutorial-style VBAL plots must read NetCDF groups recursively. The generic `vbal-plot` command is not enough for this because it only handles variables exposed at the root level of the dataset.

A dedicated grouped-diagnostics module was added at:

```text
src/mpas_workflow/vbal_groups.py
```

It reads grouped VBAL variables and can generate latitude-by-level plots and vertical profiles for `reg_c2`, `cov_c2` and `explained_var_c2` products.
