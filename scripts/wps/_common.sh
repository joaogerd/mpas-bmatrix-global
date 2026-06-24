#!/usr/bin/env bash
#
# Nome: _common.sh
# Descrição: Biblioteca compartilhada para os scripts de preparação e compilação
#   do WPS/ungrib.
#
# Finalidade no workflow:
#   Resolve o layout portátil de diretórios, valida pré-requisitos básicos e
#   localiza dependências usadas pelo WPS. Este arquivo é uma biblioteca interna;
#   deve ser carregado pelos scripts numerados e não executado diretamente.
#
# Uso:
#   source scripts/wps/_common.sh
#
# Pré-requisitos:
#   - Bash 4 ou superior;
#   - checkout válido do repositório mpas-bmatrix-global, identificado por
#     pyproject.toml na raiz;
#   - comandos padrão: dirname, basename, find e printf.
#
# Variáveis de ambiente relevantes:
#   REPO_ROOT, DATA_ROOT, EXTERNAL_ROOT, DOWNLOAD_ROOT, LOG_ROOT, WPS_VERSION,
#   WPS_SRC_DIR, WPS_DEP_SEARCH_ROOTS, STACK_ROOT, SPACK_ROOT e
#   SPACK_INSTALL_ROOT.
#
# Diretórios e arquivos criados ou modificados:
#   Nenhum. As funções exportam caminhos calculados e consultam diretórios
#   existentes. O array WPS_SEARCH_ROOTS é preenchido apenas em memória.
#
# Idempotência:
#   Pode ser carregado repetidamente na mesma sessão. A proteção de carregamento
#   evita redefinições e efeitos repetidos.
#
# Autor: João Gerd Zell de Mattos
# Projeto: mpas-bmatrix-global
# Última atualização: 2026-06-24
#

# Esta biblioteca deve ser carregada. Executá-la não inicializa o ambiente do
# processo chamador e poderia induzir o uso incorreto das funções exportadas.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '%s\n' "ERRO: ${BASH_SOURCE[0]} é uma biblioteca; use: source ${BASH_SOURCE[0]}" >&2
  exit 2
fi

# Evita redefinições quando a biblioteca é carregada mais de uma vez.
if [[ -n "${_MPAS_BMATRIX_WPS_COMMON_LOADED:-}" ]]; then
  return 0
fi
_MPAS_BMATRIX_WPS_COMMON_LOADED=1

WPS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="${REPO_ROOT:-$(cd "${WPS_SCRIPT_DIR}/../.." && pwd -P)}"

if [[ ! -f "${REPO_ROOT}/pyproject.toml" ]]; then
  printf '%s\n' "ERRO: não foi possível identificar a raiz do repositório." >&2
  printf '%s\n' "Defina REPO_ROOT=/caminho/para/mpas-bmatrix-global." >&2
  return 1
fi

# Registra mensagens padronizadas. Entrada: texto livre. Saída: uma linha em
# stdout ou stderr. Não altera arquivos nem o código de retorno do chamador.
wps_log_info() {
  printf '[INFO] %s\n' "$*"
}

wps_log_warn() {
  printf '[AVISO] %s\n' "$*" >&2
}

wps_log_error() {
  printf '[ERRO] %s\n' "$*" >&2
}

# Calcula a raiz persistente de dados. Não recebe argumentos e escreve o caminho
# resultante em stdout. No layout <workspace>/projects/<repo>, usa
# <workspace>/data/<repo>; em outros layouts, usa <repo>/data.
wps_default_data_root() {
  local parent workspace

  parent="$(dirname "${REPO_ROOT}")"
  if [[ "$(basename "${parent}")" == "projects" ]]; then
    workspace="$(dirname "${parent}")"
    printf '%s/data/%s\n' "${workspace}" "$(basename "${REPO_ROOT}")"
  else
    printf '%s/data\n' "${REPO_ROOT}"
  fi
}

DATA_ROOT="${DATA_ROOT:-$(wps_default_data_root)}"
EXTERNAL_ROOT="${EXTERNAL_ROOT:-${DATA_ROOT}/external}"
DOWNLOAD_ROOT="${DOWNLOAD_ROOT:-${EXTERNAL_ROOT}/downloads}"
LOG_ROOT="${LOG_ROOT:-${REPO_ROOT}/logs}"

WPS_VERSION="${WPS_VERSION:-v4.6.0}"
WPS_SRC_DIR="${WPS_SRC_DIR:-${EXTERNAL_ROOT}/WPS/WPS-${WPS_VERSION#v}}"

export REPO_ROOT DATA_ROOT EXTERNAL_ROOT DOWNLOAD_ROOT LOG_ROOT WPS_VERSION WPS_SRC_DIR

