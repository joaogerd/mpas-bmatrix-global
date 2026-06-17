# DIRAC

DIRAC é o teste de impulso da matriz B completa. Ele aplica uma perturbação pontual em uma variável de controle e grava a resposta espacial/vertical produzida pela composição SABER formada por `NICAS`, `StdDev`, `VBAL` e `Control2Analysis`.

## 1. Introdução técnica

O DIRAC aparece depois de NICAS, HDIAG e VBAL. Ele não calibra a B e não executa uma assimilação variacional com observações. Seu papel é diagnosticar a estrutura matemática da B completa: dado um impulso localizado, como a covariância espalha essa informação para outras regiões, níveis e variáveis?

No workflow, o DIRAC é complementar ao SO:

```text
SO     -> testa a B dentro do mpasjedi_variational.x com observação sintética
DIRAC  -> testa a resposta direta da B completa a um impulso
```

A saída principal é:

```text
mpas.dirac.nc
```

Esse arquivo pode ser resumido com `mpasbcov dirac-summary` e plotado com `mpasbcov dirac-plot`.

## 2. Arquivos relacionados

| Arquivo | Função |
|---|---|
| `src/mpas_workflow/bcov.py` | Implementa `write_dirac_yaml()`, `write_dirac_pbs()`, `prepare_dirac()`, `submit_dirac()`, `validate_dirac()`, `dirac-summary` e `dirac-plot`. |
| `src/mpas_workflow/dirac_summary.py` | Utilitário/entry point legado ou auxiliar para resumo de produto Dirac, localizado por busca. |
| `configs/jaci-x1.10242.yaml` | Define instalação, malha, `nproc`, fila, walltime, loader e arquivos estáticos. |
| `docs/tutorial_bmatrix.md` | Descreve a execução, validação, resumo e plotagem do DIRAC. |
| `docs/jaci-x1.10242-bmatrix-smoke.md` | Registra o DIRAC validado, produto esperado e impulso em `temperature`. |
| `docs/pipeline-and-dirac-tools.md` | Documento localizado por busca relacionado ao pipeline e ferramentas Dirac. |
| `tests/test_bcov.py`, `tests/test_pipeline_tools.py` | Testes associados ao fluxo de covariância/pipeline. |

Arquivos gerados no workspace DIRAC:

| Arquivo | Função |
|---|---|
| `run_dirac.yaml` | YAML do teste Dirac para `mpasjedi_error_covariance_toolbox.x`. |
| `qsub_dirac.bash` | PBS gerado para o teste. |
| `run_dirac.runlog` | Log principal do toolbox. |
| `stdout.log`, `stderr.log` | Saída padrão e erro. |
| `mpas.dirac.nc` | Resposta da B completa ao impulso. |
| `dirac_summary.csv` | CSV opcional gerado por `mpasbcov dirac-summary --csv`. |
| `figures/` | Diretório opcional gerado por `mpasbcov dirac-plot`. |
| `README.md` | Metadados dos workspaces NICAS, HDIAG e VBAL usados. |

## 3. Configurações disponíveis

### Argumentos CLI

| Parâmetro | Onde aparece | Tipo | Valor atual/usado | Significado e impacto |
|---|---|---|---|---|
| `--config` | `dirac-prepare`, `dirac-all` | caminho | `configs/jaci-x1.10242.yaml` | Define instalação, ambiente, malha e recursos. |
| `--nicas-workspace` | `dirac-prepare`, `dirac-all` | caminho obrigatório | `$NICAS` | Deve conter `merge/mpas_nicas.nc` e produtos locais. |
| `--hdiag-workspace` | `dirac-prepare`, `dirac-all` | caminho opcional | `$HDIAG`; pode ser inferido do README NICAS | Necessário para `mpas.stddev.nc` e arquivos estáticos. |
| `--vbal-workspace` | `dirac-prepare`, `dirac-all` | caminho opcional | `$VBAL`; pode ser inferido do README HDIAG | Necessário para produtos VBAL. |
| `--workspace` | `dirac-prepare`, `dirac-all` | caminho opcional | Padrão: `work_root/bmatrix/covariance/dirac/<NICAS_NAME>` | Diretório do teste Dirac. |
| `--clean` | `dirac-prepare`, `dirac-all` | flag | Usado no smoke | Remove workspace antes de preparar. |
| `--poll-seconds` | `dirac-submit`, `dirac-all` | inteiro | `30` | Frequência de consulta PBS. |
| `--retries` | `dirac-submit`, `dirac-all` | inteiro | `2` no tutorial | Retries para falha PBS/HOME. |
| `--wait` | `dirac-submit` | flag | Usado por `dirac-all` | Aguarda fim do job antes de validar. |

