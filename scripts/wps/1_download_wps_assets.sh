#!/usr/bin/env bash
#
# Nome: 1_download_wps_assets.sh
# Descrição: Baixa, valida e extrai o código-fonte do WPS e o pacote de dados
#   geográficos selecionado.
#
# Finalidade no workflow:
#   Prepara os artefatos externos necessários à compilação de ungrib.exe. Esta é
#   a primeira etapa pública da preparação portátil do WPS para o workflow de
#   geração da matriz B global do MPAS-JEDI.
#
# Uso:
#   bash scripts/wps/1_download_wps_assets.sh [opções]
#
# Opções:
#   --force-source  Substitui a árvore WPS existente após baixar/reutilizar o
#                   arquivo compactado validado.
#   --force-geog    Substitui o pacote de dados geográficos já extraído.
#   --force         Equivale a --force-source --force-geog.
#   -h, --help      Exibe esta ajuda e não modifica arquivos.
#
# Pré-requisitos:
#   - Bash 4 ou superior;
#   - curl ou wget para download;
#   - tar e find;
#   - acesso de rede a github.com e www2.mmm.ucar.edu;
#   - checkout válido do repositório mpas-bmatrix-global.
#
# Variáveis de ambiente relevantes:
#   REPO_ROOT, DATA_ROOT, EXTERNAL_ROOT, DOWNLOAD_ROOT, LOG_ROOT, WPS_VERSION,
#   WPS_SRC_DIR, WPS_GEOG_PACKAGE (low|high), FORCE_WPS_SOURCE_REFRESH e
#   FORCE_WPS_GEOG_REFRESH.
#
# Diretórios e arquivos criados ou modificados:
#   - $DOWNLOAD_ROOT/WPS-$WPS_VERSION.tar.gz;
#   - $DOWNLOAD_ROOT/geog_<resolução>_res_mandatory.tar.gz;
#   - $WPS_SRC_DIR;
#   - $EXTERNAL_ROOT/WPS_GEOG/{low_res_mandatory,high_res_mandatory};
#   - $WPS_SRC_DIR/.mpas-bmatrix-global-wps-assets.env.
#
# Idempotência:
#   Arquivos compactados válidos, a árvore WPS válida e dados geográficos já
#   extraídos são reutilizados. Substituições exigem --force-source,
#   --force-geog, --force ou as variáveis FORCE_WPS_* correspondentes.
#
# Autor: João Gerd Zell de Mattos
# Projeto: mpas-bmatrix-global
# Última atualização: 2026-06-24
#

usage() {
  cat <<'EOF'
Uso:
  bash scripts/wps/1_download_wps_assets.sh [opções]

Baixa, valida e extrai o WPS e os dados geográficos usados por geogrid.exe.

Opções:
  --force-source  Substitui a árvore WPS existente.
  --force-geog    Substitui os dados geográficos existentes.
  --force         Equivale a --force-source --force-geog.
  -h, --help      Exibe esta ajuda.

Variáveis de ambiente:
  WPS_GEOG_PACKAGE=low|high          Seleciona o pacote geográfico (padrão: low).
  WPS_VERSION=v4.6.0                 Tag do WPS a obter.
  DATA_ROOT, EXTERNAL_ROOT,
  DOWNLOAD_ROOT, WPS_SRC_DIR         Personalizam o layout.
  FORCE_WPS_SOURCE_REFRESH=true      Equivalente a --force-source.
  FORCE_WPS_GEOG_REFRESH=true        Equivalente a --force-geog.

Exemplos:
  bash scripts/wps/1_download_wps_assets.sh
  WPS_GEOG_PACKAGE=high bash scripts/wps/1_download_wps_assets.sh
  bash scripts/wps/1_download_wps_assets.sh --force-source
EOF
}

FORCE_WPS_SOURCE_REFRESH="${FORCE_WPS_SOURCE_REFRESH:-false}"
FORCE_WPS_GEOG_REFRESH="${FORCE_WPS_GEOG_REFRESH:-false}"

