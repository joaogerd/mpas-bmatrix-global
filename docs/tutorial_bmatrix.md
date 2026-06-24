# Tutorial completo para geração da matriz B global MPAS-JEDI no JACI

## 1. Objetivo do tutorial

Este tutorial descreve o processo completo para gerar, calibrar, validar e organizar uma matriz B estática global para uso no MPAS-JEDI/SABER, usando o repositório:

```bash
/p/projetos/monan_das/${USER}/projects/mpas-bmatrix-global
```

A matriz B representa a covariância dos erros do background. Em um sistema variacional, ela controla como a informação das observações se espalha:

```text
no espaço horizontal
na vertical
entre diferentes variáveis
com determinada amplitude estatística
```

No MPAS-JEDI/SABER, a B não é gerada como uma matriz densa única. Ela é representada por um conjunto de operadores e arquivos:

```text
B ≈ C2A · VBAL · StdDev · NICAS · StdDev · VBALᵀ · C2Aᵀ
```

onde:

```text
NICAS   representa a estrutura de correlação espacial
StdDev  representa a amplitude dos erros
VBAL    representa o balanço vertical e multivariado
C2A     representa a transformação Control2Analysis
```

O workflow completo possui estas etapas:

```text
BFLOW  -> preparação das amostras NMC
VBAL   -> calibração do balanço vertical e multivariado
HDIAG  -> cálculo de desvio padrão e escalas de correlação
NICAS  -> construção da correlação/localização
SO     -> teste de observação única
DIRAC  -> resposta da B completa a um impulso
```

---

## 2. Criação e instalação do ambiente Python `mpaswf`

### 2.1. Por que o ambiente `mpaswf` é necessário?

O repositório `mpas-bmatrix-global` contém ferramentas Python para preparar diretórios de trabalho, gerar YAMLs do JEDI/SABER, gerar scripts PBS, submeter jobs, validar saídas e criar diagnósticos.

Essas ferramentas precisam de um ambiente Python com bibliotecas como:

```text
PyYAML
numpy
netCDF4
cftime
xarray
```

Além disso, a instalação do pacote cria comandos de linha de comando, como:

```text
mpaswf
mpasbflow
mpasbcov
```

Esses comandos são usados ao longo do tutorial.

### 2.2. Criar e preparar o ambiente Conda

No JACI, carregue o módulo do Anaconda e inicialize o ambiente Conda:

```bash
module load anaconda
start_conda
```

Em seguida, crie o ambiente `mpaswf` com Python 3.11:

```bash
conda create -n mpaswf python=3.11 -y
```

Ative o ambiente criado:

```bash
conda activate mpaswf
```

Por fim, atualize o `pip` e instale as dependências Python necessárias:

```bash
python -m pip install --upgrade pip

python -m pip install \
  PyYAML \
  numpy \
  netCDF4 \
  cftime \
  xarray \
  matplotlib
```

> Nas próximas sessões, basta carregar o módulo, executar `start_conda` e ativar novamente o ambiente:
>
> ```bash
> module load anaconda
> start_conda
> conda activate mpaswf
> ```

A dependência `matplotlib` é necessária para os diagnósticos gráficos, mesmo que não esteja listada como dependência obrigatória principal no `pyproject.toml`.

### 2.3. Instalar o repositório

Entre no repositório:

```bash
cd /p/projetos/monan_das/${USER}/projects/mpas-bmatrix-global
```

Carregue o ambiente JACI:

```bash
source scripts/load_jaci_env.sh
```

Instale a ferramenta em modo editável:

```bash
python -m pip install -e .
```

Esse modo é recomendado durante o desenvolvimento porque alterações feitas no código passam a ser usadas imediatamente pelo ambiente.

### 2.4. Verificar instalação

Confira se os comandos foram instalados:

```bash
mpaswf --help
mpasbflow --help
mpasbcov --help
```

Resultado esperado:

```text
os três comandos devem imprimir suas opções de uso
não deve aparecer erro de comando não encontrado
```

---
## 3. Instalação e validação do WPS/ungrib

### 3.1. Por que o WPS é necessário?

Antes de gerar a matriz B, é necessário gerar amostras NMC. Essas amostras dependem de previsões MPAS iniciadas a partir de condições iniciais consistentes.

Quando a fonte meteorológica usada é GFS em formato GRIB, é necessário passar por uma etapa de pré-processamento com WPS, principalmente com o programa:

```text id="jz1q41"
ungrib.exe
```

O `ungrib.exe` lê os arquivos GRIB do GFS e os converte para arquivos intermediários que podem ser usados na preparação das condições iniciais do MPAS.

Portanto, o WPS não faz parte diretamente da matriz B, mas ele é necessário antes do BFLOW quando as amostras NMC serão geradas a partir de previsões MPAS inicializadas com GFS.

A sequência conceitual fica assim:

```text id="y53zis"
GFS GRIB
  -> WPS/ungrib
  -> arquivos intermediários meteorológicos
  -> MPAS init_atmosphere
  -> condições iniciais MPAS
  -> previsões f24 e f48
  -> diferenças NMC
  -> BFLOW
  -> VBAL/HDIAG/NICAS/SO/DIRAC
```

### 3.2. Configuração esperada do WPS

No arquivo:

```bash id="di2162"
configs/jaci-x1.10242.yaml
```

deve existir o bloco:

```yaml id="48lmxa"
wps:
  root: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
  ungrib_exe: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/ungrib.exe
  link_grib: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/link_grib.csh
  vtable_gfs: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/ungrib/Variable_Tables/Vtable.GFS
```

