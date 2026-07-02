# SABER e BUMP

## Objetivo

SABER é o componente do JEDI responsável por representar e aplicar operadores de covariância de erro. BUMP é usado dentro do SABER para estimar e aplicar estatísticas como variâncias, correlações, balanço e operadores NICAS.

Neste workflow, SABER/BUMP é usado para construir uma matriz B estática global para o MPAS-JEDI.

## De matriz densa para operadores

A matriz B completa seria grande demais para ser armazenada explicitamente. Em vez disso, o sistema representa B como uma composição de operadores:

```text
B ≈ transformações × desvios padrão × correlações × balanços
```

Essa composição permite aplicar B e B⁻¹ de forma eficiente em problemas variacionais.

## Blocos principais usados no workflow

### BUMP_VerticalBalance

Treina relações multivariadas e verticais entre variáveis de controle. É calibrado na etapa VBAL.

Produtos relacionados:

```text
mpas_vbal.nc
mpas_vbal_local_*.nc
```

### BUMP_NICAS

Calcula diagnósticos de correlação e constrói o operador NICAS. É usado nas etapas HDIAG e NICAS.

Produtos relacionados:

```text
mpas.cor_rh.nc
mpas.cor_rv.nc
mpas_nicas.nc
mpas_nicas_local_*.nc
```

### StdDev

Aplica desvios padrão calculados a partir das amostras de erro.

Produto relacionado:

```text
mpas.stddev.nc
```

## Sequência no projeto

```text
BFLOW → amostras NMC
  ↓
VBAL → balanço vertical/multivariado
  ↓
HDIAG → stddev, cor_rh, cor_rv
  ↓
NICAS → operador de correlação/localização
  ↓
SO → validação da B composta
```

## Amostragem

O BUMP recebe amostras de perturbação e calcula estatísticas. A qualidade dessas estatísticas depende de:

- número de membros;
- distribuição temporal;
- consistência da malha;
- qualidade das previsões MPAS;
- variáveis de controle usadas.

## Local versus global

Vários produtos são escritos em duas formas:

- global: arquivo único;
- local: arquivos particionados por rank.

Os arquivos locais são necessários para execução paralela eficiente, enquanto os arquivos globais são úteis para diagnóstico e validação.

## Validação

Uma etapa SABER/BUMP só é considerada válida quando:

- o `runlog` termina com status de sucesso;
- todos os produtos globais existem;
- todos os produtos locais esperados existem;
- o número de arquivos locais é consistente com o número de ranks;
- os produtos são lidos com sucesso pela etapa seguinte.

## Erros comuns

- Número de membros insuficiente.
- Produto local incompleto.
- Variável presente no YAML mas ausente nos NetCDFs.
- Incompatibilidade entre malha, partição e número de ranks.
- Falha em escrita paralela NetCDF.

## Relação com o JEDI

No JEDI, a matriz B é usada dentro da minimização variacional. O SABER fornece os blocos de covariância usados para aplicar a contribuição de background na função custo.

Este repositório não implementa o SABER; ele prepara os dados, YAMLs, diretórios e validações para treinar e testar a matriz B usando os executáveis MPAS-JEDI/SABER.
