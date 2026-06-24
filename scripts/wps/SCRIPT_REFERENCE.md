# Referência operacional dos scripts WPS

Este documento descreve o contrato operacional dos scripts em `scripts/wps`. Ele complementa o guia de instalação do diretório e detalha entradas, efeitos, artefatos, idempotência e recuperação de cada etapa.

## Visão geral

A instalação prepara apenas o `ungrib.exe` do WPS para converter arquivos GFS em GRIB. Os scripts são independentes de usuário e derivam os diretórios a partir da raiz do checkout. No layout usual do JACI, um clone em `<workspace>/projects/mpas-bmatrix-global` usa, por padrão, `<workspace>/data/mpas-bmatrix-global` como `DATA_ROOT`.

A sequência normal é:

```bash
source scripts/load_jaci_env.sh
bash scripts/wps/10_download_wps_assets.sh
bash scripts/wps/11_probe_wps_build_environment.sh
bash scripts/wps/12_build_wps_ungrib.sh
```

| Script | Papel | Pode alterar arquivos? | Idempotência padrão |
| --- | --- | --- | --- |
| `_common.sh` | Biblioteca compartilhada de caminhos e descoberta de dependências | Não, quando apenas carregado | Pode ser carregado repetidamente |
| `10_download_wps_assets.sh` | Download, validação e extração do WPS e dados geográficos | Sim, em `DOWNLOAD_ROOT` e `EXTERNAL_ROOT` | Reutiliza arquivos e árvores válidos |
| `11_probe_wps_build_environment.sh` | Diagnóstico prévio do ambiente de compilação | Não | Sempre somente leitura |
| `12_build_wps_ungrib.sh` | Configuração e compilação do `ungrib.exe` | Sim, na árvore WPS, logs e compatibilidade NetCDF | Não recompila um executável válido |

## Convenções de caminho e biblioteca compartilhada

### `_common.sh`

Carregue este arquivo apenas por `source`:

```bash
source scripts/wps/_common.sh
```

Ele identifica `REPO_ROOT` e exporta as variáveis abaixo:

| Variável | Valor padrão | Finalidade |
| --- | --- | --- |
| `REPO_ROOT` | Raiz identificada a partir de `scripts/wps` | Checkout do repositório |
| `DATA_ROOT` | `<repo>/data` ou `<workspace>/data/<repo>` | Raiz dos dados persistentes |
| `EXTERNAL_ROOT` | `$DATA_ROOT/external` | Fontes, bibliotecas e dados externos |
| `DOWNLOAD_ROOT` | `$EXTERNAL_ROOT/downloads` | Arquivos compactados baixados |
| `LOG_ROOT` | `$REPO_ROOT/logs` | Raiz dos logs gerados no checkout |
| `WPS_VERSION` | `v4.6.0` | Tag do WPS a obter |
| `WPS_SRC_DIR` | `$EXTERNAL_ROOT/WPS/WPS-<versão>` | Árvore extraída do WPS |

Também disponibiliza funções para interpretar valores booleanos, verificar comandos, coletar raízes de busca e localizar cabeçalhos e bibliotecas do JasPer, libpng e zlib.

A busca de dependências considera, nesta ordem, `WPS_DEP_SEARCH_ROOTS`, `STACK_ROOT`, `SPACK_ROOT`, `SPACK_INSTALL_ROOT` e os prefixos retornados por `nc-config` e `nf-config`. `WPS_DEP_SEARCH_ROOTS` aceita uma lista de diretórios separada por dois-pontos.

## Download e extração

### `10_download_wps_assets.sh`

Execução:

```bash
bash scripts/wps/10_download_wps_assets.sh
```

