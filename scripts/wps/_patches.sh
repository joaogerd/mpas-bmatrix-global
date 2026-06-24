#!/usr/bin/env bash
#
# Nome: _patches.sh
# Descrição: Biblioteca interna de correções de código-fonte necessárias à
#   compilação do WPS/ungrib.
#
# Finalidade no workflow:
#   Aplica, de forma controlada, a correção de compatibilidade JasPer exigida
#   pelo WPS 4.6.0 antes da compilação de ungrib.exe. É carregada exclusivamente
#   por 3_build_wps_ungrib.sh.
#
# Uso:
#   source scripts/wps/_patches.sh
#   wps_apply_dec_jpeg2000_patch
#
# Pré-requisitos:
#   - _common.sh já carregado e WPS_SRC_DIR definido;
#   - Python 3 no PATH;
#   - árvore WPS válida contendo ungrib/src/ngl/g2/dec_jpeg2000.c.
#
# Variáveis de ambiente relevantes:
#   WPS_SRC_DIR. Após a execução da função, a variável
#   WPS_DEC_JPEG2000_PATCH_CHANGED indica se a fonte foi modificada nesta
#   invocação.
#
# Arquivos criados ou modificados:
#   - $WPS_SRC_DIR/ungrib/src/ngl/g2/dec_jpeg2000.c;
#   - $WPS_SRC_DIR/ungrib/src/ngl/g2/dec_jpeg2000.c.orig-jpc-decode
#     (backup, criado uma única vez);
#   - $WPS_SRC_DIR/.mpas-bmatrix-global-wps-patches.env.
#
# Idempotência:
#   A correção só é aplicada quando a chamada obsoleta jpc_decode() aparece
#   exatamente uma vez. Uma fonte já corrigida é reutilizada. Estados ambíguos
#   interrompem a execução para evitar alteração indevida.
#
# Autor: João Gerd Zell de Mattos
# Projeto: mpas-bmatrix-global
# Última atualização: 2026-06-24
#

# Esta é uma biblioteca interna. A execução direta não prepara o ambiente do
# processo chamador nem representa uma etapa pública do workflow.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '%s\n' "ERRO: ${BASH_SOURCE[0]} é uma biblioteca; execute 3_build_wps_ungrib.sh." >&2
  exit 2
fi

# Evita redefinições e reaplicações acidentais quando o arquivo é carregado
# repetidamente durante a mesma sessão Bash.
if [[ -n "${_MPAS_BMATRIX_WPS_PATCHES_LOADED:-}" ]]; then
  return 0
fi
_MPAS_BMATRIX_WPS_PATCHES_LOADED=1

# Aplica a correção de compatibilidade com JasPer em dec_jpeg2000.c.
#
# Entradas:
#   - WPS_SRC_DIR: raiz da árvore WPS.
# Saídas:
#   - WPS_DEC_JPEG2000_PATCH_CHANGED=true quando a fonte foi alterada;
#   - WPS_DEC_JPEG2000_PATCH_CHANGED=false quando a correção já estava presente.
# Arquivos afetados:
#   - alvo da correção, backup original e arquivo de proveniência descritos no
#     cabeçalho.
# Dependências externas:
#   - python3 para validar o estado e fazer a substituição inequívoca.
# Falhas:
#   - retorna erro se o alvo não existir ou o estado da fonte for inesperado.
wps_apply_dec_jpeg2000_patch() {
  local target backup state

  target="${WPS_SRC_DIR}/ungrib/src/ngl/g2/dec_jpeg2000.c"
  backup="${target}.orig-jpc-decode"
  WPS_DEC_JPEG2000_PATCH_CHANGED=false
  export WPS_DEC_JPEG2000_PATCH_CHANGED

  if [[ ! -f "${target}" ]]; then
    printf '%s\n' "ERRO: arquivo alvo do patch não encontrado: ${target}" >&2
    return 1
  fi

  state="$(python3 - "${target}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
old = re.compile(r"image\s*=\s*jpc_decode\s*\(\s*jpcstream\s*,\s*opts\s*\)\s*;")
new = re.compile(
    r"image\s*=\s*jas_image_decode\s*\(\s*jpcstream\s*,\s*"
    r"jas_image_strtofmt\s*\(\s*\"jpc\"\s*\)\s*,\s*opts\s*\)\s*;"
)
old_count = len(old.findall(text))
new_count = len(new.findall(text))

if old_count == 1 and new_count == 0:
    print("needs-patch")
elif old_count == 0 and new_count == 1:
    print("already-applied")
else:
    raise SystemExit(
        "ERRO: estado inesperado em dec_jpeg2000.c "
        f"(jpc_decode={old_count}, jas_image_decode={new_count}). "
        "Inspecione o arquivo manualmente antes de continuar."
    )
PY
)" || return 1

  case "${state}" in
    already-applied)
      printf '%s\n' "Patch JasPer já aplicado: ${target}"
      ;;
    needs-patch)
      if [[ ! -e "${backup}" ]]; then
        cp -p "${target}" "${backup}"
        printf '%s\n' "Backup original criado: ${backup}"
      else
        printf '%s\n' "Backup original já existente: ${backup}"
      fi

      python3 - "${target}" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
old = re.compile(r"image\s*=\s*jpc_decode\s*\(\s*jpcstream\s*,\s*opts\s*\)\s*;")
replacement = 'image=jas_image_decode(jpcstream, jas_image_strtofmt("jpc"), opts);'
new_text, count = old.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit("ERRO: não foi possível aplicar o patch JasPer de forma inequívoca.")
path.write_text(new_text)
PY

      WPS_DEC_JPEG2000_PATCH_CHANGED=true
      export WPS_DEC_JPEG2000_PATCH_CHANGED
      printf '%s\n' "Patch JasPer aplicado: ${target}"
      ;;
    *)
      printf '%s\n' "ERRO: resposta inesperada ao verificar patch JasPer: ${state}" >&2
      return 1
      ;;
  esac

  cat > "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-patches.env.tmp" <<EOF
WPS_DEC_JPEG2000_PATCH=jas_image_decode
WPS_DEC_JPEG2000_PATCH_TARGET=${target}
EOF
  mv "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-patches.env.tmp" \
    "${WPS_SRC_DIR}/.mpas-bmatrix-global-wps-patches.env"
}
