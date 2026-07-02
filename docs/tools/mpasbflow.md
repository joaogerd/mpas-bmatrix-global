# `mpasbflow`

## Para que serve

`mpasbflow` constrói as amostras NMC usadas no treinamento da matriz B. Ele recebe pares de previsões MPAS com o mesmo tempo válido e calcula perturbações do tipo:

```text
PTB = forecast_48h - forecast_24h
```

Além disso, converte componentes de vento para variáveis de controle:

```text
u, v -> stream_function, velocity_potential
```

## Papel no workflow da matriz B

O BFLOW é a ponte entre as previsões MPAS e o treinamento estatístico da matriz B. Ele transforma saídas MPAS em arquivos compatíveis com SABER/BUMP.

## Teoria usada

### Método NMC

O método NMC usa diferenças entre previsões válidas no mesmo horário como proxy dos erros de background. A diferença entre 48 h e 24 h é usada porque ambas contêm erro de previsão, mas com amplitudes e estruturas diferentes.

### Função de corrente e potencial de velocidade

O vento horizontal é decomposto em parte rotacional e divergente:

```text
vento -> stream_function + velocity_potential
```

No Python, essa conversão usa `windspharm`, equivalente conceitual às rotinas `uv2sfvp*` do NCL.

### Pesos ESMF

A regridagem MPAS -> lat/lon -> MPAS usa pesos ESMF esparsos (`row`, `col`, `S`). O workflow aplica esses pesos diretamente em Python.

## Entradas

- `manifest.tsv` ou intervalo de tempos válidos.
- Arquivos MPAS f48 e f24.
- Pesos ESMF:
  - `MPAS_<mesh>_to_latlon_1p0_bilinear.nc`
  - `latlon_1p0_to_MPAS_<mesh>_bilinear.nc`
- Arquivo estático/invariant da malha.
- Configuração da plataforma.

## Saídas

Para cada tempo válido:

```text
output/YYYYMMDDHH/FULL_f48.nc
output/YYYYMMDDHH/FULL_f24.nc
output/YYYYMMDDHH/PTB_f48mf24.nc
```

- `FULL_f48.nc`: forecast 48 h com variáveis de controle adicionadas.
- `FULL_f24.nc`: forecast 24 h com variáveis de controle adicionadas.
- `PTB_f48mf24.nc`: diferença NMC final.

## Como funciona internamente

A implementação está em `src/mpas_workflow/bflow_core/`:

- `model.py`: datas, pares e paths;
- `manifest.py`: leitura/escrita do manifesto;
- `workspace.py`: montagem do workspace;
- `weights.py`: leitura e aplicação dos pesos ESMF;
- `psichi.py`: cálculo `u/v -> psi/chi` com `windspharm`;
- `variables.py`: criação de variáveis derivadas;
- `diff.py`: diferença `f48 - f24`;
- `validate.py`: validação dos produtos;
- `runner.py`: orquestração.

## Comandos principais

Preparar workspace:

```bash
mpasbflow prepare \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-10_00:00:00
```

Executar tudo:

```bash
mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-10_00:00:00 \
  --workspace /path/to/bflow_workspace \
  --skip-weights \
  --clean-output
```

Validar:

```bash
mpasbflow validate --workspace /path/to/bflow_workspace --stage ptb
```

## Opções

- `--config`: arquivo de configuração.
- `--start-valid-time`: primeiro tempo válido.
- `--end-valid-time`: último tempo válido.
- `--valid-interval-hours`: intervalo entre tempos válidos.
- `--manifest`: manifesto com pares explícitos.
- `--workspace`: diretório de trabalho.
- `--skip-weights`: não tenta validar/gerar pesos nesta execução.
- `--clean-output`: remove produtos anteriores antes de rodar.

## Validação

Compare o produto novo com um baseline:

```bash
mpasverify compare \
  --old OLD/PTB_f48mf24.nc \
  --new NEW/PTB_f48mf24.nc \
  --write-diff diff_ptb.nc \
  --report report.md
```

Critérios típicos:

- variáveis copiadas: idênticas;
- `temperature`/`spechum`: diferenças numéricas pequenas;
- `stream_function` e `velocity_potential`: correlação próxima de 1;
- `RelRMSE` pequeno em relação ao desvio padrão do campo.

## Problemas comuns

- Pesos ESMF ausentes ou com dimensões incompatíveis.
- `windspharm` não instalado corretamente.
- Ordem de grade lat/lon incompatível.
- Forecasts f48/f24 não correspondem ao mesmo tempo válido.
- Variáveis MPAS nativas ausentes no arquivo de entrada.
