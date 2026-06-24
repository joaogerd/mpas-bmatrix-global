# Caso MPAS global x1.10242

A configuração pública do MPAS foi reduzida a três pontos de entrada:

```text
configs/
  sites/
    jaci.yaml
  mpas/
    cases/
      global-x1.10242.yaml
    overlays/
      monan-jedi.yaml
```

`configs/sites/jaci.yaml` descreve somente a infraestrutura local: caminhos de
instalação do MPAS, catálogo de malhas e dados geográficos WPS.

`configs/mpas/cases/global-x1.10242.yaml` é o único arquivo necessário para
descrever a malha e os estágios MPAS do caso:

```text
static   -> grid.nc produz static.nc
init     -> static.nc e FILE:* produzem init.nc
forecast -> static.nc e init.nc preparam a integração MPAS
```

`configs/mpas/overlays/monan-jedi.yaml` é opcional. Ele adiciona o stream
`da_state` quando um experimento precisa de produtos para MONAN-JEDI; o caso
MPAS base não depende de JEDI.

## Renderização

No JACI:

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

A renderização gera os mesmos `namelist.*` e `streams.*` que o MPAS usa
normalmente, mais um manifesto JSON com contexto, templates e hashes. Ela não
executa WPS, não prepara links de runtime e não submete PBS.

## Uso de overlay JEDI

Um experimento que precise de JEDI pode criar um arquivo mínimo próprio:

```yaml
includes:
  - /caminho/para/configs/mpas/cases/global-x1.10242.yaml
  - /caminho/para/configs/mpas/overlays/monan-jedi.yaml

case:
  name: global-x1.10242-monan-jedi
```

Assim, a configuração básica não fica mais complexa por causa de uma extensão
opcional.

## Convenções validadas

- `config_nvertlevels` fica em `&dimensions`;
- estágios estático e de inicialização ficam em `&preproc_stages`;
- decomposição fica em `&decomposition`;
- `static` usa o WPS_GEOG local do JACI, não o caminho `/glade` do template;
- `forecast` usa opções modernas `config_epssm_*`;
- streams dependentes de malha usam nomes `x1.10242`, sem resíduos de
  `x1.40962`;
- IAU e `da_state` permanecem desativados no caso MPAS puro.
