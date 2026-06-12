# Workflow Python para rodar MPAS global

Este documento descreve o fluxo Python do repositório `mpas-bmatrix-global`.

## Objetivo

Substituir o conjunto de scripts numerados por uma CLI única, com etapas explícitas e responsabilidades separadas:

1. Baixar/decodificar GFS com WPS `ungrib`;
2. Preparar e submeter `mpas_init_atmosphere`;
3. Validar o `init.nc`;
4. Preparar e submeter `mpas_atmosphere`;
5. Montar pares NMC `f048 - f024`;
6. Validar pares NMC e gerar diferenças NetCDF;
7. Orquestrar ciclos e intervalos de pares NMC de forma idempotente.

## Instalação em modo desenvolvimento

```bash
cd /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
conda activate mpaswf
python -m pip install -e .
```

Alternativa sem instalar:

```bash
export PYTHONPATH=$PWD/src:$PYTHONPATH
scripts/mpaswf --help
```

## Configuração

Arquivo principal:

```text
configs/jaci-x1.10242.yaml
```

Ele define:

* diretórios de projeto, dados e trabalho;
* executáveis do MPAS;
* arquivos da malha `x1.10242`;
* invariant file;
* WPS/ungrib;
* fila PBS;
* `config_dt`.

## Rodar etapas individuais

### 1. ungrib

```bash
mpaswf ungrib --init-time 2026-06-11_00:00:00
```

### 2. preparar init

```bash
mpaswf init prepare --init-time 2026-06-11_00:00:00
```

### 3. submeter init

```bash
mpaswf init submit --init-time 2026-06-11_00:00:00
```

### 4. validar init

```bash
mpaswf init validate --init-time 2026-06-11_00:00:00
```

### 5. preparar forecast

Forecast de 24h:

```bash
mpaswf forecast prepare \
  --init-time 2026-06-11_00:00:00 \
  --lead-hours 24 \
  --dt 60
```

Forecast de 48h:

```bash
mpaswf forecast prepare \
  --init-time 2026-06-11_00:00:00 \
  --lead-hours 48 \
  --dt 60
```

### 6. submeter forecast

```bash
mpaswf forecast submit --init-time 2026-06-11_00:00:00 --lead-hours 24 --dt 60
mpaswf forecast submit --init-time 2026-06-11_00:00:00 --lead-hours 48 --dt 60
```

## Rodar um ciclo completo

O comando abaixo faz a orquestração idempotente de um ciclo: se o `init.nc` não existir, ele prepara/submete o `mpas_init`; se o `restart` do forecast não existir, ele prepara/submete o `mpas_atmosphere`.

```bash
mpaswf cycle run \
  --init-time 2026-06-11_00:00:00 \
  --lead-hours 24 \
  --dt 60 \
  --submit
```

Quando algum job PBS for submetido, o comando para. Depois que o job terminar, rode o mesmo comando novamente.

## Montar par NMC

Um par NMC usa dois ciclos com mesmo horário válido:

```text
OLD_INIT_TIME + 48h = VALID_TIME
NEW_INIT_TIME + 24h = VALID_TIME
```

Exemplo:

```text
OLD_INIT_TIME = 2026-06-10_00:00:00
NEW_INIT_TIME = 2026-06-11_00:00:00
VALID_TIME    = 2026-06-12_00:00:00
```

Comando:

```bash
mpaswf nmc pair \
  --old-init-time 2026-06-10_00:00:00 \
  --new-init-time 2026-06-11_00:00:00 \
  --valid-time 2026-06-12_00:00:00 \
  --dt 60
```

## Validar e gerar a diferença NMC

```bash
mpaswf nmc validate \
  --valid-time 2026-06-12_00:00:00
```

```bash
mpaswf nmc diff \
  --valid-time 2026-06-12_00:00:00 \
  --variables u,w,rho,theta,qv,surface_pressure
```

O arquivo padrão é criado dentro do diretório do par:

```text
nmc_diff_f048_minus_f024.nc
```

## Orquestração idempotente de um par

Este comando prepara/submete o que estiver faltando e para quando submeter algum job PBS.

```bash
mpaswf nmc one-pair \
  --old-init-time 2026-06-10_00:00:00 \
  --new-init-time 2026-06-11_00:00:00 \
  --valid-time 2026-06-12_00:00:00 \
  --dt 60 \
  --submit
```

Para também gerar a diferença NMC quando o par estiver completo:

```bash
mpaswf nmc one-pair \
  --old-init-time 2026-06-10_00:00:00 \
  --new-init-time 2026-06-11_00:00:00 \
  --valid-time 2026-06-12_00:00:00 \
  --dt 60 \
  --submit \
  --diff \
  --variables u,w,rho,theta,qv,surface_pressure
```

## Orquestração de vários pares NMC

Use `nmc range` para processar vários horários válidos consecutivos. Para cada `VALID_TIME`, o workflow calcula automaticamente:

```text
OLD_INIT_TIME = VALID_TIME - 48h
NEW_INIT_TIME = VALID_TIME - 24h
```

Exemplo:

```bash
mpaswf nmc range \
  --start-valid-time 2026-06-12_00:00:00 \
  --end-valid-time 2026-06-15_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --submit \
  --diff \
  --variables u,w,rho,theta,qv,surface_pressure
```

O comando é idempotente. Se algum init ou forecast ainda não existir, ele prepara/submete o job necessário e para. Depois que o PBS terminar, rode o mesmo comando novamente.

## Scripts legados

Os scripts shell numerados foram movidos para:

```text
scripts/legacy/
```

Eles ficam disponíveis apenas como referência histórica. O fluxo oficial deve usar a CLI Python `mpaswf`.

Os únicos scripts mantidos diretamente em `scripts/` são:

```text
scripts/mpaswf
scripts/load_jaci_env.sh
```

* `scripts/mpaswf` é o wrapper da CLI Python.
* `scripts/load_jaci_env.sh` continua sendo usado para carregar o ambiente JACI/MPAS nos jobs PBS.
