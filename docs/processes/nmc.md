# NMC

NMC é o processo que monta e valida pares de previsões MPAS com o mesmo horário válido, normalmente uma previsão antiga de 48h e uma previsão mais recente de 24h. Esses pares são a base estatística das perturbações usadas pelo BFLOW e pelas etapas de calibração da matriz B.

## 1. Introdução técnica

O método NMC aproxima erros de background por diferenças entre forecasts de diferentes alcances, mas válidos no mesmo instante:

```text
NMC difference = forecast antigo f048 - forecast novo f024
```

No repositório, o processo NMC aparece antes do BFLOW. Ele garante que os forecasts existam, monta links padronizados `f048.nc` e `f024.nc`, valida consistência estrutural e, opcionalmente, gera um arquivo direto de diferença `nmc_diff_f048_minus_f024.nc`.

O BFLOW usa a mesma ideia, mas aplica conversões adicionais específicas da B do MPAS-JEDI/SABER, incluindo `stream_function`, `velocity_potential`, `temperature` e `spechum`, gerando o produto final `PTB_f48mf24.nc`.

## 2. Arquivos relacionados

| Arquivo | Função |
|---|---|
| `src/mpas_workflow/nmc.py` | Implementa preparação, validação e diferença de pares NMC. |
| `src/mpas_workflow/cli.py` | Implementa a interface `mpaswf nmc pair`, `validate`, `diff`, `one-pair` e `range`. Também calcula os horários `old_init_time = valid - 48h` e `new_init_time = valid - 24h`. |
| `src/mpas_workflow/forecast.py` | Define os diretórios de forecast, `restart_file()` e `bflow_file()`. Garante que forecasts MPAS escrevam `restart` e `da_state/mpasout`. |
| `src/mpas_workflow/mpas_init.py` | Usado indiretamente por `mpaswf nmc` para preparar condições iniciais quando necessário. |
| `src/mpas_workflow/wps.py` | Usado indiretamente por `mpaswf nmc` para `ungrib` quando uma condição inicial ainda não está pronta. |
| `configs/jaci-x1.10242.yaml` | Define caminhos de instalação, work root, malha, `nproc`, `config_dt`, WPS e filas PBS usadas na geração dos forecasts. |
| `scripts/22_prepare_mpas_forecast_f024_f048.sh` | Script legado/auxiliar para preparar forecasts f024/f048. |
| `scripts/23_prepare_nmc_pair_from_forecasts.sh` | Script legado/auxiliar para preparar par NMC a partir de forecasts. |
| `scripts/24_run_one_nmc_pair_workflow.sh` | Script legado/auxiliar para rodar um par NMC. |
| `scripts/legacy/22_prepare_mpas_forecast_f024_f048.sh` | Versão legada do preparo de forecasts. |
| `scripts/legacy/23_prepare_nmc_pair_from_forecasts.sh` | Versão legada do preparo de par NMC. |
| `scripts/legacy/24_run_one_nmc_pair_workflow.sh` | Versão legada da execução de um par NMC. |
| `docs/tutorial_bmatrix.md` | Explica a geração de amostras NMC e sua relação com BFLOW. |
| `docs/jaci-x1.10242-bmatrix-smoke.md` | Registra o smoke validado com período `2026-06-10` a `2026-06-13`. |
| `pyproject.toml` | Registra o entry point `mpaswf = mpas_workflow.cli:main`. |

Arquivos gerados no workspace de um par NMC:

| Arquivo | Função |
|---|---|
| `f048.nc` | Link para forecast antigo de 48h. |
| `f024.nc` | Link para forecast novo de 24h. |
| `pair.env` | Metadados do par: malha, `dt`, horários inicial/validade e caminhos. |
| `README.md` | Descrição resumida do par. |
| `nmc_diff_f048_minus_f024.nc` | Produto opcional gerado por `mpaswf nmc diff`. Não substitui automaticamente o `PTB_f48mf24.nc` do BFLOW. |

## 3. Configurações disponíveis

### Argumentos do `mpaswf nmc pair`

| Parâmetro | Tipo | Significado | Valor atual/usado | Impacto e cuidado |
|---|---|---|---|---|
| `--old-init-time` | data `YYYY-MM-DD_HH:MM:SS` | Data inicial do forecast antigo de 48h. | Calculado automaticamente no `range`; exemplo: `valid_time - 48h`. | Deve produzir forecast válido no mesmo horário de `f024`. |
| `--new-init-time` | data | Data inicial do forecast novo de 24h. | Calculado automaticamente no `range`; exemplo: `valid_time - 24h`. | Deve produzir forecast válido no mesmo horário de `f048`. |
| `--valid-time` | data | Horário válido comum do par. | No smoke: `2026-06-10_00:00:00` até `2026-06-13_00:00:00`. | Define diretório `nmc_pairs/nmc_<mesh>_valid_<valid>`. |
| `--dt` | inteiro, segundos | Passo de tempo do forecast usado para localizar diretórios. | `60`, via `runtime.config_dt`. | Deve ser igual ao usado na execução MPAS. |