# Interpreta as opções antes de carregar a biblioteca, para que --help funcione
# mesmo quando o script é chamado fora de uma árvore de trabalho válida.
while (($# > 0)); do
  case "$1" in
    --force-source)
      FORCE_WPS_SOURCE_REFRESH=true
      ;;
    --force-geog)
      FORCE_WPS_GEOG_REFRESH=true
      ;;
    --force)
      FORCE_WPS_SOURCE_REFRESH=true
      FORCE_WPS_GEOG_REFRESH=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERRO: opção desconhecida: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

WPS_GEOG_PACKAGE="${WPS_GEOG_PACKAGE:-low}"
WPS_TARBALL="WPS-${WPS_VERSION}.tar.gz"
WPS_URL="https://github.com/wrf-model/WPS/archive/refs/tags/${WPS_VERSION}.tar.gz"
WPS_SRC_PARENT="$(dirname "${WPS_SRC_DIR}")"

case "${WPS_GEOG_PACKAGE}" in
  low)
    GEOG_URL="https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_low_res_mandatory.tar.gz"
    GEOG_TARBALL="geog_low_res_mandatory.tar.gz"
    GEOG_DIR="${EXTERNAL_ROOT}/WPS_GEOG/low_res_mandatory"
    ;;
  high)
    GEOG_URL="https://www2.mmm.ucar.edu/wrf/src/wps_files/geog_high_res_mandatory.tar.gz"
    GEOG_TARBALL="geog_high_res_mandatory.tar.gz"
    GEOG_DIR="${EXTERNAL_ROOT}/WPS_GEOG/high_res_mandatory"
    ;;
  *)
    wps_log_error "WPS_GEOG_PACKAGE deve ser 'low' ou 'high'; recebido: ${WPS_GEOG_PACKAGE}"
    exit 2
    ;;
esac

# Valida a estrutura de um arquivo .tar.gz sem extraí-lo. Entrada: caminho do
# arquivo. Retorna sucesso quando tar consegue listar seu conteúdo. Não altera
# o arquivo nem o diretório de trabalho.
archive_is_valid() {
  tar -tzf "$1" >/dev/null 2>&1
}

# Baixa um arquivo compactado de forma atômica e o valida antes de publicá-lo.
#
# Entradas:
#   $1: URL de origem; $2: caminho de destino.
# Efeitos:
#   Cria ou substitui somente arquivos em DOWNLOAD_ROOT. O arquivo temporário
#   <destino>.part é removido após falha ou renomeado atomicamente após sucesso.
# Dependências:
#   curl ou wget, e tar para validação.
# Idempotência:
#   Um arquivo de destino válido é reutilizado sem download.
fetch_archive() {
  local url="$1"
  local destination="$2"
  local temporary="${destination}.part"

  if [[ -f "${destination}" ]] && archive_is_valid "${destination}"; then
    wps_log_info "Arquivo já disponível e válido: ${destination}"
    return 0
  fi

  rm -f "${destination}" "${temporary}"
  wps_log_info "Baixando: ${url}"
  wps_log_info "Destino: ${destination}"

  if command -v curl >/dev/null 2>&1; then
    curl --fail --location --retry 5 --retry-delay 10 --output "${temporary}" "${url}"
  elif command -v wget >/dev/null 2>&1; then
    wget --output-document="${temporary}" "${url}"
  else
    wps_log_error "É necessário ter curl ou wget no PATH."
    exit 1
  fi

  if ! archive_is_valid "${temporary}"; then
    rm -f "${temporary}"
    wps_log_error "Download inválido ou incompleto: ${url}"
    exit 1
  fi

  mv "${temporary}" "${destination}"
}

# Confirma a presença dos arquivos mínimos esperados na árvore WPS. Entrada:
# nenhuma; usa WPS_SRC_DIR. Saída: código de retorno. Não altera arquivos.
wps_source_is_valid() {
  [[ -f "${WPS_SRC_DIR}/configure" ]] \
    && [[ -f "${WPS_SRC_DIR}/compile" ]] \
    && [[ -f "${WPS_SRC_DIR}/link_grib.csh" ]] \
    && [[ -f "${WPS_SRC_DIR}/ungrib/Variable_Tables/Vtable.GFS" ]]
}

# Verifica se um diretório existe e possui ao menos uma entrada. Entrada: caminho
# de diretório. Saída: código de retorno. Não cria nem remove arquivos.
directory_has_content() {
  [[ -d "$1" ]] && find "$1" -mindepth 1 -maxdepth 1 -print -quit | grep -q .
}