### Argumentos de diagnóstico

| Comando | Parâmetro | Valor padrão | Função |
|---|---|---:|---|
| `dirac-summary` | `--workspace` | obrigatório | Lê `$DIRAC/mpas.dirac.nc`. |
| `dirac-summary` | `--csv` | opcional | Escreve tabela CSV com estatísticas por variável. |
| `dirac-plot` | `--variables` | `temperature`, `surface_pressure`, `stream_function`, `velocity_potential` | Variáveis a plotar. |
| `dirac-plot` | `--level` | `30` | Nível vertical usado para variáveis 3D. |
| `dirac-plot` | `--output-dir` | opcional | Diretório de figuras. |
| `dirac-plot` | `--dpi` | `150` | Resolução das figuras. |

### YAML gerado por `write_dirac_yaml()`

| Parâmetro YAML | Valor atual | Significado | Quando alterar |
|---|---|---|---|
| `geometry.deallocate non-da fields` | `true` | Reduz campos não usados em DA. | Não há alternativa documentada. |
| `background.state variables` | `uReconstructZonal`, `uReconstructMeridional`, `temperature`, `spechum`, `surface_pressure` | Variáveis de análise/background. | Deve ser consistente com `Control2Analysis`. |
| `background.filename` | `./bg.nc` | Background linkado do HDIAG. | Não alterar manualmente. |
| `BUMP_NICAS.active variables` | `stream_function`, `velocity_potential`, `temperature`, `spechum`, `surface_pressure` | Variáveis de controle da B. | Deve bater com NICAS/VBAL/HDIAG. |
| `BUMP_NICAS.read.io.data directory` | `$NICAS/merge` | Diretório NICAS mesclado. | Deve conter produtos locais e globais. |
| `read local nicas` | `true` | Usa produtos locais NICAS. | Necessário no fluxo atual. |
| `StdDev.read.model file.filename` | `$HDIAG/HDIAG/mpas.stddev.nc` | Amplitude dos erros. | Deve ser consistente com a mesma malha/variáveis. |
| `BUMP_VerticalBalance.read.io.data directory` | `$VBAL/VBAL` | Diretório dos produtos VBAL. | Deve conter `mpas_vbal.nc` e `mpas_sampling.nc`. |
| `read local sampling` | `true` | Lê amostragem local VBAL. | Necessário no fluxo atual. |
| `read vertical balance` | `true` | Lê coeficientes VBAL. | Necessário para B completa. |
| `linear variable change name` | `Control2Analysis` | Transforma controle em análise. | Essencial para a resposta da B no espaço de análise. |
| `dirac.ndir` | `1` | Número de direções/impulsos ativos. | Fixo no código. |
| `dirac.ildir` | `10` | Índice do impulso escolhido entre as listas de pontos. | Fixo no código. |
| `dirac.dirvar` | `temperature` | Variável perturbada. | Fixo no código; alterar exige editar `bcov.py`. |
| `output dirac.filename` | `./mpas.dirac.nc` | Produto final. | Nome esperado pela validação e diagnósticos. |

### Pontos Dirac configurados no código

As listas de latitude/longitude estão fixas em `DIRAC_LATS` e `DIRAC_LONS` dentro de `src/mpas_workflow/bcov.py`:

```text
latitudes:
30.31011691, 26.56505123, 35.68501691, 19.01699038,
19.44244244, 31.21645245, -23.55867959, 40.74997906,
24.86999229, -34.60250161, 28.6699929, 55.75216412,
41.10499615, 23.72305971, 30.04996035, 37.5663491,
22.4949693, 39.92889223, -6.174417705, 33.98997825,
51.49999473, 35.67194277

longitudes:
130.11182691, -102.95294521, 139.7514074, 72.8569893,
-99.1309882, 121.4365047, -46.62501998, -73.98001693,
66.99000891, -58.39753137, 77.23000403, 37.61552283,
29.01000159, 90.40857947, 31.24996822, 126.999731,
88.32467566, 116.3882857, 106.8294376, -118.1799805,
-0.116721844, 51.42434403
```

Como `ildir` está configurado como `10`, o impulso efetivamente usado é selecionado internamente pelo toolbox a partir dessas listas. O repositório não documenta a justificativa científica para esses pontos.

