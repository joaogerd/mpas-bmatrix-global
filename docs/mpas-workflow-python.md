# Workflow Python para rodar MPAS global

Este documento descreve o novo fluxo Python do repositório `mpas-bmatrix-global`.

## Objetivo

Substituir o conjunto de scripts numerados em `scripts/` por uma CLI única, com etapas explícitas e responsabilidades separadas:

1. Baixar/decodificar GFS com WPS `ungrib`;
2. Preparar e submeter `mpas_init_atmosphere`;
3. Validar o `init.nc`;
4. Preparar e submeter `mpas_atmosphere`;
5. Montar pares NMC `f048 - f024`.

## Instalação em modo desenvolvimento

```bash
cd /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
python3 -m pip install --user -e .
````

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

## Rodar um ciclo MPAS

Exemplo para `2026-06-11_00:00:00`.

### 1. ungrib

```bash
scripts/mpaswf ungrib --init-time 2026-06-11_00:00:00
```

### 2. preparar init

```bash
scripts/mpaswf init prepare --init-time 2026-06-11_00:00:00
```

### 3. submeter init

```bash
scripts/mpaswf init submit --init-time 2026-06-11_00:00:00
```

### 4. validar init

```bash
scripts/mpaswf init validate --init-time 2026-06-11_00:00:00
```

### 5. preparar forecast

Forecast de 24h:

```bash
scripts/mpaswf forecast prepare \
  --init-time 2026-06-11_00:00:00 \
  --lead-hours 24 \
  --dt 60
```

Forecast de 48h:

```bash
scripts/mpaswf forecast prepare \
  --init-time 2026-06-11_00:00:00 \
  --lead-hours 48 \
  --dt 60
```

### 6. submeter forecast

```bash
scripts/mpaswf forecast submit --init-time 2026-06-11_00:00:00 --lead-hours 24 --dt 60
scripts/mpaswf forecast submit --init-time 2026-06-11_00:00:00 --lead-hours 48 --dt 60
```

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
scripts/mpaswf nmc pair \
  --old-init-time 2026-06-10_00:00:00 \
  --new-init-time 2026-06-11_00:00:00 \
  --valid-time 2026-06-12_00:00:00 \
  --dt 60
```

## Orquestração idempotente de um par

Este comando prepara/submete o que estiver faltando e para quando submeter algum job PBS.

```bash
scripts/mpaswf nmc one-pair \
  --old-init-time 2026-06-10_00:00:00 \
  --new-init-time 2026-06-11_00:00:00 \
  --valid-time 2026-06-12_00:00:00 \
  --dt 60 \
  --submit
```

Depois que o PBS terminar, rode o mesmo comando novamente.

## Scripts legados

Os scripts shell numerados foram movidos para:

```text
scripts/legacy/
````

Eles ficam disponíveis apenas como referência histórica. O fluxo oficial deve usar a CLI Python `mpaswf`.

Os únicos scripts mantidos diretamente em `scripts/` são:

```text
scripts/mpaswf
scripts/load_jaci_env.sh
```

* `scripts/mpaswf` é o wrapper da CLI Python.
* `scripts/load_jaci_env.sh` continua sendo usado para carregar o ambiente JACI/MPAS nos jobs PBS.