Esses caminhos significam:

```text id="np57xk"
root
  diretório de instalação/código-fonte do WPS

ungrib_exe
  executável que converte GRIB para arquivos intermediários

link_grib
  script do WPS que cria links GRIBFILE.AAA, GRIBFILE.AAB, ...

vtable_gfs
  tabela que informa ao ungrib como interpretar as variáveis do GFS
```

### 3.3. Onde o WPS deve estar instalado?

O diretório esperado é:

```bash id="d5esxi"
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

Dentro dele devem existir, ao final da instalação:

```text id="x7v5uf"
ungrib.exe
link_grib.csh
ungrib/Variable_Tables/Vtable.GFS
```

O arquivo mais importante para o workflow é:

```bash id="nj85h4"
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/ungrib.exe
```

### 3.4. Verificar se o WPS já está instalado

Antes de compilar, verifique:

```bash id="vp9qqf"
WPS_ROOT=/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0

ls -lh "$WPS_ROOT"
ls -lh "$WPS_ROOT/ungrib.exe"
ls -lh "$WPS_ROOT/link_grib.csh"
ls -lh "$WPS_ROOT/ungrib/Variable_Tables/Vtable.GFS"
```

Se `ungrib.exe` existir e for executável, a etapa de instalação do WPS já está pronta:

```bash id="vvsoqe"
test -x "$WPS_ROOT/ungrib.exe" && echo "OK: ungrib.exe executável"
```

### 3.5. Baixar ou preparar o código-fonte do WPS

O código-fonte do WPS deve estar em:

```bash id="j2mxo4"
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

Caso o diretório não exista, é necessário baixar/preparar o WPS antes de compilar.

No repositório, o script de build informa que, se o diretório do WPS não existir, primeiro deve ser executada a etapa de download/preparação dos assets do WPS.

Verifique se existe um script legado para isso:

```bash id="m2c45g"
ls -lh scripts/legacy/*wps* scripts/legacy/*WPS* 2>/dev/null
```

Depois rode o script apropriado de download/preparação, se ele existir no repositório. Em algumas versões do repositório, essa etapa foi chamada de:

```bash id="panqtv"
scripts/legacy/10_download_wps_assets.sh
```

Se esse script não existir na versão atual, o WPS deve ser obtido manualmente ou copiado de uma instalação já preparada para:

```bash id="x8l6yh"
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

### 3.6. Compilar o `ungrib.exe`

Entre no repositório:

```bash id="8w9rhs"
cd /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
```

Carregue o ambiente JACI:

```bash id="z455bp"
source scripts/load_jaci_env.sh
```

Ative o ambiente Python, se necessário:

```bash id="mnjref"
conda activate mpaswf
```

Rode a compilação:

```bash id="twl2wb"
bash scripts/legacy/12_build_wps_ungrib.sh \
  | tee logs/12_build_wps_ungrib.log
```

Se quiser forçar recompilação:

```bash id="asfn1k"
FORCE_WPS_REBUILD=true \
bash scripts/legacy/12_build_wps_ungrib.sh \
  | tee logs/12_build_wps_ungrib_rebuild.log
```

### 3.7. O que o script de build faz?

O script `scripts/legacy/12_build_wps_ungrib.sh` executa as seguintes ações:

```text id="v23415"
1. verifica se o diretório do WPS existe
2. verifica comandos necessários como nc-config, nf-config, make, perl e csh
3. cria um prefixo NetCDF compatível com o WPS
4. detecta dependências GRIB2, como JasPer, PNG e ZLIB
5. configura o WPS com --nowrf
6. ajusta configure.wps para usar os wrappers Cray ftn e cc
7. compila somente o ungrib.exe
8. verifica se ungrib.exe foi criado
```

O prefixo NetCDF compatível é necessário porque o ambiente JACI possui `netcdf-c` e `netcdf-fortran` em prefixos separados, enquanto o WPS espera uma única variável `NETCDF`.

### 3.8. Resultado esperado

Ao final, deve existir:

```bash id="czf1da"
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/ungrib.exe
```

Verifique:

```bash id="k1gi5l"
WPS_ROOT=/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0

ls -lh "$WPS_ROOT/ungrib.exe"
file "$WPS_ROOT/ungrib.exe"
ldd "$WPS_ROOT/ungrib.exe" | grep -Ei "not found|netcdf|jasper|png|zlib|hdf5|curl|gcc|gfortran|mpi|fabric" || true
```

O resultado esperado é:

```text id="mdf21t"
ungrib.exe existe
ungrib.exe é executável
ldd não mostra bibliotecas obrigatórias como "not found"
```

### 3.9. Teste mínimo do `ungrib.exe`

Rode:

```bash id="33j5fi"
"$WPS_ROOT/ungrib.exe" 2>&1 | head -40
```

É normal que ele reclame da ausência de `namelist.wps` se for executado fora de um diretório preparado. O objetivo desse teste simples é verificar se o executável inicia e não falha imediatamente por biblioteca ausente.

### 3.10. Arquivos do WPS usados depois

Depois da instalação, o workflow usa:

```text id="m610h8"
ungrib.exe
  para converter GRIB em arquivos intermediários

link_grib.csh
  para criar links GRIBFILE.* no diretório de execução do ungrib

Vtable.GFS
  para informar ao ungrib como interpretar os campos do GFS
