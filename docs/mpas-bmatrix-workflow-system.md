# Sistema de geração de estados MPAS para cálculo da matriz B

> Documento técnico do workflow `mpas-bmatrix-global`.
>
> Objetivo: explicar, de forma operacional, como o sistema gera os estados MPAS usados na construção de perturbações NMC e, posteriormente, no cálculo da matriz B do MPAS-JEDI.

---

## 1. Visão geral do workflow

O workflow gera pares NMC a partir de duas previsões MPAS válidas no mesmo horário:

```text
f048 - f024
```

onde:

- `f048` é a previsão de 48 horas iniciada em um ciclo mais antigo;
- `f024` é a previsão de 24 horas iniciada em um ciclo mais recente;
- ambas são comparadas no mesmo horário válido.

Para um horário válido `T`, o par NMC é definido como:

```text
OLD_INIT_TIME = T - 48 h
NEW_INIT_TIME = T - 24 h
VALID_TIME    = T
```

Exemplo:

```text
VALID_TIME    = 2026-06-12_00:00:00
OLD_INIT_TIME = 2026-06-10_00:00:00  -> forecast f048
NEW_INIT_TIME = 2026-06-11_00:00:00  -> forecast f024
```

O fluxo completo é:

```text
GFS GRIB2
   ↓
WPS ungrib
   ↓
FILE:YYYY-MM-DD_HH
   ↓
MPAS init_atmosphere
   ↓
x1.10242.init.YYYY-MM-DD_HH.MM.SS.nc
   ↓
MPAS atmosphere forecast f024/f048
   ↓
restart.YYYY-MM-DD_HH.MM.SS.nc
   ↓
Par NMC: f048.nc + f024.nc
   ↓
Diferença NMC: nmc_diff_f048_minus_f024.nc
   ↓
Entrada para estatísticas/cálculo da matriz B
```

---

## 2. Configuração central do workflow

A configuração padrão usada no JACI fica em:

```text
configs/jaci-x1.10242.yaml
```

Esse arquivo define todos os caminhos e parâmetros operacionais necessários para o workflow.

### 2.1 Seção `project`

Define as áreas principais do projeto:

```yaml
project:
  name: mpas-bmatrix-global
  project_root: /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
  data_root: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global
  work_root: /p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global
```

Uso de cada diretório:

| Diretório | Função |
|---|---|
| `project_root` | repositório, código-fonte, scripts e configuração |
| `data_root` | dados externos persistentes, como GFS e WPS |
| `work_root` | diretórios de execução, saídas temporárias, forecasts e pares NMC |

No JACI, tudo que será lido pelos jobs PBS deve estar em `/p`, pois os nós computacionais não acessam `/home2`.

### 2.2 Seção `environment`

Define o script usado para carregar o ambiente no PBS:

```yaml
environment:
  loader: scripts/load_jaci_env.sh
```

Esse script é chamado dentro dos arquivos PBS gerados automaticamente.

### 2.3 Seção `install`

Define os executáveis e diretórios de instalação do MPAS/MONAN-JEDI:

```yaml
install:
  root: /p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas
  mpas_init: /p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas/bin/mpas_init_atmosphere
  mpas_atmosphere: /p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas/bin/mpas_atmosphere
  init_share: /p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas/share/MPAS/core_init_atmosphere
  atmosphere_share: /p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas/share/MPAS/core_atmosphere
```

Arquivos necessários:

| Campo | Descrição |
|---|---|
| `mpas_init` | executável `mpas_init_atmosphere` |
| `mpas_atmosphere` | executável `mpas_atmosphere` |
| `init_share` | templates e arquivos auxiliares do core `init_atmosphere` |
| `atmosphere_share` | arquivos auxiliares do core `atmosphere` |

### 2.4 Seção `mesh`

Define a malha MPAS usada no workflow:

```yaml
mesh:
  name: x1.10242
  grid: /p/projetos/.../x1.10242.grid.nc
  graph: /p/projetos/.../x1.10242.graph.info
  partitions_dir: /p/projetos/.../partitions
  nproc: 64
  nvertlevels: 55
```

Arquivos necessários:

| Arquivo | Função |
|---|---|
| `x1.10242.grid.nc` | arquivo de malha MPAS |
| `x1.10242.graph.info` | grafo da malha para decomposição paralela |
| `x1.10242.graph.info.part.64` | partição METIS para execução com 64 MPI ranks |

O número em `nproc` precisa ser compatível com a partição disponível.

### 2.5 Seção `static`

Define arquivos estáticos usados na inicialização e no forecast:

```yaml
static:
  invariant: /p/projetos/.../x1.10242.invariant.nc
  tutorial_physics_files: /p/projetos/.../MPAS_namelist_stream_physics_files
```

