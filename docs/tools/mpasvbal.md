# `mpasvbal`

## Para que serve

`mpasvbal` prepara, executa e valida a etapa de balanço vertical/multivariado da matriz B usando SABER/BUMP.

A etapa VBAL estima relações estatísticas entre variáveis de controle, por exemplo relações entre `stream_function` e componentes balanceadas de outras variáveis.

## Papel no workflow da matriz B

A entrada do VBAL são as perturbações NMC geradas pelo BFLOW. A saída é usada depois por HDIAG, NICAS e SO como parte da composição da matriz B.

## Teoria usada

O balanço vertical/multivariado busca representar relações estatísticas condicionais entre variáveis. Em meteorologia, parte do erro em massa, temperatura ou divergência pode estar estatisticamente associada à componente rotacional do vento.

No YAML SABER, isso aparece como bloco:

```text
BUMP_VerticalBalance
```

Exemplos de relações treinadas:

```text
velocity_potential <- stream_function
temperature        <- stream_function
surface_pressure   <- stream_function
```

## Entradas

- Workspace BFLOW completo.
- Arquivos `PTB_f48mf24_*.nc`.
- Background representativo `FULL_f24.nc`.
- Arquivos estáticos MPAS.
- Executável `mpasjedi_error_covariance_toolbox.x`.

## Saídas

No diretório `VBAL/`:

```text
run_vbal.yaml
qsub_vbal.bash
run_vbal.runlog
mpas_sampling.nc
mpas_vbal.nc
mpas_sampling_local_*.nc
mpas_vbal_local_*.nc
```

## Como funciona internamente

A implementação está em `src/mpas_workflow/vbal_core/`:

- `model.py`: amostras, variáveis e paths;
- `static.py`: staging de amostras e arquivos estáticos;
- `config_files.py`: YAML e PBS;
- `prepare.py`: montagem do workspace;
- `jobs.py`: submissão PBS;
- `validate.py`: validação;
- `cli.py`: CLI.

## Comandos principais

Preparar:

```bash
mpasvbal prepare \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace /path/to/bflow_workspace \
  --clean
```

Submeter:

```bash
mpasvbal submit --workspace /path/to/vbal_workspace --wait
```

Validar:

```bash
mpasvbal validate --workspace /path/to/vbal_workspace
```

## Opções

- `--bflow-workspace`: workspace BFLOW de origem.
- `--workspace`: workspace VBAL de destino. Se omitido, é inferido.
- `--clean`: remove workspace anterior.
- `--wait`: aguarda o job PBS terminar.
- `--poll-seconds`: intervalo de consulta ao PBS.

## Validação

A validação confere:

- presença do `run_vbal.runlog`;
- status final de sucesso;
- existência de produtos globais;
- existência e completude dos produtos locais por rank.

## Problemas comuns

- Amostras BFLOW ausentes.
- Número de membros insuficiente.
- Arquivos `mpas_vbal_local_*` incompletos.
- Job PBS terminou sem escrever status final de sucesso.
- Caminhos de `bg.nc` ou arquivos estáticos incorretos.