```

Esses arquivos não são produtos da matriz B. Eles são pré-requisitos para preparar os dados atmosféricos que serão usados para gerar as condições iniciais e as previsões MPAS.

### 3.11. Relação com o BFLOW

O WPS deve estar pronto antes da etapa NMC/BFLOW quando as amostras forem geradas a partir do GFS.

A relação é:

```text id="og4vvc"
WPS/ungrib gera entrada meteorológica para o MPAS
MPAS init gera condição inicial
MPAS atmosphere gera previsões f24 e f48
NMC calcula PTB_f48mf24
BFLOW organiza essas amostras
VBAL/HDIAG/NICAS usam essas amostras para calibrar a B
```

Portanto, a etapa WPS deve aparecer no tutorial antes de:

```text id="zq1p3g"
gerar amostras NMC
preparar BFLOW
rodar VBAL
```

### 3.12. Problemas comuns

#### 3.12.1. `WPS source directory not found`

Significa que o diretório abaixo ainda não existe:

```bash id="agv0o8"
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

Solução: baixar/copiar o WPS para esse caminho antes da compilação.

#### 3.12.2. `required command not found`

Significa que algum comando necessário não está disponível no ambiente, por exemplo:

```text id="ao829p"
nc-config
nf-config
make
perl
csh
```

Solução: carregar o ambiente JACI correto com:

```bash id="kmgu2j"
source scripts/load_jaci_env.sh
```

#### 3.12.3. dependência GRIB2 ausente

Se aparecer erro relacionado a JasPer, PNG ou ZLIB, o script não encontrou uma das dependências necessárias para GRIB2.

Nesse caso, informe explicitamente os caminhos:

```bash id="d6h575"
JASPERINC=/caminho/include \
JASPERLIB=/caminho/lib \
PNG_INC=/caminho/include \
PNG_LIB=/caminho/lib \
ZLIB_INC=/caminho/include \
ZLIB_LIB=/caminho/lib \
bash scripts/legacy/12_build_wps_ungrib.sh
```

#### 3.12.4. `ungrib.exe was not created`

Verifique o log:

```bash id="y58r59"
tail -120 logs/12_wps_compile_ungrib.log
```

Esse log mostra o erro real de compilação.


## 4. Configuração principal do workflow

A configuração principal usada neste tutorial é:

```bash
configs/jaci-x1.10242.yaml
```

Ela define os principais caminhos do projeto:

```text
project_root = /p/projetos/monan_das/${USER}/projects/mpas-bmatrix-global
data_root    = /p/projetos/monan_das/${USER}/data/mpas-bmatrix-global
work_root    = /p/projetos/monan_das/${USER}/work/mpas-bmatrix-global
```

Também define a malha:

```text
mesh name    = x1.10242
nproc        = 128
nvertlevels  = 55
```

E define os executáveis necessários:

```text
mpas_init_atmosphere
mpas_atmosphere
mpasjedi_error_covariance_toolbox.x
mpasjedi_variational.x
```

Esses executáveis ficam em:

```bash
/p/projetos/monan_das/${USER}/builds/monan-jedi-mpas/bin
```

---

## 5. Arquivos necessários antes da rodada

Esta seção é uma das mais importantes. Nem tudo é gerado pelo workflow. Alguns arquivos precisam existir antes da execução.

A configuração atual espera os arquivos nos caminhos definidos em `configs/jaci-x1.10242.yaml`.

---

### 5.1. Arquivos da malha MPAS

#### 5.1.1. `x1.10242.grid.nc`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/mesh/x1.10242.grid.nc
```

Esse arquivo representa a malha MPAS propriamente dita. Ele contém informações de células, arestas, vértices e conectividade da malha.

Ele deve existir antes da rodada.

Origem esperada:

```text
malhas MPAS baixadas/preparadas previamente
```

Não é gerado pelo workflow da B.

---

#### 5.1.2. `x1.10242.graph.info`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/graph/x1.10242.graph.info
```

Esse arquivo descreve o grafo da malha MPAS. Ele é usado para particionamento MPI.

Ele deve existir antes da rodada.

Não é gerado pelas etapas VBAL, HDIAG, NICAS, SO ou DIRAC.

---

#### 5.1.3. `x1.10242.graph.info.part.128`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/partitions/x1.10242.graph.info.part.128
```

Esse arquivo é a partição da malha para 128 processos MPI.

Ele deve existir antes das etapas de B, porque o workflow está configurado para `nproc: 128`.

Origem:

```text
gerado previamente com gpmetis ou ferramenta equivalente
```

Não é gerado automaticamente durante VBAL/HDIAG/NICAS/SO/DIRAC.

---

#### 5.1.4. `x1.10242.invariant.nc`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/external-inputs/mpasjedi_tutorial202509NCAR/MPAS_namelist_stream_physics_files/x1.10242.invariant.nc
```

Esse arquivo contém campos invariantes da malha, como topografia, landmask e informações fixas usadas pelo MPAS/JEDI.

Ele deve existir antes da rodada.

Origem:

```text
entrada estática preparada a partir dos dados do tutorial/adaptação para x1.10242
```

Não é gerado pelo workflow da B.

---

### 5.2. Arquivos de namelist e streams

Esses arquivos devem estar no diretório:

```bash
/p/projetos/monan_das/joao.gerd/external-inputs/mpasjedi_tutorial202509NCAR/MPAS_namelist_stream_physics_files
```

#### 5.2.1. `namelist.atmosphere_240km`

