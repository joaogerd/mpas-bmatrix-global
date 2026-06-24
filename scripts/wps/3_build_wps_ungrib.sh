#!/usr/bin/env bash
#
# Nome: 3_build_wps_ungrib.sh
# Descrição: Corrige a compatibilidade com JasPer, configura o WPS e compila
#   ungrib.exe com o layout portátil do repositório.
#
# Finalidade no workflow:
#   Conclui a preparação do WPS para converter GFS/GRIB em arquivos
#   intermediários consumidos pela preparação de condições iniciais do MPAS.
#   É a terceira etapa pública, executada após o download e o diagnóstico.
#
# Uso:
#   bash scripts/wps/3_build_wps_ungrib.sh [opções]
#
# Opções:
#   --force                 Limpa artefatos gerados pelo WPS e recompila
#                           ungrib.exe.
#   --configure-option N    Escolhe a opção numérica N do menu ./configure.
#   -h, --help              Exibe esta ajuda e não modifica arquivos.
#
# Pré-requisitos:
#   - Bash 4 ou superior;
#   - árvore WPS válida, obtida por 1_download_wps_assets.sh;
#   - ambiente de compilação carregado, incluindo NetCDF-C e NetCDF-Fortran;
#   - make, perl, csh, python3, sed, awk, grep e find;
#   - JasPer, libpng e zlib detectáveis ou informados explicitamente.
#
# Variáveis de ambiente relevantes:
#   REPO_ROOT, DATA_ROOT, EXTERNAL_ROOT, WPS_SRC_DIR, WPS_LOG_DIR,
#   WPS_CONFIGURE_OPTION, FORCE_WPS_REBUILD, NETCDF_COMPAT_DIR,
#   WPS_DEP_SEARCH_ROOTS, JASPERINC, JASPERLIB, PNG_INC, PNG_LIB, ZLIB_INC,
#   ZLIB_LIB, FC e CC.
#
# Diretórios e arquivos criados ou modificados:
#   - $NETCDF_COMPAT_DIR/{include,lib} (somente links simbólicos gerenciados);
#   - $WPS_LOG_DIR/configure.log e $WPS_LOG_DIR/compile-ungrib.log;
#   - $WPS_SRC_DIR/configure.wps e configure.wps.original;
#   - $WPS_SRC_DIR/ungrib.exe;
#   - arquivos .mpas-bmatrix-global-wps-*.env na árvore WPS;
#   - dec_jpeg2000.c e seu backup, somente quando o patch JasPer for necessário.
#
# Idempotência:
#   O patch JasPer é aplicado apenas uma vez; um ungrib.exe consistente é
#   reutilizado. Uma recompilação automática ocorre quando a fonte corrigida é
#   mais nova que o executável. --force ou FORCE_WPS_REBUILD=true limpa somente
#   artefatos gerados pelo build WPS e recompila.
#
# Autor: João Gerd Zell de Mattos
# Projeto: mpas-bmatrix-global
# Última atualização: 2026-06-24
#

usage() {
  cat <<'EOF'
Uso:
  bash scripts/wps/3_build_wps_ungrib.sh [opções]

Aplica o patch JasPer necessário, configura o WPS sem WRF e compila ungrib.exe.

Opções:
  --force                 Limpa os artefatos gerados pelo build e recompila.
  --configure-option N    Opção numérica enviada a ./configure --nowrf.
  -h, --help              Exibe esta ajuda.

Variáveis de ambiente:
  FORCE_WPS_REBUILD=true  Equivalente a --force.
  WPS_CONFIGURE_OPTION=1  Opção do menu ./configure (padrão: 1).
  NETCDF_COMPAT_DIR=DIR   Prefixo local composto por links NetCDF.
  WPS_LOG_DIR=DIR         Diretório para configure.log e compile-ungrib.log.
  WPS_DEP_SEARCH_ROOTS    Raízes adicionais para JasPer, libpng e zlib.
  JASPERINC, JASPERLIB, PNG_INC, PNG_LIB, ZLIB_INC, ZLIB_LIB
                           Sobrescrevem a descoberta automática.
  FC, CC                  Compiladores alternativos quando ftn/cc não existem.

Exemplos:
  bash scripts/wps/3_build_wps_ungrib.sh
  bash scripts/wps/3_build_wps_ungrib.sh --configure-option 1
  bash scripts/wps/3_build_wps_ungrib.sh --force
EOF
}