### PBS gerado por `write_dirac_pbs()`

| Parâmetro | Valor atual | Origem |
|---|---:|---|
| Nome PBS | `DiracTest` | Fixo no código. |
| Fila | `pesqmidi` | `pbs.queues.bmatrix`. |
| Recursos | `select=1:ncpus=128:mpiprocs=128` | `mesh.nproc=128`. |
| Walltime | `02:00:00` | `pbs.walltime.bmatrix`. |
| Executável | `install.root/bin/mpasjedi_error_covariance_toolbox.x` | `toolbox_exe(config)`. |
| Ambiente | `OMP_NUM_THREADS=1`, `GFORTRAN_CONVERT_UNIT=big_endian:101-200`, `FI_CXI_RX_MATCH_MODE=hybrid`, `ulimit -s unlimited` | Fixo no PBS gerado. |

## 4. Dependências

- Executável: `mpasjedi_error_covariance_toolbox.x`.
- Workspaces anteriores: NICAS, HDIAG e VBAL validados.
- Produto NICAS: `$NICAS/merge/mpas_nicas.nc` e produtos locais/grids locais.
- Produto StdDev: `$HDIAG/HDIAG/mpas.stddev.nc`.
- Produtos VBAL: `$VBAL/VBAL/mpas_vbal.nc` e `$VBAL/VBAL/mpas_sampling.nc`.
- Arquivos estáticos: namelist, streams, graph, partição, invariant, stream lists, geovars, keptvars e tabelas físicas linkadas a partir do HDIAG.
- Python diagnóstico: `netCDF4` e `numpy` para `dirac-summary`; `matplotlib` pode ser necessário para geração de figuras conforme ferramentas diagnósticas do repositório.
- Ambiente JACI: loader, MPI, PBS e variáveis Fortran/Libfabric.

## 5. Entradas e saídas

### Entradas

```text
$NICAS/merge/mpas_nicas.nc
$NICAS/merge/mpas_nicas_local_*
$NICAS/merge/mpas_nicas_grids_local_*
$HDIAG/HDIAG/mpas.stddev.nc
$VBAL/VBAL/mpas_vbal.nc
$VBAL/VBAL/mpas_sampling.nc
$HDIAG/HDIAG/bg.nc
arquivos estáticos MPAS/JEDI linkados do HDIAG
```

### Saídas

```text
$DIRAC/run_dirac.yaml
$DIRAC/qsub_dirac.bash
$DIRAC/run_dirac.runlog
$DIRAC/stdout.log
$DIRAC/stderr.log
$DIRAC/mpas.dirac.nc
```

Saídas diagnósticas opcionais:

```text
$DIRAC/dirac_summary.csv
$DIRAC/figures/*.png
```

Interpretação:

- `mpas.dirac.nc` contém a resposta da B completa a um impulso em `temperature`.
- `dirac_summary.csv` resume mínimo, máximo, média, RMS, máximo absoluto e contagem de valores não nulos por variável numérica.
- Figuras permitem inspeção espacial simples da resposta em variáveis e níveis selecionados.

## 6. Configuração usada neste workflow

Valores extraídos dos arquivos analisados:

```text
config: configs/jaci-x1.10242.yaml
mesh: x1.10242
nproc: 128
queue bmatrix: pesqmidi
walltime bmatrix: 02:00:00
dirac.dirvar: temperature
dirac.ndir: 1
dirac.ildir: 10
produto: mpas.dirac.nc
plot level usado no tutorial: 30
plot dpi usado no tutorial: 150
```

Comando principal:

```bash
export DIRAC=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/dirac/np128_2026061000_2026061300

mpasbcov dirac-all \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --hdiag-workspace "$HDIAG" \
  --vbal-workspace "$VBAL" \
  --workspace "$DIRAC" \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

O smoke validado registra que o Dirac aplica impulso em `temperature` e escreve `mpas.dirac.nc`. A justificativa para `ildir=10` e para a lista de pontos não está documentada no repositório.

## 7. Como modificar com segurança

Baixo risco:

- Alterar `--workspace`.
- Alterar `--poll-seconds`.
- Alterar `--retries`.
- Alterar variáveis, nível, `output-dir` e `dpi` apenas no `dirac-plot`.
- Gerar ou não `dirac_summary.csv`.

Exige cuidado:

- Alterar `dirvar`, `ildir`, latitudes ou longitudes do impulso, pois isso exige editar o código e muda a interpretação científica do teste.
- Alterar variáveis de controle ou de análise.
- Alterar blocos SABER ou remover `Control2Analysis`.
- Alterar malha, `nproc` ou produtos B sem reexecutar NICAS/HDIAG/VBAL.

Validações recomendadas:

```bash
mpasbcov dirac-validate --workspace "$DIRAC"
mpasbcov dirac-summary --workspace "$DIRAC" --csv "$DIRAC/dirac_summary.csv"
mpasbcov dirac-plot \
  --workspace "$DIRAC" \
  --variables temperature surface_pressure stream_function velocity_potential \
  --level 30 \
  --output-dir "$DIRAC/figures" \
  --dpi 150
