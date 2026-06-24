# Instalação e validação do WPS/ungrib no JACI

## 1. Finalidade e escopo

Este documento instala e valida o componente `ungrib.exe` do WPS, usado para converter dados meteorológicos em formato GRIB — especialmente do GFS — em arquivos intermediários para a preparação das condições iniciais do MPAS.

O WPS é um **pré-requisito condicional** do workflow: ele é necessário quando as amostras NMC precisam ser produzidas a partir de previsões MPAS inicializadas com dados GFS/GRIB. Ele não é necessário para instalar o pacote Python `mpaswf`, nem para executar VBAL, HDIAG, NICAS, SO ou DIRAC quando as amostras NMC já existirem.

Para preparar o ambiente Python utilizado nos comandos deste documento, consulte [Instalação do ambiente `mpaswf`](install-mpaswf-jaci.md).

## 2. Quando o WPS/ungrib é necessário?

Antes de gerar a matriz B, é necessário gerar amostras NMC. Essas amostras dependem de previsões MPAS iniciadas a partir de condições iniciais consistentes.

Quando a fonte meteorológica usada é GFS em formato GRIB, é necessário passar por uma etapa de pré-processamento com WPS, principalmente com o programa:

```text
ungrib.exe
```

O `ungrib.exe` lê os arquivos GRIB do GFS e os converte para arquivos intermediários que podem ser usados na preparação das condições iniciais do MPAS.

Portanto, o WPS não faz parte diretamente da matriz B, mas ele é necessário antes do BFLOW quando as amostras NMC serão geradas a partir de previsões MPAS inicializadas com GFS.

A sequência conceitual fica assim:

```text
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

## 3. Configuração esperada do WPS

No arquivo:

```bash
configs/jaci-x1.10242.yaml
```

deve existir o bloco:

```yaml
wps:
  root: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
  ungrib_exe: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/ungrib.exe
  link_grib: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/link_grib.csh
  vtable_gfs: /p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/ungrib/Variable_Tables/Vtable.GFS
```

Esses caminhos significam:

```text
root
  diretório de instalação/código-fonte do WPS

ungrib_exe
  executável que converte GRIB para arquivos intermediários

link_grib
  script do WPS que cria links GRIBFILE.AAA, GRIBFILE.AAB, ...

vtable_gfs
  tabela que informa ao ungrib como interpretar as variáveis do GFS
```

## 4. Onde o WPS deve estar instalado?

O diretório esperado é:

```bash
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

Dentro dele devem existir, ao final da instalação:

```text
ungrib.exe
link_grib.csh
ungrib/Variable_Tables/Vtable.GFS
```

O arquivo mais importante para o workflow é:

```bash
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/ungrib.exe
```

## 5. Verificar se o WPS já está instalado

Antes de compilar, verifique:

```bash
WPS_ROOT=/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0

ls -lh "$WPS_ROOT"
ls -lh "$WPS_ROOT/ungrib.exe"
ls -lh "$WPS_ROOT/link_grib.csh"
ls -lh "$WPS_ROOT/ungrib/Variable_Tables/Vtable.GFS"
```

Se `ungrib.exe` existir e for executável, a etapa de instalação do WPS já está pronta:

```bash
test -x "$WPS_ROOT/ungrib.exe" && echo "OK: ungrib.exe executável"
```

## 6. Baixar ou preparar o código-fonte do WPS

O código-fonte do WPS deve estar em:

