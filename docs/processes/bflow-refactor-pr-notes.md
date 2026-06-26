# BFLOW PR notes

## Objetivo

Refatorar `mpasbflow` para deixar de ser um gerador de scripts e passar a ser um pipeline Python modular.

## Escopo desta branch

Inclui:

- modularização em `bflow_core`;
- remoção do `run_all_bflow.sh` como orquestrador;
- remoção dos scripts Python gerados no workspace;
- geração do template NetCDF em Python;
- documentação do caminho para remover NCL.

Não inclui ainda:

- substituição completa do NCL;
- validação numérica no JACI;
- alteração do contrato dos arquivos `PTB_f48mf24.nc`.
