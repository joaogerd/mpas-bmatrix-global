# Quickstart

Este guia mostra a ordem mínima de execução para validar o workflow em uma amostra pequena.

## 1. Instalar e testar comandos

```bash
conda activate mpaswf
pip install -e .

mpasforecast --help
mpasbflow --help
mpasvbal --help
mpashdiag --help
mpasnicas --help
mpasso --help
mpasverify --help
```

## 2. Gerar ou localizar forecasts MPAS

Se os forecasts ainda não existirem, use `mpasforecast` para preparar e submeter f24/f48.

```bash
mpasforecast prepare --config configs/jaci-x1.10242.yaml --init-time YYYY-MM-DD_HH:MM:SS --lead-hours 48
mpasforecast submit  --config configs/jaci-x1.10242.yaml --init-time YYYY-MM-DD_HH:MM:SS --lead-hours 48
```

Repita para o forecast de 24 h.

## 3. Rodar BFLOW

```bash
mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time YYYY-MM-DD_HH:MM:SS \
  --end-valid-time YYYY-MM-DD_HH:MM:SS \
  --workspace $BFLOW \
  --skip-weights \
  --clean-output
```

## 4. Rodar VBAL

```bash
mpasvbal prepare --config configs/jaci-x1.10242.yaml --bflow-workspace $BFLOW --workspace $VBAL --clean
mpasvbal submit --workspace $VBAL --wait
mpasvbal validate --workspace $VBAL
```

## 5. Rodar HDIAG

```bash
mpashdiag prepare --config configs/jaci-x1.10242.yaml --vbal-workspace $VBAL --workspace $HDIAG --clean
mpashdiag submit --workspace $HDIAG --wait
mpashdiag validate --workspace $HDIAG
```

## 6. Rodar NICAS

```bash
mpasnicas prepare --config configs/jaci-x1.10242.yaml --hdiag-workspace $HDIAG --workspace $NICAS --clean
mpasnicas submit --workspace $NICAS --wait
mpasnicas validate --workspace $NICAS
```

## 7. Rodar SO

```bash
mpasso prepare \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace $NICAS \
  --hdiag-workspace $HDIAG \
  --vbal-workspace $VBAL \
  --workspace $SO \
  --clean

mpasso submit --workspace $SO --wait
mpasso validate --workspace $SO
```

## 8. Comparar com baseline

```bash
mpasverify compare \
  --old $OLD/PTB_f48mf24.nc \
  --new $NEW/PTB_f48mf24.nc \
  --write-diff diff.nc \
  --report report.md
```

## O que observar

- Jobs PBS terminando com status de sucesso.
- Produtos globais e locais presentes.
- `mpasverify` sem diferenças inesperadas.
- SO gerando arquivo de análise e obsout.
