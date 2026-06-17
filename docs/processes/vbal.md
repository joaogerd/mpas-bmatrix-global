# VBAL

VBAL é a etapa de calibração do balanço vertical e multivariado da matriz B. No workflow, ela usa as amostras NMC/BFLOW para estimar relações estatísticas entre variáveis de controle, principalmente a resposta balanceada de `velocity_potential`, `temperature` e `surface_pressure` a perturbações em `stream_function`.

## 1. Introdução técnica

VBAL significa *Vertical Balance*. No SABER, esta etapa é implementada com o bloco `BUMP_VerticalBalance` em modo de calibração.

O objetivo é estimar coeficientes de balanço vertical/multivariado a partir das amostras `PTB_f48mf24.nc`. Conceitualmente, a etapa responde a perguntas como:

```text
Se existe erro em stream_function,
qual parcela desse erro aparece de forma balanceada em velocity_potential,
temperature e surface_pressure?
```

VBAL aparece depois de BFLOW/NMC e antes de HDIAG. O HDIAG lê os PTBs originais e aplica o `BUMP_VerticalBalance` em modo leitura, por isso a qualidade e completude do `mpas_vbal.nc` e dos produtos locais é crítica.

## 2. Arquivos relacionados

| Arquivo | Função |
|---|---|
| `src/mpas_workflow/bcov.py` | Implementa `write_vbal_yaml()`, `write_vbal_pbs()`, `prepare_vbal()`, `submit_vbal()` e `validate_vbal()`. |
| `src/mpas_workflow/bflow.py` | Gera o workspace e os `PTB_f48mf24.nc` usados como ensemble de entrada. |
| `configs/jaci-x1.10242.yaml` | Fornece `nproc`, fila PBS, walltime, loader de ambiente, instalação MPAS-JEDI e arquivos estáticos. |
| `pyproject.toml` | Registra `mpasbcov = mpas_workflow.bcov:main`. |
| `src/mpas_workflow/vbal_groups.py` | Utilitário diagnóstico para inspecionar grupos NetCDF-4 do produto VBAL. |
| `scripts/mpasvbal-groups` | Wrapper/atalho associado ao diagnóstico de grupos VBAL. |
| `docs/vbal-empty-product-note.md` | Nota localizada por busca sobre interpretação de produto VBAL aparentemente vazio. |
| `docs/tutorial_bmatrix.md` | Descreve a execução de `mpasbcov vbal-all` e os produtos esperados. |
| `docs/jaci-x1.10242-bmatrix-smoke.md` | Registra validação do smoke: 4 membros, produtos globais e 128 produtos locais. |
| `tests/test_bcov.py`, `tests/test_pipeline_tools.py` | Testes associados ao fluxo de covariância/pipeline. |

Arquivos gerados no workspace VBAL:

| Arquivo/diretório | Função |
|---|---|
| `samples/PTB_f48mf24_001.nc`, `..._002.nc`, etc. | Cópias CDF5 dos `PTB_f48mf24.nc` do BFLOW, com numeração de membro. |
| `VBAL/run_vbal.yaml` | YAML gerado para o `mpasjedi_error_covariance_toolbox.x`. |
| `VBAL/qsub_vbal.bash` | Script PBS gerado. |
| `VBAL/run_vbal.runlog` | Log principal do toolbox. |
| `VBAL/stdout.log`, `VBAL/stderr.log` | Saída padrão e erro do PBS/toolbox. |
| `VBAL/mpas_sampling.nc` | Amostragem global/grade diagnóstica usada pelo BUMP/VBAL. |
| `VBAL/mpas_vbal.nc` | Produto global de coeficientes de balanço vertical. |
| `VBAL/mpas_sampling_local_*` | Produtos locais por rank MPI. |
| `VBAL/mpas_vbal_local_*` | Produtos locais de balanço por rank MPI. |
| `README.md` | Metadados do workspace, incluindo BFLOW de origem e número de membros. |

## 3. Configurações disponíveis

