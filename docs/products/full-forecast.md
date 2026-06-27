# `FULL_f24.nc` e `FULL_f48.nc`

## O que são

Arquivos MPAS completos preparados pelo `mpasbflow` a partir das previsões de 24 h e 48 h.

Eles contêm as variáveis necessárias para calcular a perturbação NMC e alimentar etapas posteriores.

## Quem produz

```text
mpasbflow
```

## Quem utiliza

- `mpasbflow`, para gerar `PTB_f48mf24.nc`;
- `mpasvbal`, como background/template;
- etapas posteriores indiretamente.

## Origem

Entradas originais:

```text
mpasout.<valid_time>.nc  forecast 24h
mpasout.<valid_time>.nc  forecast 48h
```

Produtos:

```text
FULL_f24.nc
FULL_f48.nc
```

## Conteúdo esperado

Além das variáveis MPAS nativas, esses arquivos devem conter variáveis de controle e derivadas, como:

- `stream_function`
- `velocity_potential`
- `temperature`
- `spechum`
- `surface_pressure`

## Como validar

Verifique se as variáveis existem:

```bash
python - <<'PY'
import xarray as xr
for path in ['FULL_f24.nc', 'FULL_f48.nc']:
    ds = xr.open_dataset(path)
    for v in ['stream_function', 'velocity_potential', 'temperature', 'spechum', 'surface_pressure']:
        assert v in ds, f'{v} ausente em {path}'
    print(path, 'OK')
PY
```

## Problemas comuns

- `stream_function` ou `velocity_potential` ausentes.
- Diferença de dimensões entre f24 e f48.
- Arquivo f24/f48 não corresponde ao mesmo tempo válido.
- Variáveis derivadas com unidades ou sinais inconsistentes.
