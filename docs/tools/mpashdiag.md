# `mpashdiag`

## Para que serve

`mpashdiag` prepara, executa e valida a etapa HDIAG do treinamento da matriz B. Ela calcula diagnósticos estatísticos a partir das amostras NMC e do balanço vertical previamente estimado.

## Papel no workflow da matriz B

HDIAG estima parâmetros usados posteriormente pelo NICAS e pelo bloco `StdDev` do SABER:

- desvio padrão dos erros;
- correlações horizontais;
- correlações verticais;
- diagnósticos de amostragem.

## Teoria usada

A partir de um ensemble de perturbações NMC, o BUMP estima estatísticas de erro. Essas estatísticas são agregadas espacial e verticalmente para construir representações compactas da variância e das correlações.

A etapa usa o bloco:

```text
BUMP_NICAS
```

em modo diagnóstico/calibração, além da leitura do bloco `BUMP_VerticalBalance` treinado no VBAL.

## Entradas

- Workspace VBAL validado.
- Amostras BFLOW linkadas pelo workspace VBAL.
- Produtos VBAL:
  - `mpas_vbal.nc`
  - `mpas_vbal_local_*.nc`
  - `mpas_sampling.nc`
- Arquivos estáticos MPAS.
- Executável `mpasjedi_error_covariance_toolbox.x`.

## Saídas

No diretório `HDIAG/`:

```text
run_hdiag.yaml
qsub_hdiag.bash
run_hdiag.runlog
mpas.stddev.nc
mpas.cor_rh.nc
mpas.cor_rv.nc
```

## Como funciona internamente

A implementação está em `src/mpas_workflow/hdiag_core/`:

- `model.py`: paths, constantes e regras de membros mínimos;
- `static.py`: links para arquivos de entrada;
- `config_files.py`: YAML e PBS;
- `prepare.py`: montagem do workspace;
- `jobs.py`: submissão PBS;
- `checks.py`: validação;
- `cli.py`: CLI.

## Comandos principais

Preparar:

```bash
mpashdiag prepare \
  --config configs/jaci-x1.10242.yaml \
  --vbal-workspace /path/to/vbal_workspace \
  --clean
```

Submeter:

```bash
mpashdiag submit --workspace /path/to/hdiag_workspace --wait
```

Validar:

```bash
mpashdiag validate --workspace /path/to/hdiag_workspace
```

## Opções

- `--vbal-workspace`: workspace VBAL validado.
- `--workspace`: workspace HDIAG de destino. Se omitido, é inferido.
- `--clean`: remove workspace anterior.
- `--wait`: aguarda job PBS.
- `--poll-seconds`: intervalo de consulta ao PBS.

## Validação

A validação confere:

- `run_hdiag.runlog`;
- status final de sucesso;
- `mpas.stddev.nc`;
- `mpas.cor_rh.nc`;
- `mpas.cor_rv.nc`.

## Problemas comuns

- Menos de 4 membros para BUMP/NICAS.
- Produtos VBAL incompletos.
- `run_hdiag.runlog` sem status final.
- `mpas.stddev.nc` ou arquivos de correlação ausentes.
- Incompatibilidade entre variáveis do YAML e arquivos BFLOW.
