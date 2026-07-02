# Workflow completo de geração da matriz B

## Objetivo

Este documento descreve o processo completo para gerar e validar uma matriz B global MPAS-JEDI/SABER a partir de amostras NMC.

## Visão geral

```text
1. MPAS forecasts f48/f24
2. BFLOW: diferenças NMC e variáveis de controle
3. VBAL: balanço vertical/multivariado
4. HDIAG: variância e correlações diagnósticas
5. NICAS: operador de correlação/localização
6. SO: teste de observação única
7. Verificação e documentação dos produtos
```

## 1. Forecasts MPAS

Ferramenta:

```bash
mpasforecast
```

Objetivo:

- gerar previsões MPAS com alcances 24 h e 48 h;
- garantir que as duas previsões tenham o mesmo tempo válido;
- produzir arquivos compatíveis com JEDI/BFLOW.

Produtos usados adiante:

```text
mpasout.<valid_time>.nc
```

## 2. BFLOW

Ferramenta:

```bash
mpasbflow
```

Objetivo:

- parear f48 e f24;
- calcular `stream_function` e `velocity_potential`;
- adicionar variáveis derivadas;
- gerar a diferença NMC.

Produtos:

```text
FULL_f48.nc
FULL_f24.nc
PTB_f48mf24.nc
```

## 3. VBAL

Ferramenta:

```bash
mpasvbal
```

Objetivo:

- estimar balanço vertical/multivariado;
- calcular relações entre variáveis de controle;
- gerar arquivos globais e locais de balanço.

Produtos:

```text
mpas_vbal.nc
mpas_vbal_local_*.nc
mpas_sampling.nc
mpas_sampling_local_*.nc
```

## 4. HDIAG

Ferramenta:

```bash
mpashdiag
```

Objetivo:

- estimar desvio padrão;
- diagnosticar correlações horizontais e verticais;
- produzir arquivos usados por NICAS e StdDev.

Produtos:

```text
mpas.stddev.nc
mpas.cor_rh.nc
mpas.cor_rv.nc
```

## 5. NICAS

Ferramenta:

```bash
mpasnicas
```

Objetivo:

- construir o operador NICAS;
- gerar produtos locais por rank;
- mesclar produtos por variável em produtos globais finais.

Produtos finais:

```text
merge/mpas_nicas.nc
merge/mpas_nicas_local_*.nc
merge/mpas_nicas_grids_local_*.nc
merge/mpas.nicas_norm.nc
merge/mpas.dirac_nicas.nc
```

## 6. Single Observation

Ferramenta:

```bash
mpasso
```

Objetivo:

- validar a resposta da matriz B;
- verificar incrementos gerados por observações sintéticas;
- testar coerência espacial, vertical e multivariada.

Produtos:

```text
an.*.nc
obsout_SO_T.h5
obsout_SO_U.h5
```

## 7. Verificação

Ferramenta:

```bash
mpasverify
```

Uso típico:

```bash
mpasverify compare \
  --old baseline.nc \
  --new new.nc \
  --write-diff diff.nc \
  --report report.md
```

## Sequência operacional mínima

```bash
mpasforecast prepare ...
mpasforecast submit ...

mpasbflow all ...

mpasvbal prepare ...
mpasvbal submit --wait ...
mpasvbal validate ...

mpashdiag prepare ...
mpashdiag submit --wait ...
mpashdiag validate ...

mpasnicas prepare ...
mpasnicas submit --wait ...
mpasnicas validate ...

mpasso prepare ...
mpasso submit --wait ...
mpasso validate ...
```

## Critérios mínimos de aceite

Uma execução só deve ser considerada válida se:

- todos os jobs terminarem com status final de sucesso;
- todos os arquivos globais e locais esperados existirem;
- `mpasverify` não indicar mudanças inesperadas contra baselines;
- o teste SO produzir incrementos coerentes;
- os logs não indicarem inconsistência de variáveis, dimensões ou ranks.

## Produtos finais da matriz B

Os produtos principais para uso posterior são:

```text
VBAL/mpas_vbal.nc
VBAL/mpas_vbal_local_*.nc
HDIAG/mpas.stddev.nc
NICAS/merge/mpas_nicas.nc
NICAS/merge/mpas_nicas_local_*.nc
NICAS/merge/mpas_nicas_grids_local_*.nc
```

A configuração JEDI/SABER deve apontar para esses diretórios ao aplicar a matriz B em experimentos de assimilação.
