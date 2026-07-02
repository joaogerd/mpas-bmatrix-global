# `mpas_vbal.nc` e `mpas_vbal_local_*.nc`

## O que são

Produtos do treinamento de balanço vertical/multivariado gerados pelo SABER/BUMP na etapa VBAL.

## Quem produz

```text
mpasvbal
```

## Quem utiliza

- `mpashdiag`
- `mpasso`
- configurações SABER que usam `BUMP_VerticalBalance`

## Papel científico

Esses arquivos armazenam coeficientes e estruturas usadas para representar relações balanceadas entre variáveis de controle.

Exemplos:

```text
velocity_potential <- stream_function
temperature        <- stream_function
surface_pressure   <- stream_function
```

## Produtos

```text
mpas_vbal.nc
mpas_vbal_local_*.nc
mpas_sampling.nc
mpas_sampling_local_*.nc
```

## Como validar

Use:

```bash
mpasvbal validate --workspace $VBAL
```

A validação confere:

- produto global;
- produtos locais por rank;
- status final no `run_vbal.runlog`.

## Problemas comuns

- número de arquivos locais menor que o número esperado de ranks;
- `run_vbal.runlog` ausente;
- status final de sucesso ausente;
- amostras NMC insuficientes ou inconsistentes.
