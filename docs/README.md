# Documentação do `mpas-bmatrix-global`

Este diretório contém a documentação oficial do workflow de geração e validação da matriz B global MPAS-JEDI/SABER.

A documentação está organizada para separar:

- uso operacional;
- teoria científica;
- documentação de cada ferramenta;
- workflow completo;
- produtos gerados;
- referência de configuração;
- documentação de desenvolvedor.

## Leitura recomendada

1. [Instalação](user-guide/installation.md)
2. [Quickstart](user-guide/quickstart.md)
3. [Introdução à assimilação de dados](theory/assimilation.md)
4. [Teoria da matriz B](theory/bmatrix.md)
5. [Workflow completo](workflows/bmatrix-full-pipeline.md)
6. Documentação da ferramenta específica que você irá executar.

## Guias de usuário

| Documento | Conteúdo |
| --- | --- |
| [installation.md](user-guide/installation.md) | Instalação do ambiente `mpaswf`, dependências e testes dos comandos. |
| [quickstart.md](user-guide/quickstart.md) | Sequência mínima para rodar um smoke test do workflow. |

## Teoria

| Documento | Conteúdo |
| --- | --- |
| [assimilation.md](theory/assimilation.md) | Introdução à assimilação de dados e papel da matriz B. |
| [bmatrix.md](theory/bmatrix.md) | Conceito da matriz B, componentes e fluxo científico. |
| [nmc-method.md](theory/nmc-method.md) | Método NMC e uso de diferenças f48-f24. |
| [control-variables.md](theory/control-variables.md) | Variáveis de controle usadas no workflow. |
| [saber-bump.md](theory/saber-bump.md) | Papel do SABER/BUMP na construção da matriz B. |
| [single-observation.md](theory/single-observation.md) | Fundamentos do teste de observação única. |
| [validation.md](theory/validation.md) | Estratégia de validação estrutural, numérica e física. |

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

## Produtos

| Documento | Conteúdo |
| --- | --- |
| [products/README.md](products/README.md) | Índice dos produtos do workflow. |
| [full-forecast.md](products/full-forecast.md) | `FULL_f24.nc` e `FULL_f48.nc`. |
| [ptb.md](products/ptb.md) | `PTB_f48mf24.nc`. |
| [mpas-vbal.md](products/mpas-vbal.md) | Produtos VBAL. |
| [mpas-stddev.md](products/mpas-stddev.md) | Produto `mpas.stddev.nc`. |
| [mpas-correlations.md](products/mpas-correlations.md) | Produtos `mpas.cor_rh.nc` e `mpas.cor_rv.nc`. |
| [mpas-nicas.md](products/mpas-nicas.md) | Produtos NICAS. |
| [single-observation-products.md](products/single-observation-products.md) | Produtos do teste SO. |

## Referência

| Documento | Conteúdo |
| --- | --- |
| [configuration.md](reference/configuration.md) | Estrutura dos arquivos `configs/*.yaml`. |
| [outputs.md](reference/outputs.md) | Produtos esperados por etapa. |

## Desenvolvedores

| Documento | Conteúdo |
| --- | --- |
| [architecture.md](developers/architecture.md) | Organização interna dos módulos e responsabilidades. |

## Política de documentação

A documentação oficial deve estar nos diretórios listados acima. Documentos temporários, notas de refatoração e registros históricos devem ser removidos ou arquivados para evitar ambiguidade.