Representa as configurações de execução do MPAS para a malha de 240 km.

O workflow copia ou reescreve esse arquivo dentro de cada diretório de execução, ajustando principalmente o `config_start_time` conforme a data da amostra usada.

Ele deve existir antes da rodada.

---

#### 5.2.2. `streams.atmosphere_240km`

Representa a configuração dos streams de entrada e saída do MPAS.

O workflow cria links simbólicos para esse arquivo nos diretórios de execução.

Ele deve existir antes da rodada.

---

### 5.3. Arquivos `stream_list.atmosphere.*`

Os arquivos esperados são:

```text
stream_list.atmosphere.analysis
stream_list.atmosphere.background
stream_list.atmosphere.control
stream_list.atmosphere.ensemble
```

#### 5.3.1. Onde devem estar antes da rodada

Os arquivos de referência devem estar em:

```bash
/p/projetos/monan_das/joao.gerd/external-inputs/mpasjedi_tutorial202509NCAR/MPAS_namelist_stream_physics_files
```

Durante a preparação das etapas, eles são linkados para os diretórios de execução.

#### 5.3.2. Observação importante sobre `stream_list.atmosphere.control`

O workflow atual escreve o `stream_list.atmosphere.control` com as variáveis de controle da B:

```text
stream_function
velocity_potential
temperature
spechum
surface_pressure
```

Essas são as variáveis usadas pelo SABER/BUMP para calibrar a B.

#### 5.3.3. O que representam

```text
analysis    variáveis esperadas no espaço de análise
background  variáveis esperadas no background
control     variáveis do espaço de controle da B
ensemble    variáveis esperadas nos membros/amostras
```

---

### 5.4. Arquivos `geovars.yaml` e `keptvars.yaml`

#### 5.4.1. `geovars.yaml`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/projects/MONAN-JEDI/mpas-jedi/test/testinput/namelists/geovars.yaml
```

Esse arquivo informa variáveis geofísicas usadas pelo MPAS-JEDI.

Ele deve existir antes da rodada.

---

#### 5.4.2. `keptvars.yaml`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/projects/MONAN-JEDI/mpas-jedi/test/testinput/namelists/keptvars.yaml
```

Esse arquivo informa variáveis que devem ser mantidas durante transformações e leituras do MPAS-JEDI.

Ele deve existir antes da rodada.

---

### 5.5. Arquivos físicos do MPAS

Os arquivos listados abaixo devem existir antes da rodada:

```text
CAM_ABS_DATA.DBL
CAM_AEROPT_DATA.DBL
GENPARM.TBL
LANDUSE.TBL
OZONE_DAT.TBL
RRTMG_LW_DATA
RRTMG_LW_DATA.DBL
RRTMG_SW_DATA
RRTMG_SW_DATA.DBL
SOILPARM.TBL
VEGPARM.TBL
VERSION
```

#### 5.5.1. Onde devem estar

O workflow procura esses arquivos preferencialmente no diretório de compartilhamento da instalação do MPAS atmosphere:

```bash
/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas/share/MPAS/core_atmosphere
```

Caso necessário, também podem estar no diretório de arquivos físicos do tutorial:

```bash
/p/projetos/monan_das/joao.gerd/external-inputs/mpasjedi_tutorial202509NCAR/MPAS_namelist_stream_physics_files
```

#### 5.5.2. O que representam

Esses arquivos são tabelas físicas usadas pelo MPAS. Eles contêm parâmetros de radiação, solo, vegetação, aerossóis, ozônio e outras informações fixas.

Eles não são produtos da matriz B. São arquivos auxiliares necessários para que o MPAS-JEDI consiga inicializar a geometria e interpretar corretamente os campos.

---

### 5.6. Resumo: arquivos de entrada versus arquivos gerados

| Arquivo                             |               Deve existir antes? | Gerado durante o workflow? | Papel                            |
| ----------------------------------- | --------------------------------: | -------------------------: | -------------------------------- |
| `x1.10242.grid.nc`                  |                               sim |                        não | malha MPAS                       |
| `x1.10242.graph.info`               |                               sim |                        não | grafo da malha                   |
| `x1.10242.graph.info.part.128`      |                               sim |                        não | partição MPI                     |
| `x1.10242.invariant.nc`             |                               sim |                        não | campos invariantes               |
| `namelist.atmosphere_240km`         |                               sim |             cópia ajustada | configuração MPAS                |
| `streams.atmosphere_240km`          |                               sim |                 link/cópia | streams MPAS                     |
| `stream_list.atmosphere.analysis`   |                               sim |                 link/cópia | lista de variáveis de análise    |
| `stream_list.atmosphere.background` |                               sim |                 link/cópia | lista de variáveis do background |
| `stream_list.atmosphere.control`    |               referência opcional | sim, escrito pelo workflow | variáveis de controle da B       |
| `stream_list.atmosphere.ensemble`   |                               sim |                 link/cópia | variáveis dos membros            |
| `geovars.yaml`                      |                               sim |                 link/cópia | geovariáveis MPAS-JEDI           |
| `keptvars.yaml`                     |                               sim |                 link/cópia | variáveis mantidas               |
| tabelas físicas MPAS                |                               sim |                        não | suporte físico MPAS              |
| `PTB_f48mf24.nc`                    | não, se BFLOW completo for rodado |                        sim | amostra NMC                      |
| `mpas_vbal.nc`                      |                               não |                        sim | balanço vertical                 |
| `mpas_sampling.nc`                  |                               não |                        sim | grade diagnóstica VBAL           |
| `mpas.stddev.nc`                    |                               não |                        sim | desvio padrão                    |
| `mpas.cor_rh.nc`                    |                               não |                        sim | escala horizontal                |
| `mpas.cor_rv.nc`                    |                               não |                        sim | escala vertical                  |
| `mpas_nicas.nc`                     |                               não |                        sim | operador NICAS                   |
| `mpas.nicas_norm.nc`                |                               não |                        sim | normalização NICAS               |
| `mpas.dirac_nicas.nc`               |                               não |                        sim | Dirac do NICAS                   |
| `mpas.dirac.nc`                     |                               não |                        sim | resposta da B completa           |