O arquivo `invariant` é usado como entrada de malha/informação estática no `mpas_init_atmosphere` e no `mpas_atmosphere`.

### 2.6 Seção `wps`

Define a instalação do WPS usada para converter GFS GRIB2 em arquivos intermediários:

```yaml
wps:
  root: /p/projetos/.../WPS-4.6.0
  ungrib_exe: /p/projetos/.../WPS-4.6.0/ungrib.exe
  link_grib: /p/projetos/.../WPS-4.6.0/link_grib.csh
  vtable_gfs: /p/projetos/.../WPS-4.6.0/ungrib/Variable_Tables/Vtable.GFS
```

Arquivos necessários:

| Arquivo | Função |
|---|---|
| `ungrib.exe` | converte GRIB2 para formato intermediário WPS |
| `link_grib.csh` | cria links `GRIBFILE.*` esperados pelo WPS |
| `Vtable.GFS` | tabela de variáveis para interpretar os campos do GFS |

### 2.7 Seção `pbs`

Define fila, número de processos e walltimes:

```yaml
pbs:
  queue: pesqmini
  nproc: 64

  walltime:
    init: "00:10:00"
    forecast:
      f024: "00:30:00"
      f048: "00:30:00"
      default: "00:30:00"
```

No JACI, a fila `pesqmini` é apropriada para testes rápidos e tem limite de 30 minutos. Para execuções mais longas, deve-se trocar a fila e o walltime de acordo com a política do sistema.

### 2.8 Seção `runtime`

Define parâmetros de execução do modelo:

```yaml
runtime:
  config_dt: 60
  output_interval: "24:00:00"
```

| Campo | Função |
|---|---|
| `config_dt` | passo de tempo do MPAS, em segundos |
| `output_interval` | intervalo de saída dos arquivos `restart`, `history` e `diagnostics` |

Para a malha `x1.10242`, o workflow estabilizado usa `config_dt = 60`.

---

## 3. Etapa 1: obtenção do GFS e execução do WPS `ungrib`

### 3.1 Objetivo

Converter uma análise GFS em GRIB2 para o formato intermediário WPS:

```text
FILE:YYYY-MM-DD_HH
```

Esse arquivo é usado pelo `mpas_init_atmosphere` como first guess meteorológico.

### 3.2 Entradas necessárias

Para um ciclo `INIT_TIME`, por exemplo:

```text
2026-06-09_00:00:00
```

são necessários:

| Entrada | Exemplo |
|---|---|
| GFS GRIB2 | `gfs.t00z.pgrb2.0p25.f000` |
| `ungrib.exe` | definido em `wps.ungrib_exe` |
| `link_grib.csh` | definido em `wps.link_grib` |
| `Vtable.GFS` | definido em `wps.vtable_gfs` |
| `namelist.wps` | gerado automaticamente pelo workflow |

### 3.3 Diretórios usados

O GRIB é salvo em:

```text
${data_root}/external/gfs/YYYYMMDD/HH/gfs.tHHz.pgrb2.0p25.f000
```

Exemplo:

```text
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/gfs/20260609/00/gfs.t00z.pgrb2.0p25.f000
```

O diretório de execução do `ungrib` é:

```text
${work_root}/wps_ungrib/gfs.YYYYMMDDHH.f000
```

Exemplo:

```text
/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/wps_ungrib/gfs.2026060900.f000
```

### 3.4 `namelist.wps`

O workflow gera automaticamente um `namelist.wps` mínimo para o `ungrib`:

```fortran
&share
 wrf_core = 'ARW',
 max_dom = 1,
 start_date = 'YYYY-MM-DD_HH:00:00',
 end_date   = 'YYYY-MM-DD_HH:00:00',
 interval_seconds = 21600,
 io_form_geogrid = 2,
 /

&ungrib
 out_format = 'WPS',
 prefix = 'FILE',
 /

&metgrid
 fg_name = 'FILE',
 io_form_metgrid = 2,
 /
```

Campos importantes:

| Campo | Valor | Função |
|---|---|---|
| `start_date` | ciclo GFS | horário inicial do arquivo intermediário |
| `end_date` | igual ao `start_date` | somente uma análise é usada |
| `out_format` | `WPS` | formato intermediário de saída |
| `prefix` | `FILE` | prefixo do arquivo gerado |

### 3.5 Saída esperada

A saída principal é:

```text
FILE:YYYY-MM-DD_HH
```

Exemplo:

```text
FILE:2026-06-09_00
```

Se esse arquivo não existir, o `mpas_init_atmosphere` não deve ser submetido.

### 3.6 Comando isolado

```bash
mpaswf --config configs/jaci-x1.10242.yaml ungrib \
  --init-time 2026-06-09_00:00:00
```

---

## 4. Etapa 2: geração da condição inicial MPAS