```bash
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

Caso o diretório não exista, é necessário baixar/preparar o WPS antes de compilar.

No repositório, o script de build informa que, se o diretório do WPS não existir, primeiro deve ser executada a etapa de download/preparação dos assets do WPS.

Verifique se existe um script legado para isso:

```bash
ls -lh scripts/legacy/*wps* scripts/legacy/*WPS* 2>/dev/null
```

Depois rode o script apropriado de download/preparação, se ele existir no repositório. Em algumas versões do repositório, essa etapa foi chamada de:

```bash
scripts/legacy/10_download_wps_assets.sh
```

Se esse script não existir na versão atual, o WPS deve ser obtido manualmente ou copiado de uma instalação já preparada para:

```bash
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

## 7. Compilar o `ungrib.exe`

Entre no repositório:

```bash
cd /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
```

Carregue o ambiente JACI e ative o ambiente Python `mpaswf`:

```bash
source scripts/load_jaci_env.sh
module load anaconda
start_conda
conda activate mpaswf
```

A criação do ambiente Python é documentada em [Instalação do ambiente `mpaswf`](install-mpaswf-jaci.md).

Rode a compilação:

```bash
bash scripts/legacy/12_build_wps_ungrib.sh \
  | tee logs/12_build_wps_ungrib.log
```

Se quiser forçar recompilação:

```bash
FORCE_WPS_REBUILD=true \
bash scripts/legacy/12_build_wps_ungrib.sh \
  | tee logs/12_build_wps_ungrib_rebuild.log
```

## 8. O que o script de build faz?

O script `scripts/legacy/12_build_wps_ungrib.sh` executa as seguintes ações:

```text
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

## 9. Resultado esperado

Ao final, deve existir:

```bash
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0/ungrib.exe
```

Verifique:

```bash
WPS_ROOT=/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0

ls -lh "$WPS_ROOT/ungrib.exe"
file "$WPS_ROOT/ungrib.exe"
ldd "$WPS_ROOT/ungrib.exe" | grep -Ei "not found|netcdf|jasper|png|zlib|hdf5|curl|gcc|gfortran|mpi|fabric" || true
```

O resultado esperado é:

```text
ungrib.exe existe
ungrib.exe é executável
ldd não mostra bibliotecas obrigatórias como "not found"
```

## 10. Teste mínimo do `ungrib.exe`

Rode:

```bash
"$WPS_ROOT/ungrib.exe" 2>&1 | head -40
```

É normal que ele reclame da ausência de `namelist.wps` se for executado fora de um diretório preparado. O objetivo desse teste simples é verificar se o executável inicia e não falha imediatamente por biblioteca ausente.

## 11. Arquivos do WPS usados depois

Depois da instalação, o workflow usa:

```text
ungrib.exe
  para converter GRIB em arquivos intermediários

link_grib.csh
  para criar links GRIBFILE.* no diretório de execução do ungrib

Vtable.GFS
  para informar ao ungrib como interpretar os campos do GFS
```

Esses arquivos não são produtos da matriz B. Eles são pré-requisitos para preparar os dados atmosféricos que serão usados para gerar as condições iniciais e as previsões MPAS.

## 12. Relação com o BFLOW

O WPS deve estar pronto antes da etapa NMC/BFLOW quando as amostras forem geradas a partir do GFS.

A relação é:

```text
WPS/ungrib gera entrada meteorológica para o MPAS
MPAS init gera condição inicial
MPAS atmosphere gera previsões f24 e f48
NMC calcula PTB_f48mf24
BFLOW organiza essas amostras
VBAL/HDIAG/NICAS usam essas amostras para calibrar a B
```

Portanto, a etapa WPS deve aparecer no tutorial antes de:

```text
gerar amostras NMC
preparar BFLOW
rodar VBAL
```

## 13. Problemas comuns

### 13.1. `WPS source directory not found`

Significa que o diretório abaixo ainda não existe:

```bash
/p/projetos/monan_das/joao.gerd/data/mpas-bmatrix-global/external/WPS/WPS-4.6.0
```

Solução: baixar/copiar o WPS para esse caminho antes da compilação.

### 13.2. `required command not found`

Significa que algum comando necessário não está disponível no ambiente, por exemplo:

```text
nc-config
nf-config
make
perl
csh
```

Solução: carregar o ambiente JACI correto com:

```bash
source scripts/load_jaci_env.sh
```

### 13.3. dependência GRIB2 ausente

Se aparecer erro relacionado a JasPer, PNG ou ZLIB, o script não encontrou uma das dependências necessárias para GRIB2.

Nesse caso, informe explicitamente os caminhos:

```bash
JASPERINC=/caminho/include \
JASPERLIB=/caminho/lib \
PNG_INC=/caminho/include \
PNG_LIB=/caminho/lib \
ZLIB_INC=/caminho/include \
ZLIB_LIB=/caminho/lib \
bash scripts/legacy/12_build_wps_ungrib.sh
```

### 13.4. `ungrib.exe was not created`

Verifique o log:

```bash
tail -120 logs/12_wps_compile_ungrib.log
```

Esse log mostra o erro real de compilação.
