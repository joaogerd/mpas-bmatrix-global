# mpas-bmatrix-global

Workflow para geração de condições iniciais MPAS, forecasts globais e pares NMC para preparação de matriz B.

## Novo workflow Python

A reorganização do processo MPAS está documentada em:

```text
docs/mpas-workflow-python.md
```

Entrada principal:

```bash
scripts/mpaswf --help
```

Configuração padrão JACI:

```text
configs/jaci-x1.10242.yaml
```

## Documentação JACI

Resumo operacional da infraestrutura JACI, filas PBS, tempos máximos, tipos de nós, filesystems e boas práticas:

```text
docs/jaci-operational-guide.md
```

## Exemplo rápido

```bash
export PYTHONPATH=$PWD/src:$PYTHONPATH

scripts/mpaswf nmc one-pair \
  --old-init-time 2026-06-10_00:00:00 \
  --new-init-time 2026-06-11_00:00:00 \
  --valid-time 2026-06-12_00:00:00 \
  --dt 60 \
  --submit
```
