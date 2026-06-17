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

# 2. Criação e instalação do ambiente Python `mpaswf`

## 2.1. Por que o ambiente `mpaswf` é necessário?

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

## 2.2. Criar o ambiente Conda

No JACI, carregue o ambiente base do Conda e crie o ambiente `mpaswf`:

```bash
conda create -n mpaswf python=3.11 -y
```

Ative o ambiente:

```bash
conda activate mpaswf
```

Instale as dependências principais:

```bash
python -m pip install --upgrade pip
python -m pip install PyYAML numpy netCDF4 cftime xarray matplotlib
```

A dependência `matplotlib` é necessária para os diagnósticos gráficos, mesmo que não esteja listada como dependência obrigatória principal no `pyproject.toml`.

## 2.3. Instalar o repositório

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

## 2.4. Verificar instalação

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

# 3. Configuração principal do workflow

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

# 4. Arquivos necessários antes da rodada

Esta seção é uma das mais importantes. Nem tudo é gerado pelo workflow. Alguns arquivos precisam existir antes da execução.

A configuração atual espera os arquivos nos caminhos definidos em `configs/jaci-x1.10242.yaml`.

---

## 4.1. Arquivos da malha MPAS

### 4.1.1. `x1.10242.grid.nc`

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

### 4.1.2. `x1.10242.graph.info`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/projects/mpas_meshes/quasi_uniform/x1.10242_240km/graph/x1.10242.graph.info
```

Esse arquivo descreve o grafo da malha MPAS. Ele é usado para particionamento MPI.

Ele deve existir antes da rodada.

Não é gerado pelas etapas VBAL, HDIAG, NICAS, SO ou DIRAC.

---

### 4.1.3. `x1.10242.graph.info.part.128`

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

### 4.1.4. `x1.10242.invariant.nc`

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

## 4.2. Arquivos de namelist e streams

Esses arquivos devem estar no diretório:

```bash
/p/projetos/monan_das/joao.gerd/external-inputs/mpasjedi_tutorial202509NCAR/MPAS_namelist_stream_physics_files
```

### 4.2.1. `namelist.atmosphere_240km`

Representa as configurações de execução do MPAS para a malha de 240 km.

O workflow copia ou reescreve esse arquivo dentro de cada diretório de execução, ajustando principalmente o `config_start_time` conforme a data da amostra usada.

Ele deve existir antes da rodada.

---

### 4.2.2. `streams.atmosphere_240km`

Representa a configuração dos streams de entrada e saída do MPAS.

O workflow cria links simbólicos para esse arquivo nos diretórios de execução.

Ele deve existir antes da rodada.

---

## 4.3. Arquivos `stream_list.atmosphere.*`

Os arquivos esperados são:

```text
stream_list.atmosphere.analysis
stream_list.atmosphere.background
stream_list.atmosphere.control
stream_list.atmosphere.ensemble
```

### Onde devem estar antes da rodada

Os arquivos de referência devem estar em:

```bash
/p/projetos/monan_das/joao.gerd/external-inputs/mpasjedi_tutorial202509NCAR/MPAS_namelist_stream_physics_files
```

Durante a preparação das etapas, eles são linkados para os diretórios de execução.

### Observação importante sobre `stream_list.atmosphere.control`

O workflow atual escreve o `stream_list.atmosphere.control` com as variáveis de controle da B:

```text
stream_function
velocity_potential
temperature
spechum
surface_pressure
```

Essas são as variáveis usadas pelo SABER/BUMP para calibrar a B.

### O que representam

```text
analysis    variáveis esperadas no espaço de análise
background  variáveis esperadas no background
control     variáveis do espaço de controle da B
ensemble    variáveis esperadas nos membros/amostras
```

---

## 4.4. Arquivos `geovars.yaml` e `keptvars.yaml`

### `geovars.yaml`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/projects/MONAN-JEDI/mpas-jedi/test/testinput/namelists/geovars.yaml
```

Esse arquivo informa variáveis geofísicas usadas pelo MPAS-JEDI.

Ele deve existir antes da rodada.

---

### `keptvars.yaml`

Caminho esperado:

```bash
/p/projetos/monan_das/joao.gerd/projects/MONAN-JEDI/mpas-jedi/test/testinput/namelists/keptvars.yaml
```

Esse arquivo informa variáveis que devem ser mantidas durante transformações e leituras do MPAS-JEDI.

Ele deve existir antes da rodada.

---