---

## 6. Definir o período da rodada

Antes de gerar a B, é necessário definir o período usado para formar as amostras NMC.

Neste tutorial, usaremos o smoke validado:

```bash
START_VALID=2026-06-10_00:00:00
END_VALID=2026-06-13_00:00:00
VALID_INTERVAL_HOURS=24
DT=60
```

Esse período gera quatro amostras válidas:

```text
2026-06-10_00:00:00
2026-06-11_00:00:00
2026-06-12_00:00:00
2026-06-13_00:00:00
```

Quatro amostras são o mínimo técnico para HDIAG/NICAS. Para uma B de produção, isso é insuficiente. Para produção, é necessário usar muito mais datas, cobrindo maior variabilidade meteorológica.

---

## 7. BFLOW: o que é e por que existe?

### 7.1. O que é BFLOW?

BFLOW é a etapa de preparação das amostras estatísticas usadas para calibrar a matriz B.

O nome aqui representa o fluxo de geração dos arquivos de perturbação do background. Essas perturbações são calculadas pelo método NMC:

```text
PTB = previsão de 48h - previsão de 24h
```

As duas previsões precisam ser válidas no mesmo horário.

Por exemplo:

```text
previsão iniciada em 2026-06-10 00 UTC com 48h
previsão iniciada em 2026-06-11 00 UTC com 24h

ambas válidas em 2026-06-12 00 UTC
```

A diferença entre elas é usada como aproximação estatística do erro do background.

### 7.2. Por que BFLOW é feito antes de tudo?

Porque VBAL, HDIAG e NICAS precisam de amostras. Sem amostras NMC, não há como calcular:

```text
covariância vertical
balanço entre variáveis
desvio padrão
comprimento de correlação horizontal
comprimento de correlação vertical
```

Então o BFLOW é a base estatística de todo o processo.

### 7.3. O que o BFLOW gera?

Para cada data válida, espera-se gerar:

```text
FULL_f24.nc
FULL_f48.nc
PTB_f48mf24.nc
```

O produto mais importante para a B é:

```text
PTB_f48mf24.nc
```

O BFLOW também deve produzir um arquivo de manifesto:

```text
manifest.tsv
```

Esse manifesto informa às etapas seguintes onde estão as amostras.

---

## 8. Gerar as amostras NMC

Entre no repositório:

```bash
cd /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
source scripts/load_jaci_env.sh
conda activate mpaswf
```

Rode:

```bash
mpaswf \
  --config configs/jaci-x1.10242.yaml \
  nmc range \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time   2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --submit \
  --wait \
  --poll-seconds 30 \
  --diff
```

Essa etapa submete previsões MPAS e calcula as diferenças NMC.

Resultado esperado:

```text
work/mpas-bmatrix-global/bmatrix/bflow_preprocessing/np128_2026061000_2026061300/output/YYYYMMDDHH/PTB_f48mf24.nc
```

---

## 9. Preparar o workspace BFLOW

Depois que as diferenças NMC existem, defina:

```bash
export BFLOW=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/bflow_preprocessing/np128_2026061000_2026061300
```

Verifique:

```bash
cat "$BFLOW/manifest.tsv"
find "$BFLOW/output" -name "PTB_f48mf24.nc" | sort
```

O `manifest.tsv` deve listar as datas válidas e os arquivos de origem.

Essa etapa é importante porque o `mpasbcov vbal-all` lê o `manifest.tsv`, copia os `PTB_f48mf24.nc` para um diretório padronizado `samples/` e cria a sequência de membros:

```text
PTB_f48mf24_001.nc
PTB_f48mf24_002.nc
PTB_f48mf24_003.nc
PTB_f48mf24_004.nc
```

---

## 10. VBAL: balanço vertical e multivariado

### 10.1. O que é VBAL?

VBAL significa Vertical Balance.

Essa etapa calibra relações estatísticas entre variáveis de controle. No nosso caso:

```text
stream_function -> velocity_potential
stream_function -> temperature
stream_function -> surface_pressure
```

Em termos científicos, ela tenta responder:

```text
quando há erro em stream_function, 
qual parte desse erro aparece de forma balanceada em temperatura,
potencial de velocidade e pressão de superfície?
```

### 10.2. Por que VBAL vem depois do BFLOW?

Porque o VBAL precisa das perturbações NMC. Ele calcula relações estatísticas a partir das amostras `PTB_f48mf24`.

### 10.3. Rodar VBAL

```bash
export VBAL=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/vbal/np128_2026061000_2026061300

mpasbcov vbal-all \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --workspace "$VBAL" \
  --clean \
  --poll-seconds 30
```

### 10.4. Produtos esperados do VBAL

