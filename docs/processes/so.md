# SO

SO é o teste de observação única (*Single Observation Test*) usado para validar a matriz B completa dentro de uma assimilação variacional 3D-Var do MPAS-JEDI. Ele não calibra a B; ele verifica se os produtos `NICAS`, `StdDev` e `VBAL` podem ser lidos e usados por `mpasjedi_variational.x` em uma configuração variacional simples com observações sintéticas.

## 1. Introdução técnica

No workflow, SO aparece depois de NICAS, HDIAG e VBAL. A B completa lida pelo SO é composta por:

```text
BUMP_NICAS          -> correlação/localização
StdDev              -> amplitude dos erros
BUMP_VerticalBalance -> balanço vertical/multivariado
Control2Analysis    -> mudança linear de variáveis de controle para análise
```

O SO testa essa composição dentro do ciclo variacional. O YAML gerado cria uma janela 3D-Var, um background enriquecido (`bg_so.nc`) e uma ou duas observações sintéticas, dependendo da variante:

```text
default -> temperatura + vento zonal
t-only  -> somente temperatura
u-only  -> somente vento zonal
```

Esse teste é útil para detectar problemas que não aparecem na calibração da B, como variáveis ausentes no background, aliases de GeoVaLs, problemas de `Control2Analysis`, leitura de produtos locais NICAS ou incompatibilidades no bloco `StdDev`.

## 2. Arquivos relacionados

| Arquivo | Função |
|---|---|
| `src/mpas_workflow/bcov.py` | Implementa `write_so_yaml()`, `write_so_pbs()`, `prepare_so()`, `submit_so()`, `validate_so()` e scripts de debug para `t-only`. |
| `configs/jaci-x1.10242.yaml` | Define `install.root`, `nproc`, fila, walltime, loader de ambiente, malha e arquivos estáticos. |
| `docs/tutorial_bmatrix.md` | Descreve a execução de `mpasbcov so-all`, os produtos esperados e a validação. |
| `docs/jaci-x1.10242-bmatrix-smoke.md` | Registra variantes validadas (`t-only` e `default`) e correções aplicadas ao SO. |
| `docs/pipeline-and-dirac-tools.md` | Documento localizado por busca relacionado ao pipeline e diagnósticos. |
| `tests/test_bcov.py`, `tests/test_pipeline_tools.py` | Testes associados ao fluxo de covariância/validação. |

Arquivos gerados no workspace SO:

| Arquivo | Função |
|---|---|
| `run_SO.yaml` | YAML variacional da variante `default`. |
| `run_SO_t_only.yaml` | YAML da variante `t-only`, quando solicitada. |
| `run_SO_u_only.yaml` | YAML da variante `u-only`, quando solicitada. |
| `qsub_so.bash` | PBS da variante `default`. |
| `qsub_so_t_only.bash`, `qsub_so_u_only.bash` | PBS das variantes específicas. |
| `run_SO.runlog` | Log principal da variante `default`. |
| `stdout.log`, `stderr.log` | Saídas padrão e erro da variante `default`. |
| `bg_so.nc` | Background enriquecido com variáveis e aliases necessários ao SO. |
| `obsout_SO_T.h5` | Saída IODA/HDF5 da observação sintética de temperatura. |
| `obsout_SO_U.h5` | Saída IODA/HDF5 da observação sintética de vento zonal. |
| `an.*.nc` | Arquivo de análise produzido pelo 3D-Var. |
| `qsub_so_t_only_debug.bash`, `qsub_so_t_only_gdb1.bash` | Scripts opcionais de diagnóstico quando `--debug-core` é usado com `--variant t-only`. |
| `README.md` | Metadados dos workspaces NICAS, HDIAG e VBAL usados. |

## 3. Configurações disponíveis

### Argumentos CLI

