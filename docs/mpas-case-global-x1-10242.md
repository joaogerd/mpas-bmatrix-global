# Caso declarativo MPAS global x1.10242

O caso `configs/mpas/cases/global-x1.10242` descreve somente a preparação de
configurações para um MPAS-Atmosphere global, em três estágios independentes:

```text
static   -> interpola campos estáticos da malha e produz x1.10242.static.nc
init     -> usa static.nc e FILE:YYYY-MM-DD_HH para produzir init.nc
forecast -> usa static.nc e init.nc para preparar um forecast MPAS
```

O caso não chama WPS, não cria links de runtime, não submete PBS e não cria
produtos JEDI. Essas responsabilidades pertencem às tarefas de preparação e
ao orquestrador.

## Estrutura

```text
configs/mpas/
  defaults/mpas-atmosphere.yaml
  sites/jaci.yaml
  cases/global-x1.10242/case.yaml
  overlays/monan-jedi-da.yaml
  cases/global-x1.10242-monan-jedi/case.yaml
```

O caso JEDI não replica o caso base: ele inclui `global-x1.10242` e acrescenta
somente o stream `da_state`, com `packages="jedi_da"`.

## Renderização em modo seco

No JACI:

```bash
source scripts/load_jaci_env.sh

export INIT=2026-06-12_00:00:00
export DT=1200

bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242 \
  --stage static \
  --init-time "$INIT" \
  --dt "$DT" \
  --dry-run

bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242 \
  --stage init \
  --init-time "$INIT" \
  --dt "$DT" \
  --dry-run

bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242 \
  --stage forecast \
  --init-time "$INIT" \
  --lead-hours 6 \
  --dt "$DT" \
  --dry-run
```

O modo seco resolve o caso, verifica os placeholders e mostra os caminhos que
seriam emitidos. Ele não exige que os templates instalados existam no ambiente
local onde o comando foi executado.

## Primeira renderização real

A primeira execução real deve ir para um diretório temporário, pois ela valida
os nomes dos grupos do namelist e dos streams da versão MPAS instalada:

```bash
export RENDER_TEST=/tmp/mpas-render-x1.10242-static
rm -rf "$RENDER_TEST"

bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242 \
  --stage static \
  --init-time "$INIT" \
  --dt "$DT" \
  --output-dir "$RENDER_TEST"

sed -n '1,180p' "$RENDER_TEST/namelist.init_atmosphere"
sed -n '1,120p' "$RENDER_TEST/streams.init_atmosphere"
cat "$RENDER_TEST/mpas-render-manifest.json"
```

A renderização deve falhar antes de escrever resultados quando o build não
contiver um grupo de namelist ou um stream que o caso declarou. Esse é um erro
de contrato da configuração, não uma razão para inserir exceções específicas
no código Python.

## Convenções científicas do caso

- A fase `static` usa a grade `x1.10242.grid.nc` e produz
  `x1.10242.static.nc`.
- A fase `init` consome esse `static.nc`, gera a grade vertical e interpola os
  arquivos meteorológicos `FILE:*`.
- A fase `forecast` usa o `static.nc` recém-gerado como stream `invariant` e o
  `init.nc` correspondente como stream `input`.
- O namelist de forecast vem do `core_atmosphere` instalado pelo build; não é
  copiado do tutorial.
- A configuração de amortecimento usa as opções modernas
  `config_epssm_minimum`, `config_epssm_maximum` e faixas de transição.

Ainda não há execução científica validada desse caso nesta branch. O objetivo
desta etapa é tornar os arquivos de entrada explícitos, reproduzíveis e
comparáveis antes de conectar a preparação de runtime e a execução pelo
simpleWorkflow.
