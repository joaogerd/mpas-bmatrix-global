# Introdução à assimilação de dados

## Objetivo

Assimilação de dados é o processo de combinar informações de um modelo numérico com observações para produzir a melhor estimativa possível do estado da atmosfera. Essa estimativa é chamada de análise e serve como condição inicial para previsões subsequentes.

## Elementos principais

```text
Estado verdadeiro da atmosfera
        ↓
Observações imperfeitas
        ↓
Background do modelo
        ↓
Assimilação de dados
        ↓
Análise
        ↓
Previsão
```

## Background

O background, geralmente indicado por `x_b`, é uma estimativa prévia do estado atmosférico. Em sistemas operacionais, normalmente vem de uma previsão curta iniciada a partir da análise anterior.

O background contém erro. Esse erro é representado estatisticamente pela matriz B.

## Observações

As observações, indicadas por `y`, podem vir de:

- estações de superfície;
- radiossondas;
- aeronaves;
- satélites;
- radares;
- boias;
- sensores diversos.

Elas também possuem erro, representado pela matriz R.

## Operador de observação

O modelo representa o estado em uma grade e em variáveis próprias. As observações estão em posições, níveis e variáveis diferentes. O operador de observação `H` converte o estado do modelo para o espaço das observações.

```text
H(x) ≈ equivalente observado pelo modelo
```

## Análise

A análise é o estado que equilibra duas informações:

- não se afastar demais do background;
- ajustar-se às observações dentro das incertezas observacionais.

Em 3D-Var, isso aparece na função custo:

```text
J(x) = J_b(x) + J_o(x)
```

onde:

```text
J_b(x) = 1/2 (x - x_b)^T B^{-1} (x - x_b)
J_o(x) = 1/2 (H(x) - y)^T R^{-1} (H(x) - y)
```

## Papel da matriz B

A matriz B define como o sistema interpreta diferenças entre análise e background. Ela controla:

- amplitude dos incrementos;
- espalhamento horizontal;
- espalhamento vertical;
- relações multivariadas;
- equilíbrio físico dos incrementos.

Uma B ruim pode produzir incrementos ruidosos, fisicamente inconsistentes ou com impacto negativo na previsão.

## Métodos de assimilação

### 3D-Var

Usa observações dentro de uma janela, mas sem evolução explícita do modelo dentro da janela. É mais simples e robusto.

### 4D-Var

Usa o modelo para propagar a informação dentro da janela temporal. É mais caro e exige modelo tangente linear e adjunto.

### EnKF

Usa ensembles para estimar covariâncias de erro dependentes do fluxo.

### Métodos híbridos

Combinam uma matriz B climatológica/estática com informação de ensemble.

## Onde entra este projeto

Este repositório trata da construção de uma matriz B estática para o MPAS-JEDI usando:

- método NMC;
- variáveis de controle meteorológicas;
- SABER/BUMP;
- diagnóstico e validação por observação única.

A matriz B resultante pode ser usada como componente estático ou base inicial para configurações híbridas futuras.
