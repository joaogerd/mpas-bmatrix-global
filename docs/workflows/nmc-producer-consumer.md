# Contrato entre o produtor MPAS e o consumidor da matriz B

## Objetivo

O repositório `monan-jedi-workflow` é o produtor dos dados de forecast MPAS.
O `mpas-bmatrix-global` é o consumidor científico dos pares NMC e executa:

```text
BFLOW -> VBAL -> HDIAG -> NICAS -> SO
```

A integração não usa importações Python entre repositórios e não depende de um
layout interno de diretórios. Ela usa um manifesto tabulado pequeno, versionável
e validável.

## O que o produtor deve fazer

Para cada tempo válido `t`, produzir dois forecasts MPAS com a mesma malha,
partição, física, `config_dt` e convenção de variáveis:

```text
f048: iniciado em t - 48 h, válido em t
f024: iniciado em t - 24 h, válido em t
```

Quando a fonte é GRIB, a sequência é:

```text
campos de análise/condição inicial
-> WPS/ungrib
-> mpas_init_atmosphere
-> mpas_atmosphere f024/f048
-> restart e mpasout (stream da_state)
```

O `restart` é usado pelo produtor para conferir que o par NMC foi construído
com estados MPAS compatíveis. O BFLOW consome os arquivos `mpasout` do stream
`da_state`, porque eles carregam as variáveis necessárias para gerar
`stream_function`, `velocity_potential`, temperatura e umidade específica.

## Manifesto BFLOW

O produtor escreve `bflow-manifest.tsv`:

```tsv
valid_time	f048	f024
2026-06-22T00:00:00Z	/forecast/f048/mpasout.2026-06-22_00.00.00.nc	/forecast/f024/mpasout.2026-06-22_00.00.00.nc
```

As colunas obrigatórias são:

- `valid_time`: ISO-8601 com fuso ou formato MPAS `YYYY-MM-DD_HH:MM:SS`;
- `f048`: caminho do `mpasout` antigo, válido no mesmo horário;
- `f024`: caminho do `mpasout` recente, válido no mesmo horário.

`mpasnmc validate-manifest` e `mpasbflow` normalizam timestamps ISO para a
convenção MPAS antes de montar workspaces.

## Número mínimo de pares

A campanha precisa ter no mínimo quatro pares completos. Este é um limiar
operacional para smoke técnico, não uma amostragem suficiente para uma matriz B
de produção. O consumidor rejeita manifestos com menos de quatro linhas de
amostra, horários duplicados, horários fora de ordem, arquivos ausentes, vazios
ou caminhos iguais para f024 e f048.

Com quatro tempos válidos separados por seis horas, o produtor precisa de oito
inicializações independentes. A campanha inicia 48 h antes do primeiro tempo
válido e só termina no último tempo válido; portanto, não deve ser interpretada
como apenas uma rodada de dois dias de dados.

## Uso

Depois que `monan-jedi-workflow` tiver exportado o manifesto:

```bash
mpasnmc validate-manifest \
  --manifest /caminho/bflow-manifest.tsv \
  --minimum-pairs 4

mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --manifest /caminho/bflow-manifest.tsv \
  --workspace /caminho/bflow \
  --minimum-pairs 4 \
  --clean-output
```

O BFLOW cria um workspace com `inputs/`, `manifest.tsv`, `FULL_f24.nc`,
`FULL_f48.nc` e `PTB_f48mf24.nc`. Os PTBs são as amostras usadas pelas etapas
VBAL, HDIAG e NICAS.
