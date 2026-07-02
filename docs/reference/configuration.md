# Referência de configuração

## Arquivo principal

O workflow usa arquivos YAML em `configs/`. O arquivo padrão para a JACI e malha `x1.10242` é:

```text
configs/jaci-x1.10242.yaml
```

## Blocos principais

### `project`

Define diretórios de projeto, dados e trabalho.

Campos típicos:

```yaml
project:
  project_root: /p/projetos/monan_das/<user>/projects/mpas-bmatrix-global
  data_root: /p/projetos/monan_das/<user>/data/mpas-bmatrix-global
  work_root: /p/projetos/monan_das/<user>/work/mpas-bmatrix-global
```

### `environment`

Define como carregar o ambiente JACI.

```yaml
environment:
  loader: scripts/load_jaci_env.sh
```

### `install`

Define executáveis e diretórios instalados.

Campos usados:

- `root`
- `mpas_init`
- `mpas_atmosphere`
- `atmosphere_share`

### `mesh`

Define a malha MPAS e particionamento.

Campos usados:

- `name`
- `grid`
- `graph`
- `partitions_dir`
- `nproc`
- `nvertlevels`

### `static`

Define arquivos estáticos e auxiliares.

Campos usados:

- `invariant`
- `tutorial_physics_files`
- `geovars`
- `keptvars`

### `runtime`

Define parâmetros de execução MPAS.

Campos usados:

- `config_dt`
- `output_interval`

### `pbs`

Define fila, número de processos e tempos de execução.

Campos comuns:

```yaml
pbs:
  queue: pesqmini
  nproc: 128
  walltime_short: 00:10:00
  queues:
    bmatrix: pesqmini
  walltime:
    bmatrix: 00:30:00
```

## Como os comandos usam a configuração

- `mpasforecast`: usa `project`, `install`, `mesh`, `static`, `runtime`, `pbs`.
- `mpasbflow`: usa `project`, `mesh`, `static`, `runtime`.
- `mpasvbal`: usa `project`, `install`, `mesh`, `static`, `pbs`, `environment`.
- `mpashdiag`: usa `project`, `install`, `mesh`, `pbs`, `environment`.
- `mpasnicas`: usa `project`, `install`, `mesh`, `pbs`, `environment`.
- `mpasso`: usa `project`, `install`, `mesh`, `pbs`, `environment`.

## Boas práticas

- Não codificar caminhos absolutos dentro dos scripts.
- Manter caminhos específicos da plataforma somente em `configs/*.yaml`.
- Usar um arquivo por plataforma/malha.
- Validar comandos com `--help` após instalar.
- Versionar alterações de configuração junto com mudanças no workflow.

## Problemas comuns

- `work_root` apontando para diretório sem permissão de escrita.
- `nproc` sem partição correspondente.
- `install.root` inconsistente com os executáveis instalados.
- `static.invariant` incompatível com a malha.
- `environment.loader` não carregando módulos esperados.