Não recebe argumentos posicionais. As variáveis relevantes são:

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `WPS_GEOG_PACKAGE` | `low` | Seleciona o pacote geográfico `low` ou `high` |
| `WPS_VERSION` | `v4.6.0` | Seleciona a tag do código-fonte WPS |
| `DATA_ROOT`, `EXTERNAL_ROOT`, `DOWNLOAD_ROOT`, `WPS_SRC_DIR` | Derivados pelo `_common.sh` | Sobrescrevem o layout portátil |
| `FORCE_WPS_SOURCE_REFRESH` | `false` | Permite substituir uma árvore WPS existente |
| `FORCE_WPS_GEOG_REFRESH` | `false` | Permite substituir os dados geográficos existentes |

O script baixa `WPS-<versão>.tar.gz` da tag oficial do WPS e o pacote geográfico selecionado. `curl` é preferido; `wget` é usado caso `curl` não esteja disponível. Todo arquivo compactado é validado com `tar -tzf` antes de ser considerado utilizável.

Artefatos principais:

```text
$DOWNLOAD_ROOT/WPS-v4.6.0.tar.gz
$DOWNLOAD_ROOT/geog_<resolução>_res_mandatory.tar.gz
$WPS_SRC_DIR/
$EXTERNAL_ROOT/WPS_GEOG/<pacote>/
$WPS_SRC_DIR/.mpas-bmatrix-global-wps-assets.env
```

Uma árvore de fontes é aceita como válida somente se contiver `configure`, `compile`, `link_grib.csh` e `ungrib/Variable_Tables/Vtable.GFS`. Dados geográficos existentes também são preservados quando o diretório contém arquivos.

Quando uma árvore existente for inválida, o script interrompe a execução em vez de removê-la automaticamente. Use uma das opções abaixo somente quando a substituição for intencional:

```bash
FORCE_WPS_SOURCE_REFRESH=true bash scripts/wps/10_download_wps_assets.sh
FORCE_WPS_GEOG_REFRESH=true bash scripts/wps/10_download_wps_assets.sh
```

## Diagnóstico não destrutivo

### `11_probe_wps_build_environment.sh`

Execução:

```bash
bash scripts/wps/11_probe_wps_build_environment.sh
```

Esta etapa não executa `./configure`, não modifica a árvore WPS e não cria arquivos. Ela verifica:

- os arquivos obrigatórios da árvore WPS;
- os comandos `nc-config`, `nf-config`, `make`, `perl`, `csh`, `python3`, `sed`, `awk`, `grep` e `find`;
- os prefixos NetCDF retornados por `nc-config --prefix` e `nf-config --prefix`;
- os diretórios de include e biblioteca para JasPer, libpng e zlib.

Por padrão, a falta de um pré-requisito é relatada no diagnóstico, mas não altera o status de saída. Para usar a verificação em automação, CI ou script de submissão, defina:

```bash
STRICT_WPS_PROBE=true bash scripts/wps/11_probe_wps_build_environment.sh
```

Com `STRICT_WPS_PROBE=true`, o retorno é `1` quando a árvore WPS, os comandos obrigatórios ou qualquer uma das seis variáveis de dependência não puder ser validada.

As dependências podem ser especificadas manualmente quando a descoberta automática não alcançar a instalação:

```bash
JASPERINC=/caminho/include \
JASPERLIB=/caminho/lib \
PNG_INC=/caminho/include \
PNG_LIB=/caminho/lib \
ZLIB_INC=/caminho/include \
ZLIB_LIB=/caminho/lib \
bash scripts/wps/11_probe_wps_build_environment.sh
```

## Configuração e compilação

### `12_build_wps_ungrib.sh`

Execução:

```bash
bash scripts/wps/12_build_wps_ungrib.sh
```

Pré-requisitos:

1. a etapa de download deve ter criado uma árvore WPS válida em `WPS_SRC_DIR`;
2. o ambiente de compiladores e NetCDF deve estar carregado;
3. a sondagem deve localizar JasPer, libpng e zlib, ou os seis caminhos devem ser fornecidos explicitamente.