## 4.5. Arquivos físicos do MPAS

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

### Onde devem estar

O workflow procura esses arquivos preferencialmente no diretório de compartilhamento da instalação do MPAS atmosphere:

```bash
/p/projetos/monan_das/joao.gerd/builds/monan-jedi-mpas/share/MPAS/core_atmosphere
```

Caso necessário, também podem estar no diretório de arquivos físicos do tutorial:

```bash
/p/projetos/monan_das/joao.gerd/external-inputs/mpasjedi_tutorial202509NCAR/MPAS_namelist_stream_physics_files
```

### O que representam

Esses arquivos são tabelas físicas usadas pelo MPAS. Eles contêm parâmetros de radiação, solo, vegetação, aerossóis, ozônio e outras informações fixas.

Eles não são produtos da matriz B. São arquivos auxiliares necessários para que o MPAS-JEDI consiga inicializar a geometria e interpretar corretamente os campos.

---

## 4.6. Resumo: arquivos de entrada versus arquivos gerados

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

# 5. Definir o período da rodada

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

# 6. BFLOW: o que é e por que existe?

## 6.1. O que é BFLOW?

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

## 6.2. Por que BFLOW é feito antes de tudo?

Porque VBAL, HDIAG e NICAS precisam de amostras. Sem amostras NMC, não há como calcular:

```text
covariância vertical
balanço entre variáveis
desvio padrão
comprimento de correlação horizontal
comprimento de correlação vertical
```

Então o BFLOW é a base estatística de todo o processo.

## 6.3. O que o BFLOW gera?

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

# 7. Gerar as amostras NMC

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

# 8. Preparar o workspace BFLOW

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

# 9. VBAL: balanço vertical e multivariado

## 9.1. O que é VBAL?

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

## 9.2. Por que VBAL vem depois do BFLOW?

Porque o VBAL precisa das perturbações NMC. Ele calcula relações estatísticas a partir das amostras `PTB_f48mf24`.

## 9.3. Rodar VBAL

```bash
export VBAL=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/vbal/np128_2026061000_2026061300

mpasbcov vbal-all \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --workspace "$VBAL" \
  --clean \
  --poll-seconds 30
```

## 9.4. Produtos esperados do VBAL

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

## 9.5. O que esses arquivos representam?

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

## 9.6. Validação

```bash
mpasbcov vbal-validate --workspace "$VBAL"
```

Resultado esperado:

```text
SUCCESS: VBAL validado.
```

---

# 10. HDIAG: desvio padrão e escalas de correlação

## 10.1. O que é HDIAG?

HDIAG é a etapa que calcula diagnósticos estatísticos da B, principalmente:

```text
stddev   desvio padrão dos erros
cor_rh   escala horizontal de correlação
cor_rv   escala vertical de correlação
```

## 10.2. Por que HDIAG vem depois do VBAL?

Porque o HDIAG precisa considerar o balanço vertical calibrado. No tutorial antigo, isso era feito usando amostras desbalanceadas. No SABER atual, o workflow lê os PTBs originais e aplica o `BUMP_VerticalBalance` em modo leitura dentro do próprio HDIAG.

Assim, a ordem é:

```text
BFLOW gera amostras
VBAL calibra balanço
HDIAG calcula estatísticas usando esse balanço
```

## 10.3. Rodar HDIAG

```bash
export HDIAG=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/hdiag/np128_2026061000_2026061300

mpasbcov hdiag-all \
  --config configs/jaci-x1.10242.yaml \
  --vbal-workspace "$VBAL" \
  --workspace "$HDIAG" \
  --clean \
  --poll-seconds 30
```

## 10.4. Produtos esperados do HDIAG

```text
$HDIAG/HDIAG/mpas.stddev.nc
$HDIAG/HDIAG/mpas.cor_rh.nc
$HDIAG/HDIAG/mpas.cor_rv.nc
$HDIAG/HDIAG/run_hdiag.yaml
$HDIAG/HDIAG/run_hdiag.runlog
```

## 10.5. O que esses arquivos representam?

```text
mpas.stddev.nc
  amplitude dos erros de background por variável

mpas.cor_rh.nc
  escala horizontal de correlação

mpas.cor_rv.nc
  escala vertical de correlação
```

Esses arquivos serão usados depois pelo NICAS e pela B final.

## 10.6. Validação

```bash
mpasbcov hdiag-validate --workspace "$HDIAG"
```

Resultado esperado:

