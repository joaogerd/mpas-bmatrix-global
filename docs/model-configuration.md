# Configuração do init e forecast MPAS

O bloco `model` em `configs/jaci-x1.10242.yaml` concentra os parâmetros de execução MPAS que antes estavam fixos no código Python.

```text
model.init
  workspace, saída, namelist, streams e validação

model.forecast
  workspace, templates, saída da_state/restart, namelist e streams
```

Os comandos permanecem os mesmos:

```bash
scripts/mpaswf init prepare --init-time 2018-04-13_00:00:00
scripts/mpaswf forecast prepare --init-time 2018-04-13_00:00:00 --lead-hours 24
```

## Init

`model.init` permite alterar o nome do arquivo de saída, o diretório de trabalho, o nome local da malha/invariant, os valores do `namelist.init_atmosphere`, a política de sobrescrita no stream e os tokens que confirmam sucesso no log.

Placeholders aceitos em caminhos e nomes:

```text
{mesh_name}  {init_time}  {safe_time}  {nproc}
```

## Forecast

`model.forecast` permite alterar os templates de namelist e streams, seus fallbacks na instalação MPAS, flags de runtime, nomes de streams e os nomes de arquivos `restart` e `da_state`.

Além dos placeholders anteriores, `run_directory` aceita:

```text
{lead_hours}  {dt}
```

Os nomes de saída MPAS aceitam os tokens de tempo:

```text
$Y  $M  $D  $h  $m  $s
```

## Regeneração

Alterar `model.init` exige gerar o init novamente. Alterar `model.forecast` exige recriar os forecasts afetados e, quando eles alimentam a matriz B, refazer:

```text
forecast → BFLOW/NMC → VBAL → HDIAG → NICAS → SO → DIRAC
```

## Validação no JACI

```bash
source scripts/load_jaci_env.sh
python -m pip install -e .
pytest -q tests/test_model_config.py
```

Depois, faça um init e forecast smoke e confira os arquivos `namelist.*` e `streams.*` gerados antes de submeter PBS.
