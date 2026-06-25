# Preparação de runtime MPAS

## Objetivo

`mpas-stage-prepare` cria um diretório de execução reproduzível a partir de um
caso MPAS e de arquivos já renderizados por `mpas-render`. Ele **não** executa
MPAS, WPS, PBS, JEDI ou etapas de matriz B.

O preparador valida todos os insumos antes de criar links simbólicos. Em caso
de arquivo ausente, diretório inválido, destino incompatível ou partição não
encontrada, ele falha sem criar um runtime parcial.

## Separação de responsabilidades

```text
mpas-render
  -> namelist.*, streams.*, mpas-render-manifest.json

mpas-stage-prepare
  -> diretório de runtime com links e mpas-runtime-manifest.json

camada de execução futura
  -> PBS / MPI / MPAS / validação NetCDF
```

Os contratos de runtime estão em `configs/mpas/default/runtime-*.yaml`. Eles
são incluídos pelo caso MPAS, assim como os defaults de renderização.

## Estágio static

O `static` é o primeiro estágio executável. Ele precisa de:

- `namelist.init_atmosphere` e `streams.init_atmosphere` já renderizados;
- `mpas_init_atmosphere` instalado;
- grade, grafo e partição da malha;
- diretório local `WPS_GEOG_LOW_RES`.

Primeiro, gere os artefatos reais de renderização:

```bash
export INIT=2026-06-12_00:00:00
export DT=1200

bash scripts/mpas-render \
  --case configs/mpas/cases/global-x1.10242.yaml \
  --stage static \
  --init-time "$INIT" \
  --dt "$DT"
```

Verifique o plano de runtime, sem gravar links:

```bash
bash scripts/mpas-stage-prepare \
  --case configs/mpas/cases/global-x1.10242.yaml \
  --stage static \
  --init-time "$INIT" \
  --dt "$DT" \
  --dry-run
```

Quando o plano estiver correto, prepare o diretório:

```bash
bash scripts/mpas-stage-prepare \
  --case configs/mpas/cases/global-x1.10242.yaml \
  --stage static \
  --init-time "$INIT" \
  --dt "$DT"
```

O diretório padrão será:

```text
{work_root}/mpas-runtime/global-x1.10242/static
```

Ele conterá links para executável, namelist, streams, grade, grafo e partição,
além de `mpas-runtime-manifest.json`. O próximo passo será uma tarefa de
execução controlada do `mpas_init_atmosphere`, ainda fora do escopo deste
comando.

## Estágio init

O `init` depende de produtos já existentes do runtime `static` e dos arquivos
`FILE:*` gerados pelo WPS. Por padrão, esses arquivos são procurados em:

```text
{work_root}/wps/{safe_time}
```

Quando estiverem em outro local, informe-o explicitamente:

```bash
bash scripts/mpas-stage-prepare \
  --case configs/mpas/cases/global-x1.10242.yaml \
  --stage init \
  --init-time "$INIT" \
  --dt "$DT" \
  --set wps_input_dir=/caminho/para/FILE
```

## Estágio forecast

O `forecast` exige os produtos de `static` e o `init.nc` do mesmo ciclo. Ele
prepara o diretório com `mpas_atmosphere`, namelist, streams, grafo, partição e
links para as entradas. A execução MPI/PBS será uma etapa posterior.

## Idempotência

Repetir um comando com os mesmos insumos preserva links já corretos. Um destino
que exista como arquivo comum ou link para origem diferente é tratado como
incompatível e interrompe o comando antes de qualquer escrita.
