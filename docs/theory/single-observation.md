# Teste de observação única

## Objetivo

O teste de observação única avalia a resposta da matriz B a uma observação sintética isolada. Ele é uma ferramenta de validação física e numérica.

## Por que fazer esse teste?

Mesmo que VBAL, HDIAG e NICAS executem sem erro, a matriz B pode produzir incrementos ruins. O teste de observação única ajuda a verificar:

- escala horizontal dos incrementos;
- estrutura vertical;
- relações multivariadas;
- sinal dos incrementos;
- suavidade espacial;
- presença de ruído ou artefatos.

## Ideia básica

Uma observação sintética é colocada em uma posição, nível e variável conhecidos. O sistema executa uma assimilação simples e gera uma análise.

```text
Background + observação sintética + B
                 ↓
              análise
                 ↓
           incremento = análise - background
```

O incremento revela como a matriz B espalha a informação observacional.

## O que observar

### Estrutura espacial

O incremento deve ser suave e compatível com as escalas horizontais estimadas pelo NICAS.

### Estrutura vertical

O incremento deve ter coerência vertical. Estruturas pontuais ou descontínuas podem indicar problema nas correlações verticais.

### Relações multivariadas

Uma observação de temperatura ou vento pode produzir resposta em outras variáveis, dependendo do balanceamento treinado.

### Sinal

Incrementos com sinal invertido podem indicar erro de convenção, variável, unidade ou operador de observação.

## Variantes no workflow

O `mpasso` suporta:

- `default`: temperatura e vento zonal;
- `t-only`: apenas temperatura;
- `u-only`: apenas vento zonal.

Essas variantes ajudam a isolar problemas.

## Entradas

- produtos NICAS;
- produto de desvio padrão;
- produtos VBAL;
- background compatível;
- configuração variacional JEDI.

## Saídas

- arquivo de análise `an.*.nc`;
- arquivos `obsout_SO_*.h5`;
- logs de execução.

## Validação qualitativa

É recomendado visualizar:

- incremento de temperatura;
- incremento de vento;
- incremento de pressão de superfície;
- cortes verticais;
- mapas horizontais em níveis selecionados.

## Validação quantitativa

Comparar execuções com `mpasverify` e calcular:

- máximo absoluto do incremento;
- norma do incremento;
- localização do máximo;
- simetria e decaimento espacial;
- diferença entre configurações de B.

## Problemas comuns

- operador de observação incompatível com variáveis do background;
- unidade de pressão incorreta;
- variáveis derivadas ausentes no `bg_so.nc`;
- produtos NICAS incompletos;
- balanceamento produzindo resposta multivariada inesperada.

## Interpretação

O teste SO não prova que a matriz B é operacionalmente ótima. Ele verifica se a matriz B é fisicamente plausível e numericamente utilizável. A validação final exige experimentos de assimilação e impacto em previsão.
