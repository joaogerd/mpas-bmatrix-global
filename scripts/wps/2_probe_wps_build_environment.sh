#!/usr/bin/env bash
#
# Nome: 2_probe_wps_build_environment.sh
# Descrição: Verifica, sem modificar a instalação, se o ambiente está pronto
#   para configurar e compilar o WPS/ungrib.
#
# Finalidade no workflow:
#   Diagnostica a árvore WPS, comandos, prefixos NetCDF e dependências GRIB2
#   antes de iniciar a compilação. É a segunda etapa pública e pode ser usada
#   isoladamente para investigar problemas de ambiente.
#
# Uso:
#   bash scripts/wps/2_probe_wps_build_environment.sh [opções]
#
# Opções:
#   --strict        Retorna código diferente de zero se qualquer requisito
#                   obrigatório estiver ausente.
#   -h, --help      Exibe esta ajuda e não modifica arquivos.
#
# Pré-requisitos:
#   - Bash 4 ou superior;
#   - checkout válido do repositório mpas-bmatrix-global;
#   - para validação completa: WPS extraído, NetCDF-C, NetCDF-Fortran,
#     make, perl, csh, Python 3, JasPer, libpng e zlib disponíveis.
#
# Variáveis de ambiente relevantes:
#   REPO_ROOT, DATA_ROOT, EXTERNAL_ROOT, WPS_SRC_DIR, WPS_DEP_SEARCH_ROOTS,
#   STACK_ROOT, SPACK_ROOT, SPACK_INSTALL_ROOT, JASPERINC, JASPERLIB, PNG_INC,
#   PNG_LIB, ZLIB_INC, ZLIB_LIB e STRICT_WPS_PROBE.
#
# Diretórios e arquivos criados ou modificados:
#   Nenhum. O script é estritamente de leitura e apenas escreve o diagnóstico
#   em stdout/stderr.
#
# Idempotência:
#   O script não altera a árvore WPS, dependências ou variáveis persistentes.
#   Pode ser executado repetidamente com o mesmo resultado para o mesmo
#   ambiente carregado.
#
# Autor: João Gerd Zell de Mattos
# Projeto: mpas-bmatrix-global
# Última atualização: 2026-06-24
#

usage() {
  cat <<'EOF'
Uso:
  bash scripts/wps/2_probe_wps_build_environment.sh [opções]

Executa diagnóstico somente de leitura para o build de WPS/ungrib.

Opções:
  --strict        Retorna 1 quando algum requisito estiver ausente.
  -h, --help      Exibe esta ajuda.

Variáveis de ambiente:
  WPS_DEP_SEARCH_ROOTS=/prefixo1:/prefixo2
      Raízes adicionais para localizar JasPer, libpng e zlib.
  JASPERINC, JASPERLIB, PNG_INC, PNG_LIB, ZLIB_INC, ZLIB_LIB
      Diretórios explícitos de cabeçalhos e bibliotecas GRIB2.
  STRICT_WPS_PROBE=true
      Equivalente a --strict.

Exemplos:
  bash scripts/wps/2_probe_wps_build_environment.sh
  bash scripts/wps/2_probe_wps_build_environment.sh --strict
  WPS_DEP_SEARCH_ROOTS=/caminho/spack/install \
    bash scripts/wps/2_probe_wps_build_environment.sh --strict
EOF
}

STRICT_WPS_PROBE="${STRICT_WPS_PROBE:-false}"

