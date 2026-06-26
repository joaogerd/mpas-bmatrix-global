# Plano de teste da refatoração BFLOW

## 1. Teste de importação

```bash
python -m compileall src/mpas_workflow/bflow.py src/mpas_workflow/bflow_core
python -c 'from mpas_workflow.bflow import main; print(main)'
```

## 2. Teste de preparação

```bash
mpasbflow prepare \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --force
```

Verificar:

```bash
find $WORKSPACE -maxdepth 3 -type f | sort
cat $WORKSPACE/manifest.tsv
```

## 3. Teste ponta a ponta

```bash
mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --clean-output \
  --force
```

Verificar:

```bash
find $WORKSPACE/output -name PTB_f48mf24.nc -print
find $WORKSPACE/logs -type f -maxdepth 1 -print
```

## 4. Comparação com fluxo antigo

Se houver produtos antigos disponíveis:

```bash
ncdump -h antigo/PTB_f48mf24.nc > /tmp/old.header
ncdump -h novo/PTB_f48mf24.nc > /tmp/new.header
diff -u /tmp/old.header /tmp/new.header
```

Para comparação numérica, usar Python/xarray ou NCO, avaliando no mínimo:

- `stream_function`;
- `velocity_potential`;
- `temperature`;
- `spechum`;
- `pressure`;
- `surface_pressure`.

## 5. Critério de aceite

- O comando `mpasbflow all` produz todos os `PTB_f48mf24.nc` esperados.
- A validação interna passa para os estágios `full` e `ptb`.
- As diferenças contra o fluxo antigo são nulas ou explicáveis pela substituição do template NCO por `netCDF4`.
