# mpas-bmatrix-global

Workflow para geração de condições iniciais MPAS, forecasts globais e pares NMC para preparação de matriz B.

## Novo workflow Python

A reorganização do processo MPAS está documentada em:

[docs/mpas-workflow-python.md](docs/mpas-workflow-python.md)

Entrada principal:

[scripts/mpaswf](scripts/mpaswf)

Para ver as opções disponíveis:

```bash
scripts/mpaswf --help
```

Configuração padrão JACI:

[configs/jaci-x1.10242.yaml](configs/jaci-x1.10242.yaml)

## Documentação do sistema

Guia técnico completo do sistema de geração dos estados MPAS usados no cálculo da matriz B:

[docs/mpas-bmatrix-workflow-system.md](docs/mpas-bmatrix-workflow-system.md)

## Tutorial para execução do sistema

Tutorial que descreve o processo completo para gerar, calibrar, validar e organizar uma matriz B estática global para uso no MPAS-JEDI/SABER:

[docs/tutorial_bmatrix.md](docs/tutorial_bmatrix.md)

## Documentação JACI

Resumo operacional da infraestrutura JACI, filas PBS, tempos máximos, tipos de nós, filesystems e boas práticas:

[docs/jaci-operational-guide.md](docs/jaci-operational-guide.md)

## Exemplo rápido

```bash
export PYTHONPATH=$PWD/src:$PYTHONPATH
scripts/mpaswf nmc one-pair --old-init-time 2026-06-10_00:00:00 --new-init-time 2026-06-11_00:00:00 --valid-time 2026-06-12_00:00:00 --dt 60 --submit
```

