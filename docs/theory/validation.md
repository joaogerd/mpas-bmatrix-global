# Validação de uma matriz B

## Objetivo

Validar uma matriz B significa verificar se ela é numericamente consistente, fisicamente plausível e útil para assimilação de dados.

Executar o workflow sem erro não é suficiente. É necessário avaliar os produtos e a resposta da matriz B.

## Níveis de validação

### 1. Validação estrutural

Confere se os arquivos esperados existem e possuem dimensões compatíveis.

Exemplos:

- arquivos globais presentes;
- arquivos locais por rank completos;
- variáveis esperadas nos NetCDFs;
- shapes consistentes;
- YAMLs compatíveis com os produtos.

### 2. Validação numérica

Compara produtos novos com baselines ou entre configurações.

Ferramenta recomendada:

```bash
mpasverify compare --old baseline.nc --new novo.nc --report report.md
```

Métricas principais:

- `Bias`;
- `MAE`;
- `RMSE`;
- `RelRMSE`;
- `MaxAbs`;
- `Corr`.

### 3. Validação física

Avalia se os campos possuem estrutura meteorológica plausível.

Exemplos:

- variância positiva;
- correlações suaves;
- escalas horizontais realistas;
- ausência de ruído de grade;
- balanço coerente entre variáveis.

### 4. Validação por observação única

Usa o `mpasso` para gerar incrementos a partir de observações sintéticas. Essa etapa avalia a resposta composta da B.

### 5. Validação em assimilação/previsão

A validação final exige experimentos reais de assimilação:

- comparação contra controle;
- O-B e O-A;
- impacto em forecast;
- métricas por variável, nível e região;
- sensibilidade a tipos de observação.

## Critérios mínimos para aceitar uma execução

Uma execução de treinamento deve ser aceita apenas se:

- BFLOW produziu todos os `PTB_f48mf24.nc` esperados;
- VBAL produziu arquivos globais e locais completos;
- HDIAG produziu `mpas.stddev.nc`, `mpas.cor_rh.nc` e `mpas.cor_rv.nc`;
- NICAS produziu merge completo;
- SO gerou análise e arquivos `obsout`;
- logs indicam status final de sucesso;
- `mpasverify` não mostra diferenças inesperadas contra baseline.

## Como interpretar `mpasverify`

- `Corr` próximo de 1 indica forte equivalência estrutural.
- `RelRMSE` pequeno indica erro pequeno em relação à escala do campo.
- `Corr` próximo de -1 sugere inversão de sinal.
- `MaxAbs` alto com `RelRMSE` pequeno pode indicar poucos pontos problemáticos.
- `shape_mismatch` exige investigação antes de seguir.

## Checklist operacional

```text
[ ] Forecasts f24/f48 disponíveis
[ ] BFLOW validado
[ ] VBAL validado
[ ] HDIAG validado
[ ] NICAS validado
[ ] SO validado
[ ] Produtos finais copiados ou registrados
[ ] Relatório de validação salvo
```

## Erros que invalidam a matriz B

- produtos locais incompletos;
- variáveis ausentes;
- correlação com baseline negativa sem justificativa;
- SO sem análise;
- incrementos com ruído extremo;
- falha silenciosa em logs;
- mismatch entre número de ranks e arquivos locais.

## Observação final

A matriz B é uma hipótese estatística sobre erros de background. Sua qualidade só pode ser confirmada plenamente em experimentos de assimilação e previsão. O workflow deste repositório fornece a cadeia de construção e validação inicial.
