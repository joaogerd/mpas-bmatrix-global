# Status da refatoração BFLOW

Estado atual da branch `refactor/bflow-python-pipeline`.

## Feito

- `src/mpas_workflow/bflow.py` foi reduzido a um entrypoint de compatibilidade.
- A implementação foi modularizada em `src/mpas_workflow/bflow_core/`.
- O pipeline principal passou para `bflow_core/runner.py`.
- O manifesto foi isolado em `manifest.py`.
- A montagem de pares NMC e utilitários de tempo foram isolados em `model.py`.
- A criação de workspace, links e README foi isolada em `workspace.py`.
- A geração de `template_PTB.nc` foi reimplementada em Python usando `netCDF4`.
- A adição de variáveis, diferença NMC e validação foram movidas para módulos Python reais.
- A execução externa foi centralizada em `external.py`.

## Ainda pendente para Python puro

- Substituir `weights.py`, que ainda chama NCL para pesos ESMF.
- Substituir `psichi.py`, que ainda chama NCL para `u/v -> psi/chi`.
- Criar testes de regressão numérica contra produtos gerados pelo fluxo antigo.

## Recomendação

Antes de remover NCL, validar esta branch no JACI usando o smoke de quatro amostras. Após isso, seguir para uma segunda branch focada exclusivamente em substituir `weights.py` e `psichi.py`.
