# NICAS

NICAS é a etapa que constrói o operador de correlação/localização espacial da matriz B. No workflow MPAS-JEDI/SABER deste repositório, ela usa as escalas calculadas pelo HDIAG (`mpas.cor_rh.nc` e `mpas.cor_rv.nc`) para gerar produtos BUMP/NICAS por variável e, em seguida, mesclar esses produtos em um diretório único `merge/`.

## 1. Introdução técnica

NICAS representa a parte de correlação espacial da B. Enquanto o `StdDev` representa a amplitude dos erros e o `VBAL` representa relações balanceadas entre variáveis, o NICAS define como uma perturbação se espalha no espaço horizontal e vertical.

No workflow, NICAS aparece depois de HDIAG porque precisa das escalas de correlação calculadas anteriormente:

```text
HDIAG/mpas.cor_rh.nc  -> escala horizontal
HDIAG/mpas.cor_rv.nc  -> escala vertical
```

A etapa é executada de forma separada para cada variável de controle:

```text
stream_function
velocity_potential
temperature
spechum
surface_pressure
```

Depois, os produtos por variável são mesclados no diretório `merge/`, que passa a ser a entrada usada por `SO`, `DIRAC` e por futuras assimilações variacionais que leem a B estática.

## 2. Arquivos relacionados

| Arquivo | Função |
|---|---|
| `src/mpas_workflow/bcov.py` | Implementa `write_nicas_yaml()`, `write_nicas_pbs()`, `write_nicas_merge_files()`, `prepare_nicas()`, `submit_nicas()` e `validate_nicas()`. |
| `src/mpas_workflow/nicas_summary.py` | Utilitário diagnóstico para avaliar produtos NICAS e gerar figuras. |
| `configs/jaci-x1.10242.yaml` | Define `nproc`, `nvertlevels`, fila, walltime, loader de ambiente, instalação MPAS-JEDI e arquivos estáticos. |
| `docs/tutorial_bmatrix.md` | Descreve a execução de `mpasbcov nicas-all` e os produtos esperados. |
| `docs/jaci-x1.10242-bmatrix-smoke.md` | Registra o smoke validado e a lista de variáveis processadas pelo NICAS. |
| `docs/pipeline-and-dirac-tools.md` | Documento localizado por busca relacionado ao pipeline e ferramentas de diagnóstico. |
| `docs/bmatrix-smoke-vs-production.md` | Documento localizado por busca relacionado à distinção entre smoke e produção. |
| `tests/test_bcov.py`, `tests/test_pipeline_tools.py` | Testes do fluxo de covariância/pipeline. |

Arquivos gerados por variável:

| Arquivo/diretório | Função |
|---|---|
| `$NICAS/<variavel>/run_nicas.yaml` | YAML do toolbox para uma variável de controle. |
| `$NICAS/<variavel>/qsub_nicas.bash` | PBS gerado para aquela variável. |
| `$NICAS/<variavel>/run_nicas.runlog` | Log principal do toolbox. |
| `$NICAS/<variavel>/stdout.log`, `stderr.log` | Saída padrão e erro. |
| `$NICAS/<variavel>/mpas_nicas.nc` | Produto NICAS global da variável. |
| `$NICAS/<variavel>/mpas_nicas_local_*` | Produto NICAS local por rank MPI. |
| `$NICAS/<variavel>/mpas_nicas_grids_local_*` | Informações locais de grade NICAS por rank MPI. |
| `$NICAS/<variavel>/mpas.nicas_norm.nc` | Diagnóstico de normalização NICAS da variável. |
| `$NICAS/<variavel>/mpas.dirac_nicas.nc` | Resposta Dirac interna do NICAS puro para aquela variável. |

Arquivos gerados no merge:

| Arquivo/diretório | Função |
|---|---|
| `$NICAS/merge/merge_nicas_*.bash` | Scripts de merge por rank. |
| `$NICAS/merge/merge_nicas_global.bash` | Script de merge global. |
| `$NICAS/merge/qsub_nicas_merge.bash` | PBS do merge. |
| `$NICAS/merge/merge.done` | Marcador de conclusão do merge. |
| `$NICAS/merge/mpas_nicas.nc` | Operador NICAS global mesclado. |
| `$NICAS/merge/mpas_nicas_local_*` | Produtos locais mesclados. |
| `$NICAS/merge/mpas_nicas_grids_local_*` | Grades locais mescladas. |
| `$NICAS/merge/mpas.nicas_norm.nc` | Normalização NICAS mesclada para diagnóstico. |
| `$NICAS/merge/mpas.dirac_nicas.nc` | Dirac NICAS puro mesclado para diagnóstico. |