| Parâmetro | Onde aparece | Tipo | Valor atual/usado | Significado e impacto |
|---|---|---|---|---|
| `--config` | `so-prepare`, `so-all` | caminho | `configs/jaci-x1.10242.yaml` | Define instalação, ambiente e recursos. |
| `--nicas-workspace` | `so-prepare`, `so-all` | caminho obrigatório | `$NICAS` | Deve conter `merge/mpas_nicas.nc` e produtos locais. |
| `--hdiag-workspace` | `so-prepare`, `so-all` | caminho opcional | `$HDIAG`; pode ser inferido do README NICAS | Necessário para `mpas.stddev.nc` e arquivos estáticos. |
| `--vbal-workspace` | `so-prepare`, `so-all` | caminho opcional | `$VBAL`; pode ser inferido do README HDIAG | Necessário para `mpas_vbal.nc` e `mpas_sampling.nc`. |
| `--workspace` | `so-prepare`, `so-all` | caminho opcional | Padrão: `work_root/bmatrix/covariance/so/<NICAS_NAME>` | Diretório do teste SO. |
| `--clean` | `so-prepare`, `so-all` | flag | Usado no smoke | Remove workspace antes de preparar. |
| `--poll-seconds` | `so-submit`, `so-all` | inteiro | `30` | Frequência de consulta PBS. |
| `--retries` | `so-submit`, `so-all` | inteiro | `2` no tutorial | Retries para falha PBS/HOME. |
| `--variant` | `so-prepare`, `so-submit`, `so-validate`, `so-all` | enum | `default` por padrão | Valores aceitos: `default`, `t-only`, `u-only`. |
| `--debug-core` | `so-prepare`, `so-all` | flag | Não usado no fluxo principal | Restrito a `--variant t-only`; gera scripts PBS de diagnóstico/gdb. |
| `--wait` | `so-submit` | flag | Usado por `so-all` | Aguarda fim do job antes de validar. |

### YAML variacional gerado por `write_so_yaml()`

| Parâmetro YAML | Valor atual | Significado | Quando alterar |
|---|---|---|---|
| `output.filename` | `./an.$Y-$M-$D_$h.$m.$s.nc` | Arquivo de análise. | Pode ser alterado no código, mas validação espera `an.*.nc`. |
| `variational.minimizer.algorithm` | `DRPCG` | Algoritmo de minimização. | Parâmetro variacional sensível. |
| `gradient norm reduction` | `1e-3` | Critério de redução do gradiente. | Alterar muda convergência/custo. |
| `ninner` | `10` | Número de iterações internas. | Baixo número para teste; produção exigiria avaliação. |
| `diagnostics.departures` | `ombg` e `oman` | Diagnósticos antes/depois. | Manter para validação. |
| `cost type` | `3D-Var` | Tipo de assimilação. | O SO atual é 3D-Var; não há FGAT documentado para esse teste. |
| `time window.begin` | data da análise menos 3h | Início da janela. | Derivado da data HDIAG/VBAL. |
| `time window.length` | `PT6H` | Janela de 6 horas. | Alteração exige consistência com observações. |
| `jb evaluation` | `false` | Desativa avaliação explícita de Jb. | Não há justificativa alternativa documentada. |
| `analysis variables` | `spechum`, `surface_pressure`, `temperature`, `uReconstructMeridional`, `uReconstructZonal` | Variáveis de incremento/análise. | Deve ser consistente com `Control2Analysis`. |
| `background.filename` | `./bg_so.nc` | Background enriquecido criado pelo prepare. | Não alterar manualmente sem recriar aliases. |
| `background.state variables` | Inclui variáveis MPAS, aliases e diagnósticas | Garante GeoVaLs/operadores e variável de fundo. | Alterar pode quebrar `VertInterp` ou `Model2GeoVars`. |
| `BUMP_NICAS.active variables` | `stream_function`, `velocity_potential`, `temperature`, `spechum`, `surface_pressure` | Variáveis de controle da B. | Deve bater com NICAS/VBAL/HDIAG. |
| `BUMP_NICAS.read.io.data directory` | `$NICAS/merge` | Diretório de produtos NICAS mesclados. | Deve conter produtos locais e globais. |
| `read local nicas` | `true` | Lê produtos locais NICAS. | Necessário para o fluxo atual. |
| `StdDev.read.model file.filename` | `$HDIAG/HDIAG/mpas.stddev.nc` | Amplitude dos erros. | Deve existir e corresponder à mesma malha/variáveis. |
| `BUMP_VerticalBalance.read.io.data directory` | `$VBAL/VBAL` | Diretório VBAL. | Deve conter produtos globais e locais. |
| `read local sampling` | `true` | Lê amostragem local VBAL. | Necessário no fluxo atual. |
| `read vertical balance` | `true` | Lê coeficientes de balanço. | Necessário para B completa. |
| `linear variable change name` | `Control2Analysis` | Transforma controle em análise. | Essencial para aplicar B no espaço de análise. |

### Observações sintéticas

