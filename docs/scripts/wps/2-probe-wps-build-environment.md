# `2_probe_wps_build_environment.sh`: diagnóstico do ambiente

## Visão geral e objetivo

`2_probe_wps_build_environment.sh` verifica se o ambiente atual tem os elementos necessários para configurar e compilar o `ungrib.exe`. É uma etapa de diagnóstico: não cria, edita, remove ou baixa arquivos.

Use-o depois do download dos ativos WPS e sempre que um build falhar por causa de compiladores, NetCDF ou bibliotecas GRIB2.

## Escopo e limitações

O diagnóstico verifica:

- arquivos mínimos da árvore WPS;
- presença de comandos necessários no `PATH`;
- prefixos retornados por `nc-config` e `nf-config`;
- diretórios de cabeçalhos e bibliotecas de JasPer, libpng e zlib.

Ele não garante que uma opção específica do menu `./configure` seja adequada ao ambiente, nem substitui um build real. A validação de ligação dinâmica é feita ao fim de `3_build_wps_ungrib.sh`.

## Pré-requisitos

- Bash 4 ou superior;
- checkout válido do repositório;
- para resultado completo: WPS já extraído e ambiente de compilação carregado;
- `nc-config`, `nf-config`, `make`, `perl`, `csh`, `python3`, `sed`, `awk`, `grep` e `find`.

## Variáveis e descoberta de dependências

| Variável | Finalidade |
| --- | --- |
| `WPS_SRC_DIR` | Local da árvore WPS a verificar. |
| `WPS_DEP_SEARCH_ROOTS` | Lista, separada por `:`, de prefixos adicionais onde procurar dependências. |
| `STACK_ROOT`, `SPACK_ROOT`, `SPACK_INSTALL_ROOT` | Raízes adicionais consideradas automaticamente. |
| `JASPERINC`, `JASPERLIB` | Diretórios explícitos para cabeçalhos e bibliotecas JasPer. |
| `PNG_INC`, `PNG_LIB` | Diretórios explícitos para libpng. |
| `ZLIB_INC`, `ZLIB_LIB` | Diretórios explícitos para zlib. |
| `STRICT_WPS_PROBE` | Quando verdadeiro, torna uma verificação incompleta um erro de retorno. |

A ordem de busca prioriza `WPS_DEP_SEARCH_ROOTS`, depois as raízes de pilha/Spack e, por fim, os prefixos NetCDF e seus diretórios-pai. Não há caminho específico do JACI embutido no script.

## Opções de linha de comando

```text
--strict        Retorna 1 quando algum requisito está ausente.
-h, --help      Exibe a ajuda sem executar o diagnóstico.
```

Sem `--strict`, problemas são relatados, mas o script termina com sucesso para permitir investigação incremental. Em pipelines, CI e preparação automatizada, prefira `--strict`.

## Exemplos completos

Diagnóstico informativo:

```bash
bash scripts/wps/2_probe_wps_build_environment.sh
```

Diagnóstico adequado para automação:

```bash
bash scripts/wps/2_probe_wps_build_environment.sh --strict
```

Uso de uma instalação Spack fora do caminho normalmente detectado:

```bash
export WPS_DEP_SEARCH_ROOTS=/caminho/para/spack/opt/spack
bash scripts/wps/2_probe_wps_build_environment.sh --strict
```

Informando dependências diretamente:

```bash
export JASPERINC=/prefixo/jasper/include
export JASPERLIB=/prefixo/jasper/lib
export PNG_INC=/prefixo/libpng/include
export PNG_LIB=/prefixo/libpng/lib
export ZLIB_INC=/prefixo/zlib/include
export ZLIB_LIB=/prefixo/zlib/lib
bash scripts/wps/2_probe_wps_build_environment.sh --strict
```

## Comportamento idempotente

A execução é somente leitura. O script não cria logs, diretórios de compatibilidade, arquivos temporários ou alterações na árvore WPS. Pode ser repetido quantas vezes forem necessárias.

## Como interpretar o resultado

- `OK` em todos os grupos: o ambiente está aparentemente pronto para o build.
- `AUSENTE` em `nc-config` ou `nf-config`: carregue ou disponibilize NetCDF-C e NetCDF-Fortran.
- `AUSENTE` em `JASPER*`, `PNG_*` ou `ZLIB_*`: configure `WPS_DEP_SEARCH_ROOTS` ou as seis variáveis explícitas.
- Arquivo WPS ausente: execute `1_download_wps_assets.sh`, ou confirme o valor de `WPS_SRC_DIR`.

O código de retorno é `0` quando o ambiente está completo, ou sempre no modo informativo. No modo `--strict`, requisitos ausentes resultam em `1`; argumento inválido resulta em `2`.

## Troubleshooting

| Sintoma | Causa provável | Ação recomendada |
| --- | --- | --- |
| `nc-config` ausente | NetCDF-C não está carregado. | Carregue o ambiente que fornece NetCDF-C e confira `command -v nc-config`. |
| `nf-config` ausente | NetCDF-Fortran não está carregado. | Carregue NetCDF-Fortran compatível com o NetCDF-C atual. |
| NetCDF encontrado, GRIB2 ausente | JasPer/libpng/zlib não estão abaixo das raízes investigadas. | Defina `WPS_DEP_SEARCH_ROOTS` ou os caminhos explícitos. |
| WPS ausente | Download não foi executado ou `WPS_SRC_DIR` é incorreto. | Rode o passo 1 ou exporte o caminho correto. |
| Resultado varia entre sessões | Módulos/variáveis foram alterados. | Registre `module list`, `PATH`, `LD_LIBRARY_PATH` e execute novamente. |

## Relação com os demais scripts

Este script é a ponte entre `1_download_wps_assets.sh` e `3_build_wps_ungrib.sh`. Em condições normais, a próxima ação após um diagnóstico estrito bem-sucedido é:

```bash
bash scripts/wps/3_build_wps_ungrib.sh
```

> **[TBD: ambiente JACI]** Registrar no guia local os módulos que disponibilizam as dependências observadas pelo diagnóstico, sem inserir nomes presumidos no script.
