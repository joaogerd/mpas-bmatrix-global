# `_common.sh`: biblioteca comum dos scripts WPS

## Objetivo

`_common.sh` centraliza o contrato operacional compartilhado pelos scripts WPS: resolução de diretórios, interpretação de booleanos, mensagens de log, validação de comandos e descoberta de diretórios de dependências GRIB2.

É uma biblioteca interna. Não é uma etapa do workflow e não deve ser executada diretamente:

```bash
source scripts/wps/_common.sh
```

A execução direta termina com código `2`, porque não conseguiria inicializar o shell chamador.

## Pré-requisitos e entradas

- Bash 4 ou superior;
- raiz válida do repositório com `pyproject.toml`;
- `dirname`, `basename`, `find` e `printf`.

A biblioteca aceita as seguintes variáveis antes de ser carregada:

| Variável | Função |
| --- | --- |
| `REPO_ROOT` | Força a raiz do checkout. |
| `DATA_ROOT` | Força a raiz de dados persistentes. |
| `EXTERNAL_ROOT` | Força a raiz de fontes e dados externos. |
| `DOWNLOAD_ROOT` | Força o diretório de arquivos baixados. |
| `LOG_ROOT` | Força a raiz dos logs. |
| `WPS_VERSION` | Define a tag do WPS; padrão `v4.6.0`. |
| `WPS_SRC_DIR` | Define a árvore WPS a utilizar. |
| `WPS_DEP_SEARCH_ROOTS` | Lista separada por `:` de raízes para busca de dependências. |
| `STACK_ROOT`, `SPACK_ROOT`, `SPACK_INSTALL_ROOT` | Raízes adicionais de dependências. |

## Saídas e efeitos

Após ser carregada, a biblioteca exporta:

```text
REPO_ROOT
DATA_ROOT
EXTERNAL_ROOT
DOWNLOAD_ROOT
LOG_ROOT
WPS_VERSION
WPS_SRC_DIR
```

A função `wps_collect_search_roots` preenche em memória o array `WPS_SEARCH_ROOTS`. Nenhum diretório ou arquivo é criado, removido ou modificado.

## Convenção de layout

Sem sobrescritas, a raiz de dados é calculada assim:

- `<repo>/data` para um clone em localização arbitrária;
- `<workspace>/data/mpas-bmatrix-global` quando o checkout está em `<workspace>/projects/mpas-bmatrix-global`.

Para conferir os valores efetivos:

```bash
source scripts/wps/_common.sh
wps_show_layout
```

## Funções públicas

| Função | Papel |
| --- | --- |
| `wps_log_info`, `wps_log_warn`, `wps_log_error` | Produzem mensagens padronizadas. |
| `wps_default_data_root` | Calcula a raiz padrão de dados. |
| `wps_is_true` | Interpreta `1`, `true`, `yes` e `on` como verdadeiro. |
| `wps_require_command` | Falha se algum comando informado não existir no `PATH`. |
| `wps_add_search_root` | Acrescenta diretório existente sem duplicá-lo. |
| `wps_collect_search_roots` | Compõe as raízes para busca de dependências. |
| `wps_find_include_root` | Localiza cabeçalhos sob as raízes coletadas. |
| `wps_find_library_dir` | Localiza bibliotecas sob as raízes coletadas. |
| `wps_show_layout` | Exibe a configuração de caminhos resolvida. |

## Idempotência

A variável de guarda `_MPAS_BMATRIX_WPS_COMMON_LOADED` evita redefinições quando o arquivo é carregado mais de uma vez na mesma sessão. Carregamentos subsequentes retornam sucesso sem recalcular ou alterar o estado.

## Troubleshooting

| Sintoma | Correção |
| --- | --- |
| Erro ao identificar a raiz do repositório | Execute a partir de um checkout válido ou defina `REPO_ROOT`. |
| Dependências não são localizadas | Informe `WPS_DEP_SEARCH_ROOTS` ou os diretórios explícitos na etapa de diagnóstico/build. |
| O layout aponta para área indesejada | Defina `DATA_ROOT` ou `EXTERNAL_ROOT` antes de chamar os scripts. |

## Relação com os outros scripts

Os três scripts públicos carregam esta biblioteca. Alterações em suas funções ou convenções de diretório têm efeito em todo o fluxo WPS; por isso, mudanças devem ser validadas com `bash -n` e `shellcheck` nos scripts dependentes.
