# Produtos do teste de observação única

## O que são

Arquivos gerados pelo `mpasso` para validar a resposta da matriz B a observações sintéticas.

## Quem produz

```text
mpasso
```

## Produtos principais

```text
bg_so.nc
run_SO.yaml
run_SO.runlog
an.*.nc
obsout_SO_T.h5
obsout_SO_U.h5
```

## Quem utiliza

- usuário/pesquisador para validação;
- ferramentas de visualização;
- `mpasverify` para comparação numérica.

## Papel científico

O arquivo `an.*.nc` contém a análise gerada pelo teste. A diferença entre análise e background mostra a resposta espacial, vertical e multivariada da matriz B.

## Como validar

```bash
mpasso validate --workspace $SO
```

Verifique também:

- se `an.*.nc` foi criado;
- se os arquivos `obsout` existem;
- se o incremento possui padrão físico plausível;
- se não há status final diferente de zero nos logs.

## Problemas comuns

- `bg_so.nc` sem variáveis derivadas;
- operador de observação incompatível;
- produtos NICAS ou VBAL incompletos;
- análise ausente;
- incremento ruidoso ou com sinal inesperado.
