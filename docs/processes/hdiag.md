# HDIAG

HDIAG é a etapa de diagnóstico estatístico usada para calcular os desvios-padrão e as escalas de correlação que compõem a matriz B. No workflow atual, ela roda depois do VBAL e antes do NICAS.

## 1. Introdução técnica

HDIAG calcula os campos que representam a amplitude e as escalas espaciais dos erros de background:

```text
mpas.stddev.nc  -> desvio padrão dos erros
mpas.cor_rh.nc  -> escala horizontal de correlação
mpas.cor_rv.nc  -> escala vertical de correlação
```

A etapa usa o bloco `BUMP_NICAS` em modo de calibração/diagnóstico para estimar variância, momentos, covariância/correlação e ajustes associados. Ela também lê o produto VBAL em modo leitura, aplicando `BUMP_VerticalBalance` aos PTBs originais dentro do próprio HDIAG.

No fluxo da matriz B, HDIAG é a ponte entre a calibração de balanço (`VBAL`) e a construção do operador de correlação (`NICAS`). Sem `mpas.cor_rh.nc` e `mpas.cor_rv.nc`, o NICAS não tem escalas para construir a correlação. Sem `mpas.stddev.nc`, SO e DIRAC não conseguem montar a B completa com o bloco `StdDev`.

## 2. Arquivos relacionados

| Arquivo | Função |
|---|---|
| `src/mpas_workflow/bcov.py` | Implementa `write_hdiag_yaml()`, `write_hdiag_pbs()`, `prepare_hdiag()`, `submit_hdiag()` e `validate_hdiag()`. |
| `src/mpas_workflow/hdiag_summary.py` | Utilitário diagnóstico para resumir/plotar produtos HDIAG. |
| `scripts/mpashdiag-summary` | Wrapper localizado por busca para o resumo HDIAG. |
| `configs/jaci-x1.10242.yaml` | Define malha, `nproc`, fila `bmatrix`, walltime, instalação e arquivos estáticos. |
| `docs/tutorial_bmatrix.md` | Descreve a execução de `mpasbcov hdiag-all`, os produtos esperados e diagnósticos. |
| `docs/jaci-x1.10242-bmatrix-smoke.md` | Registra o smoke validado, incluindo o fato de que 3 membros falharam e 4 membros foram usados. |
| `docs/bmatrix-smoke-vs-production.md` | Documento localizado por busca relacionado à diferença entre smoke e produção. |
| `tests/test_bcov.py`, `tests/test_pipeline_tools.py` | Testes associados ao fluxo de covariância. |

Arquivos gerados no workspace HDIAG:

| Arquivo/diretório | Função |
|---|---|
| `samples` | Link para as amostras staged no workspace VBAL. |
| `vbal` | Link para `$VBAL/VBAL`, contendo `mpas_vbal.nc`, `mpas_sampling.nc` e produtos locais. |
| `HDIAG/run_hdiag.yaml` | YAML gerado para o toolbox. |
| `HDIAG/qsub_hdiag.bash` | Script PBS gerado. |
| `HDIAG/run_hdiag.runlog` | Log principal do toolbox. |
| `HDIAG/stdout.log`, `HDIAG/stderr.log` | Saídas padrão e erro. |
| `HDIAG/mpas.stddev.nc` | Desvio padrão por variável. |
| `HDIAG/mpas.cor_rh.nc` | Escala horizontal de correlação. |
| `HDIAG/mpas.cor_rv.nc` | Escala vertical de correlação. |
| `README.md` | Metadados do workspace, incluindo VBAL de origem e número de membros. |

## 3. Configurações disponíveis

### Argumentos CLI