mkdir -p "${DOWNLOAD_ROOT}" "${WPS_SRC_PARENT}"

printf '%s\n' "=== Configuração do download do WPS ==="
wps_show_layout
printf '%s\n' \
  "WPS_GEOG_PACKAGE=${WPS_GEOG_PACKAGE}" \
  "WPS_GEOG_DIR=${GEOG_DIR}" \
  "FORCE_WPS_SOURCE_REFRESH=${FORCE_WPS_SOURCE_REFRESH}" \
  "FORCE_WPS_GEOG_REFRESH=${FORCE_WPS_GEOG_REFRESH}" \
  ""

fetch_archive "${WPS_URL}" "${DOWNLOAD_ROOT}/${WPS_TARBALL}"
fetch_archive "${GEOG_URL}" "${DOWNLOAD_ROOT}/${GEOG_TARBALL}"

printf '\n%s\n' "=== Código-fonte do WPS ==="
if wps_source_is_valid && ! wps_is_true "${FORCE_WPS_SOURCE_REFRESH}"; then
  wps_log_info "Código-fonte já extraído e validado: ${WPS_SRC_DIR}"
else
  if [[ -e "${WPS_SRC_DIR}" ]]; then
    if ! wps_is_true "${FORCE_WPS_SOURCE_REFRESH}"; then
      wps_log_error "${WPS_SRC_DIR} existe, mas não contém uma árvore WPS válida."
      wps_log_error "Use --force-source ou FORCE_WPS_SOURCE_REFRESH=true somente se puder substituir esse diretório."
      exit 1
    fi
    wps_log_warn "Substituindo árvore WPS existente por solicitação explícita: ${WPS_SRC_DIR}"
    rm -rf "${WPS_SRC_DIR}"
  fi

  tar -xzf "${DOWNLOAD_ROOT}/${WPS_TARBALL}" -C "${WPS_SRC_PARENT}"
  if ! wps_source_is_valid; then
    wps_log_error "O arquivo foi extraído, mas a árvore WPS esperada não foi encontrada: ${WPS_SRC_DIR}"
    exit 1
  fi
  wps_log_info "Código-fonte extraído: ${WPS_SRC_DIR}"
fi

printf '\n%s\n' "=== Dados geográficos do WPS ==="
if directory_has_content "${GEOG_DIR}" && ! wps_is_true "${FORCE_WPS_GEOG_REFRESH}"; then
  wps_log_info "Dados geográficos já disponíveis: ${GEOG_DIR}"
else
  if [[ -e "${GEOG_DIR}" ]] && wps_is_true "${FORCE_WPS_GEOG_REFRESH}"; then
    wps_log_warn "Substituindo dados geográficos por solicitação explícita: ${GEOG_DIR}"
    rm -rf "${GEOG_DIR}"
  fi
  mkdir -p "${GEOG_DIR}"
  tar -xzf "${DOWNLOAD_ROOT}/${GEOG_TARBALL}" -C "${GEOG_DIR}"
  if ! directory_has_content "${GEOG_DIR}"; then
    wps_log_error "A extração dos dados geográficos não produziu arquivos em ${GEOG_DIR}"
    exit 1
  fi
  wps_log_info "Dados geográficos extraídos: ${GEOG_DIR}"
fi

cat > "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-assets.env.tmp" <<EOF
WPS_VERSION=${WPS_VERSION}
WPS_SOURCE_ARCHIVE=${DOWNLOAD_ROOT}/${WPS_TARBALL}
WPS_GEOG_PACKAGE=${WPS_GEOG_PACKAGE}
WPS_GEOG_DIR=${GEOG_DIR}
EOF
mv "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-assets.env.tmp" \
  "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-assets.env"

printf '\n%s\n' "=== Resultado ==="
printf '%s\n' \
  "WPS_SRC_DIR=${WPS_SRC_DIR}" \
  "WPS_GEOG_DIR=${GEOG_DIR}" \
  "Próximo passo: source scripts/load_jaci_env.sh && bash scripts/wps/2_probe_wps_build_environment.sh"