### Argumentos do `mpaswf nmc one-pair`

| Parâmetro | Tipo | Significado | Valor atual/usado | Impacto e cuidado |
|---|---|---|---|---|
| `--submit` | flag | Submete init/forecast quando necessário. | Usado no tutorial para geração automática. | Sem `--wait`, o fluxo para após submissão se os jobs ainda não terminaram. |
| `--wait` | flag | Aguarda jobs PBS terminarem e continua. | Usado no tutorial/smoke. | Útil para fluxo automático; pode demorar conforme fila. |
| `--poll-seconds` | inteiro | Intervalo de consulta ao PBS. | `30` no tutorial/smoke. | Baixo risco; apenas afeta frequência de checagem. |
| `--diff` | flag | Gera `nmc_diff_f048_minus_f024.nc`. | Usado no comando `nmc range` do tutorial. | Produto diagnóstico; o BFLOW gera seu próprio `PTB_f48mf24.nc`. |
| `--variables` | string CSV | Lista de variáveis para a diferença direta. | Não especificado no smoke; usa padrão. | Se pedir variáveis ausentes, elas são ignoradas; se nenhuma estiver disponível, falha. |
| `--force-forecasts` | flag | Refaz forecasts mesmo se restart existir. | Não documentado como usado no smoke. | Alto custo; pode sobrescrever resultados de forecast. |

### Argumentos do `mpaswf nmc range`

| Parâmetro | Tipo | Significado | Valor atual/usado | Impacto e cuidado |
|---|---|---|---|---|
| `--start-valid-time` | data | Primeiro horário válido da sequência. | `2026-06-10_00:00:00`. | Define início das amostras. |
| `--end-valid-time` | data | Último horário válido da sequência, inclusive. | `2026-06-13_00:00:00`. | Define fim das amostras. |
| `--valid-interval-hours` | inteiro positivo | Passo entre horários válidos. | `24`. | O código aborta se for `<= 0`. |
| `--dt` | inteiro, segundos | Passo de tempo MPAS. | `60`. | Precisa ser consistente com forecasts. |
| `--submit`, `--wait`, `--poll-seconds`, `--diff`, `--variables`, `--force-forecasts` | vários | Mesma função de `one-pair`, aplicada a todos os horários válidos. | No tutorial: `--submit --wait --poll-seconds 30 --diff`. | Pode submeter muitos jobs. Usar com cuidado em produção. |

### Variáveis padrão da diferença direta NMC

Em `src/mpas_workflow/nmc.py`, `DEFAULT_DIFF_VARIABLES` contém:

```text
u, w, rho, theta, qv, qc, qr, qi, qs, qg, pressure_p, surface_pressure
```

O código também lista variáveis derivadas/aliases opcionais que não são esperadas nos restart/diff atuais:

```text
pressure, temperature, air_temperature,
water_vapor_mixing_ratio_wrt_moist_air,
water_vapor_mixing_ratio_wrt_dry_air
```

Essas aliases não são incluídas por padrão porque o comentário do código registra que elas não estão presentes nos arquivos MPAS restart/diff usados neste workflow.

## 4. Dependências

- Executáveis: `mpaswf`, `mpas_init_atmosphere`, `mpas_atmosphere`, `qsub`, `ncdump`.
- Python: `netCDF4` para `nmc diff`, `PyYAML` para leitura de configuração.
- WPS: `ungrib.exe`, `link_grib.csh`, `Vtable.GFS` quando as condições iniciais ainda precisam ser preparadas a partir de GFS.
- Entradas: arquivos GRIB/GFS para init quando necessário, condições iniciais MPAS, forecasts MPAS f024/f048, malha e partição.
- Variáveis de ambiente: carregadas por `scripts/load_jaci_env.sh` durante init/forecast/PBS; o NMC Python em si depende do ambiente Python e dos comandos NetCDF.
- Recursos computacionais: geração de forecasts usa PBS. No YAML atual, forecast usa fila `pesqmidi`, `nproc=128`, walltime `f024=01:00:00` e `f048=02:00:00`.
- Dependências entre processos: NMC depende de WPS/init/forecast e alimenta BFLOW.

## 5. Entradas e saídas

### Entradas

```text
runs/forecast_<mesh>_<old_init>_f048_dt<dt>_np<nproc>/restart.<valid>.nc
runs/forecast_<mesh>_<new_init>_f024_dt<dt>_np<nproc>/restart.<valid>.nc
```

Para BFLOW, o arquivo usado é o `mpasout.<valid>.nc` do stream `da_state`, definido por `forecast.bflow_file()`.

### Saídas

