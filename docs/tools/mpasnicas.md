# `mpasnicas`

## Para que serve

`mpasnicas` prepara, executa, mescla e valida a etapa NICAS da matriz B. NICAS constrói uma representação eficiente das correlações espaciais usadas pelo SABER.

## Papel no workflow da matriz B

Após HDIAG calcular variâncias e correlações diagnósticas, NICAS transforma essas informações em operadores utilizáveis na aplicação da covariância de background.

## Teoria usada

NICAS representa correlações por meio de operadores locais e grades auxiliares, evitando armazenar uma matriz de correlação completa. Isso torna possível aplicar correlações em malhas grandes como MPAS global.

No workflow, NICAS é executado por variável de controle e depois os produtos locais/globais são mesclados.

## Entradas

- Workspace HDIAG validado.
- Arquivos:
  - `mpas.cor_rh.nc`
  - `mpas.cor_rv.nc`
  - `mpas.stddev.nc`
- Arquivos estáticos MPAS.
- Executável `mpasjedi_error_covariance_toolbox.x`.

## Saídas

Por variável de controle:

```text
<variable>/run_nicas.yaml
<variable>/qsub_nicas.bash
<variable>/mpas_nicas.nc
<variable>/mpas_nicas_local_*.nc
<variable>/mpas_nicas_grids_local_*.nc
<variable>/mpas.nicas_norm.nc
<variable>/mpas.dirac_nicas.nc
```

No diretório `merge/`:

```text
mpas_nicas.nc
mpas_nicas_local_*.nc
mpas_nicas_grids_local_*.nc
mpas.nicas_norm.nc
mpas.dirac_nicas.nc
merge.done
```

## Como funciona internamente

A implementação está em `src/mpas_workflow/nicas_core/`:

- `model.py`: variáveis e pontos Dirac;
- `static.py`: links de suporte;
- `config_files.py`: YAML, PBS e scripts de merge;
- `prepare.py`: montagem dos diretórios por variável;
- `jobs.py`: submissão sequencial/paralela e merge;
- `checks.py`: validação dos produtos locais e globais;
- `cli.py`: CLI.

## Comandos principais

Preparar:

```bash
mpasnicas prepare \
  --config configs/jaci-x1.10242.yaml \
  --hdiag-workspace /path/to/hdiag_workspace \
  --clean
```

Submeter sequencialmente:

```bash
mpasnicas submit --workspace /path/to/nicas_workspace --wait
```

Submeter em paralelo:

```bash
mpasnicas submit --workspace /path/to/nicas_workspace --parallel --wait
```

Validar:

```bash
mpasnicas validate --workspace /path/to/nicas_workspace
```

## Opções

- `--hdiag-workspace`: workspace HDIAG validado.
- `--workspace`: workspace NICAS de destino.
- `--parallel`: submete jobs por variável em paralelo e agenda merge com dependência.
- `--retries`: número de tentativas em caso de falha PBS transitória.
- `--wait`: aguarda finalização.
- `--poll-seconds`: intervalo de consulta ao PBS.

## Validação

A validação verifica:

- produtos globais por variável;
- produtos locais por rank;
- produtos de grades NICAS por rank;
- produtos finais mesclados;
- arquivo `merge.done`.

## Problemas comuns

- Falha PBS transitória de diretório HOME no JACI.
- Produtos locais incompletos por rank.
- Falha no merge por ausência de NCO (`ncks`, `ncatted`).
- Arquivos `mpas.cor_rh.nc` ou `mpas.cor_rv.nc` ausentes.
- Incompatibilidade entre número de ranks e produtos locais esperados.