| Parâmetro | Onde aparece | Tipo | Valor atual/usado | Significado e impacto |
|---|---|---|---|---|
| `--config` | `hdiag-prepare`, `hdiag-all` | caminho | `configs/jaci-x1.10242.yaml` | Define caminhos, recursos e ambiente. |
| `--vbal-workspace` | `hdiag-prepare`, `hdiag-all` | caminho obrigatório | `$VBAL` | Deve apontar para VBAL validado. |
| `--workspace` | `hdiag-prepare`, `hdiag-all` | caminho opcional | Padrão: `work_root/bmatrix/covariance/hdiag/<VBAL_NAME>` | Permite separar experimentos. |
| `--clean` | `hdiag-prepare`, `hdiag-all` | flag | Usado no smoke | Remove workspace antes de preparar. |
| `--poll-seconds` | `hdiag-submit`, `hdiag-all` | inteiro | `30` | Frequência de consulta PBS. |
| `--wait` | `hdiag-submit` | flag | Usado por `hdiag-all` | Aguarda fim do job antes de validar. |

### YAML gerado por `write_hdiag_yaml()`

| Parâmetro YAML | Valor atual | Significado | Quando alterar |
|---|---|---|---|
| `state variables` | `stream_function`, `velocity_potential`, `temperature`, `spechum`, `surface_pressure` | Variáveis de controle da B. | Alterar exige consistência com BFLOW, VBAL, NICAS e testes finais. |
| `geometry.bump vunit` | `avgheight` | Unidade vertical usada pelo BUMP. | Parâmetro sensível; não há justificativa alternativa documentada. |
| `background.filename` | `./bg.nc` | Background linkado do workspace VBAL. | Não alterar manualmente. |
| `iterative ensemble loading` | `true` | Carrega ensemble iterativamente. | Afeta memória/I/O; não há opção CLI exposta. |
| `ensemble.nmembers` | número de samples em `$VBAL/samples` | Quantidade de membros. | Deve ser pelo menos 4 no fluxo atual. |
| `saber central block.name` | `BUMP_NICAS` | Bloco usado para diagnósticos BUMP. | Essencial para HDIAG. |
| `compute covariance` | `true` | Calcula covariância. | Não alterar sem validar todo o pipeline. |
| `compute correlation` | `true` | Calcula correlação. | Necessário para escalas. |
| `multivariate strategy` | `univariate` | Estratégia por variável. | Deve ser consistente com NICAS. |
| `write global sampling` | `true` | Escreve amostragem global. | Usado para diagnóstico. |
| `compute variance` | `true` | Calcula variância. | Necessário para `stddev`. |
| `compute moments` | `true` | Calcula momentos estatísticos. | Base para diagnósticos. |
| `write diagnostics` | `true` | Escreve diagnósticos. | Útil para validação. |
| `sampling.computation grid size` | `12000` | Grade de computação BUMP. | Impacta custo/memória e qualidade. |
| `sampling.diagnostic grid size` | `1000` | Grade diagnóstica. | Impacta resolução dos diagnósticos. |
| `sampling.distance classes` | `10` | Número de classes de distância. | Parâmetro estatístico sensível. |
| `sampling.distance class width` | `1000.0e3` | Largura das classes de distância em metros. | Afeta ajuste das escalas de correlação. |
| `sampling.reduced levels` | `10` | Níveis reduzidos para diagnóstico. | Não confundir com `nvertlevels=55`. |
| `sampling.local diagnostic` | `true` | Ativa diagnóstico local. | Afeta saídas/custo. |
| `sampling.averaging length-scale` | `3000.0e3` | Comprimento de suavização/averaging. | Parâmetro científico; exige validação. |
| `variance.objective filtering` | `true` | Usa filtragem objetiva. | Afeta suavização de variância. |
| `variance.filtering iterations` | `1` | Número de iterações. | Alterar pode mudar suavidade da variância. |
| `variance.initial length-scale.value` | `3000.0e3` | Escala inicial para variáveis. | Sensível ao problema/escala da malha. |
| `fit.horizontal filtering length-scale` | `3000.0e3` | Filtragem horizontal do ajuste. | Afeta escalas finais. |
| `output model files.stddev` | `./mpas.stddev.nc` | Saída de desvio padrão. | Nome esperado por NICAS/SO/DIRAC. |
| `output model files.cor_rh` | `./mpas.cor_rh.nc` | Saída de escala horizontal. | Nome esperado por NICAS. |
| `output model files.cor_rv` | `./mpas.cor_rv.nc` | Saída de escala vertical. | Nome esperado por NICAS. |
| `BUMP_VerticalBalance.read.data directory` | `../vbal` | Lê produtos VBAL. | Deve apontar para o link correto. |
| `read local sampling` | `true` | Lê amostragem local VBAL. | Necessário no fluxo atual. |
| `read vertical balance` | `true` | Lê coeficientes VBAL. | Necessário para aplicar balanço. |