### Argumentos CLI

| Parâmetro | Onde aparece | Tipo | Valor atual/usado | Significado e impacto |
|---|---|---|---|---|
| `--config` | `mpasbcov vbal-prepare`, `vbal-all` | caminho | `configs/jaci-x1.10242.yaml` | Define ambiente, malha, `nproc`, instalação, fila e walltime. |
| `--bflow-workspace` | `vbal-prepare`, `vbal-all` | caminho obrigatório | `$BFLOW` | Workspace contendo `manifest.tsv` e `output/YYYYMMDDHH/PTB_f48mf24.nc`. |
| `--workspace` | `vbal-prepare`, `vbal-all` | caminho opcional | Padrão: `work_root/bmatrix/covariance/vbal/<BFLOW_NAME>` | Permite separar experimentos ou usar nome customizado. |
| `--clean` | `vbal-prepare`, `vbal-all` | flag | Usado no smoke | Remove workspace antes de preparar. Apaga produtos anteriores. |
| `--poll-seconds` | `vbal-submit`, `vbal-all` | inteiro | `30` | Frequência de consulta PBS ao usar `--wait` internamente no `all`. |
| `--wait` | `vbal-submit` | flag | Usado indiretamente por `vbal-all` | Aguarda o job terminar antes de validar. |

### YAML gerado por `write_vbal_yaml()`

| Parâmetro YAML | Valor atual | Significado | Quando alterar |
|---|---|---|---|
| `state variables` | `stream_function`, `velocity_potential`, `temperature`, `spechum`, `surface_pressure` | Variáveis de controle usadas na calibração. | Alterar exige consistência com BFLOW, HDIAG, NICAS, SO, DIRAC e `stream_list.atmosphere.control`. |
| `date` | Data do primeiro membro, convertida para ISO UTC | Data associada ao background e aos membros. | Normalmente não alterar manualmente; deriva do BFLOW. |
| `background.filename` | `./bg.nc` | Link para o `FULL_f24.nc` do primeiro membro usado como background. | Não alterar sem controlar `link_static_files()`. |
| `ensemble.members from template.filename` | `../samples/PTB_f48mf24_%mem%.nc` | Template dos membros. | Não alterar sem mudar o staging dos samples. |
| `ensemble.nmembers` | número de amostras BFLOW | Quantidade de membros do ensemble. | Produção deve aumentar membros; valor deriva do manifesto. |
| `zero padding` | `3` | Formato `%mem%` como `001`, `002`, ... | Alterar exige renomear samples. |
| `saber central block.name` | `ID` | Bloco central neutro durante calibração VBAL. | Não documentado no repositório como parâmetro de usuário. |
| `saber outer block.name` | `BUMP_VerticalBalance` | Bloco SABER calibrado. | Não alterar para VBAL. |
| `files prefix` | `mpas` | Prefixo dos arquivos de saída VBAL. | Alterar muda nomes esperados pela validação e etapas posteriores. |
| `write local sampling` | `true` | Escreve amostragem local por rank. | Necessário para leitura posterior. |
| `write global sampling` | `true` | Escreve `mpas_sampling.nc`. | Necessário para diagnóstico/validação. |
| `compute vertical covariance` | `true` | Calcula covariância vertical. | Não alterar sem entender o algoritmo SABER/BUMP. |
| `compute vertical balance` | `true` | Calcula coeficientes de balanço. | Essencial para a etapa. |
| `write vertical balance` | `true` | Escreve `mpas_vbal.nc` e locais. | Essencial para HDIAG/SO/DIRAC. |
| `sampling.computation grid size` | `12000` | Tamanho da grade de computação BUMP. | Requer avaliação de custo/memória/qualidade. |
| `sampling.diagnostic grid size` | `200` | Grade diagnóstica. | Pode afetar diagnósticos; não é parâmetro CLI. |
| `sampling.reduced levels` | `55` | Níveis reduzidos usados no BUMP. | Deve ser compatível com `mesh.nvertlevels=55`. |
| `sampling.averaging latitude width` | `10.0` | Largura latitudinal de média. | Parâmetro científico; alteração exige validação estatística. |
| `vertical balance.vbal` | `velocity_potential <- stream_function`, `temperature <- stream_function`, `surface_pressure <- stream_function` | Relações balanceadas calibradas. | Alterar muda a estrutura multivariada da B. |
| `diagonal regression` | `true` somente para `velocity_potential` | Usa regressão diagonal nessa relação. | Não há justificativa adicional documentada no repositório. |
| `pseudo inverse` | `true` | Usa pseudo-inversa na calibração. | Alteração pode afetar estabilidade numérica. |
| `dominant mode` | `20` | Modo dominante usado na calibração. | Parâmetro científico; não alterar sem teste. |

