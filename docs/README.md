# Documentação do `mpas-bmatrix-global`

Este diretório contém a documentação oficial do workflow de geração e validação da matriz B global MPAS-JEDI/SABER.

A documentação foi reorganizada para separar:

- uso operacional;
- teoria científica;
- documentação de cada ferramenta;
- workflow completo;
- referência de configuração e produtos.

## Leitura recomendada

1. [Instalação](user-guide/installation.md)
2. [Quickstart](user-guide/quickstart.md)
3. [Teoria da matriz B](theory/bmatrix.md)
4. [Workflow completo](workflows/bmatrix-full-pipeline.md)
5. Documentação da ferramenta específica que você irá executar.

## Guias de usuário

| Documento | Conteúdo |
| --- | --- |
| [installation.md](user-guide/installation.md) | Instalação do ambiente `mpaswf`, dependências e testes dos comandos. |
| [quickstart.md](user-guide/quickstart.md) | Sequência mínima para rodar um smoke test do workflow. |

## Teoria

| Documento | Conteúdo |
| --- | --- |
| [bmatrix.md](theory/bmatrix.md) | Conceito da matriz B, componentes, variáveis de controle e fluxo científico. |

## Ferramentas

| Ferramenta | Documento | Função |
| --- | --- | --- |
| `mpasforecast` | [mpasforecast.md](tools/mpasforecast.md) | Prepara e submete previsões MPAS f24/f48. |
| `mpasbflow` | [mpasbflow.md](tools/mpasbflow.md) | Gera amostras NMC e variáveis de controle. |
| `mpasvbal` | [mpasvbal.md](tools/mpasvbal.md) | Treina balanço vertical/multivariado. |
| `mpashdiag` | [mpashdiag.md](tools/mpashdiag.md) | Calcula diagnósticos, variâncias e correlações. |
| `mpasnicas` | [mpasnicas.md](tools/mpasnicas.md) | Constrói e mescla o operador NICAS. |
| `mpasso` | [mpasso.md](tools/mpasso.md) | Executa teste de observação única. |
| `mpasverify` | [mpasverify.md](tools/mpasverify.md) | Compara NetCDFs e gera relatórios de validação. |

## Workflows

| Documento | Conteúdo |
| --- | --- |
| [bmatrix-full-pipeline.md](workflows/bmatrix-full-pipeline.md) | Processo completo de geração da matriz B, ponta a ponta. |

## Referência

| Documento | Conteúdo |
| --- | --- |
| [configuration.md](reference/configuration.md) | Estrutura dos arquivos `configs/*.yaml`. |
| [outputs.md](reference/outputs.md) | Produtos esperados por etapa. |

## Documentos antigos

Documentos antigos, notas de desenvolvimento e registros temporários devem ser removidos ou arquivados. A documentação oficial deve apontar para os arquivos listados acima.
