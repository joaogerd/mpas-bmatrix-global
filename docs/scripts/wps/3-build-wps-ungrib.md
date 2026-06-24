# `3_build_wps_ungrib.sh`: patch, configuração e compilação

## Visão geral e objetivo

`3_build_wps_ungrib.sh` é a etapa que produz `$WPS_SRC_DIR/ungrib.exe`. O script aplica uma correção de compatibilidade com JasPer, prepara um prefixo local de compatibilidade NetCDF, executa `./configure --nowrf`, ajusta apenas as entradas necessárias de `configure.wps` e chama `./compile ungrib`.

O resultado é usado pelo workflow para converter arquivos GFS/GRIB em arquivos intermediários do WPS. Ele não executa a conversão em si.

## Escopo e limitações

O script:

- requer uma árvore WPS previamente extraída;
- requer NetCDF-C e NetCDF-Fortran utilizáveis no ambiente atual;
- localiza JasPer, libpng e zlib automaticamente ou por variáveis explícitas;
- gera somente `ungrib.exe`, usando `./configure --nowrf`.

Ele não instala bibliotecas, não escolhe módulos do JACI e não constrói WRF, `geogrid.exe` ou `metgrid.exe`.

## Pré-requisitos

Antes de executar, complete e valide as etapas anteriores:

```bash
bash scripts/wps/1_download_wps_assets.sh
source scripts/load_jaci_env.sh
bash scripts/wps/2_probe_wps_build_environment.sh --strict
```

Também são necessários `make`, `perl`, `csh`, `python3`, `sed`, `awk`, `grep`, `find`, `nc-config` e `nf-config`. O script seleciona `ftn` e `cc` quando disponíveis; caso contrário, usa `FC`/`CC` ou `gfortran`/`gcc`.

> **[TBD: ambiente JACI]** Confirmar a opção numérica do menu `./configure --nowrf` correspondente ao conjunto de compiladores e MPI carregado. O padrão `1` é preservado como valor atual do script, mas não deve ser interpretado como escolha universal do JACI.

## Variáveis de ambiente

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `FORCE_WPS_REBUILD` | `false` | Autoriza limpar artefatos gerados e recompilar. |
| `WPS_CONFIGURE_OPTION` | `1` | Número enviado ao menu de `./configure --nowrf`. |
| `WPS_LOG_DIR` | `$LOG_ROOT/wps` | Local de `configure.log` e `compile-ungrib.log`. |
| `NETCDF_COMPAT_DIR` | `$EXTERNAL_ROOT/netcdf_compat` | Prefixo local de links NetCDF para o WPS. |
| `WPS_DEP_SEARCH_ROOTS` | vazio | Raízes adicionais para JasPer/libpng/zlib. |
| `JASPERINC`, `JASPERLIB` | descoberta | Cabeçalhos e bibliotecas JasPer. |
| `PNG_INC`, `PNG_LIB` | descoberta | Cabeçalhos e bibliotecas libpng. |
| `ZLIB_INC`, `ZLIB_LIB` | descoberta | Cabeçalhos e bibliotecas zlib. |
| `FC`, `CC` | `gfortran`, `gcc` se necessário | Compiladores alternativos. |

## Opções de linha de comando

```text
--force                 Limpa os artefatos gerados pelo WPS e recompila.
--configure-option N    Informa a opção numérica N ao ./configure --nowrf.
-h, --help              Exibe a ajuda sem modificar arquivos.
```

`--force` equivale a `FORCE_WPS_REBUILD=true`. A limpeza remove apenas `configure.wps`, `configure.wps.original`, `ungrib.exe` e `ungrib/src/ungrib.exe`, que são artefatos de build do WPS. O conteúdo original extraído e os dados geográficos não são removidos.

## Execução passo a passo

Build padrão:

```bash
bash scripts/wps/3_build_wps_ungrib.sh
```

Escolhendo a opção de configuração de modo explícito:

```bash
bash scripts/wps/3_build_wps_ungrib.sh --configure-option 1
```

Recompilação solicitada pelo usuário:

```bash
bash scripts/wps/3_build_wps_ungrib.sh --force
```

Uso de dependências fora das raízes investigadas:

```bash
export WPS_DEP_SEARCH_ROOTS=/caminho/para/install
bash scripts/wps/3_build_wps_ungrib.sh
```

## Patch JasPer

Antes do build, o script chama a biblioteca `_patches.sh`. Ela verifica `ungrib/src/ngl/g2/dec_jpeg2000.c` e substitui uma única chamada obsoleta a `jpc_decode()` pela API pública `jas_image_decode(..., jas_image_strtofmt("jpc"), ...)`.

A operação é idempotente: uma fonte já corrigida não é modificada. Quando a correção é aplicada, o original é salvo como `dec_jpeg2000.c.orig-jpc-decode`. Se a fonte contiver estado inesperado, o processo falha sem tentar uma substituição ampla.