### 4.1 Objetivo

Gerar uma condição inicial MPAS a partir de:

- arquivo intermediário WPS `FILE:YYYY-MM-DD_HH`;
- arquivo estático/invariant da malha;
- configuração do `namelist.init_atmosphere`;
- configuração do `streams.init_atmosphere`.

A saída é um arquivo:

```text
x1.10242.init.YYYY-MM-DD_HH.MM.SS.nc
```

### 4.2 Entradas necessárias

| Entrada | Origem |
|---|---|
| `mpas_init_atmosphere` | `install.mpas_init` |
| `FILE:YYYY-MM-DD_HH` | saída do WPS `ungrib` |
| `x1.10242.invariant.nc` | `static.invariant` |
| `x1.10242.graph.info` | `mesh.graph` |
| `x1.10242.graph.info.part.64` | `mesh.partitions_dir` |
| `namelist.init_atmosphere` | template em `install.init_share` |
| `streams.init_atmosphere` | template em `install.init_share` |
| `run_mpas_init.pbs` | gerado pelo workflow |

### 4.3 Diretório de execução

Para cada `INIT_TIME`, o diretório é:

```text
${work_root}/mpas_init/${mesh_name}/${INIT_TIME}_invariant_np${nproc}
```

Exemplo:

```text
/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/mpas_init/x1.10242/2026-06-09_00:00:00_invariant_np64
```

### 4.4 Arquivos locais criados no diretório

O workflow prepara links e arquivos locais:

| Arquivo local | Origem/Função |
|---|---|
| `mpas_init_atmosphere` | link para o executável |
| `x1.10242.grid.nc` | link para `static.invariant` |
| `FILE:YYYY-MM-DD_HH` | link para saída do WPS |
| `x1.10242.graph.info` | link para grafo da malha |
| `x1.10242.graph.info.part.64` | link para partição MPI |
| `namelist.init_atmosphere` | gerado a partir do template |
| `streams.init_atmosphere` | gerado a partir do template corrigido |
| `run_mpas_init.pbs` | script PBS gerado |

### 4.5 Campos importantes do `namelist.init_atmosphere`

O workflow modifica automaticamente os seguintes campos:

```fortran
&nhyd_model
    config_init_case = 7
    config_start_time = 'YYYY-MM-DD_HH:00:00'
    config_stop_time = 'YYYY-MM-DD_HH:00:00'
/

&dimensions
    config_nvertlevels = 55
/

&data_sources
    config_met_prefix = 'FILE'
    config_sfc_prefix = 'FILE'
/

&preproc_stages
    config_static_interp = .false.
    config_native_gwd_static = .false.
    config_native_gwd_gsl_static = .false.
    config_vertical_grid = .true.
    config_met_interp = .true.
/

&decomposition
    config_block_decomp_file_prefix = 'x1.10242.graph.info.part.'
/
```

Descrição dos campos principais:

| Campo | Função |
|---|---|
| `config_init_case = 7` | usa dados intermediários do WPS/met como fonte meteorológica |
| `config_start_time` | horário da análise GFS usada na inicialização |
| `config_stop_time` | igual ao `config_start_time` neste workflow |
| `config_nvertlevels` | número de níveis verticais da malha/modelo |
| `config_met_prefix = 'FILE'` | prefixo dos arquivos WPS |
| `config_sfc_prefix = 'FILE'` | prefixo dos campos de superfície |
| `config_static_interp = .false.` | evita interpolação estática porque já se usa `invariant` da malha |
| `config_vertical_grid = .true.` | gera a estrutura vertical |
| `config_met_interp = .true.` | interpola os campos meteorológicos para a malha MPAS |
| `config_block_decomp_file_prefix` | prefixo da decomposição MPI da malha |

### 4.6 `streams.init_atmosphere`

O `streams.init_atmosphere` precisa apontar para a malha correta e para o arquivo de saída correto.

O workflow corrige referências herdadas de templates, como:

```text
x1.40962.grid.nc
x1.40962.init.nc
```

para:

```text
x1.10242.grid.nc
x1.10242.init.YYYY-MM-DD_HH.MM.SS.nc
```

Também força `clobber_mode="overwrite"` quando necessário, para que uma reexecução não falhe por arquivos antigos.

Um trecho esperado é:

```xml
<immutable_stream name="input"
                  type="input"
                  filename_template="x1.10242.grid.nc"
                  input_interval="initial_only" />

<immutable_stream name="output"
                  type="output"
                  filename_template="x1.10242.init.YYYY-MM-DD_HH.MM.SS.nc"
                  packages="initial_conds"
                  output_interval="initial_only"
                  clobber_mode="overwrite" />
```

### 4.7 Validação antes do PBS

Antes de submeter o job, o workflow verifica:

- se `mpas_init_atmosphere` existe no diretório de execução;
- se `x1.10242.grid.nc` existe;
- se o arquivo WPS `FILE:YYYY-MM-DD_HH` existe;
- se `graph.info` e `part.64` existem;
- se `namelist.init_atmosphere` existe;
- se `streams.init_atmosphere` existe;
- se `run_mpas_init.pbs` existe;
- se o `streams` contém a malha correta;
- se o `streams` contém o nome de saída esperado;
- se não há referências residuais a outra malha, como `x1.40962`;
- se não há `clobber_mode="never_modify"`.

### 4.8 PBS do init

O PBS do init é gerado automaticamente com:

```bash
#PBS -N mpas_init_x1.10242
#PBS -q pesqmini
#PBS -l select=1:ncpus=64:mpiprocs=64
#PBS -l walltime=00:10:00
#PBS -j oe
```

O comando principal dentro do job é:

```bash
mpiexec -n 64 ./mpas_init_atmosphere > stdout.log 2> stderr.log
```

### 4.9 Saídas esperadas

| Saída | Função |
|---|---|
| `x1.10242.init.YYYY-MM-DD_HH.MM.SS.nc` | condição inicial MPAS |
| `log.init_atmosphere.0000.out` | log principal do rank 0 |
| `stdout.log` | stdout do `mpiexec` |
| `stderr.log` | stderr do `mpiexec` |

A condição inicial só é aceita se:

- o arquivo `init.nc` esperado existir;
- o log existir;
- `Critical error messages = 0`;
- `Error messages = 0`.

### 4.10 Comandos isolados

Preparar:

```bash
mpaswf --config configs/jaci-x1.10242.yaml init prepare \
  --init-time 2026-06-09_00:00:00
```

Submeter:

```bash
mpaswf --config configs/jaci-x1.10242.yaml init submit \
  --init-time 2026-06-09_00:00:00
```

Validar:

```bash
mpaswf --config configs/jaci-x1.10242.yaml init validate \
  --init-time 2026-06-09_00:00:00
```

---

## 5. Etapa 3: execução dos forecasts MPAS

### 5.1 Objetivo

Executar o `mpas_atmosphere` a partir de uma condição inicial MPAS para gerar arquivos `restart` nos horários de interesse.

No método NMC usado aqui, são necessários dois forecasts:

| Forecast | Inicialização | Duração | Saída usada |
|---|---|---:|---|
| `f048` | `OLD_INIT_TIME` | 48 h | `restart` em `VALID_TIME` |
| `f024` | `NEW_INIT_TIME` | 24 h | `restart` em `VALID_TIME` |

### 5.2 Entradas necessárias

| Entrada | Origem |
|---|---|
| `mpas_atmosphere` | `install.mpas_atmosphere` |
| `init.nc` | condição inicial gerada pelo `mpas_init_atmosphere` |
| `x1.10242.invariant.nc` | `static.invariant` |
| `x1.10242.grid.nc` | `mesh.grid` |
| `x1.10242.graph.info` | `mesh.graph` |
| `x1.10242.graph.info.part.64` | `mesh.partitions_dir` |
| arquivos auxiliares do core atmosphere | `install.atmosphere_share` |
| `namelist.atmosphere` | gerado pelo workflow |
| `streams.atmosphere` | gerado pelo workflow |
| `run_mpas_forecast.pbs` | gerado pelo workflow |

### 5.3 Diretório de execução

O diretório de forecast segue o padrão:

```text
${work_root}/runs/forecast_${mesh_name}_${INIT_TIME_SAFE}_f${LEAD}_dt${DT}_np${NPROC}
```

Exemplo f048:

```text
/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/runs/forecast_x1.10242_2026-06-08_00.00.00_f048_dt60_np64
```

Exemplo f024:

```text
/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/runs/forecast_x1.10242_2026-06-09_00.00.00_f024_dt60_np64
```

### 5.4 Campos importantes do `namelist.atmosphere`

O workflow modifica automaticamente:

```fortran
config_dt = 60
config_start_time = 'YYYY-MM-DD_HH:00:00'
config_run_duration = 'D_HH:MM:SS'
config_do_restart = .false.
config_block_decomp_file_prefix = 'x1.10242.graph.info.part.'
config_sst_update = .false.
config_sstdiurn_update = .false.
config_deepsoiltemp_update = .false.
config_do_DAcycling = .false.
```

Descrição:

| Campo | Função |
|---|---|
| `config_dt` | passo de tempo em segundos |
| `config_start_time` | tempo inicial do forecast |
| `config_run_duration` | duração total da previsão |
| `config_do_restart = .false.` | forecast inicia de `init.nc`, não de um restart anterior |
| `config_block_decomp_file_prefix` | prefixo da decomposição MPI |
| `config_sst_update = .false.` | desativa atualização de SST durante o forecast |
| `config_sstdiurn_update = .false.` | desativa atualização diurna de SST |
| `config_deepsoiltemp_update = .false.` | desativa atualização de temperatura profunda do solo |
| `config_do_DAcycling = .false.` | desativa modo de ciclo de assimilação |

