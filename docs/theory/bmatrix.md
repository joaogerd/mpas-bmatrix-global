# Matriz B do MPAS-JEDI/SABER

## O que é a matriz B

Em assimilação variacional, a matriz B representa a covariância dos erros de background. Ela descreve estatisticamente como os erros da condição inicial se distribuem no espaço, na vertical, entre variáveis e entre escalas.

Na função custo 3D-Var, a contribuição do background é escrita de forma idealizada como:

```text
J_b(x) = 1/2 (x - x_b)^T B^{-1} (x - x_b)
```

onde:

- `x` é o estado analisado;
- `x_b` é o background;
- `B` é a covariância dos erros de background.

A matriz B não é armazenada como uma matriz densa. No SABER/JEDI, ela é implementada como uma composição de operadores, transformações e arquivos de parâmetros estatísticos.

## Variáveis de controle

O workflow usa como variáveis de controle principais:

- `stream_function`
- `velocity_potential`
- `temperature`
- `spechum`
- `surface_pressure`

Essas variáveis são escolhidas porque representam uma base meteorológica mais apropriada para modelar correlações de erro do que diretamente `u`, `v`, `theta` e `qv`.

## Como a B é concebida neste workflow

A matriz B é construída a partir de amostras de erro de previsão obtidas pelo método NMC. Para cada tempo válido, comparam-se previsões com o mesmo tempo válido e diferentes alcances:

```text
perturbação NMC = forecast_48h - forecast_24h
```

Essas diferenças são usadas como proxy dos erros de background.

O workflow completo calcula, a partir dessas amostras:

1. perturbações NMC em variáveis de controle;
2. balanço vertical/multivariado;
3. variâncias e correlações diagnósticas;
4. operador NICAS de correlação/localização;
5. teste de observação única para verificar a resposta da B.

## Componentes da B

### Desvio padrão

Representa a amplitude esperada do erro de background por variável e posição. No workflow, é produzido a partir da etapa HDIAG e usado no bloco `StdDev` do SABER.

Produto típico:

```text
mpas.stddev.nc
```

### Correlações horizontais e verticais

Representam como erros em uma posição se relacionam com erros em outras posições e níveis. A etapa HDIAG calcula diagnósticos de correlação horizontal e vertical.

Produtos típicos:

```text
mpas.cor_rh.nc
mpas.cor_rv.nc
```

### Balanço vertical/multivariado

Modela relações estatísticas entre variáveis, por exemplo a parte balanceada de temperatura, pressão de superfície ou potencial de velocidade em relação à função de corrente.

Produto típico:

```text
mpas_vbal.nc
mpas_vbal_local_*.nc
```

### NICAS

NICAS representa a correlação/localização de forma eficiente e escalável, evitando armazenar uma matriz completa. Ele constrói operadores locais e globais que são usados pelo SABER para aplicar a covariância.

Produtos típicos:

```text
mpas_nicas.nc
mpas_nicas_local_*.nc
mpas_nicas_grids_local_*.nc
mpas.nicas_norm.nc
mpas.dirac_nicas.nc
```

### Single Observation

O teste de observação única não cria a matriz B. Ele avalia a resposta física e espacial da B ao assimilar uma observação sintética. É uma etapa de validação qualitativa e quantitativa.

## Sequência conceitual

```text
MPAS forecasts f48/f24
  -> BFLOW: diferenças NMC e variáveis de controle
  -> VBAL: balanço vertical/multivariado
  -> HDIAG: variâncias e correlações diagnósticas
  -> NICAS: operador de correlação/localização
  -> SO: teste de resposta da matriz B
```

## O que a matriz B final precisa conter

Uma configuração operacional mínima precisa conter:

- arquivos de desvio padrão;
- arquivos de balanço vertical;
- arquivos de correlação/NICAS;
- consistência entre variáveis de controle e variáveis de análise;
- validação por diagnóstico e por observação única.

## Limitações

A B gerada por NMC depende de:

- quantidade e distribuição temporal das amostras;
- qualidade das previsões MPAS usadas;
- configuração da malha;
- consistência entre executáveis MPAS-JEDI/SABER;
- escolhas de variáveis e transformações.

Por isso, uma matriz B não deve ser considerada final apenas porque o workflow executou sem erro. Ela deve ser validada com `mpasverify`, diagnósticos internos e testes de impacto em assimilação/previsão.
