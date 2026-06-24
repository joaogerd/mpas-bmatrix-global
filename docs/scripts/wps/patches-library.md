# `_patches.sh`: biblioteca de correções do WPS

## Objetivo

`_patches.sh` contém correções internas necessárias para construir o `ungrib.exe`. Atualmente, ela implementa exclusivamente o patch de compatibilidade JasPer para WPS 4.6.0.

A biblioteca é carregada por `3_build_wps_ungrib.sh`; não é uma etapa pública e não deve ser executada diretamente:

```bash
source scripts/wps/_common.sh
source scripts/wps/_patches.sh
wps_apply_dec_jpeg2000_patch
```

A execução direta termina com código `2` e orienta o uso do script de build.

## Pré-requisitos

- `_common.sh` já carregado;
- `WPS_SRC_DIR` resolvido para uma árvore WPS válida;
- `python3` no `PATH`;
- arquivo `$WPS_SRC_DIR/ungrib/src/ngl/g2/dec_jpeg2000.c` presente.

## Correção aplicada

O WPS 4.6.0 chama `jpc_decode()` em `dec_jpeg2000.c`. Em instalações modernas de JasPer, esse símbolo pode não ser exportado. A biblioteca substitui essa chamada pela API pública:

```c
jas_image_decode(jpcstream, jas_image_strtofmt("jpc"), opts)
```

A substituição é específica, limitada a uma ocorrência e feita por um pequeno programa Python que valida o estado do arquivo antes de escrever.

## Arquivos afetados

| Arquivo | Efeito |
| --- | --- |
| `dec_jpeg2000.c` | É alterado apenas quando a chamada antiga está presente uma única vez. |
| `dec_jpeg2000.c.orig-jpc-decode` | Backup criado uma única vez antes da alteração. |
| `.mpas-bmatrix-global-wps-patches.env` | Registro de proveniência do patch aplicado. |

## Idempotência e segurança

A função determina um entre três estados:

1. **Precisa de patch**: encontra uma única chamada antiga e nenhuma chamada nova; cria backup e aplica a alteração.
2. **Patch já aplicado**: encontra uma única chamada nova e nenhuma antiga; não modifica a fonte.
3. **Estado inesperado**: qualquer outra combinação; retorna erro e exige inspeção manual.

Esse terceiro caso protege contra versões incompatíveis do WPS, alterações manuais ou substituições parciais. A função define `WPS_DEC_JPEG2000_PATCH_CHANGED=true` somente quando alterou a fonte na invocação atual.

## Como validar

A validação normal é indireta, por meio do build:

```bash
bash scripts/wps/3_build_wps_ungrib.sh
```

Para inspecionar a origem da alteração:

```bash
source scripts/wps/_common.sh
sed -n '/jas_image_decode/p' "$WPS_SRC_DIR/ungrib/src/ngl/g2/dec_jpeg2000.c"
test -f "$WPS_SRC_DIR/ungrib/src/ngl/g2/dec_jpeg2000.c.orig-jpc-decode"
```

## Recuperação de falhas

| Situação | Ação recomendada |
| --- | --- |
| Arquivo-alvo não encontrado | Verifique `WPS_SRC_DIR` e se a árvore corresponde ao WPS esperado. |
| Estado inesperado | Não edite automaticamente; compare o arquivo com a fonte da versão usada. |
| Necessidade de restaurar a fonte | Use o backup `.orig-jpc-decode` somente após confirmar que ele pertence à mesma árvore WPS. |
| Patch incompatível com nova versão | Não adapte por suposição; registre uma correção nova, validada contra a fonte e a biblioteca do ambiente. |

## Relação com o workflow

A biblioteca não deve ser chamada como uma etapa isolada em procedimentos normais. O build a executa antes de verificar se um `ungrib.exe` existente pode ser reutilizado, garantindo que uma fonte corrigida mais nova force recompilação quando necessário.
