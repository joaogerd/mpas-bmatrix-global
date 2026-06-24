# `1_download_wps_assets.sh`: download e extração do WPS

## Visão geral e objetivo

`1_download_wps_assets.sh` prepara os artefatos externos usados pelo WPS: o código-fonte da tag selecionada e um pacote de dados geográficos obrigatórios. É a primeira etapa pública da instalação do `ungrib.exe` e pode ser executada de forma independente, desde que o checkout do repositório exista e haja acesso à rede.

O script não compila o WPS. A compilação é responsabilidade de [`3_build_wps_ungrib.sh`](3-build-wps-ungrib.md).

## Escopo e limitações

O script obtém apenas:

- o arquivo de código-fonte do WPS publicado no GitHub;
- o pacote geográfico obrigatório de baixa ou alta resolução publicado pelo NCAR/UCAR.

Ele não instala compiladores, NetCDF, JasPer, libpng ou zlib; também não executa `geogrid.exe`. O pacote `low` é o padrão. A escolha entre `low` e `high` deve considerar espaço disponível e a necessidade do experimento.

## Pré-requisitos

- Bash 4 ou superior;
- `tar`, `find` e ferramentas básicas do sistema;
- `curl` ou `wget` no `PATH`;
- acesso de rede a `github.com` e `www2.mmm.ucar.edu`;
- checkout válido identificado por `pyproject.toml` na raiz.

No JACI, carregue antes o ambiente que forneça conectividade e ferramentas básicas. Não há módulo específico assumido pelo script.

> **[TBD: ambiente JACI]** Confirmar a política de acesso externo dos nós de login e, se necessário, baixar os arquivos em área com conectividade e copiar os arquivos compactados para `$DOWNLOAD_ROOT`.

## Estrutura de diretórios

A biblioteca `_common.sh` resolve os caminhos automaticamente. Em um checkout comum, o padrão é:

```text
<repo>/data/
├── external/
│   ├── downloads/
│   │   ├── WPS-v4.6.0.tar.gz
│   │   └── geog_low_res_mandatory.tar.gz
│   ├── WPS/WPS-4.6.0/
│   └── WPS_GEOG/low_res_mandatory/
└── ...
```

Quando o checkout estiver em `<workspace>/projects/mpas-bmatrix-global`, a raiz padrão passa a ser `<workspace>/data/mpas-bmatrix-global`. Os valores efetivos são impressos no início da execução.

## Variáveis de ambiente

| Variável | Padrão | Uso |
| --- | --- | --- |
| `WPS_VERSION` | `v4.6.0` | Tag do WPS a baixar. |
| `WPS_GEOG_PACKAGE` | `low` | Pacote geográfico: `low` ou `high`. |
| `DATA_ROOT` | Calculado pelo layout | Raiz dos dados persistentes. |
| `EXTERNAL_ROOT` | `$DATA_ROOT/external` | Fontes, downloads e dados externos. |
| `DOWNLOAD_ROOT` | `$EXTERNAL_ROOT/downloads` | Arquivos compactados. |
| `WPS_SRC_DIR` | `$EXTERNAL_ROOT/WPS/WPS-<versão>` | Árvore WPS resultante. |
| `FORCE_WPS_SOURCE_REFRESH` | `false` | Autoriza substituir a árvore WPS. |
| `FORCE_WPS_GEOG_REFRESH` | `false` | Autoriza substituir os dados geográficos. |

## Opções de linha de comando

```text
--force-source  Substitui a árvore WPS existente.
--force-geog    Substitui o diretório de dados geográficos existente.
--force         Equivale a --force-source --force-geog.
-h, --help      Exibe a ajuda sem modificar arquivos.
```

As opções de força equivalem às variáveis `FORCE_WPS_SOURCE_REFRESH=true` e `FORCE_WPS_GEOG_REFRESH=true`. Use-as apenas após confirmar que os diretórios apontados pelas variáveis de ambiente correspondem à instalação que pode ser substituída.