```text
$VBAL/samples/PTB_f48mf24_001.nc
$VBAL/samples/PTB_f48mf24_002.nc
$VBAL/samples/PTB_f48mf24_003.nc
$VBAL/samples/PTB_f48mf24_004.nc

$VBAL/VBAL/mpas_sampling.nc
$VBAL/VBAL/mpas_vbal.nc
$VBAL/VBAL/mpas_sampling_local_*
$VBAL/VBAL/mpas_vbal_local_*
$VBAL/VBAL/run_vbal.yaml
$VBAL/VBAL/run_vbal.runlog
```

### 10.5. O que esses arquivos representam?

```text
mpas_sampling.nc
  contém a grade diagnóstica usada pelo BUMP/VBAL

mpas_vbal.nc
  contém os coeficientes de balanço vertical e multivariado

mpas_sampling_local_*
  produtos locais por rank MPI

mpas_vbal_local_*
  produtos locais de balanço por rank MPI
```

No SABER atual, `mpas_vbal.nc` usa groups NetCDF-4. Portanto, ele pode parecer vazio se for lido apenas no nível raiz. É necessário ler os groups para acessar variáveis como:

```text
reg_c2
cov_c2
explained_var_c2
```

### 10.6. Validação

```bash
mpasbcov vbal-validate --workspace "$VBAL"
```

Resultado esperado:

```text
SUCCESS: VBAL validado.
```

---

## 11. HDIAG: desvio padrão e escalas de correlação

### 11.1. O que é HDIAG?

HDIAG é a etapa que calcula diagnósticos estatísticos da B, principalmente:

```text
stddev   desvio padrão dos erros
cor_rh   escala horizontal de correlação
cor_rv   escala vertical de correlação
```

### 11.2. Por que HDIAG vem depois do VBAL?

Porque o HDIAG precisa considerar o balanço vertical calibrado. No tutorial antigo, isso era feito usando amostras desbalanceadas. No SABER atual, o workflow lê os PTBs originais e aplica o `BUMP_VerticalBalance` em modo leitura dentro do próprio HDIAG.

Assim, a ordem é:

```text
BFLOW gera amostras
VBAL calibra balanço
HDIAG calcula estatísticas usando esse balanço
```

### 11.3. Rodar HDIAG

```bash
export HDIAG=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/hdiag/np128_2026061000_2026061300

mpasbcov hdiag-all \
  --config configs/jaci-x1.10242.yaml \
  --vbal-workspace "$VBAL" \
  --workspace "$HDIAG" \
  --clean \
  --poll-seconds 30
```

### 11.4. Produtos esperados do HDIAG

```text
$HDIAG/HDIAG/mpas.stddev.nc
$HDIAG/HDIAG/mpas.cor_rh.nc
$HDIAG/HDIAG/mpas.cor_rv.nc
$HDIAG/HDIAG/run_hdiag.yaml
$HDIAG/HDIAG/run_hdiag.runlog
```

### 11.5. O que esses arquivos representam?

```text
mpas.stddev.nc
  amplitude dos erros de background por variável

mpas.cor_rh.nc
  escala horizontal de correlação

mpas.cor_rv.nc
  escala vertical de correlação
```

Esses arquivos serão usados depois pelo NICAS e pela B final.

### 11.6. Validação

```bash
mpasbcov hdiag-validate --workspace "$HDIAG"
```

Resultado esperado:

```text
SUCCESS: HDIAG validado.
```

---

## 12. NICAS: construção da correlação

### 12.1. O que é NICAS?

NICAS é o bloco que constrói uma representação eficiente da correlação espacial da B. Ele usa as escalas calculadas no HDIAG para definir como o erro se espalha horizontal e verticalmente.

### 12.2. Por que NICAS vem depois do HDIAG?

Porque NICAS precisa dos arquivos:

```text
mpas.cor_rh.nc
mpas.cor_rv.nc
mpas.stddev.nc
```

O NICAS usa principalmente as escalas de correlação horizontal e vertical para construir o operador de correlação.

### 12.3. Rodar NICAS

```bash
export NICAS=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/nicas/np128_2026061000_2026061300

mpasbcov nicas-all \
  --config configs/jaci-x1.10242.yaml \
  --hdiag-workspace "$HDIAG" \
  --workspace "$NICAS" \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

### 12.4. Produtos esperados do NICAS

Por variável:

```text
$NICAS/stream_function/mpas_nicas.nc
$NICAS/velocity_potential/mpas_nicas.nc
$NICAS/temperature/mpas_nicas.nc
$NICAS/spechum/mpas_nicas.nc
$NICAS/surface_pressure/mpas_nicas.nc
```

Depois do merge:

```text
$NICAS/merge/mpas_nicas.nc
$NICAS/merge/mpas.nicas_norm.nc
$NICAS/merge/mpas.dirac_nicas.nc
$NICAS/merge/mpas_nicas_local_*
$NICAS/merge/mpas_nicas_grids_local_*
```

### 12.5. O que esses arquivos representam?

```text
mpas_nicas.nc
  operador global NICAS

mpas_nicas_local_*
  parte local do operador NICAS por rank MPI

mpas_nicas_grids_local_*
  informações das grades locais usadas pelo NICAS

mpas.nicas_norm.nc
  normalização do NICAS

mpas.dirac_nicas.nc
  resposta Dirac do NICAS puro
