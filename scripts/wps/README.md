# Instalação portátil do WPS/ungrib

Este diretório contém as etapas para preparar o `ungrib.exe` do WPS, necessário para converter dados GFS em GRIB antes da criação de condições iniciais do MPAS.

Os scripts não dependem de uma conta específica. Eles localizam a raiz do repositório a partir da própria localização e aceitam variáveis de ambiente para qualquer diretório que precise ser personalizado.

## Sequência de instalação

A partir da raiz do repositório:

```bash
source scripts/load_jaci_env.sh

bash scripts/wps/10_download_wps_assets.sh
bash scripts/wps/11_probe_wps_build_environment.sh
bash scripts/wps/12_build_wps_ungrib.sh
```

O segundo passo é somente diagnóstico e não altera a árvore do WPS. Ele verifica os compiladores, NetCDF, JasPer, libpng e zlib antes da compilação.

## Diretórios padrão

Sem variáveis adicionais, os scripts usam uma das duas convenções abaixo:

- checkout comum: `<repositorio>/data`;
- checkout em `<workspace>/projects/mpas-bmatrix-global`: `<workspace>/data/mpas-bmatrix-global`.

Assim, no layout usual do JACI, com o clone em:

```text
/p/projetos/monan_das/$USER/projects/mpas-bmatrix-global
```

os arquivos são preparados em:

```text
/p/projetos/monan_das/$USER/data/mpas-bmatrix-global/external
```

A instalação não depende de `joao.gerd` nem exige que todos os usuários adotem esse layout.

## Personalização de caminhos

Defina `DATA_ROOT` quando os dados devem ficar em outro local:

```bash
export DATA_ROOT=/caminho/para/dados/mpas-bmatrix-global

bash scripts/wps/10_download_wps_assets.sh
bash scripts/wps/12_build_wps_ungrib.sh
```

Outras variáveis disponíveis:

```bash
REPO_ROOT=/caminho/para/mpas-bmatrix-global
EXTERNAL_ROOT=/caminho/para/external
DOWNLOAD_ROOT=/caminho/para/downloads
WPS_SRC_DIR=/caminho/para/WPS-4.6.0
LOG_ROOT=/caminho/para/logs
WPS_LOG_DIR=/caminho/para/logs/wps
```

## Dependências GRIB2

O build procura JasPer, libpng e zlib a partir dos prefixos retornados por `nc-config` e `nf-config`, além de `STACK_ROOT`, `SPACK_ROOT` e `SPACK_INSTALL_ROOT`, quando definidos.

Quando as bibliotecas estiverem fora dessas raízes, informe a instalação Spack ou outro prefixo de busca:

```bash
export WPS_DEP_SEARCH_ROOTS=/caminho/para/spack/install
bash scripts/wps/11_probe_wps_build_environment.sh
bash scripts/wps/12_build_wps_ungrib.sh
```

Como alternativa, informe os seis caminhos diretamente:

```bash
JASPERINC=/caminho/include \
JASPERLIB=/caminho/lib \
PNG_INC=/caminho/include \
PNG_LIB=/caminho/lib \
ZLIB_INC=/caminho/include \
ZLIB_LIB=/caminho/lib \
bash scripts/wps/12_build_wps_ungrib.sh
```

## Idempotência e reexecução

- `10_download_wps_assets.sh` valida os arquivos `.tar.gz`, reaproveita downloads e não extrai novamente uma árvore WPS válida ou dados geográficos já existentes.
- `11_probe_wps_build_environment.sh` é somente leitura; pode ser executado quantas vezes forem necessárias.
- `12_build_wps_ungrib.sh` não recompila quando `ungrib.exe` já existe e é executável. O diretório de compatibilidade NetCDF é atualizado com links simbólicos sem modificar as instalações originais de NetCDF.

Para ações destrutivas explícitas, use:

```bash
FORCE_WPS_SOURCE_REFRESH=true bash scripts/wps/10_download_wps_assets.sh
FORCE_WPS_GEOG_REFRESH=true bash scripts/wps/10_download_wps_assets.sh
FORCE_WPS_REBUILD=true bash scripts/wps/12_build_wps_ungrib.sh
```

O primeiro e o segundo comandos substituem, respectivamente, o código-fonte WPS e os dados geográficos no diretório selecionado. Use-os apenas quando essa substituição for desejada.

## Resultado esperado

Ao fim da compilação, recalcule o caminho portátil e verifique o executável:

```bash
source scripts/wps/_common.sh
ls -lh "$WPS_SRC_DIR/ungrib.exe"
```

O caminho definitivo sempre é mostrado pelos scripts como `WPS_SRC_DIR`. Use esse mesmo valor ao preencher os campos `wps.root`, `wps.ungrib_exe`, `wps.link_grib` e `wps.vtable_gfs` na configuração específica do seu workflow.
