# BFLOW Python pipeline refactor

Esta mudança reorganiza o `mpasbflow` para reduzir a geração dinâmica de scripts e aproximar o BFLOW de um pipeline Python puro.

## O que mudou

- `src/mpas_workflow/bflow.py` virou apenas um entrypoint de compatibilidade.
- A implementação foi movida para `src/mpas_workflow/bflow_core/`.
- As etapas que antes eram escritas como scripts Python gerados no workspace agora são módulos Python reais:
  - `variables.py`: adiciona variáveis físicas e derivadas aos arquivos `FULL_f48.nc` e `FULL_f24.nc`.
  - `diff.py`: calcula `PTB_f48mf24.nc` como `FULL_f48.nc - FULL_f24.nc`.
  - `validate.py`: valida produtos `FULL` e `PTB`.
- O `run_all_bflow.sh` deixou de ser o orquestrador principal. A execução ponta a ponta agora passa por `runner.py`.
- A criação de `template_PTB.nc`, que antes dependia de NCO, foi reimplementada em Python com `netCDF4`.

## O que ainda não é Python puro

Duas etapas continuam usando NCL como backend externo:

1. geração dos pesos ESMF em `weights.py`;
2. conversão `uReconstructZonal/uReconstructMeridional -> stream_function/velocity_potential` em `psichi.py`.

Essas etapas ainda geram arquivos `.ncl`, mas não geram mais um script Bash mestre nem scripts Python auxiliares. A próxima refatoração deve substituir essas duas partes por alternativas Python, provavelmente usando `xarray`, `xesmf`/ESMF ou uma implementação específica para a malha MPAS.

## Estrutura nova

```text
src/mpas_workflow/bflow_core/
  cli.py            # argparse e comandos prepare/run/all
  model.py          # BflowPair, datas, paths e pares NMC
  manifest.py       # leitura/escrita de manifest.tsv
  workspace.py      # criação de workspace, links e README
  runner.py         # pipeline Python ponta a ponta
  template.py       # geração Python de template_PTB.nc
  weights.py        # ponte temporária para NCL/ESMF weights
  psichi.py         # ponte temporária para NCL uv -> psi/chi
  variables.py      # enriquecimento NetCDF em Python
  diff.py           # diferença NMC em Python
  validate.py       # validação NetCDF em Python
  netcdf_utils.py   # utilitários compartilhados NetCDF
  external.py       # execução controlada de comandos externos
```

## Comandos preservados

```bash
mpasbflow prepare --config configs/jaci-x1.10242.yaml ...
mpasbflow run --config configs/jaci-x1.10242.yaml --workspace /caminho/do/workspace
mpasbflow all --config configs/jaci-x1.10242.yaml ...
```

A diferença operacional importante é que `mpasbflow run` agora precisa do `--config` quando não for usado o padrão, pois o runner Python precisa conhecer a malha e o caminho do `static.invariant` para as etapas NCL remanescentes.

## Próxima etapa: remover NCL

A próxima etapa natural é substituir:

- `weights.generate_esmf_weights()`;
- `psichi.convert_uv_to_psichi()`.

Quando isso for feito, o BFLOW ficará de fato Python puro: sem Bash gerado, sem scripts Python gerados, sem NCO e sem NCL.