# Interpreta valores booleanos de variáveis de ambiente. Entrada: um valor
# opcional. Retorna sucesso para 1, true, yes e on (sem distinção de maiúsculas)
# e falha para qualquer outro valor. Não imprime nem altera arquivos.
wps_is_true() {
  case "${1:-false}" in
    1|true|TRUE|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

# Verifica se todos os comandos passados como argumentos estão no PATH. Retorna
# falha no primeiro comando ausente, com mensagem de diagnóstico em stderr.
# Não instala pacotes nem modifica o ambiente.
wps_require_command() {
  local command_name

  for command_name in "$@"; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
      wps_log_error "Comando obrigatório não encontrado no PATH: ${command_name}"
      return 1
    fi
  done
}

# Acrescenta um diretório existente ao array WPS_SEARCH_ROOTS, preservando a
# ordem e eliminando duplicações. Entrada: um candidato a diretório. Não cria,
# remove ou modifica diretórios no disco.
wps_add_search_root() {
  local candidate="${1:-}"
  local root

  [[ -n "${candidate}" && -d "${candidate}" ]] || return 0

  for root in "${WPS_SEARCH_ROOTS[@]:-}"; do
    [[ "${root}" == "${candidate}" ]] && return 0
  done
  WPS_SEARCH_ROOTS+=("${candidate}")
}

# Preenche WPS_SEARCH_ROOTS com diretórios para busca de JasPer, libpng e zlib.
# Entradas: prefixos de instalações já identificadas, por exemplo os retornados
# por nc-config e nf-config. WPS_DEP_SEARCH_ROOTS tem prioridade e aceita
# múltiplos caminhos separados por ':'. A função somente consulta diretórios.
wps_collect_search_roots() {
  local root prefix parent
  local -a explicit_roots=()

  WPS_SEARCH_ROOTS=()

  if [[ -n "${WPS_DEP_SEARCH_ROOTS:-}" ]]; then
    IFS=':' read -r -a explicit_roots <<< "${WPS_DEP_SEARCH_ROOTS}"
    for root in "${explicit_roots[@]}"; do
      wps_add_search_root "${root}"
    done
  fi

  for root in "${STACK_ROOT:-}" "${SPACK_ROOT:-}" "${SPACK_INSTALL_ROOT:-}"; do
    wps_add_search_root "${root}"
  done

  for prefix in "$@"; do
    [[ -n "${prefix:-}" && -d "${prefix}" ]] || continue
    wps_add_search_root "${prefix}"
    parent="$(dirname "${prefix}")"
    wps_add_search_root "${parent}"
    parent="$(dirname "${parent}")"
    wps_add_search_root "${parent}"
    parent="$(dirname "${parent}")"
    wps_add_search_root "${parent}"
  done
}

# Procura um cabeçalho abaixo das raízes coletadas. Entrada: caminho relativo do
# cabeçalho a localizar, por exemplo include/png.h. Saída: diretório de include
# apropriado ou saída vazia. A busca pode percorrer instalações grandes; não
# altera seu conteúdo.
wps_find_include_root() {
  local header_path="$1"
  local root found

  for root in "${WPS_SEARCH_ROOTS[@]:-}"; do
    found="$(find "${root}" -type f -path "*/${header_path}" -print -quit 2>/dev/null || true)"
    [[ -n "${found}" ]] || continue

    if [[ "${header_path}" == "include/jasper/jasper.h" ]]; then
      dirname "$(dirname "${found}")"
    else
      dirname "${found}"
    fi
    return 0
  done
  return 0
}

# Procura a primeira biblioteca compatível com os padrões recebidos. Entrada:
# um ou mais padrões de nome de arquivo. Saída: o diretório que contém a
# biblioteca ou saída vazia. Não altera instalações externas.
wps_find_library_dir() {
  local root pattern found

  for root in "${WPS_SEARCH_ROOTS[@]:-}"; do
    for pattern in "$@"; do
      found="$(find "${root}" \( -type f -o -type l \) -name "${pattern}" -print -quit 2>/dev/null || true)"
      [[ -n "${found}" ]] || continue
      dirname "${found}"
      return 0
    done
  done
  return 0
}

# Exibe o layout efetivo resolvido pela biblioteca. Não recebe argumentos, não
# altera o sistema de arquivos e serve apenas a diagnóstico.
wps_show_layout() {
  printf '%s\n' \
    "REPO_ROOT=${REPO_ROOT}" \
    "DATA_ROOT=${DATA_ROOT}" \
    "EXTERNAL_ROOT=${EXTERNAL_ROOT}" \
    "DOWNLOAD_ROOT=${DOWNLOAD_ROOT}" \
    "LOG_ROOT=${LOG_ROOT}" \
    "WPS_VERSION=${WPS_VERSION}" \
    "WPS_SRC_DIR=${WPS_SRC_DIR}"
}
