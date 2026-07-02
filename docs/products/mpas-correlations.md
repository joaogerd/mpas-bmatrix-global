# `mpas.cor_rh.nc` e `mpas.cor_rv.nc`

## O que são

Arquivos de correlação diagnóstica horizontal e vertical produzidos pela etapa HDIAG.

```text
mpas.cor_rh.nc  → correlação horizontal
mpas.cor_rv.nc  → correlação vertical
```

## Quem produz

```text
mpashdiag
```

## Quem utiliza

```text
mpasnicas
```

## Papel científico

Esses arquivos descrevem escalas de correlação estimadas a partir das perturbações NMC. O NICAS usa essas informações para construir operadores de correlação/localização.

## Como validar

```bash
mpashdiag validate --workspace $HDIAG
```

Também é recomendado verificar:

- existência dos arquivos;
- variáveis esperadas;
- ausência de valores não finitos;
- coerência espacial das escalas.

## Problemas comuns

- HDIAG terminou sem produzir os arquivos;
- poucos membros NMC geram correlações instáveis;
- variáveis do YAML não batem com variáveis dos arquivos;
- NICAS falha ao ler `cor_rh` ou `cor_rv`.
