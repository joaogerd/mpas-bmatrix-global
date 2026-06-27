# `mpasverify`

## Para que serve

`mpasverify` compara produtos NetCDF gerados pelo workflow. Ele substitui dependências externas como `ncdiff` quando essas ferramentas não estão disponíveis no ambiente.

## Papel no workflow da matriz B

A ferramenta é usada para validar refatorações, comparar resultados novos contra baselines e gerar relatórios de diferença.

## Teoria usada

A comparação é estatística. Para cada variável numérica compatível, são calculados:

- `Bias`: média de `new - old`;
- `MAE`: erro absoluto médio;
- `RMSE`: raiz do erro quadrático médio;
- `RelRMSE`: `RMSE / std(old)`;
- `MaxAbs`: maior diferença absoluta;
- `Corr`: correlação entre campos.

## Entradas

- Arquivo NetCDF antigo ou de referência.
- Arquivo NetCDF novo.
- Lista opcional de variáveis.

## Saídas

- Tabela no terminal.
- Arquivo NetCDF opcional com diferença `new - old`.
- Relatório Markdown opcional.

## Como funciona internamente

A implementação está em:

```text
src/mpas_workflow/verify.py
src/mpas_workflow/validation/
```

Módulos:

- `dataset.py`: leitura e comparação de datasets;
- `statistics.py`: métricas por variável;
- `report.py`: tabela e relatório Markdown.

## Comandos principais

Comparar dois arquivos:

```bash
mpasverify compare \
  --old old/PTB_f48mf24.nc \
  --new new/PTB_f48mf24.nc
```

Comparar variáveis específicas:

```bash
mpasverify compare \
  --old old.nc \
  --new new.nc \
  -v stream_function,velocity_potential,temperature
```

Gerar diferença e relatório:

```bash
mpasverify compare \
  --old old.nc \
  --new new.nc \
  --write-diff diff.nc \
  --report report.md
```

## Opções

- `--old`: arquivo de referência.
- `--new`: arquivo novo.
- `-v`, `--variable`: variável ou lista separada por vírgula.
- `--write-diff`: escreve NetCDF `new - old`.
- `--report`: escreve relatório Markdown.
- `--strict`: retorna código de erro se houver variável ausente ou shape incompatível.

## Interpretação

- `Corr = 1` e `RelRMSE` muito pequeno indicam equivalência numérica forte.
- `Corr = -1` sugere inversão de sinal.
- `shape_mismatch` indica alteração estrutural do produto.
- `missing_old` ou `missing_new` indica mudança de variáveis.

## Problemas comuns

- Arquivos com variáveis de mesmo nome mas dimensões diferentes.
- Campos constantes, nos quais correlação pode não ser informativa.
- Diferenças pequenas em `float32` aparecendo em `RMSE`, mas com `RelRMSE` desprezível.
