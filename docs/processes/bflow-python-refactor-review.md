# Revisão da refatoração BFLOW

## Resumo

A refatoração transforma o antigo `src/mpas_workflow/bflow.py`, que gerava scripts Bash, NCL e Python auxiliares, em um entrypoint fino que delega a execução para módulos em `src/mpas_workflow/bflow_core/`.

## Principais melhorias

- `bflow.py` deixa de concentrar toda a lógica operacional.
- `mpasbflow prepare`, `mpasbflow run` e `mpasbflow all` continuam existindo.
- O manifesto `manifest.tsv` continua sendo o contrato entre BFLOW e as etapas posteriores.
- As etapas Python antes geradas dinamicamente agora são módulos importáveis e testáveis:
  - `variables.py`;
  - `diff.py`;
  - `validate.py`;
  - `template.py`.
- O template `template_PTB.nc` não depende mais de NCO; agora é gerado com `netCDF4`.
- O orquestrador passou a ser `runner.py`, não `run_all_bflow.sh`.

## Dependências externas remanescentes

Ainda há duas fronteiras não puramente Python:

- `weights.py`: usa NCL para gerar pesos ESMF;
- `psichi.py`: usa NCL para converter `u/v` em `stream_function` e `velocity_potential`.

Essas duas partes foram isoladas para facilitar a substituição futura.

## Teste recomendado no JACI

Executar primeiro com uma janela pequena, preferencialmente a mesma do smoke já documentado:

```bash
mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --clean-output \
  --force
```

Depois comparar os arquivos `PTB_f48mf24.nc` com os produtos gerados pelo fluxo anterior, se ainda estiverem disponíveis.

## Atenção

`mpasbflow run` agora aceita `--config`. Quando o workspace não foi criado com a configuração padrão, use explicitamente o mesmo YAML usado no `prepare`.