### PBS gerado por `write_vbal_pbs()`

| Parâmetro | Valor atual | Origem |
|---|---:|---|
| Nome PBS | `mpasjediBTrainingVBAL` | Fixo no código. |
| Fila | `pesqmidi` | `pbs.queues.bmatrix` em `configs/jaci-x1.10242.yaml`. |
| Recursos | `select=1:ncpus=128:mpiprocs=128` | `mesh.nproc=128`. |
| Walltime | `02:00:00` | `pbs.walltime.bmatrix`. |
| Executável | `install.root/bin/mpasjedi_error_covariance_toolbox.x` | `toolbox_exe(config)`. |
| Ambiente | `OMP_NUM_THREADS=1`, `GFORTRAN_CONVERT_UNIT=big_endian:101-200`, `FI_CXI_RX_MATCH_MODE=hybrid`, `ulimit -s unlimited` | Fixo no PBS gerado. |

## 4. Dependências

- Executável: `mpasjedi_error_covariance_toolbox.x`.
- Entradas BFLOW: `manifest.tsv`, `output/YYYYMMDDHH/PTB_f48mf24.nc`, `FULL_f24.nc` do primeiro membro.
- Arquivos estáticos: `namelist.atmosphere_240km`, `streams.atmosphere_240km`, `stream_list.atmosphere.*`, `geovars.yaml`, `keptvars.yaml`, `x1.10242.invariant.nc`, grafo e partição.
- Ferramentas: `nccopy` para converter samples para CDF5.
- Ambiente JACI: `scripts/load_jaci_env.sh`, MPI via `mpiexec`, variáveis PBS/Fortran/Libfabric.
- Saída consumida por processos posteriores: `mpas_vbal.nc`, `mpas_sampling.nc`, `mpas_vbal_local_*`, `mpas_sampling_local_*`.

## 5. Entradas e saídas

### Entradas

```text
$BFLOW/manifest.tsv
$BFLOW/output/YYYYMMDDHH/PTB_f48mf24.nc
$BFLOW/output/YYYYMMDDHH/FULL_f24.nc
arquivos estáticos MPAS/JEDI definidos em configs/jaci-x1.10242.yaml
```

### Saídas

```text
$VBAL/samples/PTB_f48mf24_001.nc
$VBAL/VBAL/run_vbal.yaml
$VBAL/VBAL/qsub_vbal.bash
$VBAL/VBAL/run_vbal.runlog
$VBAL/VBAL/mpas_sampling.nc
$VBAL/VBAL/mpas_vbal.nc
$VBAL/VBAL/mpas_sampling_local_*
$VBAL/VBAL/mpas_vbal_local_*
```

`mpas_vbal.nc` pode usar grupos NetCDF-4. Portanto, ferramentas que leem apenas o nível raiz podem dar a impressão de arquivo vazio. O repositório possui diagnóstico específico (`vbal_groups.py`) para inspecionar variáveis como `reg_c2`, `cov_c2` e `explained_var_c2`.

## 6. Configuração usada neste workflow

Valores explicitamente encontrados:

```text
config: configs/jaci-x1.10242.yaml
mesh: x1.10242
nproc: 128
nVertLevels: 55
queue bmatrix: pesqmidi
walltime bmatrix: 02:00:00
members no smoke: 4
```

Comando validado:

```bash
export VBAL=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/vbal/np128_2026061000_2026061300

mpasbcov vbal-all \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --workspace "$VBAL" \
  --clean \
  --poll-seconds 30
```

A escolha de quatro membros é documentada como smoke técnico, não como configuração estatística de produção.

## 7. Como modificar com segurança

Baixo risco:

- Alterar `--workspace`.
- Alterar `--poll-seconds`.
- Rodar `vbal-validate` e diagnósticos sem modificar produtos.

Exige cuidado:

- Alterar variáveis de controle ou relações `vbal`.
- Alterar `dominant mode`, `pseudo inverse`, `sampling.*`.
- Alterar `files prefix`, pois etapas posteriores esperam prefixo `mpas`.
- Reduzir número de membros. HDIAG/NICAS exigem pelo menos 4 membros no fluxo atual.

Validações recomendadas:

```bash
mpasbcov vbal-validate --workspace "$VBAL"
python -m mpas_workflow.vbal_groups --workspace "$VBAL" --output-dir "$VBAL/VBAL/figures_vbal_groups" --mode quick --dpi 150
ls -lh "$VBAL/VBAL/mpas_vbal.nc" "$VBAL/VBAL/mpas_sampling.nc"
ls "$VBAL/VBAL"/mpas_vbal_local_* | wc -l
```

## 8. Exemplo de uso

```bash
mpasbcov vbal-all \
  --config configs/jaci-x1.10242.yaml \
  --bflow-workspace "$BFLOW" \
  --workspace "$VBAL" \
  --clean \
  --poll-seconds 30
```

Separando preparo e submissão:

```bash
mpasbcov vbal-prepare --config configs/jaci-x1.10242.yaml --bflow-workspace "$BFLOW" --workspace "$VBAL" --clean
mpasbcov vbal-submit --workspace "$VBAL" --wait --poll-seconds 30
mpasbcov vbal-validate --workspace "$VBAL"
```

## 9. Problemas comuns e diagnóstico

| Sintoma | Causa provável | Diagnóstico |
|---|---|---|
| `Bflow manifest.tsv` ausente | `--bflow-workspace` incorreto ou BFLOW não executado. | Verificar `cat $BFLOW/manifest.tsv`. |
| `PTB para <data>` ausente | BFLOW incompleto. | Verificar `find $BFLOW/output -name PTB_f48mf24.nc`. |
| `status final de sucesso ausente` | Toolbox falhou ou log incompleto. | Verificar `VBAL/run_vbal.runlog`, `stdout.log`, `stderr.log`. |
| `mpas_vbal.nc` ausente | Falha na calibração ou escrita. | Verificar mensagens `ABORT`, `Exception`, `Segmentation fault`, `CRITICAL`. |
| Nenhum `mpas_vbal_local_*` | Escrita local falhou ou `write local sampling`/MPI inconsistente. | Comparar número de arquivos locais com `nproc=128`. |
| Produto parece vazio | Arquivo usa grupos NetCDF-4. | Usar `python -m mpas_workflow.vbal_groups` ou ferramenta NetCDF com suporte a grupos. |

## 10. Resumo operacional

- Finalidade: calibrar balanço vertical e multivariado da B.
- Principal arquivo: `src/mpas_workflow/bcov.py`.
- Principais parâmetros: membros, variáveis de controle, relações `vbal`, `sampling.*`, `dominant mode`, `pseudo inverse`, `nproc`.
- Entradas: amostras BFLOW/NMC e arquivos estáticos MPAS-JEDI.
- Saídas: `mpas_vbal.nc`, `mpas_sampling.nc`, produtos locais VBAL.
- Dependências críticas: `mpasjedi_error_covariance_toolbox.x`, BFLOW completo, `nccopy`, MPI/PBS e ambiente JACI.
