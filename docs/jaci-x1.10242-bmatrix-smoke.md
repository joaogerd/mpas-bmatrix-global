# Smoke test da matriz B global no JACI — x1.10242

Este documento registra o primeiro fluxo validado de geração e teste da matriz B global do MPAS-JEDI/SABER no JACI para a malha `x1.10242`, usando 128 ranks MPI.

A cadeia validada é:

```text
Bflow preprocessing -> VBAL -> HDIAG -> NICAS -> SO -> Dirac
```

A forma conceitual usada é:

```text
B = K1 K2 Sigma C Sigma^T K2^T K1^T
```

onde `K1` representa a transformação de controle para análise, `K2` representa o balanço vertical, `Sigma` representa os desvios-padrão e `C` representa as correlações locais BUMP/NICAS.

## Configuração validada

```text
config: configs/jaci-x1.10242.yaml
mesh: x1.10242
nproc: 128
queue: pesqmidi
nVertLevels: 55
python env: mpaswf
```

Os PBS carregam `scripts/load_jaci_env.sh` e usam `OMP_NUM_THREADS=1`, `GFORTRAN_CONVERT_UNIT=big_endian:101-200`, `FI_CXI_RX_MATCH_MODE=hybrid` e `ulimit -s unlimited`.

Mensagens intermitentes do JACI sobre `HOME`, como `cannot access home directory`, não devem ser tratadas como falha científica quando o job executa no diretório de trabalho e o runlog termina com `status = 0`.

## Smoke vs produção

Este documento descreve o baseline smoke validado. A separação entre esse caso e uma futura configuração de produção está documentada em [bmatrix-smoke-vs-production.md](bmatrix-smoke-vs-production.md).

O smoke deve permanecer pequeno, reproduzível e estável para integração/regressão. Ele não deve ser tratado como estatística final de produção da B-matrix.

## Etapas validadas

### Bflow

Produto esperado por data:

```text
PTB_f48mf24.nc
```

Variáveis verificadas:

```text
stream_function
velocity_potential
temperature
spechum
pressure
surface_pressure
```

### VBAL

Produtos esperados:

```text
VBAL/mpas_vbal.nc
VBAL/mpas_sampling.nc
```

Validação observada:

```text
MEMBERS=4
SAMPLING_GLOBAL=True
VBAL_GLOBAL=True
SAMPLING_LOCAL=128
VBAL_LOCAL=128
SUCCESS: VBAL validado.
```

### HDIAG

Produtos esperados:

```text
HDIAG/mpas.stddev.nc
HDIAG/mpas.cor_rh.nc
HDIAG/mpas.cor_rv.nc
HDIAG/mpas_diag.nc
HDIAG/mpas_sampling.nc
```

O smoke test validado usa 4 membros. Uma tentativa com 3 membros falhou porque o BUMP exigiu mais membros para essa etapa.

### NICAS

Variáveis processadas:

```text
stream_function
velocity_potential
temperature
spechum
surface_pressure
```

O merge NICAS é a entrada usada pelas etapas SO e Dirac.

### SO

Variantes validadas:

```text
t-only
default
```

Produtos esperados para `t-only`:

```text
an.2026-06-10_00.00.00.nc
obsout_SO_T.h5
run_SO_t_only.runlog
```

Produtos esperados para `default`:

```text
an.2026-06-10_00.00.00.nc
obsout_SO_T.h5
obsout_SO_U.h5
run_SO.runlog
```

Critério de sucesso:

```text
Run: Finishing oops::Variational<MPAS, UFO and IODA observations> with status = 0
```

Correções importantes aplicadas ao SO:

- `background.transform model to analysis: false`;
- criação de `bg_so.nc` enriquecido com variáveis diagnósticas;
- inclusão de aliases canônicos usados por `Model2GeoVars/GetValueTLADs`.

Aliases adicionados:

```text
air_pressure = pressure
air_pressure_at_surface = surface_pressure
air_temperature = temperature
eastward_wind = uReconstructZonal
northward_wind = uReconstructMeridional
```

Esses aliases entram apenas em `background.state variables`. As variáveis de controle/análise permanecem inalteradas.

### Dirac

Artefatos gerados pelo prepare:

```text
run_dirac.yaml
qsub_dirac.bash
README.md
```

Produto esperado:

```text
mpas.dirac.nc
```

Critério de sucesso:

```text
Run: Finishing oops::ErrorCovarianceToolbox<MPAS> with status = 0
```

O Dirac validado aplica impulso em `temperature` e escreve `mpas.dirac.nc`.

## Sequência operacional validada

### Agregador seguro

