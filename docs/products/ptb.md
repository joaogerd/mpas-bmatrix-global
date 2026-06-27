# `PTB_f48mf24.nc`

## O que é

`PTB_f48mf24.nc` é a perturbação NMC calculada como diferença entre forecasts de 48 h e 24 h válidos no mesmo horário:

```text
PTB = FULL_f48 - FULL_f24
```

## Quem produz

```text
mpasbflow
```

## Quem utiliza

- `mpasvbal`
- `mpashdiag`
- `mpasnicas`
- diagnósticos e validações da matriz B

## Papel científico

Este arquivo é uma amostra de erro de background. Um conjunto de arquivos `PTB_f48mf24.nc` forma o ensemble estatístico usado pelo SABER/BUMP para estimar a matriz B.

## Conteúdo esperado

Variáveis principais:

- `stream_function`
- `velocity_potential`
- `temperature`
- `spechum`
- `surface_pressure`

## Como validar

Comparar com baseline:

```bash
mpasverify compare \
  --old baseline/PTB_f48mf24.nc \
  --new novo/PTB_f48mf24.nc \
  --write-diff diff_ptb.nc \
  --report report.md
```

Verificar métricas:

- correlação alta para campos equivalentes;
- `RelRMSE` pequeno em refatorações;
- ausência de inversão de sinal;
- dimensões compatíveis.

## Problemas comuns

- forecast f24 e f48 não têm o mesmo tempo válido;
- variáveis ausentes em `FULL_f24` ou `FULL_f48`;
- erro de sinal em `velocity_potential`;
- diferença de ordem de grade ao calcular `psi/chi`;
- pesos ESMF incorretos.
