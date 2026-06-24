# Caso MPAS global x1.10242

A configuração MPAS combina três níveis, todos em YAML e todos acessíveis no
repositório:

```text
configs/
  sites/
    jaci.yaml
  mpas/
    default/
      common.yaml
      static.yaml
      init.yaml
      forecast.yaml
    cases/
      global-x1.10242.yaml
    overlays/
      monan-jedi.yaml
```

## Responsabilidades

- `configs/sites/jaci.yaml`: infraestrutura local, instalação MPAS, catálogo de
  malhas e WPS_GEOG;
- `configs/mpas/default/*.yaml`: contrato MPAS estável e auditável usado pelo
  renderer. Cada arquivo representa uma parte importante do fluxo:
  convenções comuns, geração de `static.nc`, geração de `init.nc` e forecast;
- `configs/mpas/cases/global-x1.10242.yaml`: escolhas que normalmente variam
  entre casos: malha, resolução, processos, níveis verticais e intervalo de
  saída;
- `configs/mpas/overlays/monan-jedi.yaml`: extensão opcional que reativa
  `da_state` para MONAN-JEDI.

O caso x1.10242 inclui os defaults, mas não replica grupos de namelist ou
streams XML. Isso mantém os detalhes MPAS visíveis e versionados, sem obrigar o
usuário a editá-los em cada experimento.

## Renderização

```bash
source scripts/load_jaci_env.sh

export INIT=2026-06-12_00:00:00
export DT=1200

bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242.yaml \
  --stage static \
  --init-time "$INIT" \
  --dt "$DT" \
  --dry-run

bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242.yaml \
  --stage init \
  --init-time "$INIT" \
  --dt "$DT" \
  --dry-run

bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242.yaml \
  --stage forecast \
  --init-time "$INIT" \
  --lead-hours 6 \
  --dt "$DT" \
  --dry-run
```

A renderização gera os `namelist.*` e `streams.*` usados diretamente pelo MPAS,
além de um manifesto JSON com contexto, templates e hashes. Ela não executa
WPS, não prepara links de runtime e não submete PBS.

## Alterações avançadas

A maioria dos usuários deve criar ou editar somente um arquivo em `cases/`.
Quando uma mudança for estrutural ou específica de versão MPAS — por exemplo,
um novo grupo de namelist, um stream obrigatório ou uma alteração do fluxo
`static -> init -> forecast` — ela deve ser feita no default do estágio
correspondente. Isso torna a mudança explícita, revisável e reutilizável por
todas as malhas.

## Convenções validadas

- `config_nvertlevels` fica em `&dimensions`;
- estágios estático e de inicialização ficam em `&preproc_stages`;
- decomposição fica em `&decomposition`;
- `static` usa WPS_GEOG local do JACI, não o caminho `/glade` do template;
- `forecast` usa opções modernas `config_epssm_*`;
- streams dependentes de malha usam nomes `x1.10242`, sem resíduos de
  `x1.40962`;
- IAU e `da_state` permanecem desativados no caso MPAS puro.