| Variante | Observação | Variável simulada | Latitude | Longitude | Coordenada vertical | Erro | Valor |
|---|---|---|---:|---:|---:|---:|---:|
| `default`, `t-only` | `SO_T` | `airTemperature` | `30.3061` | `130.085` | pressão `78775.95` Pa | `0.8` | `284.5912` |
| `default`, `u-only` | `SO_U` | `windEastward` | `57.7699` | `357.713` | pressão `77693.09` Pa | `1.0` | `0.7250047` |

Ambas usam `obsdatain.engine.type: GenList`, `obsdataout.engine.type: H5File`, operador `VertInterp`, coordenada vertical `air_pressure` e interpolação `log-linear`.

### PBS gerado por `write_so_pbs()`

| Parâmetro | Valor atual | Origem |
|---|---:|---|
| Nome PBS | `SOTest` | Fixo no código. |
| Fila | `pesqmidi` | `pbs.queues.bmatrix`. |
| Recursos | `select=1:ncpus=128:mpiprocs=128` | `mesh.nproc=128`. |
| Walltime | `02:00:00` | `pbs.walltime.bmatrix`. |
| Executável | `install.root/bin/mpasjedi_variational.x` | `variational_exe(config)`. |
| Ambiente | `OMP_NUM_THREADS=1`, `GFORTRAN_CONVERT_UNIT=big_endian:101-200`, `FI_CXI_RX_MATCH_MODE=hybrid`, `ulimit -s unlimited` | Fixo no PBS gerado. |

## 4. Dependências

- Executável: `mpasjedi_variational.x`.
- Workspaces anteriores: NICAS, HDIAG e VBAL validados.
- Produto NICAS: `$NICAS/merge/mpas_nicas.nc` e produtos locais/grids locais.
- Produto StdDev: `$HDIAG/HDIAG/mpas.stddev.nc`.
- Produtos VBAL: `$VBAL/VBAL/mpas_vbal.nc` e `$VBAL/VBAL/mpas_sampling.nc`, além de produtos locais.
- Módulo Python: `netCDF4`, usado para criar `bg_so.nc`.
- Variáveis nativas necessárias no template/background: `pressure_base`, `pressure_p`, `theta`, `qv`, `surface_pressure`, `uReconstructZonal`, `uReconstructMeridional`.
- Ambiente JACI: loader, MPI, PBS e variáveis Fortran/Libfabric.
- Dependência posterior: o SO é uma validação; ele não alimenta a geração da B, mas seus produtos são usados para diagnóstico e rastreabilidade.

## 5. Entradas e saídas

### Entradas

```text
$NICAS/merge/mpas_nicas.nc
$NICAS/merge/mpas_nicas_local_*
$NICAS/merge/mpas_nicas_grids_local_*
$HDIAG/HDIAG/mpas.stddev.nc
$VBAL/VBAL/mpas_vbal.nc
$VBAL/VBAL/mpas_sampling.nc
$HDIAG/HDIAG/templateFields.*.nc
arquivos estáticos MPAS/JEDI linkados do HDIAG
```

### Saídas

```text
$SO/bg_so.nc
$SO/run_SO.yaml
$SO/qsub_so.bash
$SO/run_SO.runlog
$SO/obsout_SO_T.h5
$SO/obsout_SO_U.h5
$SO/an.*.nc
```

Para variantes:

```text
$SO/run_SO_t_only.yaml
$SO/run_SO_u_only.yaml
$SO/run_SO_t_only.runlog
$SO/run_SO_u_only.runlog
```

Interpretação principal:

- `an.*.nc`: resposta da análise ao teste com observação sintética.
- `obsout_SO_*.h5`: saídas de observação com diagnósticos de assimilação.
- `run_SO.runlog`: deve terminar com status de sucesso do `oops::Variational<MPAS, UFO and IODA observations>`.

## 6. Configuração usada neste workflow

Valores extraídos dos arquivos analisados:

```text
config: configs/jaci-x1.10242.yaml
mesh: x1.10242
nproc: 128
queue bmatrix: pesqmidi
walltime bmatrix: 02:00:00
variant padrão: default
variantes validadas no smoke: t-only e default
minimizador: DRPCG
ninner: 10
gradient norm reduction: 1e-3
time window: PT6H
```

Comando principal:

```bash
export SO=/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global/bmatrix/covariance/so/np128_2026061000_2026061300

mpasbcov so-all \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --hdiag-workspace "$HDIAG" \
  --vbal-workspace "$VBAL" \
  --workspace "$SO" \
  --variant default \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

O repositório documenta correções aplicadas ao SO: `background.transform model to analysis: false`, criação de `bg_so.nc` enriquecido e inclusão de aliases canônicos usados por GeoVaLs/operadores. A justificativa científica para os valores específicos das observações sintéticas não está documentada no repositório.

## 7. Como modificar com segurança

Baixo risco:

- Alterar `--workspace`.
- Alterar `--poll-seconds`.
- Alterar `--retries`.
- Trocar `--variant` entre `default`, `t-only` e `u-only` para diagnóstico.

Exige cuidado:

- Alterar valores, localização ou tipo das observações sintéticas.
- Alterar `analysis variables` ou `background.state variables`.
- Alterar `Control2Analysis`, variáveis de controle ou blocos SABER.
- Alterar `ninner`, minimizador ou janela temporal.
- Remover aliases de `bg_so.nc`; isso pode quebrar `VertInterp` ou GeoVaLs.

Validações recomendadas:

```bash
mpasbcov so-validate --workspace "$SO" --variant default
ls -lh "$SO"/obsout_SO_*.h5
ls -lh "$SO"/an.*.nc
grep -Ei 'ABORT|FATAL|Segmentation fault|CRITICAL|Exception|Traceback|with status' "$SO"/run_SO.runlog "$SO"/stdout.log "$SO"/stderr.log
```

Depois de modificar produtos B anteriores, sempre reexecutar SO e DIRAC.

## 8. Exemplo de uso

```bash
mpasbcov so-all \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --hdiag-workspace "$HDIAG" \
  --vbal-workspace "$VBAL" \
  --workspace "$SO" \
  --variant default \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

Executar somente a variante de temperatura:

```bash
mpasbcov so-all \
  --config configs/jaci-x1.10242.yaml \
  --nicas-workspace "$NICAS" \
  --hdiag-workspace "$HDIAG" \
  --vbal-workspace "$VBAL" \
  --workspace "$SO" \
  --variant t-only \
  --clean \
  --retries 2 \
  --poll-seconds 30
```

## 9. Problemas comuns e diagnóstico

| Sintoma | Causa provável | Diagnóstico |
|---|---|---|
| `informe --hdiag-workspace` ou `--vbal-workspace` | README de metadados não contém caminho ou workspace foi movido. | Passar caminhos explicitamente. |
| `background SO incompleto` | `bg_so.nc` não contém aliases/variáveis esperadas. | Verificar criação em `create_so_background()` e `ncdump -h bg_so.nc`. |
| `template MPAS sem variáveis nativas` | `templateFields.*.nc` não contém `pressure_base`, `pressure_p`, `theta` ou `qv`. | Conferir template vindo do HDIAG/VBAL. |
| `obsout_SO_T.h5` ou `obsout_SO_U.h5` ausente | Variante diferente, falha variacional ou operador de observação falhou. | Verificar variante usada e logs. |
| `arquivo de análise an.*.nc ausente` | Variacional não concluiu ou falhou antes da escrita. | Verificar `run_SO.runlog`, `stdout.log`, `stderr.log`. |
| `Segmentation fault`, `FATAL`, `CRITICAL` | Falha numérica, variável ausente, incompatibilidade de B ou ambiente. | Rodar `t-only` e, se necessário, `--debug-core` com `t-only`. |
| `Could not chdir to home directory` | Falha intermitente PBS/HOME na JACI. | O submit possui retries; se os produtos e status estão OK, pode ser aviso stale. |

## 10. Resumo operacional

- Finalidade: validar a B completa dentro de um 3D-Var com observação sintética.
- Principal arquivo: `src/mpas_workflow/bcov.py`.
- Principais parâmetros: variante SO, observações sintéticas, `DRPCG`, `ninner`, janela 3D-Var, blocos SABER e `Control2Analysis`.
- Entradas: `$NICAS/merge`, `mpas.stddev.nc`, `$VBAL/VBAL`, template/background e arquivos estáticos.
- Saídas: `bg_so.nc`, `obsout_SO_T.h5`, `obsout_SO_U.h5`, `an.*.nc`, `run_SO.runlog`.
- Dependências críticas: `mpasjedi_variational.x`, produtos NICAS/HDIAG/VBAL consistentes, aliases em `bg_so.nc`, MPI/PBS e ambiente JACI.