# Processa a única opção operacional antes de carregar a biblioteca, para que
# --help permaneça disponível mesmo fora de um checkout válido.
while (($# > 0)); do
  case "$1" in
    --strict)
      STRICT_WPS_PROBE=true
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

printf '%s\n' "=== Contexto da verificação ==="
printf '%s\n' \
  "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "hostname=$(hostname)" \
  "user=${USER:-unknown}" \
  "STRICT_WPS_PROBE=${STRICT_WPS_PROBE}"
wps_show_layout
printf '\n'

printf '%s\n' "=== Código-fonte do WPS ==="
source_ok=true
for required_file in configure compile link_grib.csh ungrib/Variable_Tables/Vtable.GFS; do
  if [[ -e "${WPS_SRC_DIR}/${required_file}" ]]; then
    printf 'OK: %s\n' "${WPS_SRC_DIR}/${required_file}"
  else
    printf 'AUSENTE: %s\n' "${WPS_SRC_DIR}/${required_file}"
    source_ok=false
  fi
done
printf '\n'

printf '%s\n' "=== Comandos necessários ==="
commands_ok=true
for command_name in nc-config nf-config make perl csh python3 sed awk grep find; do
  if path="$(command -v "${command_name}" 2>/dev/null)"; then
    printf 'OK:      %-12s %s\n' "${command_name}" "${path}"
  else
    printf 'AUSENTE: %-12s\n' "${command_name}"
    commands_ok=false
  fi
done
printf '\n'

NC_PREFIX=""
NF_PREFIX=""
if command -v nc-config >/dev/null 2>&1; then
  NC_PREFIX="$(nc-config --prefix 2>/dev/null || true)"
fi
if command -v nf-config >/dev/null 2>&1; then
  NF_PREFIX="$(nf-config --prefix 2>/dev/null || true)"
fi

printf '%s\n' "=== NetCDF ==="
printf '%s\n' \
  "NETCDF-C prefix=${NC_PREFIX:-AUSENTE}" \
  "NETCDF-Fortran prefix=${NF_PREFIX:-AUSENTE}"
if command -v nc-config >/dev/null 2>&1; then
  printf '%s\n' "--- nc-config --libs ---"
  nc-config --libs || true
fi
if command -v nf-config >/dev/null 2>&1; then
  printf '%s\n' "--- nf-config --flibs ---"
  nf-config --flibs || true
fi
printf '\n'

# Inicializa as raízes de busca a partir das variáveis explícitas, da pilha
# carregada e dos prefixos NetCDF detectados. Não cria nem altera diretórios.
wps_collect_search_roots "${NC_PREFIX}" "${NF_PREFIX}"

printf '%s\n' "=== Raízes de busca de dependências GRIB2 ==="
if ((${#WPS_SEARCH_ROOTS[@]} == 0)); then
  printf '%s\n' \
    "Nenhuma raiz local foi detectada." \
    "Defina WPS_DEP_SEARCH_ROOTS=/caminho/para/install[:/outro/caminho] e execute novamente."
else
  printf '%s\n' "${WPS_SEARCH_ROOTS[@]}"
fi
printf '\n'

JASPERINC="${JASPERINC:-$(wps_find_include_root 'include/jasper/jasper.h')}"
JASPERLIB="${JASPERLIB:-$(wps_find_library_dir 'libjasper.so*' 'libjasper.a')}"
PNG_INC="${PNG_INC:-$(wps_find_include_root 'include/png.h')}"
PNG_LIB="${PNG_LIB:-$(wps_find_library_dir 'libpng.so*' 'libpng.a' 'libpng16.so*' 'libpng16.a')}"
ZLIB_INC="${ZLIB_INC:-$(wps_find_include_root 'include/zlib.h')}"
ZLIB_LIB="${ZLIB_LIB:-$(wps_find_library_dir 'libz.so*' 'libz.a')}"

printf '%s\n' "=== Dependências GRIB2 ==="
dependencies_ok=true
for variable_name in JASPERINC JASPERLIB PNG_INC PNG_LIB ZLIB_INC ZLIB_LIB; do
  value="${!variable_name:-}"
  if [[ -n "${value}" && -d "${value}" ]]; then
    printf 'OK:      %-10s %s\n' "${variable_name}" "${value}"
  else
    printf 'AUSENTE: %-10s %s\n' "${variable_name}" "${value:-}"
    dependencies_ok=false
  fi
done
printf '\n'

printf '%s\n' "=== Diagnóstico ==="
if "${source_ok}" && "${commands_ok}" && "${dependencies_ok}"; then
  printf '%s\n' \
    "Ambiente aparentemente pronto para a compilação." \
    "Execute: bash scripts/wps/3_build_wps_ungrib.sh"
else
  printf '%s\n' \
    "O ambiente ainda não está completo para compilar o ungrib.exe." \
    "Os caminhos JASPERINC, JASPERLIB, PNG_INC, PNG_LIB, ZLIB_INC e ZLIB_LIB podem ser informados explicitamente." \
    "Para uma instalação Spack fora das raízes detectadas, informe WPS_DEP_SEARCH_ROOTS."
fi

if wps_is_true "${STRICT_WPS_PROBE}" && (! "${source_ok}" || ! "${commands_ok}" || ! "${dependencies_ok}"); then
  exit 1
fi