Duração esperada:

```text
f024 -> config_run_duration = '1_00:00:00'
f048 -> config_run_duration = '2_00:00:00'
```

### 5.5 `streams.atmosphere`

O workflow gera um `streams.atmosphere` explícito, em vez de depender cegamente do template instalado.

Entradas:

```xml
<immutable_stream name="invariant"
                  type="input"
                  filename_template="x1.10242.invariant.nc"
                  input_interval="initial_only" />

<immutable_stream name="input"
                  type="input"
                  filename_template="init.nc"
                  input_interval="initial_only" />
```

Saídas:

```xml
<stream name="restart"
        type="output"
        filename_template="restart.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="24:00:00"
        clobber_mode="overwrite" />

<stream name="output"
        type="output"
        filename_template="history.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="24:00:00"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.output" />

<stream name="diagnostics"
        type="output"
        filename_template="diagnostics.$Y-$M-$D_$h.$m.$s.nc"
        filename_interval="output_interval"
        output_interval="24:00:00"
        clobber_mode="overwrite"
        contents="stream_list.atmosphere.diagnostics" />
```

O arquivo mais importante para o método NMC é o `restart` no horário válido.

### 5.6 PBS do forecast

O PBS do forecast é gerado automaticamente. Para `pesqmini`, o YAML atual usa:

```yaml
walltime:
  forecast:
    f024: "00:30:00"
    f048: "00:30:00"
```

Exemplo de diretivas:

```bash
#PBS -N mpas_f048_x1.10242
#PBS -q pesqmini
#PBS -l select=1:ncpus=64:mpiprocs=64
#PBS -l walltime=00:30:00
#PBS -j oe
```

O comando principal é:

```bash
mpiexec -n 64 ./mpas_atmosphere > stdout.log 2> stderr.log
```

### 5.7 Saída esperada

Para um forecast f048 iniciado em `2026-06-08_00:00:00`, a saída usada no par NMC válido em `2026-06-10_00:00:00` é:

```text
restart.2026-06-10_00.00.00.nc
```

Para um forecast f024 iniciado em `2026-06-09_00:00:00`, a saída usada no mesmo par é:

```text
restart.2026-06-10_00.00.00.nc
```

Ambos possuem o mesmo horário válido, mas vêm de inicializações diferentes.

### 5.8 Validação antes do PBS

Antes de submeter o forecast, o workflow verifica:

- se `mpas_atmosphere` existe;
- se `init.nc` existe;
- se `x1.10242.invariant.nc` existe;
- se `x1.10242.grid.nc` existe;
- se `graph.info` e `part.64` existem;
- se `namelist.atmosphere` existe;
- se `streams.atmosphere` existe;
- se `run_mpas_forecast.pbs` existe;
- se o `namelist` contém o `config_dt`, `config_start_time`, `config_run_duration` e decomposição esperados;
- se o `streams` contém `init.nc`, `x1.10242.invariant.nc`, stream `restart` e `clobber_mode="overwrite"`;
- se o PBS contém diretiva `walltime`.

### 5.9 Comando isolado

```bash
mpaswf --config configs/jaci-x1.10242.yaml cycle run \
  --init-time 2026-06-09_00:00:00 \
  --lead-hours 24 \
  --dt 60 \
  --submit \
  --wait
```

---

## 6. Etapa 4: montagem do par NMC

### 6.1 Objetivo

Montar, em um diretório único, os dois estados MPAS que serão comparados:

```text
f048.nc
f024.nc
```

Esses arquivos são links simbólicos para os `restart` gerados nas etapas anteriores.

### 6.2 Entradas necessárias

Para um `VALID_TIME`, o workflow procura:

```text
forecast_${mesh}_${OLD_INIT_TIME}_f048_dt${DT}_np${NPROC}/restart.${VALID_TIME}.nc
forecast_${mesh}_${NEW_INIT_TIME}_f024_dt${DT}_np${NPROC}/restart.${VALID_TIME}.nc
```

Exemplo:

```text
OLD_INIT_TIME = 2026-06-08_00:00:00
NEW_INIT_TIME = 2026-06-09_00:00:00
VALID_TIME    = 2026-06-10_00:00:00
```

Arquivos esperados:

```text
runs/forecast_x1.10242_2026-06-08_00.00.00_f048_dt60_np64/restart.2026-06-10_00.00.00.nc
runs/forecast_x1.10242_2026-06-09_00.00.00_f024_dt60_np64/restart.2026-06-10_00.00.00.nc
```