Depois que o Bflow gerou o workspace de entrada, a cadeia de covariância pode ser executada pelo agregador:

```bash
mpasbcov pipeline-all \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --clean \
  --poll-seconds 30 \
  --retries 2
```

Para validar uma cadeia já executada sem preparar, limpar ou submeter jobs:

```bash
mpasbcov pipeline-all \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --validate-only
```

O agregador resolve os workspaces esperados em sequência:

```text
vbal  = covariance/vbal/<BFLOW_NAME>
hdiag = covariance/hdiag/<BFLOW_NAME>
nicas = covariance/nicas/<BFLOW_NAME>
so    = covariance/so/<BFLOW_NAME>
dirac = covariance/dirac/<BFLOW_NAME>
```

O resumo final imprime cada workspace e o status da etapa.

### Execução etapa a etapa

### Bflow

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

### VBAL

```bash
mpasbcov vbal-all \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --clean \
  --poll-seconds 30
```

### HDIAG

```bash
mpasbcov hdiag-all \
  --config configs/jaci-x1.10242.yaml \
  --vbal-workspace "$VBAL" \
  --clean \
  --poll-seconds 30
```

### NICAS

```bash
mpasbcov nicas-all \
  --config configs/jaci-x1.10242.yaml \
  --hdiag-workspace "$HDIAG" \
  --clean \
  --poll-seconds 30
```

### SO

```bash
mpasbcov so-all \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --clean \
  --poll-seconds 30
```

Validação explícita:

```bash
python -m mpas_workflow.bcov so-validate \
  --workspace "$SO" \
  --variant default
```

### Dirac

```bash
python -m mpas_workflow.bcov dirac-submit \
  --workspace "$DIRAC" \
  --wait \
  --poll-seconds 30 \
  --retries 2

python -m mpas_workflow.bcov dirac-validate \
  --workspace "$DIRAC"
```

Resumo diagnóstico do produto Dirac:

```bash
mpasbcov dirac-summary --workspace "$DIRAC"
```

Figuras simples do produto Dirac, sem Cartopy:

```bash
mpasbcov dirac-plot \
  --workspace "$DIRAC" \
  --variables temperature surface_pressure stream_function velocity_potential \
  --level 30 \
  --output-dir "$DIRAC/figures"
```

Figuras diagnósticas das etapas de covariância:

```bash
mpasbcov hdiag-plot --workspace "$HDIAG" --level 30 --output-dir "$HDIAG/figures"
mpasbcov nicas-plot --workspace "$NICAS" --level 30 --output-dir "$NICAS/figures"
mpasbcov vbal-plot  --workspace "$VBAL"  --output-dir "$VBAL/figures"
```

Relatório consolidado do smoke test. O comando escreve `report.md` e, por padrão, também cria `index.html` no mesmo diretório para navegar pelas figuras PNG:

```bash
mpasbcov report \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --vbal-workspace "$VBAL" \
  --hdiag-workspace "$HDIAG" \
  --nicas-workspace "$NICAS" \
  --so-workspace "$SO" \
  --dirac-workspace "$DIRAC" \
  --figures-dir "$HDIAG/figures" \
  --figures-dir "$NICAS/figures" \
  --figures-dir "$VBAL/figures" \
  --figures-dir "$DIRAC/figures" \
  --output "$DIRAC/report.md"
```

Para inspecionar localmente, baixe o diretório com `report.md`, `index.html` e os subdiretórios de figuras, então abra `index.html` no navegador.

## Estado final validado

```text
Bflow             OK
VBAL              OK
HDIAG             OK
NICAS             OK
SO t-only         OK
SO default        OK
SO validation     OK
Dirac             OK
Dirac validation  OK
```

## Commits relacionados

```text
3c80589 Add end-to-end Bflow command and validation
bbccdb5 Add covariance VBAL app workflow
579ce59 Adapt covariance workflow for SABER develop
ad540b2 Make NICAS submission robust on JACI
9423c5c Ignore stale PBS HOME failures in NICAS validation
5c17314 Fix SO background and GeoVaLs variables
6edbf4f Fix SO validation logic
5c24d33 Add Dirac covariance workflow
```

## Próximos passos sugeridos

1. Melhorar a documentação dos argumentos de cada subcomando.
2. Criar visualização simples do `mpas.dirac.nc` para inspeção espacial/vertical do impulso.
3. Separar claramente smoke test de produção, aumentando número de membros apenas em configurações próprias de produção.
4. Adicionar notas de troubleshooting para PBS/HOME, `air_pressure`, aliases de GeoVaLs e validação de logs.
