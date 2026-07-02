# Referência de produtos

Este documento resume os principais produtos gerados pelo workflow.

## MPAS forecast

```text
runs/forecast_<mesh>_<init>_f024_*/mpasout.<valid_time>.nc
runs/forecast_<mesh>_<init>_f048_*/mpasout.<valid_time>.nc
```

Uso: entrada para pares NMC no BFLOW.

## BFLOW

```text
bmatrix/bflow_preprocessing/<case>/manifest.tsv
bmatrix/bflow_preprocessing/<case>/output/<valid>/FULL_f48.nc
bmatrix/bflow_preprocessing/<case>/output/<valid>/FULL_f24.nc
bmatrix/bflow_preprocessing/<case>/output/<valid>/PTB_f48mf24.nc
```

Uso: amostras de perturbação NMC.

## VBAL

```text
bmatrix/covariance/vbal/<case>/VBAL/mpas_sampling.nc
bmatrix/covariance/vbal/<case>/VBAL/mpas_vbal.nc
bmatrix/covariance/vbal/<case>/VBAL/mpas_sampling_local_*.nc
bmatrix/covariance/vbal/<case>/VBAL/mpas_vbal_local_*.nc
```

Uso: balanço vertical/multivariado.

## HDIAG

```text
bmatrix/covariance/hdiag/<case>/HDIAG/mpas.stddev.nc
bmatrix/covariance/hdiag/<case>/HDIAG/mpas.cor_rh.nc
bmatrix/covariance/hdiag/<case>/HDIAG/mpas.cor_rv.nc
```

Uso: desvio padrão e correlações diagnósticas.

## NICAS

```text
bmatrix/covariance/nicas/<case>/merge/mpas_nicas.nc
bmatrix/covariance/nicas/<case>/merge/mpas_nicas_local_*.nc
bmatrix/covariance/nicas/<case>/merge/mpas_nicas_grids_local_*.nc
bmatrix/covariance/nicas/<case>/merge/mpas.nicas_norm.nc
bmatrix/covariance/nicas/<case>/merge/mpas.dirac_nicas.nc
```

Uso: operador de correlação/localização.

## SO

```text
bmatrix/covariance/so/<case>/bg_so.nc
bmatrix/covariance/so/<case>/run_SO.yaml
bmatrix/covariance/so/<case>/an.*.nc
bmatrix/covariance/so/<case>/obsout_SO_T.h5
bmatrix/covariance/so/<case>/obsout_SO_U.h5
```

Uso: validação de resposta da matriz B.

## Relatórios de validação

```text
report.md
diff.nc
```

Gerados por `mpasverify compare` quando solicitado.