```

Depois de alterar a B, reexecutar também SO para validar a leitura em `mpasjedi_variational.x`.

## 8. Exemplo de uso

Execução completa:

```bash
mpasbcov dirac-all \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --hdiag-workspace "$HDIAG" \
  --vbal-workspace "$VBAL" \
  --workspace "$DIRAC" \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

Execução separada:

```bash
mpasbcov dirac-prepare \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --hdiag-workspace "$HDIAG" \
  --vbal-workspace "$VBAL" \
  --workspace "$DIRAC" \
  --clean

mpasbcov dirac-submit --workspace "$DIRAC" --wait --poll-seconds 30 --retries 2
mpasbcov dirac-validate --workspace "$DIRAC"
```

Resumo e figuras:

```bash
mpasbcov dirac-summary \
  --workspace "$DIRAC" \
  --csv "$DIRAC/dirac_summary.csv"

mpasbcov dirac-plot \
  --workspace "$DIRAC" \
  --variables stream_function velocity_potential temperature spechum surface_pressure \
  --level 30 \
  --output-dir "$DIRAC/figures" \
  --dpi 150
```

## 9. Problemas comuns e diagnóstico

| Sintoma | Causa provável | Diagnóstico |
|---|---|---|
| `informe --hdiag-workspace` ou `--vbal-workspace` | Caminhos não puderam ser inferidos dos READMEs. | Passar caminhos explicitamente. |
| `NICAS global mesclado` ausente | NICAS merge incompleto. | Verificar `$NICAS/merge/mpas_nicas.nc` e `merge.done`. |
| `StdDev HDIAG` ausente | HDIAG não completou ou workspace errado. | Verificar `$HDIAG/HDIAG/mpas.stddev.nc`. |
| `VBAL global` ou `sampling VBAL global` ausente | VBAL incompleto. | Verificar `$VBAL/VBAL/mpas_vbal.nc` e `mpas_sampling.nc`. |
| `status final de sucesso ausente no run_dirac.runlog` | Toolbox falhou ou log incompleto. | Verificar `run_dirac.runlog`, `stdout.log`, `stderr.log`. |
| `produto Dirac ausente: mpas.dirac.nc` | Execução falhou antes da escrita. | Procurar `ABORT`, `FATAL`, `Segmentation fault`, `CRITICAL`, `Exception`, `Traceback`. |
| `variável ausente` no plot | Variável não existe em `mpas.dirac.nc`. | Rodar `ncdump -h mpas.dirac.nc` ou `mpasbcov dirac-summary`. |
| `latCell/lonCell não encontrados` | Arquivos de coordenadas não estão no workspace ou links estáticos ausentes. | Verificar `x1.10242.invariant.nc`, `bg.nc` e arquivos `.nc` linkados. |
| Status final diferente de zero | Falha do toolbox ou ambiente. | Verificar todos os logs e módulos carregados. |

## 10. Resumo operacional

- Finalidade: diagnosticar a resposta da B completa a um impulso pontual.
- Principal arquivo: `src/mpas_workflow/bcov.py`.
- Principais parâmetros: `dirvar=temperature`, `ildir=10`, listas de lat/lon, blocos SABER, `StdDev`, `VBAL`, `Control2Analysis`.
- Entradas: `$NICAS/merge`, `$HDIAG/HDIAG/mpas.stddev.nc`, `$VBAL/VBAL`, background e arquivos estáticos.
- Saídas: `mpas.dirac.nc`, `run_dirac.runlog`, resumo CSV e figuras opcionais.
- Dependências críticas: toolbox MPAS-JEDI/SABER, produtos NICAS/HDIAG/VBAL consistentes, MPI/PBS e ambiente JACI.
