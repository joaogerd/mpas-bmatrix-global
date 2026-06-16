# Configuracao smoke vs producao da matriz B

Este documento separa o caso smoke test validado no JACI de uma futura configuracao de producao para a B-matrix global MPAS-JEDI/SABER.

## Baseline smoke validado

O smoke test validado usa a configuracao atual:

```text
configs/jaci-x1.10242.yaml
```

Esse caso ja foi executado e validado no JACI para a cadeia:

```text
Bflow -> VBAL -> HDIAG -> NICAS -> SO -> Dirac -> dirac-summary
```

O objetivo do smoke e manter um baseline funcional, pequeno e reproduzivel para:

- integracao entre etapas do workflow;
- regressao apos mudancas no app;
- validacao rapida de ambiente, YAMLs, PBS e produtos esperados;
- diagnostico de falhas de infraestrutura ou de schema SABER/MPAS-JEDI.

O smoke usa poucos membros. Portanto, ele nao deve ser interpretado como estatistica final de producao da matriz B.

## Regra de manutencao

Nao aumentar o custo do smoke test para atender objetivos de producao.

O caso `configs/jaci-x1.10242.yaml` deve permanecer o baseline funcional validado. Alteracoes nele devem ser pequenas, justificadas e voltadas a preservar o caminho ja testado.

Mudancas de producao devem entrar em configuracao propria, documentacao propria ou ambos.

## Configuracao de producao

Uma configuracao de producao deve ser definida separadamente quando os parametros cientificos e operacionais estiverem fechados.

Ela deve especificar, no minimo:

- numero de membros maior que o smoke;
- periodo de amostragem mais longo;
- intervalo temporal de amostras adequado ao objetivo estatistico;
- filas, walltime e politicas de retry adequadas ao custo real;
- politica de retencao de logs, workspaces e produtos intermediarios;
- local final dos produtos da B-matrix;
- criterios de validacao estatistica alem dos checks estruturais do smoke.

Enquanto esses valores nao estiverem definidos, nao ha um `configs/jaci-x1.10242-production.example.yaml` neste repositorio. Criar um YAML com numeros arbitrarios poderia dar a falsa impressao de configuracao operacional aprovada.

## Comparacao

| Aspecto | Smoke test | Producao |
| --- | --- | --- |
| Objetivo | Verificar integracao e regressao do workflow | Gerar estatisticas finais para uso cientifico/operacional |
| Configuracao atual | `configs/jaci-x1.10242.yaml` | A definir em configuracao separada |
| Numero de membros | Pequeno, validado com 4 membros | Maior, definido pelo desenho estatistico |
| Periodo de amostragem | Curto | Longo o suficiente para amostrar variabilidade desejada |
| Custo | Baixo/moderado para depuracao no JACI | Alto, dependente de membros e periodo |
| Filas/walltime | Ajustados para smoke validado | Devem ser dimensionados para a carga de producao |
| Produtos | Produtos estruturais de cada etapa e testes SO/Dirac | Produtos finais aprovados para uso da B-matrix |
| Validacao | Presenca de produtos, status 0 e diagnosticos basicos | Validacao estrutural, estatistica e cientifica |
| Manutencao | Deve permanecer estavel como baseline | Pode evoluir conforme requisitos de producao |

## Fluxo recomendado

1. Rodar o Bflow smoke para gerar os PTBs de entrada.
2. Rodar ou validar a cadeia com `mpasbcov pipeline-all`.
3. Confirmar produtos de VBAL, HDIAG, NICAS, SO e Dirac.
4. Usar `mpasbcov dirac-summary --workspace "$DIRAC"` para diagnostico rapido do produto Dirac.
5. Somente depois de o smoke continuar verde, avaliar configuracoes de producao.

## Decisao atual

A separacao entre smoke e producao e documental neste momento.

Nao foi criado YAML de producao porque os parametros de producao ainda nao foram definidos. Essa decisao evita versionar uma configuracao exemplo com valores especulativos.
