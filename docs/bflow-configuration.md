# Configuração do BFLOW

## Objetivo

O comando padrão `mpasbflow` agora lê as decisões físicas e científicas do bloco `bflow` em:

```text
configs/bmatrix-x1.10242.yaml
```

A infraestrutura continua em:

```text
configs/jaci-x1.10242.yaml
```

```text
jaci-x1.10242.yaml
  caminhos, executáveis, malha, MPI, PBS e ambiente

bmatrix-x1.10242.yaml
  controles SABER, VBAL, HDIAG, NICAS, DIRAC, SO e BFLOW
```

Ao executar `mpasbflow prepare` ou `mpasbflow all`, o workflow grava uma cópia resolvida da configuração em:

```text
$BFLOW/bflow_config.json
```

Essa cópia é a referência reproduzível usada pelos scripts gerados no workspace. Alterar o YAML depois da preparação não altera retroativamente um workspace já preparado.

## NMC

O bloco abaixo controla a seleção temporal dos pares:

```yaml
bflow:
  nmc:
    older_lead_hours: 48
    newer_lead_hours: 24
    older_label: f48
    newer_label: f24
```

A amostra é sempre calculada como:

```text
forecast older_lead_hours − forecast newer_lead_hours
```

Com os valores atuais:

```text
PTB = f48 − f24
```

Os nomes internos históricos `f048` e `f024` do manifesto são mantidos por compatibilidade; o cálculo dos leads é configurável.

## Produtos

```yaml
products:
  template: template_PTB.nc
  older_full: FULL_f48.nc
  newer_full: FULL_f24.nc
  perturbation: PTB_f48mf24.nc
```

Esses valores definem os nomes de arquivos que os scripts BFLOW criam e consomem. Se forem modificados, uma nova preparação de workspace é obrigatória.

## Regridding ESMF

O bloco `regridding` concentra a grade auxiliar, pesos e método de interpolação:

```yaml
regridding:
  scrip_resolution: 1.0deg
  interpolation_method: bilinear
  lower_left: [-89.5, -179.5]
  upper_right: [89.5, 179.5]
  weight_latlon_to_mpas: latlon_1p0_to_MPAS_{mesh_name}_bilinear.nc
  weight_mpas_to_latlon: MPAS_{mesh_name}_to_latlon_1p0_bilinear.nc
```

`{mesh_name}` é resolvido automaticamente a partir de `mesh.name` no YAML de plataforma.

Ao mudar resolução, domínio, método ou malha, não reutilize os pesos ESMF existentes. Rode sem `--skip-weights` e gere um workspace novo.

## Conversão de vento para psi/chi

```yaml
wind_transform:
  zonal_file_variable: uReconstructZonal
  meridional_file_variable: uReconstructMeridional
  template_file_variable: theta
  radius_numerator_m: 6371229.0
  radius_denominator_m: 6371220.0
```

Os campos físicos produzidos são ligados aos controles canônicos da matriz B:

```yaml
outputs:
  stream_function:
    output_control: air_horizontal_streamfunction
  velocity_potential:
    output_control: air_horizontal_velocity_potential
```

Assim, os nomes físicos continuam vindo de `controls[].file`, enquanto o contrato científico usa `controls[].code`.

## Campos copiados e derivados

A lista `copy_variables` define quais campos do forecast MPAS são copiados para os arquivos `FULL_*`.

`derived_variables` declara transformações suportadas pelo renderer:

```yaml
- operation: sum
- operation: potential_temperature_to_temperature
- operation: mixing_ratio_to_specific_humidity
```

Cada transformação define a saída, entradas, campo-template NetCDF e atributos. As três operações atuais representam:

```text
pressure    = pressure_p + pressure_base
temperature = theta × (pressure / reference_pressure_pa)^exponent
spechum     = qv / (1 + qv)
```

Para modificar fontes, nomes, escala de Exner, atributos, pressão de referência ou expoente, altere somente o YAML e prepare o BFLOW novamente.

## Validação

O bloco `validation` declara os campos e dimensões exigidos nos produtos `FULL_*` e `PTB_*`.

```yaml
validation:
  full_required: [...]
  ptb_required: [...]
  dimension_checks:
    - file: stream_function
      dimensions: [Time, nCells, nVertLevels]
```

Isso elimina a lista fixa de variáveis dentro do script Python gerado.

## Compatibilidade e migração

Depois de atualizar o repositório:

```bash
source scripts/load_jaci_env.sh
conda activate mpaswf
python -m pip install -e .
```

Use normalmente:

```bash
mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --clean-output \
  --force
```

O comportamento anterior permanece disponível para comparação:

```bash
mpasbflow-legacy all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --clean-output \
  --force
```

## Quando regenerar

| Alteração | O que deve ser refeito |
| --- | --- |
| Leads NMC, nomes de produtos, regridding, vento, campos copiados/derivados ou validações BFLOW | BFLOW → VBAL → HDIAG → NICAS → SO → DIRAC |
| `controls` ou mapeamento `code`/`file` | BFLOW → VBAL → HDIAG → NICAS → SO → DIRAC |
| VBAL | VBAL → HDIAG → NICAS → SO → DIRAC |
| HDIAG | HDIAG → NICAS → SO → DIRAC |
| NICAS | NICAS → SO → DIRAC |
| SO ou DIRAC | somente o teste alterado |