### 6.3 Diretório de saída

O par é montado em:

```text
${work_root}/nmc_pairs/nmc_${mesh_name}_valid_${VALID_TIME_SAFE}
```

Exemplo:

```text
/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/nmc_pairs/nmc_x1.10242_valid_2026-06-10_00.00.00
```

### 6.4 Arquivos gerados

| Arquivo | Função |
|---|---|
| `f048.nc` | link para forecast antigo de 48 h |
| `f024.nc` | link para forecast novo de 24 h |
| `pair.env` | metadados do par em formato shell |
| `README.md` | descrição curta do par |

### 6.5 Conteúdo do `pair.env`

Exemplo:

```bash
MESH_NAME=x1.10242
CONFIG_DT=60
OLD_INIT_TIME=2026-06-08_00:00:00
NEW_INIT_TIME=2026-06-09_00:00:00
VALID_TIME=2026-06-10_00:00:00
F048=/p/projetos/.../nmc_pairs/.../f048.nc
F024=/p/projetos/.../nmc_pairs/.../f024.nc
```

---

## 7. Etapa 5: validação estrutural do par NMC

### 7.1 Objetivo

Verificar se `f048.nc` e `f024.nc` são estruturalmente compatíveis antes de calcular a diferença.

### 7.2 Verificações feitas

O workflow usa `ncdump -h` para verificar dimensões e variáveis.

Dimensões obrigatórias:

```text
Time
nCells
nEdges
nVertices
nVertLevels
```

Variáveis obrigatórias:

```text
u
rho
theta
qv
```

Também verifica se variáveis comuns possuem as mesmas dimensões nos dois arquivos.

### 7.3 Saída esperada

Quando o par está correto:

```text
SUCCESS: par NMC estruturalmente consistente.
```

Se houver erro, o workflow interrompe antes de gerar a diferença.

### 7.4 Comando isolado

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc validate \
  --valid-time 2026-06-10_00:00:00
```

---

## 8. Etapa 6: geração da diferença NMC

### 8.1 Objetivo

Gerar um arquivo NetCDF contendo a diferença:

```text
f048 - f024
```

Essa diferença representa uma perturbação NMC para o horário válido.

### 8.2 Entrada

O comando usa:

```text
f048.nc
f024.nc
```

no diretório do par NMC.

### 8.3 Variáveis usadas

Por padrão, o workflow tenta gerar diferenças para variáveis como:

```text
u
w
rho
theta
qv
qc
qr
qi
qs
qg
pressure
pressure_p
surface_pressure
temperature
air_temperature
water_vapor_mixing_ratio_wrt_moist_air
water_vapor_mixing_ratio_wrt_dry_air
```

Só são processadas variáveis que existem nos dois arquivos e possuem as mesmas dimensões.

### 8.4 Saída

A saída padrão é:

```text
nmc_diff_f048_minus_f024.nc
```

Esse arquivo recebe atributos globais indicando:

```text
nmc_difference = f048_minus_f024
source_f048 = caminho absoluto do f048.nc
source_f024 = caminho absoluto do f024.nc
valid_time = VALID_TIME
nmc_variables = lista de variáveis processadas
```

### 8.5 Comando isolado

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc diff \
  --valid-time 2026-06-10_00:00:00
```

Para limitar variáveis:

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc diff \
  --valid-time 2026-06-10_00:00:00 \
  --variables u,rho,theta,qv
```

---

## 9. Etapa 7: execução automática para um intervalo de pares

### 9.1 Objetivo

Automatizar a geração de vários pares NMC consecutivos.

O comando:

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc range \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time   2026-06-12_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --submit \
  --wait \
  --poll-seconds 30 \
  --diff
```

produz três horários válidos:

```text
2026-06-10_00:00:00
2026-06-11_00:00:00
2026-06-12_00:00:00
```

Para cada horário válido, calcula automaticamente:

```text
OLD_INIT_TIME = VALID_TIME - 48 h
NEW_INIT_TIME = VALID_TIME - 24 h
```

### 9.2 Comportamento com `--submit`

Com `--submit`, o workflow submete automaticamente jobs PBS para etapas que ainda não possuem saída válida.

### 9.3 Comportamento com `--wait`

Com `--wait`, o workflow monitora o job com `qstat` e continua automaticamente quando o job sai da fila.

Exemplo de mensagem:

```text
Aguardando job PBS terminar: 266138.pbs-ha
Ainda aguardando PBS job 266138.pbs-ha | elapsed=00:30 | ... R pesqmini
Job PBS saiu do qstat: 266138.pbs-ha | elapsed=01:00
```

### 9.4 Reaproveitamento de resultados

Antes de refazer uma etapa, o workflow verifica se a saída já existe e é válida.

Exemplos:

