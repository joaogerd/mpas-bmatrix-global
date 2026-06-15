# Ferramentas auxiliares do workflow de B

Este documento registra os comandos auxiliares adicionados após a validação do smoke test da matriz B global.

## Validação agregada da cadeia

O comando abaixo valida, em ordem, os workspaces esperados de VBAL, HDIAG, NICAS, SO e Dirac:

```bash
mpasbcov-pipeline \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace /caminho/para/bflow_workspace
```

Também é possível informar explicitamente cada workspace:

```bash
mpasbcov-pipeline \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --vbal-workspace "$VBAL" \
  --hdiag-workspace "$HDIAG" \
  --nicas-workspace "$NICAS" \
  --so-workspace "$SO" \
  --dirac-workspace "$DIRAC"
```

O comando não cria dados novos. Ele apenas resolve os caminhos e chama as validações existentes.

## Diagnóstico do Dirac

O comando abaixo resume variáveis numéricas de um arquivo `mpas.dirac.nc`:

```bash
mpasdirac-summary /caminho/para/mpas.dirac.nc
```

A saída é CSV simples com:

```text
variable,shape,min,max,rms,absmax,nonzero
```

Essa ferramenta serve para uma primeira inspeção rápida do produto Dirac, antes de visualizações espaciais mais completas.

## Smoke versus produção

O smoke test validado deve permanecer pequeno e barato. Configurações de produção devem ser criadas separadamente, com mais membros e política própria de filas, walltime e retenção de produtos.