### PBS gerado por `write_hdiag_pbs()`

| Parâmetro | Valor atual | Origem |
|---|---:|---|
| Nome PBS | `mpasjediBTrainingHDIAG` | Fixo no código. |
| Fila | `pesqmidi` | `pbs.queues.bmatrix`. |
| Recursos | `select=1:ncpus=128:mpiprocs=128` | `mesh.nproc=128`. |
| Walltime | `02:00:00` | `pbs.walltime.bmatrix`. |
| Executável | `install.root/bin/mpasjedi_error_covariance_toolbox.x` | `toolbox_exe(config)`. |
| Ambiente | `OMP_NUM_THREADS=1`, `GFORTRAN_CONVERT_UNIT=big_endian:101-200`, `FI_CXI_RX_MATCH_MODE=hybrid`, `ulimit -s unlimited` | Fixo no PBS gerado. |

## 4. Dependências

- Executável: `mpasjedi_error_covariance_toolbox.x`.
- Workspace anterior: VBAL completo e validado.
- Amostras: `$VBAL/samples/PTB_f48mf24_*.nc`.
- Mínimo técnico: `MIN_HDIAG_MEMBERS = 4`; o código aborta se houver menos de quatro membros.
- Produtos VBAL: `mpas_vbal.nc`, `mpas_sampling.nc`, `mpas_vbal_local_*`, `mpas_sampling_local_*`.
- Arquivos estáticos MPAS-JEDI: namelist, streams, invariant, graph, partição, geovars, keptvars e tabelas físicas.
- Recursos JACI: 128 ranks MPI no smoke validado, fila `pesqmidi`, walltime `02:00:00`.
- Dependência posterior: NICAS consome `mpas.cor_rh.nc`, `mpas.cor_rv.nc` e também linka `mpas.stddev.nc`; SO/DIRAC consomem `mpas.stddev.nc`.

## 5. Entradas e saídas

### Entradas

```text
$VBAL/samples/PTB_f48mf24_*.nc
$VBAL/VBAL/mpas_vbal.nc
$VBAL/VBAL/mpas_sampling.nc
$VBAL/VBAL/mpas_vbal_local_*
$VBAL/VBAL/mpas_sampling_local_*
$VBAL/VBAL/bg.nc
$VBAL/VBAL/namelist.atmosphere_240km
$VBAL/VBAL/streams.atmosphere_240km
```

### Saídas

```text
$HDIAG/HDIAG/run_hdiag.yaml
$HDIAG/HDIAG/qsub_hdiag.bash
$HDIAG/HDIAG/run_hdiag.runlog
$HDIAG/HDIAG/mpas.stddev.nc
$HDIAG/HDIAG/mpas.cor_rh.nc
$HDIAG/HDIAG/mpas.cor_rv.nc
```

Interpretação principal:

- `mpas.stddev.nc`: amplitude do erro de background por variável.
- `mpas.cor_rh.nc`: escala horizontal usada pelo NICAS.
- `mpas.cor_rv.nc`: escala vertical usada pelo NICAS.

## 6. Configuração usada neste workflow

Valores extraídos dos arquivos analisados:

```text
config: configs/jaci-x1.10242.yaml
mesh: x1.10242
nproc: 128
nVertLevels: 55
queue bmatrix: pesqmidi
walltime bmatrix: 02:00:00
membros smoke: 4
mínimo técnico no código: 4 membros
```

Comando validado:

```bash
export HDIAG=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/hdiag/np128_2026061000_2026061300

mpasbcov hdiag-all \
  --config configs/jaci-x1.10242.yaml \
  --vbal-workspace "$VBAL" \
  --workspace "$HDIAG" \
  --clean \
  --poll-seconds 30
```

O repositório registra que uma tentativa com 3 membros falhou porque o BUMP exigiu mais membros. A escolha de 4 membros é documentada como smoke técnico, não como produção.

## 7. Como modificar com segurança

Baixo risco:

- Alterar `--workspace`.
- Alterar `--poll-seconds`.
- Rodar `hdiag-validate` e `hdiag-plot`.

Exige cuidado:

- Alterar qualquer `sampling.*`, `variance.*` ou `fit.*`.
- Alterar `multivariate strategy`.
- Alterar nomes dos arquivos `mpas.stddev.nc`, `mpas.cor_rh.nc`, `mpas.cor_rv.nc`.
- Rodar com menos de 4 membros: o código impede essa configuração.
- Usar poucos membros para inferência científica: o repositório declara que smoke não é estatística robusta de produção.

Validações recomendadas:

```bash
mpasbcov hdiag-validate --workspace "$HDIAG"
ls -lh "$HDIAG/HDIAG/mpas.stddev.nc" "$HDIAG/HDIAG/mpas.cor_rh.nc" "$HDIAG/HDIAG/mpas.cor_rv.nc"
python -m mpas_workflow.hdiag_summary --workspace "$HDIAG" --output-dir "$HDIAG/HDIAG/figures_hdiag_summary" --level 30 --mode standard --dpi 150
```

## 8. Exemplo de uso

```bash
mpasbcov hdiag-all \
  --config configs/jaci-x1.10242.yaml \
  --vbal-workspace "$VBAL" \
  --workspace "$HDIAG" \
  --clean \
  --poll-seconds 30
```

Separando etapas:

```bash
mpasbcov hdiag-prepare --config configs/jaci-x1.10242.yaml --vbal-workspace "$VBAL" --workspace "$HDIAG" --clean
mpasbcov hdiag-submit --workspace "$HDIAG" --wait --poll-seconds 30
mpasbcov hdiag-validate --workspace "$HDIAG"
```

## 9. Problemas comuns e diagnóstico

| Sintoma | Causa provável | Diagnóstico |
|---|---|---|
| `ERRO: nenhum PTB original encontrado no workspace VBAL` | VBAL não preparou/stageou `samples`. | Verificar `$VBAL/samples/PTB_f48mf24_*.nc`. |
| `HDIAG/NICAS requer pelo menos 4 membros` | Menos de quatro amostras. | Aumentar período ou corrigir BFLOW. |
| `status final de sucesso ausente` | Toolbox falhou. | Verificar `HDIAG/run_hdiag.runlog`, `stdout.log`, `stderr.log`. |
| `produto HDIAG ausente` | Escrita de `stddev`, `cor_rh` ou `cor_rv` falhou. | Conferir mensagens `ABORT`, `Exception`, `Segmentation fault`, `CRITICAL`. |
| Mensagem `ens_ne/ens_nsub should be larger than 3` | Número insuficiente de membros por sub-ensemble. | Usar no mínimo 4 membros; para produção usar muito mais. |

## 10. Resumo operacional

- Finalidade: calcular desvio padrão e escalas de correlação da B.
- Principal arquivo: `src/mpas_workflow/bcov.py`.
- Principais parâmetros: membros, `BUMP_NICAS` calibration, `sampling.*`, `variance.*`, `fit.*`, `BUMP_VerticalBalance` em modo leitura.
- Entradas: samples do VBAL/BFLOW e produtos VBAL.
- Saídas: `mpas.stddev.nc`, `mpas.cor_rh.nc`, `mpas.cor_rv.nc`.
- Dependências críticas: no mínimo 4 membros, VBAL validado, toolbox MPAS-JEDI/SABER, MPI/PBS e ambiente JACI.
