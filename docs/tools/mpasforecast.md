# `mpasforecast`

## Para que serve

`mpasforecast` prepara e submete previsões MPAS necessárias para gerar pares NMC. Ele é usado para produzir previsões com diferentes alcances, por exemplo 24 h e 48 h, que depois serão comparadas no mesmo tempo válido pelo `mpasbflow`.

## Papel no workflow da matriz B

O método NMC precisa de duas previsões válidas no mesmo horário, mas iniciadas em horários diferentes:

```text
forecast iniciado em t-48h, válido em t
forecast iniciado em t-24h, válido em t
```

O `mpasforecast` organiza os diretórios de execução, links, namelist, streams e PBS para essas previsões.

## Teoria envolvida

A etapa em si não estima a matriz B. Ela fornece as previsões usadas para construir amostras de erro por diferença NMC:

```text
perturbação = forecast_48h - forecast_24h
```

A qualidade, consistência e reprodutibilidade dessas previsões afetam diretamente a matriz B final.

## Entradas

- Arquivo de configuração, normalmente `configs/jaci-x1.10242.yaml`.
- Condição inicial MPAS já preparada.
- Arquivos estáticos da malha:
  - grid MPAS;
  - `graph.info`;
  - partições;
  - invariant;
  - arquivos físicos/tabelas do MPAS.
- Executável `mpas_atmosphere`.

## Saídas

Em cada diretório de forecast, a ferramenta cria:

- `namelist.atmosphere`
- `streams.atmosphere`
- links para arquivos estáticos;
- `run_mpas_forecast.pbs`
- arquivo de saída esperado do tipo `mpasout.YYYY-MM-DD_HH.MM.SS.nc`;
- restart esperado `restart.YYYY-MM-DD_HH.MM.SS.nc`.

O produto usado pelo BFLOW é:

```text
mpasout.<valid_time>.nc
```

## Como funciona internamente

A lógica está organizada em `src/mpas_workflow/mpas_core/`:

- `model.py`: datas, nomes e paths esperados;
- `streams.py`: edição de `streams.atmosphere`;
- `setup.py`: montagem do diretório de execução;
- `jobs.py`: submissão PBS;
- `checks.py`: validação pré-execução;
- `cli.py`: interface de linha de comando.

## Comandos principais

Preparar uma previsão:

```bash
mpasforecast prepare \
  --config configs/jaci-x1.10242.yaml \
  --init-time 2026-06-08_00:00:00 \
  --lead-hours 48
```

Submeter:

```bash
mpasforecast submit \
  --config configs/jaci-x1.10242.yaml \
  --init-time 2026-06-08_00:00:00 \
  --lead-hours 48
```

## Opções

- `--config`: arquivo YAML de configuração da plataforma.
- `--init-time`: tempo inicial no formato `YYYY-MM-DD_HH:MM:SS`.
- `--lead-hours`: alcance da previsão em horas.
- `--dt`: passo de tempo do MPAS. Se omitido, usa o valor do YAML.
- `--output-interval`: intervalo de saída. Se omitido, usa o valor do YAML.

## Validação

A validação pré-execução confere:

- existência do executável;
- existência da condição inicial;
- links de malha e partições;
- opções críticas do namelist;
- streams necessários para gerar saída compatível com JEDI.

## Problemas comuns

- Partição inexistente para o número de MPI ranks.
- Caminho incorreto para `mpas_atmosphere`.
- `config_dt` incompatível com a malha.
- `streams.atmosphere` sem stream `da_state`.
- Forecast executa, mas não gera `mpasout` no tempo válido esperado.
