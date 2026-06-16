# VBAL product finding

The current smoke-test VBAL product does not contain the physical vertical-balance diagnostics needed for the tutorial-style figures.

Observed file:

```text
VBAL/mpas_vbal.nc
```

Current contents:

```text
dimensions:
  nc2: 200
  nl0_1: 55
  nl0_2: 55
variables:
  none
```

The companion file contains only sampling coordinates and masks:

```text
VBAL/mpas_sampling.nc
```

with variables such as `lon_c1`, `lat_c1`, `vert_coord_c1`, `smask_c1`, `lon_c2`, `lat_c2`, `vert_coord_c2` and `smask_c2`.

Therefore, plots such as explained variance, `psi-T` regression coefficients, `chi-psi` profiles and `ps-psi` profiles cannot be generated from the current VBAL output. The missing item is not a plotting routine; the BUMP vertical-balance calibration is not writing those diagnostic variables to `mpas_vbal.nc` in the current workflow.

Next action: review the generated `run_vbal.yaml` and the SABER/BUMP `BUMP_VerticalBalance` output options so the calibration writes the vertical-balance regression and explained-variance products expected by the tutorial diagnostics.
