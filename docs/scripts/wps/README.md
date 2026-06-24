# Referência dos scripts WPS

Esta seção documenta os scripts em `scripts/wps`, responsáveis por preparar e compilar o `ungrib.exe` do WPS para o workflow de geração da matriz B global do MPAS-JEDI.

## Fluxo público

A execução normal tem três etapas, sempre a partir da raiz do repositório:

```bash
source scripts/load_jaci_env.sh
bash scripts/wps/1_download_wps_assets.sh
bash scripts/wps/2_probe_wps_build_environment.sh --strict
bash scripts/wps/3_build_wps_ungrib.sh
```

O carregamento de `scripts/load_jaci_env.sh` é necessário apenas no JACI ou em outro ambiente no qual ele configure compiladores e bibliotecas. Os scripts não assumem nomes de módulos, versões ou caminhos específicos do JACI. Onde essas informações forem necessárias, a configuração do ambiente deve fornecê-las.

## Documentos por componente

| Componente | Responsabilidade | Documento |
| --- | --- | --- |
| `1_download_wps_assets.sh` | Download, validação e extração do WPS e dos dados geográficos | [Download e extração](1-download-wps-assets.md) |
| `2_probe_wps_build_environment.sh` | Diagnóstico somente de leitura de pré-requisitos | [Diagnóstico do ambiente](2-probe-wps-build-environment.md) |
| `3_build_wps_ungrib.sh` | Patch JasPer, configuração e compilação de `ungrib.exe` | [Build do ungrib](3-build-wps-ungrib.md) |
| `_common.sh` | Biblioteca de layout, logs e descoberta de dependências | [Biblioteca comum](common-library.md) |
| `_patches.sh` | Biblioteca interna do patch JasPer | [Biblioteca de patches](patches-library.md) |

O guia de instalação completo para uso no JACI permanece em [Instalação e validação do WPS/ungrib](../../install-wps-ungrib-jaci.md).

## Propriedades de segurança e reexecução

- Downloads só são reutilizados após validação por `tar -tzf`.
- Árvores ou dados já válidos são reaproveitados.
- Substituições de diretórios exigem `--force-source`, `--force-geog` ou `--force`.
- O diagnóstico não altera o sistema de arquivos.
- O build só remove artefatos gerados pelo próprio WPS e links simbólicos gerenciados no prefixo local de compatibilidade NetCDF.
- O patch JasPer verifica o estado da fonte antes de modificá-la e preserva um backup.

## Validação recomendada

Execute estes comandos após obter a branch:

```bash
bash -n scripts/wps/_common.sh
bash -n scripts/wps/_patches.sh
bash -n scripts/wps/1_download_wps_assets.sh
bash -n scripts/wps/2_probe_wps_build_environment.sh
bash -n scripts/wps/3_build_wps_ungrib.sh

shellcheck scripts/wps/_common.sh scripts/wps/_patches.sh scripts/wps/*.sh

bash scripts/wps/1_download_wps_assets.sh --help
bash scripts/wps/2_probe_wps_build_environment.sh --help
bash scripts/wps/3_build_wps_ungrib.sh --help
```

> **[TBD: ambiente JACI]** Confirmar, na configuração de ambiente efetivamente usada, os módulos e versões que fornecem NetCDF-C, NetCDF-Fortran, JasPer, libpng, zlib, C/C++ e Fortran. Os scripts deliberadamente não fixam esses detalhes.
