# Resumo curto da refatoração BFLOW

A branch `refactor/bflow-python-pipeline` transforma o BFLOW em um pipeline Python modular.

## Antes

`src/mpas_workflow/bflow.py` acumulava responsabilidades:

- montava pares NMC;
- criava workspace;
- escrevia scripts Bash;
- escrevia scripts Python auxiliares;
- escrevia scripts NCL;
- executava `run_all_bflow.sh`.

## Depois

`src/mpas_workflow/bflow.py` é apenas compatibilidade de CLI. A lógica foi movida para:

```text
src/mpas_workflow/bflow_core/
```

O pipeline principal está em:

```text
src/mpas_workflow/bflow_core/runner.py
```

## O que virou Python real

- criação de manifesto;
- preparação de workspace;
- geração de template NetCDF;
- adição de variáveis derivadas;
- cálculo de `PTB_f48mf24.nc`;
- validação dos produtos.

## O que ainda chama NCL

- geração dos pesos ESMF;
- conversão `u/v -> psi/chi`.

Essas duas partes já estão isoladas para serem substituídas depois.