Variáveis adicionais:

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `WPS_CONFIGURE_OPTION` | `1` | Opção numérica enviada para `./configure --nowrf` |
| `FORCE_WPS_REBUILD` | `false` | Obriga limpeza, configuração e recompilação |
| `NETCDF_COMPAT_DIR` | `$EXTERNAL_ROOT/netcdf_compat` | Prefixo local de compatibilidade NetCDF |
| `WPS_LOG_DIR` | `$LOG_ROOT/wps` | Diretório dos logs de configuração e compilação |
| `FC`, `CC` | `gfortran`, `gcc` se `ftn` e `cc` não existirem | Compiladores alternativos |

Quando `ungrib.exe` já existe e é executável, a compilação não é repetida. Para refazer explicitamente a etapa:

```bash
FORCE_WPS_REBUILD=true bash scripts/wps/12_build_wps_ungrib.sh
```

O script cria `NETCDF_COMPAT_DIR/include` e `NETCDF_COMPAT_DIR/lib`, removendo apenas links simbólicos produzidos por execuções anteriores. Em seguida, cria novos links para headers e bibliotecas NetCDF/HDF5 necessárias. Arquivos regulares existentes nesse diretório não são removidos e as instalações originais de NetCDF não são alteradas.

Durante a configuração, o script:

1. executa `./clean -a` e remove produtos de configuração e build do `ungrib`;
2. executa `./configure --nowrf` com a opção selecionada;
3. preserva a configuração gerada como `configure.wps.original`;
4. ajusta os compiladores e `COMPRESSION_INC`/`COMPRESSION_LIBS` em `configure.wps`;
5. executa `./compile ungrib`;
6. exige que `ungrib.exe` seja executável e que `ldd` não reporte bibliotecas ausentes, quando `ldd` estiver disponível.

Artefatos:

```text
$WPS_LOG_DIR/configure.log
$WPS_LOG_DIR/compile-ungrib.log
$NETCDF_COMPAT_DIR/.mpas-bmatrix-global-wps-netcdf-compat.env
$WPS_SRC_DIR/configure.wps.original
$WPS_SRC_DIR/.mpas-bmatrix-global-wps-build.env
$WPS_SRC_DIR/ungrib.exe
```

O arquivo `.mpas-bmatrix-global-wps-build.env` registra a versão do WPS, prefixos NetCDF, diretórios das dependências GRIB2 e a opção escolhida no menu de configuração. Ele permite revisar a proveniência do executável sem repetir a descoberta do ambiente.

## Recuperação de falhas

| Sintoma | Causa provável | Ação recomendada |
| --- | --- | --- |
| Arquivo compactado inválido | Download incompleto ou corrompido | Execute novamente; o arquivo temporário é removido antes de nova tentativa |
| Árvore WPS existente, mas inválida | Extração interrompida ou diretório incompatível | Inspecione o diretório; use `FORCE_WPS_SOURCE_REFRESH=true` somente se puder substituí-lo |
| Dependência GRIB2 ausente | Instalação Spack fora das raízes conhecidas | Defina `WPS_DEP_SEARCH_ROOTS` ou informe os seis caminhos manualmente |
| `ungrib.exe` não foi criado | Falha em `configure` ou `compile` | Consulte `$WPS_LOG_DIR/configure.log` e `$WPS_LOG_DIR/compile-ungrib.log` |
| `ldd` indica `not found` | Biblioteca dinâmica ausente no ambiente de execução | Recarregue os módulos/ambiente que fornecem a biblioteca e refaça o build se necessário |
| Configuração WPS inadequada | Opção errada de compilador no menu | Ajuste `WPS_CONFIGURE_OPTION` e execute com `FORCE_WPS_REBUILD=true` |

## Verificação final

Depois de uma compilação bem-sucedida, recalcule o caminho portátil e verifique o executável:

```bash
source scripts/wps/_common.sh
ls -lh "$WPS_SRC_DIR/ungrib.exe"
```

Use o valor mostrado para `WPS_SRC_DIR` ao preencher `wps.root`, `wps.ungrib_exe`, `wps.link_grib` e `wps.vtable_gfs` na configuração do workflow que consome o WPS.