```text
work_root/nmc_pairs/nmc_x1.10242_valid_YYYY-MM-DD_HH.MM.SS/f048.nc
work_root/nmc_pairs/nmc_x1.10242_valid_YYYY-MM-DD_HH.MM.SS/f024.nc
work_root/nmc_pairs/nmc_x1.10242_valid_YYYY-MM-DD_HH.MM.SS/pair.env
work_root/nmc_pairs/nmc_x1.10242_valid_YYYY-MM-DD_HH.MM.SS/nmc_diff_f048_minus_f024.nc  # opcional
```

A saída mais importante para o caminho BFLOW é a existência dos forecasts `mpasout`/`da_state` correspondentes, pois `mpasbflow` monta seus pares a partir deles.

## 6. Configuração usada neste workflow

Extraído de `configs/jaci-x1.10242.yaml` e dos comandos validados:

```text
project.work_root: /p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global
mesh.name: x1.10242
mesh.nproc: 128
mesh.nvertlevels: 55
runtime.config_dt: 60
runtime.output_interval: 24:00:00
forecast queue: pesqmidi
forecast walltime f024: 01:00:00
forecast walltime f048: 02:00:00
```

Comando usado no tutorial para gerar a faixa NMC:

```bash
mpaswf \
  --config configs/jaci-x1.10242.yaml \
  nmc range \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time   2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --submit \
  --wait \
  --poll-seconds 30 \
  --diff
```

A razão científica exata para escolher o período `2026-06-10` a `2026-06-13` não está documentada como escolha estatística de produção. O repositório registra esse período como smoke test validado.

## 7. Como modificar com segurança

Baixo risco:

- Alterar `--poll-seconds`.
- Rodar `nmc validate` para conferir pares existentes.
- Usar `--variables` para diagnóstico direto, sem alterar o fluxo BFLOW, desde que se saiba que as variáveis existem nos arquivos.

Exige cuidado:

- Alterar `--dt`; afeta o nome dos diretórios de forecast esperados.
- Usar `--force-forecasts`; pode refazer jobs caros e sobrescrever forecasts.
- Alterar período/intervalo; muda o número de amostras e pode deixar HDIAG/NICAS com membros insuficientes.
- Trocar malha ou `nproc`; exige partições e arquivos estáticos compatíveis.

Validações recomendadas:

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc validate --valid-time YYYY-MM-DD_HH:MM:SS
ncdump -h f048.nc | head
ncdump -h f024.nc | head
```

Para seguir ao BFLOW:

```bash
mpasbflow all --config configs/jaci-x1.10242.yaml --start-valid-time ... --end-valid-time ... --dt 60
```

## 8. Exemplo de uso

Um par isolado:

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc one-pair \
  --old-init-time 2026-06-08_00:00:00 \
  --new-init-time 2026-06-09_00:00:00 \
  --valid-time    2026-06-10_00:00:00 \
  --dt 60 \
  --submit \
  --wait \
  --poll-seconds 30 \
  --diff
```

Uma sequência:

```bash
mpaswf --config configs/jaci-x1.10242.yaml nmc range \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --submit \
  --wait \
  --poll-seconds 30 \
  --diff
```

## 9. Problemas comuns e diagnóstico

| Sintoma | Causa provável | Diagnóstico |
|---|---|---|
| `forecast antigo f048` ou `forecast novo f024` ausente | Forecast ainda não terminou, `dt` incorreto ou diretório esperado mudou. | Verificar `runs/forecast_*` e os arquivos `restart.*.nc`/`mpasout.*.nc`. |
| `ncdump não encontrado` | Ambiente NetCDF não carregado. | Carregar `scripts/load_jaci_env.sh` ou módulo NetCDF. |
| Dimensões incompatíveis | Forecasts gerados com malha, partição ou configuração diferente. | Comparar `nCells`, `nEdges`, `nVertices`, `nVertLevels`. |
| Variável obrigatória ausente (`u`, `rho`, `theta`, `qv`) | Arquivo não é um restart/da_state esperado ou stream incompleto. | Verificar `ncdump -h` e stream `da_state`. |
| `Par ainda não concluído` no `range` | Job foi submetido sem `--wait` ou ainda está em fila. | Usar `qstat`/logs PBS e repetir com `--wait` quando apropriado. |

## 10. Resumo operacional

- Finalidade: montar pares `f048/f024` válidos no mesmo horário para o método NMC.
- Principal código: `src/mpas_workflow/nmc.py` e `src/mpas_workflow/cli.py`.
- Principais parâmetros: `valid_time`, `old_init_time`, `new_init_time`, `dt`, `submit`, `wait`, `variables`.
- Entradas: forecasts MPAS f024/f048 e, indiretamente, WPS/init.
- Saídas: `f048.nc`, `f024.nc`, `pair.env`, opcionalmente `nmc_diff_f048_minus_f024.nc`.
- Dependências críticas: forecasts consistentes na mesma malha, NetCDF/NCO, ambiente JACI e configuração `configs/jaci-x1.10242.yaml`.
