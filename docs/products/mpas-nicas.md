# `mpas_nicas.nc` e produtos NICAS locais

## O que são

Produtos que representam o operador NICAS de correlação/localização da matriz B.

## Quem produz

```text
mpasnicas
```

## Quem utiliza

- `mpasso`
- configurações SABER/JEDI que aplicam a matriz B

## Produtos principais

```text
mpas_nicas.nc
mpas_nicas_local_*.nc
mpas_nicas_grids_local_*.nc
mpas.nicas_norm.nc
mpas.dirac_nicas.nc
```

## Papel científico

O NICAS evita armazenar uma matriz de correlação completa. Ele representa a correlação por operadores locais e estruturas auxiliares escaláveis.

## Produtos locais e merge

Cada variável é processada separadamente. Depois, os produtos são mesclados no diretório `merge/`.

O arquivo `merge.done` indica que a etapa de merge terminou.

## Como validar

```bash
mpasnicas validate --workspace $NICAS
```

A validação confere:

- produtos por variável;
- produtos locais por rank;
- produtos globais mesclados;
- existência de `merge.done`.

## Problemas comuns

- falha no merge por ausência de NCO;
- produtos locais incompletos;
- inconsistência no número de ranks;
- arquivos `mpas.cor_rh.nc` ou `mpas.cor_rv.nc` ausentes;
- falha transitória de PBS/HOME.