```

### 12.6. Validação

```bash
mpasbcov nicas-validate --workspace "$NICAS"
```

Resultado esperado:

```text
SUCCESS: NICAS split/merge validado.
```

---

## 13. SO: teste de observação única

### 13.1. O que é SO?

SO significa Single Observation Test.

Ele testa a B completa dentro de uma assimilação variacional com uma observação sintética. Ele não calibra a B. Ele verifica se a B já construída responde de forma física.

### 13.2. Por que SO vem depois de NICAS?

Porque o SO usa a B completa, ou seja:

```text
NICAS
StdDev
VBAL
Control2Analysis
```

Sem NICAS, HDIAG e VBAL, o SO não tem a B completa para testar.

### 13.3. Rodar SO

```bash
export SO=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/so/np128_2026061000_2026061300

mpasbcov so-all \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --hdiag-workspace "$HDIAG" \
  --vbal-workspace "$VBAL" \
  --workspace "$SO" \
  --variant default \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

### 13.4. Produtos esperados do SO

```text
$SO/run_SO.yaml
$SO/run_SO.runlog
$SO/obsout_SO_T.h5
$SO/obsout_SO_U.h5
$SO/an.*.nc
```

### 13.5. O que esses arquivos representam?

```text
obsout_SO_T.h5
  saída da observação sintética de temperatura

obsout_SO_U.h5
  saída da observação sintética de vento

an.*.nc
  arquivo de análise produzido pelo teste

run_SO.runlog
  log da execução variacional
```

### 13.6. Validação

```bash
mpasbcov so-validate \
  --workspace "$SO" \
  --variant default
```

Resultado esperado:

```text
SUCCESS: SO validado.
```

---

## 14. DIRAC: resposta da B completa

### 14.1. O que é DIRAC?

DIRAC é um teste de impulso. Ele aplica uma perturbação pontual em uma variável e mostra como a B completa espalha essa perturbação.

### 14.2. Por que DIRAC vem depois de NICAS, HDIAG e VBAL?

Porque ele usa a B completa:

```text
NICAS
StdDev
VBAL
Control2Analysis
```

O DIRAC testa a estrutura matemática da B. O SO testa a B dentro da assimilação variacional.

### 14.3. Rodar DIRAC

```bash
export DIRAC=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/dirac/np128_2026061000_2026061300

mpasbcov dirac-all \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --hdiag-workspace "$HDIAG" \
  --vbal-workspace "$VBAL" \
  --workspace "$DIRAC" \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

### 14.4. Produtos esperados do DIRAC

```text
$DIRAC/run_dirac.yaml
$DIRAC/run_dirac.runlog
$DIRAC/mpas.dirac.nc
```

### 14.5. O que esses arquivos representam?

```text
mpas.dirac.nc
  resposta da B completa a um impulso
```

### 14.6. Validação

```bash
mpasbcov dirac-validate --workspace "$DIRAC"
```

Resultado esperado:

```text
SUCCESS: Dirac validado.
```

Gerar resumo:

```bash
mpasbcov dirac-summary \
  --workspace "$DIRAC" \
  --csv "$DIRAC/dirac_summary.csv"
```

Gerar figuras:

```bash
mpasbcov dirac-plot \
  --workspace "$DIRAC" \
  --variables stream_function velocity_potential temperature spechum surface_pressure \
  --level 30 \
  --output-dir "$DIRAC/figures" \
  --dpi 150
```

---

## 15. Qual é o arquivo final da matriz B?

Esta é uma questão importante: a B final não é um único arquivo.

No MPAS-JEDI/SABER, a matriz B estática é usada como um conjunto de arquivos e blocos de configuração.

A B final é composta por:

### 15.1. Produtos NICAS

Diretório principal:

```bash
$NICAS/merge
```

Arquivos principais:

```text
mpas_nicas.nc
mpas_nicas_local_*
mpas_nicas_grids_local_*
```

Esses arquivos representam a correlação espacial.

Arquivos diagnósticos associados:

```text
mpas.nicas_norm.nc
mpas.dirac_nicas.nc
```

Esses dois são úteis para validação, mas o operador principal usado pela B é o NICAS.

### 15.2. Produto StdDev

Arquivo:

```bash
$HDIAG/HDIAG/mpas.stddev.nc
```

Esse arquivo representa a amplitude dos erros.

Ele é lido pelo bloco `StdDev`.

### 15.3. Produtos VBAL

Diretório principal:

```bash
$VBAL/VBAL
```

Arquivos principais:

```text
mpas_vbal.nc
mpas_sampling.nc
mpas_vbal_local_*
mpas_sampling_local_*
```

Esses arquivos representam o balanço vertical e multivariado.

### 15.4. Configuração YAML no MPAS-JEDI

Na assimilação, a B deve ser configurada no YAML do MPAS-JEDI como uma composição de blocos SABER:

```yaml
background error:
  covariance model: SABER

  saber central block:
    saber block name: BUMP_NICAS
    read:
      io:
        data directory: /caminho/para/NICAS/merge
        files prefix: mpas
      drivers:
        read local nicas: true

  saber outer blocks:
  - saber block name: StdDev
    read:
      model file:
        filename: /caminho/para/HDIAG/HDIAG/mpas.stddev.nc

  - saber block name: BUMP_VerticalBalance
    read:
      io:
        data directory: /caminho/para/VBAL/VBAL
        files prefix: mpas
      drivers:
        read local sampling: true
        read vertical balance: true

  linear variable change:
    linear variable change name: Control2Analysis