- se o `init.nc` já existe e o log terminou sem erros, ele é reutilizado;
- se o `restart` esperado já existe, o forecast é reutilizado;
- se o par NMC já existe, pode ser validado e usado para gerar a diferença.

### 9.5 Reexecução idempotente

Quando uma etapa precisa ser refeita, o workflow remove arquivos antigos gerados pela própria etapa, como:

- logs anteriores;
- arquivos de saída parciais;
- arquivos `x1.*.init*.nc` obsoletos;
- arquivos `restart`, `history` e `diagnostics` antigos no caso de forecast.

Isso reduz o risco de um erro antigo contaminar uma execução nova.

---

## 10. Etapa 8: uso das perturbações no cálculo da matriz B

### 10.1 O que já está sendo produzido

Ao fim das etapas anteriores, o workflow terá uma coleção de arquivos:

```text
nmc_diff_f048_minus_f024.nc
```

um para cada horário válido.

Esses arquivos representam amostras de erro de previsão segundo a ideia NMC.

### 10.2 Interpretação física

A diferença `f048 - f024`, válida no mesmo horário, é usada como proxy de erro de previsão. A partir de muitos pares, é possível estimar estatísticas de covariância entre variáveis, níveis e pontos da malha.

Em termos práticos:

```text
perturbação_i = forecast_48h_i - forecast_24h_i
```

A matriz B representa estatisticamente a covariância dessas perturbações.

### 10.3 Quantidade de pares

Para teste técnico de workflow:

```text
1 par
```

Para teste funcional inicial:

```text
3 a 5 pares
```

Para estatística preliminar:

```text
10 a 20 pares
```

Para uma matriz B robusta, será necessário usar uma amostra muito maior, cobrindo diferentes dias, horários e condições atmosféricas.

### 10.4 Próximas etapas esperadas no pacote

O pacote ainda deve evoluir para incluir comandos como:

```bash
mpaswf bmatrix stats
mpaswf bmatrix prepare
mpaswf bmatrix run
```

Função esperada de cada comando:

| Comando | Função |
|---|---|
| `bmatrix stats` | calcular estatísticas básicas das perturbações NMC |
| `bmatrix prepare` | montar diretório/YAML de entrada do `mpasjedi_error_covariance_toolbox.x` |
| `bmatrix run` | submeter ou executar o cálculo da matriz B |

### 10.5 Validação antes de calcular B

Antes de usar os arquivos no `mpasjedi_error_covariance_toolbox.x`, recomenda-se verificar:

- número de pares disponíveis;
- consistência de dimensões entre todos os arquivos;
- presença das variáveis esperadas;
- ausência de valores absurdos, NaN ou infinitos;
- estatísticas mínimas por variável, como mínimo, máximo, média, desvio padrão e RMS;
- compatibilidade entre nomes de variáveis MPAS e nomes esperados pelo MPAS-JEDI/SABER.

---

## 11. Filas PBS e política JACI

O workflow deve respeitar os limites das filas JACI. O guia operacional está documentado em:

```text
docs/jaci-operational-guide.md
```

Resumo das filas de pesquisa:

| Fila | Tempo máximo | Uso recomendado |
|---|---:|---|
| `pesqmini` | 00:30:00 | smoke tests e validações rápidas |
| `pesqmidi` | 02:00:00 | jobs médios |
| `pesqhigh` | 06:00:00 | simulações mais longas/importantes |
| `pesqextra` | 08:00:00 | processamento extenso |

Para o workflow atual, a configuração de teste usa:

```yaml
pbs:
  queue: pesqmini
  walltime:
    init: "00:10:00"
    forecast:
      f024: "00:30:00"
      f048: "00:30:00"
```

Se o forecast f048 não couber em `pesqmini`, deve-se mudar para `pesqmidi` ou outra fila compatível.

---

## 12. Checklist operacional do workflow

### 12.1 Antes de rodar

Verifique:

- [ ] repositório em `/p`;
- [ ] `data_root` em `/p`;
- [ ] `work_root` em `/p`;
- [ ] executáveis `mpas_init_atmosphere` e `mpas_atmosphere` existem;
- [ ] WPS existe e possui `ungrib.exe`, `link_grib.csh` e `Vtable.GFS`;
- [ ] arquivo `x1.10242.invariant.nc` existe;
- [ ] arquivo `x1.10242.grid.nc` existe;
- [ ] arquivo `x1.10242.graph.info` existe;
- [ ] partição `x1.10242.graph.info.part.64` existe;
- [ ] `config_dt` está coerente com a malha;
- [ ] fila e walltime são compatíveis com a duração esperada;
- [ ] ambiente JACI é carregado pelo `scripts/load_jaci_env.sh`.

### 12.2 Durante a execução

Monitorar:

```bash
qstat -u $USER
```

