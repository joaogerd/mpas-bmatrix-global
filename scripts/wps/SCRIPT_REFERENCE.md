# Referência operacional dos scripts WPS

Este documento detalha o contrato operacional dos scripts em `scripts/wps`: entradas, efeitos, artefatos, idempotência e recuperação de falhas.

## Visão geral

A interface pública possui somente três etapas:

```bash
source scripts/load_jaci_env.sh
bash scripts/wps/1_download_wps_assets.sh
bash scripts/wps/2_probe_wps_build_environment.sh
bash scripts/wps/3_build_wps_ungrib.sh
```

| Script | Papel | Pode alterar arquivos? | Idempotência padrão |
| --- | --- | --- | --- |
| `1_download_wps_assets.sh` | Download, validação e extração do WPS e dados geográficos | Sim | Reutiliza arquivos e árvores válidos |
| `2_probe_wps_build_environment.sh` | Diagnóstico prévio do ambiente | Não | Sempre somente leitura |
| `3_build_wps_ungrib.sh` | Patch JasPer, configuração e compilação do `ungrib.exe` | Sim | Reutiliza executável consistente |
| `_common.sh` | Biblioteca compartilhada de caminhos e descoberta | Não, quando carregada | Pode ser carregada repetidamente |
| `_patches.sh` | Biblioteca interna de correções de fonte | Altera a fonte quando necessário | Idempotente |

## Convenções de caminho

`_common.sh` identifica `REPO_ROOT` a partir de `scripts/wps` e exporta:

| Variável | Valor padrão | Finalidade |
| --- | --- | --- |
| `DATA_ROOT` | `<repo>/data` ou `<workspace>/data/<repo>` | Raiz dos dados persistentes |
| `EXTERNAL_ROOT` | `$DATA_ROOT/external` | Fontes, bibliotecas e dados externos |
| `DOWNLOAD_ROOT` | `$EXTERNAL_ROOT/downloads` | Arquivos compactados baixados |
| `LOG_ROOT` | `$REPO_ROOT/logs` | Raiz dos logs |
| `WPS_VERSION` | `v4.6.0` | Tag do WPS |
| `WPS_SRC_DIR` | `$EXTERNAL_ROOT/WPS/WPS-<versão>` | Árvore extraída do WPS |

A descoberta de dependências considera `WPS_DEP_SEARCH_ROOTS`, `STACK_ROOT`, `SPACK_ROOT`, `SPACK_INSTALL_ROOT` e os prefixos retornados por `nc-config` e `nf-config`.

## 1. Download e extração

```bash
bash scripts/wps/1_download_wps_assets.sh
```

Variáveis principais:

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `WPS_GEOG_PACKAGE` | `low` | Seleciona o pacote geográfico `low` ou `high` |
| `WPS_VERSION` | `v4.6.0` | Seleciona a tag do WPS |
| `DATA_ROOT`, `EXTERNAL_ROOT`, `DOWNLOAD_ROOT`, `WPS_SRC_DIR` | Derivados por `_common.sh` | Sobrescrevem o layout |
| `FORCE_WPS_SOURCE_REFRESH` | `false` | Permite substituir uma árvore WPS existente |
| `FORCE_WPS_GEOG_REFRESH` | `false` | Permite substituir os dados geográficos existentes |

O script valida todos os arquivos compactados com `tar -tzf`, reutiliza downloads válidos e só substitui uma árvore existente quando a respectiva variável `FORCE_*` for informada.

Artefatos principais:

```text
$DOWNLOAD_ROOT/WPS-v4.6.0.tar.gz
$WPS_SRC_DIR/
$EXTERNAL_ROOT/WPS_GEOG/<pacote>/
$WPS_SRC_DIR/.mpas-bmatrix-global-wps-assets.env
```

## 2. Diagnóstico não destrutivo

```bash
bash scripts/wps/2_probe_wps_build_environment.sh
```

O script verifica a árvore WPS, comandos obrigatórios, prefixos NetCDF e os diretórios de headers/bibliotecas de JasPer, libpng e zlib. Por padrão ele apenas relata problemas. Em automação, use:

```bash
STRICT_WPS_PROBE=true bash scripts/wps/2_probe_wps_build_environment.sh
```

Quando a descoberta automática não alcançar a instalação, use `WPS_DEP_SEARCH_ROOTS` ou informe explicitamente `JASPERINC`, `JASPERLIB`, `PNG_INC`, `PNG_LIB`, `ZLIB_INC` e `ZLIB_LIB`.

## 3. Patch, configuração e compilação

```bash
bash scripts/wps/3_build_wps_ungrib.sh
```

Pré-requisitos: árvore WPS válida, ambiente de compiladores/NetCDF carregado e dependências GRIB2 detectadas ou informadas explicitamente.

Antes de qualquer decisão de reaproveitar `ungrib.exe`, o script aplica internamente o patch JasPer em `ungrib/src/ngl/g2/dec_jpeg2000.c`. Ele substitui a chamada obsoleta `jpc_decode()` pela API pública `jas_image_decode(..., jas_image_strtofmt("jpc"), ...)`. Não existe script público separado para esse patch. A alteração é aplicada uma vez, preserva um backup da fonte original e falha se o arquivo estiver em estado inesperado.

Se a fonte corrigida for mais nova que `ungrib.exe`, a recompilação é feita automaticamente. Para forçar a etapa completa:

```bash
FORCE_WPS_REBUILD=true bash scripts/wps/3_build_wps_ungrib.sh
```

Variáveis adicionais:

| Variável | Padrão | Efeito |
| --- | --- | --- |
| `WPS_CONFIGURE_OPTION` | `1` | Opção numérica enviada para `./configure --nowrf` |
| `NETCDF_COMPAT_DIR` | `$EXTERNAL_ROOT/netcdf_compat` | Prefixo local de compatibilidade NetCDF |
| `WPS_LOG_DIR` | `$LOG_ROOT/wps` | Diretório de logs |
| `FC`, `CC` | `gfortran`, `gcc` se `ftn` e `cc` não existirem | Compiladores alternativos |

O prefixo de compatibilidade NetCDF é atualizado somente por links simbólicos; instalações externas não são modificadas. Durante o build, são criados `configure.wps.original`, os logs de configuração e compilação, arquivos de proveniência e `ungrib.exe`.

## Recuperação de falhas

| Sintoma | Ação recomendada |
| --- | --- |
| Arquivo compactado inválido | Execute novamente; o download temporário será substituído |
| Árvore WPS existente, mas inválida | Inspecione e use `FORCE_WPS_SOURCE_REFRESH=true` somente se puder substituí-la |
| Dependência GRIB2 ausente | Defina `WPS_DEP_SEARCH_ROOTS` ou os seis caminhos explicitamente |
| `ungrib.exe` não foi criado | Consulte `$WPS_LOG_DIR/configure.log` e `$WPS_LOG_DIR/compile-ungrib.log` |
| `ldd` indica `not found` | Recarregue o ambiente que fornece a biblioteca e refaça o build |
| Opção de compilador inadequada | Ajuste `WPS_CONFIGURE_OPTION` e use `FORCE_WPS_REBUILD=true` |

## Verificação final

```bash
source scripts/wps/_common.sh
ls -lh "$WPS_SRC_DIR/ungrib.exe"
```

Use `WPS_SRC_DIR` nos campos `wps.root`, `wps.ungrib_exe`, `wps.link_grib` e `wps.vtable_gfs` do workflow.