## 3. Configurações disponíveis

### Argumentos CLI

| Parâmetro | Onde aparece | Tipo | Valor atual/usado | Significado e impacto |
|---|---|---|---|---|
| `--config` | `nicas-prepare`, `nicas-all` | caminho | `configs/jaci-x1.10242.yaml` | Define ambiente, malha, recursos e instalação. |
| `--hdiag-workspace` | `nicas-prepare`, `nicas-all` | caminho obrigatório | `$HDIAG` | Workspace com `mpas.cor_rh.nc`, `mpas.cor_rv.nc` e `mpas.stddev.nc`. |
| `--workspace` | `nicas-prepare`, `nicas-all` | caminho opcional | Padrão: `work_root/bmatrix/covariance/nicas/<HDIAG_NAME>` | Permite separar experimentos. |
| `--clean` | `nicas-prepare`, `nicas-all` | flag | Usado no smoke | Remove workspace antes de preparar. |
| `--poll-seconds` | `nicas-submit`, `nicas-all` | inteiro | `30` | Frequência de consulta PBS. |
| `--parallel` | `nicas-submit`, `nicas-all` | flag | Não usado no comando tutorial principal | Submete variáveis em paralelo e agenda merge com dependência `afterok`. O padrão sequencial é mais robusto para retries. |
| `--retries` | `nicas-submit`, `nicas-all` | inteiro | `2` no tutorial | Número de novas tentativas para falhas PBS/HOME. |
| `--wait` | `nicas-submit` | flag | Usado por `nicas-all` | Aguarda e valida também o merge. |

### YAML gerado por `write_nicas_yaml()`

| Parâmetro YAML | Valor atual | Significado | Quando alterar |
|---|---|---|---|
| `background.state variables` | Uma variável por execução | NICAS é preparado separadamente para cada variável. | Alterar exige modificar `NICAS_VARIABLES` no código. |
| `geometry.deallocate non-da fields` | `true` | Reduz uso de memória para campos não DA. | Não há alternativa documentada no repositório. |
| `geometry.bump vunit` | `avgheight` | Unidade vertical usada pelo BUMP. | Sensível; manter consistente com HDIAG. |
| `saber central block.name` | `BUMP_NICAS` | Bloco SABER responsável pelo NICAS. | Essencial para esta etapa. |
| `multivariate strategy` | `univariate` | Estratégia por variável. | Deve ser consistente com HDIAG e merge por variável. |
| `compute nicas` | `true` | Calcula o operador NICAS. | Essencial. |
| `write local nicas` | `true` | Escreve produtos locais por rank. | Necessário para leitura eficiente posterior. |
| `write global nicas` | `true` | Escreve `mpas_nicas.nc`. | Necessário para diagnóstico e merge. |
| `write nicas grids` | `true` | Escreve grades locais NICAS. | Necessário para o conjunto final lido por SABER. |
| `internal dirac test` | `true` | Gera resposta Dirac interna do NICAS puro. | Útil para validação; não é a B completa. |
| `nicas.resolution` | `8` | Resolução interna do NICAS. | Parâmetro científico/técnico; alteração exige validação completa. |
| `nicas.max horizontal grid size` | `15000` | Tamanho máximo da grade horizontal interna. | Afeta custo, memória e representação espacial. |
| `dirac.longitude/latitude` | 12 pontos fixos em `NICAS_DIRAC_POINTS` | Pontos usados no teste Dirac interno do NICAS. | Alteração exige modificar código. |
| `dirac.level` | `1` para `surface_pressure`; para demais variáveis `nvertlevels - 20 + 1` | Nível do impulso interno NICAS. Com `nvertlevels=55`, resulta em `36` para variáveis 3D. | Alterar exige modificar código. |
| `input model files.rh` | `../mpas.cor_rh.nc` | Escala horizontal vinda do HDIAG. | Nome/caminho esperado pelo prepare. |
| `input model files.rv` | `../mpas.cor_rv.nc` | Escala vertical vinda do HDIAG. | Nome/caminho esperado pelo prepare. |
| `output model files.nicas_norm` | `./mpas.nicas_norm.nc` | Diagnóstico de normalização. | Nome esperado no merge/validação. |
| `output model files.dirac_nicas` | `./mpas.dirac_nicas.nc` | Dirac interno do NICAS. | Nome esperado no merge/validação. |