```text
SUCCESS: HDIAG validado.
```

---

# 11. NICAS: construção da correlação

## 11.1. O que é NICAS?

NICAS é o bloco que constrói uma representação eficiente da correlação espacial da B. Ele usa as escalas calculadas no HDIAG para definir como o erro se espalha horizontal e verticalmente.

## 11.2. Por que NICAS vem depois do HDIAG?

Porque NICAS precisa dos arquivos:

```text
mpas.cor_rh.nc
mpas.cor_rv.nc
mpas.stddev.nc
```

O NICAS usa principalmente as escalas de correlação horizontal e vertical para construir o operador de correlação.

## 11.3. Rodar NICAS

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

## 11.4. Produtos esperados do NICAS

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

## 11.5. O que esses arquivos representam?

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

## 11.6. Validação

```bash
mpasbcov nicas-validate --workspace "$NICAS"
```

Resultado esperado:

```text
SUCCESS: NICAS split/merge validado.
```

---

# 12. SO: teste de observação única

## 12.1. O que é SO?

SO significa Single Observation Test.

Ele testa a B completa dentro de uma assimilação variacional com uma observação sintética. Ele não calibra a B. Ele verifica se a B já construída responde de forma física.

## 12.2. Por que SO vem depois de NICAS?

Porque o SO usa a B completa, ou seja:

```text
NICAS
StdDev
VBAL
Control2Analysis
```

Sem NICAS, HDIAG e VBAL, o SO não tem a B completa para testar.

## 12.3. Rodar SO

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

## 12.4. Produtos esperados do SO

```text
$SO/run_SO.yaml
$SO/run_SO.runlog
$SO/obsout_SO_T.h5
$SO/obsout_SO_U.h5
$SO/an.*.nc
```

## 12.5. O que esses arquivos representam?

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

## 12.6. Validação

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

# 13. DIRAC: resposta da B completa

## 13.1. O que é DIRAC?

DIRAC é um teste de impulso. Ele aplica uma perturbação pontual em uma variável e mostra como a B completa espalha essa perturbação.

## 13.2. Por que DIRAC vem depois de NICAS, HDIAG e VBAL?

Porque ele usa a B completa:

```text
NICAS
StdDev
VBAL
Control2Analysis
```

O DIRAC testa a estrutura matemática da B. O SO testa a B dentro da assimilação variacional.

## 13.3. Rodar DIRAC

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

## 13.4. Produtos esperados do DIRAC

```text
$DIRAC/run_dirac.yaml
$DIRAC/run_dirac.runlog
$DIRAC/mpas.dirac.nc
```

## 13.5. O que esses arquivos representam?

```text
mpas.dirac.nc
  resposta da B completa a um impulso
```

## 13.6. Validação

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

# 14. Qual é o arquivo final da matriz B?

Esta é uma questão importante: a B final não é um único arquivo.

No MPAS-JEDI/SABER, a matriz B estática é usada como um conjunto de arquivos e blocos de configuração.

A B final é composta por:

## 14.1. Produtos NICAS

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

## 14.2. Produto StdDev

Arquivo:

```bash
$HDIAG/HDIAG/mpas.stddev.nc
```

Esse arquivo representa a amplitude dos erros.

Ele é lido pelo bloco `StdDev`.

## 14.3. Produtos VBAL

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

## 14.4. Configuração YAML no MPAS-JEDI

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

## 14.5. Conjunto mínimo de arquivos para usar a B no MPAS-JEDI

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

# 15. Diagnósticos recomendados

## 15.1. VBAL

```bash
python -m mpas_workflow.vbal_groups \
  --workspace "$VBAL" \
  --output-dir "$VBAL/VBAL/figures_vbal_groups" \
  --mode quick \
  --dpi 150
```

Esse diagnóstico mostra a variância explicada e os coeficientes de regressão do balanço vertical.

## 15.2. HDIAG

```bash
python -m mpas_workflow.hdiag_summary \
  --workspace "$HDIAG" \
  --output-dir "$HDIAG/HDIAG/figures_hdiag_summary" \
  --level 30 \
  --mode standard \
  --dpi 150
```

Esse diagnóstico mostra perfis, estatísticas e histogramas de `stddev`, `cor_rh` e `cor_rv`.

## 15.3. NICAS

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

## 15.4. DIRAC

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

# 16. Verificação final

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

# 17. Diferença entre smoke test e produção

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

# 18. Resumo final

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