```

Portanto, a resposta correta é:

```text
A B final não é um único arquivo.
Ela é composta por produtos NICAS, StdDev, VBAL e pela configuração SABER no YAML.
```

### 15.5. Conjunto mínimo de arquivos para usar a B no MPAS-JEDI

Para usar a B em uma assimilação 3DVar/FGAT, mantenha:

```text
NICAS:
  $NICAS/merge/mpas_nicas.nc
  $NICAS/merge/mpas_nicas_local_*
  $NICAS/merge/mpas_nicas_grids_local_*

StdDev:
  $HDIAG/HDIAG/mpas.stddev.nc

VBAL:
  $VBAL/VBAL/mpas_vbal.nc
  $VBAL/VBAL/mpas_sampling.nc
  $VBAL/VBAL/mpas_vbal_local_*
  $VBAL/VBAL/mpas_sampling_local_*
```

Arquivos recomendados para diagnóstico e rastreabilidade:

```text
$HDIAG/HDIAG/mpas.cor_rh.nc
$HDIAG/HDIAG/mpas.cor_rv.nc
$NICAS/merge/mpas.nicas_norm.nc
$NICAS/merge/mpas.dirac_nicas.nc
$DIRAC/mpas.dirac.nc
$SO/obsout_SO_T.h5
$SO/obsout_SO_U.h5
$SO/an.*.nc
```

---

## 16. Diagnósticos recomendados

### 16.1. VBAL

```bash
python -m mpas_workflow.vbal_groups \
  --workspace "$VBAL" \
  --output-dir "$VBAL/VBAL/figures_vbal_groups" \
  --mode quick \
  --dpi 150
```

Esse diagnóstico mostra a variância explicada e os coeficientes de regressão do balanço vertical.

### 16.2. HDIAG

```bash
python -m mpas_workflow.hdiag_summary \
  --workspace "$HDIAG" \
  --output-dir "$HDIAG/HDIAG/figures_hdiag_summary" \
  --level 30 \
  --mode standard \
  --dpi 150
```

Esse diagnóstico mostra perfis, estatísticas e histogramas de `stddev`, `cor_rh` e `cor_rv`.

### 16.3. NICAS

```bash
python -m mpas_workflow.nicas_summary \
  --workspace "$NICAS" \
  --output-dir "$NICAS/figures_nicas_summary" \
  --variables all \
  --level 30 \
  --mode standard \
  --dpi 150
```

Esse diagnóstico avalia os produtos NICAS.

### 16.4. DIRAC

```bash
mpasbcov dirac-summary \
  --workspace "$DIRAC" \
  --csv "$DIRAC/dirac_summary.csv"

mpasbcov dirac-plot \
  --workspace "$DIRAC" \
  --variables stream_function velocity_potential temperature spechum surface_pressure \
  --level 30 \
  --output-dir "$DIRAC/figures" \
  --dpi 150
```

---

## 17. Verificação final

Ao final, rode:

```bash
mpasbcov vbal-validate  --workspace "$VBAL"
mpasbcov hdiag-validate --workspace "$HDIAG"
mpasbcov nicas-validate --workspace "$NICAS"
mpasbcov so-validate    --workspace "$SO" --variant default
mpasbcov dirac-validate --workspace "$DIRAC"
```

Todas as etapas devem retornar sucesso.

Verifique os produtos principais:

```bash
ls -lh "$VBAL/VBAL/mpas_vbal.nc"
ls -lh "$VBAL/VBAL/mpas_sampling.nc"

ls -lh "$HDIAG/HDIAG/mpas.stddev.nc"
ls -lh "$HDIAG/HDIAG/mpas.cor_rh.nc"
ls -lh "$HDIAG/HDIAG/mpas.cor_rv.nc"

ls -lh "$NICAS/merge/mpas_nicas.nc"
ls -lh "$NICAS/merge/mpas.nicas_norm.nc"
ls -lh "$NICAS/merge/mpas.dirac_nicas.nc"

ls -lh "$SO"/obsout_SO_*.h5
ls -lh "$SO"/an.*.nc

ls -lh "$DIRAC/mpas.dirac.nc"
```

---

## 18. Diferença entre smoke test e produção

O smoke test usa poucos membros para validar o funcionamento técnico do workflow.

Ele responde:

```text
o workflow roda?
os YAMLs estão corretos?
os executáveis funcionam?
os produtos são gerados?
a B pode ser lida pelo SO e pelo DIRAC?
```

Mas ele não responde completamente:

```text
a B é estatisticamente robusta?
a B representa várias situações meteorológicas?
a B é adequada para assimilação operacional?
```

Para uma B de produção, é necessário aumentar:

```text
número de amostras
período temporal
representatividade sazonal
checagem estatística
validação com experimentos reais de assimilação
```

---

## 19. Resumo final

O processo completo é:

```text
1. Preparar ambiente Python mpaswf
2. Garantir arquivos estáticos da malha, namelist, streams e física
3. Gerar pares NMC f48 - f24
4. Preparar BFLOW e manifesto de amostras
5. Rodar VBAL para calibrar balanço vertical
6. Rodar HDIAG para calcular stddev e escalas de correlação
7. Rodar NICAS para construir o operador de correlação
8. Rodar SO para testar a B dentro do 3DVar
9. Rodar DIRAC para verificar a resposta da B completa
10. Usar na assimilação os produtos NICAS + StdDev + VBAL no YAML do MPAS-JEDI
```

A matriz B final, portanto, não é um arquivo único. Ela é um conjunto de produtos calibrados e lidos pelo SABER dentro do MPAS-JEDI.