### PBS e merge

| Parâmetro | Valor atual | Origem |
|---|---:|---|
| Nome PBS por variável | `NICAS_<variavel>` | Fixo no código. |
| Nome PBS do merge | `NICASmerge` | Fixo no código. |
| Fila | `pesqmidi` | `pbs.queues.bmatrix`. |
| Recursos por variável | `select=1:ncpus=128:mpiprocs=128` | `mesh.nproc=128`. |
| Recursos merge | `select=1:ncpus=128` | `mesh.nproc=128`. |
| Walltime | `02:00:00` | `pbs.walltime.bmatrix`. |
| Executável por variável | `install.root/bin/mpasjedi_error_covariance_toolbox.x` | `toolbox_exe(config)`. |
| Merge | `ncks`, `ncatted`, `module load nco` | Script gerado por `write_nicas_merge_files()`. |
| Ambiente | `OMP_NUM_THREADS=1`, `GFORTRAN_CONVERT_UNIT=big_endian:101-200`, `FI_CXI_RX_MATCH_MODE=hybrid`, `ulimit -s unlimited` | Fixo nos PBS gerados. |

## 4. Dependências

- Executável: `mpasjedi_error_covariance_toolbox.x`.
- Workspace anterior: HDIAG validado.
- Arquivos HDIAG obrigatórios: `mpas.cor_rh.nc`, `mpas.cor_rv.nc`, `mpas.stddev.nc`.
- Arquivos estáticos: `bg.nc`, namelist, streams, graph, partição, invariant, stream lists, geovars, keptvars e tabelas físicas.
- Ferramentas de merge: NCO (`ncks`, `ncatted`).
- Ambiente JACI: `scripts/load_jaci_env.sh`, MPI, PBS, módulos NetCDF/NCO disponíveis.
- Dependências posteriores: `SO` e `DIRAC` leem `$NICAS/merge` como bloco central `BUMP_NICAS`.

## 5. Entradas e saídas

### Entradas

```text
$HDIAG/HDIAG/mpas.cor_rh.nc
$HDIAG/HDIAG/mpas.cor_rv.nc
$HDIAG/HDIAG/mpas.stddev.nc
$HDIAG/HDIAG/bg.nc
$HDIAG/HDIAG/namelist.atmosphere_240km
$HDIAG/HDIAG/streams.atmosphere_240km
arquivos estáticos MPAS/JEDI linkados do HDIAG
```

### Saídas

Por variável:

```text
$NICAS/<variavel>/mpas_nicas.nc
$NICAS/<variavel>/mpas_nicas_local_*
$NICAS/<variavel>/mpas_nicas_grids_local_*
$NICAS/<variavel>/mpas.nicas_norm.nc
$NICAS/<variavel>/mpas.dirac_nicas.nc
```

Após merge:

```text
$NICAS/merge/mpas_nicas.nc
$NICAS/merge/mpas_nicas_local_*
$NICAS/merge/mpas_nicas_grids_local_*
$NICAS/merge/mpas.nicas_norm.nc
$NICAS/merge/mpas.dirac_nicas.nc
$NICAS/merge/merge.done
```

Interpretação:

- `mpas_nicas.nc`: operador global de correlação NICAS.
- `mpas_nicas_local_*`: partes locais usadas por `read local nicas: true`.
- `mpas_nicas_grids_local_*`: grades locais necessárias para leitura/aplicação do NICAS.
- `mpas.nicas_norm.nc` e `mpas.dirac_nicas.nc`: diagnósticos úteis, mas não substituem o produto principal da B completa.

## 6. Configuração usada neste workflow

Valores extraídos dos arquivos analisados:

```text
config: configs/jaci-x1.10242.yaml
mesh: x1.10242
nproc: 128
nVertLevels: 55
queue bmatrix: pesqmidi
walltime bmatrix: 02:00:00
variáveis NICAS: stream_function, velocity_potential, temperature, spechum, surface_pressure
nicas.resolution: 8
nicas.max horizontal grid size: 15000
retries no tutorial: 2
poll-seconds no tutorial: 30
```

Comando validado:

```bash
export NICAS=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/nicas/np128_2026061000_2026061300

mpasbcov nicas-all \
  --config configs/jaci-x1.10242.yaml \
  --hdiag-workspace "$HDIAG" \
  --workspace "$NICAS" \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

A escolha dos parâmetros `resolution=8` e `max horizontal grid size=15000` está explícita no código, mas a justificativa científica detalhada para esses valores não está documentada no repositório.

## 7. Como modificar com segurança

Baixo risco:

- Alterar `--workspace`.
- Alterar `--poll-seconds`.
- Alterar `--retries` para lidar com instabilidade PBS/HOME.
- Rodar diagnósticos `nicas-validate` e `nicas-plot`.

Exige cuidado:

- Usar `--parallel`; pode acelerar, mas reduz a robustez sequencial com retry por variável.
- Alterar `nicas.resolution` ou `max horizontal grid size`; afeta custo/memória e a forma da correlação.
- Alterar lista de variáveis; exige consistência com `STATE_VARIABLES`, HDIAG, SO, DIRAC e YAMLs de assimilação.
- Alterar `multivariate strategy`; o fluxo atual é univariado por variável e faz merge posterior.
- Alterar malha ou `nproc`; requer partições e produtos locais compatíveis.

Validações recomendadas:

```bash
mpasbcov nicas-validate --workspace "$NICAS"
ls -lh "$NICAS/merge/mpas_nicas.nc"
ls "$NICAS/merge"/mpas_nicas_local_* | wc -l
ls "$NICAS/merge"/mpas_nicas_grids_local_* | wc -l
python -m mpas_workflow.nicas_summary --workspace "$NICAS" --output-dir "$NICAS/figures_nicas_summary" --variables all --level 30 --mode standard --dpi 150
```

Depois de qualquer mudança, validar também SO e DIRAC, porque eles são os principais consumidores do NICAS mesclado.

## 8. Exemplo de uso

```bash
mpasbcov nicas-all \
  --config configs/jaci-x1.10242.yaml \
  --hdiag-workspace "$HDIAG" \
  --workspace "$NICAS" \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

Separando preparo e submissão:

```bash
mpasbcov nicas-prepare --config configs/jaci-x1.10242.yaml --hdiag-workspace "$HDIAG" --workspace "$NICAS" --clean
mpasbcov nicas-submit --workspace "$NICAS" --wait --retries 2 --poll-seconds 30
mpasbcov nicas-validate --workspace "$NICAS"
```

## 9. Problemas comuns e diagnóstico

| Sintoma | Causa provável | Diagnóstico |
|---|---|---|
| `produto HDIAG ausente` | HDIAG não completou ou caminho incorreto. | Verificar `$HDIAG/HDIAG/mpas.cor_rh.nc`, `mpas.cor_rv.nc`, `mpas.stddev.nc`. |
| Falha em uma variável específica | Problema no YAML, escala de correlação, arquivo estático ou execução MPI daquela variável. | Verificar `$NICAS/<variavel>/run_nicas.runlog`, `stdout.log`, `stderr.log`. |
| `Could not chdir to home directory` | Falha intermitente PBS/HOME na JACI. | O código detecta e tenta ressubmeter; verificar arquivos `*.o*`/`*.e*`. Se produtos existem e validação passa, pode ser stale warning. |
| `ncks` ou `ncatted` ausente | Módulo NCO não carregado. | Verificar `module load nco` e `command -v ncks ncatted`. |
| `merge.done` ausente | Merge não executou ou falhou. | Verificar `$NICAS/merge/qsub_nicas_merge.bash`, `stdout.log`, `stderr.log`. |
| Número de `mpas_nicas_local_*` menor que `nproc` | Produtos locais incompletos. | Comparar com `mesh.nproc=128`; verificar ranks ausentes na validação. |
| `status final de sucesso ausente` | Toolbox não terminou com sucesso. | Procurar `ABORT`, `Exception`, `Segmentation fault`, `CRITICAL` nos logs. |

## 10. Resumo operacional

- Finalidade: construir e mesclar o operador de correlação NICAS da B.
- Principal arquivo: `src/mpas_workflow/bcov.py`.
- Principais parâmetros: variáveis NICAS, `resolution`, `max horizontal grid size`, `multivariate strategy`, produtos locais/globais, `nproc`.
- Entradas: `mpas.cor_rh.nc`, `mpas.cor_rv.nc`, `mpas.stddev.nc` e arquivos estáticos MPAS-JEDI.
- Saídas: `$NICAS/merge/mpas_nicas.nc`, produtos locais/grids locais e diagnósticos `mpas.nicas_norm.nc`, `mpas.dirac_nicas.nc`.
- Dependências críticas: HDIAG validado, NCO para merge, toolbox MPAS-JEDI/SABER, MPI/PBS e consistência entre malha, `nproc` e produtos locais.
