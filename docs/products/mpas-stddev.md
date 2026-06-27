# `mpas.stddev.nc`

## O que é

`mpas.stddev.nc` contém estimativas de desvio padrão dos erros de background para as variáveis de controle.

## Quem produz

```text
mpashdiag
```

## Quem utiliza

- `mpasso`
- configurações SABER com bloco `StdDev`
- validação da matriz B

## Papel científico

O desvio padrão define a amplitude esperada dos erros. Na aplicação da matriz B, ele controla a escala dos incrementos.

Se o desvio padrão for muito pequeno, a análise tende a confiar excessivamente no background. Se for muito grande, a análise pode produzir incrementos exagerados.

## Conteúdo esperado

Variáveis de controle, por exemplo:

- `stream_function`
- `velocity_potential`
- `temperature`
- `spechum`
- `surface_pressure`

## Como validar

```bash
mpashdiag validate --workspace $HDIAG
```

Também é recomendado verificar:

- valores finitos;
- ausência de desvios padrão negativos;
- magnitudes plausíveis;
- consistência espacial.

## Problemas comuns

- arquivo ausente após HDIAG;
- variáveis ausentes;
- valores não finitos;
- magnitudes anômalas por poucas amostras NMC.
