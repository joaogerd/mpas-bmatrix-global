# Nota de validação BFLOW

Esta branch deve ser validada no JACI porque as etapas remanescentes dependem de módulos e executáveis disponíveis no ambiente operacional, especialmente NCL.

Validação mínima:

```bash
python -m compileall src/mpas_workflow/bflow.py src/mpas_workflow/bflow_core
mpasbflow prepare --config configs/jaci-x1.10242.yaml --start-valid-time 2026-06-10_00:00:00 --end-valid-time 2026-06-13_00:00:00 --valid-interval-hours 24 --dt 60 --force
mpasbflow all --config configs/jaci-x1.10242.yaml --start-valid-time 2026-06-10_00:00:00 --end-valid-time 2026-06-13_00:00:00 --valid-interval-hours 24 --dt 60 --clean-output --force
```

A saída esperada é um conjunto de arquivos `output/YYYYMMDDHH/PTB_f48mf24.nc`, um para cada horário válido no manifesto.