## Prefixo de compatibilidade NetCDF

O WPS costuma esperar `include/` e `lib/` abaixo de um único prefixo `NETCDF`. O script cria `$NETCDF_COMPAT_DIR` apenas com links simbólicos para os arquivos de NetCDF-C, NetCDF-Fortran e bibliotecas transitivas localizados nos prefixos retornados por `nc-config` e `nf-config`.

Em reexecuções, somente links simbólicos no diretório de compatibilidade são removidos e recriados. Arquivos regulares eventualmente existentes ali não são removidos. As instalações NetCDF originais não são modificadas.

## Arquivos e diretórios criados

```text
$WPS_LOG_DIR/configure.log
$WPS_LOG_DIR/compile-ungrib.log
$NETCDF_COMPAT_DIR/include/              # links simbólicos
$NETCDF_COMPAT_DIR/lib/                  # links simbólicos
$NETCDF_COMPAT_DIR/.mpas-bmatrix-global-wps-netcdf-compat.env
$WPS_SRC_DIR/configure.wps
$WPS_SRC_DIR/configure.wps.original
$WPS_SRC_DIR/ungrib.exe
$WPS_SRC_DIR/.mpas-bmatrix-global-wps-build.env
$WPS_SRC_DIR/.mpas-bmatrix-global-wps-patches.env
```

## Comportamento idempotente

- Uma fonte já corrigida pelo patch JasPer é reutilizada.
- Um `ungrib.exe` existente é reutilizado quando a fonte não é mais nova e `--force` não foi informado.
- Se o patch atualizar a fonte, ou se o alvo do patch for mais novo que `ungrib.exe`, a recompilação é ativada automaticamente.
- Links simbólicos de compatibilidade NetCDF são atualizados sem tocar em arquivos regulares e sem alterar bibliotecas externas.

## Como validar o resultado

```bash
source scripts/wps/_common.sh
ls -lh "$WPS_SRC_DIR/ungrib.exe"
file "$WPS_SRC_DIR/ungrib.exe"
ldd "$WPS_SRC_DIR/ungrib.exe" | grep 'not found' && exit 1 || true
```

Inspecione também os logs:

```bash
tail -n 80 "$WPS_LOG_DIR/configure.log"
tail -n 80 "$WPS_LOG_DIR/compile-ungrib.log"
```

É esperado que `ungrib.exe` exija um `namelist.wps` e arquivos GRIB quando for executado diretamente em um diretório vazio. A validação inicial é a existência do binário executável e a ausência de bibliotecas ausentes em `ldd`.

## Troubleshooting

| Sintoma | Causa provável | Ação recomendada |
| --- | --- | --- |
| `WPS_SRC_DIR` não encontrado | A etapa de download não foi executada ou o caminho foi alterado. | Execute o script 1 ou corrija `WPS_SRC_DIR`. |
| `nc-config`/`nf-config` retornam prefixos inválidos | Mistura de ambientes ou instalação incompleta. | Recarregue o ambiente de compilação e execute o diagnóstico estrito. |
| Dependência GRIB2 ausente | A biblioteca não está nas raízes conhecidas. | Use `WPS_DEP_SEARCH_ROOTS` ou os seis diretórios explícitos. |
| `configure.wps` não foi criado | Opção inválida ou falha no menu do WPS. | Consulte `configure.log`; confirme `WPS_CONFIGURE_OPTION`. |
| `ungrib.exe` não foi criado | Erro de compilação ou ligação. | Consulte `compile-ungrib.log` e valide a descoberta de bibliotecas. |
| `ldd` mostra `not found` | Biblioteca dinâmica não está disponível em execução. | Recarregue o ambiente que a fornece e faça rebuild. |
| Patch JasPer falha por estado inesperado | Fonte WPS já foi alterada manualmente ou pertence a outra versão. | Inspecione o arquivo e restaure uma árvore WPS conhecida antes de prosseguir. |

## Reinstalação e atualização

Para recompilar com as mesmas fontes, use `--force`. Para mudar a versão do WPS, defina `WPS_VERSION`, execute novamente o download e depois o build. Para recomeçar de uma árvore limpa, use `1_download_wps_assets.sh --force-source` e só então faça o build; não remova diretórios manualmente sem confirmar as variáveis de layout.

## Relação com o workflow

Após sucesso, use `WPS_SRC_DIR` nos campos de configuração do workflow:

```yaml
wps:
  root: /caminho/para/WPS-4.6.0
  ungrib_exe: /caminho/para/WPS-4.6.0/ungrib.exe
  link_grib: /caminho/para/WPS-4.6.0/link_grib.csh
  vtable_gfs: /caminho/para/WPS-4.6.0/ungrib/Variable_Tables/Vtable.GFS
```
