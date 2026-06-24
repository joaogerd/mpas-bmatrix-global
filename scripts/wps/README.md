# Instalação portátil do WPS/ungrib

Este diretório prepara o `ungrib.exe` do WPS, usado para converter GFS/GRIB em arquivos intermediários para a preparação das condições iniciais do MPAS.

A interface pública possui apenas três etapas, executadas a partir da raiz do repositório:

```bash
source scripts/load_jaci_env.sh

bash scripts/wps/1_download_wps_assets.sh
bash scripts/wps/2_probe_wps_build_environment.sh
bash scripts/wps/3_build_wps_ungrib.sh
```

`2_probe_wps_build_environment.sh` é somente diagnóstico e não modifica a árvore WPS. `3_build_wps_ungrib.sh` aplica automaticamente o patch de compatibilidade com JasPer antes de configurar ou compilar: ele substitui a chamada obsoleta `jpc_decode()` por `jas_image_decode(..., jas_image_strtofmt("jpc"), ...)` em `ungrib/src/ngl/g2/dec_jpeg2000.c`.

Não há uma quarta etapa pública para esse patch: ele é uma dependência interna do build, implementada em `_patches.sh`. O build é idempotente e recompila quando a fonte corrigida for mais nova que `ungrib.exe`.

## Diretórios padrão

Os scripts localizam a raiz do checkout automaticamente. Sem variáveis adicionais, usam:

- `<repositorio>/data`, para um clone em local arbitrário;
- `<workspace>/data/mpas-bmatrix-global`, quando o checkout está em `<workspace>/projects/mpas-bmatrix-global`.

No layout usual do JACI:

```text
/p/projetos/monan_das/$USER/projects/mpas-bmatrix-global
```

os dados são instalados em:

```text
/p/projetos/monan_das/$USER/data/mpas-bmatrix-global/external
```

## Personalização de caminhos

```bash
export DATA_ROOT=/caminho/para/dados/mpas-bmatrix-global
bash scripts/wps/1_download_wps_assets.sh
bash scripts/wps/3_build_wps_ungrib.sh
```

As principais sobrescritas são:

```bash
REPO_ROOT=/caminho/para/mpas-bmatrix-global
EXTERNAL_ROOT=/caminho/para/external
DOWNLOAD_ROOT=/caminho/para/downloads
WPS_SRC_DIR=/caminho/para/WPS-4.6.0
LOG_ROOT=/caminho/para/logs
WPS_LOG_DIR=/caminho/para/logs/wps
```

## Dependências GRIB2

O build detecta JasPer, libpng e zlib a partir de `nc-config`, `nf-config`, `STACK_ROOT`, `SPACK_ROOT` e `SPACK_INSTALL_ROOT`. Caso a instalação esteja fora dessas raízes:

```bash
export WPS_DEP_SEARCH_ROOTS=/caminho/para/spack/install
bash scripts/wps/2_probe_wps_build_environment.sh
bash scripts/wps/3_build_wps_ungrib.sh
```

Também é possível definir `JASPERINC`, `JASPERLIB`, `PNG_INC`, `PNG_LIB`, `ZLIB_INC` e `ZLIB_LIB` explicitamente.

## Idempotência e reexecução

- `1_download_wps_assets.sh` reutiliza arquivos válidos e instalações já extraídas.
- `2_probe_wps_build_environment.sh` é somente leitura.
- `3_build_wps_ungrib.sh` reaproveita um `ungrib.exe` consistente e atualiza o prefixo NetCDF somente por links simbólicos.

As substituições destrutivas exigem uma escolha explícita:

```bash
FORCE_WPS_SOURCE_REFRESH=true bash scripts/wps/1_download_wps_assets.sh
FORCE_WPS_GEOG_REFRESH=true bash scripts/wps/1_download_wps_assets.sh
FORCE_WPS_REBUILD=true bash scripts/wps/3_build_wps_ungrib.sh
```

## Verificação

```bash
source scripts/wps/_common.sh
ls -lh "$WPS_SRC_DIR/ungrib.exe"
```

Use o `WPS_SRC_DIR` mostrado pelos scripts nos campos `wps.root`, `wps.ungrib_exe`, `wps.link_grib` e `wps.vtable_gfs` da configuração do workflow.
