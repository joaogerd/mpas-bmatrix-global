# BFLOW

BFLOW é o processo de pré-processamento que organiza pares NMC e gera as amostras estatísticas `PTB_f48mf24.nc` usadas nas etapas de calibração da matriz B do MPAS-JEDI/SABER.

## 1. Introdução técnica

No workflow deste repositório, BFLOW representa a preparação dos arquivos de perturbação do background. A perturbação é construída como:

```text
PTB = previsão de 48h - previsão de 24h
```

As duas previsões precisam ter o mesmo horário válido. O BFLOW não roda a assimilação variacional; ele produz o ensemble/amostra de perturbações que será lido por `VBAL`, `HDIAG` e, indiretamente, por `NICAS`.

A etapa aparece depois da geração das previsões MPAS/NMC e antes da calibração da B. Sem os `PTB_f48mf24.nc`, o workflow não tem amostras para estimar covariância vertical, balanço, desvio padrão ou escalas de correlação.

## 2. Arquivos relacionados

| Arquivo | Função |
|---|---|
| `src/mpas_workflow/bflow.py` | Implementa o comando `mpasbflow`, a criação do workspace BFLOW, o manifesto, os links de entrada e os scripts gerados para pesos ESMF, conversão `u/v -> psi/chi`, adição de variáveis, diferença NMC e validação. |
| `src/mpas_workflow/forecast.py` | Define `bflow_file()`, que aponta para o arquivo `mpasout.YYYY-MM-DD_HH.MM.SS.nc` produzido pelo stream `da_state` do MPAS-JEDI. Também configura o forecast para escrever o stream `da_state`. |
| `src/mpas_workflow/cli.py` | Aciona a geração NMC via `mpaswf nmc range` ou `mpaswf nmc one-pair`, que produz as previsões usadas depois pelo BFLOW. |
| `src/mpas_workflow/bcov.py` | Lê o `manifest.tsv` do BFLOW por meio de `read_bflow_samples()` e copia os `PTB_f48mf24.nc` para `samples/PTB_f48mf24_###.nc` na etapa VBAL. |
| `configs/jaci-x1.10242.yaml` | Define `project.work_root`, malha, `nproc`, `nvertlevels`, caminhos de instalação, arquivos estáticos, fila PBS e `runtime.config_dt`. |
| `pyproject.toml` | Registra o entry point `mpasbflow = mpas_workflow.bflow:main`. |
| `docs/tutorial_bmatrix.md` | Tutorial operacional que descreve BFLOW e sua relação com NMC, VBAL, HDIAG e NICAS. |
| `docs/jaci-x1.10242-bmatrix-smoke.md` | Registra o smoke test validado e o comando `mpasbflow all` usado. |
| `scripts/22_prepare_mpas_forecast_f024_f048.sh`, `scripts/23_prepare_nmc_pair_from_forecasts.sh`, `scripts/24_run_one_nmc_pair_workflow.sh` | Scripts legados/auxiliares encontrados no repositório para preparação de forecasts e pares NMC. O fluxo Python atual centraliza a execução em `mpaswf` e `mpasbflow`. |

Arquivos gerados no workspace BFLOW:

| Arquivo/diretório | Função |
|---|---|
| `manifest.tsv` | Tabela tabulada com `valid_time`, `f048` e `f024`. É o contrato de entrada para o BFLOW e para o `mpasbcov vbal-all`. |
| `inputs/YYYYMMDDHH/f048.nc` | Link para o forecast antigo de 48h válido no horário comum. |
| `inputs/YYYYMMDDHH/f024.nc` | Link para o forecast novo de 24h válido no horário comum. |
| `inputs/YYYYMMDDHH/pair.env` | Metadados do par usado naquele horário válido. |
| `scripts/01_generate_esmf_weights.bash` | Gera pesos ESMF entre grade lat/lon 1 grau e a malha MPAS. |
| `scripts/02_generate_template_ptb.bash` | Cria `template_PTB.nc` contendo `stream_function` e `velocity_potential` com dimensões compatíveis. |
| `scripts/03_convert_uv_to_psichi.bash` | Usa NCL para converter vento reconstruído zonal/meridional em função corrente e potencial de velocidade. |
| `scripts/04_add_variables.py` | Copia/adiciona variáveis físicas e derivadas aos arquivos `FULL_f48.nc` e `FULL_f24.nc`. |
| `scripts/05_ncdiff.py` | Gera `PTB_f48mf24.nc` como `FULL_f48.nc - FULL_f24.nc`. |
| `scripts/06_validate_products.py` | Valida presença e dimensões das variáveis principais. |
| `scripts/run_all_bflow.sh` | Orquestra todas as etapas locais do BFLOW. |
| `output/YYYYMMDDHH/FULL_f48.nc` | Forecast de 48h enriquecido/consolidado para o cálculo da perturbação. |
| `output/YYYYMMDDHH/FULL_f24.nc` | Forecast de 24h enriquecido/consolidado para o cálculo da perturbação. |
| `output/YYYYMMDDHH/PTB_f48mf24.nc` | Amostra NMC final consumida pelo workflow de covariância. |

## 3. Configurações disponíveis

### Argumentos do `mpasbflow prepare` e `mpasbflow all`

| Parâmetro | Onde aparece | Tipo | Significado | Valor atual/usado | Impacto e cuidado |
|---|---|---|---|---|---|
| `--config` | CLI `mpasbflow`; padrão em `bflow.py` | caminho | Arquivo YAML principal. | `configs/jaci-x1.10242.yaml` | Trocar muda todos os caminhos, malha, `nproc`, runtime e PBS. Deve apontar para YAML completo. |
| `--start-valid-time` | CLI `mpasbflow`; smoke | data `YYYY-MM-DD_HH:MM:SS` | Primeiro horário válido das amostras. | `2026-06-10_00:00:00` no smoke | Afeta número de amostras e nomes de workspace. Precisa estar alinhado aos forecasts disponíveis. |
| `--end-valid-time` | CLI `mpasbflow`; smoke | data | Último horário válido, inclusive. | `2026-06-13_00:00:00` no smoke | Mesmo cuidado do início. No smoke gera quatro amostras. |
| `--valid-interval-hours` | CLI `mpasbflow` | inteiro positivo | Passo temporal entre horários válidos. | `24` | Valores não positivos abortam. Para produção, deve representar o plano amostral. |
| `--dt` | CLI `mpasbflow`; `runtime.config_dt` | inteiro, segundos | Passo de tempo MPAS usado para localizar forecasts. | `60` | Deve ser igual ao usado nos forecasts MPAS; inconsistência muda os caminhos esperados. |
| `--manifest` | CLI `mpasbflow` | caminho | Usa pares explícitos em vez de range. | Não usado no smoke documentado | Útil quando as amostras não seguem range regular. O arquivo deve ter colunas `valid_time`, `f048`, `f024`. |
| `--workspace` | CLI `mpasbflow` | caminho | Diretório de trabalho BFLOW. | Por padrão `work_root/bmatrix/bflow_preprocessing/np128_2026061000_2026061300` no caso smoke | Alterar apenas quando for necessário separar experimentos. |
| `--force` | CLI `mpasbflow` | flag | Recria arquivos do workspace. | Usado no comando smoke | Pode sobrescrever scripts/metadados gerados. Não deve ser usado sem rastrear o experimento. |
| `--clean-output` | `mpasbflow all` e `mpasbflow run` | flag | Remove `output/` antes de executar. | Usado no smoke | Seguro para reprocessamento, mas apaga produtos intermediários e finais BFLOW. |
| `--skip-weights` | `mpasbflow all` e `mpasbflow run` | flag | Não regenera pesos ESMF. | Não usado no smoke | Baixo risco se os pesos já existem e são compatíveis com a malha; perigoso se a malha mudou. |

### Parâmetros vindos de `configs/jaci-x1.10242.yaml`