## Execução passo a passo

Na raiz do repositório:

```bash
bash scripts/wps/1_download_wps_assets.sh
```

Para selecionar os dados de alta resolução:

```bash
WPS_GEOG_PACKAGE=high bash scripts/wps/1_download_wps_assets.sh
```

Para usar uma área de dados fora do layout padrão:

```bash
export DATA_ROOT=/caminho/para/dados/mpas-bmatrix-global
bash scripts/wps/1_download_wps_assets.sh
```

Para recuperar uma árvore WPS existente, mas inválida, após inspeção:

```bash
bash scripts/wps/1_download_wps_assets.sh --force-source
```

## Comportamento idempotente

O script valida cada arquivo compactado com `tar -tzf`. Um download válido é reutilizado e não é transferido novamente. Uma árvore WPS é reutilizada somente quando contém `configure`, `compile`, `link_grib.csh` e `ungrib/Variable_Tables/Vtable.GFS`; dados geográficos são reutilizados quando o diretório já possui conteúdo.

Por padrão, uma árvore WPS existente e inválida produz erro em vez de ser apagada. Os diretórios só são removidos após uma solicitação explícita de força.

## Arquivos e diretórios produzidos

- `$DOWNLOAD_ROOT/WPS-$WPS_VERSION.tar.gz`;
- `$DOWNLOAD_ROOT/geog_low_res_mandatory.tar.gz` ou `geog_high_res_mandatory.tar.gz`;
- `$WPS_SRC_DIR`;
- `$EXTERNAL_ROOT/WPS_GEOG/low_res_mandatory` ou `high_res_mandatory`;
- `$WPS_SRC_DIR/.mpas-bmatrix-global-wps-assets.env`, com proveniência básica.

## Como validar o resultado

```bash
source scripts/wps/_common.sh
ls -ld "$WPS_SRC_DIR"
test -f "$WPS_SRC_DIR/configure"
test -f "$WPS_SRC_DIR/ungrib/Variable_Tables/Vtable.GFS"
```

Em seguida, execute o diagnóstico sem alterações:

```bash
bash scripts/wps/2_probe_wps_build_environment.sh --strict
```

## Troubleshooting

| Sintoma | Causa provável | Correção |
| --- | --- | --- |
| `curl` e `wget` ausentes | Ferramentas de download não estão no `PATH`. | Carregue ou instale uma delas antes de executar. |
| `download inválido ou incompleto` | Falha de rede, página de erro ou transferência interrompida. | Execute novamente; o `.part` é removido e o download é repetido. |
| Diretório WPS existe, mas é inválido | Extração anterior incompleta ou caminho incorreto. | Inspecione o diretório e use `--force-source` apenas se puder substituí-lo. |
| Pacote geográfico não cabe no disco | Espaço insuficiente na área de dados. | Use `WPS_GEOG_PACKAGE=low`, escolha outra `DATA_ROOT` ou libere espaço. |
| Sem acesso externo no JACI | Política de rede do nó. | Baixe em local autorizado e copie os arquivos compactados para `$DOWNLOAD_ROOT`. |

## Remoção, atualização e reinstalação

Para apagar a instalação manualmente, confirme o layout com `wps_show_layout` e remova somente diretórios pertencentes a esta instalação. O script não oferece remoção automática para evitar apagar dados incorretos.

Para trocar a versão do WPS, defina `WPS_VERSION` e execute novamente; isso cria uma árvore diferente por padrão. Para reinstalar a mesma versão, use `--force-source`. Para trocar o pacote geográfico, defina `WPS_GEOG_PACKAGE` e, se necessário, `--force-geog`.

## Relação com o workflow

O resultado é consumido por `2_probe_wps_build_environment.sh` e `3_build_wps_ungrib.sh`. Após compilar, use o caminho `WPS_SRC_DIR` nos campos `wps.root`, `wps.ungrib_exe`, `wps.link_grib` e `wps.vtable_gfs` da configuração do workflow.