FORCE_WPS_REBUILD="${FORCE_WPS_REBUILD:-false}"
WPS_CONFIGURE_OPTION="${WPS_CONFIGURE_OPTION:-1}"

# Processa argumentos antes de carregar as bibliotecas, garantindo que --help
# esteja disponível mesmo fora da árvore do repositório.
while (($# > 0)); do
  case "$1" in
    --force)
      FORCE_WPS_REBUILD=true
      ;;
    --configure-option)
      if (($# < 2)); then
        printf '%s\n\n' "ERRO: --configure-option exige um número." >&2
        usage >&2
        exit 2
      fi
      WPS_CONFIGURE_OPTION="$2"
      shift 2
      continue
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
# shellcheck source=_patches.sh
source "${SCRIPT_DIR}/_patches.sh"

NETCDF_COMPAT_DIR="${NETCDF_COMPAT_DIR:-${EXTERNAL_ROOT}/netcdf_compat}"
WPS_LOG_DIR="${WPS_LOG_DIR:-${LOG_ROOT}/wps}"

if [[ ! "${WPS_CONFIGURE_OPTION}" =~ ^[0-9]+$ ]]; then
  wps_log_error "WPS_CONFIGURE_OPTION deve ser um número do menu ./configure."
  exit 2
fi

if [[ ! -d "${WPS_SRC_DIR}" ]]; then
  wps_log_error "Diretório do WPS não encontrado: ${WPS_SRC_DIR}"
  wps_log_error "Execute primeiro: bash scripts/wps/1_download_wps_assets.sh"
  exit 1
fi

if [[ ! -f "${WPS_SRC_DIR}/configure" || ! -f "${WPS_SRC_DIR}/compile" ]]; then
  wps_log_error "${WPS_SRC_DIR} não parece ser uma árvore WPS válida."
  exit 1
fi

mkdir -p "${WPS_LOG_DIR}"

# Aplica o patch antes de decidir se um executável existente pode ser reutilizado.
# A função é idempotente e falha deliberadamente quando a fonte estiver em estado
# inesperado, evitando substituições cegas.
wps_require_command python3
wps_apply_dec_jpeg2000_patch
WPS_PATCH_TARGET="${WPS_SRC_DIR}/ungrib/src/ngl/g2/dec_jpeg2000.c"

printf '%s\n' "=== Configuração da compilação WPS/ungrib ==="
printf '%s\n' \
  "date_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "hostname=$(hostname)" \
  "user=${USER:-unknown}"
wps_show_layout
printf '%s\n' \
  "NETCDF_COMPAT_DIR=${NETCDF_COMPAT_DIR}" \
  "WPS_LOG_DIR=${WPS_LOG_DIR}" \
  "WPS_CONFIGURE_OPTION=${WPS_CONFIGURE_OPTION}" \
  "FORCE_WPS_REBUILD=${FORCE_WPS_REBUILD}" \
  ""

if [[ -x "${WPS_SRC_DIR}/ungrib.exe" ]] \
  && ! wps_is_true "${FORCE_WPS_REBUILD}" \
  && { wps_is_true "${WPS_DEC_JPEG2000_PATCH_CHANGED}" || [[ "${WPS_PATCH_TARGET}" -nt "${WPS_SRC_DIR}/ungrib.exe" ]]; }; then
  wps_log_info "O código-fonte WPS foi atualizado após a geração de ungrib.exe; recompilação será feita."
  FORCE_WPS_REBUILD=true
fi

if [[ -x "${WPS_SRC_DIR}/ungrib.exe" ]] && ! wps_is_true "${FORCE_WPS_REBUILD}"; then
  wps_log_info "ungrib.exe já existe e está consistente com o código-fonte; nenhuma recompilação foi necessária:"
  ls -lh "${WPS_SRC_DIR}/ungrib.exe"
  wps_log_info "Use --force ou FORCE_WPS_REBUILD=true para limpar, reconfigurar e recompilar."
  exit 0
fi

wps_require_command nc-config nf-config make perl csh python3 sed awk grep find

NC_PREFIX="$(nc-config --prefix)"
NF_PREFIX="$(nf-config --prefix)"

if [[ ! -d "${NC_PREFIX}" || ! -d "${NF_PREFIX}" ]]; then
  wps_log_error "nc-config/nf-config retornaram prefixos inválidos."
  printf '%s\n' \
    "NC_PREFIX=${NC_PREFIX}" \
    "NF_PREFIX=${NF_PREFIX}" >&2
  exit 1
fi

# Cria links simbólicos para arquivos que correspondam aos padrões recebidos.
#
# Entradas:
#   $1: diretório de origem; $2: diretório de destino; demais argumentos:
#   padrões de nomes.
# Efeitos:
#   Cria ou atualiza links em NETCDF_COMPAT_DIR; nunca remove arquivos regulares
#   fornecidos pelo usuário. Depende de find, ln e basename.
link_directory_entries() {
  local source_dir="$1"
  local destination_dir="$2"
  local pattern file

  shift 2
  [[ -d "${source_dir}" ]] || return 0

  for pattern in "$@"; do
    while IFS= read -r -d '' file; do
      ln -sfn "${file}" "${destination_dir}/$(basename "${file}")"
    done < <(find "${source_dir}" -maxdepth 1 \( -type f -o -type l \) -name "${pattern}" -print0)
  done
}

# Monta um prefixo de compatibilidade NetCDF a partir dos prefixos detectados.
#
# Entradas:
#   NC_PREFIX e NF_PREFIX obtidos por nc-config/nf-config.
# Efeitos:
#   Cria include/ e lib/ em NETCDF_COMPAT_DIR, remove somente links simbólicos
#   de execuções anteriores e grava proveniência. Não altera instalações NetCDF
#   externas nem remove arquivos regulares no diretório de compatibilidade.
refresh_netcdf_compat() {
  local include_dir library_dir file

  mkdir -p "${NETCDF_COMPAT_DIR}/include" "${NETCDF_COMPAT_DIR}/lib"

  # Limpa exclusivamente links gerenciados por este script. Arquivos regulares
  # possivelmente fornecidos pelo usuário permanecem intactos.
  find "${NETCDF_COMPAT_DIR}/include" -maxdepth 1 -type l -delete
  find "${NETCDF_COMPAT_DIR}/lib" -maxdepth 1 -type l -delete

  for include_dir in "${NC_PREFIX}/include" "${NF_PREFIX}/include"; do
    [[ -d "${include_dir}" ]] || continue
    while IFS= read -r -d '' file; do
      ln -sfn "${file}" "${NETCDF_COMPAT_DIR}/include/$(basename "${file}")"
    done < <(find "${include_dir}" -maxdepth 1 \( -type f -o -type l \) -print0)
  done

  for library_dir in "${NC_PREFIX}/lib" "${NC_PREFIX}/lib64" "${NF_PREFIX}/lib" "${NF_PREFIX}/lib64"; do
    link_directory_entries "${library_dir}" "${NETCDF_COMPAT_DIR}/lib" \
      'libnetcdf*' 'libhdf5*' 'libcurl*' 'libsz*' 'libz*'
  done

  cat > "${NETCDF_COMPAT_DIR}/.mpas-bmatrix-global-wps-netcdf-compat.env.tmp" <<EOF
NETCDF_C_PREFIX=${NC_PREFIX}
NETCDF_FORTRAN_PREFIX=${NF_PREFIX}
EOF
  mv "${NETCDF_COMPAT_DIR}/.mpas-bmatrix-global-wps-netcdf-compat.env.tmp" \
    "${NETCDF_COMPAT_DIR}/.mpas-bmatrix-global-wps-netcdf-compat.env"
}

printf '%s\n' "=== Prefixos NetCDF ==="
printf '%s\n' \
  "NC_PREFIX=${NC_PREFIX}" \
  "NF_PREFIX=${NF_PREFIX}"
refresh_netcdf_compat
export NETCDF="${NETCDF_COMPAT_DIR}"
export NETCDFF="${NF_PREFIX}"
printf '%s\n\n' \
  "NETCDF=${NETCDF}" \
  "NETCDFF=${NETCDFF}"

# A descoberta é limitada às raízes explicitamente configuradas, à pilha e aos
# prefixos NetCDF. Isso evita assumir caminhos ou módulos específicos do JACI.
wps_collect_search_roots "${NC_PREFIX}" "${NF_PREFIX}"

JASPERINC="${JASPERINC:-$(wps_find_include_root 'include/jasper/jasper.h')}"
JASPERLIB="${JASPERLIB:-$(wps_find_library_dir 'libjasper.so*' 'libjasper.a')}"
PNG_INC="${PNG_INC:-$(wps_find_include_root 'include/png.h')}"
PNG_LIB="${PNG_LIB:-$(wps_find_library_dir 'libpng.so*' 'libpng.a' 'libpng16.so*' 'libpng16.a')}"
ZLIB_INC="${ZLIB_INC:-$(wps_find_include_root 'include/zlib.h')}"
ZLIB_LIB="${ZLIB_LIB:-$(wps_find_library_dir 'libz.so*' 'libz.a')}"

export JASPERINC JASPERLIB PNG_INC PNG_LIB ZLIB_INC ZLIB_LIB

printf '%s\n' "=== Dependências GRIB2 ==="
missing_dependencies=false
for variable_name in JASPERINC JASPERLIB PNG_INC PNG_LIB ZLIB_INC ZLIB_LIB; do
  value="${!variable_name:-}"
  printf '%s=%s\n' "${variable_name}" "${value}"
  if [[ -z "${value}" || ! -d "${value}" ]]; then
    missing_dependencies=true
  fi
done

if "${missing_dependencies}"; then
  wps_log_error "Não foi possível localizar todas as dependências GRIB2."
  wps_log_error "Defina WPS_DEP_SEARCH_ROOTS ou informe explicitamente JASPERINC/JASPERLIB/PNG_INC/PNG_LIB/ZLIB_INC/ZLIB_LIB."
  exit 1
fi

if command -v ftn >/dev/null 2>&1; then
  WPS_FORTRAN_COMPILER="ftn"
else
  WPS_FORTRAN_COMPILER="${FC:-gfortran}"
fi
if command -v cc >/dev/null 2>&1; then
  WPS_C_COMPILER="cc"
else
  WPS_C_COMPILER="${CC:-gcc}"
fi
export WPS_FORTRAN_COMPILER WPS_C_COMPILER

cd "${WPS_SRC_DIR}"

printf '\n%s\n' "=== Limpeza e configuração do WPS ==="
./clean -a >/dev/null 2>&1 || true
rm -f configure.wps configure.wps.original ungrib.exe ungrib/src/ungrib.exe

printf '%s\n' "${WPS_CONFIGURE_OPTION}" | ./configure --nowrf \
  2>&1 | tee "${WPS_LOG_DIR}/configure.log"

if [[ ! -f configure.wps ]]; then
  wps_log_error "./configure não gerou configure.wps."
  exit 1
fi

cp configure.wps configure.wps.original

# Atualiza somente as atribuições de compilador e compressão necessárias ao
# ambiente resolvido. O script Python mantém o restante do configure.wps gerado
# pelo próprio WPS intacto e adiciona linhas apenas quando necessário.
python3 - <<'PY'
from __future__ import annotations

import os
import re
from pathlib import Path

path = Path("configure.wps")
text = path.read_text()

def set_assignment(name: str, value: str, append_when_missing: bool = True) -> None:
    global text
    pattern = rf"^{re.escape(name)}\s*=.*$"
    replacement = f"{name:<16}=       {value}"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    elif append_when_missing:
        text += f"\n{replacement}\n"

for variable in ("SFC", "DM_FC", "FC", "LD"):
    set_assignment(variable, os.environ["WPS_FORTRAN_COMPILER"], append_when_missing=False)
for variable in ("SCC", "SCC_NOMPI", "DM_CC", "CC"):
    set_assignment(variable, os.environ["WPS_C_COMPILER"], append_when_missing=False)

compression_inc = " ".join(
    f"-I{os.environ[name]}" for name in ("JASPERINC", "PNG_INC", "ZLIB_INC")
)
compression_libs = " ".join(
    (
        f"-L{os.environ['JASPERLIB']}", "-ljasper",
        f"-L{os.environ['PNG_LIB']}", "-lpng",
        f"-L{os.environ['ZLIB_LIB']}", "-lz",
    )
)
set_assignment("COMPRESSION_INC", compression_inc)
set_assignment("COMPRESSION_LIBS", compression_libs)
path.write_text(text)
PY

printf '%s\n' "--- Linhas relevantes de configure.wps ---"
grep -nE '^(SFC|SCC|SCC_NOMPI|DM_FC|DM_CC|CC|FC|LD|COMPRESSION_INC|COMPRESSION_LIBS|NETCDF)[[:space:]]*=' \
  configure.wps || true

printf '\n%s\n' "=== Compilação do ungrib ==="
./compile ungrib 2>&1 | tee "${WPS_LOG_DIR}/compile-ungrib.log"

if [[ ! -x "${WPS_SRC_DIR}/ungrib.exe" ]]; then
  wps_log_error "ungrib.exe não foi criado."
  printf '%s\n' "Últimas linhas do log:" >&2
  tail -120 "${WPS_LOG_DIR}/compile-ungrib.log" >&2 || true
  exit 1
fi

cat > "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-build.env.tmp" <<EOF
WPS_VERSION=${WPS_VERSION}
NETCDF_C_PREFIX=${NC_PREFIX}
NETCDF_FORTRAN_PREFIX=${NF_PREFIX}
JASPERINC=${JASPERINC}
JASPERLIB=${JASPERLIB}
PNG_INC=${PNG_INC}
PNG_LIB=${PNG_LIB}
ZLIB_INC=${ZLIB_INC}
ZLIB_LIB=${ZLIB_LIB}
WPS_CONFIGURE_OPTION=${WPS_CONFIGURE_OPTION}
WPS_DEC_JPEG2000_PATCH=jas_image_decode
EOF
mv "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-build.env.tmp" \
  "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-build.env"

printf '\n%s\n' "=== Resultado ==="
ls -lh "${WPS_SRC_DIR}/ungrib.exe"
command -v file >/dev/null 2>&1 && file "${WPS_SRC_DIR}/ungrib.exe" || true
if command -v ldd >/dev/null 2>&1 && ldd "${WPS_SRC_DIR}/ungrib.exe" | grep -q 'not found'; then
  wps_log_error "Há bibliotecas dinâmicas ausentes na saída de ldd."
  ldd "${WPS_SRC_DIR}/ungrib.exe" >&2 || true
  exit 1
fi
wps_log_info "SUCESSO: ungrib.exe compilado em ${WPS_SRC_DIR}/ungrib.exe"