| Parâmetro | Valor atual | Uso no BFLOW |
|---|---:|---|
| `project.work_root` | `/p/projetos/monan_das/joao.gerd/work/mpas-bmatrix-global` | Base do workspace padrão. |
| `mesh.name` | `x1.10242` | Nome da malha usado nos arquivos de peso e nos links estáticos. |
| `mesh.nproc` | `128` | Entra no nome do workspace padrão `np128_...`. |
| `mesh.nvertlevels` | `55` | Não controla diretamente o BFLOW, mas deve ser compatível com os NetCDF gerados. |
| `static.invariant` | caminho para `x1.10242.invariant.nc` | Usado para gerar pesos ESMF. |
| `runtime.config_dt` | `60` | Padrão de `--dt`. |
| `runtime.output_interval` | `24:00:00` | Vem da geração dos forecasts que alimentam o BFLOW. |

### Parâmetros internos gerados pelo código

| Parâmetro | Onde aparece | Valor atual no código | Observação |
|---|---|---|---|
| Grade lat/lon auxiliar | `write_weights_script()` | `1.0deg`, cantos `-89.50/-179.50` a `89.50/179.50` | Fixo no script gerado. Não há opção CLI documentada para alterar. |
| Método ESMF | `write_weights_script()` | `bilinear` | Fixo no script gerado. Alterar exige modificar o código. |
| Conversão `u/v -> psi/chi` | `write_psichi_script()` | `uv2sfvpf` via NCL | Depende de NCL e pesos ESMF. |
| Variáveis copiadas | `write_add_variables_script()` | `surface_pressure`, `uReconstructZonal`, `uReconstructMeridional`, `qv`, hidrometeoros, `pressure_p`, `pressure_base` | Lista fixa no script gerado. |
| Variáveis derivadas | `write_add_variables_script()` | `pressure`, `temperature`, `spechum` | Calculadas a partir de `pressure_p`, `pressure_base`, `theta` e `qv`. |
| Variáveis exigidas no `PTB` | `write_validate_script()` | `stream_function`, `velocity_potential`, `temperature`, `spechum`, `pressure`, `surface_pressure`, `uReconstructZonal`, `uReconstructMeridional` | Se faltarem, a validação falha. |

## 4. Dependências

- Executáveis/comandos: `mpasbflow`, `python`, `ncl`, `ncdump`, `ncks`, `ncap2`, `ncrename`, `ncatted`.
- Bibliotecas Python: `netCDF4`; indiretamente `PyYAML`, `numpy`, `cftime`, `xarray` pelo pacote do workflow.
- Módulos/ambiente: o smoke assume ambiente `mpaswf` e `scripts/load_jaci_env.sh` carregado antes dos comandos principais.
- Dados de entrada: forecasts MPAS `f048` e `f024`, malha/invariant da `x1.10242`, arquivos de stream/physics quando usados pela geração dos forecasts.
- Saídas anteriores: forecasts produzidos por `mpaswf nmc range` ou por etapas equivalentes.
- Recursos computacionais: o BFLOW em si é executado localmente no workspace, mas depende de forecasts previamente produzidos em PBS/MPAS. O custo maior está em NMC/forecast e nas etapas posteriores de covariância.
- Dependência entre processos: alimenta `VBAL`, que lê o `manifest.tsv` e copia os `PTB_f48mf24.nc` para `samples/`.

## 5. Entradas e saídas

### Entradas

```text
manifest.tsv
inputs/YYYYMMDDHH/f048.nc
inputs/YYYYMMDDHH/f024.nc
static.invariant
```

Se o workspace é preparado por range, o próprio `mpasbflow` monta o manifesto a partir dos caminhos retornados por `forecast.bflow_file()`.

### Saídas

```text
output/YYYYMMDDHH/FULL_f48.nc
output/YYYYMMDDHH/FULL_f24.nc
output/YYYYMMDDHH/PTB_f48mf24.nc
logs/run_all_bflow.log
```

O arquivo mais importante é `PTB_f48mf24.nc`. Ele representa a diferença NMC enriquecida com as variáveis que o SABER/MPAS-JEDI usará para calibrar ou aplicar a B.

## 6. Configuração usada neste workflow

Valores extraídos dos arquivos analisados:

```text
config: configs/jaci-x1.10242.yaml
mesh: x1.10242
nproc: 128
nVertLevels: 55
runtime.config_dt: 60
runtime.output_interval: 24:00:00
bmatrix queue: pesqmidi
bmatrix walltime: 02:00:00
```

No smoke validado, o comando registrado é:

```bash
mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --clean-output \
  --force
```

A escolha de quatro amostras é documentada como suficiente para um smoke técnico. Não é uma justificativa de produção; o próprio repositório registra que produção exigiria mais amostras e representatividade temporal.

## 7. Como modificar com segurança

Baixo risco:

- Alterar `--workspace` para separar experimentos.
- Usar `--manifest` quando os pares já foram selecionados manualmente.
- Usar `--skip-weights` somente se a malha e o arquivo `invariant` não mudaram e os pesos já foram gerados.

Exige cuidado:

- Alterar `--dt`; os forecasts esperados mudam de diretório.
- Alterar período e intervalo; isso muda o número de membros consumidos por `VBAL` e `HDIAG`.
- Alterar malha, `nproc`, `invariant` ou arquivos de física; pesos ESMF e partições precisam ser compatíveis.
- Alterar variáveis copiadas/derivadas; etapas posteriores podem falhar por ausência de variáveis.

Validações recomendadas:

```bash
python scripts/06_validate_products.py --stage full
python scripts/06_validate_products.py --stage ptb
find output -name 'PTB_f48mf24.nc' | sort
cat manifest.tsv
```

Depois, validar a próxima etapa:

```bash
mpasbcov vbal-all --config configs/jaci-x1.10242.yaml --bflow-workspace "$BFLOW" --clean --poll-seconds 30
mpasbcov vbal-validate --workspace "$VBAL"
```

## 8. Exemplo de uso

```bash
cd /p/projetos/monan_das/joao.gerd/projects/mpas-bmatrix-global
source scripts/load_jaci_env.sh
conda activate mpaswf

mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --start-valid-time 2026-06-10_00:00:00 \
  --end-valid-time 2026-06-13_00:00:00 \
  --valid-interval-hours 24 \
  --dt 60 \
  --clean-output \
  --force
```

Se o workspace já foi preparado:

```bash
mpasbflow run --workspace "$BFLOW" --clean-output
```

## 9. Problemas comuns e diagnóstico

| Sintoma | Causa provável | Diagnóstico |
|---|---|---|
| `ERRO: arquivo não encontrado: f048/f024` | Forecast MPAS ainda não foi gerado ou caminho do manifesto está errado. | Verificar `manifest.tsv`, `inputs/YYYYMMDDHH/pair.env` e diretórios `runs/forecast_*`. |
| `peso não encontrado` | Pesos ESMF não existem ou foram apagados. | Verificar `ESMF_weights/` e rodar sem `--skip-weights`. |
| `NCL não gerou FULL_f48.nc` | Falha na conversão `u/v -> psi/chi`, NCL ausente ou pesos incompatíveis. | Verificar `logs/run_all_bflow.log` e scripts `uv_to_psichi_*.ncl`. |
| `variável ausente` na validação | Forecast não contém variáveis esperadas ou etapa `04_add_variables.py` falhou. | Rodar `ncdump -h` nos `FULL_*` e no `PTB_f48mf24.nc`. |
| `PTB_f48mf24.nc` ausente | Falha no `05_ncdiff.py`. | Verificar `FULL_f48.nc`, `FULL_f24.nc` e permissões do diretório `output/`. |

## 10. Resumo operacional

- Finalidade: transformar pares NMC `f048/f024` em amostras `PTB_f48mf24.nc`.
- Principal arquivo de código: `src/mpas_workflow/bflow.py`.
- Principais configurações: período válido, intervalo, `dt`, `workspace`, malha, `invariant` e `nproc`.
- Entradas: `f048.nc`, `f024.nc`, `manifest.tsv`, pesos/grade estática.
- Saídas: `FULL_f48.nc`, `FULL_f24.nc`, `PTB_f48mf24.nc`.
- Dependências críticas: forecasts MPAS válidos, NCL, NCO, NetCDF, `static.invariant` e consistência da malha.