Ver logs de init:

```bash
tail -120 ${RUN_DIR}/log.init_atmosphere.0000.out
tail -120 ${RUN_DIR}/stderr.log
```

Ver logs de forecast:

```bash
tail -120 ${RUN_DIR}/log.atmosphere.0000.out
tail -120 ${RUN_DIR}/stderr.log
```

### 12.3 Depois da execução

Verificar pares:

```bash
find /p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/nmc_pairs \
  -name 'nmc_diff_f048_minus_f024.nc' \
  -print
```

Validar um par:

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc validate \
  --valid-time 2026-06-10_00:00:00
```

---

## 13. Diagnóstico de problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `namelist.wps` ausente | diretório WPS preparado incorretamente | usar `mpaswf ungrib`; o workflow gera o namelist automaticamente |
| `FILE:YYYY-MM-DD_HH` ausente | `ungrib` falhou ou GRIB não foi baixado | verificar GRIB, `Vtable.GFS` e log do `ungrib` |
| `x1.40962.grid.nc` aparece no log | template de `streams.init_atmosphere` não foi corrigido | refazer `prepare_init` com versão atual do pacote |
| `x1.40962.init.nc` aparece no log | saída antiga do template não foi corrigida | refazer `prepare_init`; preflight deve bloquear isso |
| `clobber_mode=never_modify` impede saída | arquivo antigo existe e stream não permite sobrescrever | usar versão atual, que troca para `overwrite` |
| `init.nc não encontrado` | `mpas_init` não gerou a saída esperada | olhar `log.init_atmosphere.0000.out` e `stderr.log` |
| `qsub` falha com código 188 | fila/walltime/recurso incompatível | conferir `STDERR` do `qsub` e ajustar `pbs.queue`/`walltime` |
| forecast não gera `restart` | modelo falhou, tempo insuficiente ou `config_dt` inadequado | olhar `log.atmosphere.0000.out`, `stderr.log` e usar `config_dt=60` |
| par NMC inválido | `f048` e `f024` têm dimensões/variáveis incompatíveis | validar arquivos com `ncdump -h` e `mpaswf nmc validate` |

---

## 14. Comandos principais

Gerar três pares NMC com espera automática:

```bash
mpaswf \
  --config configs/jaci-x1.10242.yaml \
  nmc range \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time   2026-06-12_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --submit \
  --wait \
  --poll-seconds 30 \
  --diff
```

Gerar apenas um par:

```bash
mpaswf \
  --config configs/jaci-x1.10242.yaml \
  nmc one-pair \
  --old-init-time 2026-06-10_00:00:00 \
  --new-init-time 2026-06-11_00:00:00 \
  --valid-time 2026-06-12_00:00:00 \
  --dt 60 \
  --submit \
  --wait \
  --diff
```

Validar par:

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc validate \
  --valid-time 2026-06-12_00:00:00
```

Gerar diferença:

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc diff \
  --valid-time 2026-06-12_00:00:00
```

---

## 15. Organização dos módulos Python

| Módulo | Responsabilidade |
|---|---|
| `config.py` | carregar YAML, expandir variáveis de ambiente e formatar datas |
| `wps.py` | baixar GFS, preparar e executar `ungrib` |
| `mpas_init.py` | preparar, submeter e validar condições iniciais MPAS |
| `forecast.py` | preparar, submeter e validar estrutura dos forecasts MPAS |
| `nmc.py` | montar pares NMC, validar dimensões/variáveis e gerar diferenças |
| `pbs.py` | gerar scripts PBS para init e forecast |
| `shell.py` | utilitários de shell, links, `qsub`, `qstat` e espera de jobs |
| `doctor.py` | auditoria de ambiente, configuração e status dos arquivos |
| `cli.py` | interface de linha de comando `mpaswf` |

---

## 16. Estado atual e próximos passos

O sistema atual já cobre:

- download/reuso do GFS;
- geração WPS `FILE:*`;
- geração de condição inicial MPAS;
- execução de forecast MPAS;
- montagem de pares NMC;
- validação estrutural dos pares;
- geração de diferenças NetCDF `f048 - f024`;
- submissão PBS com espera automática;
- preflight para evitar submissões inconsistentes.

Próximas melhorias recomendadas:

1. adicionar comando `mpaswf doctor` diretamente ao CLI principal;
2. adicionar comando `mpaswf bmatrix stats`;
3. adicionar comando `mpaswf bmatrix prepare`;
4. adicionar template YAML para `mpasjedi_error_covariance_toolbox.x`;
5. registrar uma tabela de experimentos NMC com pares disponíveis, variáveis e estatísticas;
6. permitir escolha automática de fila conforme walltime estimado;
7. permitir reaproveitamento de `restart` f024 gerado dentro de um forecast f048, quando aplicável.
